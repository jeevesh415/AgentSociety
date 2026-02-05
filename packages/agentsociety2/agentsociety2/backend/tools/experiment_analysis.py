"""实验分析工具

提供实验结果分析功能，支持：
- 查询sqlite.db中的实验数据
- 生成分析代码
- 在Docker沙箱中执行分析代码
- 保存分析结论
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.code_executor.code_generator import CodeGenerator
from agentsociety2.code_executor.docker_runner import DockerRunner
from agentsociety2.code_executor.dependency_detector import DependencyDetector
from agentsociety2.code_executor.runtime_config import DockerRuntimeConfig
from agentsociety2.config import get_llm_router_and_model
from agentsociety2.logger import get_logger

logger = get_logger()


class ExperimentAnalysisTool(BaseTool):
    """实验分析工具

    支持以下操作：
    - query_data: 查询实验数据库中的数据
    - generate_analysis: 使用LLM生成分析代码
    - execute_analysis: 在Docker沙箱中执行分析代码
    - save_conclusion: 保存分析结论到Markdown文件
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
        # 延迟初始化LLM router，只在需要时获取
        self._router = None
        self._model_name = None

    def _get_llm_router(self):
        """延迟获取LLM router"""
        if self._router is None:
            self._router, self._model_name = get_llm_router_and_model("coder")
        return self._router, self._model_name

    def get_name(self) -> str:
        return "experiment_analysis"

    def get_description(self) -> str:
        return (
            "Analyze experiment results by querying data, generating analysis code, and saving conclusions.\n\n"
            "Actions:\n"
            "- query_data: Query the experiment SQLite database to retrieve agent states, step executions, or raw data.\n"
            "- generate_analysis: Generate Python analysis code based on the experiment data and analysis goals.\n"
            "- execute_analysis: Execute Python analysis code in a Docker sandbox with data visualization support.\n"
            "- save_conclusion: Save the analysis conclusion to a Markdown file.\n\n"
            "Typical workflow:\n"
            "1. Use 'query_data' to understand the data structure and content\n"
            "2. Use 'generate_analysis' to create analysis code based on your findings\n"
            "3. Use 'execute_analysis' to run the code and generate visualizations\n"
            "4. Use 'save_conclusion' to document your findings\n\n"
            "Output files are saved to:\n"
            "- analysis/codes/: Generated analysis code\n"
            "- analysis/figures/: Generated plots and visualizations\n"
            "- analysis/CONCLUSION.md: Final analysis conclusion"
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["query_data", "generate_analysis", "execute_analysis", "save_conclusion"],
                    "description": "Action to perform",
                },
                "hypothesis_id": {
                    "type": "string",
                    "description": "ID of the hypothesis",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "ID of the experiment within the hypothesis",
                },
                "query": {
                    "type": "string",
                    "description": "SQL query to execute (for 'query_data' action)",
                },
                "analysis_goal": {
                    "type": "string",
                    "description": "Description of the analysis goal (for 'generate_analysis' action)",
                },
                "code": {
                    "type": "string",
                    "description": "Python code to execute (for 'execute_analysis' action)",
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content to save (for 'save_conclusion' action)",
                },
                "table": {
                    "type": "string",
                    "enum": ["experiment_state", "step_executions"],
                    "description": "Table to query (optional, for 'query_data' action with predefined queries)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return (for 'query_data' action)",
                    "default": 100,
                },
            },
            "required": ["action", "hypothesis_id", "experiment_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行实验分析操作"""
        action = arguments.get("action")
        hypothesis_id = arguments.get("hypothesis_id")
        experiment_id = arguments.get("experiment_id")

        if not hypothesis_id or not experiment_id:
            return ToolResult(
                success=False,
                content="hypothesis_id and experiment_id are required",
                error="Missing required parameters",
            )

        workspace_path = Path(self._workspace_path)
        hyp_dir = workspace_path / f"hypothesis_{hypothesis_id}"
        exp_dir = hyp_dir / f"experiment_{experiment_id}"

        if not exp_dir.exists():
            return ToolResult(
                success=False,
                content=f"Experiment directory not found: {exp_dir}",
                error="Experiment not found",
            )

        if action == "query_data":
            return await self._query_data(exp_dir, arguments)
        elif action == "generate_analysis":
            return await self._generate_analysis(exp_dir, arguments)
        elif action == "execute_analysis":
            return await self._execute_analysis(exp_dir, arguments)
        elif action == "save_conclusion":
            return await self._save_conclusion(exp_dir, arguments)
        else:
            return ToolResult(
                success=False,
                content=f"Unknown action: {action}",
                error="Invalid action",
            )

    async def _query_data(
        self,
        exp_dir: Path,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """查询实验数据"""
        db_file = exp_dir / "run" / "sqlite.db"

        if not db_file.exists():
            return ToolResult(
                success=False,
                content=(
                    f"Database not found: {db_file}\n"
                    "The experiment may not have been run yet."
                ),
                error="Database not found",
            )

        query = arguments.get("query")
        table = arguments.get("table")
        limit = arguments.get("limit", 100)

        try:
            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 如果没有提供query，根据table生成默认查询
            if not query:
                if table == "experiment_state":
                    query = f"SELECT * FROM experiment_state ORDER BY id DESC LIMIT {limit}"
                elif table == "step_executions":
                    query = f"SELECT * FROM step_executions ORDER BY step_index ASC LIMIT {limit}"
                else:
                    # 返回表结构信息
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]

                    table_info = {}
                    for tbl in tables:
                        cursor.execute(f"PRAGMA table_info({tbl})")
                        columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
                        cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
                        count = cursor.fetchone()[0]
                        table_info[tbl] = {"columns": columns, "row_count": count}

                    conn.close()

                    return ToolResult(
                        success=True,
                        content=(
                            f"Database schema:\n\n"
                            + "\n".join([
                                f"Table: {tbl}\n"
                                f"  Columns: {', '.join([c['name'] + ':' + c['type'] for c in info['columns']])}\n"
                                f"  Rows: {info['row_count']}"
                                for tbl, info in table_info.items()
                            ])
                        ),
                        data={"tables": table_info},
                    )

            # 执行查询
            await self._send_progress(
                ToolEvent(
                    tool_name=self.name,
                    tool_id=self._current_tool_id,
                    status="progress",
                    content=f"Executing query: {query[:100]}...",
                )
            )

            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            # 转换为字典列表
            results = [dict(row) for row in rows]

            # 如果数据太大，只返回摘要
            if len(results) > 10:
                content = (
                    f"Query returned {len(results)} rows.\n\n"
                    f"First 5 rows:\n"
                    f"{json.dumps(results[:5], ensure_ascii=False, indent=2, default=str)}\n\n"
                    f"Last 5 rows:\n"
                    f"{json.dumps(results[-5:], ensure_ascii=False, indent=2, default=str)}"
                )
            else:
                content = (
                    f"Query returned {len(results)} rows:\n\n"
                    f"{json.dumps(results, ensure_ascii=False, indent=2, default=str)}"
                )

            return ToolResult(
                success=True,
                content=content,
                data={"rows": results, "count": len(results)},
            )

        except sqlite3.Error as e:
            return ToolResult(
                success=False,
                content=f"SQL error: {str(e)}",
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Query failed: {str(e)}",
                error=str(e),
            )

    async def _generate_analysis(
        self,
        exp_dir: Path,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """生成分析代码"""
        analysis_goal = arguments.get("analysis_goal")

        if not analysis_goal:
            return ToolResult(
                success=False,
                content="analysis_goal is required for 'generate_analysis' action",
                error="Missing analysis_goal",
            )

        db_file = exp_dir / "run" / "sqlite.db"

        if not db_file.exists():
            return ToolResult(
                success=False,
                content="Database not found. Run the experiment first.",
                error="Database not found",
            )

        # 获取数据库结构
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema_info = []
            sample_data = {}

            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [(row[1], row[2]) for row in cursor.fetchall()]
                schema_info.append(f"Table {table}: {', '.join([f'{c[0]}:{c[1]}' for c in columns])}")

                # 获取样本数据
                cursor.execute(f"SELECT * FROM {table} LIMIT 2")
                rows = cursor.fetchall()
                if rows:
                    sample_data[table] = [dict(zip([c[0] for c in columns], row)) for row in rows]

            conn.close()
        except Exception as e:
            return ToolResult(
                success=False,
                content=f"Failed to read database schema: {str(e)}",
                error=str(e),
            )

        # 构建提示词
        prompt = self._build_analysis_prompt(
            analysis_goal=analysis_goal,
            schema_info=schema_info,
            sample_data=sample_data,
            db_path=str(db_file),
            output_dir=str(exp_dir / "analysis" / "figures"),
        )

        await self._send_progress(
            ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content="Generating analysis code with LLM...",
            )
        )

        try:
            code_gen = CodeGenerator()
            generated_code, success = await code_gen.generate_with_feedback(
                initial_description=prompt,
                input_files=[str(db_file)],
                max_retries=0,
            )

            if not success or not generated_code:
                return ToolResult(
                    success=False,
                    content="Failed to generate analysis code",
                    error="Code generation failed",
                )

            # 保存生成的代码
            analysis_dir = exp_dir / "analysis"
            codes_dir = analysis_dir / "codes"
            codes_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            code_file = codes_dir / f"analysis_{timestamp}.py"
            code_file.write_text(generated_code, encoding="utf-8")

            return ToolResult(
                success=True,
                content=(
                    f"Analysis code generated and saved to: {code_file}\n\n"
                    f"```python\n{generated_code[:2000]}{'...' if len(generated_code) > 2000 else ''}\n```\n\n"
                    f"To execute this code, use 'execute_analysis' action with the code."
                ),
                data={
                    "code": generated_code,
                    "code_file": str(code_file),
                },
            )

        except Exception as e:
            logger.error(f"Code generation failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to generate code: {str(e)}",
                error=str(e),
            )

    async def _execute_analysis(
        self,
        exp_dir: Path,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """执行分析代码"""
        code = arguments.get("code")

        if not code:
            return ToolResult(
                success=False,
                content="code is required for 'execute_analysis' action",
                error="Missing code",
            )

        db_file = exp_dir / "run" / "sqlite.db"

        if not db_file.exists():
            return ToolResult(
                success=False,
                content="Database not found. Run the experiment first.",
                error="Database not found",
            )

        # 创建输出目录
        analysis_dir = exp_dir / "analysis"
        figures_dir = analysis_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        await self._send_progress(
            ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content="Executing analysis code in Docker sandbox...",
            )
        )

        try:
            # 检测依赖
            detector = DependencyDetector()
            dependencies = detector.detect(code)
            # 添加常用分析库
            dependencies.update({"pandas", "matplotlib", "seaborn", "numpy"})
            dependencies = list(dependencies)

            # 配置Docker运行器
            config = DockerRuntimeConfig()
            runner = DockerRunner(
                config=config,
                work_dir=analysis_dir / "temp",
                artifacts_dir=figures_dir,
            )

            # 执行代码
            result = await runner.execute(
                code=code,
                dependencies=dependencies,
                timeout=300,
                extra_files=[str(db_file)],
            )

            if result.success:
                # 检查生成的图表文件
                generated_files = list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.jpg"))

                content = (
                    f"Analysis code executed successfully!\n\n"
                    f"stdout:\n```\n{result.stdout[:2000] if result.stdout else '(empty)'}\n```\n\n"
                )

                if generated_files:
                    content += f"Generated {len(generated_files)} figure(s):\n"
                    for f in generated_files:
                        content += f"- {f.name}\n"
                else:
                    content += "No figures were generated.\n"

                return ToolResult(
                    success=True,
                    content=content,
                    data={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "figures": [str(f) for f in generated_files],
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    content=(
                        f"Analysis code execution failed.\n\n"
                        f"stderr:\n```\n{result.stderr[:2000] if result.stderr else '(empty)'}\n```"
                    ),
                    error=result.stderr or "Execution failed",
                )

        except Exception as e:
            logger.error(f"Analysis execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Execution failed: {str(e)}",
                error=str(e),
            )

    async def _save_conclusion(
        self,
        exp_dir: Path,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """保存分析结论"""
        content = arguments.get("content")

        if not content:
            return ToolResult(
                success=False,
                content="content is required for 'save_conclusion' action",
                error="Missing content",
            )

        analysis_dir = exp_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        conclusion_file = analysis_dir / "CONCLUSION.md"

        try:
            # 添加YAML front matter
            timestamp = datetime.now().isoformat()
            full_content = (
                f"---\n"
                f"generated_at: {timestamp}\n"
                f"experiment: {exp_dir.name}\n"
                f"---\n\n"
                f"{content}"
            )

            conclusion_file.write_text(full_content, encoding="utf-8")

            return ToolResult(
                success=True,
                content=f"Conclusion saved to: {conclusion_file}",
                data={"file": str(conclusion_file)},
            )

        except Exception as e:
            logger.error(f"Failed to save conclusion: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to save conclusion: {str(e)}",
                error=str(e),
            )

    def _build_analysis_prompt(
        self,
        analysis_goal: str,
        schema_info: List[str],
        sample_data: Dict[str, Any],
        db_path: str,
        output_dir: str,
    ) -> str:
        """构建分析代码生成提示词"""
        return f"""You are generating Python code to analyze experiment results from an AgentSociety2 simulation.

## Analysis Goal
{analysis_goal}

## Database Information
Database path: {db_path}
(Note: In the Docker container, the database file will be available as 'sqlite.db' in the current directory)

### Schema
{chr(10).join(schema_info)}

### Sample Data
{json.dumps(sample_data, ensure_ascii=False, indent=2, default=str)[:3000]}

## Requirements
1. Connect to the SQLite database and query the necessary data
2. Perform data analysis to achieve the analysis goal
3. Generate visualizations (save to the figures/ directory)
4. Print key findings and statistics to stdout
5. Use pandas for data manipulation
6. Use matplotlib/seaborn for visualization
7. Save all figures as PNG files

## Important Notes
- The database file is available as 'sqlite.db' in the current working directory
- Save figures to the 'figures/' directory (it will be created if it doesn't exist)
- Use plt.savefig() to save figures, don't use plt.show()
- Print a summary of findings at the end
- Handle edge cases (empty data, missing columns, etc.)

## Output Directory for Figures
{output_dir}

Generate the Python code:
"""
