# Content rules for the generated skill

The reader is an expert who loads this skill in the middle of a task and pays for every token out of
the context the task needs. Write only what it would be wrong without.

## Admission: every unit of content has evidence

A rule, example, table row, or configuration block enters the skill only with one of these evidence
tags, recorded in `skill/PROVENANCE.md` against the section that holds it:

- **`baseline`**: a row in `baseline/mistakes.md`. The model wrote it wrong without help.
- **`probe`**: a `contradicted` or `cutoff-relevant` facts row. The model believes something stale
  or cannot know something new.
- **`decision`**: a tool, configuration, version, or project convention chosen for this stack.
  Nothing could infer it; it has to be stated.
- **`compat`**: a verified incompatibility or availability floor that changes what code is correct.
- **`structure`**: one of the fixed `SKILL.md` sections (Decisions, Top mistakes, Check, Routing) or
  a Contents list in a long reference. These hold no claims of their own; every row inside them
  still traces to one of the four tags above.

A file in `assets/` or `scripts/` is cited by its path with section `*`. No tag, no content. In
particular, anything listed under "Done correctly without help" in
`mistakes.md` is excluded, however fundamental it feels. The model already does it; a sentence
restating it costs tokens and buys nothing. `$BUILDER_DIR/scripts/check_provenance.py` fails on
sections with no row and on anti-pattern rows with no grep. This is a structural check: separately
resolve every reference against the cited mistakes/facts/decision and verify that it supports the
claim before delivery. Preserve the cited evidence excerpts in `PROVENANCE.md` so the delivered
artifact remains auditable without access to the run folder.

Evidence tags live in `PROVENANCE.md`, not in the loaded files; the skill's reader does not need
them.

## Versions and compatibility

- Honor every explicitly named tool, version constraint, preset, adapter, platform, minimum target,
  and exclusion in the stack block. Within those, target the latest mutually compatible stable
  releases from `versions.json` and the facts, verified as a combination, not component by
  component. If the newest release of one component is incompatible with the rest, use the newest
  compatible one and say why in one line.
- If the stack's explicit requirements cannot be reconciled, state the conflict in the version table
  and do not present the affected configuration as working.
- Distinguish toolchain or SDK version, language mode or edition, and minimum supported runtime or
  OS. A new SDK does not raise the deployment target. Code that supports the stated minimum behind an
  availability check is current code.
- Frame guidance around release lines. Exact versions appear only in configuration that requires
  them and in the version table; do not repeat them through the prose.
- Annotate a feature with the release that stabilized it only when that affects its use, and only
  when the facts confirm it shipped. Preview, experimental, and feature-flagged capabilities are
  mentioned once, to say not to use them, and only if the probe or a baseline showed the model
  reaching for one.

## Tooling

- Where the stack names a tool, teach that tool's real configuration and commands; never replace it.
- Where the stack leaves a role unnamed, the research decision stands: the current maintained
  default, with the familiar alternative named once and the precise reason it is not used here (for
  another ecosystem, superseded by X, discontinued, not preferred here). Call something deprecated,
  unsupported, or discontinued only when a facts row verifies it.
- One coherent setup: dependencies, configuration files, and the build, run, format, lint,
  type-check, and test commands agree with each other and with `examples/`. Exact dependency versions
  live in the one place the ecosystem keeps them (manifest, lockfile, version catalog) and nowhere
  else.

## Examples

- A code block exists where a `baseline` or `probe` row needs a demonstration or a `decision` is
  easier to show than describe. A rule the model gets wrong in one predictable way gets one sentence
  and a two-line before/after, not a program.
