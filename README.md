# MOD Supplier Monitor

A static **Quarto + Python** website connecting MOD supplier spending to share-price performance and recent company news.

**[Live website](https://defenceeconomist.github.io/stockmonitor/)**

- Interactive treemap: area represents 2024/25 MOD payments; colour represents adjusted share-price performance over a selected window.
- Company price explorer: 1W, 1M, 3M, 6M, YTD, 1Y and 5Y, closing/adjusted prices or rebased to 100.
- Company news: up to 30 recent headlines per quoted company, markers on the daily chart, and a paired session's adjusted close-to-close change. This is a timing association, **not causal attribution**.
- Searchable supplier directory and complete source/methodology notes.
- Responsive layout with keyboard-accessible company selection and directory.

## Sources and scope

The fixed spending universe comes from **Table 4a** of [MOD trade, industry and contracts: 2025](https://www.gov.uk/government/statistics/mod-trade-industry-and-contracts-2025), revised 12 March 2026. Original ODS: `data/source/mod-tic-2025.ods`. The original table includes £50m and above; this project applies **strictly more than £50m** to the published rounded figures: 78 holding companies. A row at exactly £50m is excluded. Values include MOD Core, UKHO and Dstl; Foreign Military Sales are excluded. Ownership and joint-venture attribution follow the source release.

The 50 explicitly mapped direct stock listings are in `data/listings.csv`. Other rows remain visible without a quote. We deliberately do not substitute prices of portfolio companies or parents for unmatched entities such as IBM International C.V. and Turner & Townsend Partners LLP. Mappings need manual review after corporate actions or listing changes; provider company names are retained in the snapshot to support that review.

Prices come from the Yahoo Finance chart endpoint (five years of completed daily sessions); headlines come from company-name Google News RSS searches limited to 90 days. No API key or browser-side financial API is required. These unofficial public endpoints can be rate limited or change without notice. Review provider terms and data redistribution permissions before commercial use. Only headline metadata/links are stored, never article bodies.

Prices retain native listing currencies (GBp = pence); there is no FX conversion. Performance uses adjusted closes. This is not a calculated investment total return or an investment recommendation. Price/news fetch failures retain the prior successful cache with an explicit stale status. If fewer than 80% of mapped companies return fresh price data, the refresh fails without replacing the snapshot.

### News session pairing

Publication timestamps are converted to the listing's exchange timezone. Before the normal close, a story maps to that date's session; at/after close and on non-trading dates it maps to the next observed completed session. The paired move is adjusted close / preceding adjusted close − 1. Stories with no subsequent completed session remain pending. Normal close is derived from the provider's current regular trading schedule; historical early closes are not modelled. Intraday sequencing, other stories, macro events, earnings and overnight gaps can all affect the same daily return. Name searches can include irrelevant stories; the feed is not comprehensive. Markers show only stories in the visible chart window.

## Run locally

Install [Quarto](https://quarto.org/docs/get-started/) (tested with 1.8.26) and Python 3.12+:

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

To refresh prices and news manually:

```sh
python3 scripts/update_data.py
quarto render
```

Use `--refresh-source` to deliberately re-download the pinned March 2026 MOD release. Future annual releases require reviewing the table layout, universe, ticker mapping and methodology, not silently switching datasets.

The Quarto pre-render step runs `scripts/build.py` to copy the snapshot into the website assets. Plotly.js is vendored locally in `assets/plotly.min.js` (v3.4.0, MIT, see its header); no chart CDN is required.

## GitHub Pages and weekly refresh

`.github/workflows/publish.yml` runs on pushes to `main`, manual dispatch, and **Saturdays at 08:00 UTC** (08:00 UK winter / 09:00 UK summer). GitHub schedules may run late or be disabled after prolonged repository inactivity. It refreshes the data, runs tests, builds Quarto, saves the data snapshot back to `main`, uploads `_site`, and deploys through the official GitHub Pages actions. Bot snapshot commits use `[skip ci]` to avoid a second build.

Repository Settings → Pages → Source must be **GitHub Actions**. No secrets are required beyond the automatically supplied `GITHUB_TOKEN`; the workflow requests content write and Pages deployment permissions. A failed refresh/build leaves the previous deployed website intact. Individual stale series/news are flagged on the site.

## Files

| Path | Purpose |
| --- | --- |
| `index.qmd`, `_quarto.yml` | Quarto site and content |
| `scripts/update_data.py` | Source parsing, price/news downloads and session pairing |
| `scripts/build.py` | Network-free static build preparation |
| `data/listings.csv` | Explicit MOD holding-company to direct listing mapping |
| `data/snapshot.json` | Auditable latest successful cached dataset |
| `assets/app.js`, `assets/styles.css` | Interactive charts and responsive design |
| `tests/test_pipeline.py` | Threshold, source, session-pairing and snapshot checks |

MOD source data © Crown copyright, available under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Market and news content remain subject to their providers' terms. Project code is MIT licensed.
