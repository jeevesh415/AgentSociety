"""
报告生成器

使用 LLM 生成报告，完全自主决定格式、结构和样式。
"""

import base64
import json
import mimetypes
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from agentsociety2.logger import get_logger
from litellm import AllMessageValues
from pydantic import BaseModel

from .models import (
    ExperimentContext,
    AnalysisResult,
    ReportContent,
    ReportAsset,
    SUPPORTED_IMAGE_FORMATS,
)
from .analysis_agent import AnalysisAgent
from .utils import parse_llm_json_to_model, get_analysis_skills, AnalysisProgressCallback


class ReportGenerationResult(BaseModel):
    """报告生成结果判断"""

    success: bool
    reason: str
    has_markdown: bool
    has_html: bool
    should_retry: bool = False
    retry_instruction: str = ""


class AssetProcessor:
    """发现并处理报告所需的可视化资源（复制/内嵌）。"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.logger = get_logger()

    def discover_assets(self, experiment_id: str, hypothesis_id: str) -> List[ReportAsset]:
        """
        在固定默认路径下发现可视化资源。

        Args:
            experiment_id: 实验ID
            hypothesis_id: 假设ID

        Returns:
            发现到的 ReportAsset 列表
        """
        hypothesis_dir_name = f"hypothesis_{hypothesis_id}"
        experiment_dir_name = f"experiment_{experiment_id}"
        run_dir_name = "run"

        asset_path = (
            self.workspace_path
            / hypothesis_dir_name
            / experiment_dir_name
            / run_dir_name
            / "artifacts"
        )

        assets: list[ReportAsset] = []
        if not asset_path.exists():
            return assets

        for file_path in asset_path.rglob("*"):
            if file_path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
                continue
            assets.append(
                ReportAsset(
                    asset_id=f"viz_{file_path.stem}",
                    asset_type="visualization",
                    title=self._format_title(file_path.stem),
                    file_path=str(file_path),
                    description=f"Generated visualization: {file_path.name}",
                    file_size=file_path.stat().st_size,
                    embedded_content=None,
                )
            )

        return assets

    def process_assets(self, assets: List[ReportAsset], output_dir: Path) -> Dict[str, Any]:
        """
        处理资源并复制到输出目录，同时可选生成可内嵌的 base64 数据。

        Args:
            assets: ReportAsset 列表
            output_dir: 输出目录

        Returns:
            asset_id -> 处理后信息 的字典
        """
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)

        processed_assets: dict[str, Any] = {}

        for asset in assets:
            source_path = Path(asset.file_path)
            if not source_path.exists():
                self.logger.warning(f"Asset not found: {source_path}")
                continue

            dest_path = assets_dir / source_path.name
            src_resolved = source_path.resolve(strict=False)
            dst_resolved = dest_path.resolve(strict=False)
            if src_resolved != dst_resolved:
                shutil.copy2(source_path, dest_path)

            if source_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
                with open(source_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    mime_type, _ = mimetypes.guess_type(source_path.name)
                    if not mime_type:
                        suffix = source_path.suffix.lower()
                        mime_type = f"image/{suffix[1:]}" if suffix.startswith('.') else "application/octet-stream"
                    asset.embedded_content = (
                        f"data:{mime_type};base64,{encoded}"
                    )

            processed_assets[asset.asset_id] = {
                "title": asset.title,
                "local_path": str(dest_path),
                "relative_path": f"assets/{source_path.name}",
                "embedded_data": asset.embedded_content,
                "description": asset.description,
            }

        return processed_assets

    def _format_title(self, filename: str) -> str:
        """将文件名格式化为可读标题。"""
        title = filename.replace("_", " ").replace("-", " ")
        return " ".join(word.capitalize() for word in title.split())


class ReportGenerator:
    """使用 LLM 生成报告，完全自主决定格式、结构和样式。"""

    def __init__(self, agent: AnalysisAgent):
        """
        初始化报告生成器。

        Args:
            agent: AnalysisAgent 实例
        """
        self.logger = get_logger()
        self.agent = agent
        self.logger.info(f"Report generator using model: {self.agent.model_name}")

    async def generate(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        processed_assets: Dict[str, Any],
        output_dir: Path,
        on_progress: AnalysisProgressCallback = None,
    ) -> Tuple[Dict[str, str], bool]:
        """
        生成报告，同时保存 Markdown 和 HTML 格式。
        Returns: (文件路径字典, report_complete 是否成功)
        """
        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            await progress("Generating report content...")
            content = await self._generate_content(
                context, analysis_result, processed_assets
            )
            files: Dict[str, str] = {}
            await progress("Saving report (Markdown & HTML)...")
            md_path = await self._save_markdown(content, output_dir)
            files["markdown"] = str(md_path)
            html_path = await self._save_html(content, output_dir)
            files["html"] = str(html_path)
            judgment = await self._judge_report_generation(content, md_path, html_path)

            if judgment.success:
                files.update(
                    await self._save_supporting_files(
                        context, analysis_result, output_dir
                    )
                )
                return (files, True)

            if not judgment.should_retry or retry_count >= max_retries - 1:
                self.logger.warning(
                    f"Report generation failed: {judgment.reason}. Saving partial results."
                )
                files.update(
                    await self._save_supporting_files(
                        context, analysis_result, output_dir
                    )
                )
                return (files, False)

            retry_count += 1
            self.logger.info(
                f"Retrying report generation ({retry_count}/{max_retries}): {judgment.retry_instruction}"
            )

        files = {}
        files.update(
            await self._save_supporting_files(context, analysis_result, output_dir)
        )
        return (files, False)

    async def _generate_content(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        processed_assets: Dict[str, Any],
    ) -> ReportContent:
        prompt = self._build_prompt(context, analysis_result, processed_assets)
        skills = get_analysis_skills()
        system = (f"{skills}\n\n---\n\nWrite the experiment report. Output: Markdown block between ---MARKDOWN--- and ---END MARKDOWN---, then HTML block between ---HTML--- and ---END HTML---." if skills else "Write the experiment report. Output: ---MARKDOWN--- ... ---END MARKDOWN---, then ---HTML--- ... ---END HTML---.")
        messages: list[AllMessageValues] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        self.logger.info(f"Generating report content with {self.agent.model_name}")

        response = await self.agent.llm_router.acompletion(
            model=self.agent.model_name,
            messages=messages,
            temperature=self.agent.temperature,
        )

        llm_content = response.choices[0].message.content or ""

        return self._parse_content(llm_content, context)

    def _build_prompt(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        processed_assets: Dict[str, Any],
    ) -> str:
        status_msg = self._get_status_message(context.execution_status.value)
        viz_info = self._format_viz_info(processed_assets)

        return f"""## Experiment Context

