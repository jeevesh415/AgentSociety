"""
models.py

标准化实验分析数据模型

说明:
    本模块定义了实验分析的核心 Pydantic 数据模型，包括实验设计、执行上下文、分析结果和报告资源等。
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
SUPPORTED_ASSET_FORMATS = SUPPORTED_IMAGE_FORMATS | {".pdf"}


class ExperimentStatus(str, Enum):
    """实验执行的状态"""

    SUCCESSFUL = "successful"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class ExperimentDesign(BaseModel):
    """实验设计"""

    hypothesis: str = Field(..., description="Primary hypothesis being tested")
    objectives: List[str] = Field(
        default_factory=list, description="Experiment objectives"
    )
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables")
    methodology: str = Field(default="", description="Experimental methodology")
    success_criteria: List[str] = Field(
        default_factory=list, description="Success criteria"
    )

    hypothesis_markdown: Optional[str] = Field(
        default=None, description="Raw content of HYPOTHESIS.md if available"
    )
    experiment_markdown: Optional[str] = Field(
        default=None, description="Raw content of EXPERIMENT.md if available"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExperimentContext(BaseModel):
    """完整实验状态"""

    experiment_id: str = Field(..., description="Experiment identifier")
    hypothesis_id: str = Field(..., description="Hypothesis identifier")
    design: ExperimentDesign = Field(..., description="Experiment design")

    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")
    execution_status: ExperimentStatus = Field(
        default=ExperimentStatus.UNKNOWN, description="Execution status"
    )
    completion_percentage: float = Field(
        default=0.0, description="Completion percentage"
    )
    error_messages: List[str] = Field(
        default_factory=list, description="Error messages"
    )


class AnalysisResult(BaseModel):
    """实验分析结果"""

    experiment_id: str = Field(..., description="Experiment identifier")
    hypothesis_id: str = Field(..., description="Hypothesis identifier")

    insights: List[Any] = Field(default_factory=list, description="Generated insights")
    findings: List[Any] = Field(default_factory=list, description="Key findings")
    conclusions: Any = Field(default="", description="Conclusions")
    recommendations: List[Any] = Field(
        default_factory=list, description="Recommendations"
    )

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Generation time"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ReportContent(BaseModel):
    """报告内容"""

    title: str = Field(..., description="Report title")
    subtitle: str = Field(default="", description="Report subtitle")
    format_preference: str = Field(
        default="markdown", description="Preferred format: markdown, html, or both"
    )
    full_content_markdown: Optional[str] = Field(
        default=None, description="Complete markdown report content"
    )
    full_content_html: Optional[str] = Field(
        default=None, description="Complete HTML report content"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ReportAsset(BaseModel):
    """报告所需要的其他资源"""

    asset_id: str = Field(..., description="Asset identifier")
    asset_type: str = Field(..., description="Asset type")
    title: str = Field(..., description="Asset title")
    description: str = Field(default="", description="Asset description")

    file_path: str = Field(..., description="File path")
    embedded_content: Optional[str] = Field(None, description="Base64 content")
    file_size: int = Field(default=0, description="File size in bytes")

    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation time"
    )
    dimensions: Optional[Dict[str, int]] = Field(None, description="Dimensions")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AnalysisConfig(BaseModel):
    """分析服务配置"""

    workspace_path: str = Field(..., description="Workspace path")

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, v):
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Workspace path does not exist: {v}")
        return str(path.absolute())


class HypothesisSummary(BaseModel):
    """单个假设的聚合总结（跨多个实验）。"""

    hypothesis_id: str = Field(..., description="Hypothesis identifier")
    hypothesis_text: str = Field(..., description="Hypothesis text")

    experiment_count: int = Field(default=0, description="Number of experiments")
    successful_experiments: int = Field(default=0, description="Number of successful experiments")
    total_completion: float = Field(default=0.0, description="Average completion percentage")

    key_insights: List[str] = Field(default_factory=list, description="Key insights")
    main_findings: List[str] = Field(default_factory=list, description="Main findings")
    experiment_results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Analysis results for each experiment",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExperimentSynthesis(BaseModel):
    """多假设/多实验的综合结果。"""

    synthesis_id: str = Field(..., description="Synthesis identifier")
    workspace_path: str = Field(..., description="Workspace path")
    synthesis_timestamp: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")

    hypothesis_summaries: List[HypothesisSummary] = Field(
        default_factory=list,
        description="Summary information for each hypothesis",
    )

    synthesis_strategy: str = Field(default="", description="Analysis strategy decided by LLM")
    cross_hypothesis_analysis: str = Field(default="", description="Cross-hypothesis analysis")
    comparative_insights: List[str] = Field(default_factory=list, description="Comparative insights")
    unified_conclusions: str = Field(default="", description="Unified conclusions")
    recommendations: List[str] = Field(default_factory=list, description="Comprehensive recommendations")

    best_hypothesis: Optional[str] = Field(None, description="Best hypothesis identifier")
    best_hypothesis_reason: str = Field(default="", description="Reason for best hypothesis")
    overall_assessment: str = Field(default="", description="Overall assessment")

    synthesis_report_path: Optional[str] = Field(None, description="Synthesis report file path")

    model_config = ConfigDict(arbitrary_types_allowed=True)
