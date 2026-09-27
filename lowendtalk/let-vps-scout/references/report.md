# Report

The report is one self-contained HTML file with a fixed design. Every run looks the same so reports can be compared over time. `init` copies `assets/report-template.html` to `<run>/report.html`; you fill its content and `publish` validates it and archives it.

## Contents

- [Rules](#rules)
- [Slots](#slots)
- [Components](#components)
- [Writing](#writing)
- [Publish](#publish)

## Rules

- **Change content, not design.** Edit only between `<!-- slot:name -->` and `<!-- /slot:name -->` markers, plus the `<title>` text. Leave `<style>`, `<script>`, section headings, table headers and the markers themselves unchanged; `publish` refuses a report whose style or script differs from the template or whose markers moved.
- **Replace all sample content.** Every element carrying `data-sample` is example material. Remove it; `publish` refuses a report where any remains. A section with nothing to show gets an empty-state line, not a deleted section.
- **Self-contained.** No external stylesheets, scripts, images or fonts. Plain `<a href>` links to LET threads, product pages, order pages and the exchange-rate source are expected. Do not link to files in the run folder; they will be gone.
- **Build tables from the ledger.** Take every figure from `candidates.csv` and `fx.csv` so the report and ledger agree. Only `verified` candidates appear in the ranking tables.
- Title: `Cheapest European VPS for a game server, <day month year>` (adjust the wording if the brief was overridden).

## Slots

| Slot | Content |
|---|---|
| `masthead` | `h1`, a one-sentence `.brief` stating the effective requirements and check date, and a `.facts` list: verified annual plans, providers checked, LET listing pages, exchange-rate source and date |
| `picks` | Two `article.pick` blocks: cheapest verified annual plan, then best inexpensive 6+ vCPU option. If no 6+ vCPU plan was verified, say so in the second block with the nearest lead |
| `ladder` | `ol.ladder-data` with one `li` per verified annual IPv4 plan: `data-eur` (first-year EUR), `data-vcpu`, and `data-pick="<short name>"` on the two picks only. The `li` text is the readable fallback |
| `annual` | One `tbody` per verified annual plan, cheapest first; the cheapest gets `class="is-pick"` |
| `upgrades` | 6+ vCPU choices and substantial upgrades with the extra cost over the cheapest plan; the 6+ pick gets `class="is-pick"` |
| `nonannual` | Exceptional monthly or multi-year alternatives with the full upfront commitment |
| `altconn` | Qualifying IPv6-only or NAT plans and their connectivity limitation |
| `leads` | Unavailable, blocked or provisional leads that could change the decision, with status, why it matters and what is missing |
| `coverage` | `.facts` (listing pages and batches, unique threads, comment pages read, provider sites checked, verification window, exchange-rate source) and `.prose` paragraphs: stopping condition reached, intentional reading limits, blocked or unfinished work |
| `appendix` | `details` sections: excluded plans with reasons, threads read with pages, providers checked with outcomes, gaps, exchange rates. These replace the ledger once the run folder is gone |
| `footer` | Run ID, skill name and a reminder to confirm prices at checkout |

## Components

Ranking row, with an optional note row for network details, restrictions, payment-dependent totals and verification time:

```html
<tbody class="is-pick">
  <tr>
    <td class="rank">1</td>
    <td class="plan"><strong>Provider Plan</strong><span class="sub">Coupon CODE, first year only</span></td>
    <td>City, CC</td>
    <td>4 vCPU shared<span class="sub">AMD EPYC 9454P</span></td>
    <td class="num">8 GB</td>
    <td>120 GB NVMe</td>
    <td>Included</td>
    <td class="num"><strong>€71.88</strong><span class="sub">USD 78.00</span></td>
    <td class="num">€95.88<span class="sub">USD 104.00</span></td>
    <td class="num">€5.99</td>
    <td>Yes<span class="sub">BTC, USDT</span></td>
    <td class="links"><a href="...">Order</a><a href="...">LET</a></td>
  </tr>
  <tr class="note"><td colspan="12"><p>1 Gbit/s port, 20 TB transfer. Game servers allowed. Verified 27 Sep 2026 14:12 CEST.</p></td></tr>
</tbody>
```

- Match each table's column count: `annual` 12, `upgrades` 8, `nonannual` 9, `altconn` 7, `leads` 5.
- Inexpensive upgrade on a ranked row: `<span class="tag">+2 vCPU and 4 GB for €17.52 more</span>` inside the plan cell. It highlights without reordering.
- Lead status: `<span class="status status--provisional">Provisional</span>`; variants `--verified`, `--blocked`, `--unavailable`, `--unknown`.
- Empty section: `<tbody><tr><td colspan="N" class="empty">No qualifying IPv6-only or NAT plans were found.</td></tr></tbody>`; outside tables use `<p class="empty">`.
- Unknown values: write `Unknown`, never leave a cell blank or guess.

## Writing

Plain, specific, sentence case. State facts as observed, and name unknowns as unknown. Prices: `€71.88` with two decimals in EUR; original currency as `USD 78.00`. Dates: `27 Sep 2026 14:12 CEST`. Describe the result as the cheapest verified offers found within the stated coverage, not as exhaustive.

## Publish

```sh
python3 scripts/ledger.py publish <run>             # final report
python3 scripts/ledger.py publish <run> --partial   # interrupted run
```

It checks the design lock, slot markers, leftover sample content and external resources, embeds the fonts and writes `<archive>/<year>/<date>_let-vps-report.html` (default archive `~/Documents/Research/LET-VPS`; override with `--archive` or `LET_VPS_ARCHIVE`). If it refuses, fix the listed problem in `report.html` and publish again. Open the published file once to confirm it renders.
