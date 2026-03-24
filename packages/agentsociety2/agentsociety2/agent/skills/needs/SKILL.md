---
name: needs
description: Adjust physiological and social need satisfaction levels (satiety, energy, safety, social). Activate when the agent's physical or social state may have changed.
trigger: always
script: scripts/needs.py
priority: 30
requires:
  - observation
provides:
  - need_adjustment
  - current_need
---

# Needs

Models four fundamental human needs with continuous satisfaction levels (0–1).

## Need Types

| Need | Description | Threshold |
|------|-------------|-----------|
| **Satiety** | Hunger / food satisfaction | T_H (default 0.2) |
| **Energy** | Rest / sleep satisfaction | T_D (default 0.2) |
| **Safety** | Physical and psychological safety | T_P (default 0.2) |
| **Social** | Social connection and belonging | T_C (default 0.3) |

## What It Does

1. After observation, the agent reviews its recent memories and current environment.
2. An LLM call decides which satisfaction levels to adjust (increase / decrease / maintain) with reasoning.
3. The most urgent need (lowest satisfaction relative to its threshold) becomes `current_need`, steering downstream intention and planning.

## Behavioral Guidelines

- Needs decay naturally if not addressed; successful actions restore them.
- The LLM considers time of day, recent activities, and environment when adjusting needs.
- Need adjustments are recorded as cognition memory for later reflection.

## Data Models

```
Satisfactions(satiety, energy, safety, social)   # 0.0–1.0 each
NeedAdjustment(need_type, adjustment_type, amount, reasoning)
NeedAdjustmentResult(adjustments[], reasoning)
```
