---
name: observation
description: Environment perception — the agent's eyes and ears.
priority: 0
provides:
  - observation
  - environment awareness
---

# Observation

Gives the agent the ability to perceive its surrounding environment at each simulation step.

## What It Does

1. Sends an `<observe>` instruction to the environment router
2. Receives a structured text description of the agent's surroundings (location, nearby agents, objects, time, weather, etc.)
3. Stores the observation as a timestamped memory entry

## Behavioral Guidelines

- Observation is always the **first** action in a step; all downstream skills depend on it.
- If the environment returns `status: in_progress`, the step is skipped entirely (the world is still settling).
- The observation text becomes the agent's "sensory input" for the current tick.

## Context Keys

| Key | Type | Description |
|-----|------|-------------|
| `observation` | `str \| None` | Raw observation text from the environment |
| `observation_ctx` | `dict \| None` | Full context dict returned by the environment |
| `early_return` | `str` | Set when the step must be short-circuited |
| `stop` | `bool` | When `True`, the pipeline stops after this skill |
