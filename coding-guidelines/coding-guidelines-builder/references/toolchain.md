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

`RUN_ID` is the run folder name. A fresh named volume mounted at a path the image does not have is
root-owned and unwritable under `--user`, so initialize each one once:
`docker run --rm -v "${RUN_ID}-cargo-target":/v alpine chown "$(id -u):$(id -g)" /v`. Services run
on a dedicated network from a compose file inside `examples/`. Give each concurrent task,
configuration, and run a unique compose project and reset its database and volumes, so
configurations never share mutable service state.

## The task runner

`claude -p` must build with the same pinned toolchain as the examples, so in Docker mode it runs
inside a runner image derived from the pinned one, built once per run as `${RUN_ID}-runner` and
recorded in `manifest.md` with its digest and the CLI version (the same one as the host's
`claude --version`):

```Dockerfile
FROM rust:1.91.0
COPY --from=node:22-bookworm /usr/local/bin/node /usr/local/bin/
COPY --from=node:22-bookworm /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g @anthropic-ai/claude-code@<cli-version>
```

Run each task with only its directory mounted as `/work`, an empty per-run directory mounted as
`HOME`, and credentials in the environment (`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, or
`ANTHROPIC_API_KEY`); never mount `~/.claude`. In host mode, run `claude -p` with `HOME` set to an
empty per-run directory, the same credential variable, and the `.toolchain/` variables exported
with `.toolchain/bin` first on `PATH`, so every build the agent starts uses the pinned tools.
Record the effective tool versions from the first transcript of each configuration; a run that
built with another toolchain is invalid.

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
