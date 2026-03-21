"""
统一分析智能体：数据优先的分析流程，合并定性分析与定量分析。

设计原则：
1. 数据优先：先读取数据，理解数据结构，再进行分析
2. 统一上下文：洞察生成与可视化共享数据上下文
3. 确保准确性：基于实际数据生成洞察，而非空洞的文本生成
4. 上下文压缩：在迭代过程中压缩历史上下文，防止膨胀
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json_repair
from pydantic import BaseModel, Field
from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model, get_model_name
from litellm import AllMessageValues

from .models import (
    ExperimentContext,
    AnalysisResult,
    AnalysisConfig,
    SUPPORTED_ASSET_FORMATS,
    DIR_DATA,
)
from .prompts import (
    judgment_prompt,
    analysis_xml_contract,
    strategy_xml_contract,
    adjust_tools_xml_contract,
    visualization_xml_contract,
    summary_xml_contract,
)
from .utils import (
    XmlParseError,
    parse_llm_xml_response,
    parse_llm_xml_to_model,
    get_analysis_skills,
    extract_database_schema,
    format_database_schema_markdown,
    collect_experiment_files,
    AnalysisProgressCallback,
)
from .tool_executor import AnalysisRunner


class ContextSummary(BaseModel):
    """上下文摘要，用于压缩历史信息"""

    key_findings: List[str] = Field(default_factory=list)  # 关键发现
    failed_attempts: List[str] = Field(default_factory=list)  # 失败尝试
    successful_tools: List[str] = Field(default_factory=list)  # 成功的工具
    recommendations: str = ""  # 后续建议
    iteration_count: int = 0  # 迭代次数


def _system_with_skills(config: Optional[AnalysisConfig] = None) -> str:
    """返回分析子智能体的技能说明，并要求返回XML格式。"""
    selected_names = config.analysis_skill_names if config else None
    strict_selection = (
        config.analysis_skill_strict_selection if config else True
    )
    skills = get_analysis_skills(
        selected_names=selected_names,
        strict_selection=strict_selection,
    )
    base = "Return only the XML the prompt requests."
    return f"{skills}\n\n---\n\n{base}" if skills else base


class AnalysisJudgment(BaseModel):
    """分析结果判断"""

    success: bool
    reason: str
    should_retry: bool = False
    retry_instruction: str = ""


class StrategyJudgment(BaseModel):
    """分析策略判断"""

    success: bool
    reason: str
    should_retry: bool = False
    retry_instruction: str = ""


class VisualizationJudgment(BaseModel):
    """可视化结果判断"""

    success: bool
    reason: str
    should_retry: bool = False
    retry_instruction: str = ""


class DataSummary(BaseModel):
    """数据摘要，用于共享上下文"""

    db_path: Optional[str] = None
    schema_markdown: str = ""
    tables: List[str] = Field(default_factory=list)
    row_counts: Dict[str, int] = Field(default_factory=dict)
    quick_stats: str = ""
    sample_data: Dict[str, List[Dict]] = Field(default_factory=dict)  # 每个表的前几行数据
    numeric_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # 数值列统计摘要
    categorical_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # 分类列统计摘要


def _quote_identifier(name: str) -> str:
    """Safely quote SQLite identifiers (table/column names)."""
    return '"' + name.replace('"', '""') + '"'


class AnalysisAgent:
    """
    统一分析智能体：数据优先的分析流程。

    流程：
    1. 读取并理解数据结构
    2. 基于实际数据生成洞察
    3. 决定分析策略和可视化方案
    4. 执行数据分析代码
    5. 生成可视化图表
    """

    def __init__(
        self,
        config: AnalysisConfig,
        llm_router=None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        workspace_path: Optional[Path] = None,
    ):
        """初始化统一分析智能体。"""
        self.logger = get_logger()
        self.config = config
        self.temperature = (
            temperature if temperature is not None else config.temperature
        )
        self.workspace_path = workspace_path or Path.cwd()
        self.max_retries = max(1, min(20, config.max_analysis_retries))

        # LLM 配置
        profile = config.llm_profile_default
        if llm_router is None:
            self.llm_router, self.model_name = get_llm_router_and_model(profile)
        else:
            self.llm_router = llm_router
            self.model_name = (
                model_name if model_name is not None else get_model_name(profile)
            )

        self.logger.info("统一分析智能体初始化完成，使用模型: %s", self.model_name)

    async def analyze(
        self,
        context: ExperimentContext,
        db_path: Optional[Path],
        output_dir: Path,
        custom_instructions: Optional[str] = None,
        literature_summary: Optional[str] = None,
        on_progress: AnalysisProgressCallback = None,
    ) -> Tuple[AnalysisResult, Dict[str, Any]]:
        """
        执行完整的数据分析流程。

        Returns:
            (AnalysisResult, 数据分析产物字典)
        """
        self.logger.info("开始分析实验 %s", context.experiment_id)

        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        # Step 1: 读取并理解数据
        data_summary = DataSummary()
        if db_path and db_path.exists():
            await progress("Reading and understanding data structure...")
            data_summary = await self._understand_data(db_path)
            self.logger.info(
                "数据理解完成: %s 个表, 总行数: %s",
                len(data_summary.tables),
                sum(data_summary.row_counts.values()),
            )
        else:
            self.logger.info("未找到数据库，跳过数据分析")

        # Step 2: 基于数据生成洞察
        await progress("Generating insights from data...")
        analysis_result = await self._generate_insights_with_data(
            context,
            data_summary,
            custom_instructions,
            literature_summary,
        )

        # Step 3: 执行数据分析和可视化
        data_analysis_result: Dict[str, Any] = {
            "analysis_plan": {},
            "tool_results": {},
            "visualization_plan": [],
            "generated_charts": [],
            "eda_profile_path": None,
            "eda_sweetviz_path": None,
        }

        if db_path and db_path.exists():
            await progress("Planning data analysis...")
            tool_executor = AnalysisRunner(
                self.workspace_path,
                output_dir,
                tool_registry=None,
                config=self.config,
            )

            # Step 3.1: 决定分析策略
            analysis_plan = await self._decide_analysis_strategy_with_judgment(
                context, analysis_result, data_summary, tool_executor, on_progress
            )
            data_analysis_result["analysis_plan"] = analysis_plan

            # Step 3.2: 执行工具
            if analysis_plan.get("tools_to_use"):
                await progress("Running data analysis tools...")
                tool_results = await self._execute_tools_with_feedback(
                    tool_executor,
                    analysis_plan.get("tools_to_use", []),
                    db_path,
                    output_dir,
                    context,
                    analysis_result,
                    data_summary,
                    on_progress=on_progress,
                )
                data_analysis_result["tool_results"] = tool_results

                # 提取 EDA 路径
                data_analysis_result["eda_profile_path"] = tool_results.get("eda_profile", {}).get("path")
                data_analysis_result["eda_sweetviz_path"] = tool_results.get("eda_sweetviz", {}).get("path")

            # Step 3.3: 生成可视化
            await progress("Generating visualizations...")
            viz_plan, charts = await self._decide_and_generate_visualizations_with_judgment(
                context,
                analysis_result,
                data_summary,
                data_analysis_result["tool_results"],
                db_path,
                output_dir,
                tool_executor,
                on_progress=on_progress,
            )
            data_analysis_result["visualization_plan"] = viz_plan
            data_analysis_result["generated_charts"] = charts

        # 将 data_summary 添加到返回结果中，供后续报告生成使用
        data_analysis_result["data_summary"] = data_summary

        return analysis_result, data_analysis_result

    async def _understand_data(self, db_path: Path) -> DataSummary:
        """
        读取并理解数据结构。

        这是数据优先分析流程的核心：在实际分析之前，
        先了解数据的结构、行数、样本数据、统计摘要。
        """
        summary = DataSummary(db_path=str(db_path))

        if not db_path.exists():
            return summary

        # 提取 schema
        schema = extract_database_schema(db_path)
        summary.tables = list(schema.keys())
        summary.schema_markdown = format_database_schema_markdown(
            schema, include_row_counts=True, db_path=db_path
        )

        # 提取行数
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        for table in summary.tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}")
                summary.row_counts[table] = cursor.fetchone()[0]
            except sqlite3.Error:
                summary.row_counts[table] = 0

        # 提取每个表的前几行数据作为样本（增加到5行）
        for table in summary.tables:
            if summary.row_counts.get(table, 0) > 0:
                try:
                    cursor.execute(
                        f"SELECT * FROM {_quote_identifier(table)} LIMIT 5"
                    )
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    summary.sample_data[table] = [
                        dict(zip(columns, row)) for row in rows
                    ]
                except sqlite3.Error:
                    pass

        # 计算数值列和分类列的统计摘要
        summary.numeric_stats = self._compute_numeric_stats(conn, summary.tables, schema)
        summary.categorical_stats = self._compute_categorical_stats(conn, summary.tables, schema)

        # 生成快速统计
        summary.quick_stats = self._generate_quick_stats_markdown(summary)
        conn.close()

        return summary

    def _compute_numeric_stats(
        self,
        conn,
        tables: List[str],
        schema: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """计算数值列的统计摘要（min, max, avg, count）。"""
        import sqlite3
        cursor = conn.cursor()
        result: Dict[str, Dict[str, Any]] = {}

        for table in tables:
            columns_info = schema.get(table, [])
            numeric_cols = [
                col["name"] for col in columns_info
                if col.get("type", "").upper() in ("INTEGER", "REAL", "FLOAT", "DOUBLE", "NUMERIC")
            ]
            if not numeric_cols:
                continue

            table_stats: Dict[str, Any] = {}
            for col in numeric_cols:
                try:
                    t = _quote_identifier(table)
                    c = _quote_identifier(col)
                    cursor.execute(
                        f"SELECT MIN({c}), MAX({c}), AVG({c}), COUNT({c}) FROM {t}"
                    )
                    row = cursor.fetchone()
                    if row and row[3] > 0:  # 有数据
                        table_stats[col] = {
                            "min": row[0],
                            "max": row[1],
                            "avg": round(row[2], 4) if row[2] is not None else None,
                            "count": row[3],
                        }
                except sqlite3.Error:
                    pass
            if table_stats:
                result[table] = table_stats

        return result

    def _compute_categorical_stats(
        self,
        conn,
        tables: List[str],
        schema: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """计算分类列的统计摘要（唯一值数量、高频值）。"""
        import sqlite3
        cursor = conn.cursor()
        result: Dict[str, Dict[str, Any]] = {}

        for table in tables:
            columns_info = schema.get(table, [])
            text_cols = [
                col["name"] for col in columns_info
                if col.get("type", "").upper() in ("TEXT", "VARCHAR", "CHAR", "STRING")
            ]
            if not text_cols:
                continue

            table_stats: Dict[str, Any] = {}
            for col in text_cols:
                try:
                    # 唯一值数量
                    t = _quote_identifier(table)
                    c = _quote_identifier(col)
                    cursor.execute(f"SELECT COUNT(DISTINCT {c}) FROM {t}")
                    unique_count = cursor.fetchone()[0]

                    # 高频值（top 5）
                    cursor.execute(
                        f"SELECT {c}, COUNT(*) as cnt FROM {t} "
                        f"WHERE {c} IS NOT NULL GROUP BY {c} ORDER BY cnt DESC LIMIT 5"
                    )
                    top_values = cursor.fetchall()

                    if unique_count > 0:
                        table_stats[col] = {
                            "unique_count": unique_count,
                            "top_values": [(v[0], v[1]) for v in top_values] if top_values else [],
                        }
                except sqlite3.Error:
                    pass
            if table_stats:
                result[table] = table_stats

        return result

    def _generate_quick_stats_markdown(self, summary: DataSummary) -> str:
        """生成快速统计的 Markdown 摘要。"""
        lines = ["## Data Overview\n"]
        lines.append(f"- **Database**: {summary.db_path}")
        lines.append(f"- **Tables**: {len(summary.tables)}")
        lines.append(f"- **Total Rows**: {sum(summary.row_counts.values())}")
        lines.append("")

        for table in summary.tables:
            rows = summary.row_counts.get(table, 0)
            lines.append(f"### Table: `{table}` ({rows} rows)")

            # 样本数据
            if summary.sample_data.get(table):
                lines.append("Sample data (first rows):")
                for i, row in enumerate(summary.sample_data[table][:3], 1):
                    items = [f"  - {k}: {v}" for k, v in list(row.items())[:5]]
                    lines.append(f"  Row {i}:")
                    lines.extend(items)
                lines.append("")

            # 数值列统计
            if table in summary.numeric_stats:
                lines.append("Numeric columns stats:")
                for col, stats in summary.numeric_stats[table].items():
                    lines.append(f"  - `{col}`: min={stats.get('min')}, max={stats.get('max')}, avg={stats.get('avg')}")
                lines.append("")

            # 分类列统计
            if table in summary.categorical_stats:
                lines.append("Categorical columns stats:")
                for col, stats in summary.categorical_stats[table].items():
                    unique = stats.get('unique_count', 0)
                    top_vals = stats.get('top_values', [])[:3]
                    top_str = ", ".join([f"'{v[0]}'({v[1]})" for v in top_vals if v[0] is not None])
                    lines.append(f"  - `{col}`: {unique} unique values, top: {top_str}")
                lines.append("")

        return "\n".join(lines)

    async def _generate_insights_with_data(
        self,
        context: ExperimentContext,
        data_summary: DataSummary,
        custom_instructions: Optional[str] = None,
        literature_summary: Optional[str] = None,
    ) -> AnalysisResult:
        """
        基于实际数据生成洞察。

        关键：洞察生成时能看到数据结构和样本数据，
        使用 LLM 总结长文档。
        """
        # 使用 LLM 总结长文档
        hypothesis_md_block = ""
        if getattr(context.design, "hypothesis_markdown", None):
            hyp_md = await self._summarize_document(
                context.design.hypothesis_markdown,
                "hypothesis",
                max_length=800,
            )
            hypothesis_md_block = f"\n## Hypothesis Document\n\n```markdown\n{hyp_md}\n```\n"

        experiment_md_block = ""
        if getattr(context.design, "experiment_markdown", None):
            exp_md = await self._summarize_document(
                context.design.experiment_markdown,
                "experiment design",
                max_length=800,
            )
            experiment_md_block = f"\n## Experiment Design Document\n\n```markdown\n{exp_md}\n```\n"

        literature_block = ""
        if literature_summary and literature_summary.strip():
            lit = await self._summarize_document(
                literature_summary.strip(),
                "literature context",
                max_length=600,
            )
            literature_block = f"\n## Literature Context\n\n{lit}\n"

        data_block = ""
        if data_summary.schema_markdown:
            # 对于 schema，使用 LLM 总结（schema 很重要，需要智能提取）
            schema_md = await self._summarize_schema(
                data_summary.schema_markdown,
                data_summary.row_counts,
            )

            # quick_stats 可以截断（统计信息相对结构化）
            quick_stats = data_summary.quick_stats
            if len(quick_stats) > 1500:
                quick_stats = quick_stats[:1500] + "\n...[more stats available]"

            data_block = f"""
