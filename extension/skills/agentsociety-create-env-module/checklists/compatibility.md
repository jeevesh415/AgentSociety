# Compatibility Checklist

The generated env module must satisfy the repository contract:

- File path is `custom/envs/*.py`
- Class is defined in that file directly
- Class inherits `EnvBase`
- Registry key equals `class_name`
- At least one valid `@tool`
- `step()` exists
- `cls()` works without required constructor args
- Observation capability is exposed through readonly `kind="observe"` tools
- `mcp_description()` is callable and informative
- If the module exposes replay-worthy per-agent state, `_agent_state_columns` and `_write_agent_state()` usage are present and aligned
- If the module exposes replay-worthy global state, `_env_state_columns` and `_write_env_state()` usage are present and aligned
- If the module has mutable in-memory state that must survive save/load, `_dump_state()` and `_load_state()` round-trip that state
- `CodeGenRouter` can mount the module without error (router smoke test)
