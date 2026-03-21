---
name: cognition
description: Update emotions, generate thoughts, and form intentions (TPB). Activate when the agent needs to reflect, decide what to do next, or process emotional events.
priority: 40
requires:
  - observation
provides:
  - emotion_update
  - thought_generation
  - intention_formation
  - need_adjustment
---

# Cognition

Handles the agent's inner mental life: emotions, thoughts, and intention selection.

## What It Does

1. **Emotion update** — Based on memories and current need satisfaction, updates six emotion dimensions (sadness, joy, fear, disgust, anger, surprise) on a 0–10 scale and selects a dominant emotion type (e.g. Joy, Distress, Hope).
2. **Thought update** — Generates a natural-language thought reflecting the agent's current situation.
3. **Intention formation** — Uses Theory of Planned Behavior (TPB) to generate candidate intentions, scoring each on attitude, subjective norm, and perceived behavioral control, then selects the highest-priority one.

All three updates are performed in a **single merged LLM call** for efficiency.

## Behavioral Guidelines

- Emotions should evolve gradually — no wild swings without strong triggers.
- Intentions should be grounded in the agent's profile, current needs, and recent memories.
- The selected intention drives the downstream planning skill.

## Data Models

```
EmotionType          — 21 discrete emotion categories (OCC model)
Emotion              — 6-dimensional intensity vector (0–10)
CognitionUpdateResult(emotion, emotion_type, thought)
Intention(intention, priority, attitude, subjective_norm, perceived_control, reasoning)
IntentionUpdate(intentions[], reasoning)
CognitionIntentionUpdateResult(need_adjustment, current_need, cognition_update, intention_update)
```
