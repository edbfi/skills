# Writing rules

The reader is a coding agent in the middle of a task, pointed at a pack because its own knowledge may
be out of date. It knows how to program. It needs to know what is correct on this release, why, and
what changed from what it remembers. Thoroughness and currency matter more than brevity, except in
`README.md`, which routes.

## Content

- **Everything comes from research.** Every recommendation, change item and anti-pattern traces to
  a `verified` fact and cites its source. Never invent versions, packages, commands, configuration
  keys or APIs; omit a claim that could not be verified, or narrow it to what the facts support.
- **Cover the topic, not the delta.** A pack documents current best practice for every checklist
  topic and outline concept, including what a model might already know. Other models, and future
  readers, rely on the same pack.
- **Recent changes get extra care.** For anything that changed in the covered window, say what the
  old form was, what replaced it, and since when.
- **Honor the request.** Every named tool, version constraint, preset, adapter, language mode,
  target and exclusion is a fact about the stack. Within those, use the resolved versions. Code that
  supports a declared target behind an availability check is current code.
- **Three separate facts.** Toolchain or SDK version, language mode or edition, and minimum
  supported target are stated separately; a new SDK does not raise the deployment target.
- **Defaults for unnamed roles** come from research: the current maintained default with real
  adoption, the familiar alternative named once with the precise reason it is not used. Call
  something deprecated, unsupported or discontinued only when a fact verifies it.
- **Preview, experimental and feature-flagged** capabilities are mentioned only to say not to use
  them, unless the request asks for them.
- **Paraphrase sources.** Quote only short passages, with the citation; never paste documentation.

## Recommendations

- Title each `### ` recommendation as a short imperative ("Validate untrusted input at the
  boundary"). The paragraph under it states why it is current best practice, with the reason
  attached where the reason changes a decision ("use `{id}` path syntax; the `:id` form is rejected
  at route registration since 0.8").
- Reserve "must" and "never" for correctness requirements, verified incompatibilities and explicit
  stack constraints. A preferred approach with legitimate exceptions is the default plus the
  exception.
- Performance and concurrency claims are contracts: state a number only when a fact verified it,
  with the conditions that make it meaningful.
- Use tables where a real choice exists (a decision table, a compatibility matrix). Do not restate
  prose as a table.

## Examples

- A recommendation gets a code block when the pattern is easier to show than describe. Every
  verified block is a file or region in `examples/`, synchronised with `verify_examples.py --sync`;
  edit the example, never the block. The line before the fence names the source:
  `<!-- example: src/handlers.rs -->`, or `<!-- example: src/handlers.rs#create_order -->` for the
  lines between `region: create_order` and `endregion: create_order` comments.
- Blocks are complete: real imports, realistic names, the setup the behaviour depends on. No
  ellipses and no undefined helpers in the logic being taught. A block that depends on omitted
  application code is labelled an excerpt and names what it depends on.
- Blocks survive ordinary use: changing inputs, empty data, the expected failure, cancellation and
  cleanup, with ownership clear.
- The text around a block points at what to notice; it does not re-explain the code.
- Use standalone fences with at most three leading spaces; no fences inside lists or blockquotes,
  and no indented code blocks. Nested lists use two-space indentation.
- Shell commands, old-API snippets in `changes.md` and an anti-pattern's wrong code are exempt by
  position. Anything else that cannot be a file needs `<!-- example-exempt: reason -->`.

## Leave out

- Tutorials, history, roadmaps, "coming soon", marketing and onboarding.
- References to this builder, the request, or "what was specified": every constraint is a fact
  about the stack.
- Unverified claims, however plausible.
