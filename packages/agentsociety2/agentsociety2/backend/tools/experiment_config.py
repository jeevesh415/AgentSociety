"""实验配置初始化工具

根据假设、agent类型和环境模块类型，生成并验证初始化参数。
渐进式构建：先环境模块参数，再agent参数，循环验证直到都通过。
"""

from __future__ import annotations

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.mcp.registry import (
    REGISTERED_ENV_MODULES,
    REGISTERED_AGENT_MODULES,
)
from agentsociety2.code_executor.code_generator import CodeGenerator
from agentsociety2.code_executor.code_saver import CodeSaver
from agentsociety2.code_executor.dependency_detector import DependencyDetector
from agentsociety2.code_executor.local_executor import LocalCodeExecutor
from agentsociety2.code_executor.path_config import PathConfig
from agentsociety2.config import get_llm_router_and_model
from agentsociety2.logger import get_logger
from agentsociety2.society.models import InitConfig

logger = get_logger()


def _is_binary_file(file_path: Path) -> bool:
    """
    检测文件是否为二进制文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        如果是二进制文件返回True，否则返回False
    """
    try:
        # 常见的文本文件扩展名
        text_extensions = {
            '.txt', '.md', '.json', '.csv', '.tsv', '.xml', '.yaml', '.yml',
            '.py', '.js', '.ts', '.html', '.css', '.sql', '.sh', '.bat',
            '.log', '.ini', '.cfg', '.conf', '.toml', '.properties',
            '.r', '.R', '.m', '.matlab', '.java', '.cpp', '.c', '.h',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
            '.jl', '.clj', '.hs', '.elm', '.ex', '.exs', '.erl', '.hrl',
            '.lua', '.pl', '.pm', '.rkt', '.scm', '.lisp', '.cl', '.ml',
            '.fs', '.fsx', '.vb', '.cs', '.dart', '.nim', '.zig', '.v',
            '.proto', '.graphql', '.gql', '.vue', '.svelte', '.jsx', '.tsx',
            '.tex', '.latex', '.bib', '.rst', '.adoc', '.asciidoc',
            '.jsonl', '.ndjson', '.geojson', '.topojson',
        }
        
        # 检查扩展名
        if file_path.suffix.lower() in text_extensions:
            return False
        
        # 尝试读取文件的前512字节来检测二进制内容
        with open(file_path, 'rb') as f:
            chunk = f.read(512)
            # 如果包含空字节，很可能是二进制文件
            if b'\x00' in chunk:
                return True
            # 检查是否包含大量非文本字符
            text_chars = bytes({7,8,9,10,12,13,27} | set(range(0x20, 0x7f)) | set(range(0x80, 0x100)))
            # 使用bytes的translate方法，删除文本字符，如果还有剩余则可能是二进制
            non_text = chunk.translate(None, text_chars)
            if len(non_text) > len(chunk) * 0.3:  # 如果超过30%是非文本字符，认为是二进制
                return True
        
        return False
    except Exception as e:
        logger.warning(f"无法检测文件 {file_path} 是否为二进制文件: {e}")
        # 如果无法检测，默认认为是二进制文件（更安全）
        return True


def _read_text_file_preview(file_path: Path, max_chars: int = 1000) -> Tuple[str, int]:
    """
    读取文本文件的前N个字符
    
    Args:
        file_path: 文件路径
        max_chars: 最大字符数
        
    Returns:
        (文件内容预览, 总字符数)
    """
    try:
        # 尝试不同的编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
        content = None
        total_chars = 0
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    total_chars = len(content)
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if content is None:
            return "[无法读取文件: 编码不支持]", 0
        
        # 截断到最大字符数
        preview = content[:max_chars]
        if len(content) > max_chars:
            preview += f"\n... (文件总长度: {total_chars} 字符，已截断)"
        
        return preview, total_chars
    except Exception as e:
        logger.warning(f"无法读取文件 {file_path} 的预览: {e}")
        return f"[无法读取文件: {str(e)}]", 0


