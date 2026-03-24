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
    parser.add_argument("--hypothesis-id", required=True, help="Hypothesis ID")
    parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    parser.add_argument("--workspace", default=".", help="Workspace path")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()

    # Delay importing the main package until after argparse handles --help,
    # avoiding unnecessary initialization failures during help usage.
    from agentsociety2.skills.analysis import run_analysis

    try:
        result = asyncio.run(
            run_analysis(
                workspace_path=str(workspace_path),
                hypothesis_id=args.hypothesis_id,
                experiment_id=args.experiment_id,
            )
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1

    if result.get("success"):
        output_dir = result.get("output_directory", "")
        files = result.get("generated_files", {}) or {}
        report_md = files.get("markdown", "")
        report_html = files.get("html", "")
        print("Analysis completed successfully")
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
