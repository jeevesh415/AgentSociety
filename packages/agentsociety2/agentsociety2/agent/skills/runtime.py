from __future__ import annotations

"""Agent 技能运行时（workspace + skill 执行）。

该模块提供 :class:`~agentsociety2.agent.skills.runtime.AgentSkillRuntime`，用于把 PersonAgent 的
“工作目录隔离、文件读写、thread/tool 日志、skill 激活与执行”等细节集中在一个组件内，
避免 agent 主体过度膨胀。
"""

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import json_repair

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
        """确保 agent 工作目录已初始化并返回其路径。

        :param env_obj: 通常为 env_router；若其包含 ``run_dir`` 属性则以其为基准目录，
            否则退化为当前工作目录。
        :returns: agent 工作目录路径（形如 ``<run_dir>/agents/agent_0001``）。
        """
        if self._agent_work_dir is not None:
            return self._agent_work_dir

        # 优先从 env_router 获取 run_dir
        run_dir = getattr(env_obj, "run_dir", None)
        if run_dir is not None:
            base_path = Path(run_dir)
        else:
            base_path = Path.cwd()

        self._agent_work_dir = (base_path / "agents" / f"agent_{self._agent_id:04d}").resolve()
        self._agent_work_dir.mkdir(parents=True, exist_ok=True)
        return self._agent_work_dir

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        """将相对路径解析到 workspace 内并做越界保护。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        work_dir = self._agent_work_dir
        target = (work_dir / relative_path).resolve()
        if target != work_dir and work_dir not in target.parents:
            raise ValueError(f"Path escapes agent workspace: {relative_path}")
        return target

    def workspace_root(self) -> Path:
        """:returns: workspace 根目录路径。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        return self._agent_work_dir

    def workspace_read(self, relative_path: str) -> str:
        """读取 workspace 内文件内容。

        :param relative_path: 相对 workspace 的路径。
        :returns: 文件文本内容；若文件不存在则返回空字符串。
        """
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def workspace_write(self, relative_path: str, content: str) -> str:
        """写入 workspace 内文件（UTF-8）。

        :param relative_path: 相对 workspace 的路径。
        :param content: 写入内容。
        :returns: 实际写入的绝对路径字符串。
        """
        target = self._resolve_workspace_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def workspace_exists(self, relative_path: str) -> bool:
        """:returns: workspace 内路径是否存在。"""
        target = self._resolve_workspace_path(relative_path)
        return target.exists()

    def workspace_delete(self, relative_path: str) -> bool:
        """删除 workspace 内文件（仅文件，目录不删除）。"""
        target = self._resolve_workspace_path(relative_path)
        if not target.exists() or target.is_dir():
            return False
        target.unlink()
        return True

    def workspace_list(self, relative_path: str = ".") -> list[str]:
        """列出 workspace 内文件（递归）。

        :param relative_path: 相对 workspace 的根路径。
        :returns: 文件相对路径列表（相对 workspace 根）。
        """
        work_dir = self.workspace_root()  # raises RuntimeError if not initialized
        root = self._resolve_workspace_path(relative_path)
        if not root.exists():
            return []
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
        """执行某个 skill（转发到 registry）。

        :param skill_name: skill 名称。
        :param args: 执行参数（由 skill 脚本/协议自行定义）。
        :param codegen_executor: 可选。用于把 skill 内部的 codegen 调度回 env 的执行器。
        :returns: 执行结果字典（由 :class:`~agentsociety2.agent.skills.SkillRegistry` 约定）。
        :raises RuntimeError: workspace 未初始化时抛出。
        """
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
        tick: int,
        t: datetime,
        selected_skills: set[str],
        activated_skills: set[str] | None = None,
    ) -> None:
        """落地当前会话状态到 workspace，并追加到历史记录。

        :param tick: 当前 tick。
        :param t: 当前仿真时间。
        :param selected_skills: 本步可见/可选技能集合。
        :param activated_skills: 可选。已激活技能集合。
        """
        state = {
            "agent_id": self._agent_id,
            "tick": tick,
            "time": t.isoformat(),
            "selected_skills": sorted(selected_skills),
            "activated_skills": sorted(activated_skills or set()),
        }
        self.workspace_write(
            "session_state.json",
            json.dumps(state, ensure_ascii=False, indent=2),
        )
        self.append_session_state_event(state)

    def append_session_state_event(self, state: dict[str, Any]) -> None:
        """追加 session_state 事件到 ``session_state_history.jsonl``。"""
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
        """读取工作目录中的 JSON 文件；空内容返回 default。"""
        raw = self.workspace_read(relative_path)
        if not raw:
            return default
        return json_repair.loads(raw)

    def read_recent_tool_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """读取最近 N 条工具调用日志。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "tool_calls.jsonl"
        if not path.exists():
            return []
        if limit > 0:
            recent_lines: deque[str] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        recent_lines.append(line)
            source = list(recent_lines)
        else:
            with path.open("r", encoding="utf-8") as f:
                source = [line for line in f if line.strip()]
        return [json_repair.loads(line) for line in source]

    def append_thread_message(self, role: str, content: str, tick: int, t: datetime) -> None:
        """追加 thread 消息到 ``thread_messages.jsonl``。"""
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
        """读取最近 N 条 thread 消息并转换为 LLM messages 结构。"""
        if self._agent_work_dir is None:
            raise RuntimeError("Agent workspace is not initialized")
        path = self._agent_work_dir / "thread_messages.jsonl"
        if not path.exists():
            return []
        if limit > 0:
            recent_lines: deque[str] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        recent_lines.append(line)
            recent = list(recent_lines)
        else:
            with path.open("r", encoding="utf-8") as f:
                recent = [line.rstrip("\n") for line in f if line.strip()]
        messages: list[dict[str, str]] = []
        for line in recent:
            if not line.strip():
                continue
            obj = json_repair.loads(line)
            role = str(obj.get("role", "")).strip()
            content = str(obj.get("content", ""))
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

