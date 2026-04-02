"""PersonAgent：skills-first 的工具代理实现。

该模块的核心类是 :class:`~agentsociety2.agent.person.PersonAgent`，它将每个 Person 视作一个拥有：

- **独立工作区**：每个 agent 的文件与日志隔离在自身 workspace；
- **独立会话线程**：通过 thread_messages 维护短上下文，并在必要时做摘要压缩；
- **渐进式 skill 发现**：模型先看到 skill catalog（名称+摘要），再通过 ``activate_skill`` 加载完整指令；
- **工具循环**：每个 step 内循环产出 ``ToolDecision``，执行工具并回写 ``TOOL_RESULT_JSON``，直到 done。

Skill 作者通常只需要提供 ``SKILL.md``（以及可选脚本），无需理解 PersonAgent 内部实现细节。
"""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Mapping
from fnmatch import fnmatch
import re
import shlex
from datetime import datetime
from typing import Any, Optional

import json_repair
from pydantic import BaseModel, Field

from agentsociety2.agent.base import AgentBase
from agentsociety2.agent.skills import SkillRegistry, get_skill_registry
from agentsociety2.agent.skills.runtime import AgentSkillRuntime
from agentsociety2.env import (
    PersonStepConstraints,
    RouterBase,
    merge_person_step_constraints,
)
from agentsociety2.logger import get_logger

logger = get_logger()


