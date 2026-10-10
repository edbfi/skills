# Research method

Aim for broad provider discovery, selective comment reading and rigorous verification of competitive plans. Do not crawl every comment or enumerate every product configuration.

## Contents

- [Discovery and thread reading](#discovery-and-thread-reading)
- [Provider investigation](#provider-investigation)
- [Shortlisting and purchase verification](#shortlisting-and-purchase-verification)
- [Pricing and currency](#pricing-and-currency)
- [Adaptive stopping rule](#adaptive-stopping-rule)

## Discovery and thread reading

1. Start at https://lowendtalk.com/categories/offers and inspect **20 consecutive offer-listing pages**, beginning with page 1. These are listing pages, not threads.
2. Record every discussion linked from those listings, sticky threads included, in `listings.csv` and `threads.csv`. Deduplicate by the stable discussion ID in the thread URL (`/discussion/<id>/...`). Open every unique thread; do not skip one because its title or advertised configuration looks unsuitable, since small or mislabelled offers often lead to competitive larger plans.
3. Read each thread's **opening post and final comment page**. If they are the same page, read it once. If the final page is too sparse to explain a relevant update, also read the preceding page. Open other comment pages only for a concrete lead: a referenced coupon, replacement offer, larger configuration or restock. Use thread search or linked references to find it efficiently.
4. Extract provider identities, relevant offers, public product links and coupons. Record exactly which comment pages were read in `pages_read`.
5. Save listing URLs with capture timestamps and the thread IDs seen on each page. Listings shift as threads get bumped: do a limited overlap check between batches (the last threads of one page against the first of the next) instead of restarting the crawl to chase bumps, and note any resulting uncertainty in `overlap_note`.
6. Treat old offers as discovery leads, not current prices. LowEndBox and linked deal pages are useful supplementary leads, but they do not count toward LET listing coverage.

## Provider investigation

Investigate the current official website and ordering portal of **every distinct provider offering server products** found in the material read, even when its LET promotion is expired, unavailable or below the brief. A small advertised VPS may sit next to a competitive larger plan.

- Consolidate all threads and coupons for the provider first, then investigate its catalogue once. Revisit only for new relevant evidence or finalist rechecks.
- Check VPS/VDS catalogues, current promotions, clearance or special-offer sections, European location variants and annual billing discounts through public, linked paths. Do not guess hidden endpoints.
- Follow relevant product and order links. Open configurable upgrades when they could reach the minimum or yield an inexpensive resource upgrade; skip combinations that cannot plausibly affect the recommendations.
- During discovery capture enough to judge competitiveness: plan, advertised price, currency, billing term, vCPUs, actual RAM, European locations, apparent availability, IPv4 status when visible and source links. Record these as `provisional` candidates.
- Defer payment, network, policy and renewal detail until a plan is a credible contender.
- When a provider has no qualifying or competitive option, record a concise `outcome` and `reason` (for example `no-qualifying`: "largest EU plan 2 vCPU/4 GB").
- Deduplicate identical offers but keep materially distinct locations, configurations and coupon terms as separate candidates. Expired, deprecated and unavailable plans never enter the purchasable results.

## Shortlisting and purchase verification

Maintain a provisional shortlist covering the cheapest annual plans, inexpensive 6+ vCPU choices and substantial resource upgrades. Fully verify any candidate that could enter the final comparison or displace a recommendation; if it fails, move to the next. Do not fully configure clearly uncompetitive plans merely because they qualify.

For each finalist:

1. Follow the official product link into its configurator or cart. Select the qualifying European location, specifications, required public IPv4 and annual billing. Test applicable published coupons.
2. Verify stock, payable first-year total, setup fees, mandatory extras, discount scope and whether the discount recurs. Establish the normal annual renewal total where possible, otherwise `unknown`. Annual billing alone does not establish a guaranteed renewal price.
3. From official sources, collect CPU model, shared versus dedicated cores, storage, port speed and transfer allowance where disclosed, crypto methods, payment fees, and game-server and CPU-use policies. Distinguish explicit permission (`allowed`), explicit prohibition (`prohibited`, which excludes the plan) and `unknown`. Note relevant explicit CPU-use restrictions such as sustained-load throttling.
4. Record public IPv4 availability. IPv6-only and NAT-only plans stay out of the main ranking; note their connectivity limitation.
5. Set `state=verified` with `verified_at` only after the cart shows the payable total. If login, challenges or missing information prevent it, set `state=blocked`, add a gap, and continue.

Recheck the cheapest annual plan, the recommended 6+ vCPU option and highlighted upgrades before delivery. Keep verified purchasable plans clearly separate from provisional or blocked leads.

## Pricing and currency

- Rank by first-year total excluding VAT. If a VAT-inclusive total cannot reliably be split into net and tax, mark the net price unverified in `notes` instead of guessing.
- Normalize to EUR with one dated exchange-rate source visited through the run's browser (for example ECB reference rates). Store rates once in `fx.csv` and reuse them for the whole run; keep original-currency totals alongside.
- For each plan show annual first-year cost, annual renewal and first-year monthly equivalent (first year / 12).
- Put exceptional monthly or multi-year alternatives in their own list with the full upfront commitment.
- When a payment method changes the total (for example a crypto processor fee), record both totals.

## Adaptive stopping rule

After the first 20 listing pages and their thread and provider checks, continue in **five-page batches** with the same selective reading and provider investigation. Track each batch in `batches.csv`.

Stop after **two consecutive completed batches leave the substantive recommendations unchanged**: the cheapest verified qualifying annual plan, the best inexpensive 6+ vCPU choice and compelling resource upgrades. A change must be backed by purchase verification. Duplicate offers, trivial variations and merely beating an expensive entry elsewhere in the comparison do not reset the counter.

Before closing a batch, resolve accessible leads that could plausibly change those recommendations. Record blocked leads as unresolved, not ruled out. Explain any judgment about whether an upgrade is substantial in the batch `reason`. There is no runtime limit; if interrupted, keep the exact resume point and report partial coverage.
