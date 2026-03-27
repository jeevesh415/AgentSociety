#!/usr/bin/env python3
"""Innovation framing CLI script."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from workspace .env file
workspace_root = Path(__file__).resolve().parents[4]
env_file = workspace_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add the workspace root to Python path
import sys

sys.path.insert(0, str(workspace_root / "packages" / "agentsociety2"))

from agentsociety2.config import extract_json, get_llm_router, get_llm_router_and_model
from agentsociety2.skills.literature import load_literature_index, search_literature_and_save

FIXED_HEADINGS = [
    "## Description",
    "## Research Gap",
    "## Innovation Direction",
    "## Candidate Hypotheses",
    "## Next Steps",
]

def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _entry_sort_key(entry: Any) -> tuple[int, float, str]:
    similarity = entry.avg_similarity if entry.avg_similarity is not None else -1.0
    query_priority = 1 if entry.query else 0
    saved_at = entry.saved_at or ""
    return (query_priority, similarity, saved_at)


def normalize_queries(
    raw_queries: list[Any],
    existing_query: str | None,
    fallback_title: str,
) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    blocked = {existing_query.strip().lower()} if existing_query and existing_query.strip() else set()

    for item in raw_queries:
        query = str(item).strip()
        if not query:
            continue
        lowered = query.lower()
        if lowered in seen or lowered in blocked:
            continue
        seen.add(lowered)
        normalized.append(query)

    if normalized:
        return normalized[:3]
    return [fallback_title]


def select_literature_entries(index: Any, query: str | None, top_k: int) -> list[Any]:
    entries = list(index.entries)
    if query:
        matched = [entry for entry in entries if entry.query == query]
        if matched:
            entries = matched
    entries.sort(key=_entry_sort_key, reverse=True)
    return entries[:top_k]


def _read_entry_excerpt(
    workspace_path: Path, relative_path: str, max_chars: int = 1800
) -> str:
    file_path = workspace_path / relative_path
    if not file_path.exists():
        return ""
    content = file_path.read_text(encoding="utf-8")
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "\n..."


def build_literature_context(workspace_path: Path, entries: list[Any]) -> str:
    blocks: list[str] = []
    for idx, entry in enumerate(entries, 1):
        excerpt = _read_entry_excerpt(workspace_path, entry.file_path)
        blocks.append(
            "\n".join(
                [
                    f"[Paper {idx}]",
                    f"Title: {entry.title}",
                    f"Journal: {entry.journal or 'N/A'}",
                    f"Query: {entry.query or 'N/A'}",
                    f"Similarity: {entry.avg_similarity if entry.avg_similarity is not None else 'N/A'}",
                    f"Abstract: {entry.abstract or 'N/A'}",
                    "Saved Markdown Excerpt:",
                    excerpt or "N/A",
                ]
            )
        )
    return "\n\n".join(blocks)


def infer_fallback_title(topic_text: str) -> str:
    for line in topic_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or "Research Topic"
    return "Research Topic"


def extract_section(topic_markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(topic_markdown)
    if not match:
        return ""
    return match.group(1).strip()


def normalize_fixed_structure(topic_markdown: str, fallback_title: str) -> str:
    title = infer_fallback_title(topic_markdown) or fallback_title
    sections = [f"# {title}", ""]
    for heading in FIXED_HEADINGS:
        body = extract_section(topic_markdown, heading)
        if not body:
            if heading == "## Candidate Hypotheses":
                body = "- [To be refined from literature-grounded framing]"
            else:
                body = "[To be refined]"
        sections.extend([heading, "", body, ""])
    return "\n".join(sections).rstrip() + "\n"


def finalize_topic_markdown(topic_markdown: str, fallback_title: str) -> str:
    content = topic_markdown.strip()
    if not content:
        content = ""
    elif not re.search(r"^#\s+\S", content, re.MULTILINE):
        content = f"# {fallback_title}\n\n{content}"
    return normalize_fixed_structure(content, fallback_title=fallback_title)


async def assess_literature_sufficiency(
    topic_text: str,
    literature_context: str,
    query: str | None,
    focus: str | None,
    fallback_title: str,
) -> dict[str, Any]:
    router, model_name = get_llm_router_and_model("default")
    preferred_language = (
        "Chinese" if _contains_chinese(topic_text + "\n" + (focus or "")) else "English"
    )

    system_prompt = (
        "You are an AI Social Scientist literature strategist. "
        "Judge whether the current literature library is sufficient to understand the state of research for innovation framing. "
        "Return valid JSON only."
    )
    user_prompt = f"""
Current TOPIC.md content:
<topic>
{topic_text}
</topic>

Optional scoped query:
{query or "N/A"}

Optional framing focus:
{focus or "N/A"}

Current literature evidence:
<literature>
{literature_context}
</literature>

Write in {preferred_language}.

Return JSON with this schema:
{{
  "is_sufficient": true,
  "reasoning": "brief rationale",
  "additional_queries": ["query 1", "query 2"]
}}

