"""实验执行器"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_project_root = Path(__file__).resolve().parents[2]

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import json_repair

from agentsociety2.logger import get_logger
from agentsociety2.mcp import CreateInstanceRequest

logger = get_logger()


class ExecutorSettings(BaseSettings):
    """执行器设置"""

    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_file_required=False,
        extra="ignore",  # 忽略 .env 文件中未定义的字段
    )

    mcp_server_url: str = "http://localhost:8001/mcp"
    log_dir: Optional[str] = None
    enable_console_logging: bool = True
    default_num_steps: int = 10
    poll_interval: float = 1.0
    max_wait_time: int = 3600  # 默认60分钟（3600秒），对于多agent实验更合理


settings = ExecutorSettings()


class ExperimentResult(BaseModel):
    """实验结果"""

    instance_id: str
    experiment_name: str
    hypothesis_index: int
    group_index: int
    experiment_index: int
    status: str
    num_steps: int
    completed_steps: int = 0
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    final_status: Optional[Dict[str, Any]] = None
    experiment_results: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class ExperimentExecutor:
    """实验执行器"""

    def __init__(
        self,
        server_url: Optional[str] = None,
        log_dir: Optional[Union[str, Path]] = None,
        enable_console_logging: bool = True,
    ) -> None:
        """
        初始化实验执行器

        Args:
            server_url: MCP server 的 HTTP URL
            log_dir: 结果保存目录
            enable_console_logging: 是否启用控制台日志保存到文件
        """
        self._server_url = server_url or settings.mcp_server_url
        logger.info(f"ExperimentExecutor 初始化，MCP server: {self._server_url}")

        if log_dir is None:
            if settings.log_dir:
                self._log_dir = Path(settings.log_dir)
            else:
                self._log_dir = _project_root / "log" / "experiments"
        else:
            self._log_dir = Path(log_dir)

        self._log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"结果保存目录: {self._log_dir}")

        self._console_log_file = None
        self._console_log_handler = None
        if enable_console_logging:
            self._setup_console_logging()

    def _setup_console_logging(self) -> None:
        """设置控制台日志保存到文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            log_file = self._log_dir / f"{timestamp}_console.log"
            self._console_log_file = log_file

            root_logger = get_logger()
            file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            self._console_log_handler = file_handler

            logger.info(f"控制台日志将保存到: {log_file}")
        except Exception as e:
            logger.warning(f"设置控制台日志保存失败: {e}")

    def _cleanup_console_logging(self) -> None:
        """清理控制台日志处理器"""
        if self._console_log_handler:
            try:
                root_logger = get_logger()
                root_logger.removeHandler(self._console_log_handler)
                self._console_log_handler.close()
                self._console_log_handler = None
            except Exception as e:
                logger.warning(f"清理控制台日志处理器失败: {e}")

    async def _call_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """通过 HTTP 调用 MCP 工具"""
        async with streamablehttp_client(self._server_url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                if result.content:
                    for content_item in result.content:
                        if hasattr(content_item, "text"):
                            try:
                                return json_repair.loads(content_item.text)
                            except Exception:
                                return {"text": content_item.text}
                return {}

    async def run_experiment(
        self,
        config: CreateInstanceRequest,
        experiment_name: str = "",
        num_steps: int = 10,
        wait_for_completion: bool = True,
    ) -> ExperimentResult:
        """
        运行单个实验
        
        超时时间会根据实验规模（步数 × agents数量）自动计算。

        Args:
            config: 已验证的配置
            experiment_name: 实验名称
            num_steps: 运行的步数
            wait_for_completion: 是否等待实验完成

        Returns:
            实验结果
        """
        instance_id = config.instance_id
        logger.info(f"开始运行实验: {instance_id} ({experiment_name or instance_id}, {num_steps} 步)")

        result = ExperimentResult(
            instance_id=instance_id,
            experiment_name=experiment_name or instance_id,
            hypothesis_index=0,
            group_index=0,
            experiment_index=0,
            status="unknown",
            num_steps=num_steps,
            started_at=datetime.now().isoformat(),
            logs=[],
        )

        instance_created = False

        async def cleanup_instance() -> None:
            """清理实例"""
            if instance_created:
                try:
                    await self._call_mcp_tool("close_instance", {"instance_id": instance_id})
                    logger.info(f"已清理实验实例 {instance_id}")
                except Exception as e:
                    logger.warning(f"清理实例 {instance_id} 失败: {e}")

        try:
            try:
                status_result = await self._call_mcp_tool(
                    "get_instance_status", {"instance_id": instance_id}
                )
                if status_result.get("success"):
                    logger.warning(f"实例 {instance_id} 已存在，先清理")
                    await self._call_mcp_tool("close_instance", {"instance_id": instance_id})
            except Exception:
                pass

            create_result = await self._call_mcp_tool(
                "create_society_instance",
                {"request": config.model_dump(mode="json")},
            )

            if not create_result.get("success"):
                error_msg = create_result.get("error", "Unknown error")
                if "already exists" in error_msg.lower():
                    try:
                        await self._call_mcp_tool("close_instance", {"instance_id": instance_id})
                        create_result = await self._call_mcp_tool(
                            "create_society_instance",
                            {"request": config.model_dump(mode="json")},
                        )
                        if not create_result.get("success"):
                            raise RuntimeError(f"创建实例失败（重试后）: {create_result.get('error')}")
                    except Exception as e:
                        raise RuntimeError(f"创建实例失败: {error_msg}，清理时出错: {e}")
                else:
                    raise RuntimeError(f"创建实例失败: {error_msg}")

            result.logs.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": "instance_created",
                    "message": f"实例 {instance_id} 创建成功",
                }
            )
            instance_created = True

            logger.info(f"运行实验: {instance_id} ({num_steps} 步)")
            result.logs.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": "experiment_started",
                    "message": f"开始运行 {num_steps} 步",
                }
            )

            run_result = await self._call_mcp_tool(
                "run_instance",
                {
                    "instance_id": instance_id,
                    "num_steps": num_steps,
                    "tick": config.tick,
                },
            )

            if not run_result.get("success"):
                raise RuntimeError(f"启动运行失败: {run_result.get('error', 'Unknown error')}")

            # 等待实验完成：轮询实例状态直到完成或超时
            if wait_for_completion:
                waited_time = 0
                consecutive_errors = 0
                max_consecutive_errors = 20
                last_error_msg = None

                # 根据实验规模动态计算超时时间
                # 公式：max(基础时间300秒, 步数 × Agent数量 × 每步预估时间30秒)
                num_agents = len(config.agents) if hasattr(config, 'agents') else 1
                estimated_time = max(300, num_steps * num_agents * 30)
                timeout = max(settings.max_wait_time, estimated_time)
                logger.info(f"根据实验规模（{num_steps}步，{num_agents}个agents）设置超时时间: {timeout}秒（约 {timeout // 60} 分钟）")

                # 轮询循环：定期检查实例状态
                while waited_time < timeout:
                    await asyncio.sleep(settings.poll_interval)
                    waited_time += settings.poll_interval

                    status_result = await self._call_mcp_tool(
                        "get_instance_status", {"instance_id": instance_id}
                    )

                    if not status_result.get("success"):
                        raise RuntimeError(
                            f"获取状态失败: {status_result.get('error', 'Unknown error')}"
                        )

                    status_dict = status_result.get("status", {})
                    current_status = status_dict.get("status", "unknown")

                    # 状态处理：idle表示完成，error需要判断是否可重试，running表示进行中
                    if current_status == "idle":
                        result.status = "completed"
                        result.completed_steps = num_steps
                        result.logs.append(
                            {
                                "timestamp": datetime.now().isoformat(),
                                "event": "experiment_completed",
                                "message": f"实验完成，共运行 {num_steps} 步",
                            }
                        )
                        logger.info(f"实验 {instance_id} 完成")
                        break
                    elif current_status == "error":
                        error_msg = status_dict.get("error_message", "Unknown error")
                        # 判断错误是否可重试（如API限流、网络错误等）
                        retryable_keywords = [
                            "RateLimitError",
                            "quota exceeded",
                            "ServiceUnavailableError",
                            "APIConnectionError",
                            "Timeout",
                            "InternalServerError",
                        ]
                        is_retryable = any(
                            keyword.lower() in error_msg.lower()
                            for keyword in retryable_keywords
                        )

                        if is_retryable:
                            # 可重试错误：记录连续错误次数，超过阈值才判定为失败
                            if error_msg != last_error_msg:
                                consecutive_errors = 1
                                last_error_msg = error_msg
                            else:
                                consecutive_errors += 1

                            if consecutive_errors >= max_consecutive_errors:
                                result.status = "runtime_error"
                                result.error = error_msg
                                result.completed_steps = 0
                                break
                        else:
                            # 不可重试错误：立即判定为失败
                            result.status = "error"
                            result.error = error_msg
                            result.completed_steps = 0
                            break
                    elif current_status == "running":
                        # 实验正在运行，重置错误计数
                        if consecutive_errors > 0:
                            consecutive_errors = 0
                            last_error_msg = None

                    # 超时检查
                    if waited_time >= timeout and result.status == "unknown":
                        result.status = "timeout"
                        result.error = f"运行超时（等待超过 {timeout} 秒，约 {timeout // 60} 分钟）"
                        logger.warning(f"实验 {instance_id} 超时，当前状态: {current_status}")
                        break

            # 收集最终实验结果
            try:
                status_result = await self._call_mcp_tool(
                    "get_instance_status", {"instance_id": instance_id}
                )
                if status_result.get("success"):
                    result.final_status = status_result.get("status", {})

                results_response = await self._call_mcp_tool(
                    "get_experiment_results", {"instance_id": instance_id}
                )
                if results_response.get("success"):
                    result.experiment_results = results_response.get("experiment_results", {})
            except Exception as e:
                logger.warning(f"收集实验数据时出错: {e}")

            result.completed_at = datetime.now().isoformat()

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.completed_at = datetime.now().isoformat()
            logger.error(f"实验执行失败: {e}", exc_info=True)
            await cleanup_instance()

        return result

    async def run_experiments(
        self,
        config_file: Union[str, Path],
        experiments: List[Dict[str, Any]],
    ) -> List[ExperimentResult]:
        """
        从配置文件运行多个实验，每个实验使用不同的步数
        
        Args:
            config_file: 配置文件路径（由 config_builder 保存）
            experiments: 实验配置列表，每个元素包含：
                - "config": 实验配置字典
                - "num_steps": 该实验的步数
        
        Returns:
            实验结果列表
        """
        if not experiments:
            logger.warning("没有要运行的配置")
            return []

        logger.info(f"准备运行 {len(experiments)} 个实验")

        results = []
        try:
            for idx, exp_info in enumerate(experiments):
                config_entry = exp_info["config"]
                num_steps = exp_info["num_steps"]
                
                logger.info(
                    f"\n{'='*80}\n"
                    f"运行实验 {idx + 1}/{len(experiments)}\n"
                    f"实验名称: {config_entry.get('experiment_name', 'Unknown')}\n"
                    f"步数: {num_steps}\n"
                    f"Instance ID: {config_entry.get('instance_id')}\n"
                    f"{'='*80}"
                )

                try:
                    config_dict = config_entry["config"]
                    config = CreateInstanceRequest.model_validate(config_dict)

                    result = await self.run_experiment(
                        config,
                        experiment_name=config_entry.get("experiment_name", ""),
                        num_steps=num_steps,
                    )

                    result.hypothesis_index = config_entry.get("hypothesis_index", 0)
                    result.group_index = config_entry.get("group_index", 0)
                    result.experiment_index = config_entry.get("experiment_index", 0)

                    results.append(result)
                    
                    if config_file:
                        try:
                            self._save_single_result(result, config_file, results)
                            logger.info(f"实验 {idx + 1} 结果已保存")
                        except Exception as save_error:
                            logger.warning(f"保存实验 {idx + 1} 结果失败: {save_error}")
                except KeyboardInterrupt:
                    logger.warning(f"实验 {idx + 1} 执行过程中被中断")
                    raise
                except Exception as e:
                    logger.error(f"运行实验 {idx + 1}/{len(experiments)} 时出错: {e}", exc_info=True)
                    error_result = ExperimentResult(
                        instance_id=config_entry.get("instance_id", "unknown"),
                        experiment_name=config_entry.get("experiment_name", "Unknown"),
                        hypothesis_index=config_entry.get("hypothesis_index", 0),
                        group_index=config_entry.get("group_index", 0),
                        experiment_index=config_entry.get("experiment_index", 0),
                        status="error",
                        num_steps=num_steps,
                        error=str(e),
                        started_at=datetime.now().isoformat(),
                        completed_at=datetime.now().isoformat(),
                    )
                    results.append(error_result)
                    
                    if config_file:
                        try:
                            self._save_single_result(error_result, config_file, results)
                            logger.info(f"实验 {idx + 1} 错误结果已保存")
                        except Exception as save_error:
                            logger.warning(f"保存实验 {idx + 1} 错误结果失败: {save_error}")
        except KeyboardInterrupt:
            logger.info(f"实验执行被中断，已完成 {len(results)} 个实验")
            if config_file and results:
                try:
                    self.save_results(results, config_file=config_file)
                    logger.info(f"已保存 {len(results)} 个已完成实验的结果")
                except Exception as save_error:
                    logger.warning(f"保存中断前的结果失败: {save_error}")
            raise

        return results

    def _save_single_result(
        self,
        result: ExperimentResult,
        config_file: Union[str, Path],
        all_results: List[ExperimentResult],
    ) -> None:
        """保存单个实验结果（追加到现有结果文件）"""
        try:
            log_folder = self._log_dir
            log_folder.mkdir(parents=True, exist_ok=True)

            config_path = Path(config_file)
            config_stem = config_path.stem
            if "_configs" in config_stem:
                base_name = config_stem.replace("_configs", "")
                file_name = f"{base_name}_results.json"
            else:
                file_name = f"{config_stem}_results.json"

            json_file = log_folder / file_name

            existing_results = []
            if json_file.exists():
                try:
                    with json_file.open("r", encoding="utf-8") as f:
                        existing_data = json_repair.loads(f.read())
                        existing_results = [
                            ExperimentResult.model_validate(r)
                            for r in existing_data.get("results", [])
                        ]
                except Exception:
                    existing_results = []

            updated_results = []
            found = False
            for r in existing_results:
                if r.instance_id == result.instance_id:
                    updated_results.append(result)
                    found = True
                else:
                    updated_results.append(r)
            if not found:
                updated_results.append(result)

            saved_data = {
                "config_file": str(config_file),
                "saved_at": datetime.now().isoformat(),
                "num_experiments": len(updated_results),
                "results": [r.model_dump(mode="json") for r in updated_results],
            }

            temp_json_file = json_file.with_suffix(".tmp")
            with temp_json_file.open("w", encoding="utf-8") as f:
                json.dump(saved_data, f, indent=2, ensure_ascii=False)
            temp_json_file.replace(json_file)

        except Exception as e:
            logger.warning(f"保存单个实验结果失败: {e}")

    def _load_configs_from_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """从文件加载配置"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")

        logger.info(f"从文件加载配置: {path}")
        try:
            with path.open("r", encoding="utf-8") as f:
                content = f.read()
                data = json_repair.loads(content)
        except Exception as e:
            raise ValueError(f"无法读取文件 {path}: {e}")

        if "configs" not in data:
            raise ValueError(f"文件 {path} 中缺少 'configs' 字段")

        logger.info(f"成功从文件加载 {len(data['configs'])} 个配置")
        return data

    def save_results(
        self,
        results: List[ExperimentResult],
        config_file: Optional[Union[str, Path]] = None,
        folder_name: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> tuple[Path, Optional[Path], Optional[Path]]:
        """
        保存实验结果

        Args:
            results: 实验结果列表
            config_file: 原始配置文件路径
            folder_name: 文件夹名称
            file_name: 文件名

        Returns:
            (JSON文件路径, 详细日志文件路径, 控制台日志文件路径)
        """
        if folder_name:
            log_folder = self._log_dir / folder_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            log_folder = self._log_dir / timestamp

        log_folder.mkdir(parents=True, exist_ok=True)

        if file_name:
            if not file_name.endswith(".json"):
                file_name = f"{file_name}.json"
            if "_results" not in file_name:
                base_name = file_name.replace(".json", "")
                file_name = f"{base_name}_results.json"
        else:
            if config_file:
                try:
                    config_path = Path(config_file)
                    config_stem = config_path.stem
                    if "_configs" in config_stem:
                        base_name = config_stem.replace("_configs", "")
                        file_name = f"{base_name}_results.json"
                    else:
                        file_name = f"{config_stem}_results.json"
                except Exception:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    file_name = f"{timestamp}_experiment_results.json"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                file_name = f"{timestamp}_experiment_results.json"

        json_file = log_folder / file_name
        log_file = log_folder / file_name.replace("_results.json", ".log")

        if json_file.exists():
            timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            base_name = json_file.stem
            json_file = log_folder / f"{base_name}_{timestamp_suffix}.json"
            log_file = log_folder / f"{base_name.replace('_results', '')}_{timestamp_suffix}.log"

        saved_data = {
            "config_file": str(config_file) if config_file else None,
            "saved_at": datetime.now().isoformat(),
            "num_experiments": len(results),
            "results": [result.model_dump(mode="json") for result in results],
        }

        temp_json_file = json_file.with_suffix(".tmp")
        try:
            with temp_json_file.open("w", encoding="utf-8") as f:
                json.dump(saved_data, f, indent=2, ensure_ascii=False)
            temp_json_file.replace(json_file)
            logger.info(f"实验结果已保存到: {json_file}")
        except Exception as e:
            logger.error(f"保存结果 JSON 失败: {e}", exc_info=True)
            if temp_json_file.exists():
                temp_json_file.unlink()
            raise

        temp_log_file = log_file.with_suffix(".tmp")
        try:
            with temp_log_file.open("w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("实验运行详细日志\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"配置文件: {config_file}\n")
                f.write(f"保存时间: {datetime.now().isoformat()}\n")
                f.write(f"实验数量: {len(results)}\n\n")

                for i, result in enumerate(results, 1):
                    f.write("=" * 80 + "\n")
                    f.write(f"实验 {i}: {result.experiment_name}\n")
                    f.write("=" * 80 + "\n")
                    f.write(f"Instance ID: {result.instance_id}\n")
                    f.write(f"状态: {result.status}\n")
                    f.write(f"运行步数: {result.num_steps}\n")
                    f.write(f"完成步数: {result.completed_steps}\n")
                    f.write(f"开始时间: {result.started_at}\n")
                    f.write(f"完成时间: {result.completed_at}\n")
                    if result.error:
                        f.write(f"错误: {result.error}\n")
                    f.write("\n")

                    f.write("详细执行日志:\n")
                    f.write("-" * 80 + "\n")
                    for log_entry in result.logs:
                        timestamp = log_entry.get("timestamp", "")
                        event = log_entry.get("event", "")
                        f.write(f"[{timestamp}] {event}\n")
                        if "message" in log_entry:
                            f.write(f"  {log_entry['message']}\n")
                        if "error" in log_entry:
                            f.write(f"  错误: {log_entry['error']}\n")

                    if result.experiment_results:
                        f.write("\n实验结果摘要:\n")
                        f.write("-" * 80 + "\n")
                        f.write(json.dumps(result.experiment_results, indent=2, ensure_ascii=False))
                        f.write("\n\n")
            temp_log_file.replace(log_file)
            logger.info(f"详细日志已保存到: {log_file}")
        except Exception as e:
            logger.error(f"保存日志文件失败: {e}", exc_info=True)
            if temp_log_file.exists():
                temp_log_file.unlink()

        self._cleanup_console_logging()
        return json_file, log_file, self._console_log_file


__all__ = [
    "ExperimentExecutor",
    "ExperimentResult",
    "settings",
]



