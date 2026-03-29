---
name: needs
description: Update physiological/social need levels via subprocess heuristic.
script: scripts/needs.py
requires:
  - observation
---

# Needs

Subprocess skill that maintains four physiological/social need levels based on the current observation. Needs drive motivation: a hungry agent seeks food, a lonely agent seeks company.

## Understanding Human Needs

As a person, you have various **needs** that drive your behavior and decisions. Each need has an associated **satisfaction level** (ranging from 0.0 to 1.0), where lower values indicate less satisfaction and higher urgency. When a satisfaction level drops below a certain **threshold**, the corresponding need becomes urgent and should be addressed.

## Initial Values

When the agent is initialized, need satisfaction levels start at:

| Need | Initial Value | Description |
|------|---------------|-------------|
| `satiety` | 0.7 | Starting satiety level |
| `energy` | 0.3 | Starting energy level (lower, needs rest soon) |
| `safety` | 0.9 | Starting safety level (high, feeling secure) |
| `social` | 0.8 | Starting social satisfaction |

These values will change over time through natural decay and activities.

## Need Dimensions

| Need | Range | Threshold | Description |
|------|-------|-----------|-------------|
| `satiety` | 0.0–1.0 | 0.2 (T_H) | Hunger satisfaction. Decays over time; increases when eating. |
| `energy` | 0.0–1.0 | 0.2 (T_D) | Physical energy. Decays over time; increases when resting/sleeping. |
| `safety` | 0.0–1.0 | 0.2 (T_P) | Feeling of security. Drops in dangerous situations. |
| `social` | 0.0–1.0 | 0.3 (T_C) | Social fulfillment. Increases through conversation and companionship. |

## Need Priorities and Interruption Rules

Needs are organized by priority, with lower priority numbers indicating higher urgency. **Some needs can interrupt ongoing plans:**

### 1. **Satiety** (Priority 1 - Highest)
- **Meaning**: The need to eat food to satisfy your hunger
- **When it becomes urgent**: When `satiety` drops below or equals the threshold
- **Can interrupt other plans**:  **YES** - This is a basic survival need that can interrupt any ongoing activity

### 2. **Energy** (Priority 2)
- **Meaning**: The need to rest, sleep or do some leisure or relaxing activities to recover your energy
- **When it becomes urgent**: When `energy` drops below or equals the threshold
- **Can interrupt other plans**:  **YES** - Fatigue can make it difficult to continue other activities effectively

### 3. **Safety** (Priority 3)
- **Meaning**: The need to maintain or improve your safety level
- **When it becomes urgent**: When `safety` drops below or equals the threshold
- **Can interrupt other plans**:  **NO** - Safety needs are important but typically don't require immediate interruption

### 4. **Social** (Priority 4)
- **Meaning**: The need to satisfy your social needs
- **When it becomes urgent**: When `social` drops below or equals the threshold
- **Can interrupt other plans**:  **NO** - Social needs are important for well-being but can usually be planned for

### 5. **Whatever** (Priority 5 - Lowest)
- **Meaning**: You have no specific urgent needs right now
- **When it applies**: When all other needs are satisfied above their thresholds
- **Can interrupt other plans**:  **NO** - This is a passive state

## Natural Decay

Needs naturally decay each tick:
- satiety: −0.02 per tick
- energy: −0.03 per tick
- safety: varies based on environment (no natural decay)
- social: varies based on interactions (no natural decay)

Even without negative events, the agent will eventually need to eat and rest.

## Decision Rules for Determining Current Need

1. **Priority matters**: Lower priority numbers mean higher urgency. Always consider needs in priority order (1 → 2 → 3 → 4 → 5).
2. **Urgency threshold**: A need is considered urgent when its satisfaction value is **below or equal to** its threshold.
3. **Default state**: If no needs are urgent, return "whatever".

## Plan Interruption Logic

The `should_interrupt_plan` output indicates whether the current urgent need should cause the agent to abandon its current plan. **This value is written into `needs.json` each tick** so downstream skills can reliably read it from the workspace.

```json
{
  "current_need": "satiety",
  "should_interrupt_plan": true
}
```

**Interruption happens when:**
1. The current need is `satiety` or `energy` (can_interrupt = true)
2. AND the need value is at or below threshold

**Plan skill should:**
1. Read `should_interrupt_plan` from `needs.json`
2. If true, abandon current plan and generate new plan addressing the urgent need

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

The `tick` and `time` fields are auto-injected. Pass the full observation text so the heuristic can detect keywords.

## Outputs

The subprocess writes files to the agent workspace:

### `needs.json`
```json
{
  "satiety": 0.72,
  "energy": 0.65,
  "safety": 0.80,
  "social": 0.45,
  "current_need": "satiety",
  "thresholds": {
    "satiety": 0.2,
    "energy": 0.2,
    "safety": 0.2,
    "social": 0.3
  },
  "can_interrupt": {
    "satiety": true,
    "energy": true,
    "safety": false,
    "social": false
  },
  "should_interrupt_plan": true
}
```

### `current_need.txt`
The single most urgent need key (e.g. `"satiety"` or `"whatever"`)

### stdout output
```json
{
  "ok": true,
  "current_need": "satiety",
  "needs": {...},
  "thresholds": {...},
  "adjustments": [...],
  "should_interrupt_plan": true
}
```

## How Downstream Skills Should Use This

### cognition skill
- Read `current_need.txt` to understand what's driving motivation
- Read `needs.json` for nuanced multi-need awareness
- Consider `should_interrupt_plan` when updating intentions

### plan skill
- If `should_interrupt_plan` is true, abandon current plan
- Generate new plan addressing the urgent need
- Prioritize actions that address the current need

## Need Adjustment Logic

Adjustments happen based on:

1. **Natural decay** (automatic each tick)
2. **Observation keywords**:
   - Food/eating keywords → increase satiety
   - Rest/sleep keywords → increase energy
   - Danger keywords → decrease safety
   - Social keywords → increase social
   - Work keywords → decrease energy

## Notes

- The subprocess uses keyword matching—heuristic baseline. Cognition provides intelligence.
- Low values (< 0.3) indicate urgency.
- Need satisfaction influences emotion.
- Initial values are chosen to create realistic starting conditions (energy starts lower, safety higher).