## Actual Data Structure

**CRITICAL - DATA-FIRST PRINCIPLE**:
- You MUST base your insights on the ACTUAL data structure below.
- Do NOT invent tables, columns, or values that are not shown here.
- If tables are empty or sparse, explicitly acknowledge this limitation.
- Reference actual table/column names and row counts in your insights.

{schema_md}

{quick_stats}

**Data Quality Notes**:
- Total tables: {len(data_summary.tables)}
- Non-empty tables: {sum(1 for t in data_summary.tables if data_summary.row_counts.get(t, 0) > 0)}
- Empty tables: {sum(1 for t in data_summary.tables if data_summary.row_counts.get(t, 0) == 0)}
"""

        custom_block = ""
        if custom_instructions:
            custom_block = f"\n## Custom Instructions\n\n{custom_instructions}\n"

        # 压缩错误信息
        errors_text = "None"
        if context.error_messages:
            errors = [str(e)[:150] for e in context.error_messages[:3]]
            errors_text = "\n".join([f"- {e}" for e in errors])
            if len(context.error_messages) > 3:
                errors_text += f"\n... ({len(context.error_messages) - 3} more errors)"

        prompt = f"""## Experiment Context

**Experiment ID**: {context.experiment_id} | **Hypothesis ID**: {context.hypothesis_id}
**Hypothesis**: {context.design.hypothesis}
**Status**: {context.execution_status.value} | **Completion**: {context.completion_percentage:.1f}% | **Duration**: {f"{context.duration_seconds:.2f}s" if context.duration_seconds else "Unknown"}
**Errors**: {errors_text}

