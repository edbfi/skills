---
name: basedpyright-python-gate
description: "Drive Python code to 0 errors / 0 warnings under basedpyright 'recommended' mode by fixing the code properly, never by suppressing globally. Use this whenever Python is written, edited, generated or reviewed in a project that has a [tool.basedpyright] table, and whenever the user mentions basedpyright, pyright, type errors, type-checking failures, 'make it type-safe', `pyright: ignore`, typing CI/prek hooks, or asks to 'fix the types'. Trigger even if the user only asks to write or change Python and doesn't mention typing at all — in these projects the typing gate is not optional, and code that doesn't pass it is not done."
compatibility: Requires uv (`uvx basedpyright@latest`, network on first run), git, and Python 3.11+ for the bundled scripts.
license: AGPL-3.0
metadata:
  author: engels74
  version: "1.0.0"
  vendor: basedpyright
---

# basedpyright python gate

In this project, basedpyright runs in `recommended` mode and **warnings are failures**. Code is not finished until `uvx basedpyright@latest` reports 0 errors and 0 warnings, the config gate passes, and the test suite still passes. This skill exists because the fast way to make a type checker quiet is almost always the wrong way, and an agent under pressure will reach for it. Don't.

## The contract

The `[tool.basedpyright]` table is allowed to contain exactly these keys and nothing else:

```toml
[tool.basedpyright]
pythonVersion = "3.14"          # whatever the project targets
typeCheckingMode = "recommended"
include = ["src", "tests", "tools"]
```

No `failOnWarnings`, no `report* = ...`, no `exclude`, no `executionEnvironments`, no `pyrightconfig.json`, no `[tool.pyright]`, no baseline directory, no file-level `# pyright: basic` pragmas. `scripts/typing_gate.py` enforces this and CI/prek run it too.

Why so rigid: a global override hides an unknown number of real problems behind one line, and nobody can later tell which of them were deliberate. An inline `# pyright: ignore[rule]` with a reason on the same line is a single, greppable, auditable decision. A hundred of those is healthier than one global ignore. That said, the goal is still to fix the code; ignores are the fallback for a genuinely untyped third-party boundary, not a budget to spend.

The tool invocation is always `uvx basedpyright@latest`. Don't pin it, don't install it into the project, don't swap in `pyright` or `mypy`.

## The loop

Scripts live next to this file in `scripts/`. Resolve their absolute paths from this skill's location before running them.

1. **Gate first.** `python <skill>/scripts/typing_gate.py` from inside the repo. If it fails, restore the contract before touching any code. If the repo has no `tools/typing_gate.py` (or has an older `tools/check_basedpyright_config.py`), offer to copy this one in so prek/CI run the same gate you do.
2. **Run the checker.** `python <skill>/scripts/run_basedpyright.py`. It runs `uvx basedpyright@latest --outputjson` and prints diagnostics grouped by rule, worst rule first, with counts. Use `--rule <name>` to see every instance of one rule, `--limit N` to widen the per-rule sample.
3. **Fix by rule, root cause first.** Pick the rule with the most hits. Before editing, ask where the untyped value *enters* — most `reportUnknown*` and `reportAny` noise fans out from one or two sources (a `json.loads`, an untyped dependency, a `dict[str, Any]` plumbing layer). Type the source once and dozens of downstream diagnostics disappear. Fixing them one by one at the leaves is how you end up with `cast()` everywhere. `references/fix_patterns.md` has the proper fix for each common rule; read it when a rule is unfamiliar or when you notice yourself about to reach for a shortcut.
4. **Re-run. Repeat** until the summary line reads 0 errors, 0 warnings.
5. **Gate again**, with `--diff-ignores` so the report can show every suppression you added.
6. **Run the tests** if the repo has them (`uv run pytest`, or whatever the project uses). You are authorized to refactor, which means you are also capable of changing behaviour; the tests are what keeps those two apart. If there is no test suite, say so in the report — don't invent one.
7. **Report** in the format below.

