# Toolchain isolation

Exact versions are chosen after phase 1 resolves compatibility and installed before phase 2 runs
any task. Every baseline, example, and evaluation then builds on the same pinned toolchain.

## Default: Docker

Official images exist for most languages, the tag pins the toolchain, and the container sees only
what is mounted.

- Use a full version tag that matches the version table, never a floating tag like `rust:1` or
  `python:3`, and record the digest (`docker image inspect --format '{{index .RepoDigests 0}}'`)
  in `manifest.md`.
- Mount only the directory being worked on. Put registry caches and build output on named volumes;
  build directories on bind mounts are slow on macOS.
- Pass `--user "$(id -u):$(id -g)"` on Linux hosts so files are not root-owned, and set the tool's
  home to a writable mounted path when the image expects root.

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD/examples":/work -w /work \
  -v "${RUN_ID}-cargo-registry":/usr/local/cargo/registry \
  -v "${RUN_ID}-cargo-target":/work/target \
  -e CARGO_TARGET_DIR=/work/target \
  rust:1.91.0 cargo clippy --all-targets --all-features -- -D warnings
```

`RUN_ID` is the run folder name. Services run on a dedicated network from a compose file inside
`examples/`. Give each concurrent task, configuration, and run a unique compose project and reset
its database and volumes, so configurations never share mutable service state.

## Fallback: the host, with tool homes in `.toolchain/`

Required for stacks that need an Apple SDK or a Windows-only framework.

- Rust: `RUSTUP_HOME`, `CARGO_HOME`, `CARGO_TARGET_DIR`
- Go: `GOPATH`, `GOMODCACHE`, `GOCACHE`, `GOTOOLCHAIN`
- Python: `uv` with `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR`; `uvx` for one-off tools
- JavaScript: `bunx` or `npx` with `BUN_INSTALL_CACHE_DIR` / `npm_config_cache`
- Xcode: `-derivedDataPath` and `-clonedSourcePackagesDirPath` under `.toolchain/`; Xcode itself is
  global and its version is recorded, not controlled

A platform the host cannot run (Windows frameworks from macOS) means the examples for that component
cannot be verified here. Mark them unverified in the facts and keep them out of the skill's
recommended patterns rather than presenting them as working.
