"""
Donation game decision helper script.
This script can be executed by PersonAgent to help make donation decisions.
"""

import json
import sys
from typing import Optional


def analyze_reputation(
    my_reputation: str,
    recipient_reputation: Optional[str],
    social_norm: str = "stern_judging"
) -> dict:
    """
    Analyze the reputation implications of different actions.

    Args:
        my_reputation: My current reputation ("good" or "bad")
        recipient_reputation: Recipient's reputation ("good", "bad", or "unknown")
        social_norm: The social norm in use

    Returns:
        Dictionary with analysis results
    """
    # If we can't see recipient's reputation, use a default assumption
    if recipient_reputation is None or recipient_reputation == "unknown":
        recipient_reputation = "good"  # Assume good by default

    analysis = {
        "my_reputation": my_reputation,
        "recipient_reputation": recipient_reputation,
        "social_norm": social_norm,
        "cooperation_outcome": {},
        "defection_outcome": {}
    }

    if social_norm == "stern_judging":
        # Stern Judging: C with G -> G, D with G -> B, C with B -> B, D with B -> G
        if recipient_reputation == "good":
            analysis["cooperation_outcome"]["new_reputation"] = "good"
            analysis["defection_outcome"]["new_reputation"] = "bad"
        else:
            analysis["cooperation_outcome"]["new_reputation"] = "bad"
            analysis["defection_outcome"]["new_reputation"] = "good"

    elif social_norm == "image_score":
        # Image Score: C -> G, D -> B (regardless of recipient)
        analysis["cooperation_outcome"]["new_reputation"] = "good"
        analysis["defection_outcome"]["new_reputation"] = "bad"

    elif social_norm == "simple_standing":
        # Simple Standing: C with G -> G, C with B -> B, D -> B
        if recipient_reputation == "good":
            analysis["cooperation_outcome"]["new_reputation"] = "good"
        else:
            analysis["cooperation_outcome"]["new_reputation"] = "bad"
        analysis["defection_outcome"]["new_reputation"] = "bad"

    # Calculate payoff implications
    analysis["cooperation_outcome"]["my_payoff_change"] = -1  # COST
    analysis["cooperation_outcome"]["recipient_payoff_change"] = 3  # BENEFIT
    analysis["defection_outcome"]["my_payoff_change"] = 0
    analysis["defection_outcome"]["recipient_payoff_change"] = 0

    return analysis


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON arguments"}))
        sys.exit(1)

    action = args.get("action", "analyze")

    if action == "analyze":
        result = analyze_reputation(
            my_reputation=args.get("my_reputation", "good"),
            recipient_reputation=args.get("recipient_reputation"),
            social_norm=args.get("social_norm", "stern_judging")
        )
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
