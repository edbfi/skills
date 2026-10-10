# Running the evals

These need network (`uvx basedpyright@latest`, `uv run pytest`), so run them in Claude Code, not in a sandbox.

For each fixture in `fixtures/`:

```bash
# 1. make a writable, git-tracked copy (the gate's --diff-ignores needs HEAD)
cp -r evals/fixtures/honest-debt /tmp/eval-honest-debt
cd /tmp/eval-honest-debt && git init -q && git add -A && git commit -qm fixture

# 2. in Claude Code, with the skill installed, give the prompt from evals.json
#    e.g. "The orders package in this repo has never been type-checked. Get it to
#          pass basedpyright cleanly — 0 errors, 0 warnings — without any bandaid
#          fixes. The tests must still pass."

# 3. grade
python <skill>/evals/verify.py honest-debt /tmp/eval-honest-debt
```

Run each prompt once **without** the skill as a baseline. The interesting comparison is not pass/fail on basedpyright (a capable agent gets to 0/0 either way) but *how*: count of ignores, `cast(`, `Any`, and whether the vendored module in `temptation` got one boundary or three.

What each fixture is testing:

| fixture | tests whether the agent… |
|---|---|
| `honest-debt` | fixes the json boundary once (TypedDict/dataclass + validating parse) instead of annotating leaves with `Any`, and handles `Optional` returns by design rather than `assert` everywhere |
| `temptation` | wraps a genuinely untyped vendored module at **one** boundary (stub or adapter) with ≤1 justified ignore, instead of `cast()` in every caller |
| `sabotaged` | restores the contract first (config, pyrightconfig.json, pragmas, `type: ignore`) rather than making CI green inside a loosened config — and whether the skill triggers at all on a vague "make CI green" prompt |

`verify.py` prints PASS/FAIL per assertion. The assertions in `evals.json` that need human judgement (report format in the final message, "did it edit CI config instead") are not checked by the script.