- Every code block is a file, or a marked region of a file, in `examples/`, copied by
  `$BUILDER_DIR/scripts/verify_examples.py`, and that project builds, lints with warnings as
  errors, and passes its tests on the pinned toolchain. The line before the fence names the source:
  `<!-- example: src/handlers.rs -->` or `<!-- example: src/handlers.rs#create_order -->` for the
  lines between `region: create_order` and `endregion: create_order`. Never edit a block in the
  skill; edit the example and run `verify_examples.py --sync`. Non-executable illustrative text
  may use `<!-- example-exempt: reason -->`; the verifier reports exemptions for manual review.
  Use standalone fences with at most three leading spaces; normalize blockquote/list-prefixed
  fences and unfenced indented code before verification. The verifier conservatively rejects
  indentation of four spaces outside fenced blocks, including prose and HTML comments with that
  indentation, so nested lists use two-space indentation.
- Blocks are complete: real imports, realistic names, the setup the behaviour depends on. No
  ellipses, no undefined helpers in the logic being taught. A block that depends on omitted
  application code is labelled an excerpt and names what it depends on.
- Blocks survive ordinary use: changing inputs, empty data, the expected failure, cancellation,
  resource cleanup, with ownership clear. No scaffolding for impossible cases.
- Examples replace prose. If the block shows the pattern, the text around it is one sentence
  pointing at what to notice. The failure mode to name and avoid: a correct example followed by
  paragraphs re-explaining what it already shows.
- One coherent sample domain across examples is fine; its folder layout and architecture are
  illustration, never requirements.

## Writing

- Directive sentences with the reason attached where the reason changes a decision: "use `{id}`
  path syntax; the `:id` form is rejected at route registration since 0.8" tells the agent what and
  why in one line. A reason that does not change what the agent would do is deleted.
- Reserve "must" and "never" for correctness requirements, verified incompatibilities, and explicit
  stack constraints. A preferred approach with legitimate exceptions is one sentence stating the
  default and the exception.
- Treat performance annotations and concurrency guarantees as contracts, not decoration. State a
  number only when a facts row verified it, with the conditions that make it meaningful.
- Tables where a real choice exists: a decision table, a compatibility matrix, the file-purpose map.
  Do not restate prose as a table or label every rule.
- Explain the why rather than piling up capitalized imperatives. Agents follow reasoning better
  than volume.

## Leave out

- Anything the baseline did correctly.
- Label scaffolding (`Default / Conditional / Reject` blocks), process boilerplate, workflow
  descriptions, checklists of steps the agent would take anyway.
- Migration guides, upgrade steps, legacy-compatibility recipes, "preserve existing behaviour"
  prose. Applying good patterns to the code it touches is the agent's job.
- Roadmap, history, release narrative, "coming soon".
- Citations, URLs, footnotes, source names, dates, quotations in loaded files. They live in
  `PROVENANCE.md`. Two exceptions: a URL a working configuration needs is content, not a citation,
  and `references/versions.md` ends with its single research-date line.
- References to this builder, the stack block, or "what was specified". Every constraint is a fact
  about the stack.
- Tutorials, surveys, API catalogs, marketing, onboarding. The reader knows how to program.
- Invented version numbers, packages, commands, config keys, or APIs. Omit an unverified claim or
  narrow it to what the facts support; dropping its number does not make it admissible.

## Required lookup sections

The generated skill ends its reference set with two files the agent can consult without reading
anything else:

- `references/anti-patterns.md`: a table of wrong / why / right rows, each with a grep pattern in a
  fourth column that detects the wrong form. Rows come from `mistakes.md` and contradicted probe
  rows; a row without a grep is a guess and is removed. These rows are also eval assertions.
- `references/versions.md`: one table of targeted release lines, language mode, availability floors,
  and any unresolved constraint conflict, followed by a single `- **Research date:** <date>` line.
  The table agrees with the configuration blocks in `examples/`, which remain the home of exact pins.

## Shrinking

Ablation in phase 4 supplies evidence for cuts, within the task coverage and observed variance;
it does not prove every remaining sentence necessary. Content a newer model gets right is
demoted from `SKILL.md` to a reference, and deleted when its reference section carried nothing else.
