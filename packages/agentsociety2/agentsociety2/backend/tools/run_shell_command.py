"""运行Shell命令工具"""

from __future__ import annotations

import asyncio
import os
import platform
from pathlib import Path
from typing import Dict, Any, List

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class RunShellCommandTool(BaseTool):
    """Tool for executing shell commands"""

    def get_name(self) -> str:
        return "run_shell_command"

    def get_description(self) -> str:
        return (
            "Execute shell commands in the system. "
            "This tool runs shell commands and returns detailed execution results including "
            "stdout, stderr, exit code, and background process IDs. "
            "Commands can be run in the background using '&' at the end. "
            "On Windows, commands are executed with PowerShell. On other platforms, bash is used."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command to execute (required)",
                },
                "description": {
                    "type": "string",
                    "description": "A brief description of the command's purpose (optional)",
                },
                "directory": {
                    "type": "string",
                    "description": "The directory (relative to the workspace root) in which to execute the command (optional)",
                },
            },
            "required": ["command"],
        }

    def _detect_background_processes(self, command: str) -> tuple[str, bool]:
        """
        检测命令是否包含后台执行标记 (&)

        Returns:
            (cleaned_command, is_background)
        """
        command = command.strip()
        is_background = command.endswith("&")
        if is_background:
            command = command[:-1].strip()
        return command, is_background

    def _get_shell_command(self) -> tuple[str, List[str]]:
        """
        根据平台获取shell命令

        Returns:
            (shell_executable, shell_args)
        """
        if platform.system() == "Windows":
            # Windows使用PowerShell
            comspec = os.environ.get("ComSpec", "powershell.exe")
            if comspec.endswith("powershell.exe"):
                return comspec, ["-NoProfile", "-Command"]
            else:
                return comspec, ["/c"]
        else:
            # Linux/macOS使用bash
            return "/bin/bash", ["-c"]

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行shell命令"""
        try:
            command = arguments.get("command", "").strip()
            if not command:
                return ToolResult(
                    success=False,
                    content="Command is required",
                    error="missing_command",
                )

            description = arguments.get("description", "")
            directory = arguments.get("directory")

            # 检测后台进程
            cleaned_command, is_background = self._detect_background_processes(command)

            # 确定执行目录
            if directory:
                exec_dir = Path(self._workspace_path) / directory
            else:
                exec_dir = Path(self._workspace_path)

            exec_dir = exec_dir.resolve()

            if not exec_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Directory not found: {exec_dir}",
                    error="directory_not_found",
                    data={
                        "command": command,
                        "directory": str(exec_dir),
                    },
                )

            # 获取shell命令
            shell_executable, shell_args = self._get_shell_command()

            # 设置环境变量（添加 GEMINI_CLI=1 类似的标识）
            env = os.environ.copy()
            env["AGENTSOCIETY_CLI"] = "1"
            
            # 发送进度报告（只显示命令的前50个字符）
            command_preview = cleaned_command[:50] + ("..." if len(cleaned_command) > 50 else "")
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Running: {command_preview}",
            ))

            # 构建完整命令
            if platform.system() == "Windows":
                # Windows PowerShell需要特殊处理
                full_command = shell_args + [cleaned_command]
            else:
                # Linux/macOS bash
                full_command = shell_args + [cleaned_command]

            logger.info(f"Executing shell command: {command} in directory: {exec_dir}")

            # 执行命令
            try:
                if is_background:
                    # 后台执行 - 将输出重定向到DEVNULL避免缓冲区阻塞
                    process = await asyncio.create_subprocess_exec(
                        shell_executable,
                        *full_command,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        stdin=asyncio.subprocess.DEVNULL,
                        cwd=str(exec_dir),
                        env=env,
                        preexec_fn=(
                            os.setsid if platform.system() != "Windows" else None
                        ),
                    )

                    # 后台进程立即返回
                    background_pids = [process.pid]

                    # 后台进程的输出被重定向到DEVNULL
                    stdout = ""
                    stderr = ""

                    return ToolResult(
                        success=True,
                        content=(
                            f"Command started in background (PID: {process.pid})\n\n"
                            f"Command: {command}\n"
                            f"Directory: {exec_dir}\n"
                            f"Background PIDs: {background_pids}"
                        ),
                        data={
                            "command": command,
                            "directory": str(exec_dir),
                            "stdout": stdout,
                            "stderr": stderr,
                            "exit_code": None,
                            "signal": None,
                            "background_pids": background_pids,
                            "is_background": True,
                        },
                    )
                else:
                    # 前台执行
                    process = await asyncio.create_subprocess_exec(
                        shell_executable,
                        *full_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdin=asyncio.subprocess.DEVNULL,
                        cwd=str(exec_dir),
                        env=env,
                    )

                    stdout_data, stderr_data = await process.communicate()

                    stdout = (
                        stdout_data.decode("utf-8", errors="replace")
                        if stdout_data
                        else ""
                    )
                    stderr = (
                        stderr_data.decode("utf-8", errors="replace")
                        if stderr_data
                        else ""
                    )
                    exit_code = process.returncode

                    # 构建结果内容
                    content_parts = []
                    if description:
                        content_parts.append(f"Description: {description}\n")
                    content_parts.append(f"Command: {command}")
                    content_parts.append(f"Directory: {exec_dir}")
                    content_parts.append(f"Exit Code: {exit_code}")

                    if stdout:
                        content_parts.append(f"\n**Stdout:**\n{stdout}")
                    if stderr:
                        content_parts.append(f"\n**Stderr:**\n{stderr}")

                    content = "\n".join(content_parts)

                    return ToolResult(
                        success=exit_code == 0,
                        content=content,
                        error=(
                            None
                            if exit_code == 0
                            else f"Command exited with code {exit_code}"
                        ),
                        data={
                            "command": command,
                            "directory": str(exec_dir),
                            "stdout": stdout,
                            "stderr": stderr,
                            "exit_code": exit_code,
                            "signal": None,
                            "background_pids": [],
                            "is_background": False,
                        },
                    )

            except asyncio.TimeoutError:
                return ToolResult(
                    success=False,
                    content=f"Command execution timed out: {command}",
                    error="timeout",
                    data={
                        "command": command,
                        "directory": str(exec_dir),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to execute shell command: {e}", exc_info=True)
                return ToolResult(
                    success=False,
                    content=f"Failed to execute command: {str(e)}",
                    error=str(e),
                    data={
                        "command": command,
                        "directory": str(exec_dir),
                    },
                )

        except Exception as e:
            logger.error(f"Run shell command tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to run shell command: {str(e)}",
                error=str(e),
            )


if __name__ == "__main__":
    """调试入口"""
    import asyncio
    import sys

    async def test_run_shell_command():
        """测试运行shell命令工具"""

        # 设置工作区路径（从命令行参数或使用默认值）
        if len(sys.argv) > 1:
            workspace_path = sys.argv[1]
        else:
            workspace_path = "."

        tool = RunShellCommandTool(
            workspace_path=workspace_path, progress_callback=None, tool_id=""
        )

        # 测试参数
        arguments = {
            "command": "ls -la",
            "description": "List files in current directory",
            "directory": None,
        }

        print(f"Testing RunShellCommandTool with workspace: {workspace_path}")
        print("-" * 60)

        result = await tool.execute(arguments)

        print(f"Success: {result.success}")
        print(f"Content:\n{result.content}")
        print("-" * 60)
        if result.data:
            print(f"Exit Code: {result.data.get('exit_code')}")
            print(f"Stdout: {result.data.get('stdout', '')[:200]}...")
            print(f"Stderr: {result.data.get('stderr', '')[:200]}...")

    # 运行测试
    asyncio.run(test_run_shell_command())
