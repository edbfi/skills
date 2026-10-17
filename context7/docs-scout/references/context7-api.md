# Context7 Search API

`scripts/c7search.py` is the only client. This page records what it sends, what comes back and how
each response maps to an exit status, so an agent can read the output without guessing.

## Request

`GET https://context7.com/api/v3/search` with `Authorization: Bearer <key>`.

| Parameter | Flag | Notes |
|---|---|---|
| `query` | positional | Required. A plain-language question works best ("how to revalidate cached fetches") |
| `library` | `--library`, repeatable | Up to 4. A name (`next.js`) or a Context7 ID (`/vercel/next.js`). More than 4 is a 400 |
| `language` | `--language` | Programming language filter |
| `version` | `--version` | Needs at least one `library`; without one the API answers a misleading 404, so the script refuses it locally (exit 2) |
| `type` | `--type txt\|json` | Default `txt` |

The script also sets `User-Agent: docs-scout/1.0.0`, times out after 30 s, refuses every redirect
(the key is never sent anywhere but the API host) and makes no keyless calls: anonymous use is
documented as a demo tier.

## Response shapes (observed 2026-10-17)

`txt` is a series of blocks separated by `---`:

```text
Library: /vercel/next.js
### Caching
Source: https://nextjs.org/docs/app/getting-started/caching
Short description.
<code>
```

`json` has two arrays:

- `codeSnippets[]`: `codeTitle`, `codeDescription`, `codeLanguage`, `codeTokens`, `codeId` (the
  source URL), `pageTitle`, `codeList[{language, code}]`, `generationDate`, `libraryId`.
- `infoSnippets[]`: `pageId` (the source URL), `breadcrumb`, `content`, `contentTokens`,
  `libraryId`.

The script prints the body on stdout (cut at `--max-chars`, default 12000, with a note naming the
cached full body). It prints one status line and the de-duplicated `source:` URLs on stderr:

```text
docs-scout: key=primary remaining=871 reset=2026-11-01T00:00:00Z cache=miss
source: https://nextjs.org/docs/app/getting-started/caching
```

## Quota headers

Every response carries `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset`. The reset
value is a Unix epoch at the start of the next calendar month UTC (`1793491200` =
2026-11-01T00:00Z), so the quota is monthly. 429 responses add `Retry-After`. The script accepts a
reset given as an epoch, delta seconds or an HTTP-date, and assumes the first of next month when it
is missing.

## Status → exit code

| HTTP | Error code | Script | Exit |
|---|---|---|---|
| 200 | | prints the body, caches it for 24 h | 0 |
| 404 | `no_documentation_found` | prints nothing on stdout (unknown library, or nothing matched) | 3 |
| 400 | `validation_error` | prints the API's message | 2 |
| 429 | rate limited | marks the key exhausted until `Retry-After`/`RateLimit-Reset`, tries the other key; when none is left, names the earliest reset | 75 |
| 401 | `invalid_api_key` | marks the key invalid, tries the other key; when none is left | 78 |
| 403 | access denied | the key is fine (Context7: "check library access permissions or plan"); nothing usable for this request | 3 |
| 301 | library redirected | not followed; stderr says `library moved; retry with --library <redirectUrl>` | 3 |
| other 3xx | | not followed, so the key never reaches another URL | 69 |
| 500, 503 (`search_failed`), 504, network error | | one retry after 2 s on the same key, then gives up | 69 |

Exit 78 also covers a missing config, placeholder keys and unsafe file permissions
([config](config.md)). Exit 2 also covers local validation, which sends no request.

## Caching

Context7 recommends caching results for hours to days. The script caches each successful body
under `${XDG_CACHE_HOME:-~/.cache}/docs-scout/` for 24 hours, keyed by the normalised parameters
(library order does not matter). A hit costs no quota and reports `key=- cache=hit`. Pass
`--no-cache` to force a fresh request, for example when the user asks for the very latest docs.
