#!/usr/bin/env python3
"""Hypothesis management CLI script"""

import argparse
import json
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

from agentsociety2.skills.hypothesis import (
    add_hypothesis,
    add_hypothesis_with_validation,
    get_hypothesis,
    list_hypotheses,
    delete_hypothesis,
)


def main():
    parser = argparse.ArgumentParser(
        description="Manage research hypotheses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all hypotheses
  python scripts/hypothesis.py list

  # Add a new hypothesis (inline)
  python scripts/hypothesis.py add \\
    --description "Agents with higher social capital have more influence" \\
    --rationale "Social capital theory suggests..." \\
    --groups \\
      '{"name":"control","group_type":"control","description":"Baseline agents"}' \\
      '{"name":"treatment","group_type":"treatment","description":"High social capital agents"}'

  # Get hypothesis details
  python scripts/hypothesis.py get --hypothesis-id 1

  # Delete a hypothesis
  python scripts/hypothesis.py delete --hypothesis-id 1
        """,
    )

    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # List command
    list_parser = subparsers.add_parser("list", help="List all hypotheses")
    list_parser.add_argument("--workspace", default=".", help="Workspace path")
    list_parser.add_argument("--json", action="store_true", help="Output JSON")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new hypothesis")
    add_parser.add_argument("--workspace", default=".", help="Workspace path")
    add_parser.add_argument(
        "--description", required=True, help="Hypothesis description"
    )
    add_parser.add_argument(
        "--rationale", required=True, help="Theoretical basis for the hypothesis"
    )
    add_parser.add_argument(
        "--groups",
        nargs="+",
        required=True,
        help="Experiment groups (JSON strings). Each group must contain: "
        "name, group_type, description. Optional: agent_selection_criteria",
    )
    add_parser.add_argument(
        "--agent-classes",
        nargs="*",
        help="Agent class types to use (e.g., person_agent llm_donor_agent)",
    )
    add_parser.add_argument(
        "--env-modules",
        nargs="*",
        help="Environment module types to use (e.g., simple_social_space global_information)",
    )
    add_parser.add_argument(
        "--skip-module-validation",
        action="store_true",
        help="Skip module selection validation (not recommended)",
    )
    add_parser.add_argument("--json", action="store_true", help="Output JSON")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get hypothesis details")
    get_parser.add_argument("--hypothesis-id", required=True, help="Hypothesis ID")
    get_parser.add_argument("--workspace", default=".", help="Workspace path")
    get_parser.add_argument("--json", action="store_true", help="Output JSON")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a hypothesis")
    delete_parser.add_argument("--hypothesis-id", required=True, help="Hypothesis ID")
    delete_parser.add_argument("--workspace", default=".", help="Workspace path")
    delete_parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return 1

    workspace_path = Path(args.workspace).resolve()

    if args.action == "list":
        result = list_hypotheses(workspace_path)

    elif args.action == "add":
        # Parse groups from JSON strings
        groups = []
        for group_str in args.groups:
            try:
                group_data = json.loads(group_str)
                # Validate required fields
                if "name" not in group_data:
                    print(f"Error: Group missing 'name' field: {group_str}")
                    return 1
                if "group_type" not in group_data:
                    print(
                        f"Error: Group '{group_data.get('name')}' missing 'group_type' field"
                    )
                    return 1
                if "description" not in group_data:
                    print(
                        f"Error: Group '{group_data.get('name')}' missing 'description' field"
                    )
                    return 1
                groups.append(group_data)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in group: {group_str}")
                print(f"  {e}")
                return 1

        hypothesis_data = {
            "hypothesis": {
                "description": args.description,
                "rationale": args.rationale,
            },
            "groups": groups,
        }
        if args.agent_classes:
            hypothesis_data["agent_classes"] = args.agent_classes
        if args.env_modules:
            hypothesis_data["env_modules"] = args.env_modules

        # Use enhanced validation if not skipped
        if args.skip_module_validation:
            result = add_hypothesis(workspace_path, hypothesis_data)
        else:
            result = add_hypothesis_with_validation(
                workspace_path, hypothesis_data, validate_modules=True
            )

            # If validation failed with module errors, provide guidance
            if not result.get("success") and result.get("guidance"):
                guidance = result["guidance"]
                print(f"Error: {result.get('error', 'Validation failed')}")
                print()
                print("Available Agent Types:")
                for agent_type in guidance.get("available_agents", []):
                    print(f"  - {agent_type}")
                print()
                print("Available Environment Modules:")
                for env_type in guidance.get("available_env_modules", []):
                    print(f"  - {env_type}")
                print()
                print("Please add --agent-classes and --env-modules to your command.")
                print("Example:")
                print(f'  python scripts/hypothesis.py add --description "{args.description}" \\')
                print(f'    --rationale "{args.rationale}" \\')
                print(f'    --groups \\' )
                print(f'      \'{{"name":"control","group_type":"control","description":"Baseline"}}\' \\')
                print(f'    --agent-classes person_agent \\')
                print(f'    --env-modules simple_social_space global_information')
                return 1

    elif args.action == "get":
        result = get_hypothesis(
            workspace_path=workspace_path,
            hypothesis_id=args.hypothesis_id,
        )

    elif args.action == "delete":
        result = delete_hypothesis(
            workspace_path=workspace_path,
            hypothesis_id=args.hypothesis_id,
        )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("success"):
            print(result.get("content", "Success"))
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