**Experiment ID**: {context.experiment_id}
**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}%
**Status**: {context.execution_status.value}
**Duration**: {f"{context.duration_seconds:.2f}s" if context.duration_seconds else "Not available"}

**Objectives**: {self._format_list(context.design.objectives) if context.design.objectives else "Not specified"}

**Success Criteria**: {self._format_list(context.design.success_criteria) if context.design.success_criteria else "Not specified"}

**Status context**: {status_msg}

## Analysis Results

**Key Insights** ({len(analysis_result.insights)}):
{self._format_list(analysis_result.insights)}

**Findings** ({len(analysis_result.findings)}):
{self._format_list(analysis_result.findings)}

**Conclusions**:
{analysis_result.conclusions}

**Recommendations** ({len(analysis_result.recommendations)}):
{self._format_list(analysis_result.recommendations)}

**Visualizations**:
{viz_info}

---

Output: first a Markdown block (---MARKDOWN--- ... ---END MARKDOWN---), then an HTML block (---HTML--- ... ---END HTML---)."""

    def _parse_content(
        self,
        content: str,
        context: ExperimentContext,
    ) -> ReportContent:
        """按 ---MARKDOWN--- / ---HTML--- 分隔符提取内容。"""
        raw = (content or "").strip()
        title = f"Analysis: {context.design.hypothesis}"
        subtitle = f"Experiment {context.experiment_id}"
        markdown_content = None
        html_content = None
        if "---MARKDOWN---" in raw and "---END MARKDOWN---" in raw:
            i0 = raw.index("---MARKDOWN---") + len("---MARKDOWN---")
            i1 = raw.index("---END MARKDOWN---")
            markdown_content = raw[i0:i1].strip()
        if "---HTML---" in raw and "---END HTML---" in raw:
            i0 = raw.index("---HTML---") + len("---HTML---")
            i1 = raw.index("---END HTML---")
            html_content = raw[i0:i1].strip()
        if not markdown_content and raw:
            markdown_content = raw
        return ReportContent(
            title=title,
            subtitle=subtitle,
            format_preference="both",
            full_content_markdown=markdown_content,
            full_content_html=html_content,
        )

    async def _judge_report_generation(
        self,
        content: ReportContent,
        md_path: Path,
        html_path: Path,
    ) -> ReportGenerationResult:
        md_exists = md_path.exists() and md_path.stat().st_size > 0
        html_exists = html_path.exists() and html_path.stat().st_size > 0
        has_markdown_content = bool(
            content.full_content_markdown and content.full_content_markdown.strip()
        )
        has_html_content = bool(
            content.full_content_html and content.full_content_html.strip()
        )

        report_summary = f"""## Report Generation Result

**Markdown Report**:
- File exists: {md_exists}
- Has content: {has_markdown_content}
- File size: {md_path.stat().st_size if md_exists else 0} bytes

