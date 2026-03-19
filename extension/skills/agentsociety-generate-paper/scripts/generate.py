#!/usr/bin/env python3
"""Generate paper CLI script"""

import asyncio
import argparse
from datetime import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from workspace .env file
workspace_root = Path(__file__).resolve().parents[4]
env_file = workspace_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add the workspace root to Python path
import sys

sys.path.insert(0, str(workspace_root / "packages" / "agentsociety2"))

from agentsociety2.skills.paper import (
    generate_paper_from_metadata,
    gather_synthesis_context,
    SUPPORTED_IMAGE_FORMATS,
)


async def main():
    parser = argparse.ArgumentParser(description="Generate academic paper")
    parser.add_argument("--hypothesis-id", required=True, help="Hypothesis ID")
    parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument("--target-pages", type=int, default=6, help="Target page count")
    parser.add_argument("--template", help="LaTeX template .zip path")
    parser.add_argument("--style", help="Style guide name")
    parser.add_argument("--no-review", action="store_true", help="Disable review loop")
    parser.add_argument("--output-dir", help="Output directory")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()

    # Gather context for metadata
    context = gather_synthesis_context(
        workspace_path=workspace_path,
        hypothesis_id=args.hypothesis_id,
        experiment_id=args.experiment_id,
    )

    # Build basic metadata
    metadata = {
        "title": context.get(
            "topic", f"Experiment Report (H{args.hypothesis_id}, E{args.experiment_id})"
        )[:200],
        "idea_hypothesis": context.get("hypothesis", "Research hypothesis")[:1200],
        "method": context.get("experiment", "See experiment design")[:2000],
        "data": context.get("analysis_result_json", "{}")[:2000],
        "experiments": context.get("analysis_report", "See analysis report")[:4000],
        "references": [],
        "figures": [],
        "tables": [],
    }

    # Determine output directory
    exp_dir = (
        workspace_path
        / f"hypothesis_{args.hypothesis_id}"
        / f"experiment_{args.experiment_id}"
    )
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
        if not output_dir.is_absolute():
            output_dir = (workspace_path / args.output_dir).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = exp_dir / f"final_paper_{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)

    result = await generate_paper_from_metadata(
        metadata=metadata,
        output_dir=output_dir,
        template_path=args.template,
        style_guide=args.style,
        target_pages=args.target_pages,
        enable_review=not args.no_review,
    )

    if result.get("success"):
        print(result.get("content", "Success"))
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
