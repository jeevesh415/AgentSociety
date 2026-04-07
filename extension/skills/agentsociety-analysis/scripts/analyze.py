#!/usr/bin/env python3
"""Data analysis CLI script"""

import argparse
import asyncio
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


def main():
    parser = argparse.ArgumentParser(description="Analyze experiment data")
    parser.add_argument(
        "--mode",
        default="single",
        choices=("single", "batch", "synthesize"),
        help="Analysis mode: single|batch|synthesize",
    )
    parser.add_argument("--hypothesis-id", help="Hypothesis ID (for single/batch)")
    parser.add_argument("--experiment-id", help="Experiment ID (for single)")
    parser.add_argument(
        "--hypothesis-ids",
        nargs="+",
        help="Hypothesis IDs (for synthesize; default: auto-discover)",
    )
    parser.add_argument(
        "--experiment-ids",
        nargs="+",
        help="Experiment IDs (for batch/synthesize; default: auto-discover)",
    )
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument("--instructions", help="Additional analysis instructions")
    parser.add_argument("--literature-summary", help="Optional literature summary")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()

    # Delay importing the main package until after argparse handles --help,
    # avoiding unnecessary initialization failures during help usage.
    from agentsociety2.skills.analysis import run_analysis_workflow

    result = asyncio.run(
        run_analysis_workflow(
            workspace_path=str(workspace_path),
            mode=args.mode,
            hypothesis_id=args.hypothesis_id,
            experiment_id=args.experiment_id,
            hypothesis_ids=args.hypothesis_ids,
            experiment_ids=args.experiment_ids,
            custom_instructions=args.instructions,
            literature_summary=args.literature_summary,
        )
    )

    if result.get("success"):
        print("Analysis completed successfully")
        if result.get("mode") == "synthesize":
            synth = result.get("synthesis", {}) or {}
            if isinstance(synth, dict):
                if synth.get("synthesis_report_path"):
                    print(f"Markdown report: {synth.get('synthesis_report_path')}")
                if synth.get("synthesis_report_html_path"):
                    print(f"HTML report: {synth.get('synthesis_report_html_path')}")
        else:
            output_dir = result.get("output_directory", "")
            files = result.get("generated_files", {}) or {}
            report_md = files.get("markdown", "")
            report_html = files.get("html", "")
            if output_dir:
                print(f"Output directory: {output_dir}")
            if report_md:
                print(f"Markdown report: {report_md}")
            if report_html:
                print(f"HTML report: {report_html}")
        return 0
    else:
        error = result.get("error", "Unknown error")
        errors = result.get("error_messages", []) or []
        print(f"Error: {error}")
        if errors:
            print("Runtime errors:")
            for item in errors:
                print(f"- {item}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