class ToolDecision(BaseModel):
    """单轮工具决策输出模型。

    由 LLM 生成并通过 Pydantic 校验，作为工具循环的唯一执行输入。

    Attributes:
        tool_name: 工具名称。必须是以下之一：activate_skill, read_skill,
            execute_skill, workspace_read, workspace_write, workspace_list,
            enable_skill, disable_skill, bash, glob, grep, codegen, batch, done。
        arguments: 工具参数字典。
        done: 是否结束当前仿真步。设为 true 时，当前工具执行完后本步结束。
        summary: 执行摘要。
    """

    tool_name: str = Field(
        description=(
            "Exactly one of: activate_skill, read_skill, execute_skill, workspace_read, workspace_write, "
            "workspace_list, enable_skill, disable_skill, bash, glob, grep, codegen, batch, done. "
            "activate_skill with arguments.skill_name set to the skill name."
        )
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    done: bool = Field(
        default=False,
        description="Set true when this simulation step should end after the current tool runs. "
        "If more tools are needed this round, must be false. You may use tool_name=done with no other work.",
    )
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
        (
            "activate_skill",
            "skill_name, arguments",
            "Load skill instructions (optional args)",
        ),
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
        (
            "batch",
            "operations",
            "Execute multiple operations in one call",
        ),
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
        init_state: Optional[dict[str, Any]] = None,
        **capability_kwargs: Any,
    ):
        """初始化 PersonAgent。

        :param id: Agent 唯一标识。
        :param profile: 画像对象（dict 或可序列化对象）。
        :param name: 可选显示名。
        :param init_state: 可选初始状态（会写入 workspace，默认不覆盖已存在文件）。
        :param capability_kwargs: 行为/能力参数（节选）：

            - ``max_tool_rounds``：单步最大工具轮数（默认 24）
            - ``preload_workspace_paths``：预读文件列表（注入 system prompt 的 workspace 快照）
            - ``thread_key_state_paths``：thread 压缩时附带的 KEY_STATE_JSON 文件路径列表
            - ``catalog_working_set_json``：用于 skill 的 ``paths`` 匹配信号文件（如 ``working_set.json``）
            - ``system_prompt_max_identity_chars``：Agent Identity JSON 总长度上限（默认 10000）
        """
        super().__init__(id=id, profile=profile, name=name)
        self._agent_state: dict[str, Any] = self._coerce_llm_dict(init_state)
        self._capability_kwargs: dict[str, Any] = dict(capability_kwargs)

        base_registry = get_skill_registry()
        self._skill_registry = SkillRegistry()
        self._skill_registry._skills = copy.deepcopy(base_registry._skills)
        self._skill_registry._builtin_scanned = True
        self._skill_runtime = AgentSkillRuntime(
            agent_id=id, registry=self._skill_registry
        )
        self._selectable_skill_names: set[str] = set()
        self._skill_visibility_overrides: dict[str, bool] = {}
        self._activated_skills: set[str] = set()
        self._active_skill_scope: str = ""

        self._step_count = 0
        self._last_selected_skills: set[str] = set()
        self._max_tool_rounds = max(
            1, int(self._capability_kwargs.get("max_tool_rounds", 24))
        )

        # 上下文缓存：避免重复读取相同文件
        self._workspace_cache: dict[str, str] = {}
        self._cache_valid_paths: set[str] = set()
        # 当前 step 的上下文快照（在 step 开始时构建）
        self._step_context: dict[str, Any] = {}
        # workspace 状态版本：每次可能改动工作区后递增，避免模型使用过期上下文
        self._workspace_state_version: int = 0
        # 环境工具经 Router 改写后的世界描述，在 init 时拉取并注入 system prompt
        self._world_description: str = ""

    def _all_visible_skill_names(self) -> set[str]:
        """返回当前 agent 可见技能名集合副本。"""
        return set(self._selectable_skill_names)

    def _workspace_preload_paths(self) -> list[str]:
        """获取预加载的 workspace 文件路径列表。

        从 capability_kwargs['preload_workspace_paths'] 读取。

        Returns:
            路径字符串列表。
        """
        raw = self._capability_kwargs.get("preload_workspace_paths")
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _thread_key_state_paths(self) -> list[str]:
        """获取 thread 压缩时写入 KEY_STATE_JSON 的文件路径列表。

        从 capability_kwargs['thread_key_state_paths'] 读取。

        Returns:
            路径字符串列表。
        """
        raw = self._capability_kwargs.get("thread_key_state_paths")
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _build_step_context(self) -> dict[str, Any]:
        """构建当前 step 的上下文快照。

        仅预读 ``capability_kwargs['preload_workspace_paths']`` 列出的路径（Person 不内置 skill 文件名）。
        同时更新缓存，供后续操作使用。
        """
        context: dict[str, Any] = {}

        for path in self._workspace_preload_paths():
            if self._skill_runtime.workspace_exists(path):
                content = self._skill_runtime.workspace_read(path)
                if content:
                    # JSON 文件尝试解析
                    if path.endswith(".json"):
                        context[path] = json_repair.loads(content)
                    else:
                        context[path] = content
                    # 同时更新缓存
                    self._workspace_cache[path] = content
                    self._cache_valid_paths.add(path)

        self._step_context = context
        return context

    def _invalidate_workspace_cache(self, path: str) -> None:
        """失效指定路径的缓存（写入文件后调用）。"""
        self._cache_valid_paths.discard(path)
        self._step_context.pop(path, None)

    def _get_cached_workspace_content(self, path: str) -> Optional[str]:
        """从缓存获取文件内容，缓存未命中返回 None。"""
        if path in self._cache_valid_paths:
            return self._workspace_cache.get(path)
        return None

    def _invalidate_all_workspace_cache(self) -> None:
        """清空全部 workspace 缓存。"""
        self._cache_valid_paths.clear()
        self._workspace_cache.clear()
        self._step_context = {}

    def _bump_workspace_state_version(self) -> int:
        """递增 workspace 状态版本号并返回新值。"""
        self._workspace_state_version += 1
        return self._workspace_state_version

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

    def _agent_identity_json_for_prompt(self) -> str:
        """生成用于 system prompt 的智能体身份 JSON。

        包含 id, name, profile。若总长度超过 system_prompt_max_identity_chars，
        则对 profile 进行截断。

        Returns:
            智能体身份 JSON 字符串。
        """
        max_total = max(
            2000,
            int(self._capability_kwargs.get("system_prompt_max_identity_chars", 10000)),
        )
        agent_identity: dict[str, Any] = {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
        }

        def dump() -> str:
            return json.dumps(agent_identity, ensure_ascii=False)

        s = dump()
        if len(s) <= max_total:
            return s

        prof = agent_identity.get("profile")
        prof_s = prof if isinstance(prof, str) else json.dumps(prof, ensure_ascii=False)
        inner_budget = max(max_total - 220, 400)
        agent_identity["profile"] = (
            self._truncate_text(prof_s, max_len=inner_budget) + "…<truncated>"
        )
        s = dump()
        if len(s) <= max_total:
            return s

        agent_identity["profile"] = "<omitted: profile too large for system prompt>"
        return dump()

    # ── System Prompt ──────────────────────────────────────────────────────────

    def get_system_prompt(self, tick: int, t: datetime) -> str:
        """构建本步 system prompt（在 :class:`~agentsociety2.agent.base.AgentBase` 基础上扩展）。

        该 prompt 主要注入：

        - world description（若环境提供）
        - agent identity（含 profile，带长度上限保护）
        - 工具协议与工具表
        - skill catalog（渐进披露）
        - 已激活技能列表

        :param tick: 当前仿真步时间跨度（秒）。
        :param t: 当前仿真时间。
        :returns: system prompt 文本。
        """
        base = super().get_system_prompt(tick, t)

        wd = self._world_description.strip()
        world_block = ""
        if wd:
            world_block = (
                "\n\n# World Description\n"
                "Environment-specific modules, tools, and action conventions:\n\n"
                f"{self._truncate_text(wd, max_len=16000)}\n"
            )

        visible_names = sorted(self._all_visible_skill_names())
        catalog_names: list[str] = []
        for n in visible_names:
            info = self._skill_registry.get_skill_info(n, load_content=False)
            if info is None:
                continue
            if getattr(info, "disable_model_invocation", False):
                continue
            patterns = list(getattr(info, "paths", []) or [])
            if patterns and not self._catalog_paths_match(patterns):
                continue
            catalog_names.append(n)
        catalog = self._skill_runtime.skill_list(catalog_names)

        skill_section = (
            f"\n\n# Agent Identity\n"
            f"{self._agent_identity_json_for_prompt()}\n"
            "\n# This simulation step\n"
            "The persona and behavioral guidelines above set motivation and realism. "
            "Within this step you must act only through the tool JSON protocol below: "
            "each assistant turn is exactly one tool call (`batch` still counts as one `tool_name`).\n"
        )

        # 注入上下文快照：让 LLM 直接看到常用文件内容，减少 workspace_read 调用
        if self._step_context:
            # 过滤掉过大的内容
            context_display = {}
            for k, v in self._step_context.items():
                if isinstance(v, str) and len(v) > 2000:
                    context_display[k] = v[:2000] + "...<truncated>"
                else:
                    context_display[k] = v
            skill_section += (
                f"\n# Workspace State (pre-loaded)\n"
                "Below is a snapshot of common workspace files for faster context.\n"
                "Important: after any write/execute/codegen action, snapshot content may become stale; "
                "use `workspace_read` to fetch latest source of truth when correctness matters.\n"
                f"```json\n{json.dumps(context_display, ensure_ascii=False, indent=1)}\n```\n"
            )

        skill_section += (
            "\n# Tool protocol (output shape)\n"
            "Respond ONLY with valid JSON: {tool_name, arguments, done, summary}. "
            "`arguments` must be a JSON object (use {} if no parameters).\n"
            "For execute_skill use arguments.args as a JSON object; for codegen use arguments.ctx as a JSON object "
            "(prefer objects over stringified JSON; the runtime parses strings with json_repair).\n"
            "For activate_skill set arguments.skill_name; optional arguments.arguments (string or list) feeds "
            "SKILL.md placeholders like $ARGUMENTS / $0.\n\n"
            "# Skills\n"
            "The catalog lists name + short description only (progressive disclosure). "
            "Use `activate_skill` to load full SKILL.md, then follow it.\n"
            "If TOOL_RESULT_JSON reports blocked/visibility/dependency errors, adjust the next tool call.\n\n"
            "# Execution Rules\n"
            "- Do not invent tools or fields. `tool_name` must match the Tools table exactly.\n"
            "- Never set tool_name to a catalog skill name. Use activate_skill with arguments.skill_name.\n"
            "- To drive the **shared simulation environment** (observe, submit, status), use `codegen` with a clear "
            "instruction; the runtime merges your numeric id into ctx.\n"
            "- Prefer skill-driven execution: activate -> read/execute -> workspace operations -> done.\n"
            "- Keep `summary` concise and factual.\n"
            "- Use `batch` only when allowed by the active skill's allowed-tools (if any).\n\n"
        )
        pc = self._merged_person_step_constraints()
        if pc:
            skill_section += (
                "# Environment step constraints\n"
                "This step has environment-imposed limits: only skills listed in the catalog above exist for you. "
                "If an active skill declares allowed-tools, do not call tools outside that list.\n"
            )
            if pc.pin_allowed_tools_to_skill:
                skill_section += (
                    f"Allowed-tools scope is pinned to `{pc.pin_allowed_tools_to_skill}` at step start; "
                    "follow that skill's SKILL.md for codegen vs workspace.\n"
                )
        skill_section += (
            "# Tools\n"
            f"{self._render_tool_table()}\n\n"
            f"# Skill Catalog\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
            f"# Activated Skills\n{json.dumps(sorted(self._activated_skills), ensure_ascii=False)}"
        )

        return base + world_block + skill_section

    # ── Thread Management ─────────────────────────────────────────────────────

    def _append_tool_result_to_thread(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
        result_obj: dict[str, Any],
    ) -> None:
        """将工具结果写入 thread（同时写磁盘与内存窗口）。

        Args:
            thread_messages: thread 消息列表。
            tick: 当前仿真步的时间尺度（秒）。
            t: 当前仿真时间。
            result_obj: 工具执行结果字典。
        """
        enriched = dict(result_obj)
        enriched.setdefault("workspace_state_version", self._workspace_state_version)
        payload = json.dumps(enriched, ensure_ascii=False)
        content = "TOOL_RESULT_JSON:\n" + self._truncate_text(payload, max_len=12000)
        self._skill_runtime.append_thread_message("user", content, tick=tick, t=t)
        thread_messages.append({"role": "user", "content": content})
        if len(thread_messages) > 40:
            del thread_messages[:-40]

    def _catalog_paths_match(self, patterns: list[str]) -> bool:
        """检查当前工作集是否匹配任一模式。

        用于 skill 的 paths 过滤。若无工作集信号，返回 True 以避免意外隐藏 skill。

        Args:
            patterns: 路径模式列表。

        Returns:
            是否匹配。
        """
        if not patterns:
            return True

        signal = self._capability_kwargs.get("catalog_working_set_json")
        if not signal or not str(signal).strip():
            return True
        signal = str(signal).strip()

        candidates: list[str] = []
        obs_raw = self._step_context.get(signal)
        if obs_raw is None and self._skill_runtime.workspace_exists(signal):
            raw_text = self._skill_runtime.workspace_read(signal)
            if raw_text.strip():
                obs_raw = json_repair.loads(raw_text)
        obs = obs_raw if isinstance(obs_raw, dict) else {}
        for key in ("path", "paths", "file", "files", "working_dir", "cwd"):
            v = obs.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())
            elif isinstance(v, list):
                candidates.extend(str(x).strip() for x in v if str(x).strip())

        if not candidates:
            return True

        for c in candidates:
            for p in patterns:
                if fnmatch(c, p):
                    return True
        return False

    def _is_model_invocable_skill(self, skill_name: str) -> bool:
        """检查 skill 是否可被模型自动调用。

        Args:
            skill_name: skill 名称。

        Returns:
            是否可自动调用。
        """
        info = self._skill_registry.get_skill_info(skill_name, load_content=False)
        if info is None:
            return False
        return not bool(getattr(info, "disable_model_invocation", False))

    @staticmethod
    def _normalize_allowed_tools(raw: list[str]) -> set[str]:
        """将 skill frontmatter 的 allowed-tools 归一到 PersonAgent 的 tool_name 集合。

        Args:
            raw: 原始 allowed-tools 列表。

        Returns:
            标准化后的 tool_name 集合。
        """
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
            "batch": "batch",
            "enable_skill": "enable_skill",
            "disable_skill": "disable_skill",
            "done": "done",
        }
        out: set[str] = set()
        for item in raw:
            s = str(item).strip()
            if not s:
                continue
            base = s.split("(", 1)[0].strip().lower()
            if base in mapping:
                out.add(mapping[base])
        return out

    def _allowed_tools_for_active_scope(self) -> set[str] | None:
        """获取当前 scope 的 allowed-tools。

        Returns:
            allowed-tools 集合，为空表示不限制。
        """
        name = self._active_skill_scope.strip()
        if not name:
            return None
        info = self._skill_registry.get_skill_info(name, load_content=False)
        if info is None:
            return None
        raw_list = getattr(info, "allowed_tools", []) or []
        if not raw_list:
            return None
        return self._normalize_allowed_tools(raw_list)

    def _check_allowed_tools_for_action(self, action: str) -> dict[str, Any] | None:
        """统一处理 allowed-tools 拦截。

        Args:
            action: 工具名称。

        Returns:
            None 表示允许，否则返回错误对象。
        """
        guarded_actions = {
            "workspace_read",
            "workspace_write",
            "workspace_list",
            "bash",
            "glob",
            "grep",
            "codegen",
            "batch",
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
        """解析 activate_skill 的 arguments 为原始串与分词数组。

        Args:
            raw: 原始 arguments（可以是 None、list 或 str）。

        Returns:
            元组 (原始串, 分词数组)。
        """
        if raw is None:
            return "", []
        if isinstance(raw, list):
            parts = [str(x).strip() for x in raw if str(x).strip()]
            return " ".join(parts), parts
        s = str(raw).strip()
        if not s:
            return "", []
        parts = [x for x in shlex.split(s) if x]
        return s, parts

    @staticmethod
    def _inject_skill_arguments(
        content: str, arguments_raw: str, arguments_parts: list[str]
    ) -> str:
        """将 $ARGUMENTS/$ARGUMENTS[N]/$N 占位符渲染到 skill 内容。

        Args:
            content: skill 原始内容。
            arguments_raw: 原始参数字符串。
            arguments_parts: 分词后的参数数组。

        Returns:
            渲染后的内容。
        """
        rendered = content.replace("$ARGUMENTS", arguments_raw)

        def repl_indexed(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            return arguments_parts[idx] if 0 <= idx < len(arguments_parts) else ""

        rendered = re.sub(r"\$ARGUMENTS\[(\d+)\]", repl_indexed, rendered)
        rendered = re.sub(r"\$(\d+)", repl_indexed, rendered)

        has_argument_placeholder = ("$ARGUMENTS" in content) or bool(
            re.search(r"\$(\d+)|\$ARGUMENTS\[\d+\]", content)
        )
        if arguments_raw and not has_argument_placeholder:
            rendered += f"\n\nARGUMENTS: {arguments_raw}"
        return rendered

    async def _inject_skill_command_outputs(self, content: str) -> str:
        """注入 !`cmd` 动态上下文（Linux/bash）。

        命令失败则激活失败，不做回落。

        Args:
            content: 包含 !`cmd` 占位符的 skill 内容。

        Returns:
            渲染后的内容，占位符被命令输出替换。
        """
        pattern = re.compile(r"!\`([^`\n]+)\`")
        rendered = content
        offset = 0
        for m in list(pattern.finditer(content)):
            cmd = m.group(1).strip()
            if not cmd:
                raise ValueError("empty dynamic command")
            out = await self._run_bash_in_workspace(command=cmd, timeout_sec=20)
            if not out.get("ok"):
                raise ValueError(
                    f"dynamic command failed: {cmd}; {out.get('stderr', '')}"
                )
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

        Args:
            tick: 当前仿真步的时间尺度（秒）。
            t: 当前仿真时间。
            thread_messages: thread 消息列表。
            skill_name: 需要检查依赖的 skill 名称。

        Returns:
            包含 ok, requires, activated, missing 字段的字典。
            - ok=True: 所有依赖满足（可能有自动激活）
            - ok=False: 存在不可见/不可调用依赖，missing 给出缺失项
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
            return {
                "ok": False,
                "requires": requires,
                "activated": activated,
                "missing": missing,
            }
        return {"ok": True, "requires": requires, "activated": activated}

    # ── Command Execution ─────────────────────────────────────────────────────

    # 危险命令/token 黑名单
    _BLOCKED_COMMAND_TOKENS = frozenset(
        {
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "dd if=",
            ":(){",
            "fork bomb",
            "shutdown",
            "reboot",
            "poweroff",
            "halt",
            "init 0",
            "init 6",
            "curl",
            "wget",
            "nc ",
            "ncat",
            "ssh",
            "scp",
            "rsync",
            "ftp",
            "nmap",
            "telnet",
            "netcat",
            "sudo",
            "su ",
            "chmod 777",
            "chown",
            "chgrp",
            "> /dev/",
            ">/dev/",
        }
    )

    async def _run_bash_in_workspace(
        self, command: str, timeout_sec: int
    ) -> dict[str, Any]:
        """在 agent workspace 执行 bash 命令并施加安全限制。

        :param command: bash 命令（在 workspace 根目录执行）。
        :param timeout_sec: 超时秒数。
        :returns: ``{ok, exit_code, stdout, stderr}``。

        .. note::
           这里的护栏是“轻量”的：主要避免越界路径与明显危险 token。
        """
        command = command.strip()
        if not command:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "empty command",
            }
        # 基于“默认信任本机”的轻量护栏：
        # - 禁止绝对路径，避免直接读写系统文件
        # - 禁止 ../ 访问上级目录，避免越出 agent workspace 语义
        if re.search(r"(^|[\s'\"();|&])\/", command):
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: absolute path",
            }
        if "../" in command or "/.." in command or "..\\" in command:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: parent traversal",
            }
        cmd_lower = command.lower()
        for token in self._BLOCKED_COMMAND_TOKENS:
            if token in cmd_lower:
                return {
                    "ok": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"blocked: contains '{token}'",
                }
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
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
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

    async def _run_codegen(
        self, instruction: str, ctx: dict[str, Any], template_mode: bool
    ) -> dict[str, Any]:
        """调用环境路由器执行 codegen 指令。

        :param instruction: 指令文本。
        :param ctx: 上下文对象（会与 agent identity overlay 合并）。
        :param template_mode: 是否启用模板模式（由 RouterBase 决定如何解释指令）。
        :returns: ``{ok, stdout, stderr, ctx?}``。
        """
        if self._env is None:
            return {"ok": False, "stdout": "", "stderr": "environment not initialized"}
        if not instruction.strip():
            return {"ok": False, "stdout": "", "stderr": "empty instruction"}
        merged_ctx = {**ctx, **self.env_codegen_ctx_overlay()}
        updated_ctx, answer = await self._env.ask(
            ctx=merged_ctx,
            instruction=instruction,
            readonly=False,
            template_mode=template_mode,
        )
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

    def _grep_in_workspace(
        self, pattern: str, root: str, file_glob: str
    ) -> dict[str, Any]:
        """在 workspace 内做内容检索（限制扫描文件数/匹配数/单文件大小）。

        Args:
            pattern: 正则匹配模式。
            root: 相对根目录。
            file_glob: 文件名 glob 模式。

        Returns:
            包含 ok, count, matches, truncated 的字典。
        """
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
                    matches.append(
                        {"path": str(p.relative_to(work_dir)), "line": i, "text": line}
                    )
                    if len(matches) >= max_matches:
                        return {
                            "ok": True,
                            "count": len(matches),
                            "matches": matches,
                            "truncated": True,
                        }
        return {
            "ok": True,
            "count": len(matches),
            "matches": matches,
            "truncated": False,
        }

    # ── Skill Visibility ──────────────────────────────────────────────────────

    def _merged_person_step_constraints(self) -> Optional[PersonStepConstraints]:
        """合并当前路由器上各环境模块对本步的 Person 约束。"""
        if self._env is None:
            return None
        return merge_person_step_constraints(
            getattr(self._env, "env_modules", []) or []
        )

    def _refresh_selectable_skills(self) -> None:
        """根据 enabled/override 条件刷新可见技能集合。

        所有启用的 skill 默认可见，除非被 override 显式禁用。
        """
        c = self._merged_person_step_constraints()
        hidden = c.hide_skills if c else set()
        enabled = self._skill_registry.list_enabled()
        visible = []
        for s in enabled:
            override = self._skill_visibility_overrides.get(s.name)
            if override is False:
                continue
            if s.name in hidden:
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
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self, env: RouterBase):
        """初始化运行时目录，加载持久配置并扫描 custom/env skills。

        流程：
        1. 调用父类 init
        2. 确保 agent 工作目录存在
        3. 从 init_state 初始化 workspace
        4. 加载持久化的 agent_config.json
        5. 扫描环境模块提供的 skills
        6. 刷新可见技能列表
        7. 激活环境模块声明的默认技能
        8. 获取世界描述

        Args:
            env: 环境路由器实例。
        """
        await super().init(env=env)
        self._skill_runtime.ensure_agent_work_dir(self._env)

        # init_state 用于“出生时”的初始内在状态设定。
        # 仅在对应文件不存在时写入，避免覆盖实验过程中已经演化出的状态。
        self._seed_workspace_from_init_state()

        existing_cfg = self._skill_runtime.read_json("agent_config.json", {})
        if isinstance(existing_cfg, dict):
            raw = existing_cfg.get("skill_overrides", {})
            if isinstance(raw, dict):
                self._skill_visibility_overrides = {
                    str(k): bool(v) for k, v in raw.items()
                }
            active_raw = existing_cfg.get("activated_skills", [])
            if isinstance(active_raw, list):
                self._activated_skills = {
                    str(x).strip() for x in active_raw if str(x).strip()
                }
        self._persist_agent_config()

        # 扫描环境模块提供的 skills
        for module in env.env_modules:
            skills_dirs = module.get_agent_skills_dirs()
            for skills_dir in skills_dirs:
                added = self._skill_registry.scan_env_skills(
                    skills_dir, type(module).__name__
                )
                if added:
                    logger.info(
                        f"Agent {self.id}: loaded skills from {skills_dir}: {added}"
                    )

        self._refresh_selectable_skills()

        # 激活环境模块声明的默认技能
        for module in env.env_modules:
            skill_name = module.get_default_skill()
            if skill_name and skill_name in self._all_visible_skill_names():
                self._activated_skills.add(skill_name)
                logger.info(f"Agent {self.id}: activated default skill '{skill_name}'")
            elif skill_name:
                logger.warning(
                    f"Agent {self.id}: default skill '{skill_name}' not found in visible skills"
                )
        self._persist_agent_config()

        if self._env is not None:
            self._world_description = await self._env.get_world_description()

    def _seed_workspace_from_init_state(self) -> None:
        """从 init_state 初始化 workspace。

        写入 init_state.json 和 workspace_seed 中定义的文件。
        仅在文件不存在时写入（除非 init_state_force 为 True）。
        """
        state = self._agent_state if isinstance(self._agent_state, dict) else {}
        if not state:
            return

        force = bool(state.get("init_state_force", False))

        if force or not self._skill_runtime.workspace_exists("init_state.json"):
            self._skill_runtime.workspace_write(
                "init_state.json", json.dumps(state, ensure_ascii=False, indent=2)
            )

        seed = state.get("workspace_seed", {})
        if not isinstance(seed, dict) or not seed:
            return

        for rel_path, value in seed.items():
            rel_path = str(rel_path).strip()
            if not rel_path:
                continue
            if (not force) and self._skill_runtime.workspace_exists(rel_path):
                continue
            if isinstance(value, (dict, list)):
                content = json.dumps(value, ensure_ascii=False, indent=2)
            else:
                content = str(value)
            self._skill_runtime.workspace_write(rel_path, content)

    # ── Context Compaction (sliding summary) ─────────────────────────────────

    async def _compact_thread_if_needed(
        self,
        thread_messages: list[dict[str, str]],
        tick: int,
        t: datetime,
    ) -> list[dict[str, str]]:
        """在超出阈值时压缩 thread。

        策略：旧消息摘要 + 最近消息原样保留，控制上下文大小并保持最近决策连贯性。

        Args:
            thread_messages: thread 消息列表。
            tick: 当前仿真步的时间尺度（秒）。
            t: 当前仿真时间。

        Returns:
            压缩后的消息列表。
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
            content = m.get("content", "")
            lim = 1600 if content.startswith("TOOL_RESULT_JSON:") else 450
            chunk = f"[{m['role']}]: {content[:lim]}"
            if used + len(chunk) > char_budget:
                digest_parts.append("... (earlier messages omitted)")
                break
            digest_parts.append(chunk)
            used += len(chunk)


        summary_prompt: list[dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    "Summarize the following tool-loop history in 3-5 short sentences. "
                    "Keep only: activated skills, key tool outcomes, important errors, "
                    "current intent, and files written in workspace. Do not add analysis.\n\n"
                    + "\n---\n".join(digest_parts)
                ),
            },
        ]
        response = await self.acompletion(summary_prompt, stream=False)  # type: ignore
        summary_text = (response.choices[0].message.content or "").strip()
        if not summary_text:
            raise RuntimeError("thread compaction: LLM returned empty summary")

        key_state: dict[str, Any] = {}
        for p in self._thread_key_state_paths():
            cached = self._get_cached_workspace_content(p)
            if cached is None and self._skill_runtime.workspace_exists(p):
                cached = self._skill_runtime.workspace_read(p)
                self._workspace_cache[p] = cached
                self._cache_valid_paths.add(p)
            if cached:
                if p.endswith(".json"):
                    key_state[p] = json_repair.loads(cached)
                else:
                    key_state[p] = self._truncate_text(cached, max_len=2000)

        compacted = [
            {"role": "user", "content": f"CONVERSATION_SUMMARY:\n{summary_text}"}
        ]
        if key_state:
            compacted.append(
                {
                    "role": "user",
                    "content": "KEY_STATE_JSON:\n"
                    + json.dumps(
                        {
                            "workspace_state_version": self._workspace_state_version,
                            "files": key_state,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        compacted.extend(recent_messages)
        return compacted

    # ── Batch Tool Handler ─────────────────────────────────────────────────────

    async def _handle_batch_tool(
        self,
        operations: list[dict[str, Any]],
        tick: int,
        t: datetime,
        thread_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """批量执行多个操作，减少 LLM 调用次数。

        支持的批量操作类型：
        - workspace_read: 批量读取多个文件
        - workspace_write: 批量写入多个文件
        - workspace_list: 批量列出多个目录

        Args:
            operations: 操作列表，每个操作包含 tool_name 和 arguments
            tick: 当前 tick
            t: 当前时间
            thread_messages: thread 消息列表

        Returns:
            包含所有操作结果的字典
        """
        results: list[dict[str, Any]] = []

        for op in operations:
            tool_name = op.get("tool_name", "")
            args = op.get("arguments", {})
            blocked_obj = self._check_allowed_tools_for_action(str(tool_name).strip())
            if blocked_obj is not None:
                results.append(
                    {
                        "tool_name": tool_name,
                        "ok": False,
                        "error": blocked_obj.get("error", "blocked"),
                    }
                )
                continue

            if tool_name == "workspace_read":
                # 支持批量读取
                paths = args.get("paths", [])
                if not paths:
                    path = args.get("path", "")
                    if path:
                        paths = [path]

                read_results: dict[str, Any] = {}
                for p in paths:
                    p = str(p).strip()
                    if not p:
                        continue
                    # 先检查缓存
                    cached = self._get_cached_workspace_content(p)
                    if cached is not None:
                        read_results[p] = {
                            "ok": True,
                            "content": cached,
                            "cached": True,
                        }
                    elif self._skill_runtime.workspace_exists(p):
                        content = self._skill_runtime.workspace_read(p)
                        self._workspace_cache[p] = content
                        self._cache_valid_paths.add(p)
                        read_results[p] = {
                            "ok": True,
                            "content": self._truncate_text(content, max_len=8000),
                        }
                    else:
                        read_results[p] = {"ok": False, "error": "file not found"}

                results.append(
                    {
                        "tool_name": "workspace_read",
                        "ok": all(r.get("ok", False) for r in read_results.values()),
                        "files": read_results,
                        "count": len(read_results),
                    }
                )

            elif tool_name == "workspace_write":
                # 支持批量写入
                writes = args.get("writes", {})
                if not writes:
                    path = args.get("path", "")
                    content = args.get("content", "")
                    if path:
                        writes = {path: content}

                written_paths: list[str] = []
                write_errors: list[str] = []
                for p, content in writes.items():
                    p = str(p).strip()
                    if not p:
                        continue
                    try:
                        self._skill_runtime.workspace_write(p, str(content))
                        written_paths.append(p)
                        # 失效缓存
                        self._invalidate_workspace_cache(p)
                        self._bump_workspace_state_version()
                    except Exception as e:
                        write_errors.append(f"{p}: {str(e)}")

                results.append(
                    {
                        "tool_name": "workspace_write",
                        "ok": len(write_errors) == 0,
                        "written_paths": written_paths,
                        "errors": write_errors if write_errors else None,
                        "count": len(written_paths),
                    }
                )

            elif tool_name == "workspace_list":
                paths = args.get("paths", [])
                if not paths:
                    path = args.get("path", ".")
                    paths = [path]

                list_results: dict[str, Any] = {}
                for p in paths:
                    p = str(p).strip() or "."
                    try:
                        files = self._skill_runtime.workspace_list(p)
                        list_results[p] = {
                            "ok": True,
                            "files": files[:100],
                            "count": len(files),
                        }
                    except Exception as e:
                        list_results[p] = {"ok": False, "error": str(e)}

                results.append(
                    {
                        "tool_name": "workspace_list",
                        "ok": all(r.get("ok", False) for r in list_results.values()),
                        "directories": list_results,
                    }
                )

            else:
                results.append(
                    {
                        "tool_name": tool_name,
                        "ok": False,
                        "error": f"unsupported tool in batch: {tool_name}",
                    }
                )

        return {
            "action": "batch",
            "ok": all(r.get("ok", False) for r in results),
            "results": results,
            "total_operations": len(results),
            "workspace_state_version": self._workspace_state_version,
        }

    # ── Tool Loop ─────────────────────────────────────────────────────────────

    async def _tool_loop(
        self,
        tick: int,
        t: datetime,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """执行单个 step 的工具循环。

        循环流程：
        1) 基于 thread 让 LLM 产出 ToolDecision
        2) 通过可见性/权限/依赖 gate 校验
        3) 执行工具并把结果回写 thread
        4) 直到 done 或达到轮次上限

        Args:
            tick: 当前仿真步的时间尺度（秒）。
            t: 当前仿真时间。

        Returns:
            元组 (logs, tool_history)：日志列表和工具执行历史。
        """
        logs: list[str] = []
        history: list[dict[str, Any]] = []
        thread_messages = self._skill_runtime.read_recent_thread_messages(limit=40)

        for i in range(self._max_tool_rounds):
            # 滑动摘要：当 thread 过长时压缩旧消息
            thread_messages = await self._compact_thread_if_needed(
                thread_messages, tick, t
            )

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
                self._skill_runtime.append_thread_message(
                    "user", prompt, tick=tick, t=t
                )
                self._skill_runtime.append_thread_message(
                    "assistant", decision_json, tick=tick, t=t
                )
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

            # 仅当显式选择 done 工具时立即结束。done=true 与具体工具并列时表示
            # 「执行本工具后本仿真步结束」，不得在派发工具之前 break（否则工具不会执行）。
            if action == "done":
                logs.append(f"done:{decision.summary or 'step_complete'}")
                break

            # ── disable_skill ──
            if action == "disable_skill":
                if not skill_name:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty skill_name",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("disable_skill:empty")
                    continue
                c = self._merged_person_step_constraints()
                if c and skill_name in c.forbid_disabling_skills:
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "cannot disable skill: blocked by environment step constraints",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(
                        f"disable_skill:{skill_name}:blocked_by_env_constraints"
                    )
                    continue
                self._skill_visibility_overrides[skill_name] = False
                self._activated_skills.discard(skill_name)
                if self._active_skill_scope == skill_name:
                    self._active_skill_scope = ""
                self._persist_agent_config()
                self._refresh_selectable_skills()
                result_obj = {"action": action, "skill_name": skill_name, "ok": True}
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"disable_skill:{skill_name}:ok")
                continue

            # ── enable_skill ──
            if action == "enable_skill":
                if not skill_name:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty skill_name",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("enable_skill:empty")
                    continue
                if self._skill_visibility_overrides.get(skill_name) is False:
                    del self._skill_visibility_overrides[skill_name]
                self._persist_agent_config()
                self._refresh_selectable_skills()
                if skill_name in self._all_visible_skill_names():
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": True,
                        "note": "enabled (override cleared)",
                    }
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log(
                        {"tick": tick, "time": t.isoformat(), **result_obj}
                    )
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"enable_skill:{skill_name}:ok")
                else:
                    result_obj = {
                        "action": action,
                        "skill_name": skill_name,
                        "ok": False,
                        "error": "skill not found in registry",
                    }
                    history.append(result_obj)
                    self._skill_runtime.append_tool_log(
                        {"tick": tick, "time": t.isoformat(), **result_obj}
                    )
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
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

            # ── allowed-tools gate ──
            blocked_obj = self._check_allowed_tools_for_action(action)
            if blocked_obj is not None:
                history.append(blocked_obj)
                self._append_tool_result_to_thread(
                    thread_messages, tick, t, blocked_obj
                )
                logs.append(f"{action}:blocked_allowed_tools")
                continue

            # ── activate_skill ──
            if action == "activate_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                    skill_name=skill_name,
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
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"activate:{skill_name}:blocked_requires")
                    continue

                activation_raw, activation_parts = self._split_skill_arguments(
                    args.get("arguments", "")
                )
                base_content = self._skill_runtime.skill_activate(skill_name)
                ok = bool(base_content)
                content = ""
                if ok:
                    try:
                        content = self._inject_skill_arguments(
                            base_content, activation_raw, activation_parts
                        )
                        content = await self._inject_skill_command_outputs(content)
                    except Exception as e:
                        result_obj = {
                            "action": action,
                            "skill_name": skill_name,
                            "ok": False,
                            "error": f"skill_render_failed: {e}",
                        }
                        history.append(result_obj)
                        self._append_tool_result_to_thread(
                            thread_messages, tick, t, result_obj
                        )
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
                    {
                        "tick": tick,
                        "time": t.isoformat(),
                        "action": action,
                        "skill_name": skill_name,
                        "ok": ok,
                        "size": len(content),
                    }
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"activate:{skill_name}:{'ok' if ok else 'miss'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
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
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"read:{skill_name}:{read_path}:{'ok' if ok else 'miss'}")
                continue

            # ── execute_skill ──
            if action == "execute_skill":
                dep_status = self._ensure_requires_activated(
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                    skill_name=skill_name,
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
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append(f"execute:{skill_name}:blocked_requires")
                    continue

                payload = self._coerce_llm_dict(args.get("args", {}))
                payload.setdefault("tick", tick)
                payload.setdefault("time", t.isoformat())
                out = await self.execute(skill_name, payload)
                ok = bool(out.get("ok"))
                # skill 执行可能修改多个文件：统一失效缓存并更新版本
                self._invalidate_all_workspace_cache()
                self._bump_workspace_state_version()
                if ok:
                    self._active_skill_scope = skill_name
                result_obj = {
                    "action": action,
                    "skill_name": skill_name,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "error_type": out.get("error_type"),
                    "artifacts": out.get("artifacts", []),
                    "stdout": self._truncate_text(
                        str(out.get("stdout", "")), max_len=4000
                    ),
                    "stderr": self._truncate_text(
                        str(out.get("stderr", "")), max_len=2000
                    ),
                    "workspace_state_version": self._workspace_state_version,
                }
                history.append(result_obj)
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
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"execute:{skill_name}:{'ok' if ok else 'fail'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
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
                        cached = self._get_cached_workspace_content(ws_read_path)
                        if cached is not None:
                            content = cached
                            cached_hit = True
                        else:
                            content = self._skill_runtime.workspace_read(ws_read_path)
                            self._workspace_cache[ws_read_path] = content
                            self._cache_valid_paths.add(ws_read_path)
                            cached_hit = False
                        result_obj = {
                            "action": action,
                            "path": ws_read_path,
                            "ok": True,
                            "content": self._truncate_text(content, max_len=8000),
                            "cached": cached_hit,
                        }
                except Exception as e:
                    result_obj = {
                        "action": action,
                        "path": ws_read_path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"workspace_read:{ws_read_path}:{'ok' if result_obj.get('ok') else 'fail'}"
                )
                continue

            # ── workspace_write ──
            if action == "workspace_write":
                path = str(args.get("path", ""))
                content = str(args.get("content", ""))
                try:
                    self._skill_runtime.workspace_write(path, content)
                    # 失效缓存，确保下次读取时获取最新内容
                    self._invalidate_workspace_cache(path)
                    self._bump_workspace_state_version()
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": True,
                        "size": len(content),
                    }
                except Exception as e:
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"workspace_write:{path}:{'ok' if result_obj.get('ok') else 'fail'}"
                )
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
                    result_obj = {
                        "action": action,
                        "path": path,
                        "ok": False,
                        "error": str(e),
                    }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                if result_obj.get("ok"):
                    logs.append(f"workspace_list:{path}:{result_obj.get('count', 0)}")
                else:
                    logs.append(f"workspace_list:{path}:fail")
                continue

            # ── batch ──
            if action == "batch":
                operations = args.get("operations", [])
                if not isinstance(operations, list) or not operations:
                    result_obj = {
                        "action": action,
                        "ok": False,
                        "error": "empty or invalid operations list",
                    }
                    history.append(result_obj)
                    self._append_tool_result_to_thread(
                        thread_messages, tick, t, result_obj
                    )
                    logs.append("batch:empty")
                    continue

                result_obj = await self._handle_batch_tool(
                    operations=operations,
                    tick=tick,
                    t=t,
                    thread_messages=thread_messages,
                )
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(
                    f"batch:{result_obj.get('total_operations', 0)}:{'ok' if result_obj.get('ok') else 'partial'}"
                )
                continue

            # ── bash ──
            if action == "bash":
                command = str(args.get("command", "")).strip()
                timeout_sec = int(args.get("timeout_sec", 20))
                timeout_sec = max(1, min(120, timeout_sec))
                out = await self._run_bash_in_workspace(
                    command=command, timeout_sec=timeout_sec
                )
                ok = bool(out.get("ok"))
                result_obj = {
                    "action": action,
                    "ok": ok,
                    "exit_code": out.get("exit_code"),
                    "stdout": self._truncate_text(
                        str(out.get("stdout", "")), max_len=5000
                    ),
                    "stderr": self._truncate_text(
                        str(out.get("stderr", "")), max_len=2000
                    ),
                }
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
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
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
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
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"grep:{'ok' if result_obj.get('ok') else 'fail'}")
                continue

            # ── codegen ──
            if action == "codegen":
                instruction = str(args.get("instruction", ""))
                ctx = self._coerce_llm_dict(args.get("ctx", {}))
                template_mode = bool(args.get("template_mode", False))
                out = await self._run_codegen(
                    instruction=instruction,
                    ctx=ctx,
                    template_mode=template_mode,
                )
                ok = bool(out.get("ok"))
                self._invalidate_all_workspace_cache()
                self._bump_workspace_state_version()
                result_obj: dict[str, Any] = {
                    "action": action,
                    "ok": ok,
                    "stdout": self._truncate_text(
                        str(out.get("stdout", "")), max_len=5000
                    ),
                    "stderr": self._truncate_text(
                        str(out.get("stderr", "")), max_len=2000
                    ),
                    "workspace_state_version": self._workspace_state_version,
                }
                if out.get("ctx") is not None:
                    ctx_str = json.dumps(out["ctx"], ensure_ascii=False)
                    result_obj["ctx"] = self._truncate_text(ctx_str, max_len=4000)
                history.append(result_obj)
                self._skill_runtime.append_tool_log(
                    {"tick": tick, "time": t.isoformat(), **result_obj}
                )
                self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
                logs.append(f"codegen:{'ok' if ok else 'fail'}")
                if decision.done:
                    logs.append(f"done:{decision.summary or 'step_complete'}")
                    break
                continue

            # ── unsupported action：通知 LLM ──
            valid_tools = (
                "activate_skill, read_skill, execute_skill, bash, codegen, batch, "
                "workspace_read, workspace_write, workspace_list, glob, grep, "
                "enable_skill, disable_skill, done"
            )
            hint = ""
            sk = action.strip()
            if sk and self._skill_registry.get_skill_info(sk, load_content=False):
                hint = (
                    f' Use activate_skill with arguments containing skill_name="{sk}" '
                    f'(not tool_name="{sk}").'
                )
            result_obj = {
                "action": action,
                "ok": False,
                "error": f"unsupported tool: '{action}'. Valid tools: {valid_tools}.{hint}",
            }
            history.append(result_obj)
            self._skill_runtime.append_tool_log(
                {"tick": tick, "time": t.isoformat(), **result_obj}
            )
            self._append_tool_result_to_thread(thread_messages, tick, t, result_obj)
            logs.append(f"unsupported:{action}")
            if decision.done:
                logs.append(f"done:{decision.summary or 'step_complete'}")
                break

        return logs, history

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """执行技能（转发到 runtime/registry）。

        :param skill_name: 技能名称。
        :param args: 技能参数。
        :returns: 执行结果字典。
        """
        return await self._skill_runtime.execute(skill_name=skill_name, args=args)

    async def step(self, tick: int, t: datetime) -> str:
        """执行一个仿真步并持久化会话状态与回放记录。

        流程：
        1. 步数递增，重置技能作用域
        2. 刷新可见技能列表
        3. 构建上下文快照（预读取文件）
        4. 执行工具循环
        5. 持久化会话状态和回放记录

        :param tick: 当前仿真步时间跨度（秒）。
        :param t: 当前仿真时间。
        :returns: 工具执行日志拼接字符串；如无操作返回 ``"no-action"``。
        """
        self._step_count += 1
        # 每步重新进入自由工具选择，避免上一步 skill 的 allowed-tools 作用域跨步泄漏。
        self._active_skill_scope = ""
        self._refresh_selectable_skills()
        pc = self._merged_person_step_constraints()
        if pc and pc.pin_allowed_tools_to_skill:
            pin = pc.pin_allowed_tools_to_skill.strip()
            if pin and pin in self._all_visible_skill_names():
                self._active_skill_scope = pin
        self._last_selected_skills = set(self._selectable_skill_names)

        # 构建上下文快照：预读取常用文件，注入到 system prompt
        # 这样 LLM 可以直接看到这些内容，减少 workspace_read 调用
        self._build_step_context()

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
        """通过环境路由器问答（须已 :meth:`init`）。

        :param message: 问题文本。
        :param readonly: 是否只读（只读时应避免改变环境状态）。
        :returns: 环境/系统返回的答案文本。
        :raises RuntimeError: 未初始化环境时抛出。
        """
        if self._env is None:
            raise RuntimeError("PersonAgent.ask requires an initialized environment")
        _, answer = await self.ask_env({"id": self.id}, message, readonly=readonly)
        return answer

    async def dump(self) -> dict:
        """导出最小运行状态快照（用于外部持久化/调试）。

        :returns: 可序列化字典。
        """
        return {
            "id": self.id,
            "name": self._name,
            "profile": self.get_profile(),
            "step_count": self._step_count,
            "last_selected_skills": sorted(self._last_selected_skills),
        }

    async def load(self, dump_data: dict):
        """从 :meth:`dump` 结果恢复轻量运行状态。

        :param dump_data: dump 数据。
        """
        self._step_count = int(dump_data.get("step_count", 0))
        self._last_selected_skills = set(dump_data.get("last_selected_skills", []))
