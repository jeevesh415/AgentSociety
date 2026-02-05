"""数据分析工具

提供实验数据分析功能，支持自主分析实验数据并生成可视化。
"""

from __future__ import annotations

from typing import Dict, Any

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger
from agentsociety2.backend.analysis.service import AnalysisService
from agentsociety2.backend.analysis.models import AnalysisConfig

logger = get_logger()


class DataAnalysisTool(BaseTool):
    """数据分析工具

    支持对实验数据进行自主分析，包括：
    - 分析实验数据库中的数据
    - 生成可视化图表
    - 提供分析结果和建议
    """

    def get_name(self) -> str:
        return "data_analysis"

    def get_description(self) -> str:
        return (
            "Analyze experiment data and generate visualizations autonomously.\n\n"
            "This tool performs comprehensive data analysis on experiment results:\n"
            "- Examines available data sources (database tables, JSON/YAML/CSV files, images)\n"
            "- Decides analysis strategy autonomously using LLM\n"
            "- Generates visualizations based on analysis needs\n"
            "- Provides insights and recommendations\n\n"
            "The analysis is fully autonomous - the LLM decides what to analyze and how to present results."
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
                "custom_instructions": {
                    "type": "string",
                    "description": "Optional custom instructions for the analysis (e.g., focus on specific aspects, use particular methods)",
                },
            },
            "required": ["hypothesis_id", "experiment_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行数据分析"""
        try:
            hypothesis_id = arguments.get("hypothesis_id")
            experiment_id = arguments.get("experiment_id")
            custom_instructions = arguments.get("custom_instructions")

            if not hypothesis_id or not experiment_id:
                return ToolResult(
                    success=False,
                    content="hypothesis_id and experiment_id are required",
                    error="Missing required parameters",
                )

            # 发送进度更新
            await self._send_progress(
                ToolEvent(
                    tool_id=self._current_tool_id,
                    event_type="progress",
                    content=f"Analyzing experiment {experiment_id} in hypothesis {hypothesis_id}...",
                )
            )

            # 初始化分析服务并执行
            analysis_service = AnalysisService(
                AnalysisConfig(workspace_path=self._workspace_path)
            )
            result = await analysis_service.analyze(
                hypothesis_id=hypothesis_id,
                experiment_id=experiment_id,
                custom_instructions=custom_instructions,
            )

            if result.get("success"):
                output_dir = result.get("output_directory", "")
                generated_files = result.get("generated_files", {})
                analysis_result = result.get("analysis_result")

                content_parts = [
                    f"Data analysis completed successfully for experiment {experiment_id} in hypothesis {hypothesis_id}.",
                ]

                if generated_files:
                    content_parts.append("\nGenerated files:")
                    content_parts.extend(
                        [f"- {ft}: {fp}" for ft, fp in generated_files.items()]
                    )

                if output_dir:
                    content_parts.append(f"\nOutput directory: {output_dir}")

                insights = None
                if analysis_result is not None:
                    # `analysis_result` 可能是 Pydantic 模型，也可能是 dict（兼容两种情况）
                    if hasattr(analysis_result, "insights"):
                        insights = getattr(analysis_result, "insights", None)
                    elif isinstance(analysis_result, dict):
                        insights = analysis_result.get("insights")

                if insights:
                    content_parts.append("\nKey Insights:")
                    content_parts.extend(
                        [f"{i}. {ins}" for i, ins in enumerate(list(insights)[:5], 1)]
                    )

                return ToolResult(
                    success=True,
                    content="\n".join(content_parts),
                    data={
                        "output_directory": output_dir,
                        "generated_files": generated_files,
                        "analysis_result": analysis_result,
                    },
                )
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Data analysis failed: {error_msg}")
                return ToolResult(
                    success=False,
                    content=f"Data analysis failed: {error_msg}",
                    error=error_msg,
                )

        except Exception as e:
            logger.error(f"Data analysis tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Data analysis tool execution failed: {str(e)}",
                error=str(e),
            )
