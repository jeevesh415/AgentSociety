---
name: plan
description: Generate multi-step plans from intentions and execute them via ReAct loop (reason → act → observe). Activate when the agent has an intention or active plan to carry out.
trigger: on_demand
priority: 50
requires:
  - observation
  - cognition
provides:
  - plan_execution
  - environment_interaction
---

# Plan

Translates the agent's current intention into an executable multi-step plan and carries it out using a ReAct (Reasoning + Acting) loop.

## What It Does

1. **Plan lifecycle management** — checks if the current plan step completed or failed based on new observations; advances the plan index accordingly.
2. **Plan interruption** — if the agent's intention has shifted significantly, the current plan may be abandoned.
3. **Plan generation** — given the selected intention and related memories, an LLM generates a structured plan (target, reasoning, ordered steps).
4. **Step execution (ReAct)** — for each plan step, the agent enters a ReAct loop:
   - *Reasoning*: decide what action to take next
   - *Acting*: send an instruction to the environment router
   - *Observing*: read the environment's response
   - Repeat up to `max_react_interactions_per_step` times (default 3)

## Behavioral Guidelines

- Plans should be concise (≤ `max_plan_steps`, default 6).
- Each ReAct action should be a single clear instruction to the environment.
- If a step returns `status: in_progress`, the agent waits until the next tick to check again.
- Plan completion or failure triggers an emotion update.

## Data Models

```
PlanStep(intention, status, start_time, evaluation)
PlanStepStatus      — pending / in_progress / completed / failed
Plan(target, reasoning, steps[], index, completed, failed, start_time, end_time)
StepEvaluation(success, evaluation, consumed_time)
```

## Template Mode

When `template_mode_enabled=True`, the agent's instructions to the environment use `{variable_name}` placeholders with an accompanying `variables` dict, enabling structured environment APIs.
