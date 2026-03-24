# Runtime Source Guide

Do not assume the user has the source repository checkout. In installed environments, prefer importable module names and resolve their actual file paths at runtime.

## Resolve Runtime Paths First

Use `scripts/resolve_sources.py` before reading reference code. It resolves the installed file locations for the modules this skill depends on without importing those modules.

Examples:

```bash
python scripts/resolve_sources.py
python scripts/resolve_sources.py --json
python scripts/resolve_sources.py --module agentsociety2.env.base
```

If a module cannot be resolved, treat that as an environment issue and fall back only to modules that are importable in the current Python environment.

## Required Reads

Read these modules before generating or repairing a custom env module:

- `agentsociety2.env.base`
  Confirms the real `EnvBase` and `@tool` contract.
- `agentsociety2.env.router_codegen`
  Confirms what the router smoke test needs in order to mount the generated module.
- `agentsociety2.registry.modules`
  Confirms how registry integration works and why the registry key must remain `class_name`.
- `scripts/validate.py`
  Confirms what the bundled local validator checks and which validation artifacts it writes.

## Reference Implementations Available In Installed Packages

- `agentsociety2.custom.envs.examples.advanced_env`
  Richer example showing config handling, multiple tools, and richer descriptions.
- `agentsociety2.contrib.env.simple_social_space`
  Use this for a lightweight built-in social interaction reference.
- `agentsociety2.contrib.env.economy_space`
  Use this when you need a richer reference for state handling, persistence, and economic interactions.
- `agentsociety2.contrib.env.mobility_space.environment`
  Use this when you need a complex reference for movement-related state and multi-component environment behavior.

## Registration and Workflow Integration

- Registration uses the runtime registry helpers from `agentsociety2.registry.modules`.
- Validation uses the bundled skill script. Optional run artifacts live under `.agentsociety/custom_env_skill/runs/` only as local notes.

## Optional Repo-Only References

If the source repository is available, these can provide extra context, but do not depend on them:

- `packages/agentsociety2/examples/basics/02_custom_env_module.py`
- `packages/agentsociety2/docs/custom_modules.rst`
- `docs/development/envmodule_dev.md`

## How To Use This Reference

- Resolve module paths first.
- Read the required reads before writing code.
- Read at least one packaged reference implementation before generating a new module.
- Re-open `scripts/validate.py` when validation fails so fixes follow the real checks rather than guesswork.
