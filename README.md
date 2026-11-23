# MOD Supplier Monitor

A static **Quarto + Python** website connecting MOD supplier spending to share-price performance and recent company news.

**[Live website](https://defenceeconomist.github.io/stockmonitor/)**

- **Top-50 workspace:** the 50 largest suppliers by published MOD payments, with the selected company’s price chart and news beside the treemap. Includes 34 quoted and 16 unquoted suppliers in the current source; all 78 remain searchable in the full directory.
- **Portfolio versus market:** spending/equal-weight buy-and-hold baskets in GBP, global/UK accumulating tracker proxies, exact company and FX contributions, breadth, concentration, and Codex news for the leading contributors.
- Interactive treemap: area represents 2024/25 MOD payments; colour represents adjusted share-price performance over a selected window.
- Company price explorer: 1W, 1M, 3M, 6M, YTD, 1Y and 5Y, closing/adjusted prices or rebased to 100.
- Company news: up to 30 recent headlines per quoted company, markers on the daily chart, and a paired session's adjusted close-to-close change. This is a timing association, **not causal attribution**.
- **Codex news desk:** concise, source-linked summaries for the top 50, covering the latest seven days including news after the last completed session. Search by supplier or switch between firms with news and all 50. Private firms receive news searches too.
- **Latest-week price context**: fixed seven-day window, weekly adjusted return, largest daily move, reported catalysts or clearly labelled news context, and up to three supporting reports. Companies without a direct quote or sufficient evidence are explicitly flagged.
- Searchable supplier directory and complete source/methodology notes.
- Responsive layout with keyboard-accessible company selection and directory.

## Sources and scope

The fixed spending universe comes from **Table 4a** of [MOD trade, industry and contracts: 2025](https://www.gov.uk/government/statistics/mod-trade-industry-and-contracts-2025), revised 12 March 2026. Original ODS: `data/source/mod-tic-2025.ods`. The original table includes £50m and above; this project applies **strictly more than £50m** to the published rounded figures: 78 holding companies. A row at exactly £50m is excluded. Values include MOD Core, UKHO and Dstl; Foreign Military Sales are excluded. Ownership and joint-venture attribution follow the source release.

The 50 explicitly mapped direct stock listings are in `data/listings.csv`. Other rows remain visible without a quote. We deliberately do not substitute prices of portfolio companies or parents for unmatched entities such as IBM International C.V. and Turner & Townsend Partners LLP. Mappings need manual review after corporate actions or listing changes; provider company names are retained in the snapshot to support that review.

Prices come from the Yahoo Finance chart endpoint (five years of completed daily sessions); headlines come from company-name Google News RSS searches limited to 90 days, including the unquoted suppliers in the top 50. No API key or browser-side financial API is required. These unofficial public endpoints can be rate limited or change without notice. Review provider terms and data redistribution permissions before commercial use. Only headline metadata/links are stored, never article bodies.

Company charts and treemap returns retain native listing currencies (GBp = pence). The portfolio panel separately translates returns to GBP using daily exchange rates. Performance uses adjusted closes. This is not a calculated investment total return or an investment recommendation. Price/news fetch failures retain the prior successful cache with an explicit stale status. If fewer than 80% of mapped companies return fresh price data, the refresh fails without replacing the snapshot.

### Portfolio comparison and contribution accounting

The portfolio covers the **34 directly quoted companies within today’s top 50**. The 16 unquoted suppliers are excluded, not assigned a zero return. Their exclusion and the quoted firms’ share of top-50 spending are disclosed. Every quoted member must have usable history: a missing price, required FX rate or selected benchmark blocks the panel instead of silently dropping a company. This is the performance of today’s supplier basket, not an investable historical selection strategy or the user’s actual holdings. The fixed 2024/25 spending baseline and current membership introduce hindsight into earlier historical windows.

Default starting weights are each quoted supplier’s MOD payments divided by all quoted top-50 payments; equal weights allocate 1/34 each. Weights reset at the baseline of each selected period. The holdings then drift with buy-and-hold performance; there is no daily or monthly rebalance. The comparison chart includes both weighting choices on the same window. It offers 1W, 1M, 3M, 6M, YTD, 1Y and all common history. The newest listing limits common history; there is no invented pre-listing price series.

Two **accumulating ETF proxies**, downloaded through the existing Yahoo endpoint, provide broad market comparisons:

| Comparison | Saved symbol | Provider and index |
| --- | --- | --- |
| Global, default | `VWRP.L` | [Vanguard FTSE All-World UCITS ETF (Acc)](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-accumulating-Vanguard), tracking FTSE All-World |
| UK | `FTAL.L` | [State Street SPDR FTSE UK All Share UCITS ETF (Acc)](https://www.ssga.com/uk/en_gb/institutional/etfs/state-street-spdr-ftse-uk-all-share-ucits-etf-acc-spyf-gy), tracking FTSE All-Share |

Both use GBP-listed prices. These are fund-price proxies, not licensed index total-return histories: fund fees, tracking differences and premiums/discounts can affect them. Accumulated income is already reflected in the fund; do not add dividends again. Supplier performance uses provider-adjusted closes, which approximate the effect of reported splits and dividends. This is an adjusted-return comparison, not a tax-specific audited investment return; supplier trading costs and personal taxes are excluded.

`portfolio_market` in the snapshot stores both proxies and **GBP per unit** of CAD, EUR, JPY, SEK and USD, with individual fetch timestamps and status. `USDGBP=X` is explicitly allowed to canonicalise to Yahoo’s `GBP=X`; other symbol or instrument mismatches are rejected. GBP uses a rate of 1 and GBp a rate of 0.01. No missing FX value is assumed to equal 1. Failed downloads retain dated caches with stale warnings. Cached builds require no network.

Valuations follow the selected London-listed tracker’s daily calendar. The common end is the minimum latest date across all quoted companies, required FX series and that benchmark, capped at the supplier snapshot date. The baseline is the last common-calendar date on/before the requested start, limited by the latest first observation among the required series. Local holidays use the most recent observation on/before each valuation date, at most seven calendar days old, with no future observations. Quotes across time zones are daily closing observations, not synchronised intraday marks. The panel displays exact dates and warns about stale sources or shortened history.

For initial weight `w`, local adjusted-price ratio `L`, and GBP-per-unit FX ratio `F`, a company’s GBP return is `L × F − 1`. Its contribution is `100 × w × (L × F − 1)` percentage points. Local shares contribute `100 × w × (L − 1)` and currency contributes `100 × w × L × (F − 1)`. The interaction belongs to FX, so local plus FX reconciles exactly to the company and basket returns. Company contributions reconcile to the endpoint of the selected curve. Benchmark excess is the arithmetic difference between basket and proxy returns in percentage points, not a causal market attribution.

The bar chart groups the five largest positive and five largest negative contributors plus all remaining firms; the expandable table lists every member. Breadth uses company GBP returns. The top-five contribution share uses absolute contributions as its denominator, avoiding misleading concentration figures when positive and negative effects cancel. Leading contributor cards reuse the current Codex briefing and source links, with its separate news window displayed. They do not claim that recent stories explain a longer selected return period.

### News session pairing

Publication timestamps are converted to the listing's exchange timezone. Before the normal close, a story maps to that date's session; at/after close and on non-trading dates it maps to the next observed completed session. The paired move is adjusted close / preceding adjusted close − 1. Stories with no subsequent completed session remain pending. Normal close is derived from the provider's current regular trading schedule; historical early closes are not modelled. Intraday sequencing, other stories, macro events, earnings and overnight gaps can all affect the same daily return. Name searches can include irrelevant stories; the feed is not comprehensive. Markers show only stories in the visible chart window.

### Weekly explanations

`scripts/weekly_summary.py` produces deterministic briefings for **only the latest completed week**, independent of the chart's selected horizon. The end is the latest completed session in the snapshot; the start is seven calendar days earlier. Price baselines use the last observed session on/before the start. Each briefing includes its exact observed price dates and the largest absolute daily adjusted move.

The updater fetches a dedicated date-bounded news feed per quoted company, separately from the capped 90-day feed. Evidence must have a mapped session in the measured window and a publication timestamp after the baseline session's normal close and at/before the final close. Stories after the final close cannot explain that week's return. The summaries use company-name checks, quote-page/speculative-content filters, headline theme rules, source ranking and headline deduplication. They do not read article bodies or call an AI API. A directional, explicitly event-linked headline can support a **reported catalyst**; other concrete stories supply **news context**, not causal findings. Every supporting headline links to its source. Missing coverage yields “No clear explanation found”. All unquoted entities also receive an explicit no-quote briefing. Source matching can be imperfect, and no market/sector return attribution is performed.

Weekly price context is available in a collapsed top-50 overview and alongside the selected company’s chart. They regenerate on every data refresh and are stored in the snapshot; older weekly prose is not reused when the window advances. Failed weekly-news requests fall back to the general news feed with a visible coverage caveat. Add or adjust rules with their edge-case tests as new patterns appear.

## Run locally

Install [Quarto](https://quarto.org/docs/get-started/) (tested with 1.8.26), Python 3.12+ and Node.js 22+ (for chart calculation checks):

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m unittest discover -s tests -v
quarto preview
```

The checked-in snapshot makes rendering reproducible and network-free:

```sh
quarto render
```

To refresh the monitor, run this one command from the repository root with your virtual environment activated:

```sh
python3 scripts/update_monitor.py
```

It downloads prices, benchmark proxies, FX, recent headlines and weekly evidence into a temporary candidate, regenerates weekly explanations, runs the Python and chart checks against that candidate, and renders a temporary website. Only after every step succeeds does it replace `data/snapshot.json` and `_site`. The rendered dashboard must match the candidate. A failed download/check/build retains the previous saved snapshot and website. A local lock prevents overlapping runs.

Use `python3 scripts/update_monitor.py --cached` to verify and rebuild the saved data without network downloads. This is also the build path for code pushes. `scripts/update_data.py` remains available as a lower-level fetch command, but does not provide the full check/build process.

Use `python3 scripts/update_monitor.py --refresh-source` to deliberately re-download the pinned March 2026 MOD release. Future annual releases require reviewing the table layout, universe, ticker mapping and methodology, not silently switching datasets.

After each run, inspect `data/update-report.json`: it records success/failure, the failed step and error if any, snapshot date, company count, price-fetch successes and provider warnings. The report and build outputs are local artifacts and are not committed. A successful refresh may contain individual stale series/news; review its warnings before publishing.

For a local update, review `quarto preview`, the update report, and `git diff -- data/snapshot.json`, then commit the snapshot and push to `main` to publish through GitHub Actions. The local command does not commit, push or deploy.

The Quarto pre-render step runs `scripts/build.py` to copy the snapshot into the website assets. Plotly.js is vendored locally in `assets/plotly.min.js` (v3.4.0, MIT, see its header); no chart CDN is required.

## Codex updates and GitHub Pages

Market/news updates and editorial summarisation are intended to run in a scheduled Codex task. No task is created by changing this repository. Use [prompts/codex-update.md](prompts/codex-update.md) as the scheduled prompt, with this repository as its project. A weekly Saturday morning run follows the previous cadence; choose the timing in Codex. For local-file tasks the computer needs to be on with the app running; see the [official scheduled-task documentation](https://learn.chatgpt.com/docs/automations).

The task first runs the verified data refresh, reads `python3 scripts/news_briefing.py --prepare`, writes its own concise editorial prose to `data/news-briefing.json`, validates it with `python3 scripts/news_briefing.py`, and rebuilds with `python3 scripts/update_monitor.py --cached`. The saved prompt includes the exact JSON contract and evidence rules. It leaves changes locally for review unless you explicitly authorize publishing in the task instructions. No extra AI API key is needed: Codex writes the summaries during its task.

The briefing contains every top-50 supplier exactly once, with either a sourced summary or an explicit coverage gap. Its seven-day news window ends at the snapshot timestamp, independently of the completed-session weekly return. Headline matching, noise filtering and source filtering prepare the evidence; Codex chooses and summarises the material developments. Only headline metadata is used, and each cited object must exactly match the current evidence. A validator rejects missing/duplicate suppliers, unknown citations and incorrect date windows. Codex’s prose still needs editorial judgment; structural validation cannot establish every claim’s accuracy.

The briefing records the exact snapshot it summarises. When data advances without a replacement briefing, the build omits old prose and shows an awaiting-update state. Deterministic weekly price context remains available separately. Cached rebuilds preserve a valid Codex briefing. A malformed briefing for the current snapshot fails the build.

`.github/workflows/publish.yml` only runs on pushes to `main` and manual dispatch. It always verifies and builds saved data, then deploys through GitHub Pages. It has **no refresh schedule, provider downloads or snapshot-writing bot commits**. Repository Settings → Pages → Source must be **GitHub Actions**. No additional deployment secrets are required.

After reviewing a Codex update, commit both `data/snapshot.json` and `data/news-briefing.json` together and push to `main` to publish. Check `data/update-report.json` for provider warnings. Failed checks prevent local output promotion or deployment; the previous successful website stays available. A local refresh alone does not publish the site.

If a local process was forcibly stopped, confirm no update is running before removing `.update-lock` and retrying. Interrupted `.update-*` directories can then be removed. The updater rolls back ordinary errors; forced termination during final file replacement may require restoring the snapshot from Git and rebuilding with `--cached`.

## Files

| Path | Purpose |
| --- | --- |
| `index.qmd`, `_quarto.yml` | Quarto site and content |
| `scripts/update_data.py` | Source parsing, price/news downloads and session pairing |
| `scripts/update_monitor.py` | Full update process: candidate, checks, render, report and rollback |
| `scripts/build.py` | Network-free static build preparation and dated briefing validation |
| `scripts/portfolio_data.py` | Dated benchmark and GBP-per-unit FX downloads, with stale-cache fallback |
| `assets/portfolio.js`, `assets/portfolio-ui.js` | Portfolio arithmetic, exact contribution accounting and comparison views |
| `tests/test_portfolio.cjs`, `tests/test_portfolio_data.py` | Accounting identities, coverage, calendars, instrument identity and FX direction |
| `scripts/news_briefing.py` | Compact top-50 evidence and Codex briefing validation |
| `data/news-briefing.json` | Codex-written editorial summaries and supporting headlines |
| `prompts/codex-update.md` | Ready-to-use instructions for a scheduled Codex update |
| `data/listings.csv` | Explicit MOD holding-company to direct listing mapping |
| `data/snapshot.json` | Auditable latest successful cached dataset |
| `assets/app.js`, `assets/styles.css` | Interactive charts and responsive design |
| `tests/test_news_briefing.py` | Top-50 scope, date windows, citation integrity and missing-evidence checks |
| `tests/test_pipeline.py` | Threshold, source, session-pairing and snapshot checks |
| `tests/test_update_monitor.py` | Failed-update preservation, output promotion and overlapping-run checks |

MOD source data © Crown copyright, available under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Market and news content remain subject to their providers' terms. Project code is MIT licensed.
