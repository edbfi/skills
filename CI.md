# Repository CI

Published skill metadata, README index membership, and local reference paths. Existing public install paths and descriptions remain intact.

Every PR, default-branch push and manual dispatch runs read-only JSON/TOML/YAML,
merge/case conflict, private-key and secret checks through prek. The shared
`ci / required` gate rejects missing, failed, cancelled and skipped prerequisites.
Checks must leave tracked files unchanged. All action references use full release
tags from the shared automation hub; Renovate tracks action and hook versions.

Run `SKIP=no-commit-to-branch prek run --all-files` locally with prek 0.5.3.
Use `prek install` for local checks and `prek install --hook-type commit-msg` for
Conventional Commit validation. The local branch hook is skipped in CI.

Shared actions, workflows and presets use immutable `v4.0.0` references.
Renovate is the sole ongoing dependency merge owner. Through the shared
`automerge.json` preset it arms GitHub auto-merge with the rebase strategy, and
GitHub merges only after every required CI and policy check passes on the
current head. Shared Renovate policy updates remain manual;
release-age rules, holds and repository-specific updater ownership still apply.
The legacy Actions merger and its comment commands are retired.

The separate PR policy workflow verifies Conventional Commit titles, genuine
matching author sign-offs, Renovate provenance, holds, outstanding review requests
and unresolved changes requests. After a pass, policy re-runs the other event's
older failed verdict for the same head (`actions: write`), so a withdrawn
objection clears without a manual re-run. Require its actual emitted policy context alongside
all existing application/content checks, pinned to GitHub Actions, with strict
up-to-date branch protection. Preserve stronger review requirements. Explicit CI
dispatches do not substitute for a missing metadata policy result. Review exact
head/base, full diffs and all required results before a bootstrap merge, then
verify resulting default-branch CI. Repository-specific updater ownership and
manual publication or delivery controls remain unchanged.

Content checks do not prove prose accuracy, external-service availability, or
application behavior. No application build or placeholder tests are introduced.
