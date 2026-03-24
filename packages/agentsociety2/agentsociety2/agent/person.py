"""PersonAgent: 极简 skills-first agent.

设计目标：
- Person 本身尽可能轻，只保留状态、决策与编排。
- skills/workspace/执行细节全部交给 runtime + registry。
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from agentsociety2.agent.base import AgentBase
from agentsociety2.agent.skills import SkillRegistry, get_skill_registry
from agentsociety2.agent.skills.runtime import AgentSkillRuntime
from agentsociety2.env import RouterBase

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter


class ToolDecision(BaseModel):
    tool_name: str = Field(
        description=(
            "activate_skill|read_skill|execute_skill|workspace_read|workspace_write|workspace_list|enable_skill|disable_skill|bash|glob|grep|codegen|done"
        )
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    summary: str = ""


class PersonAgent(AgentBase):
    """极简 PersonAgent。

    每步执行（Claude-like tool loop）：
    1) 注入 L0 技能目录 + 工作区状态 + 最近工具历史
    2) LLM 逐轮决策工具调用（activate/read/execute/workspace_*）
    3) 达到 done 或轮次上限
    4) 持久化最小会话状态
    """

    @classmethod
    def mcp_description(cls) -> str:
        return (
            "PersonAgent: Minimal skills-first agent. "
            "Uses progressive skill loading and isolated agent workspace."
        )

    def __init__(
        self,
        id: int,
        profile: Any,
        name: Optional[str] = None,
        replay_writer: Optional["ReplayWriter"] = None,
        init_state: Optional[dict[str, Any]] = None,
        **capability_kwargs: Any,
    ):
        super().__init__(id=id, profile=profile, name=name, replay_writer=replay_writer)
        self._agent_state: dict[str, Any] = dict(init_state or {})
        self._capability_kwargs: dict[str, Any] = dict(capability_kwargs)

        # 每个 agent 拿全局 registry 的只读快照，避免 scan_env_skills 互相污染。
        base_registry = get_skill_registry()
        self._skill_registry = SkillRegistry()
        self._skill_registry._skills = copy.deepcopy(base_registry._skills)
        self._skill_registry._builtin_scanned = True
        self._skill_runtime = AgentSkillRuntime(agent_id=id, registry=self._skill_registry)
        self._selectable_skill_names: set[str] = set()
        self._skill_visibility_overrides: dict[str, bool] = {}
        self._activated_skills: set[str] = set()

        self._step_count = 0
        self._last_selected_skills: set[str] = set()
        self._max_tool_rounds = max(1, int(self._capability_kwargs.get("max_tool_rounds", 24)))

    def _all_visible_skill_names(self) -> set[str]:
        return set(self._selectable_skill_names)

    @staticmethod
    def _truncate_text(text: str, max_len: int = 2000) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...<truncated>"

    def _append_tool_result_to_thread(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
        result_obj: dict[str, Any],
    ) -> None:
        payload = json.dumps(result_obj, ensure_ascii=False)
        content = "TOOL_RESULT_JSON:\n" + self._truncate_text(payload, max_len=12000)
        self._skill_runtime.append_thread_message("user", content, tick=tick, t=t)
        thread_messages.append({"role": "user", "content": content})
        if len(thread_messages) > 40:
            del thread_messages[:-40]

    # 危险命令/token 黑名单：阻止破坏性或逃逸操作，其余一律放行
    _BLOCKED_COMMAND_TOKENS = frozenset({
        "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){", "fork bomb",
        "shutdown", "reboot", "poweroff", "halt", "init 0", "init 6",
        "curl", "wget", "nc ", "ncat", "ssh", "scp", "rsync", "ftp",
        "nmap", "telnet", "netcat",
        "sudo", "su ",
        "chmod 777", "chown", "chgrp",
        "> /dev/", ">/dev/",
    })

    async def _run_bash_in_workspace(self, command: str, timeout_sec: int) -> dict[str, Any]:
        command = command.strip()
        if not command:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "empty command"}
        cmd_lower = command.lower()
        for token in self._BLOCKED_COMMAND_TOKENS:
            if token in cmd_lower:
                return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"blocked: contains '{token}'"}
        work_dir = self._skill_runtime.workspace_root()
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            command,
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "timeout"}
        return {
            "ok": int(proc.returncode or 0) == 0,
            "exit_code": int(proc.returncode or 0),
            "stdout": (stdout_b or b"").decode("utf-8", errors="replace"),
            "stderr": (stderr_b or b"").decode("utf-8", errors="replace"),
        }

    async def _run_codegen(self, instruction: str, ctx: dict[str, Any], template_mode: bool) -> dict[str, Any]:
        if self._env is None:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Environment router is not initialized",
                "error_type": "validation",
                "artifacts": [],
            }
        if not instruction.strip():
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Codegen requires instruction",
                "error_type": "validation",
                "artifacts": [],
            }
        try:
            updated_ctx, answer = await self._env.ask(
                ctx=ctx,
                instruction=instruction,
                readonly=False,
                template_mode=template_mode,
            )
        except Exception as e:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "error_type": "runtime",
                "artifacts": [],
            }
        return {
            "ok": True,
            "exit_code": 0,
            "stdout": answer,
            "stderr": "",
            "error_type": "none",
            "artifacts": [],
            "ctx": updated_ctx,
        }

    def _glob_in_workspace(self, pattern: str, root: str) -> dict[str, Any]:
        work_dir = self._skill_runtime.workspace_root()
        root_path = (work_dir / (root or ".")).resolve()
        if root_path != work_dir and work_dir not in root_path.parents:
            raise ValueError("Path escapes agent workspace")
        if not root_path.exists():
            return {"ok": True, "count": 0, "matches": []}
        matches = [
            str(p.relative_to(work_dir))
            for p in root_path.glob(pattern or "**/*")
            if p.is_file()
        ]
        return {"ok": True, "count": len(matches), "matches": sorted(matches)}

    def _grep_in_workspace(self, pattern: str, root: str, file_glob: str) -> dict[str, Any]:
        work_dir = self._skill_runtime.workspace_root()
        root_path = (work_dir / (root or ".")).resolve()
        if root_path != work_dir and work_dir not in root_path.parents:
            raise ValueError("Path escapes agent workspace")
        max_files = 2000
        max_matches = 1000
        max_file_bytes = 2 * 1024 * 1024
        rx = re.compile(pattern)
        walker = root_path.rglob(file_glob) if file_glob else root_path.rglob("*")
        matches: list[dict[str, Any]] = []
        scanned_files = 0
        for p in walker:
            if not p.is_file():
                continue
            scanned_files += 1
            if scanned_files > max_files:
                break
            if p.stat().st_size > max_file_bytes:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    matches.append({"path": str(p.relative_to(work_dir)), "line": i, "text": line})
                    if len(matches) >= max_matches:
                        return {"ok": True, "count": len(matches), "matches": matches, "truncated": True}
        return {"ok": True, "count": len(matches), "matches": matches, "truncated": False}

    def _refresh_selectable_skills(self) -> None:
        enabled = self._skill_registry.list_enabled()
        visible = []
        for s in enabled:
            override = self._skill_visibility_overrides.get(s.name)
            if override is False:
                continue
            visible.append(s)
        # 自由 agent 模式：所有可见技能默认可直接使用，不做预选 gate。
        self._selectable_skill_names = {s.name for s in visible}

    def _persist_agent_config(self) -> None:
        self._skill_runtime.workspace_write(
            "agent_config.json",
            json.dumps(
                {
                    "capabilities": self._capability_kwargs,
                    "state": self._agent_state,
                    "skill_overrides": self._skill_visibility_overrides,
                    "activated_skills": sorted(self._activated_skills),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    async def init(self, env: RouterBase):
        await super().init(env=env)
        self._skill_runtime.ensure_agent_work_dir(self._env)
        existing_cfg = self._skill_runtime.read_json("agent_config.json", {})
        if isinstance(existing_cfg, dict):
            raw = existing_cfg.get("skill_overrides", {})
            if isinstance(raw, dict):
                self._skill_visibility_overrides = {str(k): bool(v) for k, v in raw.items()}
            active_raw = existing_cfg.get("activated_skills", [])
            if isinstance(active_raw, list):
                self._activated_skills = {str(x).strip() for x in active_raw if str(x).strip()}
        self._persist_agent_config()

        # 扫描 custom/skills/ 目录，使用户的自定义 skill 可被发现
        for module in env.env_modules:
            workspace_path = getattr(module, "workspace_path", None)
            if workspace_path:
                self._skill_registry.scan_custom(workspace_path)
                break
        for module in env.env_modules:
            skills_dir = module.get_agent_skills_dir()
            if skills_dir:
                self._skill_registry.scan_env_skills(skills_dir, type(module).__name__)
        self._refresh_selectable_skills()

    async def _tool_loop(
        self,
        tick: int,
        t: datetime,
        selected: set[str],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        logs: list[str] = []
        history: list[dict[str, Any]] = []
        selected = set(selected)
        thread_messages = self._skill_runtime.read_recent_thread_messages(limit=40)
        catalog = self._skill_runtime.skill_list(sorted(self._all_visible_skill_names()))
        agent_identity = {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
        }
        system_prompt = (
            "You are an autonomous person agent. You act by calling tools one at a time.\n"
            f"AgentIdentity(JSON):\n{json.dumps(agent_identity, ensure_ascii=False)}\n\n"
            "# Progressive Skill Disclosure (L0 → L1 → L2)\n"
            "Skills extend your capabilities. You discover them progressively:\n"
            "- **L0 (catalog below)**: You see skill name, description, requires/provides — enough to decide relevance.\n"
            "- **L1 (activate_skill)**: Loads the full SKILL.md — behavioral instructions telling you WHAT to do and HOW.\n"
            "- **L2 (read_skill)**: Read any file inside the skill directory (e.g., script source).\n"
            "- **execute_skill**: Run a skill's subprocess script (only if it has one).\n\n"
            "Workflow: scan the catalog → activate relevant skills → follow their instructions using tools → done.\n"
            "Prompt-only skills (no script) give you instructions; you use bash/codegen/workspace_* to carry them out.\n\n"
            "# Available Tools\n"
            "| Tool | Arguments | Purpose |\n"
            "|------|-----------|----------|\n"
            "| activate_skill | skill_name | Load full SKILL.md (L1) |\n"
            "| read_skill | skill_name, path | Read file in skill dir (L2) |\n"
            "| execute_skill | skill_name, args | Run skill subprocess script |\n"
            "| bash | command, timeout_sec | Run shell command in workspace |\n"
            "| codegen | instruction, ctx | Interact with environment via code generation |\n"
            "| workspace_read | path | Read file in agent workspace |\n"
            "| workspace_write | path, content | Write file in agent workspace |\n"
            "| workspace_list | path | List files in agent workspace |\n"
            "| glob | glob, path | Find files by pattern in workspace |\n"
            "| grep | pattern, glob, path | Search file contents in workspace |\n"
            "| enable_skill | skill_name | Make a disabled skill visible |\n"
            "| disable_skill | skill_name | Hide a skill from selection |\n"
            "| done | (set done=true, summary) | Finish this step |\n\n"
            f"# Skill Catalog (L0)\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
            f"# Already Activated (L1 loaded)\n{json.dumps(sorted(self._activated_skills), ensure_ascii=False)}\n\n"
            "Return valid JSON: {tool_name, arguments, done, summary}."
        )

        for i in range(self._max_tool_rounds):
            prompt = system_prompt if i == 0 else "Continue with next best tool call based on latest TOOL_RESULT_JSON."
            try:
                messages = list(thread_messages)
                messages.append({"role": "user", "content": prompt})
                decision = await self.acompletion_with_pydantic_validation(
                    model_type=ToolDecision,
                    messages=messages,
                    tick=tick,
                    t=t,
                )
                decision_json = json.dumps(decision.model_dump(), ensure_ascii=False)
                self._skill_runtime.append_thread_message("user", prompt, tick=tick, t=t)
                self._skill_runtime.append_thread_message(
                    "assistant",
                    decision_json,
                    tick=tick,
                    t=t,
                )
                thread_messages.append({"role": "user", "content": prompt})
                thread_messages.append({"role": "assistant", "content": decision_json})
                if len(thread_messages) > 40:
                    thread_messages = thread_messages[-40:]
            except Exception as e:
                logs.append(f"tool_loop_error:{e}")
                break

            action = decision.tool_name.strip()
            args = dict(decision.arguments or {})
            skill_name = str(args.get("skill_name", "")).strip()
            if decision.done or action == "done":
                logs.append(f"done:{decision.summary or 'step_complete'}")
                break

            if action == "disable_skill":
                if not skill_name:
                    history.append({"action": action, "ok": False, "error": "empty skill_name"})
                    logs.append("disable_skill:empty")
                    continue
                self._skill_visibility_overrides[skill_name] = False
                selected.discard(skill_name)
                self._activated_skills.discard(skill_name)
                self._persist_agent_config()
                self._refresh_selectable_skills()
                selected &= self._all_visible_skill_names()
                history.append({"action": action, "skill_name": skill_name, "ok": True})
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": True,
                    }
                )
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj={"action": action, "skill_name": skill_name, "ok": True},
                )
                logs.append(f"disable_skill:{skill_name}:ok")
                continue

            if action == "enable_skill":
                if not skill_name:
                    history.append({"action": action, "ok": False, "error": "empty skill_name"})
                    logs.append("enable_skill:empty")
                    continue
                if skill_name not in self._all_visible_skill_names():
                    self._skill_visibility_overrides[skill_name] = True
                    self._persist_agent_config()
                    self._refresh_selectable_skills()
                if skill_name in self._all_visible_skill_names():
                    selected.add(skill_name)
                    history.append({"action": action, "skill_name": skill_name, "ok": True})
                    self._skill_runtime.append_tool_log(
                        {
                            "tick": tick,
                            "time": t.isoformat(),
                            "action": action,
                            "skill_name": skill_name,
                            "ok": True,
                        }
                    )
                    self._append_tool_result_to_thread(
                        thread_messages=thread_messages,
                        tick=tick,
                        t=t,
                        result_obj={"action": action, "skill_name": skill_name, "ok": True},
                    )
                    logs.append(f"enable_skill:{skill_name}:ok")
                else:
                    history.append(
                        {
                            "action": action,
                            "skill_name": skill_name,
                            "ok": False,
                            "error": "skill not visible or not enabled globally",
                        }
                    )
                    logs.append(f"enable_skill:{skill_name}:miss")
                continue

            if action in {"activate_skill", "read_skill", "execute_skill"} and (
                not skill_name or skill_name not in self._all_visible_skill_names()
            ):
                history.append(
                    {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "skill not visible for this agent",
                        "tick": tick,
                    }
                )
                logs.append(f"{action}:{skill_name}:rejected")
                continue

            if action == "activate_skill":
                content = self._skill_runtime.skill_activate(skill_name)
                ok = bool(content)
                if ok:
                    self._activated_skills.add(skill_name)
                    self._persist_agent_config()
                item = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "size": len(content),
                    "content_preview": self._truncate_text(content, max_len=6000),
                }
                history.append(item)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": ok,
                        "size": len(content),
                    }
                )
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj=item,
                )
                logs.append(f"activate:{skill_name}:{'ok' if ok else 'miss'}")
                continue

            if action == "read_skill":
                read_path = str(args.get("path", ""))
                content = self._skill_runtime.skill_read(skill_name, read_path)
                ok = bool(content)
                item = {
                    "action": action,
                    "skill_name": skill_name,
                    "path": read_path,
                    "ok": ok,
                    "size": len(content),
                    "content_preview": self._truncate_text(content, max_len=1200),
                }
                history.append(item)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "path": read_path,
                        "ok": ok,
                        "size": len(content),
                    }
                )
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj=item,
                )
                logs.append(f"read:{skill_name}:{read_path}:{'ok' if ok else 'miss'}")
                continue

            if action == "execute_skill":
                payload = {
                    "tick": tick,
                    "time": t.isoformat(),
                    "profile": self.get_profile(),
                    "agent_state": self._agent_state,
                    "capabilities": self._capability_kwargs,
                    "workspace_files": self._skill_runtime.workspace_list("."),
                }
                payload.update(args.get("args", {}) or {})
                out = await self.execute(skill_name, payload)
                ok = bool(out.get("ok"))
                item = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "error_type": out.get("error_type"),
                    "artifacts": out.get("artifacts", []),
                    "stdout_preview": self._truncate_text(str(out.get("stdout", "")), max_len=1200),
                    "stderr_preview": self._truncate_text(str(out.get("stderr", "")), max_len=1200),
                }
                history.append(item)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": ok,
                        "exit_code": out.get("exit_code"),
                        "error_type": out.get("error_type"),
                        "artifacts": out.get("artifacts", []),
                    }
                )
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj=item,
                )
                logs.append(f"execute:{skill_name}:{'ok' if ok else 'fail'}")
                continue

            if action == "workspace_read":
                ws_read_path = str(args.get("path", ""))
                try:
                    content = self._skill_runtime.workspace_read(ws_read_path)
                    item = {
                        "action": action,
                        "path": ws_read_path,
                        "ok": True,
                        "size": len(content),
                        "content_preview": self._truncate_text(content, max_len=1200),
                    }
                except Exception as e:
                    item = {"action": action, "path": ws_read_path, "ok": False, "error": str(e)}
                history.append(item)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **item})
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj=item,
                )
                logs.append(f"workspace_read:{ws_read_path}:{'ok' if item.get('ok') else 'fail'}")
                continue

            if action == "workspace_write":
                path = str(args.get("path", ""))
                content = str(args.get("content", ""))
                try:
                    self._skill_runtime.workspace_write(path, content)
                    item = {
                        "action": action,
                        "path": path,
                        "ok": True,
                        "size": len(content),
                    }
                    history.append(item)
                    self._skill_runtime.append_tool_log(
                        {
                            "tick": tick,
                            "time": t.isoformat(),
                            "action": action,
                            "path": path,
                            "ok": True,
                            "size": len(content),
                        }
                    )
                    self._append_tool_result_to_thread(
                        thread_messages=thread_messages,
                        tick=tick,
                        t=t,
                        result_obj=item,
                    )
                    logs.append(f"workspace_write:{path}:ok")
                except Exception as e:
                    item = {"action": action, "path": path, "ok": False, "error": str(e)}
                    history.append(item)
                    self._skill_runtime.append_tool_log(
                        {
                            "tick": tick,
                            "time": t.isoformat(),
                            "action": action,
                            "path": path,
                            "ok": False,
                            "error": str(e),
                        }
                    )
                    self._append_tool_result_to_thread(
                        thread_messages=thread_messages,
                        tick=tick,
                        t=t,
                        result_obj=item,
                    )
                    logs.append(f"workspace_write:{path}:fail")
                continue

            if action == "workspace_list":
                path = str(args.get("path", ".") or ".")
                files = self._skill_runtime.workspace_list(path)
                item = {
                    "action": action,
                    "path": path,
                    "ok": True,
                    "count": len(files),
                    "files_preview": files[:100],
                }
                history.append(item)
                self._skill_runtime.append_tool_log(
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "path": path,
                        "ok": True,
                        "count": len(files),
                    }
                )
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages,
                    tick=tick,
                    t=t,
                    result_obj=item,
                )
                logs.append(f"workspace_list:{path}:{len(files)}")
                continue

            if action == "bash":
                command = str(args.get("command", "")).strip()
                timeout_sec = int(args.get("timeout_sec", 20))
                timeout_sec = max(1, min(120, timeout_sec))
                out = await self._run_bash_in_workspace(command=command, timeout_sec=timeout_sec)
                ok = bool(out.get("ok"))
                item = {
                    "action": action,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "stdout": self._truncate_text(str(out.get("stdout", "")), max_len=5000),
                    "stderr": self._truncate_text(str(out.get("stderr", "")), max_len=2000),
                }
                history.append(item)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **item})
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages, tick=tick, t=t, result_obj=item
                )
                logs.append(f"bash:{'ok' if ok else 'fail'}")
                continue

            if action == "glob":
                try:
                    parsed = self._glob_in_workspace(
                        pattern=str(args.get("glob", "**/*")),
                        root=str(args.get("path", ".")),
                    )
                    item = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    item = {"action": action, "ok": False, "error": str(e)}
                history.append(item)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **item})
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages, tick=tick, t=t, result_obj=item
                )
                logs.append(f"glob:{'ok' if item.get('ok') else 'fail'}")
                continue

            if action == "grep":
                try:
                    parsed = self._grep_in_workspace(
                        pattern=str(args.get("pattern", "")),
                        root=str(args.get("path", ".")),
                        file_glob=str(args.get("glob", "")),
                    )
                    item = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    item = {"action": action, "ok": False, "error": str(e)}
                history.append(item)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **item})
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages, tick=tick, t=t, result_obj=item
                )
                logs.append(f"grep:{'ok' if item.get('ok') else 'fail'}")
                continue

            if action == "codegen":
                instruction = str(args.get("instruction", ""))
                ctx = dict(args.get("ctx", {}))
                template_mode = bool(args.get("template_mode", False))
                out = await self._run_codegen(
                    instruction=instruction,
                    ctx=ctx,
                    template_mode=template_mode,
                )
                ok = bool(out.get("ok"))
                item = {
                    "action": action,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "stdout": self._truncate_text(str(out.get("stdout", "")), max_len=5000),
                    "stderr": self._truncate_text(str(out.get("stderr", "")), max_len=2000),
                }
                history.append(item)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **item})
                self._append_tool_result_to_thread(
                    thread_messages=thread_messages, tick=tick, t=t, result_obj=item
                )
                logs.append(f"codegen:{'ok' if ok else 'fail'}")
                continue

            history.append({"action": action, "ok": False, "error": "unsupported action"})
            logs.append(f"unsupported:{action}")

        return logs, history

    async def execute(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
        return await self._skill_runtime.execute(skill_name=skill_name, args=args)

    async def step(self, tick: int, t: datetime) -> str:
        self._step_count += 1
        selected = set(self._selectable_skill_names)
        self._last_selected_skills = selected
        logs, tool_history = await self._tool_loop(tick=tick, t=t, selected=selected)

        self._skill_runtime.persist_session_state(
            selected_skills=selected,
            tick=tick,
            t=t,
            need=None,
            emotion="unknown",
            intention=None,
            activated_skills=self._activated_skills,
        )
        self._skill_runtime.append_step_replay(
            tick=tick,
            t=t,
            selected_skills=selected,
            tool_history=tool_history,
        )
        if not logs:
            return "no-action"
        return " | ".join(logs)

    async def ask(self, message: str, readonly: bool = True) -> str:
        if self._env is not None:
            _, answer = await self.ask_with_env({"id": self.id}, message, readonly=readonly)
            return answer
        return message

    async def dump(self) -> dict:
        return {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
            "step_count": self._step_count,
            "last_selected_skills": sorted(self._last_selected_skills),
        }

    async def load(self, dump_data: dict):
        self._step_count = int(dump_data.get("step_count", 0))
        self._last_selected_skills = set(dump_data.get("last_selected_skills", []))

