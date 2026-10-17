# Toolchain and example verification

Every pack's `examples/` is a real project verified on the resolved versions. Exact versions are
chosen after resolution and pinned before any example runs.

## Default: Docker

Official images exist for most languages, the tag pins the toolchain, and the container sees only
what is mounted.

- Use a full version tag matching the resolved version, never a floating tag like `rust:1` or
  `python:3`, and record the digest (`docker image inspect --format '{{index .RepoDigests 0}}'`)
  in `manifest.md`.
- Mount only the example being verified. Put registry caches and build output on named volumes.
- Pass `--user "$(id -u):$(id -g)"` on Linux hosts so files are not root-owned, and set the tool's
  home to a writable mounted path when the image expects root.

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PACK/examples":/work -w /work \
  -v "${RUN_ID}-cargo-registry":/usr/local/cargo/registry \
  -v "${RUN_ID}-cargo-target":/work/target \
  -e CARGO_TARGET_DIR=/work/target \
  rust:1.91.0 cargo clippy --all-targets --all-features -- -D warnings
```

A fresh named volume mounted at a path the image does not have is root-owned and unwritable under
`--user`; initialize it once with
`docker run --rm -v "${RUN_ID}-cargo-target":/v alpine chown "$(id -u):$(id -g)" /v`.
Services the examples need (PostgreSQL, Redis) run from a compose file inside `examples/` on a
dedicated network with a unique project name, reset before each verification.

## Fallback: the host, with tool homes in `.toolchain/`

Required for stacks that need an Apple SDK or a Windows-only framework. Put `.toolchain/bin` first
on `PATH` with symlinks to the pinned binaries and keep tool homes inside the run folder:

- Rust: `RUSTUP_HOME`, `CARGO_HOME`, `CARGO_TARGET_DIR`
- Go: `GOPATH`, `GOMODCACHE`, `GOCACHE`, `GOTOOLCHAIN`
- Python: `uv` with `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR`; `uvx` for one-off tools
- JavaScript: `bunx` or `npx` with `BUN_INSTALL_CACHE_DIR` / `npm_config_cache`
- Xcode: `-derivedDataPath` and `-clonedSourcePackagesDirPath` under `.toolchain/`; Xcode itself
  is global and its version is recorded, not controlled

Verify the actual version output inside the execution environment and keep it in `logs/`.

## What verification means

For each pack, the example project must, on the pinned toolchain:

1. install from its lockfile,
2. build or type-check with warnings treated as errors,
3. pass its linter and formatter check, when the stack has them,
4. pass its tests, including tests that exercise each recommended pattern's failure path,
5. build against the declared targets (deployment target, minimum runtime) where the toolchain can.

Record the commands, toolchain versions, `packs.py hash <pack>`, the block counts from
`verify_examples.py --json`, and the outcome in `pack.json` `verification`. Remove build output
and dependency directories before hashing. A component that cannot run alone uses a minimal host
recorded with the note "verification host, not a recommendation". A platform the host cannot run
(Windows frameworks from macOS) leaves `status` `partial` or `not-run` with the limitation spelled
out; never claim verification that did not execute.
