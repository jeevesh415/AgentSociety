"""运行实验工具

支持启动、监控和停止实验。
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class RunExperimentTool(BaseTool):
    """运行实验工具

    支持启动、监控和停止实验。
    """

    def get_name(self) -> str:
        return "run_experiment"

    def get_description(self) -> str:
        return (
            "Run, monitor, or stop AgentSociety2 simulation experiments.\n\n"
            "Actions:\n"
            "- start: Start a new experiment run. Requires hypothesis_id and experiment_id.\n"
            "- status: Check the status of a running or completed experiment. Reads pid.json and database.\n"
            "- stop: Stop a running experiment by sending SIGTERM signal to the process.\n"
            "- list: List all experiments and their running status across the workspace.\n\n"
            "The tool uses the same Python interpreter as the backend to execute the experiment CLI.\n"
            "Each experiment uses a fixed 'run' directory for execution."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "status", "stop", "list"],
                    "description": "Action to perform: start, status, stop, or list",
                },
                "hypothesis_id": {
                    "type": "string",
                    "description": "ID of the hypothesis (e.g., '1', '2'). Required for start/status/stop.",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "ID of the experiment within the hypothesis (e.g., '1', '2'). Required for start/status/stop.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行实验操作"""
        try:
            action = arguments.get("action")
            hypothesis_id = arguments.get("hypothesis_id")
            experiment_id = arguments.get("experiment_id")
            # 固定使用 "run" 作为run目录名称
            run_id = "run"

            if not action:
                return ToolResult(
                    success=False,
                    content="action is required",
                    error="Missing required parameters",
                )

            # list action 不需要 hypothesis_id 和 experiment_id
            if action == "list":
                return await self._list_experiments()

            # 其他 action 需要 hypothesis_id 和 experiment_id
            if not hypothesis_id or not experiment_id:
                return ToolResult(
                    success=False,
                    content="hypothesis_id and experiment_id are required for start/status/stop actions",
                    error="Missing required parameters",
                )

            workspace_path = Path(self._workspace_path)
            hyp_dir = workspace_path / f"hypothesis_{hypothesis_id}"
            exp_dir = hyp_dir / f"experiment_{experiment_id}"
            run_dir = exp_dir / run_id

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

            # 检查必要的配置文件
            init_config_file = exp_dir / "init" / "results" / "init_config.json"
            steps_file = exp_dir / "init" / "results" / "steps.yaml"

            if action == "start":
                # 检查是否有其他run正在运行
                running_run = await self._check_running_runs(exp_dir, exclude_run_id=run_id)
                if running_run:
                    return ToolResult(
                        success=False,
                        content=(
                            f"Another run is already running for this experiment!\n"
                            f"- Running run: {running_run['run_id']}\n"
                            f"- PID: {running_run['pid']}\n"
                            f"- Start time: {running_run.get('start_time', 'unknown')}\n\n"
                            f"Please stop the running run first before starting a new one."
                        ),
                        error="Another run is running",
                        data=running_run,
                    )
                
                return await self._start_experiment(
                    exp_dir=exp_dir,
                    run_dir=run_dir,
                    init_config_file=init_config_file,
                    steps_file=steps_file,
                    hypothesis_id=hypothesis_id,
                    experiment_id=experiment_id,
                )
            elif action == "status":
                return await self._get_status(
                    run_dir=run_dir,
                    hypothesis_id=hypothesis_id,
                    experiment_id=experiment_id,
                )
            elif action == "stop":
                return await self._stop_experiment(
                    run_dir=run_dir,
                    hypothesis_id=hypothesis_id,
                    experiment_id=experiment_id,
                )
            else:
                return ToolResult(
                    success=False,
                    content=f"Unknown action: {action}",
                    error="Invalid action",
                )

        except Exception as e:
            logger.error(
                f"Run experiment tool execution failed: {e}", exc_info=True
            )
            return ToolResult(
                success=False,
                content=f"Failed to execute experiment action: {str(e)}",
                error=str(e),
            )

    async def _check_running_runs(
        self, exp_dir: Path, exclude_run_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """检查实验目录下是否有其他run正在运行
        
        Args:
            exp_dir: 实验目录
            exclude_run_id: 要排除的run_id（通常是当前要启动的run_id）
            
        Returns:
            如果有正在运行的run，返回其信息字典；否则返回None
        """
        if not exp_dir.exists():
            return None
        
        # 遍历实验目录下的所有子目录
        for run_subdir in exp_dir.iterdir():
            if not run_subdir.is_dir():
                continue
            
            # 排除指定的run_id
            if exclude_run_id and run_subdir.name == exclude_run_id:
                continue
            
            # 检查是否有pid.json
            pid_file = run_subdir / "pid.json"
            if not pid_file.exists():
                continue
            
            try:
                pid_data = json.loads(pid_file.read_text(encoding="utf-8"))
                pid = pid_data.get("pid")
                
                # 检查进程是否真的在运行（无论pid.json中的status是什么）
                if pid:
                    try:
                        os.kill(pid, 0)  # 发送信号0检查进程是否存在
                        # 进程存在，说明这个run正在运行
                        # 如果pid.json中status不是running，也认为在运行（进程存在优先）
                        return {
                            "run_id": run_subdir.name,
                            "pid": pid,
                            "status": "running",  # 进程存在，强制设为running
                            "start_time": pid_data.get("start_time"),
                            "run_dir": str(run_subdir),
                        }
                    except OSError:
                        # 进程不存在，即使status是running也认为不在运行
                        continue
            except Exception as e:
                logger.warning(f"Failed to check run {run_subdir.name}: {e}")
                continue
        
        return None

    async def _start_experiment(
        self,
        exp_dir: Path,
        run_dir: Path,
        init_config_file: Path,
        steps_file: Path,
        hypothesis_id: str,
        experiment_id: str,
    ) -> ToolResult:
        """启动实验"""
        try:
            # 检查配置文件是否存在
            if not init_config_file.exists():
                return ToolResult(
                    success=False,
                    content=(
                        f"Initialization config file not found: {init_config_file}\n"
                        "Please run experiment_config tool first to generate the configuration."
                    ),
                    error="Config not found",
                )

            if not steps_file.exists():
                return ToolResult(
                    success=False,
                    content=(
                        f"Steps file not found: {steps_file}\n"
                        "Please run experiment_config tool first to generate the steps configuration."
                    ),
                    error="Steps not found",
                )

            # 检查是否已经在运行（根据进程存在性判断，而不只是pid.json中的status）
            pid_file = run_dir / "pid.json"
            if pid_file.exists():
                try:
                    pid_data = json.loads(pid_file.read_text(encoding="utf-8"))
                    pid = pid_data.get("pid")
                    status = pid_data.get("status", "unknown")
                    
                    # 检查进程是否真的在运行（无论pid.json中的status是什么）
                    if pid:
                        try:
                            os.kill(pid, 0)  # 发送信号0检查进程是否存在
                            # 进程存在，说明实验正在运行
                            return ToolResult(
                                success=False,
                                content=(
                                    f"Experiment is already running (PID: {pid})\n"
                                    f"Use 'stop' action to stop it first."
                                ),
                                error="Already running",
                                data={"pid": pid, "status": "running"},
                            )
                        except OSError:
                            # 进程不存在，即使status是running也可以继续启动
                            logger.info(f"PID {pid} no longer exists (status was: {status}), proceeding with start")
                except Exception as e:
                    logger.warning(f"Failed to read pid.json: {e}")

            # 创建run目录
            run_dir.mkdir(parents=True, exist_ok=True)

            # 创建日志文件路径
            stdout_log = run_dir / "stdout.log"
            stderr_log = run_dir / "stderr.log"

            # 打开日志文件（追加模式，如果文件不存在则创建）
            stdout_file = open(stdout_log, "a", encoding="utf-8")
            stderr_file = open(stderr_log, "a", encoding="utf-8")

            # 获取Python解释器路径
            python_executable = sys.executable

            # 构建CLI命令
            cli_module = "agentsociety2.society.cli"
            cmd = [
                python_executable,
                "-m",
                cli_module,
                "--config",
                str(init_config_file.resolve()),
                "--steps",
                str(steps_file.resolve()),
                "--run-dir",
                str(run_dir.resolve()),
                "--experiment-id",
                f"{hypothesis_id}/{experiment_id}",
            ]

            await self._send_progress(
                ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"Starting experiment: {hypothesis_id}/{experiment_id} (run: {run_dir.name})...",
                )
            )

            logger.info(f"Starting experiment with command: {' '.join(cmd)}")
            logger.info(f"Redirecting stdout to {stdout_log}, stderr to {stderr_log}")

            # 准备环境变量：显式传递父进程的环境变量，确保子进程可以独立运行
            # 即使父进程停止或重启，子进程也能继续执行
            env = os.environ.copy()

            # 启动实验进程（后台运行，输出重定向到文件）
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    stdin=asyncio.subprocess.DEVNULL,
                    cwd=str(exp_dir.parent),  # 在hypothesis目录下运行
                    env=env,  # 显式传递环境变量
                    preexec_fn=os.setsid if os.name != "nt" else None,  # 创建新的进程组，实现进程脱钩
                )
                
                # 进程启动后，关闭父进程的文件句柄
                # 子进程已经继承了文件描述符，可以继续写入
                stdout_file.close()
                stderr_file.close()
            except Exception as e:
                # 如果启动失败，关闭文件
                stdout_file.close()
                stderr_file.close()
                raise e

            # 等待一小段时间，让进程初始化并写入pid.json
            await asyncio.sleep(1)

            # 检查进程是否还在运行
            if process.returncode is not None:
                return ToolResult(
                    success=False,
                    content=(
                        f"Experiment process exited immediately with code {process.returncode}\n"
                        f"Check logs: {stdout_log} and {stderr_log}"
                    ),
                    error="Process exited",
                    data={
                        "pid": process.pid,
                        "returncode": process.returncode,
                        "stdout_log": str(stdout_log),
                        "stderr_log": str(stderr_log),
                    },
                )

            # 读取pid.json获取实际状态
            status_info = await self._read_status_info(run_dir)
            pid = status_info.get("pid") if status_info else process.pid

            return ToolResult(
                success=True,
                content=(
                    f"Experiment started successfully!\n"
                    f"- Hypothesis: {hypothesis_id}\n"
                    f"- Experiment: {experiment_id}\n"
                    f"- PID: {pid}\n"
                    f"- Status: {status_info.get('status', 'starting') if status_info else 'starting'}\n"
                    f"- Run directory: {run_dir}\n"
                    f"- Logs: stdout -> {stdout_log.name}, stderr -> {stderr_log.name}"
                ),
                data={
                    "pid": pid,
                    "status": status_info.get("status", "starting") if status_info else "starting",
                    "run_dir": str(run_dir),
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                    "hypothesis_id": hypothesis_id,
                    "experiment_id": experiment_id,
                },
            )

        except Exception as e:
            logger.error(f"Failed to start experiment: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to start experiment: {str(e)}",
                error=str(e),
            )

    async def _get_status(
        self,
        run_dir: Path,
        hypothesis_id: str,
        experiment_id: str,
    ) -> ToolResult:
        """获取实验状态"""
        try:
            if not run_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Run directory not found: {run_dir}\nThe experiment may not have been started yet.",
                    error="Run directory not found",
                )

            # 读取pid.json
            status_info = await self._read_status_info(run_dir)
            if not status_info:
                return ToolResult(
                    success=False,
                    content=f"pid.json not found in {run_dir}\nThe experiment may not have been started yet.",
                    error="pid.json not found",
                )

            pid = status_info.get("pid")
            status = status_info.get("status", "unknown")
            start_time = status_info.get("start_time")
            end_time = status_info.get("end_time")

            # 检查进程是否真的在运行（进程存在性优先于pid.json中的status）
            is_running = False
            if pid:
                try:
                    os.kill(pid, 0)  # 发送信号0检查进程是否存在
                    is_running = True
                    # 如果进程存在，但status不是running，更新status
                    if status != "running":
                        status = "running"
                        logger.info(f"Process {pid} exists but status was {status}, updating to running")
                except OSError:
                    # 进程不存在，即使status是running也认为不在运行
                    is_running = False
                    if status == "running":
                        status = "stopped"
                        logger.info(f"Process {pid} does not exist but status was running, updating to stopped")

            # 检查日志文件是否存在
            stdout_log = run_dir / "stdout.log"
            stderr_log = run_dir / "stderr.log"
            
            # 构建状态信息
            content_parts = [
                f"Experiment Status: {hypothesis_id}/{experiment_id}",
                f"Run ID: {run_dir.name}",
                f"PID: {pid}",
                f"Status: {status}",
            ]

            if start_time:
                content_parts.append(f"Start Time: {start_time}")
            if end_time:
                content_parts.append(f"End Time: {end_time}")

            if is_running:
                content_parts.append("Process: Running")
            else:
                content_parts.append("Process: Not running")
            
            # 添加日志文件信息
            if stdout_log.exists() or stderr_log.exists():
                content_parts.append("\nLog Files:")
                if stdout_log.exists():
                    size = stdout_log.stat().st_size
                    content_parts.append(f"- stdout.log ({size} bytes)")
                if stderr_log.exists():
                    size = stderr_log.stat().st_size
                    content_parts.append(f"- stderr.log ({size} bytes)")

            return ToolResult(
                success=True,
                content="\n".join(content_parts),
                data={
                    "pid": pid,
                    "status": status,
                    "is_running": is_running,
                    "start_time": start_time,
                    "end_time": end_time,
                    "run_dir": str(run_dir),
                    "stdout_log": str(stdout_log) if stdout_log.exists() else None,
                    "stderr_log": str(stderr_log) if stderr_log.exists() else None,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get experiment status: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to get experiment status: {str(e)}",
                error=str(e),
            )

    async def _stop_experiment(
        self,
        run_dir: Path,
        hypothesis_id: str,
        experiment_id: str,
    ) -> ToolResult:
        """停止实验"""
        try:
            if not run_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Run directory not found: {run_dir}\nThe experiment may not have been started yet.",
                    error="Run directory not found",
                )

            # 读取pid.json
            pid_file = run_dir / "pid.json"
            if not pid_file.exists():
                return ToolResult(
                    success=False,
                    content=f"pid.json not found in {run_dir}\nThe experiment may not have been started yet.",
                    error="pid.json not found",
                )

            pid_data = json.loads(pid_file.read_text(encoding="utf-8"))
            pid = pid_data.get("pid")
            status = pid_data.get("status", "unknown")

            if not pid:
                return ToolResult(
                    success=False,
                    content="PID not found in pid.json",
                    error="PID not found",
                )

            # 检查进程是否存在（进程存在性优先于pid.json中的status）
            try:
                os.kill(pid, 0)  # 发送信号0检查进程是否存在
                # 进程存在，可以停止（即使status不是running）
                if status != "running":
                    logger.info(f"Process {pid} exists but status is {status}, proceeding to stop")
            except OSError:
                # 进程不存在，即使status是running也认为不在运行
                return ToolResult(
                    success=False,
                    content=(
                        f"Process {pid} does not exist\n"
                        f"Status in pid.json was: {status}\n"
                        f"The experiment is not running."
                    ),
                    error="Process not found",
                    data={"pid": pid, "status": status},
                )

            await self._send_progress(
                ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"Stopping experiment (PID: {pid})...",
                )
            )

            # 发送SIGTERM信号
            try:
                if os.name != "nt":
                    # Linux/macOS: 尝试发送SIGTERM到进程组，如果失败则发送到进程本身
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, signal.SIGTERM)
                        logger.info(f"Sent SIGTERM to process group {pgid} (PID: {pid})")
                    except (OSError, ProcessLookupError):
                        # 进程组不存在或无法访问，直接发送到进程
                        os.kill(pid, signal.SIGTERM)
                        logger.info(f"Sent SIGTERM to process {pid}")
                else:
                    # Windows: 直接发送SIGTERM
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to process {pid}")
                
                # 等待进程退出（最多等待5秒）
                for _ in range(50):  # 50 * 0.1 = 5秒
                    try:
                        os.kill(pid, 0)
                        await asyncio.sleep(0.1)
                    except OSError:
                        # 进程已退出
                        break
                else:
                    # 如果5秒后还没退出，发送SIGKILL
                    logger.warning(f"Process {pid} did not exit after SIGTERM, sending SIGKILL")
                    try:
                        if os.name != "nt":
                            try:
                                pgid = os.getpgid(pid)
                                os.killpg(pgid, signal.SIGKILL)
                            except (OSError, ProcessLookupError):
                                os.kill(pid, signal.SIGKILL)
                        else:
                            os.kill(pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        # 进程可能已经退出
                        logger.info(f"Process {pid} already exited")

                return ToolResult(
                    success=True,
                    content=f"Experiment stopped successfully (PID: {pid})",
                    data={"pid": pid, "status": "stopped"},
                )

            except Exception as e:
                logger.error(f"Failed to stop process {pid}: {e}", exc_info=True)
                return ToolResult(
                    success=False,
                    content=f"Failed to stop experiment: {str(e)}",
                    error=str(e),
                    data={"pid": pid},
                )

        except Exception as e:
            logger.error(f"Failed to stop experiment: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to stop experiment: {str(e)}",
                error=str(e),
            )

    async def _read_status_info(self, run_dir: Path) -> Optional[Dict[str, Any]]:
        """读取pid.json文件"""
        try:
            pid_file = run_dir / "pid.json"
            if pid_file.exists():
                return json.loads(pid_file.read_text(encoding="utf-8"))
            return None
        except Exception as e:
            logger.warning(f"Failed to read pid.json: {e}")
            return None

    async def _list_experiments(self) -> ToolResult:
        """列出所有实验及其运行状态"""
        try:
            workspace_path = Path(self._workspace_path)
            if not workspace_path.exists():
                return ToolResult(
                    success=False,
                    content=f"Workspace not found: {workspace_path}",
                    error="Workspace not found",
                )

            experiments = []
            status_emoji = {
                "running": "🏃",
                "completed": "✅",
                "failed": "❌",
                "stopped": "🛑",
                "starting": "⏳",
                "unknown": "❓",
            }

            # 扫描所有 hypothesis_* 目录
            for hyp_dir in sorted(workspace_path.glob("hypothesis_*")):
                if not hyp_dir.is_dir():
                    continue

                hyp_id = hyp_dir.name.replace("hypothesis_", "")

                # 扫描该假设下的所有 experiment_* 目录
                for exp_dir in sorted(hyp_dir.glob("experiment_*")):
                    if not exp_dir.is_dir():
                        continue

                    exp_id = exp_dir.name.replace("experiment_", "")
                    run_dir = exp_dir / "run"

                    exp_info = {
                        "hypothesis_id": hyp_id,
                        "experiment_id": exp_id,
                        "path": str(exp_dir),
                        "has_init": (exp_dir / "init" / "results" / "init_config.json").exists(),
                        "has_run": run_dir.exists(),
                        "status": None,
                        "pid": None,
                        "is_running": False,
                    }

                    # 检查 run 目录中的状态
                    if run_dir.exists():
                        status_info = await self._read_status_info(run_dir)
                        if status_info:
                            pid = status_info.get("pid")
                            status = status_info.get("status", "unknown")

                            # 检查进程是否真的在运行
                            is_running = False
                            if pid:
                                try:
                                    os.kill(pid, 0)
                                    is_running = True
                                    status = "running"
                                except OSError:
                                    if status == "running":
                                        status = "stopped"

                            exp_info["status"] = status
                            exp_info["pid"] = pid
                            exp_info["is_running"] = is_running

                    experiments.append(exp_info)

            if not experiments:
                return ToolResult(
                    success=True,
                    content="No experiments found in workspace.",
                    data={"experiments": []},
                )

            # 构建输出
            content_parts = [f"Found {len(experiments)} experiment(s):\n"]

            for exp in experiments:
                status = exp["status"]
                emoji = status_emoji.get(status, "❓") if status else "⚪"
                init_mark = "✓" if exp["has_init"] else "✗"
                run_mark = "✓" if exp["has_run"] else "✗"

                line = f"{emoji} hypothesis_{exp['hypothesis_id']}/experiment_{exp['experiment_id']}"
                if exp["is_running"]:
                    line += f" (PID: {exp['pid']})"
                elif status:
                    line += f" [{status}]"

                content_parts.append(line)
                content_parts.append(f"   init: {init_mark}  run: {run_mark}")

            return ToolResult(
                success=True,
                content="\n".join(content_parts),
                data={"experiments": experiments},
            )

        except Exception as e:
            logger.error(f"Failed to list experiments: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to list experiments: {str(e)}",
                error=str(e),
            )