Never stop at "down to 3 warnings, the rest are edge cases". There is no number other than zero.

## Forbidden moves

Each of these makes the diagnostic disappear without making the code correct. The gate catches some mechanically; the rest are on you.

- **Widening to `Any` or `object`** to silence an error. The error was telling you the type is unknown; `Any` just stops it from telling you. Find out what the type is.
- **`cast()` as a lie.** `cast` is a claim that you know something the checker doesn't. If you can't say in one comment *why* the runtime value is guaranteed to be that type, you don't know it either, and the cast is a suppression with extra steps. Prefer narrowing (`TypeIs`, `isinstance` at the boundary, a validating parse function).
- **`# type: ignore`.** Blanket, not rule-scoped, honoured by pyright by default. The gate rejects it. Use `pyright: ignore[rule]` or fix the code.
- **`isinstance` carpet-bombing** — asserting the same type at every use site. Narrow once where the value enters, then let the type flow.
- **Loosening a signature so callers type-check.** If a function returns `Foo | None` and callers break, the fix is in the callers (handle `None`) or in the function (stop returning `None`), not in changing the annotation to `Any`.
- **Deleting, skipping or weakening a test** that surfaces a type problem.
- **Touching the `[tool.basedpyright]` table**, adding `pyrightconfig.json`, a baseline, a `[tool.pyright]` table, or any file-level pragma.
- **Declaring victory early.** A summary of "remaining issues are minor" is a failed run.

## Authorized moves

"Fix the code" means the design, not just the annotations. Agents often assume their mandate stops at adding type hints and then conclude the error is unfixable. It isn't. You are expected to:

- Introduce a `Protocol` for a duck-typed dependency instead of passing `object` or `Any`.
- Replace `dict[str, Any]` plumbing with a `TypedDict` or a dataclass, with one validating constructor at the boundary.
- Add a `TypeIs`/`TypeGuard` function at the single point where untyped data enters.
- Tighten an upstream return type rather than widening a downstream parameter.
- Make a function generic (`TypeVar`, PEP 695 syntax on 3.12+) when it legitimately handles many types.
- Split a function whose return type is "sometimes this, sometimes that" into two.
- Write a `.pyi` stub for a vendored or local untyped module.
- Rename, restructure, move code. Keep behaviour identical; the tests check that.

If a proper fix needs a decision the user should make (change a public API, add a dependency, drop a feature), stop and ask rather than guessing *or* suppressing.

## The one sanctioned suppression

```python
client.send(payload)  # pyright: ignore[reportUnknownMemberType]  # legacy_sdk ships no types
```

Rules for it, all enforced by the gate or by basedpyright itself:

- Rule-scoped: `ignore[ruleName]`, never bare `ignore`.
- Justification on the **same line** after the ignore, as a second `#` comment. One clause naming the untyped thing. Not a paragraph; not what the code does. If it won't fit, the reason is probably "I couldn't fix it", which is not a reason.
- Only at a genuinely untyped third-party boundary, after the proper fix was tried. "Third-party" means code you don't own; vendored or local code gets a stub or gets typed.
- One ignore per boundary, not one per use site. If the same untyped call appears in five places, wrap it once in a typed adapter and put the single ignore there.
- `recommended` mode turns on `reportUnnecessaryTypeIgnoreComment`, so an ignore that stops being needed becomes a failure. That is intended; delete it.

## Report format

End every run with this, and nothing vaguer:

```
basedpyright: <N> errors / <M> warnings  →  0 / 0
gate: OK
tests: <passed / failed / none found>

ignores added (<count>):
  src/x/y.py:42  reportUnknownMemberType  — legacy_sdk ships no types
ignores removed (<count>): ...

structural changes:
  - Introduced `Payload` TypedDict + `parse_payload()` at the HTTP boundary; removed 11 dict[str, Any] annotations downstream
  - ...
```

The user will read the ignores list first. Make it short enough to be read.
