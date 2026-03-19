#!/usr/bin/env python3
"""Literature search CLI script"""

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

from agentsociety2.skills.literature import (
    search_literature_and_save,
    format_search_results,
    generate_summary,
)
from agentsociety2.config import get_llm_router


async def main():
    parser = argparse.ArgumentParser(description="Search academic literature")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top-k", type=int, default=3, help="Number of articles")
    parser.add_argument(
        "--no-multi-query", action="store_true", help="Disable multi-query"
    )
    parser.add_argument("--workspace", default=".", help="Workspace path")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    router = get_llm_router("default")

    result = await search_literature_and_save(
        query=args.query,
        workspace_path=workspace_path,
        router=router,
        top_k=args.top_k,
        enable_multi_query=not args.no_multi_query,
    )

    if result.get("success"):
        content = format_search_results(
            result["articles"],
            result["total"],
            result["query"],
        )

        # Generate summary
        try:
            summary = await generate_summary(
                args.query,
                result["articles"],
                result["total"],
                router,
            )
            content += "\n\n" + summary
        except Exception as e:
            print(f"Warning: Failed to generate summary: {e}")

        print(content)
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
