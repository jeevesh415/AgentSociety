---
name: my-custom-skill
description: Example custom agent skill — a template to get started.
priority: 100
---

# My Custom Skill

This is a template for creating a custom agent skill.

## What It Does

Add your skill description here. Explain what behavior or capability
this skill gives to the agent.

## Behavioral Guidelines

- Describe when and how this skill should be activated.
- What context (observation, memory, etc.) does it rely on?

## Context Keys

| Key | Type | Description |
|-----|------|-------------|
| `step_log` | `list[str]` | Append log messages here |
| `stop` | `bool` | Set `True` to stop the pipeline |
