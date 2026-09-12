# Repository CI

Published skill metadata, README index membership, and local reference paths. Existing public install paths and descriptions remain intact.

Every PR, default-branch push and manual dispatch runs read-only JSON/TOML/YAML,
merge/case conflict, private-key and secret checks through prek. The shared
`ci / required` gate rejects missing, failed, cancelled and skipped prerequisites.
Checks must leave tracked files unchanged. All action references use full release
tags from the shared automation hub; Renovate tracks action and hook versions.

Run `SKIP=no-commit-to-branch prek run --all-files` locally with prek 0.5.2.
Use `prek install` for local checks and `prek install --hook-type commit-msg` for
Conventional Commit validation. The local branch hook is skipped in CI.

Renovate updates merge automatically after every required CI job passes
on the current revision, including major and shared-policy updates. The checked
merge action verifies genuine author sign-offs and dispatches final CI for the
exact merged commit. No dashboard approval, branch protections or rulesets are
configured; native GitHub automerge stays disabled. Other changes retain full
manual review and the maintainer's `ghmerge` process.

Content checks do not prove prose accuracy, external-service availability, or
application behavior. No application build or placeholder tests are introduced.
