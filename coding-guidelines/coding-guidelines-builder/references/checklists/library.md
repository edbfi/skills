# Checklist: library

The fallback for any component that no more specific checklist describes (validation,
serialization, cryptography, async runtimes, utility libraries, and, until their own checklists
exist, frameworks and tools). Each `## ` heading is a topic id and names the file
`practices/<topic>.md`. Each bullet is a sub-question that the topic file answers under a `## `
heading with exactly that title, or lists in the topic's `na_sections` with a reason and a source.
Because this list is generic, the component outline (`references/research.md`) decides the real
depth: every significant concept from the component's own documentation that these topics do not
cover becomes an `extra_topics` file.

## setup

Scope: installing and configuring the resolved release.

- Installation and version pinning
- Configuration

## core-api

Scope: what the library is for and how the current release expects it to be used.

- Core concepts
- Common tasks
- Idioms the library expects

## errors

Scope: how the library fails and how callers handle it.

- Failure modes
- Handling failures

## integration

Scope: using the library with the runtimes and frameworks it is commonly paired with, without
assuming a particular stack.

- Runtime and framework integration
- Interoperability with related libraries

## performance

Scope: costs that ordinary use can trigger.

- Performance characteristics
- Common performance traps

## testing

Scope: testing code that depends on the library.

- Testing code that uses the library
- Test doubles
