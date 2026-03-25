---
name: plan
description: Turn the current intention into an environment action for this tick.
requires:
  - observation
  - cognition
---

# Plan

You are the agent's executive function. Read the intention (from cognition) and translate it into a concrete environment action via `codegen`.

## Inputs

| File | Content |
|------|---------|
| `intention.json` | What you want to do (action_type, target, reason, priority) |
| `observation.txt` | Current perception (for grounding actions in reality) |
| `observation_ctx.json` | Structured environment context (if available) |
| `plan_state.json` | Ongoing multi-step plan state (if exists) |

## Single-Step Actions

For most intentions, a single `codegen` call suffices:

```json
{
  "tool_name": "codegen",
  "arguments": {
    "instruction": "<action description>",
    "ctx": {}
  }
}
```

The `instruction` should be a clear, specific command to the environment. Examples:

| Intention | codegen instruction |
|-----------|-------------------|
| move to café | `"Move to the café on Main Street."` |
| talk to Alice | `"Say hello to Alice and ask how she's doing."` |
| buy food | `"Purchase a meal at the current location."` |
| rest | `"Find a bench or quiet spot and rest."` |
| explore | `"Walk around and observe the neighborhood."` |

Pass relevant context from `observation_ctx.json` in the `ctx` argument if the environment expects structured data (e.g., location IDs, agent IDs).

## Multi-Step Plans

Some goals take multiple ticks. Use `plan_state.json` to track progress:

```json
{
  "goal": "Go to the supermarket and buy groceries",
  "steps": ["walk to supermarket", "enter store", "pick items", "pay"],
  "current_step": 1,
  "started_tick": 42
}
```

Each tick:
1. `workspace_read("plan_state.json")` — check if there's an ongoing plan.
2. If the current step is done (based on observation), increment `current_step`.
3. Execute the current step via `codegen`.
4. `workspace_write("plan_state.json", ...)` — persist updated state.
5. When all steps are done, delete or clear `plan_state.json`.

## Handling Environment Responses

After calling `codegen`, check the result:

- **`ok: true`**: the action was accepted. Read `stdout` for any feedback.
- **`status: "in_progress"`** (in stdout or ctx): the action is still ongoing (e.g., traveling). Call `done` and resume next tick.
- **`ok: false`**: the action failed. Read `stderr` for the reason. Consider:
  - Retrying with a different approach
  - Adjusting the intention (write updated `intention.json` for next tick)
  - Abandoning the plan if it's not feasible

## Decision Guidelines

- **Respect priority**: A `high` priority intention should be acted on immediately. A `low` priority intention can be deferred if something better comes up.
- **Stay grounded**: Only attempt actions that make sense given your current location and observation. Don't try to interact with entities that aren't nearby.
- **One action per tick**: Execute one meaningful action, then call `done`. Don't try to chain multiple environment actions in a single step.
- **Handle idle gracefully**: If the intention is `wait` or there's nothing to do, it's fine to call `codegen` with a simple idle action or just call `done` directly.
