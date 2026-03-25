#!/usr/bin/env python3
"""Synthesize CLI script

支持两种模式：
1. 自动发现模式：不指定参数，自动发现工作区中所有假设和实验进行综合
2. 指定范围模式：指定 --hypothesis-ids 或 --experiment-ids 进行部分综合

Examples:
    # 自动发现所有假设和实验进行综合
    $PYTHON_PATH scripts/synthesize.py

    # 只综合特定假设
    $PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 2 3

    # 只综合特定实验
    $PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 --experiment-ids 1 2
"""

import asyncio
import argparse
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


async def main():
    parser = argparse.ArgumentParser(
        description="Synthesize experiment results into research summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-discover all hypotheses and experiments
  %(prog)s

  # Synthesize specific hypotheses
  %(prog)s --hypothesis-ids 1 2 3

  # Synthesize specific experiments under hypothesis 1
  %(prog)s --hypothesis-ids 1 --experiment-ids 1 2
        """,
    )
    parser.add_argument(
        "--hypothesis-ids",
        nargs="+",
        help="Hypothesis IDs to synthesize (default: auto-discover all)",
    )
    parser.add_argument(
        "--experiment-ids",
        nargs="+",
        help="Experiment IDs to synthesize (default: auto-discover all under each hypothesis)",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace path (default: current directory)",
    )
    parser.add_argument(
        "--instructions",
        help="Additional synthesis instructions",
    )

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()

    # Delay importing the main package until after argparse handles --help,
    # avoiding unnecessary initialization failures during help usage.
    from agentsociety2.skills.analysis import run_synthesis

    print("=" * 60)
    print("Synthesis Configuration")
    print("=" * 60)
    print(f"Workspace: {workspace_path}")
    if args.hypothesis_ids:
        print(f"Hypotheses: {args.hypothesis_ids}")
    else:
        print("Hypotheses: Auto-discover all")
    if args.experiment_ids:
        print(f"Experiments: {args.experiment_ids}")
    else:
        print("Experiments: Auto-discover all")
    print("=" * 60)

    try:
        result = await run_synthesis(
            workspace_path=str(workspace_path),
            hypothesis_ids=args.hypothesis_ids,
            experiment_ids=args.experiment_ids,
            custom_instructions=args.instructions,
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Synthesis Completed")
    print("=" * 60)

    if result.synthesis_report_path:
        print(f"Markdown report: {result.synthesis_report_path}")
    if result.synthesis_report_html_path:
        print(f"HTML report: {result.synthesis_report_html_path}")
    if result.best_hypothesis:
        print(f"Best hypothesis: {result.best_hypothesis}")
        if result.best_hypothesis_reason:
            print(f"Reason: {result.best_hypothesis_reason[:200]}...")

    print(f"\nHypotheses analyzed: {len(result.hypothesis_summaries)}")
    for summary in result.hypothesis_summaries:
        print(
            f"  - Hypothesis {summary.hypothesis_id}: {summary.experiment_count} experiments, "
            f"{summary.successful_experiments} successful"
        )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
