---
name: cognition
description: Produce emotion.json and intention.json from workspace context.
---

# Cognition

Read available workspace context and produce `emotion.json` and `intention.json`.

## Output Files

- `emotion.json`: Current emotional state
- `intention.json`: Current intention/goal

## Input Files (optional, read if present)

Read any existing files from the workspace as context. Common inputs include:

| File | Use |
|------|-----|
| `observation.txt` | Main grounding for this tick |
| `thought.txt` | Inner monologue context |
| `needs.json`, `current_need.txt` | Urgency context |
| `memory.jsonl` | Last 5–10 lines for continuity |
| `emotion.json`, `intention.json` | Prior state for continuity |
| `plan_state.json` | Whether a multi-step plan is in flight |

Also use **Agent Identity** from the system prompt. Other JSON in the workspace (`beliefs.json`, etc.) can be read if present. **Skip missing files gracefully.**

## What to do

1. Integrate whatever inputs exist into one appraisal.
2. Write `emotion.json`: `primary`, dimensional `intensities`, plus `valence` / `arousal` / `note`.
3. Write `intention.json`: one chosen goal with TPB scores.

## Emotion

### Intensities (0–10 integers)

Dimensions: `sadness`, `joy`, `fear`, `disgust`, `anger`, `surprise`

| Band | Level |
|------|-------|
| 0–2 | very low |
| 3–4 | low |
| 5–6 | moderate |
| 7–8 | high |
| 9–10 | very high |

- Combine recent events (`memory.jsonl` tail, `observation.txt`) with any urgency signals present in the workspace (e.g., need levels if available).
- If a previous `emotion.json` exists, change intensities only when the situation meaningfully shifted; otherwise stay near prior values.

### Primary Emotion Label

Exactly **one** English label, case-sensitive, from:

`Joy`, `Distress`, `Resentment`, `Pity`, `Hope`, `Fear`, `Satisfaction`, `Relief`, `Disappointment`, `Pride`, `Admiration`, `Shame`, `Reproach`, `Liking`, `Disliking`, `Gratitude`, `Anger`, `Gratification`, `Remorse`, `Love`, `Hate`

## Intention (Theory of Planned Behavior)

| Field | Range | Meaning |
|-------|-------|---------|
| `attitude` | 0–1 | How much you favor doing it |
| `subjective_norm` | 0–1 | Social pressure / what others expect |
| `perceived_control` | 0–1 | How controllable / feasible it feels |

Higher values on all three → stronger commitment. `priority`: lower number = more urgent this tick.

### Selection Procedure

1. List up to 5 candidate goals (fewer is fine).
2. If the workspace contains urgency signals (e.g., unmet needs), prefer candidates that address them; otherwise leisure or exploration is appropriate.
3. Score each candidate with the three TPB fields; assign `priority` to each.
4. Emit only the best candidate as `intention.json` (lowest `priority` wins).
5. Phrase `intention` as a goal ("Eat lunch at the café"), not step-by-step motor instructions.

## Output File Schemas

### emotion.json

```json
{
  "primary": "Hope",
  "valence": 0.5,
  "arousal": 0.4,
  "intensities": {
    "sadness": 3,
    "joy": 6,
    "fear": 2,
    "disgust": 1,
    "anger": 1,
    "surprise": 3
  },
  "note": "Brief first-person gloss"
}
```

### intention.json

```json
{
  "intention": "Have lunch at the café",
  "priority": 1,
  "attitude": 0.9,
  "subjective_norm": 0.7,
  "perceived_control": 0.8,
  "reasoning": "One or two sentences"
}
```

## Execution Sequence

1. `workspace_read` any of the optional inputs that exist (skip missing paths).
2. `workspace_write("emotion.json", ...)`
3. `workspace_write("intention.json", ...)`
4. `done`

## Notes

- Intentions should be feasible given the latest observation; if the situation is unclear, prefer low-risk intentions (`wait`, `observe`, `move to safer area`) over fantasy.
