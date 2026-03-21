"""
Agent Skills Loader & Registry

支持两种来源的 skill：
  1. builtin  — 随包分发，位于此目录下的子目录
  2. custom   — 用户在 workspace/custom/skills/ 下创建或导入
  3. env      — 环境模块附带，位于 env 模块的 agent_skills/ 目录

每个 skill 目录约定：
  - SKILL.md       行为规范 / prompt 模板（含 YAML frontmatter）
  - scripts/*.py   运行时入口，需导出 async def run(agent, ctx)

执行顺序由 SKILL.md 中的 priority 字段决定。
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from agentsociety2.logger import get_logger

logger = get_logger()

_BUILTIN_ROOT = Path(__file__).resolve().parent

RunFn = Callable[[Any, dict[str, Any]], Coroutine[Any, Any, None]]


@dataclass
class SkillInfo:
    """Skill 元数据（不含运行时函数，用于列表展示和 LLM 选择）

    渐进式加载设计：
    - 扫描阶段：只加载 name, description, priority 等元数据（从 frontmatter 解析）
    - 启用阶段：才加载完整的 skill_md 和 run() 函数

    Attributes:
        name: Skill 唯一标识名称
        priority: 执行优先级（数字越小越先执行）
        skill_md: SKILL.md 完整内容（延迟加载）
        description: 简短描述，供 LLM Skill Selector 选择使用
        source: 来源类型 — "builtin"、"custom" 或 "env:<ClassName>"
        path: Skill 目录的绝对路径
        enabled: 是否启用
        requires: 依赖的其他 skill 名称或能力标签列表
        provides: 此 skill 提供的能力标签列表（用于能力发现）
        provides_state: 此 skill 会给 agent 添加的状态字段列表
                       例如: ["memory", "needs", "emotion", "plan"]
                       用于渐进式披露时确定需要初始化哪些状态

    Example:
        在 SKILL.md 的 frontmatter 中声明::

            ---
            name: cognition
            description: Update emotions and form intentions
            priority: 40
            requires:
              - observation        # skill 名称
              - intention_formation  # 或能力标签
            provides:
              - intention_formation
              - emotion_update
            provides_state:
              - emotion
              - thought
              - intention
            ---
    """

    name: str
    priority: int
    skill_md: str = ""  # 延迟加载：启用时才填充
    description: str = ""  # 短描述，LLM Skill Selector 的输入
    source: str = ""  # "builtin" | "custom" | "env:<ClassName>"
    path: str = ""  # 目录绝对路径
    enabled: bool = True
    requires: list[str] = field(default_factory=list)  # 依赖的其他 skill 名称或能力标签
    provides: list[str] = field(default_factory=list)  # 提供的能力标签
    provides_state: list[str] = field(default_factory=list)  # 提供的状态字段
    _skill_md_loaded: bool = False  # 内部标记：skill_md 是否已加载


@dataclass
class LoadedSkill:
    """已加载可执行的 skill。

    包含完整的 skill 信息和运行时入口函数。

    Attributes:
        name: Skill 唯一标识名称
        priority: 执行优先级（数字越小越先执行）
        skill_md: SKILL.md 完整内容
        source: 来源类型
        run: 异步执行函数，签名为 ``async def run(agent, ctx) -> None``
        requires: 依赖的 skill 名称列表
        provides: 提供的能力标签列表
        provides_state: 提供的状态字段列表
    """

    name: str
    priority: int
    skill_md: str
    source: str
    run: RunFn
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    provides_state: list[str] = field(default_factory=list)


# ── 全局 registry（单例） ─────────────────────────────


class SkillRegistry:
    """管理所有可用的 agent skill，支持热插拔和渐进式加载。

    SkillRegistry 是全局单例，负责 skill 的发现、加载、启用/禁用和热重载。

    核心功能：
        - **发现**: 扫描 builtin/custom/env 三种来源的 skill
        - **渐进式加载**: 分两阶段加载（扫描时只读元数据，启用时加载完整内容）
        - **依赖管理**: 支持 requires/provides 声明和自动解析
        - **热插拔**: 运行时添加/移除/重载 skill

    使用示例::

        from agentsociety2.agent.skills import get_skill_registry

        registry = get_skill_registry()

        # 列出所有 skill
        for skill in registry.list_all():
            print(f"{skill.name}: {skill.description}")

        # 启用/禁用
        registry.enable("cognition")
        registry.disable("plan")

        # 加载已启用的 skill
        loaded = registry.load_enabled()
        for skill in loaded:
            await skill.run(agent, ctx)
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillInfo] = {}
        self._loaded: dict[str, LoadedSkill] = {}
        self._builtin_scanned = False
        self._custom_root: Path | None = None

    # ── 发现 ──

    def scan_builtin(self, root: Path = _BUILTIN_ROOT) -> None:
        """扫描内置 skill 目录。

        Args:
            root: 内置 skill 根目录，默认为 agent/skills/
        """
        if self._builtin_scanned:
            return
        for info in _discover_skills(root, source="builtin"):
            self._skills[info.name] = info
        self._builtin_scanned = True
        logger.info(
            f"[Skills] Scanned builtin: {[n for n in self._skills if self._skills[n].source == 'builtin']}"
        )

    def scan_custom(self, workspace_path: str | Path) -> list[str]:
        """扫描 workspace/custom/skills/ 下的自定义 skill。

        Args:
            workspace_path: 工作区根目录路径

        Returns:
            新发现的 skill 名称列表
        """
        custom_root = Path(workspace_path) / "custom" / "skills"
        self._custom_root = custom_root
        if not custom_root.is_dir():
            return []

        new_names: list[str] = []
        for info in _discover_skills(custom_root, source="custom"):
            if (
                info.name not in self._skills
                or self._skills[info.name].source == "custom"
            ):
                self._skills[info.name] = info
                # 如果之前加载过同名 skill，清除缓存以便重载
                self._loaded.pop(info.name, None)
                new_names.append(info.name)

        logger.info(f"[Skills] Scanned custom: {new_names}")
        return new_names

    def scan_env_skills(self, skills_dir: Path, env_name: str) -> list[str]:
        """扫描 env 模块附带的 agent skill。

        env skill 的 source 标记为 "env:<EnvClassName>"，
        不会覆盖同名的 builtin skill（env 补充能力，不替换核心能力）。

        Args:
            skills_dir: env 模块的 skill 目录路径
            env_name: 环境模块类名

        Returns:
            新发现的 skill 名称列表
        """
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
            self._loaded.pop(info.name, None)
            new_names.append(info.name)

        if new_names:
            logger.info(f"[Skills] Scanned env ({env_name}): {new_names}")
        return new_names

    # ── 启用 / 禁用 ──

    def enable(self, name: str) -> bool:
        """启用指定的 skill。

        Args:
            name: Skill 名称

        Returns:
            是否成功启用（若 skill 不存在则返回 False）
        """
        if name in self._skills:
            self._skills[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """禁用指定的 skill。

        禁用后会清除该 skill 的已加载缓存。

        Args:
            name: Skill 名称

        Returns:
            是否成功禁用（若 skill 不存在则返回 False）
        """
        if name in self._skills:
            self._skills[name].enabled = False
            self._loaded.pop(name, None)
            return True
        return False

    def remove_custom(self, name: str) -> bool:
        """移除自定义 skill。

        只能移除 source="custom" 的 skill，无法移除 builtin 或 env skill。

        Args:
            name: Skill 名称

        Returns:
            是否成功移除（若 skill 不存在或非 custom 则返回 False）
        """
        info = self._skills.get(name)
        if info and info.source == "custom":
            del self._skills[name]
            self._loaded.pop(name, None)
            return True
        return False

    # ── 列表 ──

    def list_all(self) -> list[SkillInfo]:
        """列出所有已发现的 skill。

        Returns:
            按 priority 排序的 SkillInfo 列表
        """
        return sorted(self._skills.values(), key=lambda s: s.priority)

    def list_enabled(self) -> list[SkillInfo]:
        """列出所有已启用的 skill。

        Returns:
            按 priority 排序的已启用 SkillInfo 列表
        """
        return [s for s in self.list_all() if s.enabled]

    def list_selection_metadata(
        self,
        names: list[str] | None = None,
        only_enabled: bool = True,
    ) -> list[dict[str, Any]]:
        """导出用于 LLM 选择的紧凑 skill 元数据目录。

        只包含选择阶段所需的字段，不触发 SKILL.md 全文加载。

        Args:
            names: 可选，限定导出的 skill 名称集合
            only_enabled: 是否仅导出已启用技能（默认 True）

        Returns:
            按 priority 排序的元数据字典列表
        """
        base = self.list_enabled() if only_enabled else self.list_all()
        name_set = set(names) if names is not None else None

        result: list[dict[str, Any]] = []
        for info in base:
            if name_set is not None and info.name not in name_set:
                continue
            result.append(
                {
                    "name": info.name,
                    "description": info.description or "",
                    "priority": info.priority,
                    "requires": list(info.requires),
                    "provides": list(info.provides),
                    "source": info.source,
                }
            )

        return result

    # ── 加载 ──

    def load_filtered(self, names: list[str]) -> list[LoadedSkill]:
        """加载指定名称的 skill（不修改 enabled 状态）。

        用于渐进式披露：只加载特定 skill 而不影响全局状态。

        Args:
            names: 要加载的 skill 名称列表

        Returns:
            按 priority 排序的 LoadedSkill 列表
        """
        infos = [s for s in self.list_all() if s.name in names]
        return self._load_infos(infos)

    def load_enabled(self) -> list[LoadedSkill]:
        """加载所有已启用的 skill。

        Returns:
            按 priority 排序的 LoadedSkill 列表
        """
        return self._load_infos(self.list_enabled())

    def _load_infos(self, infos: list[SkillInfo]) -> list[LoadedSkill]:
        """内部：加载一组 SkillInfo 为 LoadedSkill

        这是渐进式加载的第二阶段：
        1. 确保完整的 skill_md 已加载
        2. 导入 Python run() 函数
        3. 包含 requires 和 provides 信息
        """
        result: list[LoadedSkill] = []
        for info in infos:
            if info.name in self._loaded:
                result.append(self._loaded[info.name])
                continue

            # 渐进式加载：在启用时才加载完整的 skill_md
            skill_md = _ensure_skill_md_loaded(info)

            run_fn = _import_skill_run(info)
            if run_fn is None:
                logger.warning(
                    f"[Skills] Failed to load run() from skill '{info.name}', skipping"
                )
                continue

            ls = LoadedSkill(
                name=info.name,
                priority=info.priority,
                skill_md=skill_md,
                source=info.source,
                run=run_fn,
                requires=info.requires,
                provides=info.provides,
                provides_state=info.provides_state,
            )
            self._loaded[info.name] = ls
            result.append(ls)

        result.sort(key=lambda s: s.priority)
        return result

    def reload_skill(self, name: str) -> bool:
        """热重载单个 skill"""
        self._loaded.pop(name, None)
        info = self._skills.get(name)
        if not info:
            return False

        # 重置 skill_md 加载状态，强制重新加载
        info._skill_md_loaded = False
        skill_md = _ensure_skill_md_loaded(info)

        run_fn = _import_skill_run(info, force_reload=True)
        if run_fn is None:
            return False
        self._loaded[name] = LoadedSkill(
            name=info.name,
            priority=info.priority,
            skill_md=skill_md,
            source=info.source,
            run=run_fn,
            requires=info.requires,
            provides=info.provides,
            provides_state=info.provides_state,
        )
        return True

    def get_skill_info(self, name: str, load_content: bool = True) -> SkillInfo | None:
        """获取指定 skill 的信息。

        Args:
            name: skill 名称
            load_content: 是否加载完整的 skill_md 内容。
                          False 时只返回元数据，用于 LLM 选择阶段。

        Returns:
            SkillInfo 实例，如果不存在则返回 None
        """
        info = self._skills.get(name)
        if info and load_content:
            _ensure_skill_md_loaded(info)
        return info

    def load_single(
        self, name: str, load_dependencies: bool = False
    ) -> LoadedSkill | None:
        """按需加载单个 skill（渐进式加载的第二阶段）。

        用于 step 执行时，只加载 LLM 选择后的 skill。
        如果已加载则返回缓存的实例。

        Args:
            name: skill 名称
            load_dependencies: 是否自动加载依赖的 skill（默认 False）

        Returns:
            LoadedSkill 实例，如果加载失败则返回 None
        """
        # 已加载则返回缓存
        if name in self._loaded:
            return self._loaded[name]

        info = self._skills.get(name)
        if not info:
            return None

        # 如果启用依赖加载，先加载依赖项
        if load_dependencies and info.requires:
            for dep_name in info.requires:
                if dep_name not in self._loaded:
                    dep = self.load_single(dep_name, load_dependencies=True)
                    if dep is None:
                        logger.warning(
                            f"[Skills] Failed to load dependency '{dep_name}' for skill '{name}'"
                        )

        # 加载 skill_md 和 Python 模块
        skill_md = _ensure_skill_md_loaded(info)
        run_fn = _import_skill_run(info)
        if run_fn is None:
            logger.warning(f"[Skills] Failed to load run() from skill '{info.name}'")
            return None

        ls = LoadedSkill(
            name=info.name,
            priority=info.priority,
            skill_md=skill_md,
            source=info.source,
            run=run_fn,
            requires=info.requires,
            provides=info.provides,
            provides_state=info.provides_state,
        )
        self._loaded[name] = ls
        logger.debug(
            f"[Skills] Loaded skill: {name}"
            + (f" (requires: {info.requires})" if info.requires else "")
        )
        return ls

    def get_dependencies(self, name: str) -> list[str]:
        """获取 skill 的所有依赖（递归）。

        Args:
            name: skill 名称

        Returns:
            依赖的 skill 名称列表（按拓扑顺序）
        """
        info = self._skills.get(name)
        if not info or not info.requires:
            return []

        result: list[str] = []
        visited: set[str] = set()

        def _collect_deps(skill_name: str) -> None:
            if skill_name in visited:
                return
            visited.add(skill_name)
            skill_info = self._skills.get(skill_name)
            if skill_info and skill_info.requires:
                for dep in skill_info.requires:
                    _collect_deps(dep)
                    if dep not in result:
                        result.append(dep)

        _collect_deps(name)
        return result

    def validate_dependencies(self) -> dict[str, list[str]]:
        """验证所有 skill 的依赖是否满足。

        Returns:
            字典：key 为有问题的 skill 名称，value 为缺失的依赖列表
        """
        missing: dict[str, list[str]] = {}
        for name, info in self._skills.items():
            for dep in info.requires:
                if dep not in self._skills:
                    if name not in missing:
                        missing[name] = []
                    missing[name].append(dep)
        return missing

    def find_skill_by_capability(self, capability: str) -> str | None:
        """根据能力标签查找提供该能力的 skill。

        Args:
            capability: 能力标签（如 'intention_formation'）

        Returns:
            提供该能力的 skill 名称，如果没有则返回 None
        """
        for name, info in self._skills.items():
            if capability in info.provides:
                return name
        return None

    def find_skill_by_state(self, state_name: str) -> str | None:
        """根据状态字段名查找提供该状态的 skill。

        Args:
            state_name: 状态字段名（如 'emotion', 'plan', 'needs'）

        Returns:
            提供该状态的 skill 名称，如果没有则返回 None
        """
        for name, info in self._skills.items():
            if state_name in info.provides_state:
                return name
        return None

    def get_all_provided_states(self) -> set[str]:
        """获取所有 skill 提供的状态字段集合。

        Returns:
            所有状态字段名的集合
        """
        states: set[str] = set()
        for info in self._skills.values():
            states.update(info.provides_state)
        return states

    def resolve_capability_dependencies(self, requires: list[str]) -> list[str]:
        """将能力标签依赖解析为 skill 名称依赖。

        如果依赖项是 skill 名称则直接使用，如果是能力标签则查找提供该能力的 skill。

        Args:
            requires: 原始依赖列表（可包含 skill 名称或能力标签）

        Returns:
            解析后的 skill 名称列表
        """
        result: list[str] = []
        for dep in requires:
            # 首先检查是否是 skill 名称
            if dep in self._skills:
                result.append(dep)
            else:
                # 尝试作为能力标签查找
                skill_name = self.find_skill_by_capability(dep)
                if skill_name:
                    result.append(skill_name)
                else:
                    logger.warning(
                        f"[Skills] Cannot resolve dependency: '{dep}' (not a skill name or capability)"
                    )
        return result

    def clear(self) -> None:
        self._skills.clear()
        self._loaded.clear()
        self._builtin_scanned = False


# ── 全局实例 ──

_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 单例实例。

    Returns:
        SkillRegistry: 全局 skill 注册表实例。

    Example:
        >>> from agentsociety2.agent.skills import get_skill_registry
        >>> registry = get_skill_registry()
        >>> skills = registry.list_all()
    """
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.scan_builtin()
    return _registry


# ── 内部工具函数 ─────────────────────────────


def _discover_skills(root: Path, source: str) -> list[SkillInfo]:
    """从给定根目录发现 skill 子目录

    自动扫描所有子目录，从 SKILL.md frontmatter 读取 priority。
    不再依赖 _order.txt 文件。
    """
    result: list[SkillInfo] = []
    auto_priority = 100

    if not root.is_dir():
        return result

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        # 需要有 SKILL.md 或 scripts/ 才认定为 skill
        if (child / "SKILL.md").exists() or (child / "scripts").is_dir():
            result.append(_make_skill_info(child, child.name, auto_priority, source))
            auto_priority += 1

    return result


def _make_skill_info(
    skill_dir: Path, name: str, priority: int, source: str
) -> SkillInfo:
    """创建 SkillInfo，只解析 frontmatter 元数据，不加载完整 skill_md。

    这是渐进式加载的第一阶段：只读取必要的信息用于 LLM 选择。
    完整的 skill_md 内容在 skill 被启用后通过 _ensure_skill_md_loaded() 加载。
    """
    skill_md_path = skill_dir / "SKILL.md"

    # 只读取 frontmatter 部分（前几行），不读取整个文件
    meta = _parse_frontmatter_from_file(skill_md_path) if skill_md_path.exists() else {}

    # 解析 requires、provides 和 provides_state（支持列表格式）
    requires_raw = meta.get("requires", [])
    provides_raw = meta.get("provides", [])
    provides_state_raw = meta.get("provides_state", [])

    requires = (
        requires_raw
        if isinstance(requires_raw, list)
        else [requires_raw] if requires_raw else []
    )
    provides = (
        provides_raw
        if isinstance(provides_raw, list)
        else [provides_raw] if provides_raw else []
    )
    provides_state = (
        provides_state_raw
        if isinstance(provides_state_raw, list)
        else [provides_state_raw] if provides_state_raw else []
    )

    return SkillInfo(
        name=meta.get("name", name),
        priority=int(meta.get("priority", priority)),
        skill_md="",  # 延迟加载，启用时才填充
        description=meta.get("description", ""),
        source=source,
        path=str(skill_dir),
        enabled=True,
        requires=requires,
        provides=provides,
        provides_state=provides_state,
        _skill_md_loaded=False,
    )


def _ensure_skill_md_loaded(info: SkillInfo) -> str:
    """确保 skill_md 已加载（渐进式加载的第二阶段）。

    如果尚未加载，从文件读取完整内容。
    """
    if info._skill_md_loaded:
        return info.skill_md

    skill_md_path = Path(info.path) / "SKILL.md"
    if skill_md_path.exists():
        info.skill_md = skill_md_path.read_text(encoding="utf-8")
    info._skill_md_loaded = True
    return info.skill_md


def _parse_frontmatter_from_file(skill_md_path: Path) -> dict[str, Any]:
    """只解析文件开头的 YAML frontmatter，不读取整个文件。

    这个函数优化了内存使用：只读取 frontmatter 部分（通常只有几行），
    而不是整个 SKILL.md 文件（可能很大）。
    """
    if not skill_md_path.exists():
        return {}

    try:
        # 只读取文件开头部分，找到 frontmatter 结束位置
        with open(skill_md_path, "r", encoding="utf-8") as f:
            lines = []
            in_frontmatter = False
            delimiter_count = 0

            for line in f:
                stripped = line.strip()

                # 检查 frontmatter 开始/结束标记
                if stripped == "---":
                    delimiter_count += 1
                    if delimiter_count == 1:
                        in_frontmatter = True
                        continue
                    elif delimiter_count == 2:
                        # frontmatter 结束
                        break

                if in_frontmatter:
                    lines.append(stripped)

                # 安全限制：最多读取 50 行（frontmatter 通常很短）
                if len(lines) > 50:
                    break

        # 解析收集到的 frontmatter 行
        return _parse_frontmatter_lines(lines)
    except Exception:
        return {}


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
    """解析 frontmatter 行列表为字典。"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in lines:
        if not line:
            continue

        # 列表项
        if (
            line.startswith("- ")
            and current_key is not None
            and current_list is not None
        ):
            current_list.append(line[2:].strip())
            continue

        # 提交上一个列表
        if current_key and current_list is not None:
            result[current_key] = current_list
            current_key = None
            current_list = None

        # key: value
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if not val:
                # 下一行可能是列表
                current_key = key
                current_list = []
            else:
                result[key] = val

    # 提交最后一个
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _parse_frontmatter(md_text: str) -> dict[str, Any]:
    """解析 SKILL.md 开头的 YAML frontmatter（--- ... ---）"""
    if not md_text.startswith("---"):
        return {}
    parts = md_text.split("---", 2)
    if len(parts) < 3:
        return {}
    yaml_str = parts[1].strip()
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in yaml_str.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # 列表项
        if (
            stripped.startswith("- ")
            and current_key is not None
            and current_list is not None
        ):
            current_list.append(stripped[2:].strip())
            continue

        # 提交上一个列表
        if current_key and current_list is not None:
            result[current_key] = current_list
            current_key = None
            current_list = None

        # key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if not val:
                # 下一行可能是列表
                current_key = key
                current_list = []
            else:
                result[key] = val

    # 提交最后一个
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _import_skill_run(info: SkillInfo, force_reload: bool = False) -> RunFn | None:
    """动态导入 skill 的 run() 函数"""
    skill_dir = Path(info.path)
    scripts_dir = skill_dir / "scripts"

    if not scripts_dir.is_dir():
        return None

    # 找到入口脚本：优先 <name>.py，否则取第一个 .py
    entry = scripts_dir / f"{info.name}.py"
    if not entry.exists():
        py_files = list(scripts_dir.glob("*.py"))
        py_files = [f for f in py_files if f.name != "__init__.py"]
        if not py_files:
            return None
        entry = py_files[0]

    if info.source == "builtin":
        # builtin skill 通过包路径导入
        module_name = f"agentsociety2.agent.skills.{info.name}.scripts.{entry.stem}"
        if force_reload and module_name in sys.modules:
            del sys.modules[module_name]
        mod = importlib.import_module(module_name)
    else:
        # custom skill 通过文件路径动态导入
        module_name = f"custom_skill_{info.name}_{entry.stem}"
        if force_reload and module_name in sys.modules:
            del sys.modules[module_name]

        # 为自定义 skill 暴露导入路径，支持入口脚本引用同 skill 目录下的辅助模块。
        scripts_dir_str = str(scripts_dir)
        skill_dir_str = str(skill_dir)
        if scripts_dir_str not in sys.path:
            sys.path.insert(0, scripts_dir_str)
        if skill_dir_str not in sys.path:
            sys.path.insert(0, skill_dir_str)

        if module_name in sys.modules:
            mod = sys.modules[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, str(entry))
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

    return getattr(mod, "run", None)
