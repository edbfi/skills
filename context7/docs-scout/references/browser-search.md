# Browser search with agent-browser

## The shared browser

`scripts/ab-host.sh` runs one host session, `docsearch-host`, that owns the only browser on the
machine. Nobody browses through the host. Each agent (and each subagent) gets its own session from
`ab-host.sh new` and runs every command as `ab-host.sh ab <session> <agent-browser args>`. That
command attaches the session to the host over CDP (`--cdp <url>`), and the session's first command
`--pin-tab tab new` gives it a tab of its own, so parallel agents never steer each other's pages.

Why one browser: a CloakBrowser plan may allow a single concurrent browser. A plain
`agent-browser --session x open ...` launches a new browser per session. With a single-seat
licence that second launch fails: Chrome exits 76, agent-browser itself exits 1 with
`Chrome exited early (exit code: 76)`. Sharing also means a search engine's consent click or
challenge clearance is earned once for every tab. `agent-browser read <url>` is no way around
the seat: on this setup it launches the browser too.

Behaviour the script relies on (agent-browser 0.39.1, observed 2026-10-17):

- `--idle-timeout` is taken from **every** command a session's daemon receives. A command without
  it resets the daemon to the 1-hour default, so `ab-host.sh` passes `--idle-timeout` on every host
  command (20 minutes) and on every attached command (10 minutes).
- `get cdp-url` launches the host's browser when it isn't running. `ab-host.sh up` uses that as
  "launch or keep alive", and `ab` calls `up` before every command (about 0.1 s).
- An attached session that times out or closes only disconnects. The shared browser and its other
  tabs keep running.
- Attaching can leave an extra `about:blank` tab, and a detach occasionally leaves the session
  listed for a moment. `release` closes the tab, detaches, checks `session list` and closes again if
  needed.
- A launch that fails can leave the session's daemon running. `ab-host.sh` closes it and, if it is
  still listed, stops the daemon by the PID that `session info` reports.

A session shows up in `session list` only once its first command runs, so `ab` also touches an
attach marker in `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/docs-scout-<uid>/` before attaching. `down`
counts markers younger than 2 minutes as attached agents. Recording a marker plus fetching the CDP
URL, and checking plus closing the host, each run under one lock in that directory. An agent that
starts while another releases therefore never gets a CDP URL for a browser about to close.

`up` recognises a busy seat by the error text (`exit code: 76`, licence, seat, session limit). It
retries twice, 30 s apart, then exits 76. `release` calls `down`, which closes the host only when no
other `docsearch-*` session is listed and no fresh attach marker exists. A crashed agent's session
expires after its 10-minute idle timeout. The host itself expires 20 minutes after the last `ab`
call.

Tunables, for unusual setups only: `DOCS_SCOUT_HOST_IDLE`, `DOCS_SCOUT_AGENT_IDLE`,
`DOCS_SCOUT_SEAT_WAIT` (seconds).

## Engines

Probed headless through CloakBrowser on 2026-10-17 with the same queries on each engine, a mix of
guideline, API and `site:` searches. Results drift; when an engine misbehaves, move to the next one
rather than fighting it.

| Order | Engine | Query URL | Observed |
|---|---|---|---|
| 1 | DuckDuckGo HTML | `https://html.duckduckgo.com/html/?q=<q>` | Clean results, no JS needed, `site:` works. `uddg=` redirects are unwrapped |
| 2 | Startpage | `https://www.startpage.com/do/search?q=<q>` | Good results (Google-sourced). The first result can be an ad (`admarketplace`), which the extractor drops. Wait for `networkidle` before extracting |
| 3 | Bing | `https://www.bing.com/search?q=<q>` | Good results. Link text is often the site name; the extractor takes the result heading |
| 4 | Ecosia | `https://www.ecosia.org/search?q=<q>` | Cookie banner (results still render behind it; "Reject non-essential" clears it). Renders client-side, so an early extraction finds nothing. After a burst of queries it showed "Confirm you're not a robot" |
| 5 | Google | `https://www.google.com/search?q=<q>&hl=en` | Consent page first; click "Reject all". Result links are opaque `/goto?url=` redirects, kept with `"redirect": true`; opening one lands on the target. After a burst of queries it redirects to `/sorry/` ("unusual traffic") |
| 6 | Brave Search | `https://search.brave.com/search?q=<q>` | "Verifying you're not a bot" CAPTCHA, headless |
| 7 | Qwant | `https://www.qwant.com/?q=<q>&t=web` | "Qwant is temporarily unavailable (HTTP 403)" |

URL-encode the query (`+` for spaces, `%3A` for `:`). Consent buttons can be clicked by name:

```bash
AB find role button click --name "Reject all"            # Google
AB find role button click --name "Reject non-essential"  # Ecosia
```

Never solve CAPTCHAs or log in; switch engines instead. If several engines challenge in a row,
slow down: the machine's IP is being rate-limited.

## Extracting results

`scripts/serp-links.js` works on any of the engines above:

```bash
AB open "<query url>"
AB wait --load networkidle
AB eval --stdin < scripts/serp-links.js
```

It returns `{engine, title, count, results: [{title, url, redirect?}]}` with up to 10 organic links.
It works like this:

- It picks the first results container that really holds links (`#links`, `#b_results`,
  `div#search`, `main`, ...).
- It unwraps redirect wrappers: DuckDuckGo `uddg=`, `/url?q=`, Bing `u=a1<base64>`.
- It drops the engines' own pages, ad networks and a few social networks (Facebook, Instagram,
  TikTok, X, LinkedIn, Pinterest), and de-duplicates by host and path. Docs hosts on an engine's
  domain, such as `developers.google.com` or `learn.microsoft.com`, are kept; Reddit and YouTube
  results are kept too, so rank them yourself.
- Each result's title comes from its heading.

`count: 0` on a page that shows results means it has not finished rendering: wait and extract once
more before switching engines. Search snippets are for picking pages, never for answering.

## Reading pages

`AB read <url>` fetches the page as text through the attached session. It asks for markdown first,
then tries the same URL with `.md`, then the nearest `llms.txt`, and falls back to readable text
extracted from the HTML. `--outline`, `--filter <text>` and `--max-output <n>` keep it small. When
it returns an empty shell or a challenge page, render the page instead: `AB open <url>`, then
`AB read` with no URL, or `AB get text body`. Docs sites that serve markdown (Next.js, for one,
returns front matter and an `llms.txt` pointer) read well this way.

GitHub `blob/` links (common in Context7 sources) read better as raw files:
`https://github.com/<o>/<r>/blob/<ref>/<path>` →
`https://raw.githubusercontent.com/<o>/<r>/<ref>/<path>`.
