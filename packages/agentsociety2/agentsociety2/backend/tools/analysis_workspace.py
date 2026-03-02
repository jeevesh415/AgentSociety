"""分析相关工具。

对主 Agent 仅暴露：SynthesizeExperimentsTool（综合分析入口）。
单实验入口：data_analysis 模块，工具名 `analyze`。

以下为分析子模块内部能力，不注册给主 Agent：
- ListAnalysisWorkspaceTool、ReadHypothesisFileTool、ReadExperimentFileTool：
  发现工作区结构、读取假设/实验文件，由 Analyzer / Synthesizer 内部使用（或通过 utils/路径约定完成）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger
from agentsociety2.backend.analysis import (
    AnalysisConfig,
    Synthesizer,
    DIR_HYPOTHESIS_PREFIX,
    DIR_EXPERIMENT_PREFIX,
    FILE_HYPOTHESIS_MD,
    FILE_EXPERIMENT_MD,
)

logger = get_logger()


def _workspace_root(workspace_path: str) -> Path:
    return Path(workspace_path).resolve()


def _list_structure(workspace_path: str) -> Dict[str, Any]:
    """先读目录结构再返回，不假设固定命名。"""
    root = _workspace_root(workspace_path)
    if not root.exists() or not root.is_dir():
        return {
            "error": "Workspace path does not exist or is not a directory",
            "hypotheses": [],
        }
    hypotheses: List[Dict[str, Any]] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or not p.name.startswith(DIR_HYPOTHESIS_PREFIX):
            continue
        rest = p.name[len(DIR_HYPOTHESIS_PREFIX) :]
        if not rest:
            continue
        hypothesis_id = rest
        experiments: List[str] = []
        for q in sorted(p.iterdir()):
            if not q.is_dir() or not q.name.startswith(DIR_EXPERIMENT_PREFIX):
                continue
            ex_rest = q.name[len(DIR_EXPERIMENT_PREFIX) :]
            if ex_rest:
                experiments.append(ex_rest)
        hypotheses.append(
            {"hypothesis_id": hypothesis_id, "experiment_ids": sorted(experiments)}
        )
    return {"workspace_path": str(root), "hypotheses": hypotheses}


def _read_hypothesis_file(workspace_path: str, hypothesis_id: str) -> str:
    """先定位文件再读取内容。"""
    root = _workspace_root(workspace_path)
    path = root / f"{DIR_HYPOTHESIS_PREFIX}{hypothesis_id}" / FILE_HYPOTHESIS_MD
    if not path.exists() or not path.is_file():
        return f"(File not found: {path})"
    return path.read_text(encoding="utf-8")


def _read_experiment_file(
    workspace_path: str, hypothesis_id: str, experiment_id: str
) -> str:
    """先定位文件再读取内容。"""
    root = _workspace_root(workspace_path)
    path = (
        root
        / f"{DIR_HYPOTHESIS_PREFIX}{hypothesis_id}"
        / f"{DIR_EXPERIMENT_PREFIX}{experiment_id}"
        / FILE_EXPERIMENT_MD
    )
    if not path.exists() or not path.is_file():
        return f"(File not found: {path})"
    return path.read_text(encoding="utf-8")


class ListAnalysisWorkspaceTool(BaseTool):
    """列出分析工作区中的假设与实验目录结构，供主 Agent 决定先分析谁、是否综合。"""

    def get_name(self) -> str:
        return "list_analysis_workspace"

    def get_description(self) -> str:
        return (
            "List the analysis workspace structure: hypotheses and their experiment IDs. "
            "Use this to see what can be analyzed (single experiment) or synthesized (multiple). "
            "No parameters required; uses current workspace."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            structure = _list_structure(self._workspace_path)
            if structure.get("error"):
                return ToolResult(
                    success=False,
                    content=structure["error"],
                    error=structure["error"],
                )
            lines = [f"Workspace: {structure['workspace_path']}", ""]
            for h in structure.get("hypotheses", []):
                lines.append(
                    f"Hypothesis {h['hypothesis_id']}: experiments {h['experiment_ids']}"
                )
            return ToolResult(
                success=True,
                content="\n".join(lines),
                data=structure,
            )
        except Exception as e:
            logger.exception("list_analysis_workspace failed")
            return ToolResult(success=False, content=str(e), error=str(e))


class ReadHypothesisFileTool(BaseTool):
    """读取指定假设的 HYPOTHESIS.md 内容，先读文件再返回。"""

    def get_name(self) -> str:
        return "read_hypothesis_file"

    def get_description(self) -> str:
        return (
            "Read the content of HYPOTHESIS.md for a given hypothesis_id. "
            "Use after list_analysis_workspace to inspect hypothesis text before analysis or synthesis."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_id": {
                    "type": "string",
                    "description": "Hypothesis ID (e.g. '1', '2').",
                },
            },
            "required": ["hypothesis_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            hypothesis_id = arguments.get("hypothesis_id", "").strip()
            if not hypothesis_id:
                return ToolResult(
                    success=False,
                    content="hypothesis_id is required",
                    error="Missing hypothesis_id",
                )
            content = _read_hypothesis_file(self._workspace_path, hypothesis_id)
            return ToolResult(
                success=True, content=content, data={"hypothesis_id": hypothesis_id}
            )
        except Exception as e:
            logger.exception("read_hypothesis_file failed")
            return ToolResult(success=False, content=str(e), error=str(e))


class ReadExperimentFileTool(BaseTool):
    """读取指定实验的 EXPERIMENT.md 内容，先读文件再返回。"""

    def get_name(self) -> str:
        return "read_experiment_file"

    def get_description(self) -> str:
        return (
            "Read the content of EXPERIMENT.md for a given hypothesis_id and experiment_id. "
            "Use to inspect experiment design before running single-experiment analysis."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_id": {"type": "string", "description": "Hypothesis ID."},
                "experiment_id": {"type": "string", "description": "Experiment ID."},
            },
            "required": ["hypothesis_id", "experiment_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            hypothesis_id = arguments.get("hypothesis_id", "").strip()
            experiment_id = arguments.get("experiment_id", "").strip()
            if not hypothesis_id or not experiment_id:
                return ToolResult(
                    success=False,
                    content="hypothesis_id and experiment_id are required",
                    error="Missing parameters",
                )
            content = _read_experiment_file(
                self._workspace_path, hypothesis_id, experiment_id
            )
            return ToolResult(
                success=True,
                content=content,
                data={"hypothesis_id": hypothesis_id, "experiment_id": experiment_id},
            )
        except Exception as e:
            logger.exception("read_experiment_file failed")
            return ToolResult(success=False, content=str(e), error=str(e))


class SynthesizeExperimentsTool(BaseTool):
    """运行多假设/多实验综合分析，生成综合报告。主 Agent 可先列目录、读文件，再决定是否调用。"""

    def get_name(self) -> str:
        return "synthesize"

    def get_description(self) -> str:
        return (
            "Trigger synthesis across hypotheses/experiments. You only decide *that* synthesis should run; "
            "the analysis module discovers hypotheses/experiments, runs per-experiment analysis as needed, "
            "then produces a unified synthesis report. Optional: hypothesis_ids, experiment_ids to restrict scope; "
            "literature_summary to incorporate literature."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional. List of hypothesis IDs to include; omit to use all.",
                },
                "experiment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional. List of experiment IDs per hypothesis; omit to use all.",
                },
                "custom_instructions": {
                    "type": "string",
                    "description": "Optional. Custom instructions for synthesis.",
                },
                "literature_summary": {
                    "type": "string",
                    "description": "Optional. Literature review summary; will be incorporated into synthesis and report.",
                },
            },
            "required": [],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            hypothesis_ids = arguments.get("hypothesis_ids")
            experiment_ids = arguments.get("experiment_ids")
            custom_instructions = arguments.get("custom_instructions")
            literature_summary = arguments.get("literature_summary")

            async def on_progress(msg: str) -> None:
                await self._send_progress(
                    ToolEvent(
                        tool_id=self._current_tool_id,
                        tool_name=self.get_name(),
                        status="progress",
                        content=msg,
                    )
                )

            config = AnalysisConfig(workspace_path=self._workspace_path)
            synth = Synthesizer(
                workspace_path=self._workspace_path,
                config=config,
            )
            synthesis = await synth.synthesize(
                hypothesis_ids=hypothesis_ids,
                experiment_ids=experiment_ids,
                custom_instructions=custom_instructions,
                literature_summary=literature_summary,
                on_progress=on_progress,
            )

            content_parts = [
                "Synthesis completed.",
                f"Best hypothesis: {synthesis.best_hypothesis or 'N/A'}",
                f"Reason: {synthesis.best_hypothesis_reason or 'N/A'}",
            ]
            if synthesis.synthesis_report_path:
                content_parts.append(f"Report: {synthesis.synthesis_report_path}")

            return ToolResult(
                success=True,
                content="\n".join(content_parts),
                data={
                    "best_hypothesis": synthesis.best_hypothesis,
                    "best_hypothesis_reason": synthesis.best_hypothesis_reason,
                    "synthesis_report_path": synthesis.synthesis_report_path,
                    "hypothesis_count": len(synthesis.hypothesis_summaries),
                },
            )
        except Exception as e:
            logger.exception("synthesize failed")
            return ToolResult(success=False, content=str(e), error=str(e))
