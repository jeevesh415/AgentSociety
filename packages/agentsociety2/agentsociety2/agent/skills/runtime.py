from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from agentsociety2.agent.skills import SkillRegistry


class AgentSkillRuntime:
    """独立的 Skill 运行时组件。

    PersonAgent 仅通过组合使用该组件，避免把 skill/workspace 执行细节堆在 agent 主体里。
    """

    def __init__(self, agent_id: int, registry: SkillRegistry) -> None:
        self._agent_id = agent_id
        self._registry = registry
        self._agent_work_dir: Path | None = None

    def ensure_agent_work_dir(self, env_obj: Any) -> Path:
        if self._agent_work_dir is not None:
            return self._agent_work_dir

        base_path: Path | None = None
        if env_obj is not None:
            for module in getattr(env_obj, "env_modules", []):
                workspace_path = getattr(module, "workspace_path", None)
                if workspace_path:
                    base_path = Path(workspace_path)
                    break

        if base_path is None:
            base_path = Path.cwd()

        self._agent_work_dir = (
            base_path / "run_dir" / "agents" / f"agent_{self._agent_id:04d}"
        ).resolve()
        self._agent_work_dir.mkdir(parents=True, exist_ok=True)
        return self._agent_work_dir

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        work_dir = self._agent_work_dir
        target = (work_dir / relative_path).resolve()
        if target != work_dir and work_dir not in target.parents:
            raise ValueError(f"Path escapes agent workspace: {relative_path}")
        return target

    def workspace_root(self) -> Path:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        return self._agent_work_dir

    def workspace_read(self, relative_path: str) -> str:
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def workspace_write(self, relative_path: str, content: str) -> str:
        target = self._resolve_workspace_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def workspace_exists(self, relative_path: str) -> bool:
        target = self._resolve_workspace_path(relative_path)
        return target.exists()

    def workspace_delete(self, relative_path: str) -> bool:
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or target.is_dir():
            return False
        target.unlink()
        return True

    def workspace_list(self, relative_path: str = ".") -> list[str]:
        root = self._resolve_workspace_path(relative_path)
        if not root.exists():
            return []
        work_dir = self.ensure_agent_work_dir(env_obj=None)
        if root.is_file():
            return [str(root.relative_to(work_dir))]
        return sorted(str(p.relative_to(work_dir)) for p in root.rglob("*") if p.is_file())

    def skill_list(self, names: list[str]) -> list[dict[str, Any]]:
        return self._registry.list_selection_metadata(names=names, only_enabled=True)

    def skill_activate(self, name: str) -> str:
        return self._registry.activate(name)

    def skill_read(self, name: str, relative_path: str) -> str:
        return self._registry.read(name, relative_path)

    async def execute(
        self,
        skill_name: str,
        args: dict[str, Any],
        codegen_executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        work_dir = self._agent_work_dir
        return await self._registry.execute(
            skill_name=skill_name,
            args=args,
            agent_work_dir=work_dir,
            codegen_executor=codegen_executor,
        )

    def persist_session_state(
        self,
        selected_skills: set[str],
        tick: int,
        t: datetime,
        need: Any,
        emotion: str,
        intention: str | None,
        activated_skills: set[str] | None = None,
    ) -> None:
        state = {
            "agent_id": self._agent_id,
            "tick": tick,
            "time": t.isoformat(),
            "selected_skills": sorted(selected_skills),
            "activated_skills": sorted(activated_skills or set()),
            "need": need,
            "emotion": emotion,
            "intention": intention,
        }
        self.workspace_write(
            "session_state.json",
            json.dumps(state, ensure_ascii=False, indent=2),
        )
        self.append_session_state_event(state)

    def append_session_state_event(self, state: dict[str, Any]) -> None:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "session_state_history.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(state, ensure_ascii=False) + "\n")

    def append_tool_log(self, entry: dict[str, Any]) -> None:
        """追加单条工具调用日志（jsonl）。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        log_path = self._agent_work_dir / "tool_calls.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def append_step_replay(
        self,
        tick: int,
        t: datetime,
        selected_skills: set[str],
        tool_history: list[dict[str, Any]],
    ) -> None:
        """追加 step 回放记录（jsonl）。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        replay_path = self._agent_work_dir / "step_replay.jsonl"
        record = {
            "tick": tick,
            "time": t.isoformat(),
            "selected_skills": sorted(selected_skills),
            "tool_history": tool_history,
        }
        with replay_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_json(self, relative_path: str, default: Any) -> Any:
        """读取工作目录中的 JSON 文件，失败返回 default。"""
        try:
            raw = self.workspace_read(relative_path)
            if not raw:
                return default
            return json.loads(raw)
        except Exception:
            return default

    def read_recent_tool_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """读取最近 N 条工具调用日志。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "tool_calls.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        recent = lines[-limit:] if limit > 0 else lines
        result: list[dict[str, Any]] = []
        for line in recent:
            try:
                result.append(json.loads(line))
            except Exception:
                continue
        return result

    def append_thread_message(self, role: str, content: str, tick: int, t: datetime) -> None:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "thread_messages.jsonl"
        entry = {
            "tick": tick,
            "time": t.isoformat(),
            "role": role,
            "content": content,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_recent_thread_messages(self, limit: int = 40) -> list[dict[str, str]]:
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "thread_messages.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        recent = lines[-limit:] if limit > 0 else lines
        messages: list[dict[str, str]] = []
        for line in recent:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            role = str(obj.get("role", "")).strip()
            content = str(obj.get("content", ""))
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

