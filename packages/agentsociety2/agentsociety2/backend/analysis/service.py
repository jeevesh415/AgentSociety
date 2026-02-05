"""分析服务 - 协调整个分析工作流的主服务。"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model

from .models import (
    ExperimentContext,
    ExperimentDesign,
    ExperimentStatus,
    AnalysisConfig,
    AnalysisResult,
    ExperimentSynthesis,
    HypothesisSummary,
    ReportAsset,
)
from .analysis_agent import AnalysisAgent
from .report_generator import ReportGenerator, AssetProcessor
from .utils import parse_llm_json_response



class AnalysisService:
    """使用基于代理架构的主分析服务。"""
    
    def __init__(self, config: AnalysisConfig):
        """
        初始化分析服务。
        
        Args:
            config: 分析配置
        """
        self.logger = get_logger()
        self.workspace_path = Path(config.workspace_path).resolve()
        self.presentation_path = self.workspace_path / "presentation"
        self.presentation_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Analysis service initialized")
        self.logger.info(f"  Workspace: {self.workspace_path}")
        self.logger.info(f"  Presentation: {self.presentation_path}")
        
        self.agent = AnalysisAgent(temperature=0.7)
        self.logger.info(f"Analysis agent initialized with model: {self.agent.model_name}")
        
        self.asset_processor = AssetProcessor(self.workspace_path)
    
    def _find_database_path(self, hypothesis_id: str, experiment_id: str) -> Optional[Path]:
        """
        查找数据库路径。
        
        Args:
            hypothesis_id: 假设标识符
            experiment_id: 实验标识符
            
        Returns:
            数据库路径，如果未找到则返回 None
        """
        run_path = (
            self.workspace_path 
            / f"hypothesis_{hypothesis_id}" 
            / f"experiment_{experiment_id}" 
            / "run"
        )
        
        db_path = run_path / "sqlite.db"
        
        if db_path.exists():
            self.logger.info(f"Found database at: {db_path}")
            return db_path
        
        self.logger.warning(f"Database not found for hypothesis_{hypothesis_id}/experiment_{experiment_id}")
        return None
    
    async def analyze(
        self,
        hypothesis_id: str,
        experiment_id: str,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        分析实验。
        
        Args:
            hypothesis_id: 假设标识符
            experiment_id: 实验标识符
            custom_instructions: 可选的定制分析指令
            
        Returns:
            包含分析结果和生成文件的字典
        """
        self.logger.info(f"Starting analysis for experiment {experiment_id}")
        
        context = await self._load_context(hypothesis_id, experiment_id)
        analysis_result = await self.agent.analyze(context, custom_instructions)
        
        assets = self.asset_processor.discover_assets(experiment_id, hypothesis_id)
        
        output_dir = self.presentation_path / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        
        db_path = self._find_database_path(hypothesis_id, experiment_id)

        if db_path:
            from .data_analysis_agent import DataAnalysisAgent

            data_agent = DataAnalysisAgent(
                llm_router=self.agent.llm_router,

                model_name=self.agent.model_name,
                temperature=self.agent.temperature,
                workspace_path=self.workspace_path,
            )
            
            try:
                data_analysis_result = await data_agent.analyze_data(
                    context, analysis_result, db_path, assets_dir
                )
                
                for chart_path in data_analysis_result.get("generated_charts", []):
                    asset = ReportAsset(
                        asset_id=f"gen_{chart_path.stem}",
                        asset_type="visualization",
                        title=chart_path.stem.replace('_', ' ').title(),
                        file_path=str(chart_path),
                        description=f"Autonomously generated visualization: {chart_path.name}",
                        file_size=chart_path.stat().st_size,
                        embedded_content=None
                    )
                    assets.append(asset)
                
                self.logger.info(f"Data analysis completed: {len(data_analysis_result.get('generated_charts', []))} charts generated")
                
            finally:
                await data_agent.close()
        
        processed_assets = self.asset_processor.process_assets(assets, output_dir)
        
        report_generator = ReportGenerator(agent=self.agent)
        
        generated_files = await report_generator.generate(
            context=context,
            analysis_result=analysis_result,
            processed_assets=processed_assets,
            output_dir=output_dir,
        )
        
        return {
            "success": True,
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis_id,
            "analysis_result": analysis_result,
            "generated_files": generated_files,
            "output_directory": str(output_dir),
            "execution_status": context.execution_status,
            "completion_percentage": context.completion_percentage,
            "error_messages": context.error_messages,
        }

    async def _load_context(
        self,
        hypothesis_id: str,
        experiment_id: str,
    ) -> ExperimentContext:
        """从文件和数据库加载实验上下文。"""
        hypothesis_base = self.workspace_path / f"hypothesis_{hypothesis_id}"
        experiment_path = hypothesis_base / f"experiment_{experiment_id}"
        if not experiment_path.exists():
            raise ValueError(f"Experiment path not found for experiment {experiment_id} in hypothesis {hypothesis_id}")
        run_path = experiment_path / "run"
        design = await self._load_design(hypothesis_base, experiment_path, hypothesis_id)
        _, _, duration = await self._load_runtime_info(run_path)
        status, completion, errors = await self._analyze_status(run_path)
        return ExperimentContext(
            experiment_id=experiment_id,
            hypothesis_id=hypothesis_id,
            design=design,
            duration_seconds=duration,
            execution_status=status,
            completion_percentage=completion,
            error_messages=errors,
        )

    async def _load_design(
        self,
        hypothesis_base: Path,
        experiment_path: Path,
        hypothesis_id: str,
    ) -> ExperimentDesign:
        """从 Markdown 文件加载实验设计。

        不再通过 LLM 解析 Markdown 为结构化字段，只读取原始 Markdown 文本，
        """
        design_data: Dict[str, Any] = {
            "hypothesis": "Hypothesis not specified",
            "objectives": [],
            "variables": {},
            "methodology": "",
            "success_criteria": [],
            "hypothesis_markdown": None,
            "experiment_markdown": None,
        }
        hypothesis_md_path = hypothesis_base / "HYPOTHESIS.md"
        if hypothesis_md_path.exists():
            content = hypothesis_md_path.read_text(encoding='utf-8')
            design_data["hypothesis_markdown"] = content
            first_non_empty = next(
                (line.strip() for line in content.splitlines() if line.strip()),
                "",
            )
            if first_non_empty:
                design_data["hypothesis"] = first_non_empty[:300]
            self.logger.info(f"Loaded hypothesis from: {hypothesis_md_path}")
        else:
            self.logger.warning(f"Hypothesis file not found: {hypothesis_md_path}")
        experiment_md_path = experiment_path / "EXPERIMENT.md"
        if experiment_md_path.exists():
            content = experiment_md_path.read_text(encoding='utf-8')
            design_data["experiment_markdown"] = content
            self.logger.info(f"Loaded experiment design from: {experiment_md_path}")
        return ExperimentDesign(
            hypothesis=design_data.get("hypothesis", "Hypothesis not specified"),
            objectives=design_data.get("objectives", []),
            variables=design_data.get("variables", {}),
            methodology=design_data.get("methodology", ""),
            success_criteria=design_data.get("success_criteria", []),
            hypothesis_markdown=design_data.get("hypothesis_markdown"),
            experiment_markdown=design_data.get("experiment_markdown"),
        )

    async def _load_runtime_info(
        self,
        run_path: Path,
    ) -> Tuple[Optional[datetime], Optional[datetime], Optional[float]]:
        """从数据库加载运行时信息。"""
        return None, None, None

    async def _analyze_status(
        self,
        run_path: Path,
    ) -> Tuple[ExperimentStatus, float, list[str]]:
        """
        读取实验状态和完成度。

        """
        db_path = run_path / "sqlite.db"
        if not db_path.exists():
            return ExperimentStatus.FAILED, 0.0, ["Database file not found"]
        return ExperimentStatus.UNKNOWN, 0.0, []


