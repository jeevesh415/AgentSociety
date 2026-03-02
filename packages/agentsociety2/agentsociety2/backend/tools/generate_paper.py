"""Generate Paper 工具

根据分析输出（及可选由 LLM 合成 meta）整理成 metadata 格式，
来调用论文写作服务来生成 PDF。
支持两种 meta 来源：use_synthesis=true 时由 LLM 根据工作区内用户提供的文件内容填写；
否则使用固定映射。

"""

from __future__ import annotations

import json
import re
import json_repair
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.config import get_llm_router_and_model
from agentsociety2.config.config import Config
from agentsociety2.logger import get_logger
from agentsociety2.backend.analysis.utils import parse_llm_json_response

logger = get_logger()

# 与 analysis/models.py 保持一致
SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

def _get_easypaper_url() -> str:
    return Config.EASYPAPER_API_URL


def _build_metadata_from_analysis(
    output_dir: Path,
    hypothesis_id: str,
    experiment_id: str,
) -> Dict[str, Any]:
    """
    从 analysis 输出目录构建 PaperMetaData 形状的 dict。
    """
    title = f"Experiment Report (Hypothesis {hypothesis_id}, Experiment {experiment_id})"
    idea_hypothesis = ""
    method = ""
    data = ""
    experiments = ""
    references: List[str] = []
    figures: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []

    result_file = output_dir / "data" / "analysis_summary.json"
    if result_file.exists():
        try:
            raw = json.loads(result_file.read_text(encoding="utf-8"))
            insights = raw.get("insights") or []
            findings = raw.get("findings") or []
            conclusions = raw.get("conclusions") or ""
            if isinstance(insights, list):
                idea_hypothesis = " ".join(str(x) for x in insights[:3])
            if isinstance(findings, list):
                experiments = "\n".join(str(x) for x in findings)
            if conclusions:
                experiments = (experiments + "\n\nConclusions: " + str(conclusions)).strip()
        except Exception as e:
            logger.warning(f"Failed to read analysis_summary.json: {e}")

    report_md = output_dir / "report.md"
    if report_md.exists():
        try:
            content = report_md.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("# ") and len(line) > 2:
                    title = line.lstrip("# ").strip()
                    break
            if not experiments and content:
                experiments = content[:8000] if len(content) > 8000 else content
            elif content and len(content) <= 8000:
                experiments = content
        except Exception as e:
            logger.warning(f"Failed to read report.md: {e}")

    assets_dir = output_dir / "assets"
    if assets_dir.is_dir():
        for path in sorted(assets_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
                continue
            try:
                rel = path.relative_to(assets_dir)
                rel_posix = rel.as_posix()
            except ValueError:
                rel_posix = path.name
            figures.append({
                "id": f"fig:{path.stem}",
                "caption": path.stem.replace("_", " ").title(),
                "description": f"Figure from analysis: {path.name}",
                "file_path": str((assets_dir / rel_posix).resolve()),
            })

    return {
        "title": title,
        "idea_hypothesis": idea_hypothesis or "Experiment analysis.",
        "method": method or "See experiment design and analysis report.",
        "data": data or "See experiment data and analysis report.",
        "experiments": experiments or "See analysis report.",
        "references": references,
        "figures": figures,
        "tables": tables,
    }


# Placeholder strings that indicate fallback metadata (no real content from TOPIC/HYPOTHESIS)
_GENERIC_IDEA = "Experiment analysis."
_GENERIC_METHOD = "See experiment design and analysis report."
_GENERIC_DATA = "See experiment data and analysis report."
_GENERIC_EXPERIMENTS = "See analysis report."
_MAX_FIELD_CHARS = 4000  # reasonable cap for EasyPaper text fields


def _merge_context_into_metadata(ctx: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """When synthesis fails, merge TOPIC/HYPOTHESIS/report from ctx into metadata so fallback still has real content."""
    topic = (ctx.get("topic") or "").strip()
    hypothesis = (ctx.get("hypothesis") or "").strip()
    report = (ctx.get("analysis_report") or "").strip()
    result_json = (ctx.get("analysis_result_json") or "").strip()

    title = metadata.get("title") or ""
    idea = (metadata.get("idea_hypothesis") or "").strip()
    method = (metadata.get("method") or "").strip()
    data = (metadata.get("data") or "").strip()
    experiments = metadata.get("experiments") or ""

    def _first_line(text: str, max_len: int = 200) -> str:
        line = text.split("\n")[0].strip() if text else ""
        return line[:max_len] if len(line) > max_len else line

    def _truncate(text: str, max_len: int = _MAX_FIELD_CHARS) -> str:
        if not text:
            return ""
        return text[:max_len] + "..." if len(text) > max_len else text

    # Title: prefer first meaningful line from topic, then hypothesis, then report # heading
    if not title or title.startswith("Experiment Report (Hypothesis"):
        if topic:
            title = _first_line(topic, 150)
        if (not title or len(title) < 3) and hypothesis:
            title = _first_line(hypothesis, 150)
        if (not title or len(title) < 3) and report:
            for line in report.split("\n"):
                line = line.strip()
                if line.startswith("# ") and len(line) > 2:
                    title = line.lstrip("# ").strip()[:150]
                    break
        if not title:
            title = metadata.get("title") or "Experiment Report"

    # idea_hypothesis: from TOPIC and HYPOTHESIS when current is generic
    if idea in (_GENERIC_IDEA, "") and (topic or hypothesis):
        parts = []
        if topic:
            parts.append(_truncate(topic, 1200))
        if hypothesis:
            parts.append(_truncate(hypothesis, 1200))
        idea = "\n\n".join(parts) if parts else idea

    # method: from HYPOTHESIS and report when current is generic
    if method in (_GENERIC_METHOD, "") and (hypothesis or report):
        parts = []
        if hypothesis:
            parts.append(_truncate(hypothesis, 2000))
        if report:
            parts.append(_truncate(report, 2000))
        method = "\n\n".join(parts) if parts else method

    # data: from report / analysis_summary when current is generic
    if data in (_GENERIC_DATA, "") and (report or result_json):
        if result_json and result_json.startswith("{"):
            try:
                obj = json.loads(result_json)
                data = _truncate(json.dumps(obj, ensure_ascii=False, indent=0), 2000)
            except Exception:
                data = _truncate(report, 2000) if report else data
        elif report:
            data = _truncate(report, 2000)

    # experiments: keep existing if already substantive; else from report
    if not experiments or experiments.strip() in (_GENERIC_EXPERIMENTS, ""):
        if report:
            experiments = _truncate(report, _MAX_FIELD_CHARS)

    out = dict(metadata)
    out["title"] = title
    out["idea_hypothesis"] = idea or metadata.get("idea_hypothesis")
    out["method"] = method or metadata.get("method")
    out["data"] = data or metadata.get("data")
    out["experiments"] = experiments or metadata.get("experiments")
    return out


def _read_text_safe(path: Path) -> str:
    """Read file content; return empty string if missing or error."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _collect_figure_paths_under(base_dir: Path) -> List[str]:
    """
    Recursively collect image file paths under base_dir (e.g. assets/).
    Returns paths relative to base_dir, e.g. ['fig.png', 'figures/plot.png'].
    """
    out: List[str] = []
    if not base_dir.is_dir():
        return out
    for p in sorted(base_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
            continue
        try:
            rel = p.relative_to(base_dir)
            out.append(str(rel.as_posix()))
        except ValueError:
            continue
    return out


def _gather_synthesis_context(
    workspace_path: Path, hypothesis_id: str, experiment_id: str
) -> Dict[str, Any]:
    """从 workspace 收集 TOPIC、HYPOTHESIS、EXPERIMENT、report、analysis_summary、assets、可选 literature。
    不硬编码绝对路径：TOPIC 在 workspace 根，HYPOTHESIS 在 hypothesis_<id>/，实验材料可在
    presentation/hypothesis_<id>/experiment_<id>/ 或 hypothesis_<id>/experiment_<id>/（后者为 fallback）。
    """
    out: Dict[str, Any] = {
        "topic": "",
        "hypothesis": "",
        "experiment": "",
        "analysis_report": "",
        "analysis_result_json": "",
        "figure_names": [],
        "literature_titles": [],
    }
    # Workspace-level: TOPIC.md
    topic_file = workspace_path / "TOPIC.md"
    out["topic"] = _read_text_safe(topic_file)
    # Hypothesis-level: hypothesis_<id>/HYPOTHESIS.md
    hyp_file = workspace_path / f"hypothesis_{hypothesis_id}" / "HYPOTHESIS.md"
    out["hypothesis"] = _read_text_safe(hyp_file)
    # Experiment-level: EXPERIMENT.md (under hypothesis_<id>/experiment_<id>/)
    exp_dir = workspace_path / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
    exp_file = exp_dir / "EXPERIMENT.md"
    out["experiment"] = _read_text_safe(exp_file)
    # Analysis outputs: try presentation/ first, then hypothesis_X/experiment_Y/ as fallback
    pres_dir = workspace_path / "presentation" / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
    report_md_pres = pres_dir / "report.md"
    report_md_exp = exp_dir / "report.md"
    out["analysis_report"] = _read_text_safe(report_md_pres) or _read_text_safe(report_md_exp)
    result_pres = pres_dir / "data" / "analysis_summary.json"
    result_exp = exp_dir / "data" / "analysis_summary.json"
    out["analysis_result_json"] = _read_text_safe(result_pres) or _read_text_safe(result_exp)
    # Collect figure paths relative to assets (include subdirs e.g. assets/figures/*.png)
    figure_paths_set: set[str] = set()
    for assets_dir in (pres_dir / "assets", exp_dir / "assets"):
        for rel in _collect_figure_paths_under(assets_dir):
            figure_paths_set.add(rel)
    out["figure_names"] = sorted(figure_paths_set)
    # Optional literature
    lit_file = workspace_path / "papers" / "literature_index.json"
    if lit_file.exists():
        try:
            data = json.loads(lit_file.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
            out["literature_titles"] = [e.get("title", "") for e in entries if e.get("title")][:15]
        except Exception:
            pass
    return out


def _build_synthesis_prompt(ctx: Dict[str, Any], custom_instructions: Optional[str]) -> str:
    topic = ctx.get("topic") or "(none)"
    hypothesis = ctx.get("hypothesis") or "(none)"
    experiment = ctx.get("experiment") or "(none)"
    report = ctx.get("analysis_report") or "(none)"
    result_json = ctx.get("analysis_result_json") or "{}"
    figure_names = ctx.get("figure_names") or []
    literature = ctx.get("literature_titles") or []
    inst = f"\nAdditional instructions: {custom_instructions}\n" if custom_instructions else ""
    figures_placeholder = (
        "For each figure path below, output one object with: id (e.g. fig:stem), caption (short English caption), description (one line), file_path (must be exactly 'assets/<path>' where path is the path below, e.g. assets/figures/foo.png)."
        if figure_names else "No figures; output figures: []."
    )
    lit_placeholder = (
        "You may include 0–3 references as BibTeX strings in 'references' (e.g. @article{...}) based on the titles below, or leave references: []."
        if literature else "Leave references: [] unless you have explicit BibTeX."
    )
    return f"""You are preparing metadata for an academic paper from experiment analysis. The context below is taken from the user's workspace: TOPIC (topic doc), HYPOTHESIS (hypothesis doc), EXPERIMENT (this run), ANALYSIS REPORT (markdown), ANALYSIS RESULT (JSON), and figure file names under assets. You must fill the JSON by summarizing this content only. Do not output file paths or placeholder text like "See ..." for the five summary fields; derive title, idea_hypothesis, method, data, and experiments from the actual text below.

**Required:** If the TOPIC or HYPOTHESIS sections below are not "(none)", you MUST incorporate their substance into idea_hypothesis and (where relevant) into method and title. Do not ignore TOPIC or HYPOTHESIS.

Context:
## TOPIC
{topic}

## HYPOTHESIS
{hypothesis}

## EXPERIMENT (this run)
{experiment}

## ANALYSIS REPORT (markdown)
{report}

## ANALYSIS RESULT (JSON)
{result_json}

## FIGURE FILES (paths under assets/; may include subdirs e.g. figures/xxx.png)
{', '.join(figure_names) or 'None'}

## LITERATURE (titles only, for optional references)
{chr(10).join(literature) or 'None'}
{inst}

Output a single JSON object with these keys (all strings except references and figures). Each of the five summary fields must be written from the above context; do not hardcode paths or "See ..." placeholders:
- title: concise paper title summarized from TOPIC, HYPOTHESIS, and report. Use English only (see additional instructions).
- idea_hypothesis: research question or hypothesis (1–3 sentences). You MUST base this on TOPIC and HYPOTHESIS when they are not "(none)"; you may also use report.
- method: methodology and design. You MUST summarize from HYPOTHESIS and EXPERIMENT and ANALYSIS REPORT (include HYPOTHESIS content when not "(none)").
- data: data or validation setup summarized from EXPERIMENT, ANALYSIS REPORT, and ANALYSIS RESULT.
- experiments: experiment design, results, and findings summarized from ANALYSIS REPORT and ANALYSIS RESULT (no file paths).
- references: array of BibTeX strings (e.g. @article{{key, ...}}). {lit_placeholder}
- figures: array of objects. {figures_placeholder} Figure list: {figure_names}
"""


# User-facing description of workspace inputs used by synthesis (no hardcoded absolute paths).
SYNTHESIS_INPUTS_DESCRIPTION = (
    "Synthesis uses content from the workspace: TOPIC.md (workspace root), "
    "HYPOTHESIS.md (per hypothesis), and per-experiment files: report.md, "
    "data/analysis_summary.json, and figures under assets/ (multi-experiment aggregation may be added later). "
    "The fields title, idea_hypothesis, method, data, and experiments are summarized from these file contents, not hardcoded paths."
)


class GeneratePaperTool(BaseTool):
    """将实验分析报告排版成学术论文 PDF

    支持两种 meta 来源：
    - use_synthesis=true（默认）：由 LLM 根据工作区内用户提供的文件内容填写 meta。依赖：TOPIC.md、HYPOTHESIS.md，
      以及单实验的 report.md、data/analysis_summary.json、assets 中的 figures（后续可扩展多实验）。
      title / idea_hypothesis / method / data / experiments 均从上述文件内容总结得出，不硬编码地址。
    - use_synthesis=false：使用固定规则从该实验的 report.md、data/analysis_summary.json、assets/ 映射为 meta 后提交 EasyPaper。
    需先对同一 hypothesis/experiment 执行 data_analysis 生成报告与图表。
    """

    def get_name(self) -> str:
        return "generate_paper"

    def get_description(self) -> str:
        return (
            "Typeset the experiment analysis report into an academic paper PDF.\n\n"
            "You MUST pass hypothesis_id and experiment_id (same as data_analysis). Call this after data_analysis "
            "has been run for that hypothesis and experiment.\n\n"
            "By default (use_synthesis=true), an LLM summarizes workspace-provided files to fill paper metadata. "
            "Required inputs in the workspace: TOPIC.md, HYPOTHESIS.md; for the chosen experiment: "
            "report.md, data/analysis_summary.json, and figures under assets/ (support for multiple "
            "experiments may be added later). The fields title, idea_hypothesis, method, data, and experiments "
            "are derived from the content of these files, not hardcoded paths. Set use_synthesis=false to use a "
            "fixed mapping from analysis output only.\n\n"
            "You SHOULD politely ask the user if they want to use a LaTeX template .zip (e.g. COLM/ICML style). "
            "If they provide a path, pass it via template_path; otherwise leave template_path unset.\n"
            "You SHOULD also ask (or infer) a target page count; when unsure, use target_pages=6 as the default.\n\n"
            "Optional parameters: synthesis_instructions (when use_synthesis=true), template_path, style_guide, "
            "target_pages, output_dir, enable_review (enable EasyPaper's internal multi-iteration review loop), "
            "max_review_iterations (when enable_review=true, default 3), and enable_vlm_review (default true; set false to disable VLM layout review)."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hypothesis_id": {
                    "type": "string",
                    "description": "Required. Hypothesis ID, e.g. '1', '2'.",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "Required. Experiment ID, e.g. '1', '2'.",
                },
                "use_synthesis": {
                    "type": "boolean",
                    "description": "Optional. If true (default), LLM fills paper metadata from TOPIC/HYPOTHESIS/report; if false, use fixed mapping from analysis output.",
                },
                "synthesis_instructions": {
                    "type": "string",
                    "description": "Optional. Extra instructions for the LLM when filling metadata (only when use_synthesis=true).",
                },
                "template_path": {
                    "type": "string",
                    "description": "Optional. LaTeX template .zip path (ask the user; if they do not care, omit this field).",
                },
                "style_guide": {
                    "type": "string",
                    "description": "Optional. Style guide name, e.g. 'COLM', 'ICML', 'NeurIPS'. Defaults to 'COLM' if not specified.",
                },
                "target_pages": {
                    "type": "integer",
                    "description": "Optional. Target number of pages for the paper. If omitted, default is 6.",
                },
                "enable_review": {
                    "type": "boolean",
                    "description": "Optional. Whether to enable EasyPaper's internal review loop (ReviewerAgent). "
                                   "Defaults to true (matching EasyPaper scripts/generate_paper.py); set false to skip review.",
                },
                "max_review_iterations": {
                    "type": "integer",
                    "description": "Optional. Maximum number of review iterations when enable_review=true. "
                                   "If omitted but enable_review=true, default is 3.",
                },
                "enable_vlm_review": {
                    "type": "boolean",
                    "description": "Optional. Whether to enable EasyPaper's VLM-based PDF layout review. "
                                   "Defaults to true; set to false to disable.",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Optional. Directory path to save output (server-side). "
                                   "If relative, it is resolved against the workspace. "
                                   "Files (main.tex, references.bib, paper_plan.json, main.pdf) are written by EasyPaper to this path; "
                                   "if EasyPaper runs on another host or in Docker, ensure this path is a shared/mounted directory so both services see the same files.",
                },
            },
            "required": ["hypothesis_id", "experiment_id"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            hypothesis_id = arguments.get("hypothesis_id")
            experiment_id = arguments.get("experiment_id")
            if not hypothesis_id or not experiment_id:
                return ToolResult(
                    success=False,
                    content="Missing required parameters: hypothesis_id and experiment_id.",
                    error="Missing required parameters",
                )

            workspace = Path(self._workspace_path)
            pres_dir = workspace / "presentation" / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
            exp_dir = workspace / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
            if pres_dir.is_dir():
                output_dir = pres_dir
            elif exp_dir.is_dir():
                output_dir = exp_dir
            else:
                return ToolResult(
                    success=False,
                    content=f"Analysis output directory not found (tried: {pres_dir}, {exp_dir}). Run data_analysis first for this hypothesis and experiment.",
                    error="Output directory not found",
                )

            use_synthesis = arguments.get("use_synthesis", True)
            synthesis_instructions = arguments.get("synthesis_instructions")
            # Default: write entire paper in English to avoid ctex dependency (COLM/ICML templates are English)
            english_default = "Write the entire paper in English (title, idea_hypothesis, method, data, experiments, and figure captions). Do not use Chinese."
            synthesis_instructions = (
                f"{english_default} {synthesis_instructions}" if synthesis_instructions else english_default
            )
            metadata = None

            if use_synthesis:
                await self._send_progress(
                    ToolEvent(
                        tool_id=self._current_tool_id,
                        tool_name=self.get_name(),
                        status="progress",
                        content="Synthesizing paper metadata with LLM (TOPIC, HYPOTHESIS, report)...",
                    )
                )
                metadata = await self._run_synthesis_async(
                    workspace, output_dir, hypothesis_id, experiment_id, synthesis_instructions
                )
                if metadata:
                    await self._send_progress(
                        ToolEvent(
                            tool_id=self._current_tool_id,
                            tool_name=self.get_name(),
                            status="progress",
                            content="Using synthesized metadata ...",
                        )
                    )
                    # Resolve figure paths to absolute; use assets dir where files actually exist (exp_dir has priority over presentation)
                    figures = metadata.get("figures") or []
                    resolved = []
                    exp_assets = exp_dir / "assets"
                    out_assets = output_dir / "assets"
                    for fig in figures:
                        if not isinstance(fig, dict):
                            continue
                        fp = fig.get("file_path") or ""
                        if fp.startswith("assets/"):
                            name = fp.replace("assets/", "").strip()
                            if not name and fig.get("id"):
                                name = (fig.get("id") or "").replace("fig:", "") + ".png"
                            cand = (exp_assets / name) if name else None
                            if cand and cand.exists():
                                abs_path = cand.resolve()
                            else:
                                abs_path = (output_dir / fp).resolve()
                            resolved.append({**fig, "file_path": str(abs_path)})
                        else:
                            resolved.append(fig)
                    metadata["figures"] = resolved
                    metadata.setdefault("tables", [])

            if metadata is None:
                await self._send_progress(
                    ToolEvent(
                        tool_id=self._current_tool_id,
                        tool_name=self.get_name(),
                        status="progress",
                        content="Building metadata from analysis output (fixed mapping)...",
                    )
                )
                metadata = _build_metadata_from_analysis(output_dir, hypothesis_id, experiment_id)
                # Merge TOPIC/HYPOTHESIS/report into fallback so metadata still reflects workspace content
                ctx = _gather_synthesis_context(workspace, hypothesis_id, experiment_id)
                metadata = _merge_context_into_metadata(ctx, metadata)

            template_path = arguments.get("template_path")
            style_guide = arguments.get("style_guide")
            target_pages = arguments.get("target_pages")
            enable_review = arguments.get("enable_review", True)
            max_review_iterations = arguments.get("max_review_iterations")
            enable_vlm_review = arguments.get("enable_vlm_review", True)
            out_dir_arg = arguments.get("output_dir")

            # Decide output directory (server-side) and where to write metadata.json.
            # - If user passes output_dir: interpret as workspace-relative when not absolute.
            # - Otherwise: base_dir = <workspace>/hypothesis_{id}/experiment_{id}
            # In both cases, the actual output goes into base_dir / "final_paper_YYYYMMDD_HHMMSS".
            if out_dir_arg:
                base_dir = Path(out_dir_arg)
                if not base_dir.is_absolute():
                    base_dir = (workspace / base_dir).resolve()
            else:
                base_dir = (workspace / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}").resolve()

            # Use final_paper_YYYYMMDD_HHMMSS for unique output directory per run.
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            paper_dir_name = f"final_paper_{timestamp}"
            paper_output_dir = base_dir / paper_dir_name

            paper_output_dir.mkdir(parents=True, exist_ok=True)
            metadata_json_path: Optional[Path] = None

            # Prefer experiment dir assets (hypothesis_X/experiment_Y/assets) so EasyPaper finds figures there
            exp_assets_dir = exp_dir / "assets"
            out_assets_dir = output_dir / "assets"
            figures_source_dir = (exp_assets_dir if exp_assets_dir.is_dir() else out_assets_dir).resolve()

            # template_path: use only when user specifies it and the file exists.
            # If not specified or path invalid (zip not found), fall back to plain compilation (no template).
            # style_guide: default COLM when template is valid; use "plain" when falling back.
            if template_path:
                if not Path(template_path).is_file():
                    logger.warning(f"template_path not found: {template_path}, falling back to plain compilation")
                    template_path = None
            if not template_path:
                style_guide = "plain"
            elif style_guide is None or style_guide == "":
                style_guide = "COLM"
            if template_path and (not style_guide or style_guide == "") and "colm" in str(template_path).lower():
                style_guide = "COLM"

            # Configure review loop: enabled by default (matching EasyPaper scripts/generate_paper.py).
            # EasyPaper creates iteration_XX (and iteration_XX_final) ONLY when the loop runs (max_review_iterations >= 1).
            # Default max_review_iterations=3 when enabled; when disabled, use 1 so we still get iteration_01
            # output structure (no restriction on template_path).
            if enable_review:
                if max_review_iterations is None:
                    max_review_iterations_int = 3
                else:
                    try:
                        max_review_iterations_int = max(1, int(max_review_iterations))
                    except Exception:
                        max_review_iterations_int = 3
            else:
                # No review: still run once (max=1) to create iteration_01 for consistent output structure.
                max_review_iterations_int = 1

            request_body: Dict[str, Any] = {
                **metadata,
                "compile_pdf": True,
                "figures_source_dir": str(figures_source_dir),
                "save_output": True,
                "enable_review": bool(enable_review),
                "max_review_iterations": max_review_iterations_int,
                # VLM-based layout review is on by default; user can disable via enable_vlm_review=false.
                "enable_vlm_review": bool(enable_vlm_review),
            }
            # Default target_pages to 6 when not explicitly provided.
            if target_pages is None:
                target_pages = 6
            request_body["target_pages"] = int(target_pages)

            if template_path:
                request_body["template_path"] = template_path
            else:
                request_body.pop("template_path", None)
            if style_guide:
                request_body["style_guide"] = style_guide
            # Always send a concrete output_dir so PDF lands in a predictable place.
            request_body["output_dir"] = str(paper_output_dir)

            # Persist the full request body as metadata.json for reproducibility.
            try:
                metadata_json_path = paper_output_dir / "metadata.json"
                metadata_json_path.write_text(
                    json.dumps(request_body, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info(f"Saved metadata.json to {metadata_json_path}")
            except Exception as e:
                logger.warning(f"Failed to write metadata.json: {e}")
                metadata_json_path = None

            api_url = _get_easypaper_url()
            await self._send_progress(
                ToolEvent(
                    tool_id=self._current_tool_id,
                    tool_name=self.get_name(),
                    status="progress",
                    content=f"Calling at {api_url}/metadata/generate ...",
                )
            )

            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{api_url.rstrip('/')}/metadata/generate",
                    json=request_body,
                )

            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    content=f"EasyPaper API error: {response.status_code} {response.text}",
                    error=f"API {response.status_code}",
                )

            result = response.json()
            ep_status = result.get("status") or "ok"
            ep_errors = result.get("errors") or []
            output_path = result.get("output_path") or ""
            pdf_path = result.get("pdf_path") or ""

            # EasyPaper returns status 'ok' | 'partial' | 'error'. If 'error', no main.tex/pdf were written.
            if ep_status == "error":
                err_msg = "; ".join(ep_errors[:5]) if ep_errors else "Unknown error"
                return ToolResult(
                    success=False,
                    content=(
                        f"EasyPaper generation failed (status=error). "
                        f"Output directory was not fully written (no main.tex, paper_plan.json, main.pdf). "
                        f"Errors: {err_msg}"
                    ),
                    error="EasyPaper status=error",
                    data={
                        "easypaper_status": ep_status,
                        "easypaper_errors": ep_errors,
                        "output_path": output_path,
                        "metadata_json_path": str(metadata_json_path) if metadata_json_path else None,
                    },
                )

            # Success or partial: report where files are. Output structure matches EasyPaper results:
            # paper_output_dir/ has metadata.json, main.tex, references.bib, paper_plan.json at root;
            # iteration_XX_final/ has the complete PDF compilation files (main.tex, references.bib, figures/, sections/, main.pdf).
            expected_dir = str(paper_output_dir)
            if output_path and output_path != expected_dir:
                logger.warning(
                    "EasyPaper output_path (%s) differs from requested paper_output_dir (%s). "
                    "If only metadata.json appears in the requested folder, EasyPaper may be writing "
                    "to a different filesystem (e.g. container); ensure both use the same output_dir.",
                    output_path,
                    expected_dir,
                )
            # Build message: mention iteration_XX_final for complete compilation files (like EasyPaper results)
            iter_final_dirs = sorted(paper_output_dir.glob("iteration_*_final"), key=lambda p: p.name, reverse=True)
            iter_msg = ""
            if iter_final_dirs:
                iter_name = iter_final_dirs[0].name
                iter_msg = f" Complete PDF compilation files (main.tex, references.bib, figures/, sections/, main.pdf) are in {iter_name}/."
            content_msg = (
                f"Paper generation completed (status={ep_status}). "
                f"Output directory: {output_path or expected_dir}. "
                f"PDF: {pdf_path or 'not generated'}.{iter_msg}"
            )
            if ep_status == "partial" and ep_errors:
                content_msg += f" Warnings: {'; '.join(ep_errors[:3])}."
            return ToolResult(
                success=True,
                content=content_msg,
                data={
                    "pdf_path": pdf_path,
                    "output_path": output_path or expected_dir,
                    "iteration_final_dir": str(iter_final_dirs[0]) if iter_final_dirs else None,
                    "easypaper_status": ep_status,
                    "metadata": metadata,
                    "metadata_json_path": str(metadata_json_path) if metadata_json_path else None,
                    "easypaper_response": result,
                },
            )
        except httpx.ConnectError as e:
            logger.error(f"EasyPaper connection failed: {e}")
            return ToolResult(
                success=False,
                content=f"Cannot connect to EasyPaper. Ensure it is running (e.g. EASYPAPER_API_URL={_get_easypaper_url()}).",
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Generate paper tool failed: {e}", exc_info=True)
            return ToolResult(success=False, content=str(e), error=str(e))

    async def _run_synthesis_async(
        self,
        workspace_path: Path,
        output_dir: Path,
        hypothesis_id: str,
        experiment_id: str,
        custom_instructions: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """异步：由 LLM 填写 meta 并保存到 synthesis_metadata.json。"""
        ctx = _gather_synthesis_context(workspace_path, hypothesis_id, experiment_id)
        prompt = _build_synthesis_prompt(ctx, custom_instructions)
        router, model_name = get_llm_router_and_model("default")
        response = await router.acompletion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = (response.choices[0].message.content or "").strip()
        data = parse_llm_json_response(content)
        if not data and content:
            # Try to extract a single {...} block (some models wrap JSON in text)
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    data = json_repair.loads(match.group(0))
                    data = data if isinstance(data, dict) else {}
                except Exception:
                    pass
        if not data:
            logger.warning(
                "Synthesis LLM did not return valid JSON; falling back to context-merged metadata. "
                "Content snippet: %s",
                (content[:500] + "..." if len(content) > 500 else content) or "(empty)",
            )
            return None

        figure_names = ctx.get("figure_names") or []
        figures = data.get("figures") or []
        by_name = {Path(n).stem: n for n in figure_names}
        normalized_figures: List[Dict[str, Any]] = []
        for i, fig in enumerate(figures):
            if not isinstance(fig, dict):
                continue
            name = by_name.get(Path(fig.get("file_path", "")).stem) or (figure_names[i] if i < len(figure_names) else None)
            if not name:
                continue
            normalized_figures.append({
                "id": fig.get("id") or f"fig:{Path(name).stem}",
                "caption": fig.get("caption") or Path(name).stem.replace("_", " ").title(),
                "description": fig.get("description") or "",
                "file_path": f"assets/{name}",
            })
        data["figures"] = normalized_figures
        data.setdefault("tables", [])

        syn_file = output_dir / "synthesis_metadata.json"
        syn_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved synthesis metadata to {syn_file}")
        return data
