"""
Experiment Analysis Module

Agent-based intelligent analysis system for experiments.
"""

from .models import (
    ExperimentStatus,
    ExperimentDesign,
    ExperimentContext,
    AnalysisResult,
    ReportContent,
    ReportAsset,
    AnalysisConfig,
    ExperimentSynthesis,
    HypothesisSummary,
)

from .analysis_agent import AnalysisAgent
from .data_analysis_agent import DataAnalysisAgent
from .tool_executor import ToolExecutor
from .service import (
    AnalysisService,
    analyze_experiment,
    ExperimentSynthesizer,
    synthesize_experiments,
)
from .report_generator import ReportGenerator
from .utils import parse_llm_json_response, parse_llm_json_to_model

__all__ = [
    # Models
    "ExperimentStatus",
    "ExperimentDesign",
    "ExperimentContext",
    "AnalysisResult",
    "ReportContent",
    "ReportAsset",
    "AnalysisConfig",
    "ExperimentSynthesis",
    "HypothesisSummary",
    # Services
    "AnalysisService",
    "analyze_experiment",
    # Components
    "AnalysisAgent",
    "ReportGenerator",
    # Synthesis
    "ExperimentSynthesizer",
    "synthesize_experiments",
    # Utils
    "parse_llm_json_response",
    "parse_llm_json_to_model",
]
