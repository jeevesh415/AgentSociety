#!/usr/bin/env python3
"""Synthesize CLI script"""

import asyncio
import argparse
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

from agentsociety2.skills.analysis import run_synthesis


async def main():
    parser = argparse.ArgumentParser(
        description="Synthesize experiment results into research summaries"
    )
    parser.add_argument("--hypothesis-id", required=True, help="Hypothesis ID")
    parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument("--instructions", help="Additional synthesis instructions")
    parser.add_argument(
        "--output-dir", help="Output directory (default: auto-determined)"
    )

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()

    result = await run_synthesis(
        workspace_path=workspace_path,
        hypothesis_id=args.hypothesis_id,
        experiment_id=args.experiment_id,
        instructions=args.instructions,
        output_dir=args.output_dir,
    )

    if result.get("success"):
        print(result.get("content", "Synthesis complete"))
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