Requirements:
- If the current literature is insufficient, set `is_sufficient` to false.
- Suggest at most 3 additional literature-search queries.
- Queries should help understand the broader field status, not just narrow implementation details.
- If the current coverage is already sufficient, return an empty query list.
""".strip()

    response = await router.acompletion(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    json_text = extract_json(content) or content
    assessment = json.loads(json_text)
    if not isinstance(assessment, dict):
        raise ValueError("Literature sufficiency response must be a JSON object")
    assessment["additional_queries"] = normalize_queries(
        list(assessment.get("additional_queries", []) or []),
        existing_query=query,
        fallback_title=fallback_title,
    ) if not bool(assessment.get("is_sufficient")) else []
    return assessment


async def generate_topic_update(
    topic_text: str,
    literature_context: str,
    query: str | None,
    focus: str | None,
) -> dict[str, Any]:
    router, model_name = get_llm_router_and_model("default")
    preferred_language = (
        "Chinese" if _contains_chinese(topic_text + "\n" + (focus or "")) else "English"
    )

    system_prompt = (
        "You are an AI Social Scientist research strategist. "
        "You read literature evidence and revise a research topic document for simulation-based social science research. "
        "Do not invent papers or claims beyond the provided evidence. "
        "Return valid JSON only."
    )
    user_prompt = f"""
Current TOPIC.md content:
<topic>
{topic_text}
</topic>

Optional scoped query:
{query or "N/A"}

Optional framing focus:
{focus or "N/A"}

Literature evidence:
<literature>
{literature_context}
</literature>

Write in {preferred_language}.

Return JSON with this schema:
{{
  "direction_title": "short title",
  "topic_markdown": "the complete updated TOPIC.md content"
}}

Requirements:
- Rewrite the whole TOPIC.md as a coherent working document.
- Use exactly this heading structure:
  1. `# <Research Title>`
  2. `## Description`
  3. `## Research Gap`
  4. `## Innovation Direction`
  5. `## Candidate Hypotheses`
  6. `## Next Steps`
- Keep these headings verbatim in the output.
- Integrate the innovation framing into these sections naturally.
- Do not create a dedicated heading named "Innovation Framing".
- The updated topic must be testable within AgentSociety-style simulation experiments.
- Candidate hypotheses should be specific enough to guide later experiment design.
- Next actions should directly support hypothesis creation and experiment setup.
- Preserve useful context from the original TOPIC.md when still relevant.
- Return markdown only inside the JSON string, without code fences.
""".strip()

    response = await router.acompletion(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    content = response.choices[0].message.content or ""
    json_text = extract_json(content) or content
    framing = json.loads(json_text)
    if not isinstance(framing, dict):
        raise ValueError("Topic update response must be a JSON object")
    return framing


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Frame innovation directions from literature search results"
    )
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument(
        "--query", help="Restrict to entries from a specific literature query"
    )
    parser.add_argument("--focus", help="Extra framing focus")
    parser.add_argument(
        "--top-k", type=int, default=6, help="Number of literature entries to use"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    topic_path = workspace_path / "TOPIC.md"

    literature_index = load_literature_index(workspace_path)
    if literature_index is None or not literature_index.entries:
        print(
            "Error: papers/literature_index.json is missing or empty. Run literature search first."
        )
        return 1

    selected_entries = select_literature_entries(
        literature_index, args.query, args.top_k
    )
    if not selected_entries:
        print("Error: No literature entries matched the requested query/filter.")
        return 1

    topic_text = topic_path.read_text(encoding="utf-8") if topic_path.exists() else ""
    fallback_title = infer_fallback_title(topic_text)
    literature_context = build_literature_context(workspace_path, selected_entries)
    supplemental_queries: list[str] = []
    sufficiency_reasoning = ""

    try:
        assessment = await assess_literature_sufficiency(
            topic_text=topic_text,
            literature_context=literature_context,
            query=args.query,
            focus=args.focus,
            fallback_title=fallback_title,
        )
        sufficiency_reasoning = str(assessment.get("reasoning", "")).strip()
    except Exception as exc:
        assessment = {"is_sufficient": True, "additional_queries": []}
        sufficiency_reasoning = f"Coverage assessment skipped: {exc}"

    if not bool(assessment.get("is_sufficient")):
        router = get_llm_router("default")
        for extra_query in assessment.get("additional_queries", []):
            try:
                search_result = await search_literature_and_save(
                    query=extra_query,
                    workspace_path=workspace_path,
                    router=router,
                    top_k=max(3, min(args.top_k, 5)),
                    enable_multi_query=True,
                )
            except Exception:
                continue
            if search_result.get("success") and search_result.get("total", 0) > 0:
                supplemental_queries.append(extra_query)

        refreshed_index = load_literature_index(workspace_path)
        if refreshed_index is not None and refreshed_index.entries:
            selected_entries = select_literature_entries(
                refreshed_index,
                args.query,
                args.top_k,
            )
            literature_context = build_literature_context(workspace_path, selected_entries)

    try:
        framing = await generate_topic_update(
            topic_text=topic_text,
            literature_context=literature_context,
            query=args.query,
            focus=args.focus,
        )
    except Exception as exc:
        print(f"Error: Failed to generate innovation framing: {exc}")
        return 1

    updated_topic = finalize_topic_markdown(
        str(framing.get("topic_markdown", "")),
        fallback_title=fallback_title,
    )
    topic_path.write_text(updated_topic, encoding="utf-8")

    result = {
        "success": True,
        "topic_path": str(topic_path),
        "selected_titles": [entry.title for entry in selected_entries],
        "direction_title": framing.get("direction_title", ""),
        "supplemental_queries": supplemental_queries,
        "coverage_reasoning": sufficiency_reasoning,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Updated TOPIC.md with innovation framing at: {topic_path}")
        print(f"Direction: {framing.get('direction_title', 'Innovation framing')}")
        if sufficiency_reasoning:
            print(f"Coverage assessment: {sufficiency_reasoning}")
        if supplemental_queries:
            print("Supplemental literature searches:")
            for extra_query in supplemental_queries:
                print(f"- {extra_query}")
        print("Evidence:")
        for title in result["selected_titles"]:
            print(f"- {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