{hypothesis_md_block}{experiment_md_block}{data_block}{literature_block}{custom_block}

Based on the experiment context and **actual data structure above**, generate analysis insights.

**CRITICAL**: Your insights must be grounded in the actual data available. If tables are empty or data is limited, acknowledge this and provide appropriate caveats.

{analysis_xml_contract()}"""

        messages: List[AllMessageValues] = []
        skills = _system_with_skills(self.config)
        if skills:
            messages.append({"role": "system", "content": skills})
        messages.append({"role": "user", "content": prompt})

        # 重试循环
        parsed: Optional[Dict[str, Any]] = None
        for attempt in range(self.max_retries):
            self.logger.info(
                "生成分析结果 (第 %s/%s 次尝试)",
                attempt + 1,
                self.max_retries,
            )
            try:
                response = await self.llm_router.acompletion(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                )
                raw = response.choices[0].message.content or ""
                parsed = self._parse_analysis_response(raw)
                judgment = await self._judge_analysis_result(parsed, context, data_summary)
            except XmlParseError as e:
                if attempt >= self.max_retries - 1:
                    self.logger.warning("XML解析失败，尝试 %s 次后失败: %s", self.max_retries, e)
                    parsed = {}
                    break
                messages.append({
                    "role": "user",
                    "content": f"XML parse failed: {e}\n\nPlease fix and return valid XML only.",
                })
                continue

            if judgment.success or not judgment.should_retry or attempt >= self.max_retries - 1:
                break

            messages.append({
                "role": "user",
                "content": f"Previous output needs improvement: {judgment.reason}\n{judgment.retry_instruction}\nReturn corrected XML only.",
            })

        if not parsed:
            parsed = {}

        return AnalysisResult(
            experiment_id=context.experiment_id,
            hypothesis_id=context.hypothesis_id,
            insights=parsed.get("insights", []),
            findings=parsed.get("findings", []),
            conclusions=parsed.get("conclusions", ""),
            recommendations=parsed.get("recommendations", []),
            generated_at=datetime.now(),
        )

    def _parse_analysis_response(self, content: str) -> Dict[str, Any]:
        """解析分析结果。"""
        data = parse_llm_xml_response(content, root_tag="analysis")
        insights = data.get("insights", [])
        findings = data.get("findings", [])
        recs = data.get("recommendations", [])

        if isinstance(insights, dict) and "item" in insights:
            insights = insights["item"] if isinstance(insights["item"], list) else [insights["item"]]
        if isinstance(findings, dict) and "item" in findings:
            findings = findings["item"] if isinstance(findings["item"], list) else [findings["item"]]
        if isinstance(recs, dict) and "item" in recs:
            recs = recs["item"] if isinstance(recs["item"], list) else [recs["item"]]

        return {
            "insights": insights if isinstance(insights, list) else [insights] if insights else [],
            "findings": findings if isinstance(findings, list) else [findings] if findings else [],
            "conclusions": data.get("conclusions", "") or "",
            "recommendations": recs if isinstance(recs, list) else [recs] if recs else [],
        }

    async def _judge_analysis_result(
        self,
        parsed: Dict[str, Any],
        context: ExperimentContext,
        data_summary: DataSummary,
    ) -> AnalysisJudgment:
        """
        判断分析结果是否合理。

        注意：data_summary.schema_markdown 已经在 _generate_insights_with_data 中被 LLM 总结过，
        这里直接使用，不需要额外处理。
        """
        hypothesis_preview = (context.design.hypothesis or "")[:300]

        # schema_markdown 已被 LLM 总结，直接使用
        schema_preview = data_summary.schema_markdown or "No data available"
        if len(schema_preview) > 1000:
            # 如果仍然很长，说明原始数据量极大，保留关键部分
            schema_preview = schema_preview[:1000] + "\n...[schema summarized]"

        # 构建数据摘要
        total_rows = sum(data_summary.row_counts.values())
        non_empty_tables = [t for t in data_summary.tables if data_summary.row_counts.get(t, 0) > 0]
        empty_tables = [t for t in data_summary.tables if data_summary.row_counts.get(t, 0) == 0]

        prompt = f"""Evaluate the analysis for experiment {context.experiment_id}.

