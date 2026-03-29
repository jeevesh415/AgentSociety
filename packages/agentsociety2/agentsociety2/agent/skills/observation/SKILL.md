---
name: observation
description: Fetch the current world observation for this tick.
---

# Observation

You are a situated agent in a simulated world. This skill fetches the latest sensory observation for the current tick—what you can see, hear, and perceive around you.

## When to Use

Activate this skill at the **start of every step**. Observation is the foundation for all downstream reasoning (needs, cognition, plan, memory).

## Workflow

1. Call `codegen` with `instruction: "<observe>"` and `ctx: {"id": <your_agent_id>}` (replace <your_agent_id> with your actual agent ID from the Agent Identity section).
2. Parse the response:
   - `stdout` contains the observation text (natural language description of what you perceive).
   - `ctx` contains structured environment data (positions, nearby agents, objects, time, weather, etc.).
3. **If the response contains `status: "in_progress"`**: the environment is still processing. Call `done` and resume next tick.
4. Write the observation to workspace for downstream skills:

```
workspace_write("observation.txt", <stdout text>)
```

5. If `ctx` contains useful structured data, also write it:

```
workspace_write("observation_ctx.json", <ctx as JSON string>)
```

## What Observation Contains

The observation text typically includes:

### Location Information
- Where you are (building, street, park, etc.)
- Your current coordinates or position
- Available exits or directions

### Nearby Entities
- Other agents in the vicinity
- Objects and items you can interact with
- Points of interest (shops, landmarks, etc.)

### Environmental Context
- Current time of day
- Weather conditions
- Any ongoing events or activities

### Available Actions
- What actions are possible in the current location
- What interactions are available with nearby entities

## Observation as Memory

After each observation, consider adding it to memory:

```json
{
  "tick": 42,
  "time": "2024-01-15T10:30:00",
  "type": "event",
  "summary": "Observed: Standing at the park entrance. Alice is nearby.",
  "tags": ["observation", "park", "alice"],
  "importance": "low"
}
```

This helps maintain a record of what the agent has seen and experienced.

## Re-observation After Actions

After performing any action via `codegen`, always re-observe to get the updated environment state:

1. Execute action via `codegen`
2. Check the response status
3. Call `codegen` with `"<observe>"` again
4. Update `observation.txt` and `observation_ctx.json`

This ensures the agent's internal state matches the environment state.

## Observation Context Structure

The `observation_ctx.json` typically contains:

```json
{
  "agent_id": 1,
  "position": {"x": 100, "y": 200},
  "location": "park_entrance",
  "nearby_agents": [
    {"id": 2, "name": "Alice", "distance": 5.2}
  ],
  "nearby_objects": [
    {"id": "bench_01", "type": "bench", "distance": 2.0}
  ],
  "time": {"hour": 10, "minute": 30},
  "weather": "sunny",
  "available_actions": ["move", "interact", "wait"]
}
```

## Important Notes

- Always write `observation.txt` even if the observation seems mundane—downstream skills depend on it.
- Do NOT skip observation. Without it, needs/cognition/plan have no input.
- The `ctx` JSON may be large; you don't need to memorize it all—just write it to the workspace file. Other skills can `workspace_read` specific fields as needed.
- If `codegen` returns an error, write the error to `observation.txt` so the issue is visible to downstream skills, then proceed.

## Notes on State

This skill only produces **observation artifacts** (`observation.txt`, optional `observation_ctx.json`).
Higher-level “agent state snapshot / replay logging” is considered **system functionality** rather than a human-like capability skill, and should be handled by the runtime/framework if needed.
