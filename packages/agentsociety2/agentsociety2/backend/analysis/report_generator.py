"""
报告生成器

使用 LLM 生成报告，完全自主决定格式、结构和样式。
"""

import base64
import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List

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
from .utils import parse_llm_json_to_model


class ReportGenerationResult(BaseModel):
    """报告生成结果判断"""

    success: bool
    reason: str
    has_markdown: bool
    has_html: bool
    should_retry: bool = False
    retry_instruction: str = ""


class AssetProcessor:
    """
    资源处理器：发现/处理/复制报告所需的可视化资源（图片/图表等）。

    说明：
    - 仅负责资源发现与复制/内嵌编码，不负责报告内容生成
    """

    def __init__(self, workspace_path: Path):
        """
        初始化资源处理器。

        Args:
            workspace_path: 工作空间根目录
        """
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
    ) -> Dict[str, str]:
        """
        生成报告，同时保存 Markdown 和 HTML 格式。

        Args:
            context: 实验上下文
            analysis_result: 分析结果
            processed_assets: 处理后的可视化资源
            output_dir: 输出目录

        Returns:
            文件路径字典
        """
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            content = await self._generate_content(
                context, analysis_result, processed_assets
            )

            files = {}
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
                return files

            if not judgment.should_retry or retry_count >= max_retries - 1:
                self.logger.warning(
                    f"Report generation failed: {judgment.reason}. Saving partial results."
                )
                files.update(
                    await self._save_supporting_files(
                        context, analysis_result, output_dir
                    )
                )
                return files

            retry_count += 1
            self.logger.info(
                f"Retrying report generation ({retry_count}/{max_retries}): {judgment.retry_instruction}"
            )

        files.update(
            await self._save_supporting_files(context, analysis_result, output_dir)
        )
        return files

    async def _generate_content(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        processed_assets: Dict[str, Any],
    ) -> ReportContent:
        """
        使用 LLM 生成报告内容。

        Args:
            context: 实验上下文
            analysis_result: 分析结果
            processed_assets: 处理后的可视化资源

        Returns:
            ReportContent 对象
        """
        prompt = self._build_prompt(context, analysis_result, processed_assets)
        messages: list[AllMessageValues] = [{"role": "user", "content": prompt}]

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
        """
        构建 LLM 报告生成提示词。

        Args:
            context: 实验上下文
            analysis_result: 分析结果
            processed_assets: 处理后的可视化资源

        Returns:
            格式化的提示词字符串
        """
        status_msg = self._get_status_message(context.execution_status.value)
        viz_info = self._format_viz_info(processed_assets)

        return f"""You are an expert data analysis report writer. Create a comprehensive, insightful report that effectively communicates the experiment results.

## Experiment Context

**Experiment ID**: {context.experiment_id}
**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}%
**Status**: {context.execution_status.value}
**Duration**: {f"{context.duration_seconds:.2f}s" if context.duration_seconds else "Not available"}

**Objectives**:
{self._format_list(context.design.objectives) if context.design.objectives else "Not specified"}

**Success Criteria**:
{self._format_list(context.design.success_criteria) if context.design.success_criteria else "Not specified"}

**Status Context**: {status_msg}

## Analysis Results

**Key Insights** ({len(analysis_result.insights)}):
{self._format_list(analysis_result.insights)}

**Main Findings** ({len(analysis_result.findings)}):
{self._format_list(analysis_result.findings)}

**Conclusions**:
{analysis_result.conclusions}

**Recommendations** ({len(analysis_result.recommendations)}):
{self._format_list(analysis_result.recommendations)}

**Visualizations**:
{viz_info}

## Your Task

Create a comprehensive report that:
- Addresses the experiment context, key results, analysis, evidence, implications, and next steps
- Is well-structured, professional, and tailored to this specific experiment
- Integrates visualizations naturally within the narrative

## Output Format

You must generate both Markdown and HTML formats:

1. **Markdown Report**: Generate a complete Markdown report first. Use `![title](assets/image.png)` syntax for images.

2. **HTML Report**: Generate a complete, standalone HTML document with:
   - `<!DOCTYPE html>` declaration
   - Complete `<head>` section with `<title>`, `<meta>` tags, and inline CSS in `<style>` tags
   - Full `<body>` content
   - Use `<img src="assets/image.png">` tags for images

Output both formats separately. Start with Markdown, then HTML."""

    def _parse_content(
        self,
        content: str,
        context: ExperimentContext,
    ) -> ReportContent:
        """
        解析 LLM 响应，检测格式并提取内容。

        Args:
            content: LLM 原始响应文本
            context: 实验上下文

        Returns:
            ReportContent 对象
        """
        has_html = "<!DOCTYPE html>" in content or "<html" in content

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if not title_match:
            title_match = re.search(r"<title>(.+?)</title>", content, re.IGNORECASE)
        title = (
            title_match.group(1)
            if title_match
            else f"Analysis: {context.design.hypothesis}"
        )

        subtitle_match = re.search(r"^##\s+(.+)$", content, re.MULTILINE)
        subtitle = (
            subtitle_match.group(1)
            if subtitle_match
            else f"Experiment {context.experiment_id}"
        )

        markdown_content = None
        html_content = None

        if has_html:
            html_match = re.search(
                r"(<!DOCTYPE html>.*?</html>)", content, re.DOTALL | re.IGNORECASE
            )
            if not html_match:
                html_match = re.search(
                    r"(<html.*?</html>)", content, re.DOTALL | re.IGNORECASE
                )

            if html_match:
                html_content = html_match.group(1)
                remaining = content.replace(html_content, "").strip()
                if remaining and not remaining.startswith(("<!DOCTYPE", "<html")):
                    markdown_content = remaining
            else:
                markdown_content = content
        else:
            markdown_content = content

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
        """
        使用 LLM 判断报告生成是否成功。

        Args:
            content: ReportContent 对象
            md_path: Markdown 文件路径
            html_path: HTML 文件路径

        Returns:
            ReportGenerationResult 判断结果
        """
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
        """
        格式化可视化信息用于 LLM 提示词。

        Args:
            processed_assets: 处理后的可视化资源字典

        Returns:
            格式化的字符串
        """
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
        """
        获取状态上下文消息用于提示词。

        Args:
            status: 执行状态字符串

        Returns:
            状态相关的消息
        """
        messages = {
            "success": "Experiment completed successfully. Focus on positive outcomes.",
            "partial_success": "Partial success. Discuss achievements and limitations.",
            "failure": "Experiment did not meet criteria. Analyze what went wrong.",
        }
        return messages.get(
            status, "Status uncertain. Present findings with limitations."
        )
