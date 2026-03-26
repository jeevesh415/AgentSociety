---
name: donation-game
description: Reputation-based donation game skills for agents in ReputationGameEnv. Activate when the agent observes reputation information, donation opportunities, or needs to make cooperation/defection decisions.
requires:
  - observation
---

# Donation Game

Provides decision-making capabilities when the agent participates in a reputation-based donation game environment.

## What It Does

1. Observes the agent's current reputation and payoff
2. Evaluates other agents' reputations (if information is available)
3. Makes cooperation or defection decisions based on strategy and social norms
4. Executes donation actions via `codegen`

## When To Activate

- Agent needs to make a donation decision (cooperate or defect)
- Agent observes reputation information about other agents
- Agent wants to check current payoff or game state

## Environment Tools Available

The ReputationGameEnv provides these tools via `codegen`:

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_agent_reputation(agent_id)` | Get reputation of an agent | agent_id: int |
| `get_agent_payoff(agent_id)` | Get cumulative payoff | agent_id: int |
| `execute_donation(donor_id, recipient_id, action)` | Make a donation | donor_id, recipient_id, action: "cooperate"/"defect" |
| `get_population_size()` | Get total agents | - |
| `get_global_statistics()` | Get cooperation stats | - |
| `get_reputation_distribution()` | Get reputation distribution | - |
| `get_public_action_log(limit)` | Get recent actions | limit: int (default 20) |
| `get_agent_history(agent_id, limit)` | Get agent's history | agent_id, limit |

## How To Play

Each round, you should:

1. **Observe**: Check your current reputation and payoff
2. **Decide**: Choose whether to cooperate or defect with a recipient
3. **Act**: Execute your decision via `execute_donation`

### Example codegen calls

**Check your own status:**
```json
{
  "tool_name": "codegen",
  "arguments": {
    "instruction": "Get my current reputation and payoff. My agent ID is specified in my profile.",
    "ctx": {"agent_id": 0}
  }
}
```

**Make a donation (cooperate):**
```json
{
  "tool_name": "codegen",
  "arguments": {
    "instruction": "Execute a donation: I (agent 0) want to cooperate with agent 1. Call execute_donation with donor_id=0, recipient_id=1, action='cooperate'.",
    "ctx": {"donor_id": 0, "recipient_id": 1, "action": "cooperate"}
  }
}
```

**Check other agents' reputation (if visible):**
```json
{
  "tool_name": "codegen",
  "arguments": {
    "instruction": "Get the reputation of all agents in the population.",
    "ctx": {}
  }
}
```

## Social Norms

The environment uses one of three social norms:

1. **Stern Judging**: Cooperating with good reputation = good; Defecting with bad reputation = good
2. **Image Score**: Cooperate = good reputation; Defect = bad reputation
3. **Simple Standing**: Cooperating with good = good; Defecting = bad

Your reputation changes based on your action AND the recipient's reputation!

## Strategy Tips

- **Check information availability**: If reputation is "unknown", you cannot see others' reputations
- **Consider reputation impact**: Your action affects YOUR reputation, not the recipient's
- **Balance short-term vs long-term**: Defecting saves cost but may hurt your reputation
- **Pay attention to social norm**: Different norms reward different behaviors

## Payoffs

- **Cooperate**: You pay COST (1), recipient gains BENEFIT (3)
- **Defect**: No cost, no benefit to anyone
