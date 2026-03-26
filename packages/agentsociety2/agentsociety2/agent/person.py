"""PersonAgent — 每个 Person 就是一个独立的 Claude-like tool-using agent。

每个 agent 拥有独立工作区、独立会话线程，通过 skill catalog + 工具调用自主完成任务。
skill 作者只需要写 SKILL.md（+ 可选脚本），无需了解 PersonAgent 内部。
"""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Mapping
import re
import shlex
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import json_repair
from pydantic import BaseModel, Field

from agentsociety2.agent.base import AgentBase
from agentsociety2.agent.skills import SkillRegistry, get_skill_registry
from agentsociety2.agent.skills.runtime import AgentSkillRuntime
from agentsociety2.env import RouterBase

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter


class ToolDecision(BaseModel):
    """单轮工具决策输出。

    由 LLM 生成并通过 Pydantic 校验，作为 `_tool_loop` 的唯一执行输入。
    """
    tool_name: str = Field(
        description=(
            "activate_skill|read_skill|execute_skill|workspace_read|workspace_write|workspace_list|enable_skill|disable_skill|bash|glob|grep|codegen|done"
        )
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    summary: str = ""


class PersonAgent(AgentBase):
    """Person 场景下的 skills-first 工具代理。

    设计目标是让每个 Person 拥有独立线程、独立工作区和独立技能可见性，
    在每个 step 内通过工具循环完成“观察-推理-行动”。
    """

    @classmethod
    def mcp_description(cls) -> str:
        """返回 MCP 候选列表中的简短描述。"""
        return (
            "PersonAgent: Minimal skills-first agent. "
            "Uses progressive skill loading and isolated agent workspace."
        )

    _TOOL_SPECS: tuple[tuple[str, str, str], ...] = (
        ("activate_skill", "skill_name, arguments", "Load skill instructions (optional args)"),
        ("read_skill", "skill_name, path", "Read a file inside a skill directory"),
        ("execute_skill", "skill_name, args", "Run a skill's subprocess script"),
        ("bash", "command, timeout_sec", "Shell command in workspace"),
        ("codegen", "instruction, ctx", "Send instruction to the environment"),
        ("workspace_read", "path", "Read file"),
        ("workspace_write", "path, content", "Write file"),
        ("workspace_list", "path", "List files"),
        ("glob", "glob, path", "Find files by pattern"),
        ("grep", "pattern, glob, path", "Search file contents"),
        ("enable_skill", "skill_name", "Reveal a hidden skill"),
        ("disable_skill", "skill_name", "Hide a skill"),
        ("done", "(done=true, summary)", "Finish this step"),
    )

    @classmethod
    def _render_tool_table(cls) -> str:
        lines = ["| Tool | Arguments | Purpose |", "|------|-----------|----------|"]
        for name, arguments, purpose in cls._TOOL_SPECS:
            lines.append(f"| {name} | {arguments} | {purpose} |")
        return "\n".join(lines)

    def __init__(
        self,
        id: int,
        profile: Any,
        name: Optional[str] = None,
        replay_writer: Optional["ReplayWriter"] = None,
        init_state: Optional[dict[str, Any]] = None,
        **capability_kwargs: Any,
    ):
        """初始化 PersonAgent。

        Args:
            id: Agent 唯一标识。
            profile: 画像对象（dict 或可序列化对象）。
            name: 可选显示名。
            replay_writer: 可选回放写入器。
            init_state: 初始状态（会被归一化为 dict）。
            **capability_kwargs: 能力参数，如 core_skills/max_tool_rounds/thread_compact_chars。
        """
        super().__init__(id=id, profile=profile, name=name, replay_writer=replay_writer)
        self._agent_state: dict[str, Any] = self._coerce_llm_dict(init_state)
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
        self._active_skill_scope: str = ""
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

    def _all_visible_skill_names(self) -> set[str]:
        """返回当前 agent 可见技能名集合副本。"""
        return set(self._selectable_skill_names)

    @staticmethod
    def _truncate_text(text: str, max_len: int = 2000) -> str:
        """按字符上限截断文本，避免 thread/tool 日志过大。"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...<truncated>"

    @staticmethod
    def _coerce_llm_dict(raw: Any) -> dict[str, Any]:
        """把「应为 dict」的字段归一成 dict（用于 ToolDecision.arguments、codegen.ctx、execute_skill.args 等）。

        - ``None`` → ``{}``；``Mapping`` → 浅拷贝 ``dict``。
        - ``str`` → ``json_repair.loads``；解析结果必须是 JSON object，否则 ``{}``。
        - 其它类型 → ``{}``。

        禁止对字符串做 ``dict(s)``（会按字符迭代，触发 ``ValueError: dictionary update sequence...``）。
        """
        if raw is None:
            return {}
        if isinstance(raw, Mapping):
            return dict(raw)
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return {}
            parsed = json_repair.loads(s)
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    # ── System Prompt ──────────────────────────────────────────────────────────

    def get_system_prompt(self, tick: int, t: datetime) -> str:
        """构造本轮 system prompt。

        包含身份信息、可见技能目录、工具说明与已激活技能列表。
        """
        base = super().get_system_prompt(tick, t)

        agent_identity = {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
        }

        catalog = self._skill_runtime.skill_list(sorted(self._all_visible_skill_names()))

        skill_section = (
            f"\n\n# Agent Identity\n"
            f"{json.dumps(agent_identity, ensure_ascii=False)}\n\n"
            "# You Are an Autonomous Tool-Using Agent\n"
            "Call exactly one tool per round. "
            "Respond ONLY with valid JSON: {tool_name, arguments, done, summary}.\n"
            "For execute_skill use arguments.args as a JSON object; for codegen use arguments.ctx as a JSON object "
            "(prefer objects over stringified JSON; the runtime parses strings with json_repair).\n\n"
            "# Skills\n"
            "The catalog below lists available skills (name + description). "
            "Use `activate_skill` to load a skill's full instructions, then follow them. "
            "You may pass `arguments` when activating a skill; the runtime will inject them into skill content.\n"
            "If TOOL_RESULT_JSON reports blocked/visibility/dependency errors, adjust your next tool call accordingly.\n\n"
            "# Execution Rules\n"
            "- Do not invent tools or fields.\n"
            "- Prefer skill-driven execution: activate -> read/execute -> workspace operations -> done.\n"
            "- Keep `summary` concise and factual.\n\n"
            "# Tools\n"
            f"{self._render_tool_table()}\n\n"
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
        """将工具结果写入 thread（同时写磁盘与内存窗口）。"""
        payload = json.dumps(result_obj, ensure_ascii=False)
        content = "TOOL_RESULT_JSON:\n" + self._truncate_text(payload, max_len=12000)
        self._skill_runtime.append_thread_message("user", content, tick=tick, t=t)
        thread_messages.append({"role": "user", "content": content})
        if len(thread_messages) > 40:
            del thread_messages[:-40]

    def _is_model_invocable_skill(self, skill_name: str) -> bool:
        """模型可调用 skill：disable_model_invocation=True 的 skill 一律拒绝工具侧激活/读取/执行。"""
        info = self._skill_registry.get_skill_info(skill_name, load_content=False)
        if info is None:
            return False
        return not bool(getattr(info, "disable_model_invocation", False))

    @staticmethod
    def _normalize_allowed_tools(raw: list[str]) -> set[str]:
        """将 skill frontmatter 的 allowed-tools 归一到 PersonAgent 的 tool_name 集合。"""
        if not raw:
            return set()

        mapping = {
            "read": "workspace_read",
            "write": "workspace_write",
            "workspace_read": "workspace_read",
            "workspace_write": "workspace_write",
            "workspace_list": "workspace_list",
            "activate_skill": "activate_skill",
            "read_skill": "read_skill",
            "execute_skill": "execute_skill",
            "bash": "bash",
            "grep": "grep",
            "glob": "glob",
            "codegen": "codegen",
            "enable_skill": "enable_skill",
            "disable_skill": "disable_skill",
            "done": "done",
        }
        out: set[str] = set()
        for item in raw:
            s = str(item).strip()
            if not s:
                continue
            # 兼容 Claude 文档里类似 Bash(gh *) 的写法：先截断到 "(" 前
            base = s.split("(", 1)[0].strip().lower()
            if base in mapping:
                out.add(mapping[base])
            else:
                out.add(base)
        return out

    def _allowed_tools_for_active_scope(self) -> set[str] | None:
        """当前 scope 的 allowed-tools；为空表示不限制。"""
        name = self._active_skill_scope.strip()
        if not name:
            return None
        info = self._skill_registry.get_skill_info(name, load_content=False)
        if info is None:
            return None
        allowed = self._normalize_allowed_tools(getattr(info, "allowed_tools", []) or [])
        return allowed or None

    def _check_allowed_tools_for_action(self, action: str) -> dict[str, Any] | None:
        """统一处理 allowed-tools 拦截。返回 None 表示允许，否则返回错误对象。"""
        guarded_actions = {
            "workspace_read",
            "workspace_write",
            "workspace_list",
            "bash",
            "glob",
            "grep",
            "codegen",
        }
        if action not in guarded_actions:
            return None
        allowed = self._allowed_tools_for_active_scope()
        if allowed is None or action in allowed:
            return None
        return {
            "action": action,
            "ok": False,
            "error": f"blocked by allowed-tools of active skill: {self._active_skill_scope}",
        }

    @staticmethod
    def _split_skill_arguments(raw: Any) -> tuple[str, list[str]]:
        """把 activate_skill 的 arguments 解析为原始串与分词数组。"""
        if raw is None:
            return "", []
        if isinstance(raw, list):
            parts = [str(x).strip() for x in raw if str(x).strip()]
            return " ".join(parts), parts
        s = str(raw).strip()
        if not s:
            return "", []
        try:
            parts = [x for x in shlex.split(s) if x]
        except ValueError:
            parts = [x for x in s.split() if x]
        return s, parts

    @staticmethod
    def _inject_skill_arguments(content: str, arguments_raw: str, arguments_parts: list[str]) -> str:
        """将 `$ARGUMENTS/$ARGUMENTS[N]/$N` 占位符渲染到 skill 内容。"""
        rendered = content.replace("$ARGUMENTS", arguments_raw)

        def repl_indexed(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            return arguments_parts[idx] if 0 <= idx < len(arguments_parts) else ""

        rendered = re.sub(r"\$ARGUMENTS\[(\d+)\]", repl_indexed, rendered)
        rendered = re.sub(r"\$(\d+)", repl_indexed, rendered)

        has_argument_placeholder = ("$ARGUMENTS" in content) or bool(re.search(r"\$(\d+)|\$ARGUMENTS\[\d+\]", content))
        if arguments_raw and not has_argument_placeholder:
            rendered += f"\n\nARGUMENTS: {arguments_raw}"
        return rendered

    async def _inject_skill_command_outputs(self, content: str) -> str:
        """注入 !`cmd` 动态上下文（Linux/bash）。命令失败则激活失败，不做回落。"""
        pattern = re.compile(r"!\`([^`\n]+)\`")
        rendered = content
        offset = 0
        for m in list(pattern.finditer(content)):
            cmd = m.group(1).strip()
            if not cmd:
                raise ValueError("empty dynamic command")
            out = await self._run_bash_in_workspace(command=cmd, timeout_sec=20)
            if not out.get("ok"):
                raise ValueError(f"dynamic command failed: {cmd}; {out.get('stderr', '')}")
            replacement = str(out.get("stdout", "")).strip()
            start = m.start() + offset
            end = m.end() + offset
            rendered = rendered[:start] + replacement + rendered[end:]
            offset += len(replacement) - (m.end() - m.start())
        return rendered

    # ── Skill Dependency ──────────────────────────────────────────────────────

    def _ensure_requires_activated(
        self,
        tick: int,
        t: datetime,
        thread_messages: list[dict[str, str]],
        skill_name: str,
    ) -> dict[str, Any]:
        """确保 skill 的 requires 依赖已激活。

        Returns:
            dict: `{"ok": bool, "requires": [...], "activated": [...], "missing": [...]}`。
                - ok=True: 所有依赖满足（可能有自动激活）
                - ok=False: 存在不可见/不可调用依赖，`missing` 给出缺失项
        """
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
            if not self._is_model_invocable_skill(dep):
                missing.append(dep)
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
        """在 agent workspace 执行 bash 命令并施加安全限制。

        限制包括：禁止绝对路径、禁止父目录遍历、危险 token 黑名单、超时终止。
        """
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
        """调用环境路由器执行 codegen 指令。"""
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
        """在 workspace 内做 glob 检索（带路径越界保护）。"""
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
        """在 workspace 内做内容检索（限制扫描文件数/匹配数/单文件大小）。"""
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
        """根据 enabled/core/override 三类条件刷新可见技能集合。"""
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
        """持久化 agent 配置与技能可见性状态到 `agent_config.json`。"""
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

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self, env: RouterBase):
        """初始化运行时目录，加载持久配置并扫描 custom/env skills。"""
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

    # ── Context Compaction (sliding summary) ─────────────────────────────────

    async def _compact_thread_if_needed(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
    ) -> list[dict[str, str]]:
        """在超出阈值时压缩 thread。

        策略：旧消息摘要 + 最近消息原样保留，控制上下文大小并保持最近决策连贯性。
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
                    "Summarize the following tool-loop history in 3-5 short sentences. "
                    "Keep only: activated skills, key tool outcomes, important errors, "
                    "current intent, and files written in workspace. "
                    "Do not include extra analysis."
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
        """执行单个 step 的工具循环。

        循环流程：
        1) 基于 thread 让 LLM 产出 `ToolDecision`
        2) 通过可见性/权限/依赖 gate 校验
        3) 执行工具并把结果回写 thread
        4) 直到 `done` 或达到轮次上限
        """
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
            args = self._coerce_llm_dict(decision.arguments)
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
                if self._active_skill_scope == skill_name:
                    self._active_skill_scope = ""
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

            # ── user-only skill gate (disable_model_invocation) ──
            if action in {"activate_skill", "read_skill", "execute_skill"} and skill_name:
                if not self._is_model_invocable_skill(skill_name):
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "skill is user-only (disable_model_invocation=true)",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                    logs.append(f"{action}:{skill_name}:user_only")
                    continue

            # ── allowed-tools gate ──
            blocked_obj = self._check_allowed_tools_for_action(action)
            if blocked_obj is not None:
                history.append(blocked_obj)
                self._append_tool_result_to_thread(thread_messages, tick, t, blocked_obj)
                logs.append(f"{action}:blocked_allowed_tools")
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

                activation_raw, activation_parts = self._split_skill_arguments(args.get("arguments", ""))
                base_content = self._skill_runtime.skill_activate(skill_name)
                ok = bool(base_content)
                content = ""
                if ok:
                    try:
                        content = self._inject_skill_arguments(base_content, activation_raw, activation_parts)
                        content = await self._inject_skill_command_outputs(content)
                    except Exception as e:
                        result_obj = {
                            "action": action,
                            "skill_name": skill_name,
                            "ok": False,
                            "error": f"skill_render_failed: {e}",
                        }
                        history.append(result_obj)
                        self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                        logs.append(f"activate:{skill_name}:render_failed")
                        continue
                    self._activated_skills.add(skill_name)
                    self._active_skill_scope = skill_name
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
                if ok:
                    self._active_skill_scope = skill_name
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

                payload = self._coerce_llm_dict(args.get("args", {}))
                payload.setdefault("tick", tick)
                payload.setdefault("time", t.isoformat())
                try:
                    out = await self.execute(skill_name, payload)
                except Exception as e:
                    out = {"ok": False, "error_type": type(e).__name__, "stderr": str(e), "stdout": ""}
                ok = bool(out.get("ok"))
                if ok:
                    self._active_skill_scope = skill_name
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
                try:
                    files = self._skill_runtime.workspace_list(path)
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": True,
                        "count": len(files),
                        "files": files[:200],
                    }
                except Exception as e:
                    result_obj = {"action": action, "path": path, "ok": False, "error": str(e)}
                history.append(result_obj)
                self._skill_runtime.append_tool_log({"tick": tick, "time": t.isoformat(), **result_obj})
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                if result_obj.get("ok"):
                    logs.append(f"workspace_list:{path}:{result_obj.get('count', 0)}")
                else:
                    logs.append(f"workspace_list:{path}:fail")
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
                ctx = self._coerce_llm_dict(args.get("ctx", {}))
                template_mode = bool(args.get("template_mode", False))
                out = await self._run_codegen(
                    instruction=instruction, ctx=ctx, template_mode=template_mode,
                )
                ok = bool(out.get("ok"))
                result_obj: dict[str, Any] = {
                    "action": action,
                    "ok": ok,
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
        """执行技能（转发到 runtime/registry）。"""
        return await self._skill_runtime.execute(skill_name=skill_name, args=args)

    async def step(self, tick: int, t: datetime) -> str:
        """执行一个仿真步并持久化会话状态与回放记录。"""
        self._step_count += 1
        # 每步重新进入自由工具选择，避免上一步 skill 的 allowed-tools 作用域跨步泄漏。
        self._active_skill_scope = ""
        self._last_selected_skills = set(self._selectable_skill_names)
        logs, tool_history = await self._tool_loop(tick=tick, t=t)

        # 使用 tool loop 结束后的最终技能状态
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
        if not logs:
            return "no-action"
        return " | ".join(logs)

    async def ask(self, message: str, readonly: bool = True) -> str:
        """转发到环境问答接口；无环境时回显输入。"""
        if self._env is not None:
            _, answer = await self.ask_env({"id": self.id}, message, readonly=readonly)
            return answer
        return message

    async def dump(self) -> dict:
        """导出最小运行状态快照（用于外部持久化/调试）。"""
        return {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
            "step_count": self._step_count,
            "last_selected_skills": sorted(self._last_selected_skills),
        }

    async def load(self, dump_data: dict):
        """从 `dump` 结果恢复轻量运行状态。"""
        self._step_count = int(dump_data.get("step_count", 0))
        self._last_selected_skills = set(dump_data.get("last_selected_skills", []))
