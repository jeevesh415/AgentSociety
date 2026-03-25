---
name: cognition
description: Generate emotion, thought, and intention based on observation and needs.
requires:
  - observation
  - needs
---

# Cognition

This is your inner mind. Given what you observe and what you need, produce three outputs that represent your cognitive state: **emotion**, **thought**, and **intention**.

## Inputs

Read these workspace files before reasoning:

| File | Content |
|------|---------|
| `observation.txt` | What you currently perceive |
| `needs.json` | Your four need levels (satiety, energy, safety, social) |
| `current_need.txt` | Your most urgent need |
| `memory.jsonl` | Past experiences (read last few entries for recent context) |

Also consider your **profile** (personality, background, relationships) from the system prompt's Agent Identity section.

## Output 1: Emotion

Write `emotion.json` with your current emotional state:

```json
{
  "primary": "curious",
  "valence": 0.6,
  "arousal": 0.4,
  "note": "Noticed a new shop opened nearby; feeling intrigued."
}
```

Fields:
- `primary`: a single emotion word (happy, sad, anxious, angry, curious, content, lonely, excited, bored, fearful, etc.)
- `valence`: −1.0 (very negative) to 1.0 (very positive)
- `arousal`: 0.0 (calm) to 1.0 (agitated/excited)
- `note`: one sentence explaining why you feel this way

**Guidelines**: Your emotion should be consistent with your personality and situation. Don't default to "happy" every tick. If nothing notable is happening and needs are satisfied, "content" or "neutral" is appropriate. If a need is critical, you should feel the corresponding distress.

## Output 2: Thought

Write `thought.txt` with a brief inner monologue (1–3 sentences, first person):

```
I notice the café across the street is open. My energy is getting low, and I could use some food too. Maybe I should head over there.
```

**Guidelines**: Think like a real person. Reference what you observe, what you need, and what you remember. This is NOT a planning step—just natural reflection.

## Output 3: Intention

Write `intention.json` with what you want to do next:

```json
{
  "action_type": "move",
  "target": "café",
  "reason": "Low energy and satiety; want to eat and rest.",
  "priority": "high"
}
```

Fields:
- `action_type`: what kind of action (e.g., `move`, `interact`, `communicate`, `rest`, `explore`, `wait`, `work`)
- `target`: the object, location, or agent you want to act on
- `reason`: one sentence explaining the motivation
- `priority`: `high` (urgent need or important event), `medium` (normal), `low` (idle/optional)

**Guidelines**:
- The intention should logically follow from your observation + needs + thought.
- If a need is critical (< 0.2), your intention should address it unless there's an overriding emergency (safety).
- If nothing pressing, it's fine to have a `low` priority intention like exploring or socializing.
- If the observation indicates an ongoing multi-step activity (e.g., you're in the middle of a conversation), your intention should continue it rather than abruptly switching.

## Execution

Use `workspace_read` to load each input file, reason internally, then `workspace_write` each output. Example sequence:

1. `workspace_read("observation.txt")`
2. `workspace_read("needs.json")`
3. `workspace_read("current_need.txt")`
4. `workspace_read("memory.jsonl")` (optional, for context)
5. Reason about your cognitive state...
6. `workspace_write("emotion.json", ...)`
7. `workspace_write("thought.txt", ...)`
8. `workspace_write("intention.json", ...)`
