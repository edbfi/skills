# Runtime capabilities

Use whatever mechanisms the current harness offers; do not branch on provider names or infer the
harness from installed binaries. Inspect actual tool catalogs, MCP schemas or CLI help, and record
what was selected in `manifest.md`.

Honor the user's tool, model and browser choices. "Prefer Exa" permits an explained fallback; "only
Exa" does not. Report missing requested capabilities instead of silently replacing them.
Discovering a capability does not authorize installations or account changes.

| Need | Suitable mechanisms | If unavailable |
|---|---|---|
| Files and commands | Native tools, CLI, or equivalent MCP/API access | Stop; nothing can be written or verified |
| Research | Native search and fetch, a user-selected MCP, a browser, registry clients, git, HTTP | Use another permitted route; leave unsupported claims unverified |
| Parallel workers | Native subagents or separate sessions with scoped inputs | Research and write components sequentially |
| Independent review | A fresh worker with only the pack, its facts and outline, and the rubric | Self-review against the rubric; record `"independent": false` |
| Optional probe | A fresh context without research tools | Skip it; research is unaffected |
| Toolchains and services | Pinned containers or host tools | Verify what can run; record the rest as limitations |

## Research tools

Discovery, reading a known URL, rendering a page and inspecting source are different operations;
a known URL or tagged source needs no search first. A browser such as `agent-browser` reads pages
that need rendering: respect the user's headed or headless preference, use a session owned by the
run, read the page content rather than a links-only snapshot, and close the session at the end.

## Workers

A worker's inputs are its prompt plus whatever its harness gives it automatically; verify inherited
context, files and tools. Component workers get the request, their component entry,
`versions.json`, relevant probe statements and the formats they write. Workers writing in parallel
write only their own `facts/`, `outline/` and `draft/` paths; the orchestrator merges shared files.
