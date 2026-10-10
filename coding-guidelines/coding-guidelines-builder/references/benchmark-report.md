# Benchmark reports

Read this when aggregating baselines, iteration results, or ablations. Run and grading records are
defined in `eval-tasks.md` §2 and §4; this reference defines their report, regardless of provider.

Write `benchmark.json` and a readable `benchmark.md` in the evaluated directory (`baseline/`,
`skill-workspace/iteration-N/`, or each ablation directory). The JSON contract is:

| Field | Required contents |
|---|---|
| `schema_version` | `1` |
| `configurations` | Array of `{name, identity, loading}`; identity records runner/version, model, effort, toolchain, tools, limits, and instruction baseline |
| `groups` | One record per task/configuration/split, as defined below |
| `comparisons` | Array of `{left, right, split, eval_ids, delta, limitations}`; every delta is explicitly left minus right |
| `limitations` | Array of missing coverage, telemetry, and validation qualifications |

Each group contains `eval_id`, `configuration`, `split`, `run_paths`, `expected_repeats`,
`valid_runs`, `invalid_runs`, `scored_assertions`, `unverifiable_assertions`, `pass_rate`,
`activation`, and `metrics`. Assertion counts sum valid grading files only. `pass_rate` is
`{n, mean, min, max}` over valid runs with at least one scored assertion; use n=0 and null statistics
when none qualify. `activation` counts valid runs by the four states in `eval-tasks.md` §2.
`metrics` records each quantity's unit and basis, with `{n, mean, min, max}` over known valid values
of that same basis.
Never turn missing telemetry into zero or combine incompatible token definitions. Report invalid
attempts and their known resource use separately, so retry spend remains visible without affecting
scores.

Compare only configurations with matched identities and loading strategies apart from the declared
guidance treatment. A comparison requires the planned valid repeats and scorable results for every
intended task on both sides; otherwise `delta` is null with coverage explained. Its value is the mean
of the per-task differences between left and right mean pass rates across the declared `eval_ids`.
Do not choose a successful subset after seeing results. Keep development and holdout comparisons
separate. Baseline-only reports have an empty `comparisons` array. Markdown reports show the same
coverage, spread, direction, and qualifications as the JSON.

Reporting helpers are optional. Inspect schemas, null handling, configuration names, and delta
direction before using one. Keep incompatible helper output under a separately recorded path and
translate it into this contract without inventing values. `claude-runner-example.md` documents
specific helper quirks; no helper's defaults redefine the builder's measurements.
