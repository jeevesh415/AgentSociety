"""
分析子智能体
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
    ExperimentPaths,
    PresentationPaths,
    DIR_HYPOTHESIS_PREFIX,
    DIR_EXPERIMENT_PREFIX,
    DIR_RUN,
    DIR_ARTIFACTS,
    DIR_CHARTS,
    DIR_PRESENTATION,
    DIR_SYNTHESIS,
    FILE_HYPOTHESIS_MD,
    FILE_EXPERIMENT_MD,
    FILE_SQLITE,
)
from .agents import InsightAgent, DataExplorer
from .tool_executor import AnalysisRunner
from .service import Analyzer, run_analysis, Synthesizer, run_synthesis
from .report_generator import Reporter
from .utils import (
    XmlParseError,
    parse_llm_xml_response,
    parse_llm_xml_to_model,
    parse_llm_report_response,
    get_analysis_skills,
    experiment_paths,
    presentation_paths,
    extract_database_schema,
    format_database_schema_markdown,
    collect_experiment_files,
)
from .eda import generate_eda_profile, generate_sweetviz_profile, generate_quick_stats

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
    "ExperimentPaths",
    "PresentationPaths",
    # Path constants (for tools / callers)
    "DIR_HYPOTHESIS_PREFIX",
    "DIR_EXPERIMENT_PREFIX",
    "DIR_RUN",
    "DIR_ARTIFACTS",
    "DIR_CHARTS",
    "DIR_PRESENTATION",
    "DIR_SYNTHESIS",
    "FILE_HYPOTHESIS_MD",
    "FILE_EXPERIMENT_MD",
    "FILE_SQLITE",
    # 分析子智能体入口与便捷函数
    "Analyzer",
    "run_analysis",
    "Synthesizer",
    "run_synthesis",
    # 子智能体组件
    "InsightAgent",
    "DataExplorer",
    "AnalysisRunner",
    "Reporter",
    # Paths & schema (utils)
    "experiment_paths",
    "presentation_paths",
    "extract_database_schema",
    "format_database_schema_markdown",
    "collect_experiment_files",
    # Utils
    "XmlParseError",
    "parse_llm_xml_response",
    "parse_llm_xml_to_model",
    "parse_llm_report_response",
    "get_analysis_skills",
    "generate_eda_profile",
    "generate_sweetviz_profile",
    "generate_quick_stats",
]