class ExperimentSynthesizer:
    """多假设/多实验综合器：复用 `AnalysisService.analyze`，再用 LLM 做跨实验对比总结。"""

    def __init__(self, workspace_path: str, llm_temperature: float = 0.7):
        self.logger = get_logger()
        self.workspace_path = Path(workspace_path).resolve()
        self.temperature = llm_temperature

        self.llm_router, self.model_name = get_llm_router_and_model("default")
        self.agent = AnalysisAgent(
            llm_router=self.llm_router,
            model_name=self.model_name,
            temperature=llm_temperature,
        )

    def _discover_hypotheses(self) -> list[str]:
        """自动发现工作区下的 hypothesis 目录。"""
        ids: list[str] = []
        for p in self.workspace_path.iterdir():
            if not p.is_dir():
                continue
            if not p.name.startswith("hypothesis_"):
                continue
            parts = p.name.split("_", 1)
            if len(parts) == 2 and parts[1]:
                ids.append(parts[1])
        return sorted(set(ids))

    def _discover_experiments(self, hypothesis_id: str) -> list[str]:
        """自动发现某个 hypothesis 下的 experiment 目录。"""
        hyp_path = self.workspace_path / f"hypothesis_{hypothesis_id}"
        if not hyp_path.exists():
            return []
        ids: list[str] = []
        for p in hyp_path.iterdir():
            if not p.is_dir():
                continue
            if not p.name.startswith("experiment_"):
                continue
            parts = p.name.split("_", 1)
            if len(parts) == 2 and parts[1]:
                ids.append(parts[1])
        return sorted(set(ids))

    async def _get_hypothesis_text(self, hypothesis_id: str) -> str:
        """从 `HYPOTHESIS.md` 抽取一段最关键的假设描述（用于综合提示词）。"""
        hyp_file = self.workspace_path / f"hypothesis_{hypothesis_id}" / "HYPOTHESIS.md"
        if not hyp_file.exists():
            return f"Hypothesis {hypothesis_id}"
        content = hyp_file.read_text(encoding="utf-8")

        for line in content.splitlines():
            if "hypothesis" in line.lower():
                line = line.strip()
                if line:
                    return line[:200]
        return content.strip()[:200] or f"Hypothesis {hypothesis_id}"

    async def _analyze_hypothesis(
        self,
        hypothesis_id: str,
        experiment_ids: Optional[list[str]],
        custom_instructions: Optional[str],
        service: AnalysisService,
    ) -> HypothesisSummary:
        """分析一个 hypothesis 下的一组 experiments，并聚合出 summary。"""
        exp_ids = experiment_ids or self._discover_experiments(hypothesis_id)
        if not exp_ids:
            return HypothesisSummary(
                hypothesis_id=hypothesis_id,
                hypothesis_text=await self._get_hypothesis_text(hypothesis_id),
                experiment_count=0,
            )

        experiment_results: list[dict[str, Any]] = []
        successful_count = 0
        total_completion = 0.0
        all_insights: list[str] = []
        all_findings: list[str] = []

        for exp_id in exp_ids:
            result = await service.analyze(
                hypothesis_id=hypothesis_id,
                experiment_id=exp_id,
                custom_instructions=custom_instructions,
            )

            if not result.get("success"):
                experiment_results.append(
                    {
                        "experiment_id": exp_id,
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
                )
                continue

            completion = float(result.get("completion_percentage", 0.0) or 0.0)
            analysis_result: AnalysisResult = result["analysis_result"]
            experiment_results.append(
                {
                    "experiment_id": exp_id,
                    "success": True,
                    "completion": completion,
                    "insights": analysis_result.insights,
                    "findings": analysis_result.findings,
                    "output_directory": result.get("output_directory", ""),
                    "generated_files": result.get("generated_files", {}),
                }
            )

            # 与旧逻辑一致：completion >= 70 视作成功
            if completion >= 70.0:
                successful_count += 1
            total_completion += completion
            all_insights.extend(analysis_result.insights)
            all_findings.extend(analysis_result.findings)

        avg_completion = total_completion / len(exp_ids) if exp_ids else 0.0
        return HypothesisSummary(
            hypothesis_id=hypothesis_id,
            hypothesis_text=await self._get_hypothesis_text(hypothesis_id),
            experiment_count=len(exp_ids),
            successful_experiments=successful_count,
            total_completion=avg_completion,
            key_insights=all_insights[:10],
            main_findings=all_findings[:10],
            experiment_results=experiment_results,
        )

    async def _perform_synthesis(
        self,
        hypothesis_summaries: list[HypothesisSummary],
        custom_instructions: Optional[str],
    ) -> ExperimentSynthesis:
        """让 LLM 基于各 hypothesis summary 做跨假设综合。"""
        synthesis_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        summaries_text = "\n\n".join(
            [
                (
                    f"Hypothesis {i + 1} (ID: {s.hypothesis_id})\n"
                    f"- Hypothesis text: {s.hypothesis_text}\n"
                    f"- Experiments: {s.experiment_count}\n"
                    f"- Successful experiments: {s.successful_experiments}\n"
                    f"- Average completion: {s.total_completion:.1f}%\n"
                    f"- Key insights: {', '.join(s.key_insights[:5])}\n"
                    f"- Main findings: {', '.join(s.main_findings[:5])}\n"
                )
                for i, s in enumerate(hypothesis_summaries)
            ]
        )

        instruction_block = (
            f"\nCustom instructions:\n{custom_instructions}\n"
            if custom_instructions
            else ""
        )

        prompt = f"""You are performing a cross-hypothesis synthesis of multiple experiment analyses.
You are given aggregated summaries for each hypothesis. Your goal is to compare them and produce an overall synthesis.

{instruction_block}

Hypothesis summaries:
{summaries_text}

Return a JSON object with the following fields:
- synthesis_strategy: string (how you approached the synthesis)
- cross_hypothesis_analysis: string (overall comparative narrative)
- comparative_insights: array of strings (bullet-like insights)
- unified_conclusions: string
- recommendations: array of strings
- best_hypothesis: string or null (hypothesis_id)
- best_hypothesis_reason: string
- overall_assessment: string

Return only JSON, no extra text."""

        response = await self.agent.llm_router.acompletion(
            model=self.agent.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )

        content = (response.choices[0].message.content or "").strip()
        data = parse_llm_json_response(content)

        return ExperimentSynthesis(
            synthesis_id=synthesis_id,
            workspace_path=str(self.workspace_path),
            hypothesis_summaries=hypothesis_summaries,
            synthesis_strategy=str(data.get("synthesis_strategy", "")),
            cross_hypothesis_analysis=str(data.get("cross_hypothesis_analysis", "")),
            comparative_insights=list(data.get("comparative_insights", []) or []),
            unified_conclusions=str(data.get("unified_conclusions", "")),
            recommendations=list(data.get("recommendations", []) or []),
            best_hypothesis=data.get("best_hypothesis"),
            best_hypothesis_reason=str(data.get("best_hypothesis_reason", "")),
            overall_assessment=str(data.get("overall_assessment", "")),
        )

    async def _generate_synthesis_report(self, synthesis: ExperimentSynthesis) -> Optional[Path]:
        """把综合结果落盘成 Markdown 报告。"""
        output_dir = self.workspace_path / "synthesis"
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"synthesis_report_{synthesis.synthesis_id}.md"

        lines: list[str] = []
        lines.append(f"# Experiment Synthesis Report ({synthesis.synthesis_id})")
        lines.append("")
        lines.append(f"- Workspace: `{synthesis.workspace_path}`")
        lines.append(f"- Generated at: {synthesis.synthesis_timestamp.isoformat()}")
        lines.append("")

        if synthesis.best_hypothesis:
            lines.append("## Best Hypothesis")
            lines.append(f"- Hypothesis ID: **{synthesis.best_hypothesis}**")
            if synthesis.best_hypothesis_reason:
                lines.append(f"- Reason: {synthesis.best_hypothesis_reason}")
            lines.append("")

        lines.append("## Cross-hypothesis Analysis")
        lines.append(synthesis.cross_hypothesis_analysis or "")
        lines.append("")

        if synthesis.comparative_insights:
            lines.append("## Comparative Insights")
            for ins in synthesis.comparative_insights:
                lines.append(f"- {ins}")
            lines.append("")

        lines.append("## Unified Conclusions")
        lines.append(synthesis.unified_conclusions or "")
        lines.append("")

        if synthesis.recommendations:
            lines.append("## Recommendations")
            for rec in synthesis.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        lines.append("## Per-hypothesis Summaries")
        for i, summary in enumerate(synthesis.hypothesis_summaries, 1):
            lines.append(f"### Hypothesis {i} (ID: {summary.hypothesis_id})")
            lines.append(f"- Hypothesis text: {summary.hypothesis_text}")
            lines.append(f"- Experiments: {summary.experiment_count}")
            lines.append(f"- Successful experiments: {summary.successful_experiments}")
            lines.append(f"- Average completion: {summary.total_completion:.1f}%")
            if summary.key_insights:
                lines.append("- Key insights:")
                for ins in summary.key_insights[:10]:
                    lines.append(f"  - {ins}")
            if summary.main_findings:
                lines.append("- Main findings:")
                for fnd in summary.main_findings[:10]:
                    lines.append(f"  - {fnd}")
            lines.append("")

        report_file.write_text("\n".join(lines), encoding="utf-8")
        return report_file

    async def synthesize(
        self,
        hypothesis_ids: Optional[list[str]] = None,
        experiment_ids: Optional[list[str]] = None,
        custom_instructions: Optional[str] = None,
    ) -> ExperimentSynthesis:
        """
        执行多假设/多实验综合分析。

        Args:
            hypothesis_ids: 指定 hypothesis_id 列表；不传则自动发现
            experiment_ids: 指定 experiment_id 列表；不传则每个 hypothesis 自动发现
            custom_instructions: 额外定制说明（会传给单实验分析与综合提示词）
        """
        hyp_ids = hypothesis_ids or self._discover_hypotheses()
        if not hyp_ids:
            raise ValueError("No hypotheses found in workspace")

        # 复用同一个 AnalysisService，避免重复初始化
        service = AnalysisService(AnalysisConfig(workspace_path=str(self.workspace_path)))

        summaries: list[HypothesisSummary] = []
        for hid in hyp_ids:
            summaries.append(
                await self._analyze_hypothesis(
                    hypothesis_id=hid,
                    experiment_ids=experiment_ids,
                    custom_instructions=custom_instructions,
                    service=service,
                )
            )

        synthesis = await self._perform_synthesis(summaries, custom_instructions)
        report_path = await self._generate_synthesis_report(synthesis)
        synthesis.synthesis_report_path = str(report_path) if report_path else None
        return synthesis


async def analyze_experiment(
    workspace_path: str,
    hypothesis_id: str,
    experiment_id: str,
    custom_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    实验分析的便捷函数。
    
    Args:
        workspace_path: 工作区目录路径
        hypothesis_id: 假设标识符
        experiment_id: 实验标识符
        custom_instructions: 可选的定制指令
        
    Returns:
        分析结果字典
    """
    from .models import AnalysisConfig
    
    config = AnalysisConfig(workspace_path=workspace_path)
    service = AnalysisService(config)
    
    return await service.analyze(hypothesis_id, experiment_id, custom_instructions)


async def synthesize_experiments(
    workspace_path: str,
    hypothesis_ids: Optional[list[str]] = None,
    experiment_ids: Optional[list[str]] = None,
    custom_instructions: Optional[str] = None,
) -> ExperimentSynthesis:
    """综合分析的便捷函数。"""
    synthesizer = ExperimentSynthesizer(workspace_path=workspace_path)
    return await synthesizer.synthesize(hypothesis_ids, experiment_ids, custom_instructions)
