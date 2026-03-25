---
name: needs
description: Update physiological/social need levels via subprocess heuristic.
script: scripts/needs.py
requires:
  - observation
---

# Needs

Subprocess skill that maintains four physiological/social need levels based on the current observation. Needs drive motivation: a hungry agent seeks food, a lonely agent seeks company.

## Need Dimensions

| Need | Range | Description |
|------|-------|-------------|
| `satiety` | 0.0–1.0 | Hunger satisfaction. Decays over time; increases when eating. |
| `energy` | 0.0–1.0 | Physical energy. Decays over time; increases when resting/sleeping. |
| `safety` | 0.0–1.0 | Feeling of security. Drops in dangerous situations. |
| `social` | 0.0–1.0 | Social fulfillment. Increases through conversation and companionship. |

**Low values (< 0.3) indicate urgency**—the agent should prioritize addressing that need.

## How to Call

```json
{
  "tool_name": "execute_skill",
  "arguments": {
    "skill_name": "needs",
    "args": {
      "observation": "<text from observation.txt>"
    }
  }
}
```

The `tick` and `time` fields are auto-injected. Pass the full observation text so the heuristic can detect keywords (food, sleep, danger, social interactions, etc.).

## Outputs

The subprocess writes two files to the agent workspace:

- **`needs.json`** — current levels:
  ```json
  {"satiety": 0.72, "energy": 0.65, "safety": 0.80, "social": 0.45}
  ```
- **`current_need.txt`** — the single most urgent need key (e.g. `"social"`)

## How Downstream Skills Should Use This

- **cognition**: read `current_need.txt` to understand what's driving motivation. Read `needs.json` for nuanced multi-need awareness.
- **plan**: consider the current need when choosing actions. If `energy` is critically low (< 0.2), seeking rest should take priority over social goals.

## Notes

- Needs naturally decay each tick (satiety −0.02, energy −0.03), so even without negative events, the agent will eventually need to eat and rest.
- The subprocess uses simple keyword matching—it's a heuristic baseline. The real intelligence comes from cognition and plan interpreting these levels.
