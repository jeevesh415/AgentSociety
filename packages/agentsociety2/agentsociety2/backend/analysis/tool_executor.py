"""
tool_executor.py

工具执行器，支持内置工具和代码执行器。

说明:
    本模块实现了工具执行器，支持内置工具和代码执行器。
    内置工具来自工具注册表。
    代码执行器通过多轮对话让LLM判断执行结果。
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model
from agentsociety2.backend.tools.file_system import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    SearchFileContentTool,
    ReplaceTool,
)
from agentsociety2.backend.tools.run_shell_command import RunShellCommandTool
from agentsociety2.backend.tools.write_todo import WriteTodoTool
from agentsociety2.backend.tools.literature_search import LiteratureSearchTool
from agentsociety2.backend.tools.load_literature import LoadLiteratureTool
from agentsociety2.code_executor.code_generator import CodeGenerator
from agentsociety2.code_executor.dependency_detector import DependencyDetector
from agentsociety2.code_executor.local_executor import LocalCodeExecutor
from pydantic import BaseModel
from litellm import AllMessageValues

from .utils import parse_llm_json_to_model


class ExecutionResult(BaseModel):
    """代码执行结果判断"""

    success: bool
    reason: str
    should_retry: bool = False
    retry_instruction: str = ""


def extract_database_schema(db_path: Path) -> Dict[str, Any]:
    """
    提取数据库schema（表结构）为字典格式。
    
    Args:
        db_path: SQLite数据库文件路径
        
    Returns:
        字典，键为表名，值为列信息列表。每个列信息包含：name, type, notnull, pk
    """
    if not db_path or not db_path.exists():
        return {}
    
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    
    schema = {}
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        schema[table_name] = [
            {"name": col[1], "type": col[2], "notnull": bool(col[3]), "pk": bool(col[5])}
            for col in columns
        ]
    
    conn.close()
    return schema


def format_database_schema_markdown(schema: Dict[str, Any], include_row_counts: bool = False, db_path: Optional[Path] = None) -> str:
    """
    将数据库schema格式化为markdown字符串。
    
    Args:
        schema: 从 extract_database_schema 返回的字典
        include_row_counts: 是否包含行数统计
        db_path: 数据库路径
        
    Returns:
        格式化的markdown字符串
    """
    if not schema:
        return "Schema not available"
    
    lines = []
    for table_name, columns in schema.items():
        lines.append(f"### Table: `{table_name}`")
        lines.append(f"Columns: {', '.join([col['name'] for col in columns])}")
        for col in columns:
            pk_marker = " (PRIMARY KEY)" if col.get("pk") else ""
            lines.append(f"  - {col['name']} ({col['type']}){pk_marker}")
        lines.append("")
    
    if include_row_counts and db_path:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        lines.append("### Table Row Counts")
        for table_name in schema.keys():
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            lines.append(f"- `{table_name}`: {count} rows")
        conn.close()
    
    return "\n".join(lines)


def collect_experiment_files(db_path: Path) -> list[str]:
    """
    收集需要提供给本地执行器的实验文件。

    Args:
        db_path: sqlite.db 的路径（上层如果实验/假设路径不同，传入对应的 db_path 即可）

    Returns:
        提供给本地执行器的文件路径列表
    """
    if not db_path:
        return []

    files: list[str] = [str(db_path)]
    if not db_path.exists():
        return files

    run_dir = db_path.parent

    # - run/ 下的同级文件（例如日志、配置、导出结果等）
    if run_dir.exists():
        for p in run_dir.glob("*"):
            if p.is_file() and p != db_path:
                files.append(str(p))

        # - run/artifacts/ 下的所有文件
        run_artifacts = run_dir / "artifacts"
        if run_artifacts.exists():
            for p in run_artifacts.rglob("*"):
                if p.is_file():
                    files.append(str(p))

    return files


class ToolExecutor:
    """
    工具执行器，支持以下功能：
    1. 内置工具（builtin）：文件系统工具等，来自 tools/ 文件夹
    2. 代码执行器（code_executor）：执行 Python 代码
    """

    def __init__(self, workspace_path: Path, output_dir: Path, tool_registry: Optional[Any] = None):
        self.workspace_path = workspace_path
        self.output_dir = output_dir
        self.logger = get_logger()

        # Tool registry (passed in to avoid circular imports)
        self._tool_registry = tool_registry

        # Built-in tools registry
        self._builtin_tools: Dict[str, Any] = {}

        # LLM router for code execution result judgment
        self._router, self._model_name = get_llm_router_and_model("coder")

        # Initialize built-in tools (only data analysis related)
        self._initialize_builtin_tools()

    def _initialize_builtin_tools(self):
        """初始化数据分析需要的内置工具。"""
        tool_classes = [
            ListDirectoryTool,
            ReadFileTool,
            WriteFileTool,
            GlobTool,
            SearchFileContentTool,
            ReplaceTool,
            RunShellCommandTool,
            WriteTodoTool,
            LiteratureSearchTool,
            LoadLiteratureTool,
        ]
        
        for tool_class in tool_classes:
            default_instance = tool_class(
                workspace_path="",
                progress_callback=None,
                tool_id="",
            )
            tool_name = default_instance.name
            self._builtin_tools[tool_name] = {
                "description": default_instance.description,
                "type": "builtin",
            }

        self.logger.info(
            f"Initialized {len(self._builtin_tools)} built-in tools for data analysis"
        )

    def discover_tools(self) -> Dict[str, Dict[str, Any]]:
        """返回所有可用的内置工具。"""
        return {
            name: {
                "description": info.get("description", ""),
                "type": "builtin",
                "usage": f"Use tool name '{name}' in your analysis plan",
            }
            for name, info in self._builtin_tools.items()
        }

    async def execute_tool(
        self,
        tool_name: str,
        tool_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行一个工具，并传递给定的参数。

        Args:
            tool_name: 工具名称
            tool_type: 工具类型 ("builtin", "code_executor")
            parameters: 传递给工具的参数

        Returns:
            执行结果字典
        """
        if tool_type == "builtin":
            return await self._execute_builtin_tool(tool_name, parameters)
        elif tool_type == "code_executor":
            return await self._execute_code(parameters)
        else:
            return {
                "success": False,
                "error": f"Unknown tool type: {tool_type}",
            }

    async def _execute_builtin_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行一个内置工具。"""
        if tool_name not in self._builtin_tools:
            return {
                "success": False,
                "error": f"Built-in tool '{tool_name}' not found",
            }

        # Use provided registry or import lazily as fallback
        if self._tool_registry is None:
            from agentsociety2.backend.tools.registry import ToolRegistry
            registry = ToolRegistry()
        else:
            registry = self._tool_registry

        tool = registry.get_tool(
            name=tool_name,
            workspace_path=str(self.workspace_path),
            progress_callback=None,
            tool_id=f"data_analysis_{tool_name}",
        )

        if tool is None:
            return {
                "success": False,
                "error": f"Failed to create tool instance for '{tool_name}'",
            }

        if tool_name == "write_todos":
            result = await tool.execute({"todos": parameters.get("todos", [])})
        else:
            result = await tool.execute(**parameters)
        return {
            "success": True,
            "tool_name": tool_name,
            "result": result,
        }

    def _discover_database_schema(self, db_path: str) -> Optional[str]:
        """
        发现数据库模式并返回格式化的模式信息。

        Args:
            db_path: SQLite 数据库文件路径

        Returns:
            格式化的 markdown 字符串，包含模式信息，如果发现失败则返回 None
        """
        db_path_obj = Path(db_path)
        schema = extract_database_schema(db_path_obj)
        if not schema:
            return None
        
        return format_database_schema_markdown(schema, include_row_counts=True, db_path=db_path_obj)

    async def _execute_code(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行Python代码。

        Args:
            parameters: 参数字典，包含:
                - code_description: 代码描述
                - db_path: 数据库文件路径
                - extra_files: 额外的文件路径列表
                - timeout: 执行超时时间，秒 (可选，默认600)

        Returns:
            执行结果字典
        """
        code_generator = CodeGenerator()
        dependency_detector = DependencyDetector()

        code_description = (
            parameters.get("code_description") or parameters.get("description") or ""
        )
        if not code_description:
            return {
                "success": False,
                "error": "No code description provided",
            }

        db_path = parameters.get("db_path")
        extra_files = parameters.get("extra_files", [])
        timeout = parameters.get("timeout", 600)

        work_dir = Path(tempfile.mkdtemp(prefix="analysis_", dir=self.output_dir))
        local_executor = LocalCodeExecutor(work_dir=work_dir)

        files_before_execution = {p for p in work_dir.rglob("*") if p.is_file()}

        schema_info = ""
        if db_path:
            discovered_schema = self._discover_database_schema(db_path)
            if discovered_schema:
                schema_info = f"""
## Database Schema

{discovered_schema}

**IMPORTANT**: 
- The schema above shows the actual database structure discovered from the file.
- Your code MUST first read and verify the database structure before processing data.
- Do NOT hardcode table or column names - always query the schema first.
- Use the discovered schema as reference, but verify it programmatically in your code.
"""
                self.logger.info(
                    "Database schema discovered and will be included in code generation prompt"
                )

        db_filename = None
        if db_path:
            src_db = Path(db_path)
            if src_db.exists() and src_db.is_file():
                db_filename = src_db.name
                shutil.copy2(src_db, work_dir / db_filename)

        for f_path in extra_files:
            src = Path(f_path)
            if not src.exists() or not src.is_file():
                continue
            if db_path and str(Path(db_path)) == str(src):
                continue
            shutil.copy2(src, work_dir / src.name)

        # Build file path info for prompt (always include if db_path exists)
        file_path_info = ""
        if db_path:
            db_filename = db_filename or Path(db_path).name

            other_files_list = [
                f"- {Path(f_path).name}"
                for f_path in extra_files
                if Path(f_path).name != db_filename
            ]
            other_files_str = (
                "\n".join(other_files_list) if other_files_list else "None"
            )

            file_path_info = f"""
## Available Files

- Database: `{db_filename}` (in current working directory)
- Output directory: `{self.output_dir}` (save all output files here)
- Other files: {other_files_str if other_files_str != "None" else "None"}

"""

        full_description = f"""{code_description}
{schema_info}
{file_path_info}
## Important Guidelines

- **No Command-Line Arguments**: Do NOT use argparse, sys.argv, or any command-line argument parsing. All file paths are provided in the context above and files are already in the current working directory.
- **File Reading**: ALWAYS read and examine file contents FIRST before processing. For databases, query the schema programmatically. For other files, read and inspect their structure and content first. Do NOT hardcode assumptions about file structure.
- **Database Schema**: ALWAYS read and verify the database structure FIRST before processing data. Query the schema programmatically, do NOT hardcode table or column names.
- **Error Handling**: Use try-except blocks for file/database operations. If the core task cannot be completed, exit with `sys.exit(1)`.
- **Type Safety**: SQLite often stores mixed types. Use `pd.to_numeric(..., errors='coerce')` for numeric conversion.
- **Output Files**: Save all output files to the output directory specified above (use relative path or Path object)."""

        MAX_RETRIES = 5

        conversation_messages: list[AllMessageValues] = []
        generated_code = None
        exec_result = None

        initial_prompt = code_generator._build_prompt(full_description)
        conversation_messages.append({"role": "user", "content": initial_prompt})

        try:
            for current_try in range(MAX_RETRIES):
                response = await code_generator._router.acompletion(
                    model=code_generator._model_name,
                    messages=conversation_messages,
                )

                generated_text = response.choices[0].message.content  # type: ignore
                if not generated_text:
                    if current_try < MAX_RETRIES - 1:
                        conversation_messages.append(
                            {
                                "role": "user",
                                "content": "Code generator returned empty content. Please generate valid Python code.",
                            }
                        )
                    continue

                generated_code = code_generator._extract_code(generated_text)
                if not generated_code or not generated_code.strip():
                    if current_try < MAX_RETRIES - 1:
                        conversation_messages.append(
                            {
                                "role": "user",
                                "content": "Code generator returned empty code. Please generate valid Python code.",
                            }
                        )
                    continue

                conversation_messages.append(
                    {"role": "assistant", "content": generated_code}
                )

                detected_dependencies = dependency_detector.detect(generated_code)
                exec_result = await local_executor.execute(
                    generated_code,
                    dependencies=detected_dependencies,
                    timeout=timeout,
                )

                judgment = await self._judge_execution_result(
                    generated_code, exec_result, work_dir, files_before_execution
                )

                if judgment.success:
                    break

                if judgment.should_retry and current_try < MAX_RETRIES - 1:
                    self.logger.info(
                        f"Execution failed, will retry. Reason: {judgment.reason}"
                    )
                    execution_output = f"""## Code Execution Result (Attempt {current_try + 1})

**Return Code**: {exec_result.return_code if exec_result else 'N/A'}

**STDOUT**:
```
{exec_result.stdout if exec_result else 'No output'}
```

**STDERR**:
```
{exec_result.stderr if exec_result else 'No error'}
```

**Generated Code**:
```python
{generated_code}
```

**Analysis**: {judgment.reason}

**What to fix**: {judgment.retry_instruction}

Please generate corrected code that addresses the issues above."""
                    conversation_messages.append(
                        {"role": "user", "content": execution_output}
                    )
                else:
                    break

            if not exec_result:
                self.logger.warning("No execution result after all attempts")
                return {
                    "success": False,
                    "error": "No execution result after all attempts",
                    "code_generated": generated_code or "",
                }

            final_judgment = await self._judge_execution_result(
                generated_code, exec_result, work_dir, files_before_execution
            )

            if not final_judgment.success:
                self.logger.warning(
                    f"All {MAX_RETRIES} attempts failed. Reason: {final_judgment.reason}"
                )
                return {
                    "success": False,
                    "error": f"Failed after {MAX_RETRIES} attempts. {final_judgment.reason}",
                    "code_generated": generated_code or "",
                }

            artifact_extensions = {
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".pdf",
                ".webp",
                ".csv",
                ".json",
                ".txt",
            }
            files_after_execution = {
                p
                for p in work_dir.rglob("*")
                if p.is_file()
                and p not in files_before_execution
                and p.suffix.lower() in artifact_extensions
            }
            artifacts = [str(p) for p in files_after_execution]

            artifacts.extend(
                str(p)
                for p in self.output_dir.glob("**/*")
                if p.is_file() and p.suffix.lower() in artifact_extensions
            )

            return {
                "success": True,
                "code_generated": generated_code or "",
                "stdout": exec_result.stdout or "",
                "stderr": exec_result.stderr or "",
                "artifacts": artifacts,
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _judge_execution_result(
        self,
        generated_code: str,
        exec_result: Any,
        work_dir: Path,
        files_before_execution: set,
    ) -> ExecutionResult:
        """
        使用LLM判断代码执行结果是否成功。

        Args:
            generated_code: 生成的代码
            exec_result: 执行结果对象
            work_dir: 工作目录
            files_before_execution: 执行前的文件集合

        Returns:
            ExecutionResult 判断结果
        """
        # Collect artifacts
        artifact_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".svg",
            ".pdf",
            ".webp",
            ".csv",
            ".json",
            ".txt",
        }
        files_after = {
            p
            for p in work_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in artifact_extensions
        }
        new_files = files_after - files_before_execution
        output_dir_files = list(self.output_dir.glob("**/*"))

        def _fallback_check() -> ExecutionResult:
            if (
                exec_result
                and exec_result.return_code == 0
                and (exec_result.stdout.strip() or new_files or output_dir_files)
            ):
                return ExecutionResult(
                    success=True, reason="Execution completed with output"
                )
            return ExecutionResult(
                success=False,
                reason="LLM judgment failed, execution may have failed",
                should_retry=True,
                retry_instruction="Check the execution output and fix any errors",
            )

        execution_summary = f"""## Code Execution Result

**Return Code**: {exec_result.return_code if exec_result else 'N/A'}

**STDOUT**:
```
{exec_result.stdout if exec_result else 'No output'}
```

**STDERR**:
```
{exec_result.stderr if exec_result else 'No error'}
```

**New Files Created in Work Directory**: {len(new_files)} files
**Output Directory Files**: {len(output_dir_files)} files

**Generated Code**:
```python
{generated_code[:1000]}...
```

You should analyze the execution result and determine:
1. Did the code execute successfully?
2. Did it produce the expected output or files?
3. Are there any errors in stderr that indicate failure?
4. Is the task completed successfully?

Respond in JSON format:
```json
{{
    "success": true/false,
    "reason": "brief explanation",
    "should_retry": true/false,
    "retry_instruction": "what to fix if should_retry is true"
}}
```"""

        messages: list[AllMessageValues] = [
            {"role": "user", "content": execution_summary}
        ]

        response = await self._router.acompletion(
            model=self._model_name,
            messages=messages,
        )

        content = response.choices[0].message.content  # type: ignore
        if not content:
            return _fallback_check()

        return parse_llm_json_to_model(content, ExecutionResult)