**HTML Report**:
- File exists: {html_exists}
- Has content: {has_html_content}
- File size: {html_path.stat().st_size if html_exists else 0} bytes

**Content Preview**:
- Markdown length: {len(content.full_content_markdown) if content.full_content_markdown else 0} characters
- HTML length: {len(content.full_content_html) if content.full_content_html else 0} characters

You should analyze the report generation result and determine:
1. Are both Markdown and HTML reports generated successfully?
2. Do the reports have meaningful content?
3. Are the files saved correctly?
4. Is the task completed successfully?

Respond in JSON format:
```json
{{
    "success": true/false,
    "reason": "brief explanation",
    "has_markdown": true/false,
    "has_html": true/false,
    "should_retry": true/false,
    "retry_instruction": "what to fix if should_retry is true"
}}
```"""

        messages: list[AllMessageValues] = [
            {"role": "user", "content": report_summary}
        ]

        response = await self.agent.llm_router.acompletion(
            model=self.agent.model_name,
            messages=messages,
            temperature=self.agent.temperature,
        )

        response_content = response.choices[0].message.content
        if not response_content:
            return ReportGenerationResult(
                success=False,
                reason="LLM returned empty response",
                has_markdown=has_markdown_content,
                has_html=has_html_content,
                should_retry=True,
                retry_instruction="Regenerate report with complete content",
            )

        return parse_llm_json_to_model(response_content, ReportGenerationResult)

    async def _save_markdown(
        self,
        content: ReportContent,
        output_dir: Path,
    ) -> Path:
        """
        保存 Markdown 报告。

        Args:
            content: ReportContent 对象
            output_dir: 输出目录

        Returns:
            保存的 Markdown 文件路径
        """
        md_file = output_dir / "analysis_report.md"
        md_content = content.full_content_markdown or ""
        md_file.write_text(md_content, encoding="utf-8")
        self.logger.info(f"Saved markdown report: {md_file}")
        return md_file

    async def _save_html(
        self,
        content: ReportContent,
        output_dir: Path,
    ) -> Path:
        """
        保存 HTML 报告。

        Args:
            content: ReportContent 对象
            output_dir: 输出目录

        Returns:
            保存的 HTML 文件路径
        """
        html_file = output_dir / "analysis_report.html"
        html_content = content.full_content_html or ""
        html_file.write_text(html_content, encoding="utf-8")
        self.logger.info(f"Saved HTML report: {html_file}")
        return html_file

    async def _save_supporting_files(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        output_dir: Path,
    ) -> Dict[str, str]:
        """
        保存文件。

        Args:
            context: 实验上下文
            analysis_result: 分析结果
            output_dir: 输出目录

        Returns:
            文件路径字典
        """
        files = {}

        data_dir = output_dir / "data"
        data_dir.mkdir(exist_ok=True)

        result_file = data_dir / "analysis_result.json"
        result_file.write_text(
            json.dumps(analysis_result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        files["result_data"] = str(result_file)

        readme_file = output_dir / "README.md"
        readme_content = f"""# Experiment Analysis Results

**Experiment ID:** {context.experiment_id}  
**Hypothesis ID:** {context.hypothesis_id}  
**Generated:** {analysis_result.generated_at.strftime("%Y-%m-%d %H:%M:%S")}

## Files

- `analysis_report.md` - Markdown report
- `analysis_report.html` - HTML report
- `data/analysis_result.json` - Raw analysis data
"""
        readme_file.write_text(readme_content, encoding="utf-8")
        files["readme"] = str(readme_file)

        return files

    def _format_list(self, items: list) -> str:
        """
        格式化列表用于提示词。

        Args:
            items: 要格式化的项目列表

        Returns:
            格式化的 Markdown 列表字符串
        """
        return "\n".join([f"- {item}" for item in items]) if items else "None"

    def _format_viz_info(self, processed_assets: Dict[str, Any]) -> str:
        if not processed_assets:
            return "No visualizations available."

        lines = [f"Available visualizations ({len(processed_assets)}):"]
        for asset_id, asset_data in processed_assets.items():
            title = asset_data.get("title", asset_id)
            desc = asset_data.get("description", "Generated visualization")
            lines.append(f"- {title}: {desc}")
            if asset_data.get("embedded_data"):
                lines.append("  (Base64 image data available)")
            elif asset_data.get("relative_path"):
                lines.append(f"  (Path: {asset_data['relative_path']})")

        return "\n".join(lines)

    def _get_status_message(self, status: str) -> str:
        messages = {
            "success": "Experiment completed successfully. Focus on positive outcomes.",
            "partial_success": "Partial success. Discuss achievements and limitations.",
            "failure": "Experiment did not meet criteria. Analyze what went wrong.",
        }
        return messages.get(
            status, "Status uncertain. Present findings with limitations."
        )
