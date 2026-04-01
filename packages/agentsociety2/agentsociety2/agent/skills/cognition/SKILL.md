---
name: cognition
description: Produce emotion.json and intention.json from workspace context (observation, optional thought, optional needs, optional memory).
---

# Cognition

**You only write:** `emotion.json` and `intention.json`.

**You do not write:** `thought.txt` (that is the `thought` skill), `needs.json` / `current_need.txt` (owned by the `needs` subprocess when used), or `plan_state.json`.

There is **no required order** with other built-in skills: use whatever files already exist; missing files mean you reason with less context.

## Optional inputs (read if present)

| File | Use |
|------|-----|
| `observation.txt` | Main grounding for this tick |
| `thought.txt` | Inner monologue; if missing, infer mental tone from observation + profile only |
| `needs.json`, `current_need.txt` | **Read-only** urgency context if the needs skill has run |
| `memory.jsonl` | Last 5–10 lines optional |
| `emotion.json`, `intention.json` | Continuity from prior ticks |
| `plan_state.json` | Whether a multi-step plan is in flight (optional) |

Also use **Agent Identity** from the system prompt. Other JSON in the workspace (`beliefs.json`, etc.) — read only if present.

## What to do (one pass)

1. Integrate whatever inputs exist into one appraisal.
2. Write **`emotion.json`**: `primary`, dimensional **`intensities`**, plus `valence` / `arousal` / `note` as in the schema below.
3. Write **`intention.json`**: one chosen goal with TPB scores.

## Emotion

**Intensities** (`sadness`, `joy`, `fear`, `disgust`, `anger`, `surprise`) are integers **0–10**:

| Band | Level |
|------|--------|
| 0–2 | very low |
| 3–4 | low |
| 5–6 | moderate |
| 7–8 | high |
| 9–10 | very high |

- Combine **recent events** (`memory.jsonl` tail, `observation.txt`) with **need levels** from `needs.json` when present: urgent unmet needs push negative dimensions up; satisfied needs support positive ones.
- If a previous `emotion.json` exists, **change intensities only when the situation meaningfully shifted**; otherwise stay near prior values.

**`primary`**: exactly **one** English label, case-sensitive, from:

`Joy`, `Distress`, `Resentment`, `Pity`, `Hope`, `Fear`, `Satisfaction`, `Relief`, `Disappointment`, `Pride`, `Admiration`, `Shame`, `Reproach`, `Liking`, `Disliking`, `Gratitude`, `Anger`, `Gratification`, `Remorse`, `Love`, `Hate`

## Intention (Theory of Planned Behavior)

| Field | Range | Meaning |
|-------|-------|---------|
| `attitude` | 0–1 | How much you favor doing it |
| `subjective_norm` | 0–1 | Social pressure / what others expect |
| `perceived_control` | 0–1 | How controllable / feasible it feels |

Higher values on all three → stronger commitment. **`priority`**: lower number = more urgent this tick.

**Selection procedure**

1. List up to **5** candidate goals (fewer is fine).
2. When `current_need.txt` / `needs.json` flags satiety, energy, safety, or social as urgent, **prefer candidates that address that**; if the active need is `whatever`, leisure or exploration is appropriate.
3. Score each candidate with the three TPB fields; assign `priority` to each.
4. **Emit only the best candidate** as `intention.json` (lowest `priority` wins ties you care about).
5. Phrase `intention` as a **goal** (“Eat lunch at the café”), not step-by-step motor instructions.

**Need ordering (for your own reasoning):** compare satisfaction to thresholds in order **satiety → energy → safety → social**; if none are at or below threshold, treat the situation as no single urgent drive.

## Output files

### `emotion.json`

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

### `intention.json`

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

## Execution sequence

1. `workspace_read` any of the optional inputs that exist (skip missing paths).
2. `workspace_write("emotion.json", ...)`
3. `workspace_write("intention.json", ...)`
4. `done`

## Notes

- Do **not** duplicate the needs subprocess: never overwrite `needs.json` here.
- Intentions should be feasible given the latest observation; if the situation is unclear, prefer low-risk intentions (`wait`, `observe`, `move to safer area`) over fantasy.
