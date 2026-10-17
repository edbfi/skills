# Optional harm check

Run this only when the user asks for it or a pack's guidance is in doubt. It is a sanity check, not
a gate: it informs fixes and never deletes content.

1. Write three to five realistic tasks for the stack, each with an objective check (build, tests,
   a grep for a known anti-pattern).
2. Run each task twice with the same coding agent and settings in fresh, isolated directories: once
   without the pack and once with an instruction to read the pack's `README.md` first.
3. Compare the results. A task that passes without the pack and fails with it points at wrong,
   stale or misleading guidance: find the recommendation responsible and fix it from its source.
4. Record the tasks, agent, model, settings and results in the run folder's `logs/`. Report the
   outcome as observations about that configuration, not as a measured improvement.
