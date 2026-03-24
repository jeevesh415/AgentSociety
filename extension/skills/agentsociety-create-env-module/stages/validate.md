# Validate

Validate the generated module through `scripts/validate.py`.

If traceability matters, keep the validation report in the same run directory as your design and generation notes. If not, validate directly and treat any run artifacts as lightweight notes.
Reusing `--run-id` should extend an existing note trail, not replace earlier design or generation artifacts.

If validation fails, run `scripts/resolve_sources.py` if needed, then read `references/runtime-sources.md` again. Use the bundled local validator implementation as the source of truth for fixes.
If the module has mutable state or replay expectations, also re-read `references/persistence-patterns.md` and compare the code against the built-in persistence examples.

Preferred paths:

- Local CLI: `scripts/validate.py --file custom/envs/<module>.py --workspace <repo> --run-id <run_id>`
- Or directly: `scripts/validate.py --file custom/envs/<module>.py --workspace <repo>`

Read and persist:

- `validation_report.json`
- `validation_summary.md`

If you need stronger traceability, keep the design and generation notes in the same run directory. If you do not, the validation result still stands on its own.

Failure mapping:

- Design mismatch: go back to `design`
- Import or codegen failure: go back to `generate`
- Compatibility or tester failure: inspect structured checks first, then choose `design` or `generate`
- Mutable state exists but replay or dump/load logic is missing: go back to `design`, fix the persistence plan, then regenerate
- Registry visibility failure: fix registry integration, not the prompt wording
