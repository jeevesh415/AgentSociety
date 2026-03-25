# Design

Turn the request into a `DesignSpec` that becomes the source of truth for generation.

If the module has mutable runtime state, counters, per-agent snapshots, or replay requirements, also read `references/persistence-patterns.md` before freezing the design.

Minimum design fields:

- `module_name`
- `class_name`
- `global_state`
- `per_agent_state`
- `tools`
- `config_fields`
- `step_semantics`
- `persistence`
- `success_criteria`

The `persistence` section should answer these questions explicitly:

- Which per-agent fields must be queryable from replay tables
- Which environment/global fields must be queryable from replay tables
- Which in-memory structures must survive `dump()` and `load()`
- Where replay writes happen, usually `step()` or another canonical mutation boundary
- Whether `_dump_state()` and `_load_state()` are required, and what they must serialize

Persist:

- `design_spec.json`
- `design_summary.md`
- Only if you want a reviewable trace under `.agentsociety/custom_env_skill/runs/<run_id>/`.

Do not start code generation until the design spec is internally coherent.
