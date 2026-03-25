# Generate

Generate a single-file environment module at `custom/envs/<module_name>.py`.

Before writing code:

- Run `scripts/resolve_sources.py` if the runtime file locations are not obvious.
- Read `references/runtime-sources.md`.
- Confirm the real contract in `EnvBase`, the bundled local validator, and registry helpers.
- Read at least one reference implementation that matches the desired complexity.
- If the module carries mutable state, replay data, or resume requirements, read `references/persistence-patterns.md`.

Generation rules:

- Keep the class definition in the target file itself.
- Inherit from `EnvBase`.
- Preserve `class_name` as the registry key.
- Include at least one legal `@tool`.
- Provide `step()`.
- Default to no-arg construction.
- If the module needs observation capability, provide it through one or more `@tool(readonly=True, kind="observe")` methods.
- Provide a useful `mcp_description()`.
- If per-agent state must be persisted to replay, declare `_agent_state_columns` and write through `_write_agent_state()` or `_write_agent_state_batch()`.
- If global environment state must be persisted to replay, declare `_env_state_columns` and write through `_write_env_state()`.
- If the module keeps mutable in-memory state that must survive save and restore, implement `_dump_state()` and `_load_state()` for the exact structures that need to round-trip.
- Persist step counters, IDs, queues, maps, or other reconstruction-critical state in `_dump_state()` when replay tables alone are not enough to restore behavior.
- Do not add placeholder persistence hooks. Either implement the real replay/dump-load path or keep the module intentionally stateless.

After writing code, keep lightweight notes only if they help later review:

- If traceability matters, write a concise `generation_input.json` or `generation_summary.md` into the current run directory.
- Include `module_path`, `class_name`, and the key generation decisions worth reviewing later.
