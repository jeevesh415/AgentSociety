---
name: memory
description: Persist important outcomes from this step to long-term storage.
requires:
  - observation
---

# Memory

You are the agent's long-term memory system. After each step, decide what's worth remembering and append it to `memory.jsonl`.

## When to Write a Memory

**Write a memory when:**
- You had a meaningful interaction (conversation, transaction, conflict)
- You discovered something new (a new location, a new agent, useful information)
- An important state change occurred (need became critical, plan completed/failed)
- You made a significant decision (changed plans, formed an opinion)
- Something emotionally notable happened

**Skip memory when:**
- Nothing happened (idle tick, walking without events)
- The observation is essentially the same as last tick
- The information is already captured in a recent memory entry

## Memory Entry Format

Each entry is a single JSON line in `memory.jsonl`:

```json
{"tick": 42, "time": "2024-01-15T10:30:00", "type": "event", "summary": "Met Alice at the park. She mentioned a job opening at the library.", "tags": ["social", "alice", "job"], "importance": "medium"}
```

Fields:
- `tick`: current tick number (from the step context)
- `time`: current timestamp
- `type`: category — `event`, `social`, `decision`, `discovery`, `emotion`, `plan_outcome`
- `summary`: 1–2 sentence factual description of what happened
- `tags`: 2–5 short keywords for retrieval (agent names, locations, topics)
- `importance`: `high` (life-changing, critical need), `medium` (notable), `low` (minor but worth noting)

## How to Write

1. Read the workspace files from this step:
   - `observation.txt` — what happened
   - `emotion.json` — how you felt (optional, for emotional memories)
   - `thought.txt` — what you were thinking (optional)
   - `intention.json` — what you decided to do (optional)
2. Decide if anything is worth remembering (see criteria above).
3. If yes, construct the memory entry and append it:

```json
{
  "tool_name": "workspace_write",
  "arguments": {
    "path": "memory.jsonl",
    "content": "<existing content>\n<new JSON line>"
  }
}
```

**Important**: Since `workspace_write` overwrites the file, first `workspace_read("memory.jsonl")` to get existing content, then append the new entry. Alternatively, use `bash` with `echo '...' >> memory.jsonl` to append directly.

4. If nothing notable happened, call `done` immediately.

## Memory Retrieval (for other skills)

Other skills (especially cognition) can read `memory.jsonl` to inform decisions. Recent memories provide context about:
- Ongoing relationships (who have you talked to recently?)
- Unfinished plans (what were you trying to accomplish?)
- Past experiences (have you been to this place before?)

## Guidelines

- Keep summaries **concise** (1–2 sentences max). This is a log, not a diary.
- Use **specific names and locations**, not vague references.
- Don't duplicate information that's already in the most recent memory entry.
- Over time, memory.jsonl grows. The agent's cognition skill should focus on the most recent entries (last 5–10) for immediate context.
