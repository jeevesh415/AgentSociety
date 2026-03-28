"""PersonAgent — 每个 Person 就是一个独立的 Claude-like tool-using agent。

每个 agent 拥有独立工作区、独立会话线程，通过 skill catalog + 工具调用自主完成任务。
skill 作者只需要写 SKILL.md（+ 可选 subprocess 脚本），无需了解 PersonAgent 内部。
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from agentsociety2.agent.base import AgentBase
from agentsociety2.agent.skills import SkillRegistry, get_skill_registry
from agentsociety2.agent.skills.runtime import AgentSkillRuntime
from agentsociety2.env import RouterBase
from agentsociety2.storage import ColumnDef, ReplayDatasetSpec, TableSchema

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
    """每个 Person = 一个独立的 Claude-like agent。

    每步：system prompt 注入身份+技能目录+工具表 → LLM 逐轮选工具 → 结果回写 thread → done 结束。
    """

    _ANALYSIS_RUN_SCHEMA = TableSchema(
        name="agent_skill_run",
        columns=[
            ColumnDef("agent_id", "INTEGER", nullable=False),
            ColumnDef("agent_name", "TEXT", nullable=False),
            ColumnDef("agent_type", "TEXT", nullable=False),
            ColumnDef("started_at", "TIMESTAMP", nullable=False),
            ColumnDef("ended_at", "TIMESTAMP"),
            ColumnDef("workspace_dir", "TEXT", nullable=False),
            ColumnDef("profile_json", "JSON", nullable=False),
            ColumnDef("capabilities_json", "JSON", nullable=False),
            ColumnDef("core_skills_json", "JSON", nullable=False),
            ColumnDef("initial_state_json", "JSON", nullable=False),
        ],
        primary_key=["agent_id"],
        indexes=[["started_at"]],
    )
    _ANALYSIS_STEP_SCHEMA = TableSchema(
        name="agent_skill_step",
        columns=[
            ColumnDef("agent_id", "INTEGER", nullable=False),
            ColumnDef("step", "INTEGER", nullable=False),
            ColumnDef("t", "TIMESTAMP", nullable=False),
            ColumnDef("selected_skills_json", "JSON", nullable=False),
            ColumnDef("activated_skills_json", "JSON", nullable=False),
            ColumnDef("current_goal", "TEXT"),
            ColumnDef("current_plan_summary", "TEXT"),
            ColumnDef("last_decision_summary", "TEXT"),
            ColumnDef("step_result", "TEXT", nullable=False),
            ColumnDef("tool_round_count", "INTEGER", nullable=False),
            ColumnDef("workspace_change_summary_json", "JSON", nullable=False),
            ColumnDef("state_json", "JSON", nullable=False),
        ],
        primary_key=["agent_id", "step"],
        indexes=[["step"], ["t"]],
    )
    _ANALYSIS_EVENT_SCHEMA = TableSchema(
        name="agent_skill_event",
        columns=[
            ColumnDef("agent_id", "INTEGER", nullable=False),
            ColumnDef("event_order", "INTEGER", nullable=False),
            ColumnDef("step", "INTEGER"),
            ColumnDef("t", "TIMESTAMP", nullable=False),
            ColumnDef("event_type", "TEXT", nullable=False),
            ColumnDef("summary", "TEXT", nullable=False),
            ColumnDef("payload_json", "JSON", nullable=False),
        ],
        primary_key=["agent_id", "event_order"],
        indexes=[["step"], ["t"], ["event_type"]],
    )

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

        # 每个 agent 拿全局 registry 的深拷贝快照，避免 scan_env_skills 互相污染。
        base_registry = get_skill_registry()
        self._skill_registry = SkillRegistry()
        self._skill_registry._skills = copy.deepcopy(base_registry._skills)
        self._skill_registry._builtin_scanned = True
        self._skill_runtime = AgentSkillRuntime(agent_id=id, registry=self._skill_registry)
        self._selectable_skill_names: set[str] = set()
        self._skill_visibility_overrides: dict[str, bool] = {}
        self._activated_skills: set[str] = set()
        # Claude-like capability disclosure: only a small core set is visible by default.
        default_core = {"observation", "needs", "cognition", "plan", "memory"}
        core = self._capability_kwargs.get("core_skills", None)
        if isinstance(core, (list, set, tuple)):
            self._core_skill_names: set[str] = {str(x).strip() for x in core if str(x).strip()}
        else:
            self._core_skill_names = set(default_core)

        self._step_count = 0
        self._last_selected_skills: set[str] = set()
        self._max_tool_rounds = max(1, int(self._capability_kwargs.get("max_tool_rounds", 24)))
        self._analysis_started_at: datetime | None = None
        self._analysis_tables_registered = False
        self._analysis_run_written = False
        self._analysis_event_order = 0

    def _all_visible_skill_names(self) -> set[str]:
        return set(self._selectable_skill_names)

    @staticmethod
    def _truncate_text(text: str, max_len: int = 2000) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...<truncated>"

    @staticmethod
    def _should_enable_template_mode(instruction: str, ctx: dict[str, Any]) -> bool:
        variables = ctx.get("variables")
        if isinstance(variables, dict) and variables:
            return True
        return bool(re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", instruction))

    # ── System Prompt ──────────────────────────────────────────────────────────

    def get_system_prompt(self, tick: int, t: datetime) -> str:
        """每轮注入完整上下文到 system role（对标 Claude Code 的行为）。"""
        base = super().get_system_prompt(tick, t)

        agent_identity = {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
        }

        try:
            catalog = self._skill_runtime.skill_list(sorted(self._all_visible_skill_names()))
        except Exception:
            catalog = []

        skill_section = (
            f"\n\n# Agent Identity\n"
            f"{json.dumps(agent_identity, ensure_ascii=False)}\n\n"
            "# You Are an Autonomous Tool-Using Agent\n"
            "Call tools one at a time. "
            "Respond ONLY with valid JSON: {tool_name, arguments, done, summary}.\n\n"
            "# Skills\n"
            "The catalog below lists available skills (name + description). "
            "Use `activate_skill` to load a skill's full instructions, then follow them.\n\n"
            "# Tools\n"
            "| Tool | Arguments | Purpose |\n"
            "|------|-----------|----------|\n"
            "| activate_skill | skill_name | Load skill instructions |\n"
            "| read_skill | skill_name, path | Read a file inside a skill directory |\n"
            "| execute_skill | skill_name, args | Run a skill's subprocess script |\n"
            "| bash | command, timeout_sec | Shell command in workspace |\n"
            "| codegen | instruction, ctx, template_mode | Send instruction to the environment; use template_mode=true for repeatable calls |\n"
            "| workspace_read | path | Read file |\n"
            "| workspace_write | path, content | Write file |\n"
            "| workspace_list | path | List files |\n"
            "| glob | glob, path | Find files by pattern |\n"
            "| grep | pattern, glob, path | Search file contents |\n"
            "| enable_skill | skill_name | Reveal a hidden skill |\n"
            "| disable_skill | skill_name | Hide a skill |\n"
            "| done | (done=true, summary) | Finish this step |\n\n"
            "For repeatable environment calls, keep `instruction` stable, put changing values in "
            "`ctx.variables`, and set `template_mode=true` on `codegen` so the router can reuse cached code.\n\n"
            f"# Skill Catalog\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
            f"# Activated Skills\n{json.dumps(sorted(self._activated_skills), ensure_ascii=False)}"
        )

        return base + skill_section

    # ── Thread Management ─────────────────────────────────────────────────────

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

    # ── Skill Dependency ──────────────────────────────────────────────────────

    def _ensure_requires_activated(
        self,
        tick: int,
        t: datetime,
        thread_messages: list[dict[str, str]],
        skill_name: str,
    ) -> dict[str, Any]:
        """确保 skill 的 requires 依赖都已激活。"""
        info = self._skill_registry.get_skill_info(skill_name, load_content=False)
        requires = list(getattr(info, "requires", []) or []) if info else []
        if not requires:
            return {"ok": True, "requires": [], "activated": []}

        missing: list[str] = []
        activated: list[str] = []
        for dep in requires:
            dep = str(dep).strip()
            if not dep:
                continue
            if dep not in self._all_visible_skill_names():
                missing.append(dep)
                continue
            if dep in self._activated_skills:
                continue
            content = self._skill_runtime.skill_activate(dep)
            if content:
                self._activated_skills.add(dep)
                activated.append(dep)

        if activated:
            self._persist_agent_config()
            self._append_tool_result_to_thread(
                thread_messages=thread_messages,
                tick=tick,
                t=t,
                result_obj={
                    "action": "auto_activate_requires",
                    "skill_name": skill_name,
                    "ok": True,
                    "requires": requires,
                    "activated": activated,
                },
            )

        if missing:
            return {"ok": False, "requires": requires, "activated": activated, "missing": missing}
        return {"ok": True, "requires": requires, "activated": activated}

    # ── Command Execution ─────────────────────────────────────────────────────

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
        # 基于“默认信任本机”的轻量护栏：
        # - 禁止绝对路径，避免直接读写系统文件
        # - 禁止 ../ 访问上级目录，避免越出 agent workspace 语义
        if re.search(r"(^|[\s'\"();|&])\/", command):
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "blocked: absolute path"}
        if "../" in command or "/.." in command or "..\\" in command:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "blocked: parent traversal"}
        cmd_lower = command.lower()
        for token in self._BLOCKED_COMMAND_TOKENS:
            if token in cmd_lower:
                return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"blocked: contains '{token}'"}
        work_dir = self._skill_runtime.workspace_root()
        # 使用 bash -c 而非 bash -lc，避免加载用户 profile 引入不确定的 alias/env
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
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
            return {"ok": False, "stdout": "", "stderr": "environment not initialized"}
        if not instruction.strip():
            return {"ok": False, "stdout": "", "stderr": "empty instruction"}
        try:
            updated_ctx, answer = await self._env.ask(
                ctx=ctx,
                instruction=instruction,
                readonly=False,
                template_mode=template_mode,
            )
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": str(e)}
        return {"ok": True, "stdout": answer, "stderr": "", "ctx": updated_ctx}

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

    # ── Skill Visibility ──────────────────────────────────────────────────────

    def _refresh_selectable_skills(self) -> None:
        enabled = self._skill_registry.list_enabled()
        visible = []
        for s in enabled:
            override = self._skill_visibility_overrides.get(s.name)
            if override is False:
                continue
            if override is not True and s.name not in self._core_skill_names:
                continue
            visible.append(s)
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
                    "core_skills": sorted(self._core_skill_names),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    async def _ensure_analysis_tables_registered(self) -> None:
        if self._replay_writer is None or self._analysis_tables_registered:
            return
        await self._replay_writer.register_table(self._ANALYSIS_RUN_SCHEMA)
        await self._replay_writer.register_table(self._ANALYSIS_STEP_SCHEMA)
        await self._replay_writer.register_table(self._ANALYSIS_EVENT_SCHEMA)
        await self._replay_writer.register_dataset(
            ReplayDatasetSpec(
                dataset_id="agent.analysis_run",
                table_name=self._ANALYSIS_RUN_SCHEMA.name,
                module_name=type(self).__name__,
                kind="metric_series",
                title="Agent Analysis Run",
                description="Per-agent analysis workspace/session metadata exported by PersonAgent.",
                entity_key="agent_id",
                step_key=None,
                time_key="started_at",
                default_order=["agent_id"],
                capabilities=["agent_analysis", "analysis_run"],
            ),
            self._ANALYSIS_RUN_SCHEMA.columns,
        )
        await self._replay_writer.register_dataset(
            ReplayDatasetSpec(
                dataset_id="agent.analysis_step",
                table_name=self._ANALYSIS_STEP_SCHEMA.name,
                module_name=type(self).__name__,
                kind="entity_snapshot",
                title="Agent Analysis Step",
                description="Per-agent, per-step analysis trace exported by PersonAgent.",
                entity_key="agent_id",
                step_key="step",
                time_key="t",
                default_order=["step", "agent_id"],
                capabilities=["agent_analysis", "timeseries", "analysis_step"],
            ),
            self._ANALYSIS_STEP_SCHEMA.columns,
        )
        await self._replay_writer.register_dataset(
            ReplayDatasetSpec(
                dataset_id="agent.analysis_event",
                table_name=self._ANALYSIS_EVENT_SCHEMA.name,
                module_name=type(self).__name__,
                kind="event_stream",
                title="Agent Analysis Event",
                description="Structured analysis events exported by PersonAgent during tool-driven execution.",
                entity_key="agent_id",
                step_key="step",
                time_key="t",
                default_order=["t", "event_order"],
                capabilities=["agent_analysis", "event_stream", "analysis_event"],
            ),
            self._ANALYSIS_EVENT_SCHEMA.columns,
        )
        self._analysis_tables_registered = True

    def _analysis_workspace_dir(self) -> str:
        try:
            return str(self._skill_runtime.workspace_root())
        except Exception:
            return ""

    def _resolve_agent_state_field(self, *candidates: str) -> Optional[str]:
        for key in candidates:
            value = self._agent_state.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    async def _write_analysis_run(self, ended_at: datetime | None = None) -> None:
        if self._replay_writer is None:
            return
        await self._ensure_analysis_tables_registered()
        started_at = self._analysis_started_at or datetime.now()
        await self._replay_writer.write(
            self._ANALYSIS_RUN_SCHEMA.name,
            {
                "agent_id": self.id,
                "agent_name": self._name,
                "agent_type": type(self).__name__,
                "started_at": started_at,
                "ended_at": ended_at,
                "workspace_dir": self._analysis_workspace_dir(),
                "profile_json": self.get_profile(),
                "capabilities_json": self._capability_kwargs,
                "core_skills_json": sorted(self._core_skill_names),
                "initial_state_json": self._agent_state,
            },
        )
        self._analysis_run_written = True

    async def _ensure_analysis_run_written(self) -> None:
        if self._analysis_run_written:
            return
        await self._write_analysis_run()
        await self._emit_analysis_event(
            event_type="lifecycle.init",
            step=None,
            t=self._analysis_started_at or datetime.now(),
            summary="agent initialized for analysis export",
            payload={
                "workspace_dir": self._analysis_workspace_dir(),
                "core_skills": sorted(self._core_skill_names),
            },
        )

    async def _emit_analysis_event(
        self,
        event_type: str,
        step: Optional[int],
        t: datetime,
        summary: str,
        payload: dict[str, Any],
    ) -> None:
        if self._replay_writer is None:
            return
        await self._ensure_analysis_tables_registered()
        self._analysis_event_order += 1
        await self._replay_writer.write(
            self._ANALYSIS_EVENT_SCHEMA.name,
            {
                "agent_id": self.id,
                "event_order": self._analysis_event_order,
                "step": step,
                "t": t,
                "event_type": event_type,
                "summary": summary,
                "payload_json": payload,
            },
        )

    def _summarize_workspace_changes(self, tool_history: list[dict[str, Any]]) -> dict[str, Any]:
        writes: list[dict[str, Any]] = []
        action_counts: dict[str, int] = {}
        for item in tool_history:
            action = str(item.get("action", "")).strip()
            if action:
                action_counts[action] = action_counts.get(action, 0) + 1
            if action == "workspace_write" and item.get("ok"):
                writes.append(
                    {
                        "path": str(item.get("path", "")),
                        "size": int(item.get("size", 0) or 0),
                    }
                )
        return {
            "write_count": len(writes),
            "written_paths": [w["path"] for w in writes],
            "written_files": writes,
            "action_counts": action_counts,
        }

    def _extract_done_summary(self, logs: list[str]) -> Optional[str]:
        for entry in reversed(logs):
            if entry.startswith("done:"):
                summary = entry.split(":", 1)[1].strip()
                return summary or None
        return None

    async def _write_analysis_step(
        self,
        t: datetime,
        logs: list[str],
        tool_history: list[dict[str, Any]],
    ) -> None:
        if self._replay_writer is None:
            return
        await self._ensure_analysis_run_written()

        workspace_change_summary = self._summarize_workspace_changes(tool_history)
        done_summary = self._extract_done_summary(logs)
        step_result = "no-action" if not logs else " | ".join(logs)
        state_json = {
            "step_count": self._step_count,
            "selected_skills": sorted(self._selectable_skill_names),
            "activated_skills": sorted(self._activated_skills),
            "last_selected_skills": sorted(self._last_selected_skills),
            "skill_overrides": self._skill_visibility_overrides,
            "core_skills": sorted(self._core_skill_names),
            "agent_state": self._agent_state,
            "tool_actions": [str(item.get("action", "")) for item in tool_history if item.get("action")],
            "logs": logs,
            "workspace_change_summary": workspace_change_summary,
        }
        await self._replay_writer.write(
            self._ANALYSIS_STEP_SCHEMA.name,
            {
                "agent_id": self.id,
                "step": self._step_count,
                "t": t,
                "selected_skills_json": sorted(self._selectable_skill_names),
                "activated_skills_json": sorted(self._activated_skills),
                "current_goal": self._resolve_agent_state_field("current_goal", "goal"),
                "current_plan_summary": self._resolve_agent_state_field("current_plan_summary", "plan_summary"),
                "last_decision_summary": done_summary or self._resolve_agent_state_field("last_decision_summary"),
                "step_result": step_result,
                "tool_round_count": len(tool_history),
                "workspace_change_summary_json": workspace_change_summary,
                "state_json": state_json,
            },
        )
        event_type = "step.error" if any(log.startswith("tool_loop_error:") for log in logs) else "step.summary"
        await self._emit_analysis_event(
            event_type=event_type,
            step=self._step_count,
            t=t,
            summary=done_summary or step_result,
            payload={
                "tool_round_count": len(tool_history),
                "selected_skills": sorted(self._selectable_skill_names),
                "activated_skills": sorted(self._activated_skills),
                "workspace_change_summary": workspace_change_summary,
            },
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self, env: RouterBase):
        await super().init(env=env)
        self._skill_runtime.ensure_agent_work_dir(self._env)
        self._analysis_started_at = datetime.now()
        existing_cfg = self._skill_runtime.read_json("agent_config.json", {})
        if isinstance(existing_cfg, dict):
            raw = existing_cfg.get("skill_overrides", {})
            if isinstance(raw, dict):
                self._skill_visibility_overrides = {str(k): bool(v) for k, v in raw.items()}
            active_raw = existing_cfg.get("activated_skills", [])
            if isinstance(active_raw, list):
                self._activated_skills = {str(x).strip() for x in active_raw if str(x).strip()}
            core_raw = existing_cfg.get("core_skills", None)
            if isinstance(core_raw, list):
                loaded = {str(x).strip() for x in core_raw if str(x).strip()}
                if loaded:
                    self._core_skill_names = loaded
        self._persist_agent_config()

        # 扫描 custom/skills/ 和环境模块提供的 skills
        for module in env.env_modules:
            workspace_path = getattr(module, "workspace_path", None)
            if workspace_path:
                self._skill_registry.scan_custom(workspace_path)
                break
        for module in env.env_modules:
            skills_dir = module.get_agent_skills_dir()
            if skills_dir:
                added = self._skill_registry.scan_env_skills(skills_dir, type(module).__name__)
                # 环境 skill 
                self._core_skill_names.update(added)
        self._refresh_selectable_skills()
        if self._replay_writer is not None:
            await self._ensure_analysis_run_written()

    # ── Context Compaction (sliding summary) ─────────────────────────────────

    async def _compact_thread_if_needed(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
    ) -> list[dict[str, str]]:
        """当 thread 过长时，用 LLM 对旧消息做摘要，保留最近消息。

        对标 Claude Code 的 context window management：旧对话压缩为摘要，
        最近 N 条消息原样保留，确保不超模型上下文窗口。
        """
        max_chars = int(self._capability_kwargs.get("thread_compact_chars", 24000))
        keep_recent = int(self._capability_kwargs.get("thread_keep_recent", 6))

        total_chars = sum(len(m.get("content", "")) for m in thread_messages)
        if total_chars <= max_chars or len(thread_messages) <= keep_recent + 2:
            return thread_messages

        split_idx = len(thread_messages) - keep_recent
        old_messages = thread_messages[:split_idx]
        recent_messages = thread_messages[split_idx:]

        digest_parts = []
        char_budget = 6000
        used = 0
        for m in old_messages:
            chunk = f"[{m['role']}]: {m['content'][:300]}"
            if used + len(chunk) > char_budget:
                digest_parts.append("... (earlier messages omitted)")
                break
            digest_parts.append(chunk)
            used += len(chunk)

        summary_prompt: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Summarize the following agent conversation history into a concise paragraph (3-5 sentences). "
                    "Focus on: key decisions made, important tool results, current agent state, "
                    "and any workspace files written. Be brief and factual."
                ),
            },
            {"role": "user", "content": "\n---\n".join(digest_parts)},
        ]

        try:
            response = await self.acompletion(summary_prompt, stream=False)  # type: ignore
            summary_text = response.choices[0].message.content or ""
            summary_text = summary_text.strip() or f"[Compacted {len(old_messages)} earlier messages]"
        except Exception:
            summary_text = f"[Compacted {len(old_messages)} earlier messages]"

        compacted = [{"role": "user", "content": f"CONVERSATION_SUMMARY:\n{summary_text}"}]
        compacted.extend(recent_messages)
        return compacted

    # ── Tool Loop ─────────────────────────────────────────────────────────────

    async def _tool_loop(
        self,
        tick: int,
        t: datetime,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """每轮 LLM 决策 → 执行工具 → 结果回写 thread → 循环。"""
        logs: list[str] = []
        history: list[dict[str, Any]] = []
        thread_messages = self._skill_runtime.read_recent_thread_messages(limit=40)

        for i in range(self._max_tool_rounds):
            # 滑动摘要：当 thread 过长时压缩旧消息
            thread_messages = await self._compact_thread_if_needed(thread_messages, tick, t)

            prompt = (
                "Begin your step. Review the skill catalog, activate relevant skills, "
                "and complete your objectives."
                if i == 0
                else "Continue. Call the next best tool based on the latest "
                "TOOL_RESULT_JSON, or set done=true if finished."
            )
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
                self._skill_runtime.append_thread_message("assistant", decision_json, tick=tick, t=t)
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

            # ── disable_skill ──
            if action == "disable_skill":
                if not skill_name:
                    result_obj = {"action": action, "ok": False, "error": "empty skill_name"}
                    history.append(result_obj)
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append("disable_skill:empty")
                    continue
                self._skill_visibility_overrides[skill_name] = False
                self._activated_skills.discard(skill_name)
                self._persist_agent_config()
                self._refresh_selectable_skills()
                result_obj = {"action": action, "skill_name": skill_name, "ok": True}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"disable_skill:{skill_name}:ok")
                continue

            # ── enable_skill ──
            if action == "enable_skill":
                if not skill_name:
                    result_obj = {"action": action, "ok": False, "error": "empty skill_name"}
                    history.append(result_obj)
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append("enable_skill:empty")
                    continue
                if skill_name not in self._all_visible_skill_names():
                    self._skill_visibility_overrides[skill_name] = True
                    self._persist_agent_config()
                    self._refresh_selectable_skills()
                if skill_name in self._all_visible_skill_names():
                    result_obj = {"action": action, "skill_name": skill_name, "ok": True}
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append(f"enable_skill:{skill_name}:ok")
                else:
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "skill not found in registry",
                    }
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append(f"enable_skill:{skill_name}:miss")
                continue

            # ── skill visibility gate ──
            if action in {"activate_skill", "read_skill", "execute_skill"} and (
                not skill_name or skill_name not in self._all_visible_skill_names()
            ):
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": False,
                    "error": "skill not visible for this agent",
                }
                history.append(result_obj)
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"{action}:{skill_name}:rejected")
                continue

            # ── activate_skill ──
            if action == "activate_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick, t=t, thread_messages=thread_messages, skill_name=skill_name,
                )
                if not dep_status.get("ok"):
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "missing required skills",
                        "missing": dep_status.get("missing", []),
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append(f"activate:{skill_name}:blocked_requires")
                    continue

                content = self._skill_runtime.skill_activate(skill_name)
                ok = bool(content)
                if ok:
                    self._activated_skills.add(skill_name)
                    self._persist_agent_config()
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "content": content,
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), "action": action,
                     "skill_name": skill_name, "ok": ok, "size": len(content)}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"activate:{skill_name}:{'ok' if ok else 'miss'}")
                continue

            # ── read_skill ──
            if action == "read_skill":
                read_path = str(args.get("path", ""))
                content = self._skill_runtime.skill_read(skill_name, read_path)
                ok = bool(content)
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "path": read_path,
                    "ok": ok,
                    "content": self._truncate_text(content, max_len=8000),
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), "action": action,
                     "skill_name": skill_name, "path": read_path, "ok": ok, "size": len(content)}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"read:{skill_name}:{read_path}:{'ok' if ok else 'miss'}")
                continue

            # ── execute_skill ──
            if action == "execute_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick, t=t, thread_messages=thread_messages, skill_name=skill_name,
                )
                if not dep_status.get("ok"):
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "missing required skills",
                        "missing": dep_status.get("missing", []),
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append(f"execute:{skill_name}:blocked_requires")
                    continue

                payload = dict(args.get("args", {}) or {})
                payload.setdefault("tick", tick)
                payload.setdefault("time", t.isoformat())
                out = await self.execute(skill_name, payload)
                ok = bool(out.get("ok"))
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "error_type": out.get("error_type"),
                    "artifacts": out.get("artifacts", []),
                    "stdout": self._truncate_text(str(out.get("stdout", "")), max_len=4000),
                    "stderr": self._truncate_text(str(out.get("stderr", "")), max_len=2000),
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), "action": action,
                     "skill_name": skill_name, "ok": ok, "exit_code": out.get("exit_code"),
                     "error_type": out.get("error_type"), "artifacts": out.get("artifacts", [])}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"execute:{skill_name}:{'ok' if ok else 'fail'}")
                continue

            # ── workspace_read ──
            if action == "workspace_read":
                ws_read_path = str(args.get("path", ""))
                try:
                    if not self._skill_runtime.workspace_exists(ws_read_path):
                        result_obj = {
                            "action": action,
                            "path": ws_read_path,
                            "ok": False,
                            "error": "file not found",
                        }
                    else:
                        content = self._skill_runtime.workspace_read(ws_read_path)
                        result_obj = {
                            "action": action,
                            "path": ws_read_path,
                            "ok": True,
                            "content": self._truncate_text(content, max_len=8000),
                        }
                except Exception as e:
                    result_obj = {"action": action, "path": ws_read_path, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"workspace_read:{ws_read_path}:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── workspace_write ──
            if action == "workspace_write":
                path = str(args.get("path", ""))
                content = str(args.get("content", ""))
                try:
                    self._skill_runtime.workspace_write(path, content)
                    result_obj = {"action": action, "path": path, "ok": True, "size": len(content)}
                except Exception as e:
                    result_obj = {"action": action, "path": path, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"workspace_write:{path}:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── workspace_list ──
            if action == "workspace_list":
                path = str(args.get("path", ".") or ".")
                files = self._skill_runtime.workspace_list(path)
                result_obj = {
                    "action": action,
                    "path": path,
                    "ok": True,
                    "count": len(files),
                    "files": files[:200],
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), "action": action,
                     "path": path, "ok": True, "count": len(files)}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"workspace_list:{path}:{len(files)}")
                continue

            # ── bash ──
            if action == "bash":
                command = str(args.get("command", "")).strip()
                timeout_sec = int(args.get("timeout_sec", 20))
                timeout_sec = max(1, min(120, timeout_sec))
                out = await self._run_bash_in_workspace(command=command, timeout_sec=timeout_sec)
                ok = bool(out.get("ok"))
                result_obj = {
                    "action": action,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "stdout": self._truncate_text(str(out.get("stdout", "")), max_len=5000),
                    "stderr": self._truncate_text(str(out.get("stderr", "")), max_len=2000),
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"bash:{'ok' if ok else 'fail'}")
                continue

            # ── glob ──
            if action == "glob":
                try:
                    parsed = self._glob_in_workspace(
                        pattern=str(args.get("glob", "**/*")),
                        root=str(args.get("path", ".")),
                    )
                    result_obj = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    result_obj = {"action": action, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"glob:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── grep ──
            if action == "grep":
                try:
                    parsed = self._grep_in_workspace(
                        pattern=str(args.get("pattern", "")),
                        root=str(args.get("path", ".")),
                        file_glob=str(args.get("glob", "")),
                    )
                    result_obj = {
                        "action": action,
                        "ok": True,
                        "count": parsed.get("count", 0),
                        "matches": parsed.get("matches", [])[:100],
                    }
                except Exception as e:
                    result_obj = {"action": action, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"grep:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── codegen ──
            if action == "codegen":
                instruction = str(args.get("instruction", ""))
                ctx = dict(args.get("ctx", {}))
                template_mode_arg = args.get("template_mode")
                if template_mode_arg is None:
                    template_mode = self._should_enable_template_mode(instruction, ctx)
                else:
                    template_mode = bool(template_mode_arg)
                out = await self._run_codegen(
                    instruction=instruction, ctx=ctx, template_mode=template_mode,
                )
                ok = bool(out.get("ok"))
                result_obj: dict[str, Any] = {
                    "action": action,
                    "ok": ok,
                    "template_mode": template_mode,
                    "stdout": self._truncate_text(str(out.get("stdout", "")), max_len=5000),
                    "stderr": self._truncate_text(str(out.get("stderr", "")), max_len=2000),
                }
                if out.get("ctx"):
                    try:
                        ctx_str = json.dumps(out["ctx"], ensure_ascii=False)
                        result_obj["ctx"] = self._truncate_text(ctx_str, max_len=4000)
                    except Exception:
                        pass
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"codegen:{'ok' if ok else 'fail'}")
                continue

            # ── unsupported action：通知 LLM ──
            valid_tools = (
                "activate_skill, read_skill, execute_skill, bash, codegen, "
                "workspace_read, workspace_write, workspace_list, glob, grep, "
                "enable_skill, disable_skill, done"
            )
            result_obj = {
                "action": action,
                "ok": False,
                "error": f"unsupported tool: '{action}'. Valid tools: {valid_tools}",
            }
            history.append(result_obj)
            self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
            self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
            logs.append(f"unsupported:{action}")

        return logs, history

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
        return await self._skill_runtime.execute(skill_name=skill_name, args=args)

    async def step(self, tick: int, t: datetime) -> str:
        self._step_count += 1
        self._last_selected_skills = set(self._selectable_skill_names)
        logs, tool_history = await self._tool_loop(tick=tick, t=t)

        # 使用 tool loop 结束后的最终技能状态（可能因 enable/disable 有变化）
        self._skill_runtime.persist_session_state(
            tick=tick,
            t=t,
            selected_skills=self._selectable_skill_names,
            activated_skills=self._activated_skills,
        )
        self._skill_runtime.append_step_replay(
            tick=tick,
            t=t,
            selected_skills=self._selectable_skill_names,
            tool_history=tool_history,
        )
        await self._write_analysis_step(t=t, logs=logs, tool_history=tool_history)
        if not logs:
            return "no-action"
        return " | ".join(logs)

    async def ask(self, message: str, readonly: bool = True) -> str:
        if self._env is not None:
            _, answer = await self.ask_env({"id": self.id}, message, readonly=readonly)
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

    async def close(self):
        if self._replay_writer is not None:
            await self._ensure_analysis_run_written()
            closed_at = datetime.now()
            await self._write_analysis_run(ended_at=closed_at)
            await self._emit_analysis_event(
                event_type="lifecycle.close",
                step=self._step_count or None,
                t=closed_at,
                summary="agent closed",
                payload={"step_count": self._step_count},
            )
