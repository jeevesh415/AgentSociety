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
            "You MUST pass hypothesis_id and experiment_id in every call. Infer them from the current "
            "conversation context (e.g. 'hypothesis 1 experiment 1' -> hypothesis_id='1', experiment_id='1'); "
            "if the user did not specify, use the default experiment (e.g. '1', '1'). Do not ask the user "
            "for these IDs in chat—always pass them in the tool call.\n\n"
            "This tool: examines data under workspace/hypothesis_<id>/experiment_<id>/ (run/, results/), "
            "decides analysis strategy via LLM, generates visualizations, and returns insights."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_id": {
                    "type": "string",
                    "description": "Required. Hypothesis ID, e.g. '1', '2'. Must be passed in this call.",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "Required. Experiment ID within the hypothesis, e.g. '1', '2'. Must be passed in this call.",
                },
                "custom_instructions": {
                    "type": "string",
                    "description": "Optional. Custom instructions for the analysis (e.g. focus on specific aspects).",
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
                    content=(
                        "Missing required parameters: hypothesis_id and experiment_id. "
                        "You must pass both in this tool call (e.g. hypothesis_id='1', experiment_id='1'). "
                        "Infer from conversation context or use default '1','1'. Do not ask the user for IDs."
                    ),
                    error="Missing required parameters",
                )

            async def on_progress(msg: str) -> None:
                await self._send_progress(
                    ToolEvent(
                        tool_id=self._current_tool_id,
                        tool_name=self.get_name(),
                        status="progress",
                        content=msg,
                    )
                )

            analysis_service = AnalysisService(
                AnalysisConfig(workspace_path=self._workspace_path)
            )
            result = await analysis_service.analyze(
                hypothesis_id=hypothesis_id,
                experiment_id=experiment_id,
                custom_instructions=custom_instructions,
                on_progress=on_progress,
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
                    if hasattr(analysis_result, "insights"):
                        insights = getattr(analysis_result, "insights", None)
                    elif isinstance(analysis_result, dict):
                        insights = analysis_result.get("insights")

                if insights:
                    content_parts.append("\nKey Insights:")
                    content_parts.extend(
                        [f"{i}. {ins}" for i, ins in enumerate(list(insights)[:5], 1)]
                    )

                ar_dict = None
                if analysis_result is not None:
                    ar_dict = (
                        analysis_result.model_dump(mode="json")
                        if hasattr(analysis_result, "model_dump")
                        else analysis_result
                    )
                    if not isinstance(ar_dict, dict):
                        ar_dict = None
                return ToolResult(
                    success=True,
                    content="\n".join(content_parts),
                    data={
                        "output_directory": output_dir,
                        "generated_files": generated_files,
                        "analysis_result": ar_dict,
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
            return ToolResult(success=False, content=str(e), error=str(e))
