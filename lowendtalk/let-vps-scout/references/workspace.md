# Run workspace

Each run works in its own folder under `/tmp/let-vps/`, created by `python3 scripts/ledger.py init`. The folder is scratch space: it coordinates the agents and may disappear on reboot. The only durable output is the report published to the archive.

## Contents

- [Layout](#layout)
- [Ledger tables](#ledger-tables)
- [Worker files](#worker-files)
- [Coordinator commands](#coordinator-commands)
- [Checkpoints, STATUS.md and resume](#checkpoints-statusmd-and-resume)
- [Archive](#archive)

## Layout

```
/tmp/let-vps/2026-09-27_1415_k3f9qa1x/
├── STATUS.md        dashboard and exact resume point, rewritten by the coordinator
├── report.html      copy of the report template, filled at the end
├── fonts/           fonts the report uses while it lives here
├── ledger/          source of truth, written only by the coordinator
│   ├── assignments.csv  batches.csv  listings.csv  threads.csv
│   └── providers.csv    candidates.csv  gaps.csv    fx.csv
├── workers/         one file per assignment, e.g. A014_provider_netcup.md
└── evidence/        saved page extracts, named by stable IDs
    ├── listings/page-01.txt
    ├── threads/<discussion-id>/p1.txt, p7.txt
    ├── providers/<provider-id>/catalogue.txt, cart-annual-fsn.txt
    └── screenshots/
```

**Ownership:** a worker writes only its own `workers/<assignment>.md` and the `evidence/` paths for its scope. It never edits `ledger/`, `STATUS.md` or `report.html`. The coordinator merges worker output into the ledger. One writer per file means parallel agents cannot overwrite each other.

## Ledger tables

CSV, UTF-8, every field quoted. `;` separates multiple values inside a cell. **Blank = not checked yet; `unknown` = checked, not disclosed.** Timestamps are ISO 8601 with offset.

Stable IDs make deduplication mechanical:

| ID | Form | Example |
|---|---|---|
| Assignment | `A` + three digits | `A014` |
| Thread | LET discussion ID | `198233` |
| Provider | lowercase slug of the brand | `netcup` |
| Candidate | provider, plan, location, and term or coupon when they differ | `netcup-rs2000-nue-annual` |
| Gap | assignment ID + `-g` + number | `A014-g1` |
| Batch | `B` + number; B1 is pages 1-20 | `B3` |

| Table | Key | Columns and allowed values |
|---|---|---|
| `assignments` | `id` | `type` (`listing-batch`, `threads`, `provider`, `finalist`, `recheck`), `scope`, `owner`, `pages` (ego-browser Page labels held), `status` (`pending`, `active`, `complete`, `blocked`), `created`, `updated`, `output`, `notes` |
| `batches` | `batch_id` | `listing_pages`, `status`, `completed_at`, `cheapest`, `six_vcpu`, `upgrades` (candidate IDs), `changed` (`yes`/`no`), `reason` |
| `listings` | `page` | `url`, `captured_at`, `thread_ids`, `overlap_note` |
| `threads` | `discussion_id` | `title`, `url`, `listing_pages`, `sticky`, `total_pages`, `pages_read` (e.g. `1; 14`), `provider_ids`, `status` (`pending`, `read`, `blocked`), `notes` |
| `providers` | `provider_id` | `name`, `website`, `thread_ids`, `coupons`, `assignment`, `status` (`pending`, `active`, `checked`, `blocked`), `outcome` (`candidates`, `no-qualifying`, `uncompetitive`, `not-server-provider`, `blocked`), `reason`, `checked_at` |
| `candidates` | `candidate_id` | See below |
| `gaps` | `gap_id` | `kind` (`blocked`, `unfinished`, `intentional-limit`, `unresolved-lead`), `subject`, `detail`, `recorded_at`, `resolved` |
| `fx` | `currency` | `eur_per_unit`, `rate_date`, `source_url`, `captured_at` |

`candidates` columns:

- Identity and state: `candidate_id`, `provider_id`, `plan`, `location`, `country`, `state` (`provisional`, `shortlisted`, `verified`, `blocked`, `unavailable`, `excluded`)
- Resources: `vcpu`, `cpu_sharing` (`shared`, `dedicated`, `unknown`), `cpu_model`, `ram_gb`, `disk`, `connectivity` (`ipv4`, `ipv6-only`, `nat`)
- Price in original currency: `billing_term` (`annual`, `monthly`, `biennial`, `triennial`, ...), `currency`, `first_year_total`, `renewal_total`, `setup_fee`, `mandatory_extras`, `coupon`, `coupon_recurs`
- Price in EUR: `first_year_eur`, `renewal_eur`, `monthly_eur`
- Payment: `payment_methods`, `crypto` (`yes`, `no`, `unknown`), `payment_fees`
- Network and policy: `port_speed`, `transfer`, `game_policy` (`allowed`, `prohibited`, `unknown`), `cpu_policy`, `stock`
- Provenance: `verified_at`, `product_url`, `order_url`, `let_source`, `evidence`, `notes` (exclusion reason, VAT caveats, payment-dependent totals)

The list-type columns (`thread_ids`, `listing_pages`, `pages_read`, `provider_ids`, `coupons`, `payment_methods`, `evidence`) merge as a union, so two workers can each add a thread to the same provider without losing either.

## Worker files

A worker returns one Markdown file, `workers/<assignment-id>_<type>_<scope>.md`: a short header, fenced CSV blocks named after ledger tables, and a few lines of notes. Include only the columns you have values for; the key column is required. Leave a cell blank rather than guessing.

````markdown
# A014 provider netcup

- Owner: provider-worker-3
- Pages used: p4
- Finished: 2026-09-27T15:42:10+02:00

```csv providers
provider_id,name,website,status,outcome,reason,checked_at
netcup,netcup,https://www.netcup.com,checked,candidates,,2026-09-27T15:40:00+02:00
```

```csv candidates
candidate_id,provider_id,plan,location,country,state,vcpu,ram_gb,connectivity,billing_term,currency,first_year_total,product_url,evidence
netcup-rs2000-nue-annual,netcup,RS 2000 G11,Nuremberg,DE,provisional,8,16,ipv4,annual,EUR,215.88,https://www.netcup.com/...,evidence/providers/netcup/catalogue.txt
```

```csv gaps
gap_id,kind,subject,detail,recorded_at
A014-g1,blocked,netcup cart,Checkout totals need login,2026-09-27T15:41:00+02:00
```

Notes: the VPS 4000 G12 annual price shown only with a 12-month contract; renewal assumed unchanged but not stated, so renewal left blank.
````

Keep notes compact and factual. Do not paste page text into the worker file; save extracts under `evidence/` and reference them.

## Coordinator commands

```sh
python3 scripts/ledger.py init                        # new run folder; prints its path
python3 scripts/ledger.py merge <run> <run>/workers/A014_*.md [--dry-run]
python3 scripts/ledger.py upsert <run> assignments A014 status=complete output=workers/A014_provider_netcup.md
python3 scripts/ledger.py summary <run>               # counters and the verified ranking
python3 scripts/ledger.py publish <run> [--partial]   # see report.md
```

`merge` rejects unknown tables or columns and invalid candidate states; fix the worker file and merge again. Blank cells never erase existing values. `upsert` is for your own edits (assignment status, batch results, FX rates).

## Checkpoints, STATUS.md and resume

Checkpoint after each listing batch, each set of merged provider checks, each finalist verification, and before any pause:

1. Merge completed worker files and update their assignments.
2. Run `summary` and rewrite `STATUS.md`: run state (`running`, `interrupted`, `complete`), counters, current batch and unchanged-batch count (for example 1/2), current recommendations and top shortlist, active assignments with their Page labels, blockers, the **resume point** as the exact next action (for example "merge A022, then open listing page 26"), and a session log line per start or resume.

To resume, read `STATUS.md`, reconcile any assignments still `active` (check whether their worker file exists and is complete before reassigning), then continue from the resume point in the same run folder and the same ego-browser TaskSpace when it still exists.

## Archive

Only `publish` writes to the archive, once per run:

```
~/Documents/Research/LET-VPS/
├── 2026/
│   ├── 2026-09-27_let-vps-report.html
│   └── 2026-10-14_let-vps-report.html
└── 2027/
    └── 2027-02-27_let-vps-report.html
```

The year folder comes from the report date. A second report on the same date gets the time added (`2026-09-27_1830_let-vps-report.html`). A partial report is named `..._let-vps-report_PARTIAL.html`; publishing again from the same run replaces that run's earlier file, so each run leaves exactly one document.