**Hypothesis**: {hypothesis_preview}

**Available Data Summary**:
- Total tables: {len(data_summary.tables)}
- Non-empty tables: {non_empty_tables}
- Empty tables: {empty_tables}
- Total rows: {total_rows}

**Schema**:
{schema_preview}

**Generated**: {len(parsed.get("insights", []))} insights, {len(parsed.get("findings", []))} findings, conclusions, {len(parsed.get("recommendations", []))} recommendations.

**Checklist**:
1. Substantive content? (not generic placeholders)
2. Relevant to hypothesis?
3. Data-grounded? (insights reference actual table/column names from schema)
4. No hallucination? (no mention of non-existent tables/columns)
5. Data limitations acknowledged? (if tables are empty/sparse)
6. Conclusions reasonable?

{judgment_prompt()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        content = response.choices[0].message.content or ""
        return parse_llm_xml_to_model(content, AnalysisJudgment, root_tag="judgment")

    # ========== 分析策略与可视化方法 ==========

    async def _decide_analysis_strategy_with_judgment(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: DataSummary,
        tool_executor: AnalysisRunner,
        on_progress: Optional[AnalysisProgressCallback],
    ) -> Dict[str, Any]:
        """决定分析策略，经 LLM 裁判通过后返回。"""
        max_retries = self.config.max_strategy_retries
        for attempt in range(max_retries):
            try:
                analysis_plan = await self._decide_analysis_strategy(
                    context, analysis_result, data_summary, tool_executor
                )
                judgment = await self._judge_analysis_strategy(analysis_plan, context, data_summary)
            except XmlParseError as e:
                if attempt >= max_retries - 1:
                    self.logger.warning("分析策略XML解析失败: %s", e)
                    return {"analysis_strategy": "", "tools_to_use": []}
                if on_progress:
                    await on_progress(f"Strategy XML parse failed, retrying: {e}")
                continue

            if judgment.success or not judgment.should_retry or attempt >= max_retries - 1:
                return analysis_plan

            if on_progress:
                await on_progress(f"Strategy needs improvement: {judgment.reason}")

        return {"analysis_strategy": "", "tools_to_use": []}

    async def _decide_analysis_strategy(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: DataSummary,
        tool_executor: AnalysisRunner,
    ) -> Dict[str, Any]:
        """决定分析策略，选表/选工具。使用 LLM 总结而非截断。"""
        available_tools = tool_executor.discover_tools_with_schemas()
        builtin = {k: v for k, v in available_tools.items() if v.get("type") == "builtin"}
        tools_list = self._format_tools_list(builtin) if builtin else "No built-in tools"

        # 添加 EDA 工具说明
        if data_summary.db_path:
            eda_tools = [
                "- **eda_profile** (tool_type=eda_profile): Generate EDA report via ydata-profiling.",
                "- **eda_sweetviz** (tool_type=eda_sweetviz): Generate EDA via Sweetviz.",
            ]
            tools_list = tools_list + "\n\n**EDA tools**:\n" + "\n".join(eda_tools)

        # 使用 LLM 总结 schema（如果是大型 schema）
        schema_block = "(no schema)"
        if data_summary.schema_markdown:
            if len(data_summary.schema_markdown) > 2000:
                schema_block = await self._summarize_schema(
                    data_summary.schema_markdown,
                    data_summary.row_counts,
                )
            else:
                schema_block = data_summary.schema_markdown

        # 压缩 insights（insights 相对结构化，可以直接截断）
        insights_text = "None yet."
        if analysis_result.insights:
            insights = [str(i)[:200] for i in analysis_result.insights[:5]]
            insights_text = "\n".join([f"- {i}" for i in insights])

        prompt = f"""Decide how to analyze the experiment data and which tools to run.

**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}% | **Status**: {context.execution_status.value}

**Previous insights** (from data-aware analysis):
{insights_text}

**Database**: {data_summary.db_path}
**Database schema**:
{schema_block}

**Available tools**: {tools_list}

{strategy_xml_contract()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": _system_with_skills(self.config)},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )

        data = parse_llm_xml_response(response.choices[0].message.content or "", root_tag="strategy")
        tools = data.get("tools_to_use", [])

        if isinstance(tools, dict) and "tool" in tools:
            tools = tools["tool"] if isinstance(tools["tool"], list) else [tools["tool"]]
        if not isinstance(tools, list):
            tools = []

        normalized = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            params = t.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json_repair.loads(params) if params.strip() else {}
                except Exception:
                    params = {}
            normalized.append({
                "tool_name": t.get("tool_name", "code_executor"),
                "tool_type": t.get("tool_type", "code_executor"),
                "action": t.get("action", ""),
                "parameters": params if isinstance(params, dict) else {},
            })

        return {"analysis_strategy": data.get("analysis_strategy", ""), "tools_to_use": normalized}

    async def _judge_analysis_strategy(
        self,
        analysis_plan: Dict[str, Any],
        context: ExperimentContext,
        data_summary: DataSummary,
    ) -> StrategyJudgment:
        """判断分析策略是否合理。"""
        # 构建数据摘要
        total_rows = sum(data_summary.row_counts.values())
        non_empty_tables = [t for t in data_summary.tables if data_summary.row_counts.get(t, 0) > 0]
        empty_tables = [t for t in data_summary.tables if data_summary.row_counts.get(t, 0) == 0]

        prompt = f"""Evaluate the analysis strategy for experiment {context.experiment_id}.

**Hypothesis**: {context.design.hypothesis}

**Actual Data Summary**:
- Tables: {data_summary.tables}
- Non-empty: {non_empty_tables}
- Empty: {empty_tables}
- Total rows: {total_rows}

**Proposed strategy**:
- analysis_strategy: {analysis_plan.get("analysis_strategy", "")}
- tools_to_use: {analysis_plan.get("tools_to_use", [])}

**CRITICAL CHECKS**:
1. **Relevance**: Strategy relevant to hypothesis?
2. **Schema Alignment**: Tools reference ONLY tables/columns that exist in schema?
3. **Data Appropriateness**: If key tables are empty, does strategy adjust accordingly?
4. **EDA Usage**: EDA tools used when data overview needed?
5. **Hallucination Check**: Do tools reference tables that do NOT exist? If YES, FAIL.

{judgment_prompt()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        return parse_llm_xml_to_model(content, StrategyJudgment, root_tag="judgment")

    async def _execute_tools_with_feedback(
        self,
        tool_executor: AnalysisRunner,
        tools_to_use: List[Dict[str, Any]],
        db_path: Path,
        output_dir: Path,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: DataSummary,
        on_progress: AnalysisProgressCallback = None,
    ) -> Dict[str, Any]:
        """执行工具，并根据反馈调整策略。使用上下文压缩防止历史膨胀。"""

        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        results = {}
        conversation_history: List[Dict[str, Any]] = []
        context_summary: Optional[ContextSummary] = None
        max_iter = self.config.max_tool_iterations

        for iteration in range(max_iter):
            current_tools = tools_to_use if iteration == 0 else []
            if iteration > 0:
                adj = await self._adjust_strategy_based_on_results(
                    context,
                    analysis_result,
                    results,
                    context_summary,
                    iteration,
                )
                if not adj.get("tools_to_use"):
                    # 即便停止迭代，也保留这一轮的结构化总结，确保流程可追踪。
                    context_summary = await self._summarize_context(
                        conversation_history,
                        results,
                        iteration + 1,
                    )
                    self.logger.info("第 %d 轮无新增工具，完成总结后停止迭代", iteration + 1)
                    break
                current_tools = adj.get("tools_to_use", [])

            for i, tool_spec in enumerate(current_tools):
                tool_name = tool_spec.get("tool_name", f"tool_{i}")
                tool_type = tool_spec.get("tool_type", "code_executor")
                parameters = tool_spec.get("parameters", {})

                await progress(f"Running tool: {tool_name}...")

                if tool_type in ("eda_profile", "eda_sweetviz") or tool_name in ("eda_profile", "eda_sweetviz"):
                    result = await self._run_eda_tool(tool_name, db_path, output_dir, on_progress=progress)
                else:
                    exec_parameters = parameters.copy()
                    if tool_type == "code_executor":
                        exec_parameters["db_path"] = str(db_path)
                        exec_parameters["code_description"] = tool_spec.get("action", "")
                        exec_parameters["extra_files"] = collect_experiment_files(db_path)
                    result = await tool_executor.execute_tool(
                        tool_name=tool_name,
                        tool_type=tool_type,
                        parameters=exec_parameters,
                    )

                results[tool_name] = result
                # 只保留关键信息，不保留完整结果
                conversation_history.append({
                    "tool": tool_name,
                    "success": result.get("success", False),
                    "iteration": iteration + 1,
                    "result": {"success": result.get("success", False), "error": result.get("error", "")[:100]}
                })

            # 每一轮都总结：有工具执行时总结执行结果；无工具时总结当前状态。
            context_summary = await self._summarize_context(
                conversation_history,
                results,
                iteration + 1,
            )
            self.logger.info("已完成第 %d 轮总结，进入下一轮策略迭代", iteration + 1)
            self.logger.info(
                "第 %d 轮总结详情: key_findings=%d, failed_attempts=%d, successful_tools=%d, recommendations=%s",
                iteration + 1,
                len(context_summary.key_findings),
                len(context_summary.failed_attempts),
                len(context_summary.successful_tools),
                (context_summary.recommendations or "N/A")[:180],
            )

        return results

    async def _run_eda_tool(
        self,
        tool_name: str,
        db_path: Path,
        output_dir: Path,
        on_progress=None,
    ) -> Dict[str, Any]:
        """执行 EDA 工具。"""
        data_dir = output_dir / DIR_DATA
        data_dir.mkdir(parents=True, exist_ok=True)
        path = None

        if tool_name == "eda_profile":
            from .eda import generate_eda_profile
            path = generate_eda_profile(db_path, data_dir, config=self.config)
            if path and on_progress:
                await on_progress(f"EDA (ydata) generated: {path.name}")
        elif tool_name == "eda_sweetviz":
            from .eda import generate_sweetviz_profile
            path = generate_sweetviz_profile(db_path, data_dir, config=self.config)
            if path and on_progress:
                await on_progress(f"EDA (sweetviz) generated: {path.name}")

        if path and path.exists():
            return {"success": True, "path": str(path), "tool_name": tool_name}
        return {"success": False, "error": "EDA generation failed or skipped", "tool_name": tool_name}

    async def _adjust_strategy_based_on_results(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        current_results: Dict[str, Any],
        context_summary: Optional[ContextSummary],
        iteration: int,
    ) -> Dict[str, Any]:
        """根据工具执行结果，决定是否继续执行工具或停止。使用 LLM 总结。"""

        # 构建简洁的上下文信息
        if context_summary:
            history_context = self._format_context_summary(context_summary)
        else:
            # 回退到简单格式
            history_context = f"**Iteration**: {iteration}"

        # 使用 LLM 总结当前结果（如果有多个或者很长）
        if current_results and sum(len(str(r)) for r in current_results.values()) > 1500:
            results_summary = await self._summarize_tool_results(
                current_results,
                analysis_result.insights,
            )
        else:
            results_summary = self._format_tool_results(current_results, max_length=1500)

        prompt = f"""Decide whether to run more tools or stop.

**Hypothesis**: {context.design.hypothesis} | **Completion**: {context.completion_percentage:.1f}%

**Progress**:
{history_context}

**Latest results**:
{results_summary}

**Decision criteria**:
- If key analysis is complete and insights are sufficient → stop (empty tools_to_use)
- If more exploration needed → specify next tools
- If previous attempts failed → try alternative approach

{adjust_tools_xml_contract()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": _system_with_skills(self.config)},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )

        data = parse_llm_xml_response(response.choices[0].message.content or "", root_tag="adjust")
        tools = data.get("tools_to_use", [])

        if isinstance(tools, dict):
            t = tools.get("tool", [])
            tools = t if isinstance(t, list) else [t] if t else []
        elif not isinstance(tools, list):
            tools = []

        normalized = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            params = t.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json_repair.loads(params) if params.strip() else {}
                except Exception:
                    params = {}
            normalized.append({
                "tool_name": t.get("tool_name", "code_executor"),
                "tool_type": t.get("tool_type", "code_executor"),
                "action": t.get("action", ""),
                "parameters": params if isinstance(params, dict) else {},
            })

        return {"assessment": data.get("assessment", ""), "tools_to_use": normalized}

    async def _decide_and_generate_visualizations_with_judgment(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: DataSummary,
        tool_results: Dict[str, Any],
        db_path: Path,
        output_dir: Path,
        tool_executor: AnalysisRunner,
        on_progress: AnalysisProgressCallback = None,
    ) -> Tuple[List[Dict[str, Any]], List[Path]]:
        """决定可视化方案、生成图表，经裁判通过后返回。"""
        max_retries = self.config.max_visualization_retries
        previous_feedback: Optional[str] = None
        visualization_plan: List[Dict[str, Any]] = []
        generated_charts: List[Path] = []

        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        for attempt in range(max_retries):
            try:
                await progress("Deciding visualizations...")
                visualization_plan = await self._decide_visualizations(
                    context, analysis_result, data_summary, tool_results, previous_feedback
                )
            except XmlParseError as e:
                if attempt >= max_retries - 1:
                    self.logger.warning("可视化XML解析失败: %s", e)
                    return [], []
                previous_feedback = str(e)
                continue

            if not visualization_plan:
                return [], []

            await progress("Generating charts...")
            generated_charts, error_logs = await self._generate_visualizations(
                visualization_plan, db_path, output_dir, tool_executor, on_progress=on_progress
            )

            try:
                judgment = await self._judge_visualizations(
                    visualization_plan, generated_charts, context, tool_results, error_logs,
                    data_summary=data_summary
                )
            except XmlParseError as e:
                if attempt >= max_retries - 1:
                    return visualization_plan, generated_charts
                previous_feedback = str(e)
                continue

            if judgment.success or not judgment.should_retry or attempt >= max_retries - 1:
                return visualization_plan, generated_charts

            previous_feedback = f"{judgment.reason}. {judgment.retry_instruction}"

        return visualization_plan, generated_charts

    async def _decide_visualizations(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: DataSummary,
        analysis_results: Dict[str, Any],
        previous_feedback: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """决定可视化方案。使用 LLM 总结长内容。"""
        feedback_block = ""
        if previous_feedback:
            feedback_block = f"\n**Previous feedback**: {previous_feedback[:500]}\n"

        # 使用 LLM 总结 schema（如果是大型 schema）
        schema_block = "(no schema)"
        if data_summary.schema_markdown:
            if len(data_summary.schema_markdown) > 1500:
                schema_block = await self._summarize_schema(
                    data_summary.schema_markdown,
                    data_summary.row_counts,
                    max_tables=8,
                )
            else:
                schema_block = data_summary.schema_markdown

        # 压缩 insights
        insights_text = "None."
        if analysis_result.insights:
            insights = [str(i)[:200] for i in analysis_result.insights[:5]]
            insights_text = "\n".join([f"- {i}" for i in insights])

        # 对于工具结果，如果有多个或者很长，使用 LLM 总结
        tool_results_text = self._format_tool_results(analysis_results, max_length=1500)
        if len(tool_results_text) > 1200 and analysis_results:
            tool_results_text = await self._summarize_tool_results(
                analysis_results,
                analysis_result.insights,
            )

        prompt = f"""Decide which charts to generate.

**Hypothesis**: {context.design.hypothesis} | **Completion**: {context.completion_percentage:.1f}%

**Insights** (from data-aware analysis):
{insights_text}

**Database**: {data_summary.db_path}
**Table row counts**: {data_summary.row_counts}

**Schema**:
{schema_block}

**Tool results**: {tool_results_text}
{feedback_block}

{visualization_xml_contract()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": _system_with_skills(self.config)},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )

        data = parse_llm_xml_response(response.choices[0].message.content or "", root_tag="visualizations")
        viz = data.get("viz", data.get("visualizations", []))

        if isinstance(viz, dict):
            viz = [viz]
        if not isinstance(viz, list):
            viz = []

        return [
            {
                "use_tool": v.get("use_tool", True) if isinstance(v, dict) else True,
                "tool_name": v.get("tool_name", "code_executor") if isinstance(v, dict) else "code_executor",
                "tool_description": v.get("tool_description", "") if isinstance(v, dict) else "",
            }
            for v in viz
        ]

    async def _judge_visualizations(
        self,
        visualization_plan: List[Dict[str, Any]],
        generated_charts: List[Path],
        context: ExperimentContext,
        tool_results: Dict[str, Any],
        error_logs: Optional[List[str]] = None,
        data_summary: Optional[DataSummary] = None,
    ) -> VisualizationJudgment:
        """判断可视化结果是否充分。"""
        chart_names = [p.name for p in generated_charts]
        errors_block = ""
        if error_logs:
            errors_block = "\n**Execution Errors**:\n" + "\n".join(f"- {e}" for e in error_logs)

        # 数据摘要
        data_block = ""
        if data_summary:
            total_rows = sum(data_summary.row_counts.values())
            non_empty = [t for t in data_summary.tables if data_summary.row_counts.get(t, 0) > 0]
            data_block = f"""
**Actual Data Context**:
- Tables with data: {non_empty}
- Total rows: {total_rows}
- Empty tables: {[t for t in data_summary.tables if data_summary.row_counts.get(t, 0) == 0]}
"""

        prompt = f"""Evaluate the visualization output for experiment {context.experiment_id}.

**Hypothesis**: {context.design.hypothesis}
**Visualization plan**: {len(visualization_plan)} items
**Generated charts**: {chart_names}{errors_block}{data_block}

**CRITICAL CHECKS**:
1. **Relevance**: Charts relevant to hypothesis?
2. **Data Alignment**: Charts based on ACTUAL data (not hypothetical)?
3. **Adequacy**: Sufficient for report given data available?
4. **Failure Handling**: If key tables empty, are diagnostic charts generated?
5. **Quality**: Any failures that need retry?

{judgment_prompt()}"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        return parse_llm_xml_to_model(content, VisualizationJudgment, root_tag="judgment")

    async def _generate_visualizations(
        self,
        visualization_plan: List[Dict[str, Any]],
        db_path: Path,
        output_dir: Path,
        tool_executor: AnalysisRunner,
        on_progress: AnalysisProgressCallback = None,
    ) -> Tuple[List[Path], List[str]]:
        """执行可视化生成。"""

        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        generated_charts: List[Path] = []
        error_logs: List[str] = []

        if not visualization_plan:
            return generated_charts, error_logs

        total = sum(1 for v in visualization_plan if v.get("use_tool") or v.get("tool_name"))
        done = 0

        for viz in visualization_plan:
            if not viz.get("use_tool") and not viz.get("tool_name"):
                continue
            done += 1
            await progress(f"Generating chart {done}/{total}..." if total > 1 else "Generating chart...")

            tool_description = viz.get("tool_description") or viz.get("description") or ""
            if not tool_description:
                continue

            result = await tool_executor.execute_tool(
                tool_name=viz.get("tool_name", "code_executor"),
                tool_type="code_executor",
                parameters={
                    "db_path": str(db_path),
                    "code_description": tool_description,
                    "extra_files": collect_experiment_files(db_path),
                },
            )

            if not result.get("success"):
                error_msg = result.get("error", "unknown")
                self.logger.warning("工具执行失败: %s", error_msg)
                error_logs.append(f"Chart {done} failed: {error_msg}")
                continue

            generated_charts.extend(self._collect_generated_chart_paths(result, output_dir))

        return generated_charts, error_logs

    def _collect_generated_chart_paths(self, tool_result: Dict[str, Any], output_dir: Path) -> List[Path]:
        """收集工具产出的图表文件。"""
        chart_paths: List[Path] = []
        for artifact_path_str in tool_result.get("artifacts", []):
            artifact_path = Path(artifact_path_str)
            if not artifact_path.exists() or not artifact_path.is_file():
                continue
            if artifact_path.suffix.lower() not in SUPPORTED_ASSET_FORMATS:
                continue
            dest_path = output_dir / artifact_path.name
            if artifact_path.resolve() != dest_path.resolve():
                shutil.copy2(artifact_path, dest_path)
            chart_paths.append(dest_path)
        return chart_paths

    def _format_tools_list(self, tools: Dict[str, Dict[str, Any]]) -> str:
        """格式化工具列表。"""
        if not tools:
            return "No built-in tools available"
        file_order = ["read_file", "write_file", "list_directory", "glob", "search_file_content"]
        entries = []
        for name, info in tools.items():
            desc = info.get("description", "No description")
            params = info.get("parameters_description") or info.get("parameters")
            if params is not None and not isinstance(params, str):
                params = ", ".join(str(p) for p in params)
            line = f"- **{name}**: {desc}" + (f" Parameters: {params}" if params else "")
            entries.append((file_order.index(name) if name in file_order else 999, line))
        entries.sort(key=lambda x: x[0])
        return "\n".join(e[1] for e in entries)

    def _format_tool_results(self, tool_results: Dict[str, Any], max_length: int = 2000) -> str:
        """格式化工具执行结果。注意：这是格式化方法，总结由 _summarize_tool_results 负责。"""
        if not tool_results:
            return "No tool execution results"
        lines = []
        for name, result in tool_results.items():
            success = result.get("success", False)
            lines.append(f"\n**{name}**: {'✅ Success' if success else '❌ Failed'}")
            if success:
                if "path" in result:
                    lines.append(f"Output: {result['path']}")
                elif "stdout" in result:
                    stdout = result['stdout']
                    # 保留较长输出，后续由 LLM 总结
                    if len(stdout) > 800:
                        stdout = stdout[:800] + f"...[+{len(result['stdout'])-800} chars]"
                    lines.append(f"Output: {stdout}")
            else:
                error = result.get('error', 'Unknown')
                if len(error) > 500:
                    error = error[:500] + "...[more]"
                lines.append(f"Error: {error}")
        result_str = "\n".join(lines) if lines else "No results"
        if len(result_str) > max_length:
            result_str = result_str[:max_length] + "\n...[see summary for key findings]"
        return result_str

    async def _summarize_tool_results(
        self,
        tool_results: Dict[str, Any],
        previous_insights: List[str],
    ) -> str:
        """
        使用 LLM 总结工具执行结果的关键发现。

        将长输出压缩为有意义的摘要，而非简单截断。
        """
        if not tool_results:
            return "No results to summarize."

        # 构建结果概览
        results_overview = []
        for name, result in tool_results.items():
            if result.get("success"):
                if "path" in result:
                    results_overview.append(f"- {name}: Generated {result['path']}")
                elif "stdout" in result:
                    # 取输出的关键部分
                    stdout = result['stdout']
                    results_overview.append(f"- {name}: {len(stdout)} chars output")
            else:
                results_overview.append(f"- {name}: FAILED - {str(result.get('error', ''))[:100]}")

        prompt = f"""Summarize the key findings from these tool execution results.

**Results Overview**:
{chr(10).join(results_overview)}

**Previous Insights**:
{chr(10).join([f"- {i[:150]}" for i in previous_insights[:3]]) if previous_insights else "None yet"}

Provide a concise summary (2-3 sentences) of what was discovered or accomplished.
Focus on actionable findings, not just listing what ran.

Return ONLY the summary text, no XML needed."""

        try:
            response = await self.llm_router.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            self.logger.warning("工具结果总结失败: %s", e)
            return "; ".join(results_overview[:5])

    async def _summarize_document(
        self,
        document: str,
        document_type: str,
        max_length: int = 500,
    ) -> str:
        """
        使用 LLM 总结长文档。

        Args:
            document: 原始文档内容
            document_type: 文档类型（如 "hypothesis", "experiment", "literature"）
            max_length: 目标最大长度

        Returns:
            总结后的文档
        """
        if not document or len(document) <= max_length:
            return document or ""

        prompt = f"""Summarize this {document_type} document concisely.

Keep the key points, main arguments, and critical details.
Target length: around {max_length} characters.

**Document**:
{document[:3000]}

Return ONLY the summary, no additional text."""

        try:
            response = await self.llm_router.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            summary = (response.choices[0].message.content or "").strip()
            self.logger.info(
                "文档总结: %s (%d -> %d chars)",
                document_type,
                len(document),
                len(summary),
            )
            return summary
        except Exception as e:
            self.logger.warning("文档总结失败 (%s): %s", document_type, e)
            # 回退到截断
            return document[:max_length] + "...[summary failed]"

    async def _summarize_schema(
        self,
        schema_markdown: str,
        row_counts: Dict[str, int],
        max_tables: int = 10,
    ) -> str:
        """
        使用 LLM 总结数据库 schema，提取关键信息。

        对于大型 schema，提取最相关的表和列。
        """
        if not schema_markdown:
            return "(no schema)"

        # 如果 schema 不长，直接返回
        if len(schema_markdown) <= 2000:
            return schema_markdown

        # 提取关键表（有数据的表优先）
        tables_with_data = [
            (t, c) for t, c in row_counts.items() if c > 0
        ]
        tables_sorted = sorted(tables_with_data, key=lambda x: -x[1])[:max_tables]

        key_tables_info = "\n".join([
            f"- {t}: {c} rows" for t, c in tables_sorted
        ])

        prompt = f"""Summarize this database schema for analysis purposes.

**Total tables**: {len(row_counts)}
**Tables with data**: {len(tables_with_data)}

**Key tables (by row count)**:
{key_tables_info}

**Full schema** (may be truncated):
{schema_markdown[:3000]}

Provide a concise schema summary that includes:
1. Most important tables and their purposes
2. Key columns in each important table
3. Any notable relationships or patterns

Keep it under 1500 characters. Return ONLY the summary."""

        try:
            response = await self.llm_router.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            summary = (response.choices[0].message.content or "").strip()
            self.logger.info(
                "Schema 总结: %d -> %d chars",
                len(schema_markdown),
                len(summary),
            )
            return summary
        except Exception as e:
            self.logger.warning("Schema 总结失败: %s", e)
            # 回退：返回关键表信息
            return f"Key tables:\n{key_tables_info}\n\n[Schema summary failed, original truncated]\n{schema_markdown[:1500]}"

    async def _summarize_context(
        self,
        conversation_history: List[Dict[str, Any]],
        current_results: Dict[str, Any],
        iteration: int,
    ) -> ContextSummary:
        """
        使用 LLM 压缩历史上下文为结构化摘要。

        当上下文过长时，用 LLM 提取关键信息，避免上下文膨胀。
        """
        # 仅当本轮尚未执行任何工具时跳过 LLM：只要跑过工具，就必须压缩一轮，
        # 把成功/失败与错误信号写进 ContextSummary，供下一轮 _adjust 使用。
        if not conversation_history:
            return ContextSummary(
                key_findings=[],
                failed_attempts=[],
                successful_tools=[],
                recommendations="",
                iteration_count=iteration,
            )

        # 构建历史摘要
        history_text = "\n".join([
            f"- Iter {h['iteration']}: {h['tool']} - {'OK' if h.get('result', {}).get('success') else 'FAILED'}"
            for h in conversation_history[-10:]  # 最多取最近10条
        ])

        # 提取关键输出
        outputs_text = ""
        for name, result in list(current_results.items())[-3:]:  # 最近3个结果
            if result.get("success") and result.get("stdout"):
                outputs_text += f"\n**{name}**: {result['stdout'][:300]}...\n"
            elif not result.get("success"):
                outputs_text += f"\n**{name}** FAILED: {str(result.get('error', ''))[:200]}\n"

        prompt = f"""Summarize the analysis execution history into a structured summary.

**Iteration**: {iteration}
**History**:
{history_text}

**Recent outputs**:
{outputs_text}

Extract:
1. key_findings: Important discoveries from tool outputs (max 3 items)
2. failed_attempts: Tools that failed and why (max 2 items)
3. successful_tools: Tools that completed successfully
4. recommendations: What to do next or what was learned

{summary_xml_contract()}"""

        try:
            response = await self.llm_router.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            data = parse_llm_xml_response(content, root_tag="summary")

            def _list(v: Any) -> List[str]:
                if isinstance(v, list):
                    return [str(i) for i in v[:3]]
                if isinstance(v, dict) and "item" in v:
                    items = v["item"]
                    return [str(i) for i in (items if isinstance(items, list) else [items])[:3]]
                return []

            return ContextSummary(
                key_findings=_list(data.get("key_findings", [])),
                failed_attempts=_list(data.get("failed_attempts", [])),
                successful_tools=_list(data.get("successful_tools", [])),
                recommendations=str(data.get("recommendations", "")),
                iteration_count=iteration,
            )
        except Exception as e:
            self.logger.warning("上下文摘要失败: %s", e)
            return ContextSummary(
                key_findings=[],
                failed_attempts=[],
                successful_tools=[h["tool"] for h in conversation_history if h.get("result", {}).get("success")],
                recommendations="",
                iteration_count=iteration,
            )

    def _format_context_summary(self, summary: ContextSummary) -> str:
        """将上下文摘要格式化为 prompt 友好的文本。"""
        lines = [f"**Iteration {summary.iteration_count} Summary**:"]

        if summary.key_findings:
            lines.append("Key findings:")
            for f in summary.key_findings[:3]:
                lines.append(f"  - {f}")

        if summary.failed_attempts:
            lines.append("Failed attempts:")
            for f in summary.failed_attempts[:2]:
                lines.append(f"  - {f}")

        if summary.successful_tools:
            lines.append(f"Successful tools: {', '.join(summary.successful_tools[:5])}")

        if summary.recommendations:
            lines.append(f"Recommendations: {summary.recommendations}")

        return "\n".join(lines)

    async def close(self) -> None:
        """关闭智能体"""
        pass    