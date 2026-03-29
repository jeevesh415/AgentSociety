---
name: memory
description: Persist important outcomes from this step to long-term storage.
requires:
  - observation
---

# Memory

You are the agent's long-term memory system. After each step, decide what's worth remembering and append it to `memory.jsonl`.

## Memory Architecture

The agent maintains multiple memory subsystems:

### 1. Short-term Memory (Working Memory)

- **Storage**: In-memory list, recent N entries (default: 10)
- **Purpose**: Quick access to recent events for immediate reasoning
- **Content**: Recent observations, actions, and their outcomes
- **Window Size**: Configurable via `short_memory_window_size`, typically 10 entries
- **Usage**: Most recent memories are included in agent state for LLM prompts

### 2. Long-term Memory (`memory.jsonl`)

- **Storage**: Persistent JSONL file
- **Purpose**: Persistent storage of important experiences
- **Content**: Significant events, decisions, social interactions, discoveries

### 3. Cognition Memory (Step-level Buffer)

- **Storage**: Temporary buffer cleared after each step
- **Purpose**: Collect cognitive updates during a step, then flush to long-term memory
- **Content**: Need adjustments, emotion updates, intention changes, plan updates, ReAct interactions
- **Types**: `need`, `emotion`, `cognition`, `intention`, `plan`, `react`, `plan_execution`

## Cognition Memory Types

During a step, various types of cognition memories are collected:

| Type | When Added | Example |
|------|------------|---------|
| `need` | After need adjustment | "Adjusted needs based on memories: satiety low after not eating" |
| `emotion` | After emotion update for plan outcome | "I feel relieved that I successfully completed my plan" |
| `cognition` | After thought/emotion update | "Updated thought: I should find food. Updated emotion: Distress" |
| `intention` | After intention update | "Selected intention: Find food (Priority: 1)" |
| `plan` | After plan generation | "Generated plan for intention: Find food. Steps: 1. Look for restaurants..." |
| `react` | During ReAct interactions | "ReAct interaction 1: Move to café -> Successfully moved" |
| `plan_execution` | After step execution completes | "Executed step: Walk to café. Status: completed. Result: Arrived at café" |

## Cognition Memory Flush

At the **end of each step**, all cognition memories are structured and flushed to long-term memory:

### Flush Process

1. **Group by type**: Organize memories by their type
2. **Format as structured text**:
   ```
   ## COGNITION
   - Updated thought: I should find something to eat soon.
   - Updated emotion: Distress

   ## NEED
   - Adjusted needs based on memories: satiety is low after not eating

   ## INTENTION
   - Selected intention: Find food (Priority: 1)

   ## PLAN
   - Generated plan for intention: Find food
     1. Look for nearby restaurants
     2. Go to the closest one
     3. Order food

   ## REACT
   - ReAct interaction 1 for step 'Walk to café': Move to café -> Successfully moved
   - ReAct interaction 2 for step 'Walk to café': Enter café -> Entered

   ## PLAN_EXECUTION
   - Executed step: Walk to café. Status: completed. Interactions: 2. Result: Arrived at café entrance
   ```
3. **Write to memory.jsonl** as a single structured entry
4. **Clear cognition memory buffer** for next step

### Why Flush at Step End?

- **Efficiency**: One structured write instead of many small writes
- **Coherence**: Related information stays together
- **Retrievability**: Easier to search and understand step activities

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

1. Read the workspace files from this step:
   - `observation.txt` — what happened
   - `emotion.json` — how you felt (optional, for emotional memories)
   - `thought.txt` — what you were thinking (optional)
   - `intention.json` — what you decided to do (optional)
   - `needs.json` — current need levels (optional)
   - `plan_state.json` — plan status (optional)
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

## Memory Retrieval (for other skills)

Other skills (especially cognition) can read `memory.jsonl` to inform decisions. Recent memories provide context about:

- **Ongoing relationships**: Who have you talked to recently?
- **Unfinished plans**: What were you trying to accomplish?
- **Past experiences**: Have you been to this place before?
- **Emotional context**: How were you feeling recently?

### Reading Recent Memories

Focus on the most recent entries (last 5–10) for immediate context:

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

## Memory Search

When planning or reasoning about a specific topic, search for related memories:

```json
{
  "tool_name": "memory_search",
  "arguments": {
    "query": "Alice",
    "limit": 5
  }
}
```

This returns memories tagged with or containing the search term.

## Guidelines

- Keep summaries **concise** (1–2 sentences max). This is a log, not a diary.
- Use **specific names and locations**, not vague references.
- Don't duplicate information that's already in the most recent memory entry.
- Over time, memory.jsonl grows. The agent's cognition skill should focus on the most recent entries (last 5–10) for immediate context.
- **Timestamp all entries** for temporal reasoning.
- **Tag entries** with relevant keywords for efficient retrieval.

## Memory-Need-Emotion Integration

Memory influences needs and emotions:

| Memory Content | Effect on State |
|----------------|-----------------|
| Recent eating | Increase satiety |
| Social interaction | Increase social satisfaction |
| Dangerous situation | Decrease safety, increase fear |
| Success/achievement | Increase positive emotions, potentially increase safety/energy |
| Failure | Decrease positive emotions, potentially decrease safety |

When writing memories, consider how they should affect the agent's state in subsequent ticks.

## Step End Memory Routine

At the end of each agent step:

1. **Flush cognition memory**: Convert buffer to structured text, write to memory.jsonl
2. **Write observation memory**: If observation was notable, add as separate entry
3. **Update short-term memory**: Add to in-memory recent list
4. **Trim short-term memory**: Remove oldest entries if exceeding window size
5. **Keep outputs consistent**: ensure `emotion.json`, `thought.txt`, `intention.json`, `plan_state.json` reflect the latest state
