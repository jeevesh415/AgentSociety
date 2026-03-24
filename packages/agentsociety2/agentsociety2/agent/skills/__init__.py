"""Skills registry (new architecture only).

设计原则：
- skill 能力由 SKILL.md frontmatter + 可选 script 驱动
- 支持 L0/L1/L2 渐进加载
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from agentsociety2.logger import get_logger

logger = get_logger()
_BUILTIN_ROOT = Path(__file__).resolve().parent


@dataclass
class SkillInfo:
    name: str
    description: str = ""
    trigger: str = "on_demand"  # always | on_demand
    script: str = ""
    executor: str = ""  # codegen
    priority: int = 100
    source: str = ""  # builtin | custom | env:<name>
    path: str = ""
    enabled: bool = True
    disable_model_invocation: bool = False
    user_invocable: bool = True
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    provides_state: list[str] = field(default_factory=list)
    skill_md: str = ""
    _skill_md_loaded: bool = False


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillInfo] = {}
        self._builtin_scanned = False
        max_workers = os.getenv("AGENT_SKILL_SUBPROCESS_MAX_WORKERS", "16")
        try:
            worker_count = max(1, int(max_workers))
        except ValueError:
            worker_count = 16
        self._subprocess_semaphore = asyncio.Semaphore(worker_count)

    # ---------- discover ----------
    def scan_builtin(self, root: Path = _BUILTIN_ROOT) -> None:
        if self._builtin_scanned:
            return
        for info in _discover_skills(root, source="builtin"):
            self._skills[info.name] = info
        self._builtin_scanned = True

    def scan_custom(self, workspace_path: str | Path) -> list[str]:
        custom_root = Path(workspace_path) / "custom" / "skills"
        if not custom_root.is_dir():
            return []
        new_names: list[str] = []
        for info in _discover_skills(custom_root, source="custom"):
            self._skills[info.name] = info
            new_names.append(info.name)
        return new_names

    def scan_env_skills(self, skills_dir: Path, env_name: str) -> list[str]:
        if not skills_dir.is_dir():
            return []
        source = f"env:{env_name}"
        new_names: list[str] = []
        for info in _discover_skills(skills_dir, source=source):
            if (
                info.name in self._skills
                and self._skills[info.name].source == "builtin"
            ):
                continue
            self._skills[info.name] = info
            new_names.append(info.name)
        return new_names

    # ---------- list ----------
    def list_all(self) -> list[SkillInfo]:
        return sorted(self._skills.values(), key=lambda s: (s.priority, s.name))

    def list_enabled(self) -> list[SkillInfo]:
        return [s for s in self.list_all() if s.enabled]

    def list_always_on_names(self) -> list[str]:
        return [s.name for s in self.list_enabled() if s.trigger == "always"]

    def list_selection_metadata(
        self, names: list[str] | None = None, only_enabled: bool = True
    ) -> list[dict[str, Any]]:
        base = self.list_enabled() if only_enabled else self.list_all()
        name_set = set(names) if names is not None else None
        result: list[dict[str, Any]] = []
        for info in base:
            if info.disable_model_invocation:
                continue
            if name_set is not None and info.name not in name_set:
                continue
            result.append(
                {
                    "name": info.name,
                    "description": info.description,
                    "trigger": info.trigger,
                    "script": info.script,
                    "executor": info.executor,
                    "priority": info.priority,
                    "requires": list(info.requires),
                    "provides": list(info.provides),
                    "source": info.source,
                }
            )
        return result

    # ---------- read ----------
    def activate(self, name: str) -> str:
        info = self._skills.get(name)
        if not info:
            return ""
        return _ensure_skill_md_loaded(info)

    def read(self, name: str, relative_path: str) -> str:
        info = self._skills.get(name)
        if not info:
            return ""
        skill_root = Path(info.path).resolve()
        target = (skill_root / relative_path).resolve()
        if not target.exists() or not target.is_file():
            return ""
        if skill_root != target and skill_root not in target.parents:
            return ""
        try:
            return target.read_text(encoding="utf-8")
        except Exception:
            return ""

    # ---------- state ----------
    def enable(self, name: str) -> bool:
        info = self._skills.get(name)
        if not info:
            return False
        info.enabled = True
        return True

    def disable(self, name: str) -> bool:
        info = self._skills.get(name)
        if not info:
            return False
        info.enabled = False
        return True

    def get_skill_info(self, name: str, load_content: bool = True) -> SkillInfo | None:
        info = self._skills.get(name)
        if info and load_content:
            _ensure_skill_md_loaded(info)
        return info

    # ---------- execute ----------
    async def execute(
        self,
        skill_name: str,
        args: dict[str, Any],
        agent_work_dir: str | Path,
        timeout_sec: int = 30,
        codegen_executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        info = self._skills.get(skill_name)
        if not info:
            return _error("validation", f"Skill not found: {skill_name}")

        if info.executor == "codegen":
            if codegen_executor is None:
                return _error("validation", "Codegen executor is not available")
            return await codegen_executor(args)

        if not info.script:
            return {
                "ok": True,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "error_type": "none",
                "artifacts": [],
            }

        skill_root = Path(info.path).resolve()
        script_path = (skill_root / info.script).resolve()
        if not script_path.exists() or not script_path.is_file():
            return _error("validation", f"Script not found: {info.script}")
        if skill_root not in script_path.parents:
            return _error("validation", "Script path escapes skill directory")

        work_dir = Path(agent_work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        before_files = {
            str(p.relative_to(work_dir)) for p in work_dir.rglob("*") if p.is_file()
        }

        env = os.environ.copy()
        env["SKILL_NAME"] = skill_name
        env["SKILL_DIR"] = str(skill_root)
        env["AGENT_WORK_DIR"] = str(work_dir)

        async with self._subprocess_semaphore:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                "--args-json",
                json.dumps(args, ensure_ascii=False),
                cwd=str(work_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return _error("timeout", f"Skill execution timed out after {timeout_sec}s")

        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        exit_code = int(proc.returncode or 0)
        after_files = {
            str(p.relative_to(work_dir)) for p in work_dir.rglob("*") if p.is_file()
        }
        artifacts = sorted(after_files - before_files)
        return {
            "ok": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "error_type": "none" if exit_code == 0 else "runtime",
            "artifacts": artifacts,
        }


def _error(error_type: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": message,
        "error_type": error_type,
        "artifacts": [],
    }


def _discover_skills(root: Path, source: str) -> list[SkillInfo]:
    result: list[SkillInfo] = []
    if not root.is_dir():
        return result
    auto_priority = 100
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        # 新架构要求必须有 SKILL.md
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = _parse_frontmatter_from_file(skill_md)
        info = SkillInfo(
            name=str(meta.get("name", child.name)),
            description=str(meta.get("description", "")),
            trigger=_normalize_trigger(meta.get("trigger", "on_demand")),
            script=str(meta.get("script", "")).strip(),
            executor=str(meta.get("executor", "")).strip().lower(),
            priority=_to_int(meta.get("priority"), auto_priority),
            source=source,
            path=str(child.resolve()),
            enabled=True,
            disable_model_invocation=_to_bool(
                meta.get("disable_model_invocation", meta.get("disable-model-invocation"))
            ),
            user_invocable=not _to_bool(
                str(meta.get("user_invocable", meta.get("user-invocable", "true"))).lower()
                in ("false", "0", "no")
            ),
            requires=_to_list(meta.get("requires")),
            provides=_to_list(meta.get("provides")),
            provides_state=_to_list(meta.get("provides_state")),
            _skill_md_loaded=False,
        )
        result.append(info)
        auto_priority += 1
    return result


def _normalize_trigger(raw: Any) -> str:
    val = str(raw or "on_demand").strip().lower()
    if val == "always":
        return "always"
    return "on_demand"


def _to_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in ("true", "1", "yes")


def _to_int(raw: Any, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _to_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        return [s]
    return []


def _ensure_skill_md_loaded(info: SkillInfo) -> str:
    if info._skill_md_loaded:
        return info.skill_md
    path = Path(info.path) / "SKILL.md"
    if path.exists():
        info.skill_md = path.read_text(encoding="utf-8")
    info._skill_md_loaded = True
    return info.skill_md


def _parse_frontmatter_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return {}
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, Any] = {}
    key: str | None = None
    list_acc: list[str] | None = None
    for line in lines[1:]:
        s = line.rstrip("\n")
        stripped = s.strip()
        if stripped == "---":
            break
        if not stripped:
            continue
        if stripped.startswith("- ") and key is not None and list_acc is not None:
            list_acc.append(stripped[2:].strip())
            continue
        if key is not None and list_acc is not None:
            data[key] = list_acc
            key, list_acc = None, None
        if ":" not in stripped:
            continue
        k, _, v = stripped.partition(":")
        k = k.strip()
        v = v.strip()
        if not v:
            key = k
            list_acc = []
        else:
            data[k] = v
    if key is not None and list_acc is not None:
        data[key] = list_acc
    return data


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.scan_builtin()
    return _registry

