"""假设生成工具集"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class HypothesisModel(BaseModel):
    """假设模型"""

    description: str = Field(
        ...,
        description="Concrete statement of the hypothesis to be tested",
    )
    rationale: str = Field(
        ...,
        description="Theoretical or empirical basis and motivation for this hypothesis",
    )


class ExperimentGroupModel(BaseModel):
    """实验组模型（用于假设生成阶段）"""

    name: str = Field(
        ...,
        description="Name of the experiment group",
    )
    group_type: str = Field(
        ...,
        description="Type of the experiment group (e.g., control, treatment_1, treatment_2)",
    )
    description: str = Field(
        ...,
        description="What is manipulated/varied in this group and what outcome is expected to change",
    )
    agent_selection_criteria: Optional[str] = Field(
        default=None,
        description=(
            "Explicit criteria for selecting agents, described in CONCEPTUAL terms. "
            "Examples: 'agents with collectivist/group-oriented personality', "
            "'agents with high positive mood', 'agents with moderate risk tolerance'. "
            "Use natural language or concepts, NOT specific field names."
        ),
    )


class HypothesisDataModel(BaseModel):
    """假设数据模型（包含假设和实验组）"""

    hypothesis: HypothesisModel = Field(
        ...,
        description="Hypothesis to be tested",
    )
    groups: List[ExperimentGroupModel] = Field(
        ...,
        min_length=1,
        description="Experiment groups designed to test this hypothesis (at least 1 group required)",
    )
    agent_classes: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of agent class types to use in this hypothesis's simulation. "
            "These should be agent type identifiers (e.g., 'basic_agent', 'social_agent'). "
            "Use 'list_agent_classes' tool to discover available agent types. "
            "If not provided, will be empty and can be configured later."
        ),
    )
    env_modules: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of environment module types to use in this hypothesis's simulation. "
            "These should be environment module type identifiers (e.g., 'mobility_space', 'event_space'). "
            "Use 'list_env_modules' tool to discover available environment module types. "
            "If not provided, will be empty and can be configured later."
        ),
    )


class HypothesisTool(BaseTool):
    """统一的假设管理工具，支持多种操作"""

    def get_name(self) -> str:
        return "hypothesis"

    def get_description(self) -> str:
        return (
            "Manage research hypotheses with different actions: add, get, list, delete.\n\n"
            "Available actions:\n"
            "- 'add': Add a new hypothesis to the existing experimental framework.\n"
            "- 'get': Get detailed information about a specific hypothesis.\n"
            "- 'list': List all existing hypotheses.\n"
            "- 'delete': Delete a hypothesis folder and its contents.\n\n"
            "IMPORTANT: Before calling this tool with 'add' action, you should:\n"
            "1. Call 'read_topic' tool to load TOPIC.md and understand the research topic\n"
            "2. Call 'load_literature' tool to load literature from the papers directory\n"
            "3. Call 'list_agent_classes' tool to discover available agent types\n"
            "4. Call 'list_env_modules' tool to discover available environment module types\n"
            "5. Use the loaded topic, literature, and available modules to generate hypotheses using LLM\n"
            "6. Select appropriate agent_classes and env_modules for each hypothesis based on the research needs\n"
            "7. Then call this tool with the generated hypothesis data\n\n"
            "Hypothesis Schema (for 'add' action):\n"
            "{\n"
            '  "hypothesis": {\n'
            '    "description": "Concrete, testable statement",\n'
            '    "rationale": "Why this hypothesis is worth studying"\n'
            "  },\n"
            '  "groups": [\n'
            "    {\n"
            '      "name": "Name of the experiment group",\n'
            '      "group_type": "Type (e.g., control, treatment_1, treatment_2)",\n'
            '      "description": "What is manipulated/varied and expected outcome",\n'
            '      "agent_selection_criteria": "Conceptual criteria for selecting agents (optional)"\n'
            "    }\n"
            "  ],\n"
            '  "agent_classes": ["agent_type_1", "agent_type_2"],  // Optional: List of agent class types\n'
            '  "env_modules": ["env_module_1", "env_module_2"]     // Optional: List of environment module types\n'
            "}\n\n"
            "Note on agent_classes and env_modules:\n"
            "- These fields are optional but STRONGLY RECOMMENDED\n"
            "- Use agent type identifiers from 'list_agent_classes' tool (e.g., 'basic_agent', 'social_agent')\n"
            "- Use environment module type identifiers from 'list_env_modules' tool (e.g., 'mobility_space', 'event_space')\n"
            "- Select modules that are appropriate for testing your hypothesis\n"
            "- If not provided, SIM_SETTINGS.json will have empty arrays and can be configured later\n"
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "get", "list", "delete"],
                    "description": "Action to perform: 'add' (add new), 'get' (get details), 'list' (list all), 'delete' (delete one)",
                },
                # For 'add' action
                "hypothesis": {
                    "type": "object",
                    "description": "Single hypothesis object (required for 'add' action)",
                    "properties": {
                        "hypothesis": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "rationale": {"type": "string"},
                            },
                            "required": ["description", "rationale"],
                        },
                        "groups": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "group_type": {"type": "string"},
                                    "description": {"type": "string"},
                                    "agent_selection_criteria": {"type": "string"},
                                },
                                "required": ["name", "group_type", "description"],
                            },
                        },
                        "agent_classes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "env_modules": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["hypothesis", "groups"],
                },
                # For 'get' and 'delete' actions
                "hypothesis_id": {
                    "type": "string",
                    "description": "ID of the hypothesis (e.g., '1', '2', etc.) - required for 'get' and 'delete' actions",
                },
                "hypothesis_path": {
                    "type": "string",
                    "description": "Path to the hypothesis folder (relative to workspace root, e.g., 'hypothesis_1') - alternative to hypothesis_id for 'get' and 'delete' actions",
                },
            },
            "required": ["action"],
        }

    def _resolve_path(self, file_path: str) -> Path:
        """解析文件路径"""
        path = Path(file_path)
        if not path.is_absolute() and self._workspace_path:
            path = Path(self._workspace_path) / path
        return path.resolve()

    def _find_existing_hypotheses(self) -> List[Path]:
        """查找现有的假设文件夹"""
        workspace = Path(self._workspace_path)
        hypothesis_dirs = []
        for item in workspace.iterdir():
            if item.is_dir() and item.name.startswith("hypothesis_"):
                hypothesis_dirs.append(item)
        return sorted(hypothesis_dirs)

    def _get_next_hypothesis_id(self) -> str:
        """获取下一个假设ID"""
        existing = self._find_existing_hypotheses()
        if not existing:
            return "1"
        # 提取所有ID
        ids = []
        for hyp_dir in existing:
            match = re.search(r"hypothesis_(\d+)", hyp_dir.name)
            if match:
                ids.append(int(match.group(1)))
        if not ids:
            return "1"
        return str(max(ids) + 1)

    def _create_hypothesis_structure(
        self,
        hypothesis_id: str,
        hypothesis_model: HypothesisDataModel,
    ) -> Path:
        """创建假设文件夹结构"""
        workspace = Path(self._workspace_path)
        hyp_dir = workspace / f"hypothesis_{hypothesis_id}"
        hyp_dir.mkdir(parents=True, exist_ok=True)

        # 创建 HYPOTHESIS.md
        hypothesis_md = hyp_dir / "HYPOTHESIS.md"
        hypothesis_content = self._generate_hypothesis_markdown(hypothesis_model)
        hypothesis_md.write_text(hypothesis_content, encoding="utf-8")

        # 创建 SIM_SETTINGS.json（基本结构）
        sim_settings = hyp_dir / "SIM_SETTINGS.json"
        sim_settings_data = self._generate_sim_settings(hypothesis_model)
        sim_settings.write_text(
            json.dumps(sim_settings_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 创建实验文件夹
        for idx, group in enumerate(hypothesis_model.groups, 1):
            exp_dir = hyp_dir / f"experiment_{idx}"
            exp_dir.mkdir(parents=True, exist_ok=True)

            # 创建 EXPERIMENT.md
            experiment_md = exp_dir / "EXPERIMENT.md"
            experiment_content = self._generate_experiment_markdown(group, idx)
            experiment_md.write_text(experiment_content, encoding="utf-8")

        return hyp_dir

    def _generate_hypothesis_markdown(self, hypothesis_model: HypothesisDataModel) -> str:
        """生成HYPOTHESIS.md内容"""
        lines = []
        lines.append("# Hypothesis")
        lines.append("")
        lines.append("## Description")
        lines.append("")
        lines.append(hypothesis_model.hypothesis.description)
        lines.append("")
        lines.append("## Rationale")
        lines.append("")
        lines.append(hypothesis_model.hypothesis.rationale)
        lines.append("")
        lines.append("## Experiment Groups")
        lines.append("")

        for idx, group in enumerate(hypothesis_model.groups, 1):
            lines.append(f"### Group {idx}: {group.name}")
            lines.append("")
            lines.append(f"**Type:** {group.group_type}")
            lines.append("")
            lines.append(f"**Description:** {group.description}")
            lines.append("")
            if group.agent_selection_criteria:
                lines.append(f"**Agent Selection Criteria:** {group.agent_selection_criteria}")
                lines.append("")
            lines.append("")

        return "\n".join(lines)

    def _generate_experiment_markdown(self, group: ExperimentGroupModel, exp_idx: int) -> str:
        """生成EXPERIMENT.md内容"""
        lines = []
        lines.append(f"# Experiment {exp_idx}")
        lines.append("")
        lines.append(f"**Group Name:** {group.name}")
        lines.append("")
        lines.append(f"**Group Type:** {group.group_type}")
        lines.append("")
        lines.append("## Description")
        lines.append("")
        lines.append(group.description)
        lines.append("")
        if group.agent_selection_criteria:
            lines.append("## Agent Selection Criteria")
            lines.append("")
            lines.append(group.agent_selection_criteria)
            lines.append("")
        lines.append("## Status")
        lines.append("")
        lines.append("Not initialized")
        lines.append("")

        return "\n".join(lines)

    def _generate_sim_settings(self, hypothesis_model: HypothesisDataModel) -> Dict[str, Any]:
        """生成SIM_SETTINGS.json内容
        
        注意：hypothesis 和 groups 的详细信息已存储在 HYPOTHESIS.md 和 EXPERIMENT.md 中，
        这里只存储模拟配置相关的字段（agentClasses 和 envModules）。
        """
        sim_settings = {}
        
        # 添加agent classes和env modules（如果提供）
        if hypothesis_model.agent_classes is not None:
            sim_settings["agentClasses"] = hypothesis_model.agent_classes
        else:
            sim_settings["agentClasses"] = []
        
        if hypothesis_model.env_modules is not None:
            sim_settings["envModules"] = hypothesis_model.env_modules
        else:
            sim_settings["envModules"] = []
        
        return sim_settings

    def _validate_hypothesis_schema(self, hypothesis_data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[HypothesisDataModel]]:
        """验证假设数据是否符合schema，返回验证结果和解析后的模型"""
        try:
            model = HypothesisDataModel(**hypothesis_data)
            return True, None, model
        except ValidationError as e:
            # 格式化验证错误信息
            errors = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"{field}: {msg}")
            error_msg = "; ".join(errors)
            return False, error_msg, None

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行假设管理操作"""
        action = arguments.get("action")
        
        # 发送进度报告
        if action == "add":
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content="Adding hypothesis",
            ))
        elif action == "get":
            hypothesis_id = arguments.get("hypothesis_id") or arguments.get("hypothesis_path", "")
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Getting H{hypothesis_id}",
            ))
        elif action == "list":
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content="Listing hypotheses",
            ))
        elif action == "delete":
            hypothesis_id = arguments.get("hypothesis_id") or arguments.get("hypothesis_path", "")
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Deleting H{hypothesis_id}",
            ))
        
        if action == "add":
            return await self._execute_add(arguments)
        elif action == "get":
            return await self._execute_get(arguments)
        elif action == "list":
            return await self._execute_list(arguments)
        elif action == "delete":
            return await self._execute_delete(arguments)
        else:
            return ToolResult(
                success=False,
                content=f"Unknown action: {action}. Supported actions: add, get, list, delete",
                error=f"Unknown action: {action}",
            )

    async def _execute_add(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行添加假设操作"""
        try:
            hypothesis_data = arguments.get("hypothesis")

            if not hypothesis_data:
                return ToolResult(
                    success=False,
                    content="'hypothesis' object is required for 'add' action",
                    error="Missing hypothesis parameter",
                )

            # 验证schema
            valid, error_msg, hypothesis_model = self._validate_hypothesis_schema(hypothesis_data)
            if not valid or hypothesis_model is None:
                return ToolResult(
                    success=False,
                    content=f"Hypothesis validation failed: {error_msg}",
                    error=f"Schema validation failed: {error_msg}",
                )

            # 创建新假设文件夹
            hyp_id = self._get_next_hypothesis_id()
            hyp_dir = self._create_hypothesis_structure(hyp_id, hypothesis_model)

            return ToolResult(
                success=True,
                content=(
                    f"Successfully added new hypothesis {hyp_id}:\n"
                    f"- Description: {hypothesis_model.hypothesis.description}\n"
                    f"- Path: {hyp_dir.relative_to(Path(self._workspace_path))}\n"
                    f"- Groups: {len(hypothesis_model.groups)}\n"
                    f"\n"
                    f"Note: You may want to update TOPIC.md to include this new hypothesis. "
                    f"Use write_file or patch tool to add it to the '## Hypotheses' section."
                ),
                data={
                    "hypothesis_id": hyp_id,
                    "path": str(hyp_dir.relative_to(Path(self._workspace_path))),
                    "hypothesis": {
                        "id": hyp_id,
                        "description": hypothesis_model.hypothesis.description,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Add hypothesis action failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to add hypothesis: {str(e)}",
                error=str(e),
            )

    async def _execute_get(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行获取假设详情操作"""
        try:
            hypothesis_id = arguments.get("hypothesis_id")
            hypothesis_path = arguments.get("hypothesis_path")

            workspace = Path(self._workspace_path)

            # 确定要获取的文件夹
            if hypothesis_path:
                hyp_dir = workspace / hypothesis_path
            elif hypothesis_id:
                hyp_dir = workspace / f"hypothesis_{hypothesis_id}"
            else:
                return ToolResult(
                    success=False,
                    content="Either hypothesis_id or hypothesis_path must be provided for 'get' action",
                    error="Missing parameter",
                )

            if not hyp_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Hypothesis folder not found: {hyp_dir}",
                    error="Hypothesis not found",
                )

            if not hyp_dir.is_dir():
                return ToolResult(
                    success=False,
                    content=f"Path is not a directory: {hyp_dir}",
                    error="Invalid path",
                )

            # 读取 HYPOTHESIS.md
            hyp_md = hyp_dir / "HYPOTHESIS.md"
            hypothesis_content = ""
            if hyp_md.exists():
                hypothesis_content = hyp_md.read_text(encoding="utf-8")
            else:
                return ToolResult(
                    success=False,
                    content=f"HYPOTHESIS.md not found in {hyp_dir}",
                    error="HYPOTHESIS.md not found",
                )

            # 读取 SIM_SETTINGS.json
            sim_settings = hyp_dir / "SIM_SETTINGS.json"
            sim_settings_data = {}
            if sim_settings.exists():
                try:
                    sim_settings_data = json.loads(sim_settings.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"Failed to parse SIM_SETTINGS.json: {e}")

            # 列出实验文件夹
            experiment_dirs = []
            for item in hyp_dir.iterdir():
                if item.is_dir() and item.name.startswith("experiment_"):
                    experiment_dirs.append(item.name)

            # 提取假设ID
            match = re.search(r"hypothesis_(\d+)", hyp_dir.name)
            hyp_id = match.group(1) if match else "unknown"

            return ToolResult(
                success=True,
                content=(
                    f"Hypothesis {hyp_id} details:\n"
                    f"Path: {hyp_dir.relative_to(workspace)}\n\n"
                    f"{hypothesis_content}\n\n"
                    f"Simulation Settings:\n{json.dumps(sim_settings_data, ensure_ascii=False, indent=2)}\n\n"
                    f"Experiments: {', '.join(sorted(experiment_dirs))}"
                ),
                data={
                    "hypothesis_id": hyp_id,
                    "path": str(hyp_dir.relative_to(workspace)),
                    "content": hypothesis_content,
                    "sim_settings": sim_settings_data,
                    "experiments": sorted(experiment_dirs),
                },
            )

        except Exception as e:
            logger.error(f"Get hypothesis action failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to get hypothesis: {str(e)}",
                error=str(e),
            )

    async def _execute_list(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行列出所有假设操作"""
        try:
            hypothesis_dirs = self._find_existing_hypotheses()
            
            if not hypothesis_dirs:
                return ToolResult(
                    success=True,
                    content="No hypotheses found in the workspace.",
                    data={
                        "hypotheses": [],
                        "total": 0,
                    },
                )

            hypotheses_info = []
            for hyp_dir in hypothesis_dirs:
                # 提取假设ID
                match = re.search(r"hypothesis_(\d+)", hyp_dir.name)
                hyp_id = match.group(1) if match else "unknown"

                # 读取假设描述
                hyp_md = hyp_dir / "HYPOTHESIS.md"
                description = ""
                if hyp_md.exists():
                    try:
                        content = hyp_md.read_text(encoding="utf-8")
                        # 尝试提取描述
                        if "## Description" in content:
                            desc_start = content.find("## Description") + len("## Description")
                            desc_end = content.find("##", desc_start)
                            if desc_end == -1:
                                description = content[desc_start:].strip()
                            else:
                                description = content[desc_start:desc_end].strip()
                    except Exception:
                        pass

                hypotheses_info.append({
                    "id": hyp_id,
                    "path": str(hyp_dir.relative_to(Path(self._workspace_path))),
                    "description": description[:200] if description else "",
                })

            content_parts = [f"Found {len(hypotheses_info)} hypothesis(es):\n"]
            for hyp in hypotheses_info:
                content_parts.append(f"- Hypothesis {hyp['id']}: {hyp['description'][:100]}...")
                content_parts.append(f"  Path: {hyp['path']}")

            return ToolResult(
                success=True,
                content="\n".join(content_parts),
                data={
                    "hypotheses": hypotheses_info,
                    "total": len(hypotheses_info),
                },
            )

        except Exception as e:
            logger.error(f"List hypotheses action failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to list hypotheses: {str(e)}",
                error=str(e),
            )

    async def _execute_delete(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行删除假设操作"""
        try:
            hypothesis_id = arguments.get("hypothesis_id")
            hypothesis_path = arguments.get("hypothesis_path")

            workspace = Path(self._workspace_path)

            # 确定要删除的文件夹
            if hypothesis_path:
                hyp_dir = workspace / hypothesis_path
            elif hypothesis_id:
                hyp_dir = workspace / f"hypothesis_{hypothesis_id}"
            else:
                return ToolResult(
                    success=False,
                    content="Either hypothesis_id or hypothesis_path must be provided for 'delete' action",
                    error="Missing parameter",
                )

            if not hyp_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Hypothesis folder not found: {hyp_dir}",
                    error="Hypothesis not found",
                )

            if not hyp_dir.is_dir():
                return ToolResult(
                    success=False,
                    content=f"Path is not a directory: {hyp_dir}",
                    error="Invalid path",
                )

            # 读取假设描述（用于更新TOPIC.md）
            hyp_md = hyp_dir / "HYPOTHESIS.md"
            hypothesis_description = ""
            if hyp_md.exists():
                try:
                    content = hyp_md.read_text(encoding="utf-8")
                    # 尝试提取描述
                    if "## Description" in content:
                        desc_start = content.find("## Description") + len("## Description")
                        desc_end = content.find("##", desc_start)
                        if desc_end == -1:
                            hypothesis_description = content[desc_start:].strip()
                        else:
                            hypothesis_description = content[desc_start:desc_end].strip()
                except Exception:
                    pass

            # 删除文件夹
            import shutil
            shutil.rmtree(hyp_dir)
            logger.info(f"Deleted hypothesis folder: {hyp_dir}")

            return ToolResult(
                success=True,
                content=(
                    f"Successfully deleted hypothesis: {hyp_dir.name}\n"
                    f"\n"
                    f"Note: You may want to update TOPIC.md to remove this hypothesis from the '## Hypotheses' section. "
                    f"Use write_file or patch tool to update it."
                ),
                data={
                    "deleted_path": str(hyp_dir.relative_to(workspace)),
                    "deleted_hypothesis_description": hypothesis_description[:100] if hypothesis_description else "",
                },
            )

        except Exception as e:
            logger.error(f"Delete hypothesis action failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to delete hypothesis: {str(e)}",
                error=str(e),
            )

