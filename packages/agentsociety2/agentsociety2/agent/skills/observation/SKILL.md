---
name: observation
description: Fetch the current world observation for this tick.
---

# Observation

You are a situated agent in a simulated world. This skill fetches the latest sensory observation for the current tick—what you can see, hear, and perceive around you.

## When to Use

Activate this skill at the **start of every step**. Observation is the foundation for all downstream reasoning (needs, cognition, plan, memory).

## Workflow

1. Call `codegen` with `instruction: "<observe>"` and `ctx: {}`.
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
- **Location**: where you are (building, street, park, etc.)
- **Nearby entities**: other agents, objects, items you can interact with
- **Events**: things happening around you (conversations, weather changes, etc.)
- **Time/state**: current time of day, any ongoing activities

## Important Notes

- Always write `observation.txt` even if the observation seems mundane—downstream skills depend on it.
- Do NOT skip observation. Without it, needs/cognition/plan have no input.
- The `ctx` JSON may be large; you don't need to memorize it all—just write it to the workspace file. Other skills can `workspace_read` specific fields as needed.
- If `codegen` returns an error, write the error to `observation.txt` so the issue is visible to downstream skills, then proceed.
