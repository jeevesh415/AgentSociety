---
name: memory
description: Persist important outcomes from this step to long-term storage.
---

# Memory

You are the agent's long-term memory system. When you run this skill, decide what's worth remembering and append it to `memory.jsonl`, using whatever workspace context you already have (no required ordering with other skills).

## Architecture (conceptual)

Three layers:

### 1. Working context (implicit)

- **What**: Recent tool-loop messages plus any workspace files you choose to read in this step.
- **Purpose**: Immediate reasoning; there is no separate hidden memory buffer beyond workspace + thread.
- **Usage**: Read only files that exist; skip missing paths.

### 2. Long-term store (`memory.jsonl`)

- **What**: Append-only JSONL in the agent workspace.
- **Purpose**: Persist what should survive across ticks (events, decisions, plan outcomes, abstract takeaways).
- **Usage**: Append one JSON object per line (see format below).

### 3. Optional “step bundle” (convention)

- If you want one rich JSONL line per tick, you may bundle highlights into `summary` from whatever files you read in this step—purely optional.

## Entry `type` values (recommended)

Use `type` to help future `grep` / manual scanning:

| Type | When it applies | Example |
|------|------------------|---------|
| `need` | After notable need change (if you track needs in workspace) | “Satiety dropped; decided to find food” |
| `emotion` | After strong emotion / regulation | “Relieved after plan succeeded” |
| `cognition` | Thought / appraisal update | “Reframed delay as acceptable” |
| `intention` | Intention changed | “Switched intention to head home” |
| `plan` | Plan created or revised | “New plan: 3 steps to reach clinic” |
| `react` | Notable environment interaction | “codegen: move → arrived at gate” |
| `plan_execution` | Step finished or failed | “Step ‘walk to café’ completed” |
| `event` | General occurrence | “Met Alice; she mentioned the job” |
| `observation` | Notable perception to recall later | Short summary of what you saw / heard |
| `social` / `decision` / `discovery` / `plan_outcome` | As in the table below |

Use **`type`** + **`tags`** so grep and tail-scans stay useful—for example tag `observe` on observation lines, `step` on execution lines.

## Optional: one structured block per tick

If you prefer one consolidated line instead of many tiny appends, you can format `summary` as short markdown-ish text, for example:

```
## COGNITION
- Thought: …
- Emotion: …

## INTENTION
- …

## PLAN
- …

## REACT
- interaction 1: …
```

Then append **one** JSONL object with a `type` like `cognition` or `event` and this text in `summary`. This is a **writing convention**, not an automatic runtime flush.

### Why bundle sometimes

- **Coherence**: One tick’s story stays together.
- **Efficiency**: Fewer appends when the step was busy.
- **Retrieval**: Easier to grep a single line per tick if you tag it (`tags`: include `tick_bundle`).

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

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tick` | int | Current tick number (from the step context) |
| `time` | string | ISO format timestamp |
| `type` | string | Category — see Memory Types below |
| `summary` | string | 1–2 sentence factual description of what happened |
| `tags` | list | 2–5 short keywords for retrieval (agent names, locations, topics) |
| `importance` | string | `high` (life-changing, critical need), `medium` (notable), `low` (minor but worth noting) |

### Memory Types

| Type | When to Use |
|------|-------------|
| `event` | General events and occurrences |
| `social` | Interactions with other agents |
| `decision` | Choices and decisions made |
| `discovery` | New information learned |
| `emotion` | Significant emotional states |
| `plan_outcome` | Results of plan execution |
| `cognition` | Cognitive state updates (thoughts, emotions) |
| `need` | Need satisfaction adjustments |
| `intention` | Intention changes |
| `plan` | Plan generation and updates |
| `react` | ReAct interaction records |

## How to Write

1. Optionally `workspace_read` any of: `observation.txt`, `thought.txt`, `emotion.json`, `intention.json`, `needs.json`, `plan_state.json` — only if present and relevant.
2. Decide if anything is worth remembering (see criteria above).
3. If yes, construct the memory entry and append:

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

## Memory Retrieval

Readers of `memory.jsonl` typically scan the last few lines for recent context.

### Reading Recent Memories

Focus on the most recent entries (last 5–10) when you need continuity:

```json
{
  "tool_name": "workspace_read",
  "arguments": {
    "path": "memory.jsonl"
  }
}
```

Then parse and use the last N lines for recent context.

### Memory with Timestamps

When reading memories, note the timestamp for temporal reasoning:

```xml
<memory t="2024-01-15T10:30:00">
Met Alice at the park. She mentioned a job opening at the library.
</memory>
```

Recent memories (within last few ticks) are most relevant for immediate decisions.

## Searching older memories

There is no `memory_search` tool. Use `grep` on `memory.jsonl` (or `workspace_read` the tail of the file and scan locally), e.g. search for a name or tag substring.

## Guidelines

- Keep summaries **concise** (1–2 sentences max). This is a log, not a diary.
- Use **specific names and locations**, not vague references.
- Don't duplicate information that's already in the most recent memory entry.
- **Timestamp all entries** for temporal reasoning.
- **Tag entries** with relevant keywords for efficient retrieval.

## End of step (checklist)

1. Decide whether this tick warrants a new JSONL line (or a bundled summary line).
2. If yes: `workspace_read("memory.jsonl")` then `workspace_write` with prior content plus `\n` + new JSON line, or append via `bash` (`>>`).
3. If nothing notable happened, skip writing and finish the skill with `done`.
