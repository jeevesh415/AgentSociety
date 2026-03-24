---
name: agentsociety-create-env-module
description: Create or update a custom EnvBase environment module under custom/envs, clarify missing requirements, keep lightweight run artifacts when useful, and validate through the bundled skill scripts.
license: Proprietary. LICENSE.txt has complete terms
---

# Create Environment Module

Use this skill as guidance for creating or repairing a custom env module.

## Standard Sequence

Treat this as a suggested sequence:

1. Collect missing requirements and write down the structured design.
2. Write `custom/envs/<module>.py` directly.
3. Validate with `scripts/validate.py`.
4. If traceability matters, keep lightweight artifacts under `.agentsociety/custom_env_skill/runs/`.

## Stage Routing

- Requirements intake: `stages/intake.md`
- Clarification: `stages/clarify.md`
- Structured design: `stages/design.md`
- Code generation: `stages/generate.md`
- Validation and failure mapping: `stages/validate.md`

## Shared References

- Compatibility contract: `checklists/compatibility.md`
- Artifact schema: `artifacts/schema.md`
- Persistence patterns: `references/persistence-patterns.md`
- Runtime source guide: `references/runtime-sources.md`
- Runtime source resolver: `scripts/resolve_sources.py`
- Validation CLI: `scripts/validate.py`

## Runtime Contract

- Final generated env code must still land in `custom/envs/*.py`.
- The class must be defined in that file directly and registered by its `class_name`.
- Do not invent a package-style output format for the generated environment.
- Prefer validating through `scripts/validate.py`, and use run artifacts only when they add review value.
