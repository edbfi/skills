# Browser backends

A run uses exactly one backend for all browsing: **ego-browser** or **agent-browser**. The user chooses it at the start, `init --browser` records it in `STATUS.md`, and every worker and every resume uses that same backend. Workers get their backend section here, not this whole file.

## Contents

- [Choosing the backend](#choosing-the-backend)
- [What every backend must do](#what-every-backend-must-do)
- [ego-browser](#ego-browser)
- [agent-browser](#agent-browser)

## Choosing the backend

Before `init`, check which CLIs are installed:

```sh
command -v ego-browser agent-browser
cat ~/.agent-browser/config.json 2>/dev/null   # an "executablePath" means a custom browser, e.g. CloakBrowser
```

Skip the question if the user already named a backend or you are resuming. Otherwise ask, with your harness's question tool if it has one, and offer only the installed backends. Recommend one and explain the trade-off in a sentence each:

| Backend | Best when | Trade-off |
|---|---|---|
| ego-browser | The user wants to watch or help in their own Ego Lite browser | Uses the user's browser profile and its Page budget; its own TaskSpace model |
| agent-browser | The user wants the run kept apart from their own browsing, or ego-browser is missing | Separate Chrome (or the custom `executablePath` browser) the agent launches; with stock Chrome, Cloudflare may need a headed window |

If neither CLI is installed, stop and say how to install one (`npm i -g agent-browser && agent-browser install`, or the ego-browser installer). Do not fall back to plain HTTP fetching, because the ground rules require visiting pages.

## What every backend must do

Whichever backend you use, the rest of the skill relies on the same five things:

1. **Open a page and wait for its real content.** LowEndTalk and many provider sites sit behind Cloudflare, which first serves an interstitial titled "Just a moment...". It isn't the page. Wait for a condition that only the real page satisfies, such as discussion links on a listing page or the plan table on a catalogue, before you extract anything. If the challenge does not clear after a couple of waits, it probably needs a human click: ask the user to solve it in the visible window, then continue. Don't keep looping on it.
2. **Save evidence.** Write the rendered text of each page you rely on to its `evidence/` path, and take a screenshot of each cart total you verify.
3. **Extract links and IDs** from the rendered DOM. Bulk extraction with page JavaScript is fine.
4. **Operate configurators and carts.** Select options, enter coupons and read totals. Never submit an order or enter personal or payment data.
5. **One owner per browsing context.** Each worker gets its own context (an ego-browser Page or an agent-browser pinned tab), recorded in the assignment's `pages` column. Two agents never drive the same context at once. Only the coordinator tears the browser down, once, at the end.

## ego-browser

Read the installed ego-browser skill before the first browser action and follow it. It is a small custom JavaScript API, not Playwright.

- **One TaskSpace for the run.** The coordinator creates it, prints its `spaceId` and records it in `STATUS.md` (`Browser handle`). Workers resume it with `await taskSpace(<spaceId>)`. Nobody creates another space, not even to recover from a stuck Page.
- **Owned Pages.** Each worker is assigned specific Page labels (`p2`, `p3`, ...). It reuses them with `goto()` instead of opening new Pages.
- **Page budget.** Never run more concurrent browsing workers than there are Pages available. If concurrent browsing turns out unsafe or unavailable, browse one worker at a time and parallelise only the analysis of saved evidence.
- **Evidence.** `page.evaluate(() => document.body.innerText)` for text, `page.evaluate` for link extraction, and `page.screenshot({ path })` for carts. Write the files with `await import("node:fs/promises")`.
- **Cloudflare.** Use `page.waitForFunction(() => !document.title.startsWith("Just a moment") && <real-content check>, undefined, { timeout: 60_000 })`. If the user must act, call `task.handOff()` and resume afterwards as the ego-browser skill describes.
- **Teardown.** Workers never call `finish()`. The coordinator calls `task.finish({ keep: [] })` once, after every worker is done.

## agent-browser

Before the first command, load the usage guide from the CLI. The installed `agent-browser` skill is only a stub that points there, and the CLI serves the guide that matches its own version:

```sh
agent-browser skills get core          # workflows, waits, tabs, sessions, troubleshooting
agent-browser skills get core --full   # full command reference, when you need a flag
```

### One shared browser, one pinned tab per agent

The run uses **one browser**. Every agent attaches to it over CDP with its own session and a pinned tab. One browser means Cloudflare clearance is earned once and shared by every tab. It also keeps the run to one license seat when agent-browser launches a seat-licensed browser through `executablePath`, such as CloakBrowser, whose cheaper plans allow a single concurrent session. Separate sessions would each launch a browser and take a seat each.

Names come from the run folder's random suffix (`2026-09-27_1415_k3f9qa1x` gives `k3f9qa1x`):

| Session | Name | Used for |
|---|---|---|
| Host | `letvps-<suffix>` | Launching and finally closing the browser. Nobody browses through it |
| Coordinator | `letvps-<suffix>-coord` | The coordinator's own browsing (FX rates, rechecks) |
| Worker | `letvps-<suffix>-<assignment>` (e.g. `letvps-k3f9qa1x-A014`) | One per assignment |

Never browse through the host session: it acts on whichever tab is active, and that may be a worker's tab.

**Coordinator: launch once, probe Cloudflare, record the handle.** Start headless, which stays out of the user's way, and let the coordinator's first LowEndTalk page decide whether headless is good enough. In testing (Oct 2026), CloakBrowser passed LowEndTalk's Cloudflare check headless. Stock Chrome stayed on the interstitial headless and passed only headed.

```sh
agent-browser --session letvps-<suffix> --idle-timeout 0 open about:blank   # 0: no idle shutdown mid-run
agent-browser --session letvps-<suffix> get cdp-url    # ws://127.0.0.1:<port>/devtools/browser/...
# attach the coordinator session (wrapper below), then probe the LET front page,
# not listing page 1, so no listing page is loaded twice:
ab --pin-tab tab new https://lowendtalk.com/
ab wait --fn '!document.title.startsWith("Just a moment") && document.querySelector("a[href*=\"/discussion/\"]")'
```

If the probe still shows the interstitial after two or three waits, close the coordinator and host sessions and relaunch the host with `--headed` added. Record the host session, its mode (headless or headed) and the CDP URL in `STATUS.md` under `Browser handle`, and give the URL to each worker in its brief.

If launching fails with a license or session-limit error, agent-browser's `executablePath` points at a seat-licensed browser whose seats are all in use. Tell the user rather than retrying, because only they can free a seat.

**Every agent: a fresh shell per command.** Shell variables don't survive between tool calls, so start each Bash call with a small wrapper instead of relying on `export`:

```sh
ab() { agent-browser --session letvps-k3f9qa1x-A014 --cdp 'ws://127.0.0.1:51186/devtools/browser/...' "$@"; }
```

Send every command for a worker or coordinator session through this wrapper, `close` included. Without `--cdp`, agent-browser launches a **new** browser for that session. That wastes a browser, and with a seat-licensed executable it fails with exit code 76 because the shared browser already holds the seat.

**Worker: take a pinned tab, browse, release it.**

```sh
ab --pin-tab tab new https://lowendtalk.com/categories/offers    # first command only; the pin is sticky
ab wait --fn '!document.title.startsWith("Just a moment") && document.querySelector("a[href*=\"/discussion/\"]")'
ab get text body > "<run>/evidence/listings/page-01.txt"
cat <<'EOF' | ab eval --stdin
JSON.stringify([...new Set([...document.querySelectorAll('a[href*="/discussion/"]')]
  .map(a => a.href.match(/\/discussion\/(\d+)/)?.[1]).filter(Boolean))])
EOF
ab open https://lowendtalk.com/categories/offers/p2              # later pages: open in your pinned tab
ab screenshot "<run>/evidence/screenshots/<candidate-id>-cart.png"
ab tab close                                                      # when the assignment is done
ab close                                                          # with --cdp this only disconnects; the shared browser keeps running
```

Expect two harmless oddities in this flow. With `--cdp`, `close` still prints `✓ Browser closed` even though it only disconnected, so don't try to "repair" the shared browser. Attaching a session can also leave an extra `about:blank` tab behind. Leave those tabs alone: they don't count toward the tab limit, and they disappear when the host closes.

- Wait after **every** `open`, because each navigation can show the interstitial again. A wait times out after 25 seconds; retry it once or twice before treating the page as blocked.
- Use `snapshot -i` and `@eN` refs to work configurators and carts, and re-snapshot after each change.
- `agent-browser read` **with a URL** fetches over plain HTTP outside the browser. That is direct scraping, which the ground rules forbid. `read` with no URL reads the rendered active tab and is fine.
- Ignore WebMCP tools that provider sites advertise. Their effects are unverified and may include ordering. Use the page UI instead.
- Keep concurrent worker tabs modest: about four to six in one browser.
- Never run `agent-browser close --all`. It also closes other agents' sessions on the machine.

**Resume.** If `agent-browser --session letvps-<suffix> get cdp-url` fails, the browser is gone, for example after a reboot. Relaunch the host, record the new CDP URL in `STATUS.md`, and give workers new briefs. Their old pinned tabs no longer exist.

**Teardown.** After every worker has released its tab and the report is published, the coordinator closes its own session through its wrapper (`ab close`) and then the host, which owns the browser: `agent-browser --session letvps-<suffix> close`. `agent-browser session list` can still show the host for a few seconds afterwards. Check again before deciding it didn't close.
