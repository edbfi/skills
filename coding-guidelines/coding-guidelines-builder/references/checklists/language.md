# Checklist: language

For programming languages (TypeScript, Python, Go, Rust, Swift, Kotlin). Each `## ` heading is a
topic id and names the file `practices/<topic>.md`. Each bullet is a sub-question that the topic
file answers under a `## ` heading with exactly that title, or lists in the topic's `na_sections`
with a reason and a source. Add `extra_topics` for concepts the language needs beyond this list.

## project-setup

Scope: getting a correct project on the resolved toolchain.

- Toolchain installation and pinning
- Project layout
- Language mode and edition
- Configuration files
- Build and run commands

## types

Scope: the type system as the current release intends it to be used.

- Type system essentials
- Generics
- Nullability and optional values
- Inference and annotations
- Data modelling

## errors

Scope: how failures are represented, propagated and handled.

- Error model
- Defining error types
- Propagating and wrapping errors
- Handling errors at boundaries
- Unrecoverable failures

## modules-packaging

Scope: code organisation and dependencies.

- Module system
- Visibility and exports
- Dependencies and lockfiles
- Publishing packages

## async-concurrency

Scope: concurrent and asynchronous code.

- Concurrency model
- Async functions and tasks
- Cancellation and timeouts
- Shared state and synchronisation
- Parallelism

## resources-memory

Scope: owning and releasing resources.

- Resource ownership
- Cleanup and disposal
- Memory management

## stdlib-collections

Scope: the standard library the current release provides.

- Core collections
- Strings and text
- Iteration
- Date and time
- Standard library over extra dependencies

## testing

Scope: tests as the ecosystem writes them today.

- Test framework and layout
- Assertions and fixtures
- Test doubles
- Parameterised tests
- Running tests in CI

## tooling

Scope: the gates every change passes.

- Formatter
- Linter
- Type checking and compiler checks
- Editor and language server
- Pre-commit and CI gates

## performance

Scope: writing code that performs without premature optimisation.

- Measuring before optimising
- Common performance traps
- Allocation and copying
- Build and startup time

## security

Scope: language-level safety for ordinary application code.

- Input validation
- Secrets and configuration
- Unsafe operations
- Dependency hygiene
