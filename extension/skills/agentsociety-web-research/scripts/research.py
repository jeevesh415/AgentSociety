#!/usr/bin/env python3
"""Web research CLI script"""

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

from agentsociety2.skills.web_research import execute_web_research


async def main():
    parser = argparse.ArgumentParser(description="Perform web research")
    parser.add_argument("query", help="Research query")
    parser.add_argument("--llm", help="LLM model name")
    parser.add_argument("--agent", help="Agent configuration name")

    args = parser.parse_args()

    result = await execute_web_research(
        query=args.query,
        llm=args.llm,
        agent=args.agent,
    )

    if result.get("success"):
        print(result.get("content", "Success"))
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
