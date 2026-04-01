---
name: thought
description: Write first-person inner monologue to thought.txt from observation and context.
---

# Thought

You maintain **`thought.txt`**: a short, natural inner monologue (what a human might “say in their head”).  
Anything else in the workspace may **optionally** read this file; nothing is auto-required to run before or after you.

## Inputs (read what exists)

| File | Use |
|------|-----|
| `observation.txt` | Ground truth for this tick, if the file exists |
| `needs.json`, `current_need.txt` | Optional; urgency and bodily/social state |
| `memory.jsonl` | Optional; last few lines for continuity |
| `intention.json`, `plan_state.json` | Optional; what you were doing |

## Output

- **`thought.txt`**: 1–4 sentences, first person, concrete (places/people from observation when available). No JSON.

## Voice and content

1. Tie what happened recently to **goals, values, and personality** (Agent Identity / profile).
2. If `needs.json` exists, let urgency (hunger, fatigue, etc.) **color tone**, not only factual mentions.
3. Use **full sentences**, one coherent inner voice—never a task checklist.
4. Prefer **concrete** who/where over slogans.

## Workflow

1. `workspace_read` the inputs above (skip missing files).
2. Write or update `thought.txt` via `workspace_write`.
3. `done` when finished.

## Notes

- This skill only owns **`thought.txt`**. Do not write `emotion.json` or `intention.json` here.
- Keep tone consistent with Agent Identity (profile) when relevant.
- If `observation.txt` is missing or empty, write a brief note that perception is unclear rather than inventing scenery.
