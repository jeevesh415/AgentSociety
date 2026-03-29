---
name: cognition
description: Generate emotion, thought, and intention based on observation and needs.
requires:
  - observation
  - needs
---

# Cognition

This is your inner mind. Given what you observe and what you need, produce three outputs that represent your cognitive state: **emotion**, **thought**, and **intention**.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_intentions` | 5 | Max number of candidate intentions to consider before selecting the top one |

## Initial State

When the agent is first initialized, the following default values are used:

### Need Satisfaction Levels
| Need | Initial Value |
|------|---------------|
| `satiety` | 0.7 |
| `energy` | 0.3 |
| `safety` | 0.9 |
| `social` | 0.8 |

### Emotion
- **Emotion Type**: `Relief` (default)
- **Intensities**: All at 5 (moderate)

### Thought
- **Default thought**: "Currently nothing good or bad is happening"

These initial values create a realistic starting point where the agent has:
- Moderate satiety (will need food soon)
- Lower energy (needs rest relatively soon)
- High safety (feeling secure)
- Good social satisfaction
- Neutral emotional state

## Cognitive Processing Flow

The cognition skill performs a **unified update** that considers:

```
1. Need Adjustment → 2. Determine Current Need → 3. Update Emotion/Thought → 4. Update Intention
```

Each step uses outputs from previous steps. This ensures coherent, human-like behavior.

## Inputs

Read these workspace files before reasoning:

### Core Inputs

| File | Content |
|------|---------|
| `observation.txt` | What you currently perceive |
| `needs.json` | Your four need levels (satiety, energy, safety, social) with thresholds |
| `current_need.txt` | Your most urgent need |
| `memory.jsonl` | Past experiences (read last 5-10 entries for recent context) |
| `emotion.json` | Current emotion state (if exists, for continuity) |
| `intention.json` | Previous intention (if exists, to consider continuation) |
| `plan_state.json` | Current plan status (if exists, to consider interruption) |

### Personality and Identity

| File | Content |
|------|---------|
| `personality_bias.json` | Big Five traits and decision biases |
| `beliefs.json` | Core values and principles |

### Social Context

| File | Content |
|------|---------|
| `social_relations.json` | Relationship graph with other agents |
| `empathy_state.json` | Perceived emotions of others |
| `communication_strategy.json` | Suggested conversation approach |

### Motivation and Regulation

| File | Content |
|------|---------|
| `habit_bias.json` | Time-based behavioral biases |
| `long_term_goals.json` | Active long-term goals |
| `curiosity_targets.json` | Things to explore when idle |
| `emotion_regulation.json` | Suggested emotion regulation strategies |

Also consider your **profile** (personality, background, relationships) from the system prompt's Agent Identity section.

## Step 1: Need Adjustment

Based on recent memories and current observation, adjust need satisfaction levels:

### Adjustment Factors

1. **Recent activities**:
   - Eating → increase satiety
   - Resting/sleeping → increase energy
   - Social interaction → increase social
   - Working/exercising → decrease energy
   - Dangerous situations → decrease safety

2. **Current observation**:
   - Available food nearby → consider eating
   - Safe/comfortable location → maintain/increase safety
   - Friends nearby → increase social desire
   - Time of day → influence sleep/meal needs

3. **Natural decay** (handled by needs skill):
   - satiety: −0.02 per tick
   - energy: −0.03 per tick

### Adjustment Decision

For each need, decide: increase, decrease, or maintain. Only adjust needs that have been meaningfully affected.

```json
{
  "adjustments": [
    {"need_type": "satiety", "adjustment_type": "decrease", "new_value": 0.45, "reasoning": "Haven't eaten in hours"},
    {"need_type": "energy", "adjustment_type": "decrease", "new_value": 0.38, "reasoning": "Been walking all day"}
  ],
  "reasoning": "Activities consumed energy; need rest and food"
}
```

## Step 2: Determine Current Need

Using **adjusted** satisfaction values and thresholds, determine the most urgent need.

### Decision Rules

1. **Priority order**: Check needs in order: satiety → energy → safety → social
2. **Urgency threshold**: A need is urgent when satisfaction ≤ threshold
3. **Default**: If no urgent needs, current_need = "whatever"

### Example Output

```json
{
  "reasoning": "Energy (0.38) is below threshold (0.2) and is highest priority among urgent needs",
  "need_type": "energy",
  "description": "I feel tired and need to rest"
}
```

## Step 3: Update Emotion and Thought

Based on recent memories, current observation, and need satisfaction levels:

### Emotion Types

Select the most appropriate emotion type from:

| Emotion Type | Description | Common Triggers |
|--------------|-------------|-----------------|
| `Joy` | Positive feeling from success or pleasure | Achievement, pleasant surprise |
| `Distress` | General negative feeling from unfulfilled needs | Hunger, fatigue, loneliness |
| `Resentment` | Anger from perceived unfairness | Unfair treatment, betrayal |
| `Pity` | Sympathy for others' misfortune | Seeing others suffer |
| `Hope` | Anticipation of positive outcomes | Good news, opportunity ahead |
| `Fear` | Anticipation of danger or negative outcomes | Danger, uncertainty |
| `Satisfaction` | Contentment from achieving goals | Completed plan, fulfilled need |
| `Relief` | Release from anxiety or fear | Problem resolved, safety restored |
| `Disappointment` | Sadness from unmet expectations | Failed plan, let down |
| `Pride` | Self-satisfaction from achievement | Personal accomplishment |
| `Admiration` | Respect for others' achievements | Impressed by others |
| `Shame` | Negative self-evaluation | Regret, embarrassment |
| `Reproach` | Disapproval of others' actions | Others' poor behavior |
| `Liking` | Positive feeling toward something/someone | Pleasant experience |
| `Disliking` | Negative feeling toward something/someone | Unpleasant experience |
| `Gratitude` | Thankfulness for others' help | Received help |
| `Anger` | Strong negative reaction to offense | Offense, injustice |
| `Gratification` | Pleasure from fulfilling desires | Need satisfied |
| `Remorse` | Regret for past actions | Guilt, mistake |
| `Love` | Deep positive attachment | Strong bond |
| `Hate` | Deep negative attachment | Strong aversion |

### Emotion Intensity Model

```json
{
  "sadness": 5,
  "joy": 5,
  "fear": 5,
  "disgust": 5,
  "anger": 5,
  "surprise": 5
}
```

Values are integers between 0-10:
- 0-2: Very low intensity
- 3-4: Low intensity
- 5-6: Moderate intensity
- 7-8: High intensity
- 9-10: Very high intensity

### Emotion-Need Relationship

Need satisfaction levels strongly influence emotions:

| Need Status | Likely Emotions |
|-------------|-----------------|
| Satiety critical (< 0.2) | Distress, Irritability |
| Energy critical (< 0.2) | Fatigue, Apathy |
| Safety critical (< 0.2) | Fear, Anxiety |
| Social critical (< 0.2) | Loneliness, Sadness |
| All needs satisfied | Contentment, Satisfaction |

### Thought Guidelines

Write a brief inner monologue (1–3 sentences, first person):

- Reference what you observe
- Consider what you need
- Reflect on recent memories
- Express how you feel
- Think naturally, not mechanically

Example:
```
The café looks inviting and my satiety is getting low. I had a productive morning, but now I need to refuel. Maybe I'll grab lunch there.
```

## Step 4: Update Intention (TPB Model)

Using the Theory of Planned Behavior, generate and evaluate intentions:

### TPB Factors

| Factor | Range | Description |
|--------|-------|-------------|
| `attitude` | 0.0–1.0 | Personal preference and evaluation of the behavior |
| `subjective_norm` | 0.0–1.0 | Social environment and others' views on this behavior |
| `perceived_control` | 0.0–1.0 | Difficulty and controllability of executing this behavior |

Higher scores in all three dimensions = more likely to be executed.

### Intention Fields

```json
{
  "intention": "Go to the café to eat and rest",
  "priority": 1,
  "attitude": 0.8,
  "subjective_norm": 0.6,
  "perceived_control": 0.7,
  "reasoning": "Low energy and satiety; café is nearby and affordable"
}
```

### Intention Generation Process

1. **Consider current need**: What would help satisfy the urgent need?
2. **Consider current situation**: What's feasible given observation?
3. **Consider ongoing activities**: Should continue current plan or change?
4. **Generate candidates**: 2-5 possible intentions
5. **Evaluate with TPB**: Score each candidate
6. **Select top priority**: Choose highest priority (lowest number)

### Intention Dynamics

Intentions can change based on:

| Factor | Effect on Intention |
|--------|---------------------|
| New urgent need | May override current intention |
| Changed observation | May provide new opportunities/constraints |
| Changed emotion | May shift motivation |
| Plan failure | Requires new intention |
| Plan completion | Seek new intention |

### Intention vs Plan

- **Intention**: A goal or desire (what you want to do)
- **Plan**: Steps to achieve intention (how you'll do it)

Intentions are concise; plans are detailed.

Example:
- Intention: "Eat lunch" (not "walk 100m, enter restaurant, order food, eat")
- Plan: Detailed steps derived from intention

## Output Files

After reasoning, write:

### 1. `emotion.json`

```json
{
  "primary": "Hope",
  "valence": 0.5,
  "arousal": 0.4,
  "intensities": {
    "sadness": 3,
    "joy": 6,
    "fear": 2,
    "disgust": 1,
    "anger": 1,
    "surprise": 3
  },
  "note": "Looking forward to lunch; feeling productive"
}
```

### 2. `thought.txt`

```
I've been working all morning and my energy is dipping. The café across the street looks perfect for a lunch break. I should head over there soon.
```

### 3. `intention.json`

```json
{
  "intention": "Have lunch at the café",
  "priority": 1,
  "attitude": 0.9,
  "subjective_norm": 0.7,
  "perceived_control": 0.8,
  "reasoning": "Need food and rest; café is nearby and I enjoy the food there"
}
```

### 4. Update `needs.json`

Apply the adjustments determined in Step 1.

## Special Cases

### Plan Outcome Emotion Update

When a plan completes or fails, perform a focused emotion update:

```json
{
  "emotion": {
    "sadness": 2,
    "joy": 8,
    "fear": 1,
    "disgust": 1,
    "anger": 1,
    "surprise": 3
  },
  "emotion_types": "Satisfaction",
  "conclusion": "I feel relieved that I successfully completed my plan to find food"
}
```

For failed plans:
- Emotion types: `Disappointment`, `Frustration`, `Shame`, `Anger`
- Negative valence, higher arousal if unexpected

For completed plans:
- Emotion types: `Satisfaction`, `Pride`, `Relief`, `Joy`
- Positive valence

### Continuing Current Activity

If currently in the middle of an activity (e.g., conversation, travel):

- Current intention should continue it
- Don't abruptly switch unless urgent need requires it
- Consider "can interrupt" flags for needs

### No Urgent Need (Whatever)

When all needs are satisfied:
- Intention can be exploratory, social, or leisure
- Lower priority is acceptable
- Consider personal interests from profile

## Execution Sequence

### Read Core Inputs

1. `workspace_read("observation.txt")`
2. `workspace_read("needs.json")`
3. `workspace_read("current_need.txt")`
4. `workspace_read("memory.jsonl")` (last 5-10 entries)
5. `workspace_read("emotion.json")` (optional, for continuity)
6. `workspace_read("intention.json")` (optional, to consider continuation)

### Read Personality and Identity

7. `workspace_read("personality_bias.json")` (apply decision biases to TPB)
8. `workspace_read("beliefs.json")` (consider values in intention evaluation)

### Read Social Context

9. `workspace_read("social_relations.json")` (influence social decisions)
10. `workspace_read("empathy_state.json")` (consider others' emotions)
11. `workspace_read("communication_strategy.json")` (if social interaction planned)

### Read Motivation and Regulation

12. `workspace_read("habit_bias.json")` (consider time-based biases)
13. `workspace_read("long_term_goals.json")` (align with goals)
14. `workspace_read("curiosity_targets.json")` (if current_need is "whatever")
15. `workspace_read("emotion_regulation.json")` (apply if emotions are intense)

### Reason and Write

16. Reason about cognitive state, applying all biases and contexts...
17. `workspace_write("emotion.json", ...)`
18. `workspace_write("thought.txt", ...)`
19. `workspace_write("intention.json", ...)`
20. Update `needs.json` with adjustments

## Notes

- Cognition integrates all information: observation, needs, memories, current state
- The output drives the planning phase
- Emotion influences and is influenced by need satisfaction levels
- Keep thoughts natural and reflective, not mechanical
- Intentions should be actionable but not over-detailed
