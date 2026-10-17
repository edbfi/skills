# Run folder, manifest and refresh

## Layout

Each run gets one folder under `${XDG_STATE_HOME:-$HOME/.local/state}/coding-guidelines-builder/runs/`,
named `<date>_<slug>_<suffix>` with a short random suffix. The same string is `RUN_ID` for Docker
volumes and networks. State lives under the XDG state directory because cache directories may be
wiped at any time; toolchain caches may live under `${XDG_CACHE_HOME:-$HOME/.cache}`.

```text
<run-id>/
  manifest.md              # resume state and cleanup contract
  components.json          # input to registry_versions.py
  versions.json            # resolution snapshot
  versions-<date>.json     # earlier snapshots on refresh
  probe.md                 # optional knowledge probe
  facts/<component>.md
  outline/<component>.md
  review/<pack-id>.md
  clones/                  # narrow clones; deleted before delivery
  draft/components/<id>/   # packs under construction, copied to the library at delivery
  draft/stacks/<id>/
  logs/                    # toolchain versions, verification output, harm-check results
  .toolchain/              # tool homes and caches, host mode only
```

Run `python3 "$BUILDER_DIR/scripts/audit_files.py" <run-dir>` at the end of every phase. Any file
it lists is moved into the layout or declared under `## Additional files` in `manifest.md` with a
reason. It is read-only; never delete unfamiliar files automatically.

## manifest.md

- **Request**: the stack as given, verbatim, and the library root.
- **Builder**: version and `BUILDER_DIR`.
- **Capabilities**: research tools, worker mechanism, whether an independent review context exists,
  Docker or host toolchains; user tool preferences and restrictions.
- **Components**: kinds, constraints, resolved versions, pack ids, reuse and dependents decisions.
- **Resources**: one row per image (tag, digest, pre-existing or pulled), volume, network, clone
  and service, each marked created by this run or pre-existing. Only resources created by this run
  are removed at the end.
- **Phases**: one line per phase, `pending`, `done <timestamp>`, `incomplete <reason>` or
  `failed <reason>`.
- **Additional files**: anything outside the layout, with a reason.
- **Limits**: verification limitations and review independence, copied into each `pack.json`.

Resume a phase marked done only if its inputs still match; changed inputs invalidate every dependent
phase.

## Refresh

`refresh: <pack path>` or `refresh: all` starts a new run. For each pack, re-research when any of
these holds:

1. the resolved version for its effective constraint changed
   (`registry_versions.py components.json --previous versions-<date>.json`, never redirected over
   its own input);
2. `refresh_after` has passed;
3. the user passed `force`;
4. `verification.limitations` or `review.open_items` is non-empty.

With no trigger, report the pack as current and stop. An expiry refresh re-checks every source, not
only the changed versions; `researched` advances only after the sources were read again. Every stack
that references a refreshed component is refreshed in the same run, and an edge whose effective
constraint moved (the framework now peers a new major) points at the new component pack.
