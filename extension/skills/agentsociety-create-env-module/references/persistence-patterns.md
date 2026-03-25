# Persistence Patterns

Use this reference when the custom environment is stateful. The goal is to make replay data and `dump()/load()` behavior explicit instead of leaving them implicit in the code.

## Read These Runtime Examples

- `agentsociety2.env.base`
  Source of truth for `_agent_state_columns`, `_env_state_columns`, `_dump_state()`, `_load_state()`, `_write_agent_state()`, `_write_agent_state_batch()`, and `_write_env_state()`.
- `agentsociety2.contrib.env.economy_space`
  Reference for combined per-agent replay, env replay, and dump/load.
- `agentsociety2.contrib.env.simple_social_space`
  Reference for env-level replay plus dump/load of mailboxes, groups, counters, and IDs.
- `agentsociety2.contrib.env.mobility_space.environment`
  Reference for per-agent replay plus dump/load of richer person state.

## Make The Design Decision Explicit

For every meaningful piece of mutable state, classify it before generating code:

- Replay only: queryable snapshots that should land in replay tables
- Dump/load only: internal structures needed to resume behavior but not useful as replay tables
- Both: queryable over time and also required for faithful restore
- Neither: truly derived or disposable values

Do not leave this undecided in prose. Put the result into the design spec's `persistence` section.

## Map Design To Code

Use `_agent_state_columns` when the replay row is keyed by `agent_id + step`.

Typical examples:

- balances, income, consumption
- lng/lat or other per-agent position snapshots
- per-agent scores or status values

Use `_env_state_columns` when the replay row is keyed by `step`.

Typical examples:

- aggregate counters
- market rates
- total message counts
- group counts

Use `_dump_state()` and `_load_state()` when the module keeps mutable in-memory structures that must survive `dump()` and `load()`.

Typical examples:

- dictionaries of model objects
- queues, mailboxes, group membership maps
- next-id counters
- step counters
- timestamps or datetimes
- serialized geometry or other non-JSON-native objects

## Write At Canonical Boundaries

Prefer replay writes at deterministic boundaries:

- `step()` for periodic snapshots
- a single canonical mutation path if state changes outside `step()`

If multiple agents are written every step, consider `_write_agent_state_batch()` instead of many single-row writes.

## Common Failure Modes

- Declaring replay columns but never writing them
- Writing replay rows whose keys do not match declared columns
- Forgetting to persist counters or IDs, causing restore to diverge
- Serializing complex objects in `_dump_state()` without converting them to JSON-safe forms
- Reconstructing the wrong types in `_load_state()`
- Assuming replay tables alone are enough to restore internal behavior

## Minimum Review Questions

- After `dump()` then `load()`, will the module continue from the same logical state?
- Can replay consumers query the intended per-agent and env snapshots without reading opaque blobs?
- Are all declared replay columns actually written?
- Are all write points stable and deterministic?
