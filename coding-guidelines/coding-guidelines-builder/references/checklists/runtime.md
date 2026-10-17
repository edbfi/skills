# Checklist: runtime

For runtimes and platforms that execute a language (Node.js, Bun, Deno, the JVM, .NET). Each `## `
heading is a topic id and names the file `practices/<topic>.md`. Each bullet is a sub-question that
the topic file answers under a `## ` heading with exactly that title, or lists in the topic's
`na_sections` with a reason and a source. Add `extra_topics` for anything else the runtime needs.

## setup

Scope: installing and configuring the resolved runtime.

- Installation and version pinning
- Project initialisation
- Configuration

## runtime-apis

Scope: built-in APIs to prefer over third-party packages.

- File system
- Networking and HTTP
- Processes and environment
- Built-in modules worth preferring

## packages

Scope: dependency management on this runtime.

- Package manager
- Lockfiles
- Workspaces
- Compatibility with other runtimes' packages

## testing

Scope: the runtime's own test tooling.

- Built-in test runner
- Test isolation
- Running tests in CI

## deployment

Scope: running in production.

- Production builds
- Containers
- Process management and signals

## performance

Scope: measuring and avoiding runtime-specific costs.

- Profiling
- Startup and memory
- Common performance traps

## security

Scope: runtime-level protections.

- Permissions and sandboxing
- Secrets and environment
- Dependency hygiene