class ExperimentConfigTool(BaseTool):
    """实验配置工具

    根据假设、agent类型和环境模块类型，生成并验证初始化参数。
    渐进式构建：先环境模块参数，再agent参数，循环验证直到都通过。
    """

    def __init__(
        self,
        workspace_path: str,
        progress_callback,
        tool_id: str,
    ):
        super().__init__(
            workspace_path=workspace_path,
            progress_callback=progress_callback,
            tool_id=tool_id,
        )
        self._router, self._model_name = get_llm_router_and_model("coder")

    def get_name(self) -> str:
        return "experiment_config"

    def get_description(self) -> str:
        return (
            "Initialize or validate experiment configuration by generating and validating initialization parameters "
            "for agents and environment modules.\n\n"
            "When validate_only is False (default):\n"
            "The tool uses an iterative approach: first generates environment module parameters, then agent parameters, "
            "and iterates until both pass validation.\n"
            "The tool will:\n"
            "1. Read hypothesis and experiment group information\n"
            "2. Get agent and environment module descriptions\n"
            "3. Generate code to build initialization parameters\n"
            "4. Execute code directly via command line\n"
            "5. Validate parameters by attempting to create instances\n"
            "6. Save generated code to init/codes/\n"
            "7. Save intermediate results to init/temp_files/\n"
            "8. Save final validated results to init/results/\n\n"
            "When validate_only is True:\n"
            "The tool validates an existing configuration by reading init/results/init_config.json "
            "and attempting to initialize the registered classes.\n\n"
            "The tool can use data from user_data/ directory to support parameter generation."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_id": {
                    "type": "string",
                    "description": "ID of the hypothesis (e.g., '1', '2')",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "ID of the experiment within the hypothesis (e.g., '1', '2')",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum number of iteration attempts (default: 5)",
                    "default": 5,
                },
                "user_instructions": {
                    "type": "string",
                    "description": "Additional user instructions for generating experiment configuration parameters. These instructions will be considered when generating agent and environment module parameters.",
                },
                "validate_only": {
                    "type": "boolean",
                    "description": "If true, only validate existing configuration without generating new parameters. Reads from init/results/init_config.json. Default: false",
                    "default": False,
                },
            },
            "required": ["hypothesis_id", "experiment_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行实验配置初始化或验证"""
        try:
            hypothesis_id = arguments.get("hypothesis_id")
            experiment_id = arguments.get("experiment_id")
            validate_only = arguments.get("validate_only", False)
            max_iterations = arguments.get("max_iterations", 5)
            user_instructions = arguments.get("user_instructions", "")

            if not hypothesis_id or not experiment_id:
                return ToolResult(
                    success=False,
                    content="hypothesis_id and experiment_id are required",
                    error="Missing required parameters",
                )

            workspace_path = Path(self._workspace_path)
            hyp_dir = workspace_path / f"hypothesis_{hypothesis_id}"
            exp_dir = hyp_dir / f"experiment_{experiment_id}"

            if not hyp_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Hypothesis directory not found: {hyp_dir}",
                    error="Hypothesis not found",
                )

            if not exp_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Experiment directory not found: {exp_dir}",
                    error="Experiment not found",
                )

            # 读取假设和实验信息
            hypothesis_info = self._read_hypothesis_info(hyp_dir)
            experiment_info = self._read_experiment_info(exp_dir)
            sim_settings = self._read_sim_settings(hyp_dir)

            # 获取agent和env_module的描述信息
            agent_types = sim_settings.get("agentClasses", [])
            env_module_types = sim_settings.get("envModules", [])

            # 如果只是验证，执行验证逻辑
            if validate_only:
                return await self._validate_existing_config(
                    exp_dir=exp_dir,
                    agent_types=agent_types,
                    env_module_types=env_module_types,
                )

            if not agent_types:
                return ToolResult(
                    success=False,
                    content="No agent classes specified in SIM_SETTINGS.json",
                    error="Missing agent classes",
                )

            if not env_module_types:
                return ToolResult(
                    success=False,
                    content="No environment modules specified in SIM_SETTINGS.json",
                    error="Missing environment modules",
                )

            # 获取模块描述信息
            agent_descriptions = self._get_agent_descriptions(agent_types)
            env_descriptions = self._get_env_descriptions(env_module_types)

            # 创建必要的目录结构
            init_dir = exp_dir / "init"
            codes_dir = init_dir / "codes"
            temp_dir = init_dir / "temp_files"
            results_dir = init_dir / "results"

            codes_dir.mkdir(parents=True, exist_ok=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            results_dir.mkdir(parents=True, exist_ok=True)

            # 检查user_data目录，排除二进制文件
            user_data_dir = workspace_path / "user_data"
            user_data_files = []
            if user_data_dir.exists():
                all_files = list(user_data_dir.glob("*"))
                # 过滤出非二进制文件
                user_data_files = [
                    f for f in all_files 
                    if f.is_file() and not _is_binary_file(f)
                ]
                logger.info(
                    f"找到 {len(user_data_files)} 个文本数据文件 "
                    f"(共 {len(all_files)} 个文件，已排除 {len(all_files) - len(user_data_files)} 个二进制文件)"
                )

            # 渐进式生成和验证
            result = await self._iterative_generate_and_validate(
                hypothesis_info=hypothesis_info,
                experiment_info=experiment_info,
                agent_types=agent_types,
                env_module_types=env_module_types,
                agent_descriptions=agent_descriptions,
                env_descriptions=env_descriptions,
                codes_dir=codes_dir,
                temp_dir=temp_dir,
                results_dir=results_dir,
                user_data_files=user_data_files,
                max_iterations=max_iterations,
                user_instructions=user_instructions,
            )

            return result

        except Exception as e:
            logger.error(
                f"Init experiment config tool execution failed: {e}", exc_info=True
            )
            return ToolResult(
                success=False,
                content=f"Failed to initialize experiment config: {str(e)}",
                error=str(e),
            )

    # ============================================================================
    # 验证相关方法（validate_only 模式）
    # ============================================================================
    # 以下方法用于 validate_only=True 时的配置验证流程

    async def _validate_existing_config(
        self,
        exp_dir: Path,
        agent_types: List[str],
        env_module_types: List[str],
    ) -> ToolResult:
        """验证已存在的配置"""
        try:
            results_dir = exp_dir / "init" / "results"

            if not results_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Results directory not found: {results_dir}. Please run init_experiment_config first.",
                    error="Results not found",
                )

            # 读取初始化配置
            init_config_file = results_dir / "init_config.json"

            if not init_config_file.exists():
                return ToolResult(
                    success=False,
                    content=f"Initialization configuration file not found: {init_config_file}",
                    error="Init config not found",
                )

            await self._send_progress(
                ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content="Loading and validating configuration...",
                )
            )

            # 使用 pydantic 模型加载和验证配置
            try:
                config_data = json.loads(init_config_file.read_text(encoding="utf-8"))
                init_config = InitConfig.model_validate(config_data)
            except Exception as e:
                return ToolResult(
                    success=False,
                    content=f"Failed to load or validate init_config.json: {str(e)}",
                    error="Config validation failed",
                )

            if not agent_types:
                return ToolResult(
                    success=False,
                    content="No agent classes specified in SIM_SETTINGS.json",
                    error="Missing agent classes",
                )

            if not env_module_types:
                return ToolResult(
                    success=False,
                    content="No environment modules specified in SIM_SETTINGS.json",
                    error="Missing environment modules",
                )

            # 验证配置
            await self._send_progress(
                ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content="Validating configuration by initializing classes...",
                )
            )

            validation_result = await self._validate_full_config(
                init_config=init_config,
                env_module_types=env_module_types,
                agent_types=agent_types,
            )

            if validation_result["success"]:
                return ToolResult(
                    success=True,
                    content=(
                        f"Configuration validation passed!\n"
                        f"- Environment modules: {len(init_config.env_modules)}\n"
                        f"- Agents: {len(init_config.agents)}\n"
                    ),
                    data={
                        "env_modules_count": len(init_config.env_modules),
                        "agents_count": len(init_config.agents),
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    content=f"Configuration validation failed: {validation_result.get('error', 'Unknown error')}",
                    error=validation_result.get("error", "Validation failed"),
                    data={
                        "env_modules_count": len(init_config.env_modules),
                        "agents_count": len(init_config.agents),
                    },
                )

        except Exception as e:
            logger.error(
                f"Validate existing config failed: {e}", exc_info=True
            )
            return ToolResult(
                success=False,
                content=f"Failed to validate experiment config: {str(e)}",
                error=str(e),
            )

    # ============================================================================
    # 文件读取和信息获取方法
    # ============================================================================
    # 用于读取实验相关的配置文件和描述信息

    def _read_hypothesis_info(self, hyp_dir: Path) -> str | None:
        """读取假设信息"""
        hyp_md = hyp_dir / "HYPOTHESIS.md"
        if hyp_md.exists():
            return hyp_md.read_text(encoding="utf-8")
        return None

    def _read_experiment_info(self, exp_dir: Path) -> str | None:
        """读取实验信息"""
        exp_md = exp_dir / "EXPERIMENT.md"
        if exp_md.exists():
            return exp_md.read_text(encoding="utf-8")
        return None

    def _read_sim_settings(self, hyp_dir: Path) -> Dict[str, Any]:
        """读取SIM_SETTINGS.json"""
        sim_settings_file = hyp_dir / "SIM_SETTINGS.json"
        if sim_settings_file.exists():
            return json.loads(sim_settings_file.read_text(encoding="utf-8"))
        return {}

    def _get_agent_descriptions(self, agent_types: List[str]) -> Dict[str, str]:
        """获取agent类型的描述信息"""
        descriptions = {}
        agent_type_map = {
            agent_type: agent_class
            for agent_type, agent_class in REGISTERED_AGENT_MODULES
        }

        for agent_type in agent_types:
            if agent_type in agent_type_map:
                try:
                    agent_class = agent_type_map[agent_type]
                    description = agent_class.mcp_description()
                    descriptions[agent_type] = description
                except Exception as e:
                    logger.warning(
                        f"Failed to get description for agent {agent_type}: {e}"
                    )
                    descriptions[agent_type] = (
                        f"Agent type: {agent_type}, Class: {agent_class.__name__}"
                    )
            else:
                descriptions[agent_type] = f"Unknown agent type: {agent_type}"

        return descriptions

    def _get_env_descriptions(self, env_module_types: List[str]) -> Dict[str, str]:
        """获取环境模块类型的描述信息"""
        descriptions = {}
        env_type_map = {
            module_type: env_class for module_type, env_class in REGISTERED_ENV_MODULES
        }

        for module_type in env_module_types:
            if module_type in env_type_map:
                try:
                    env_class = env_type_map[module_type]
                    description = env_class.mcp_description()
                    descriptions[module_type] = description
                except Exception as e:
                    logger.warning(
                        f"Failed to get description for env module {module_type}: {e}"
                    )
                    descriptions[module_type] = (
                        f"Module type: {module_type}, Class: {env_class.__name__}"
                    )
            else:
                descriptions[module_type] = f"Unknown module type: {module_type}"

        return descriptions

    # ============================================================================
    # 验证相关方法（核心验证逻辑）
    # ============================================================================
    # 以下方法用于验证配置的正确性，通过直接初始化类进行验证

    async def _validate_env_modules(
        self,
        init_config: InitConfig,
        env_module_types: List[str],
    ) -> Dict[str, Any]:
        """验证环境模块参数（验证模块类型是否注册，以及能否成功初始化）"""
        try:
            env_type_map = {
                module_type: env_class
                for module_type, env_class in REGISTERED_ENV_MODULES
            }

            # 从 InitConfig 中获取环境模块配置
            env_module_dict = {
                module.module_type: module for module in init_config.env_modules
            }

            for module_type in env_module_types:
                # 验证模块类型是否在注册表中
                if module_type not in env_type_map:
                    return {
                        "success": False,
                        "error": f"Unknown environment module type: {module_type}. Available types: {list(env_type_map.keys())}",
                    }

                # 检查配置中是否包含该模块
                if module_type not in env_module_dict:
                    return {
                        "success": False,
                        "error": f"Environment module {module_type} not found in configuration",
                    }

                env_class = env_type_map[module_type]
                module_config = env_module_dict[module_type]
                module_kwargs = module_config.kwargs

                # 尝试直接初始化环境模块（业务逻辑验证）
                try:
                    _ = env_class(**module_kwargs)  # 初始化验证，不需要保存实例
                    logger.debug(f"Successfully initialized env module {module_type}")
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to initialize env module {module_type}: {str(e)}",
                    }

            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to validate env modules: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def _validate_agents(
        self,
        init_config: InitConfig,
        agent_types: List[str],
    ) -> Dict[str, Any]:
        """验证agent参数（验证agent类型是否注册，以及能否成功初始化）"""
        try:
            agent_type_map = {
                agent_type: agent_class
                for agent_type, agent_class in REGISTERED_AGENT_MODULES
            }

            # 只验证第一个agent以加快速度（格式已由pydantic验证）
            if not init_config.agents:
                return {
                    "success": False,
                    "error": "No agents provided",
                }

            agent_config = init_config.agents[0]
            agent_type = agent_config.agent_type
            agent_id = agent_config.agent_id
            init_kwargs = agent_config.kwargs.copy()

            # 验证agent类型是否在注册表中
            if agent_type not in agent_type_map:
                return {
                    "success": False,
                    "error": f"Unknown agent type: {agent_type}. Available types: {list(agent_type_map.keys())}",
                }

            agent_class = agent_type_map[agent_type]

            # 确保id字段存在且为整数（pydantic已验证kwargs包含id，但这里确保类型正确）
            if "id" not in init_kwargs:
                init_kwargs["id"] = int(agent_id)
            else:
                init_kwargs["id"] = int(init_kwargs["id"])

            # 尝试初始化agent（业务逻辑验证）
            try:
                _ = agent_class(**init_kwargs)  # 初始化验证，不需要保存实例
                logger.debug(
                    f"Successfully initialized agent {agent_type} with id {agent_id}"
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to initialize agent {agent_type} (id={agent_id}): {str(e)}",
                }

            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to validate agents: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def _validate_full_config(
        self,
        init_config: InitConfig,
        env_module_types: List[str],
        agent_types: List[str],
    ) -> Dict[str, Any]:
        """验证完整配置（直接初始化类进行验证）"""
        try:
            # 验证环境模块
            env_validation = await self._validate_env_modules(
                init_config=init_config,
                env_module_types=env_module_types,
            )
            if not env_validation["success"]:
                return env_validation

            # 验证agent
            agent_validation = await self._validate_agents(
                init_config=init_config,
                agent_types=agent_types,
            )
            if not agent_validation["success"]:
                return agent_validation

            # 如果都通过，返回成功
            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to validate full config: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    # ============================================================================
    # 配置生成相关方法
    # ============================================================================
    # 以下方法用于生成和验证实验配置参数

    async def _iterative_generate_and_validate(
        self,
        hypothesis_info: str | None,
        experiment_info: str | None,
        agent_types: List[str],
        env_module_types: List[str],
        agent_descriptions: Dict[str, str],
        env_descriptions: Dict[str, str],
        codes_dir: Path,
        temp_dir: Path,
        results_dir: Path,
        user_data_files: List[Path],
        max_iterations: int,
        user_instructions: str = "",
    ) -> ToolResult:
        """渐进式生成和验证参数"""

        progress_event = ToolEvent(
            tool_name=self.name,
            tool_id=self._current_tool_id,
            status="progress",
            content="开始初始化实验配置",
        )
        await self._send_progress(progress_event)

        init_config: InitConfig | None = None

        iteration = 0
        validation_errors = []

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"开始第 {iteration}/{max_iterations} 次迭代")

            progress_event = ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"开始第 {iteration}/{max_iterations} 次迭代",
            )
            await self._send_progress(progress_event)

            # 统一生成agent和env参数
            logger.info("生成配置参数（agent和env）...")
            progress_event = ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"进度: {iteration}/{max_iterations} | 正在生成配置参数（agent和env）...",
            )
            await self._send_progress(progress_event)

            config_result = await self._generate_config_params(
                hypothesis_info=hypothesis_info,
                experiment_info=experiment_info,
                agent_types=agent_types,
                env_module_types=env_module_types,
                agent_descriptions=agent_descriptions,
                env_descriptions=env_descriptions,
                existing_init_config=init_config,
                codes_dir=codes_dir,
                temp_dir=temp_dir,
                user_data_files=user_data_files,
                iteration=iteration,
                user_instructions=user_instructions,
            )

            if not config_result["success"]:
                validation_errors.append(
                    f"Iteration {iteration}: Failed to generate config params: {config_result.get('error')}"
                )
                continue

            init_config = config_result["init_config"]

            # 验证完整配置（环境模块 + agent）
            logger.info("验证完整配置...")
            progress_event = ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"进度: {iteration}/{max_iterations} | 正在验证完整配置（环境模块 + agent）...",
            )
            await self._send_progress(progress_event)

            # init_config 此时一定不为 None（因为前面已经检查过 config_result["success"]）
            assert init_config is not None, "init_config should not be None at this point"

            full_validation = await self._validate_full_config(
                init_config=init_config,
                env_module_types=env_module_types,
                agent_types=agent_types,
            )

            if full_validation["success"]:
                # 验证成功，保存结果
                logger.info("配置验证成功，保存结果...")
                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"进度: {iteration}/{max_iterations} | 配置验证成功，正在保存结果...",
                )
                await self._send_progress(progress_event)

                # 保存初始化配置（直接使用 pydantic model 导出）
                init_config_file = results_dir / "init_config.json"
                init_config_file.write_text(
                    json.dumps(
                        init_config.model_dump(),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                # 生成 steps.yaml
                steps_yaml_file = results_dir / "steps.yaml"
                await self._generate_steps_yaml(
                    steps_yaml_file=steps_yaml_file,
                    hypothesis_info=hypothesis_info,
                    experiment_info=experiment_info,
                )

                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"配置生成完成！共 {iteration} 次迭代",
                )
                await self._send_progress(progress_event)

                return ToolResult(
                    success=True,
                    content=(
                        f"Successfully generated and validated experiment configuration after {iteration} iteration(s).\n"
                        f"- Environment modules: {len(env_module_types)}\n"
                        f"- Agents: {len(init_config.agents)}\n"
                        f"- Results saved to: {results_dir}\n"
                    ),
                    data={
                        "iteration_count": iteration,
                        "env_modules": env_module_types,
                        "agent_count": len(init_config.agents),
                        "results_dir": str(results_dir),
                    },
                )
            else:
                validation_errors.append(
                    f"Iteration {iteration}: Full config validation failed: {full_validation.get('error')}"
                )
                logger.warning(
                    f"第 {iteration} 次迭代验证失败: {full_validation.get('error')}"
                )
                error_msg = full_validation.get("error", "未知错误")
                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"进度: {iteration}/{max_iterations} | 错误: {error_msg}",
                )
                await self._send_progress(progress_event)

        # 所有迭代都失败
        progress_event = ToolEvent(
            tool_name=self.name,
            tool_id=self._current_tool_id,
            status="progress",
            content=f"所有 {max_iterations} 次迭代均失败",
        )
        await self._send_progress(progress_event)

        return ToolResult(
            success=False,
            content=(
                f"Failed to generate valid configuration after {max_iterations} iterations.\n"
                f"Errors:\n"
                + "\n".join(
                    f"- {e}" for e in validation_errors[-5:]
                )  # 只显示最后5个错误
            ),
            error="Max iterations reached",
            data={
                "iteration_count": max_iterations,
                "validation_errors": validation_errors,
            },
        )

    # --- 配置参数生成 ---

    async def _generate_config_params(
        self,
        hypothesis_info: str | None,
        experiment_info: str | None,
        agent_types: List[str],
        env_module_types: List[str],
        agent_descriptions: Dict[str, str],
        env_descriptions: Dict[str, str],
        existing_init_config: InitConfig | None,
        codes_dir: Path,
        temp_dir: Path,
        user_data_files: List[Path],
        iteration: int,
        user_instructions: str = "",
    ) -> Dict[str, Any]:
        """统一生成agent和env参数，返回 InitConfig"""

        # 准备现有配置用于提示词（如果有）
        existing_env_args = {}
        existing_agent_args = []
        if existing_init_config:
            for env_module in existing_init_config.env_modules:
                existing_env_args[env_module.module_type] = env_module.kwargs
            existing_agent_args = [
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "kwargs": agent.kwargs,
                }
                for agent in existing_init_config.agents
            ]

        # 构建提示词
        prompt = self._build_unified_config_prompt(
            hypothesis_info=hypothesis_info,
            experiment_info=experiment_info,
            agent_types=agent_types,
            env_module_types=env_module_types,
            agent_descriptions=agent_descriptions,
            env_descriptions=env_descriptions,
            existing_env_args=existing_env_args,
            existing_agent_args=existing_agent_args,
            user_data_files=user_data_files,
            iteration=iteration,
            user_instructions=user_instructions,
        )
        logger.info(f"prompt: {prompt}")

        # 生成和执行代码（使用多轮对话修复）
        code_file = codes_dir / f"config_params_iter_{iteration}.py"

        result = await self._generate_and_execute_code_with_retry(
            prompt=prompt,
            code_file=code_file,
            codes_dir=codes_dir,
            temp_dir=temp_dir,
            user_data_files=user_data_files,
            iteration=iteration,
            max_retries=3,
        )

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
            }

        try:
            # 从执行结果中提取JSON
            execution_result = result["execution_result"]
            output = execution_result.stdout
            config_data = self._extract_json_from_output(output)

            # 使用 pydantic 模型验证配置格式
            try:
                init_config = InitConfig.model_validate(config_data)
            except Exception as e:
                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"迭代: {iteration} | 错误: Configuration validation failed | {str(e)}",
                )
                await self._send_progress(progress_event)
                return {
                    "success": False,
                    "error": f"Configuration validation failed: {str(e)}",
                }

            # 保存中间结果（直接使用 pydantic model 导出）
            temp_result_file = temp_dir / f"config_params_iter_{iteration}.json"
            temp_result_file.write_text(
                json.dumps(
                    init_config.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            progress_event = ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"配置参数生成完成：{len(init_config.env_modules)} 个环境模块，{len(init_config.agents)} 个agent，已保存到 {code_file.name}",
            )
            await self._send_progress(progress_event)

            return {
                "success": True,
                "init_config": init_config,
            }

        except Exception as e:
            logger.error(f"Failed to generate config params: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    # --- 代码生成和执行 ---

    async def _generate_and_execute_code_with_retry(
        self,
        prompt: str,
        code_file: Path,
        codes_dir: Path,
        temp_dir: Path,
        user_data_files: List[Path],
        iteration: int,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        生成和执行代码，支持多轮对话修复
        
        Args:
            prompt: 代码生成的提示词
            code_file: 代码文件路径
            codes_dir: 代码保存目录
            temp_dir: 临时文件目录
            user_data_files: 用户数据文件列表
            iteration: 迭代次数
            max_retries: 最大重试次数
            
        Returns:
            包含 success, code, execution_result 的字典
        """
        code_gen = CodeGenerator()
        code_saver = CodeSaver(
            PathConfig(
                work_dir=str(temp_dir),
                default_save_dir=str(codes_dir),
            )
        )
        dependency_detector = DependencyDetector()
        local_executor = LocalCodeExecutor(work_dir=temp_dir)

        previous_code = None
        error_feedback = []
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 步骤1: 生成代码
                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"迭代: {iteration} | 正在使用LLM{'修复' if retry_count > 0 else '生成'}配置参数代码...",
                )
                await self._send_progress(progress_event)

                # 传递用户数据文件路径，让LLM在代码中读取这些文件
                input_file_paths = [str(f) for f in user_data_files if f.is_file()]
                generated_code, success = await code_gen.generate_with_feedback(
                    initial_description=prompt,
                    input_files=input_file_paths,
                    max_retries=0,  # 这里不重试，由外层循环控制
                    error_feedback=error_feedback if retry_count > 0 else None,
                    previous_code=previous_code if retry_count > 0 else None,
                )

                if not success or not generated_code:
                    if retry_count < max_retries:
                        retry_count += 1
                        error_feedback.append("Failed to generate code from LLM")
                        continue
                    return {
                        "success": False,
                        "error": "Failed to generate code after retries",
                        "code": None,
                        "execution_result": None,
                    }

                # 步骤2: 检测依赖
                detected_dependencies = dependency_detector.detect(generated_code)
                logger.info(f"检测到依赖: {detected_dependencies}")

                # 步骤3: 保存代码
                code_saver.save(
                    generated_code,
                    save_path=str(code_file),
                )

                # 步骤4: 执行代码
                progress_event = ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"迭代: {iteration} | 正在执行配置参数生成代码...",
                )
                await self._send_progress(progress_event)

                execution_result = await local_executor.execute(
                    generated_code,
                    dependencies=detected_dependencies,
                    timeout=300,
                )

                if not execution_result.success:
                    error_msg = execution_result.stderr or "Unknown execution error"
                    if retry_count < max_retries:
                        retry_count += 1
                        previous_code = generated_code
                        error_feedback.append(error_msg)
                        progress_event = ToolEvent(
                            tool_name=self.name,
                            tool_id=self._current_tool_id,
                            status="progress",
                            content=f"配置参数代码执行失败（第 {retry_count}/{max_retries} 次重试），将尝试修复...\n错误: {error_msg}",
                        )
                        await self._send_progress(progress_event)
                        logger.warning(
                            f"代码执行失败，将进行第 {retry_count}/{max_retries} 次修复尝试"
                        )
                        continue
                    else:
                        progress_event = ToolEvent(
                            tool_name=self.name,
                            tool_id=self._current_tool_id,
                            status="progress",
                            content=f"迭代: {iteration} | 错误: {error_msg} | 配置参数代码执行失败",
                        )
                        await self._send_progress(progress_event)
                        return {
                            "success": False,
                            "error": f"Code execution failed after {max_retries} retries: {error_msg}",
                            "code": generated_code,
                            "execution_result": execution_result,
                        }

                # 执行成功
                return {
                    "success": True,
                    "code": generated_code,
                    "execution_result": execution_result,
                }

            except Exception as e:
                logger.error(f"代码生成或执行过程中出错: {e}", exc_info=True)
                if retry_count < max_retries:
                    retry_count += 1
                    error_feedback.append(f"Exception: {str(e)}")
                    continue
                return {
                    "success": False,
                    "error": str(e),
                    "code": None,
                    "execution_result": None,
                }

        return {
            "success": False,
            "error": f"Failed after {max_retries} retries",
            "code": None,
            "execution_result": None,
        }

    # --- 提示词构建 ---

    def _build_unified_config_prompt(
        self,
        hypothesis_info: str | None,
        experiment_info: str | None,
        agent_types: List[str],
        env_module_types: List[str],
        agent_descriptions: Dict[str, str],
        env_descriptions: Dict[str, str],
        existing_env_args: Dict[str, Dict[str, Any]],
        existing_agent_args: List[Dict[str, Any]],
        user_data_files: List[Path],
        iteration: int,
        user_instructions: str = "",
    ) -> str:
        """构建统一的配置参数生成提示词（同时生成agent和env参数）"""

        prompt_parts = [
            "You are generating initialization parameters for both agents and environment modules in an AgentSociety2 simulation.",
            "",
            "## IMPORTANT: Agent and Environment Initialization are Closely Related",
            "The initialization of agents and environment modules are tightly coupled. You need to consider:",
            "- Agent parameters may depend on environment module capabilities",
            "- Environment module parameters may need to accommodate agent requirements",
            "- Both should be designed together to ensure compatibility",
            "- You have full autonomy to decide the code logic and how to coordinate between agents and env modules",
            "",
            "## Task",
            "Generate a Python script that outputs a JSON dictionary containing initialization parameters for BOTH:",
            "1. Environment modules (env_modules)",
            "2. Agents (agents)",
            "",
            "The output should be a single JSON dictionary with two keys: 'env_modules' and 'agents'.",
            "",
            "## Hypothesis Information",
            hypothesis_info if hypothesis_info else "N/A",
            "",
            "## Experiment Information",
            experiment_info if experiment_info else "N/A",
            "",
        ]

        # 添加用户额外指令
        if user_instructions and user_instructions.strip():
            prompt_parts.extend([
                "## User Instructions",
                "The user has provided the following additional instructions that you should follow when generating the configuration parameters:",
                user_instructions.strip(),
                "",
            ])

        # CRITICAL: Add explicit type identifier constraints to prevent LLM from using class names
        prompt_parts.extend([
            "## CRITICAL: Type Identifier Format",
            "**IMPORTANT**: You MUST use the EXACT type identifiers shown below. Do NOT use class names like 'PersonAgent' or 'PrisonersDilemmaEnv'.",
            "",
            "### Allowed Environment Module Types (use these EXACT strings for 'module_type'):",
            ", ".join([f"'{t}'" for t in env_module_types]),
            "",
            "### Allowed Agent Types (use these EXACT strings for 'agent_type'):",
            ", ".join([f"'{t}'" for t in agent_types]),
            "",
            "**WARNING**: Using class names (e.g., 'PersonAgent', 'PublicGoodsEnv') instead of type identifiers (e.g., 'person_agent', 'public_goods') will cause validation errors!",
            "",
        ])

        prompt_parts.append("## Environment Module Types and Descriptions")

        for module_type in env_module_types:
            prompt_parts.append(f"### Type Identifier: `{module_type}`")
            prompt_parts.append(
                env_descriptions.get(module_type, "No description available")
            )
            prompt_parts.append("")

        prompt_parts.append("## Agent Types and Descriptions")
        for agent_type in agent_types:
            prompt_parts.append(f"### Type Identifier: `{agent_type}`")
            prompt_parts.append(
                agent_descriptions.get(agent_type, "No description available")
            )
            prompt_parts.append("")

        # 【新增】直接加载并嵌入预填充参数（根据实验使用的类名）
        # subagent可以直接看到这些默认参数，无需查询
        global_prefill_file = Path(self._workspace_path) / ".agentsociety" / "prefill_params.json"
        prefill_params = {"env_modules": {}, "agents": {}}
        if global_prefill_file.exists():
            try:
                global_prefill = json.loads(global_prefill_file.read_text(encoding="utf-8"))
                # 只提取实验使用的类的预填充参数
                env_prefill = {
                    module_type: global_prefill.get("env_modules", {}).get(module_type, {})
                    for module_type in env_module_types
                }
                agent_prefill = {
                    agent_type: global_prefill.get("agents", {}).get(agent_type, {})
                    for agent_type in agent_types
                }
                # 过滤掉空字典
                prefill_params = {
                    "env_modules": {k: v for k, v in env_prefill.items() if v},
                    "agents": {k: v for k, v in agent_prefill.items() if v}
                }
            except Exception as e:
                logger.error(f"Failed to load prefill params: {e}", exc_info=True)
        
        if prefill_params.get("env_modules") or prefill_params.get("agents"):
            prompt_parts.extend([
                "## Pre-filled Parameters (Default Parameters)",
                "The following parameters have been pre-filled as default values. You should use these directly in your generated configuration:",
                "",
                "### Environment Module Default Parameters",
                json.dumps(prefill_params.get("env_modules", {}), ensure_ascii=False, indent=2),
                "",
                "### Agent Class Default Parameters",
                json.dumps(prefill_params.get("agents", {}), ensure_ascii=False, indent=2),
                "",
                "IMPORTANT:",
                "- These are the default parameters for the environment modules and agent classes used in this experiment",
                "- You MUST use these pre-filled parameters as-is in your generated configuration",
                "- Do NOT generate new values for parameters that are already pre-filled",
                "- You can still generate other parameters that are not pre-filled",
                "- When generating agent parameters, merge the pre-filled agent parameters with your generated parameters",
                "",
            ])

        if existing_env_args or existing_agent_args:
            prompt_parts.append("## Previous Configuration (for reference)")
            if existing_env_args:
                prompt_parts.append("### Previous Environment Module Parameters")
                prompt_parts.append(
                    json.dumps(existing_env_args, ensure_ascii=False, indent=2)
                )
                prompt_parts.append("")
            if existing_agent_args:
                prompt_parts.append("### Previous Agent Parameters")
                prompt_parts.append(
                    json.dumps(existing_agent_args[:3], ensure_ascii=False, indent=2)
                )  # 只显示前3个
                prompt_parts.append("")

        # 添加用户数据文件信息
        if user_data_files:
            prompt_parts.append("## User Data Files")
            prompt_parts.append(
                "The following data files are available in the user_data/ directory. "
                "You should read these files in your code to extract necessary information "
                "for generating agent and environment module parameters."
            )
            prompt_parts.append("")

            # 计算总字符数限制（所有文件预览的总和不超过一定数量）
            total_preview_chars = 0
            max_total_preview_chars = 5000  # 所有文件预览的总字符数上限

            for file_path in user_data_files:
                preview, total_chars = _read_text_file_preview(file_path, max_chars=1000)

                # 如果已经超过总限制，只显示文件路径
                if total_preview_chars >= max_total_preview_chars:
                    prompt_parts.append(f"### File: {file_path}")
                    prompt_parts.append(f"Path: {file_path}")
                    prompt_parts.append(f"Total size: {total_chars} characters")
                    prompt_parts.append(
                        "[File content preview skipped due to total size limit]"
                    )
                    prompt_parts.append("")
                    continue

                # 计算本次预览的字符数
                preview_size = len(preview)
                remaining_budget = max_total_preview_chars - total_preview_chars

                # 如果本次预览会超过总限制，截断预览
                if preview_size > remaining_budget:
                    preview = preview[:remaining_budget]
                    preview += f"\n... (预览已截断，文件总长度: {total_chars} 字符)"
                    total_preview_chars = max_total_preview_chars
                else:
                    total_preview_chars += preview_size

                prompt_parts.append(f"### File: {file_path}")
                prompt_parts.append(f"Path: {file_path}")
                prompt_parts.append(f"Total size: {total_chars} characters")
                prompt_parts.append("Preview (first 1000 characters):")
                prompt_parts.append("```")
                prompt_parts.append(preview)
                prompt_parts.append("```")
                prompt_parts.append("")

            prompt_parts.append(
                "IMPORTANT: In your generated code, you should read these files "
                "to extract necessary information for generating agent and environment parameters. "
                "Use the file paths shown above to read the files."
            )
            prompt_parts.append("")

        # Build dynamic output format example using first available types
        example_env_type = env_module_types[0] if env_module_types else "example_env"
        example_agent_type = agent_types[0] if agent_types else "example_agent"

        prompt_parts.extend(
            [
                "## Requirements",
                "1. Read both agent and environment module descriptions carefully.",
                "2. Consider the relationships between agents and environment modules when generating parameters.",
                "3. Generate appropriate parameter values based on the hypothesis and experiment design.",
                "4. You can use read from user_data files (most recommended), random values with proper distribution (for large number of agents), or generate values as Python variables and directly assign them to the parameters (for small number of agents).",
                "5. Generate parameters for multiple agents (at least 3-5 agents recommended).",
                "6. Each agent should have a unique 'agent_id' (integer) at the top level.",
                f"7. **CRITICAL**: The 'agent_type' field MUST be one of: {', '.join([repr(t) for t in agent_types])}. Do NOT use class names!",
                f"8. **CRITICAL**: The 'module_type' field MUST be one of: {', '.join([repr(t) for t in env_module_types])}. Do NOT use class names!",
                "9. All initialization parameters (including 'id', 'profile', and all other parameters) must be placed inside a 'kwargs' dictionary.",
                "10. The 'id' in kwargs should match the 'agent_id' at the top level.",
                "11. The output must be a valid JSON dictionary.",
                "12. Print the JSON dictionary to stdout (use json.dumps with ensure_ascii=False).",
                "",
                "## Output Format",
                f"The script should print a JSON dictionary. Note: Use the EXACT type identifiers like '{example_env_type}' and '{example_agent_type}', NOT class names!",
                "{",
                '  "env_modules": [',
                '    {',
                f'      "module_type": "{example_env_type}",',
                '      "kwargs": { "param1": value1, "param2": value2, ... }',
                '    }',
                "  ],",
                '  "agents": [',
                "    {",
                '      "agent_id": 1,',
                f'      "agent_type": "{example_agent_type}",',
                '      "kwargs": {',
                '        "id": 1,',
                '        "profile": { ... },',
                '        "param1": value1,',
                "        ...",
                "      }",
                "    },",
                "    ...",
                "  ]",
                "}",
                "",
                "## Code Logic",
                "You have full autonomy to decide:",
                "- How to coordinate between agent and environment module parameter generation",
                "- The order of generation (agents first, env first, or interleaved)",
                "- How to ensure compatibility between agents and environment modules",
                "- Any helper functions or classes you need",
                "",
                "Generate the Python code:",
            ]
        )

        return "\n".join(prompt_parts)

    # --- JSON提取 ---

    def _extract_json_from_output(self, output: str) -> Any:
        """从输出中提取JSON"""
        import json_repair

        # 尝试直接解析
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON块
        import re

        json_match = re.search(r"\{.*\}", output, re.DOTALL)
        if json_match:
            try:
                return json_repair.loads(json_match.group())
            except Exception:
                pass

        # 尝试提取列表
        list_match = re.search(r"\[.*\]", output, re.DOTALL)
        if list_match:
            try:
                return json_repair.loads(list_match.group())
            except Exception:
                pass

        # 最后尝试修复整个输出
        try:
            return json_repair.loads(output)
        except Exception:
            raise ValueError(f"Could not extract JSON from output: {output[:500]}")

    # ============================================================================
    # Steps YAML生成相关方法
    # ============================================================================
    # 以下方法用于生成实验的 steps.yaml 配置文件

    async def _generate_steps_yaml(
        self,
        steps_yaml_file: Path,
        hypothesis_info: str | None,
        experiment_info: str | None,
    ) -> None:
        """生成 steps.yaml 配置文件，直接使用LLM输出YAML内容"""
        # 构建提示词，让LLM直接生成YAML配置
        prompt = self._build_steps_yaml_prompt(
            hypothesis_info=hypothesis_info,
            experiment_info=experiment_info,
        )

        # 直接调用LLM生成YAML内容
        try:
            from litellm import AllMessageValues
            
            messages: list[AllMessageValues] = [
                {"role": "user", "content": prompt}
            ]

            logger.info("Generating steps.yaml using LLM...")
            response = await self._router.acompletion(
                model=self._model_name,
                messages=messages,
                stream=False,
            )

            generated_content = response.choices[0].message.content  # type: ignore

            if not generated_content:
                raise ValueError("LLM returned empty content")

            # 提取YAML内容（可能包含markdown代码块）
            yaml_content = self._extract_yaml_from_output(generated_content)

            # 验证YAML格式
            try:
                steps_data = yaml.safe_load(yaml_content)
                if not isinstance(steps_data, dict):
                    raise ValueError("Generated YAML is not a dictionary")
                
                # 验证必需字段
                if "start_t" not in steps_data:
                    raise ValueError("Missing 'start_t' field in generated YAML")
                if "steps" not in steps_data:
                    raise ValueError("Missing 'steps' field in generated YAML")
                
                # 保存YAML文件
                steps_yaml_file.write_text(
                    yaml.dump(steps_data, allow_unicode=True, default_flow_style=False),
                    encoding="utf-8",
                )
                logger.info(f"Successfully generated steps.yaml: {steps_yaml_file}")
                
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse generated YAML: {e}, using default configuration")
                raise
            except ValueError as e:
                logger.warning(f"Generated YAML validation failed: {e}, using default configuration")
                raise

        except Exception as e:
            logger.warning(f"Failed to generate steps.yaml with LLM: {e}, using default configuration")
            # 如果生成失败，使用默认配置
            default_steps = {
                "start_t": datetime.now().isoformat(),
                "steps": [
                    {
                        "type": "run",
                        "num_steps": 10,
                        "tick": 1,
                    }
                ],
            }
            steps_yaml_file.write_text(
                yaml.dump(default_steps, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )

    # --- YAML提取 ---

    def _extract_yaml_from_output(self, output: str) -> str:
        """从LLM输出中提取YAML内容（可能包含markdown代码块）"""
        import re
        
        # 尝试提取markdown代码块中的YAML
        yaml_block_pattern = r"```(?:yaml|yml)?\s*\n(.*?)```"
        match = re.search(yaml_block_pattern, output, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块，尝试提取YAML格式的内容（以start_t开头，直到文件末尾或遇到空行+非YAML内容）
        # 匹配从 start_t 开始到文件末尾的所有内容
        yaml_start_pattern = r"(start_t:.*)"
        match = re.search(yaml_start_pattern, output, re.DOTALL)
        if match:
            yaml_content = match.group(1).strip()
            # 如果后面有非YAML内容（比如解释文字），尝试截断
            # 查找可能的结束标记（空行后跟非YAML内容）
            lines = yaml_content.split('\n')
            result_lines = []
            for line in lines:
                # 如果遇到空行且后续内容看起来不像YAML，停止
                if not line.strip():
                    if result_lines:  # 如果已经有内容，保留这个空行可能是YAML的一部分
                        result_lines.append(line)
                    continue
                # 检查是否是YAML格式的行（包含 : 或 - 开头）
                if ':' in line or line.strip().startswith('-') or line.strip().startswith('#'):
                    result_lines.append(line)
                else:
                    # 如果遇到非YAML格式的行，停止
                    break
            if result_lines:
                return '\n'.join(result_lines).strip()
            return yaml_content
        
        # 如果都没有，返回整个输出（让yaml.safe_load尝试解析）
        return output.strip()

    # --- Steps YAML提示词构建 ---

    def _build_steps_yaml_prompt(
        self,
        hypothesis_info: str | None,
        experiment_info: str | None,
    ) -> str:
        """构建生成 steps.yaml 的提示词"""
        prompt_parts = [
            "You are generating a steps.yaml configuration file for an AgentSociety2 simulation experiment.",
            "",
            "## Task",
            "Generate a valid YAML configuration file containing:",
            "1. start_t: The simulation start time (ISO format datetime string, e.g., '2024-01-01T00:00:00')",
            "2. steps: A list of simulation steps, where each step can be one of:",
            "   - run: Run simulation for a specified number of steps",
            "     Format: {type: 'run', num_steps: int, tick: int}",
            "   - run_to: Run simulation until a specific end time",
            "     Format: {type: 'run_to', end_t: str (ISO format), tick: int}",
            "   - ask: Ask the society a question",
            "     Format: {type: 'ask', question: str}",
            "   - intervene: Intervene in the society",
            "     Format: {type: 'intervene', instruction: str}",
            "",
            "## Hypothesis Information",
            hypothesis_info if hypothesis_info else "N/A",
            "",
            "## Experiment Information",
            experiment_info if experiment_info else "N/A",
            "",
            "## Requirements",
            "1. Generate appropriate start_t based on the experiment design",
            "2. Generate a sequence of steps that makes sense for the experiment",
            "3. Include a mix of run/run_to steps to advance the simulation",
            "4. Optionally include ask or intervene steps if they are relevant to the experiment",
            "5. The output MUST be valid YAML format",
            "6. Output ONLY the YAML content, without any markdown code blocks or explanations",
            "",
            "## Output Format",
            "Output the YAML content directly in the following structure:",
            "",
            "start_t: '2024-01-01T00:00:00'",
            "steps:",
            "  - type: run",
            "    num_steps: 10",
            "    tick: 1",
            "  - type: ask",
            "    question: 'What is the current state of the society?'",
            "  - type: run_to",
            "    end_t: '2024-01-01T12:00:00'",
            "    tick: 1",
            "",
            "Generate the YAML content now:",
        ]

        return "\n".join(prompt_parts)

if __name__ == "__main__":
    async def _main():
        tool = ExperimentConfigTool(
            workspace_path="/root/agentsociety/scientist_demo",
            progress_callback=None,
            tool_id="test_tool",
        )
        result = await tool.execute({
            "hypothesis_id": "1",
            "experiment_id": "3",
            "max_iterations": 5,
        })
        print(result.content)

    import asyncio
    asyncio.run(_main())
