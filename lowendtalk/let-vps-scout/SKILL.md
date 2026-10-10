---
name: let-vps-scout
description: Research LowEndTalk offers and provider websites with ego-browser or agent-browser (the user picks at the start) to find and purchase-verify the cheapest currently available European VPS plans (default brief 4+ vCPU, 8+ GB RAM, annual billing, game-server use), ranked by first-year price excluding VAT, using coordinated subagents, a disposable /tmp run ledger and one archived HTML report. Use whenever the user wants to hunt LET or LowEndBox VPS deals, compare cheap European VPS/VDS offers for a game server, or start, resume or rerun a let-vps-scout run.
license: AGPL-3.0
compatibility: Requires python3 and either the ego-browser or the agent-browser CLI.
metadata:
  author: engels74
  version: "1.1.0"
  vendor: lowendtalk
---

# LET VPS scout

Find the cheapest **purchase-verified** European VPS plans by researching LowEndTalk (LET) offer threads and every provider they lead to, then publish one self-contained HTML report. Everything else the run produces lives in a disposable `/tmp` workspace that may vanish on reboot; that is intended.

Resolve this skill's directory first; `scripts/`, `assets/` and `references/` below are relative to it.

## The brief

Use these defaults unless the user overrides them in their request. Record the effective brief in `STATUS.md` and in the report masthead so a reader knows what was ranked.

| Setting | Default |
|---|---|
| Minimum | 4 CPU cores/vCPUs and 8 GB actual RAM (swap/VSwap excluded). 6+ vCPU preferred; more RAM desirable |
| Location | European datacentre, including UK, Switzerland and Norway. Verify the server location, not the provider's headquarters |
| Billing | Annual preferred. Rank by first-year total **excluding VAT**, including setup fees, required public IPv4 and mandatory extras. Renewal shown separately |
| Priorities | Price first, then vCPU count, then RAM. Highlight inexpensive resource upgrades without changing cheapest-first order |
| Payment | Crypto preferred, not required. Record methods and disclosed mandatory fees; flag payment-method-dependent totals |
| Use | Game-server hosting. Exclude plans that explicitly prohibit it; mark unclear policy **unknown** |
| Connectivity | Public IPv4 in the main ranking. IPv6-only and NAT plans listed separately with their limitations |
| Archive | `~/Documents/Research/LET-VPS` (override with the user's path or `LET_VPS_ARCHIVE`) |

Impose no disk or transfer minimum. Do not investigate reputation, outage history or refund policies.

## Ground rules

- **One browser backend for all browsing.** The run uses ego-browser or agent-browser, whichever the user chose (see step 1), and nothing else. Load that backend's own guide before the first browser action and follow it as well as [browser backends](references/browser-backends.md). Extracting text and links from a loaded page is fine. Search snippets, remembered prices, direct HTTP scraping (including `agent-browser read <url>`) and other browsers never substitute for visiting a page, because prices and stock change and the report must reflect what was actually observed.
- **Never buy or identify.** Do not submit orders, create accounts, enter personal or payment details, or contact providers. When a login, challenge or missing information blocks verification, record the limitation and move on; retry only when new information offers a plausible route.
- **Observed versus unknown.** A blank ledger cell means not checked yet; the literal `unknown` means checked and not disclosed. Discovery observations stay `provisional` until purchase-verified.
- **Coverage honesty.** Present results as the cheapest verified offers found within the stated coverage, never as an exhaustive market or comment survey. Skipped middle comment pages are an intentional limit, not completed reading.

## Workflow

1. **Choose the browser.** Unless the user already named a backend, ask whether to use ego-browser or agent-browser before doing anything else. Offer only the backends that are installed, and recommend one. See [choosing the backend](references/browser-backends.md#choosing-the-backend).
2. **Start or resume.** New run: `python3 scripts/ledger.py init --browser <ego-browser|agent-browser>` prints the run folder (`/tmp/let-vps/<date>_<time>_<random>/`) and records the backend in `STATUS.md`. Give that path in your first progress update. Then open the browser once for the whole run and record its handle in `STATUS.md`: an ego-browser TaskSpace ID, or an agent-browser host session and CDP URL. To resume, the user supplies the run folder: read its `STATUS.md` and continue with the recorded backend from the recorded resume point. A run folder without a recorded backend predates this option and used ego-browser. If the folder is gone (reboot), say so and start a new run.
3. **Discovery.** Inspect LET offer listing pages 1-20, record and deduplicate every thread, read each thread's opening post and final comment page. See [research method: discovery](references/research-method.md#discovery-and-thread-reading).
4. **Provider investigation.** Check the official site and ordering portal of every distinct server provider encountered, once per provider, with all its threads and coupons. See [provider investigation](references/research-method.md#provider-investigation).
5. **Shortlist and verify.** Keep a provisional shortlist and fully verify every credible candidate in its cart. See [purchase verification](references/research-method.md#shortlisting-and-purchase-verification).
6. **Batches.** Continue in five-page listing batches until two consecutive completed batches leave the recommendations unchanged. See [stopping rule](references/research-method.md#adaptive-stopping-rule).
7. **Report and publish.** Recheck the recommendations, fill the report template and publish it. See [report](references/report.md).

## Workspace and delegation

You coordinate; subagents do bounded browsing and analysis. You are authorized to choose their number, models and reasoning settings without asking. The run folder holds the ledger CSVs, one output file per worker assignment, saved page extracts and `STATUS.md`. Workers write only their own files; only you merge them into the ledger (`scripts/ledger.py merge`), update `STATUS.md` and publish. That single-writer rule is what keeps parallel work from overwriting itself.

- Folder layout, CSV columns, worker file format, checkpoints and resume: [workspace](references/workspace.md)
- Roles, assignment sizing, browser-context ownership and the worker brief: [delegation](references/delegation.md)
- Backend choice, the shared-browser setup for each backend, Cloudflare waits and teardown: [browser backends](references/browser-backends.md)

Give each worker only the reference sections its role needs rather than this whole skill.

## Progress updates

Keep updates short and useful: new contenders, changes to the recommendations, the stopping counter, blockers and what is next. Checkpoint the ledger and `STATUS.md` after each listing batch, each set of merged provider checks, each finalist verification and before any long pause. Never silently stop early; if interrupted, publish a partial report (`publish --partial`) and leave the exact resume point in `STATUS.md`.

## Finish

1. Recheck the cheapest annual plan, the recommended 6+ vCPU option and highlighted upgrades in their carts.
2. Fill `report.html` in the run folder following [report](references/report.md), then run `python3 scripts/ledger.py publish <run>`. It refuses reports whose design was altered or still contain sample content, inlines the fonts and writes `<archive>/<year>/<date>_let-vps-report.html`.
3. After all workers are done, tear the browser down once: ego-browser `task.finish({ keep: [] })`; agent-browser closes the coordinator session and then the host session (never `close --all`). See [browser backends](references/browser-backends.md).
4. Reply with the archived report path, the two picks with first-year EUR totals, and the main coverage limits.
