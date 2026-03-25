"""数据分析子智能体模块。

本模块提供实验结果分析和报告生成的完整工具链，核心子智能体为：

- :class:`AnalysisAgent` — 统一分析智能体，负责洞察、策略、工具执行与可视化

核心功能：

- **数据分析**: 使用 LLM 和代码执行器分析 SQLite 数据库
- **可视化生成**: 自动生成图表和 EDA 报告
- **报告生成**: 产出结构化的分析报告（支持中英双语）

主要入口函数：

- :func:`run_analysis` — 运行完整的分析流程
- :func:`run_synthesis` — 生成综合报告

Example::

    from agentsociety2.skills.analysis import run_analysis, Analyzer

    # 使用便捷函数
    result = await run_analysis(
        workspace_path=Path("./workspace"),
        hypothesis_id="1",
        experiment_id="1",
    )

    # 使用 Analyzer 类
    analyzer = Analyzer(AnalysisConfig(workspace_path="./workspace"))
    await analyzer.analyze(hypothesis_id="1", experiment_id="1")
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
    LANG_ZH,
    LANG_EN,
    FILE_REPORT_ZH_MD,
    FILE_REPORT_ZH_HTML,
    FILE_REPORT_EN_MD,
    FILE_REPORT_EN_HTML,
    FILE_SYNTHESIS_REPORT_ZH_SUFFIX,
    FILE_SYNTHESIS_REPORT_EN_SUFFIX,
)
from .agents import AnalysisAgent
from .tool_executor import AnalysisRunner
from .service import Analyzer, run_analysis, Synthesizer, run_synthesis
from .report_generator import Reporter
from .utils import (
    AnalysisSkillMeta,
    XmlParseError,
    parse_llm_xml_response,
    parse_llm_xml_to_model,
    parse_llm_report_response,
    list_analysis_skills,
    get_analysis_skills,
    experiment_paths,
    presentation_paths,
    extract_database_schema,
    format_database_schema_markdown,
    collect_experiment_files,
)
from .eda import (
    generate_eda_profile,
    generate_sweetviz_profile,
    generate_quick_stats,
    generate_missingno_visualization,
    generate_multitable_summary,
    generate_full_eda_report,
)

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
    "LANG_ZH",
    "LANG_EN",
    "FILE_REPORT_ZH_MD",
    "FILE_REPORT_ZH_HTML",
    "FILE_REPORT_EN_MD",
    "FILE_REPORT_EN_HTML",
    "FILE_SYNTHESIS_REPORT_ZH_SUFFIX",
    "FILE_SYNTHESIS_REPORT_EN_SUFFIX",
    # 分析子智能体入口与便捷函数
    "Analyzer",
    "run_analysis",
    "Synthesizer",
    "run_synthesis",
    # 统一分析智能体
    "AnalysisAgent",
    # 其他组件
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
    "AnalysisSkillMeta",
    "parse_llm_xml_response",
    "parse_llm_xml_to_model",
    "parse_llm_report_response",
    "list_analysis_skills",
    "get_analysis_skills",
    "generate_eda_profile",
    "generate_sweetviz_profile",
    "generate_quick_stats",
    "generate_missingno_visualization",
    "generate_multitable_summary",
    "generate_full_eda_report",
]
