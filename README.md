# DATAM

Türkiye election poll aggregator and scenario simulator. The static application
lives in `web/` and deploys to GitHub Pages. The data pipeline builds the poll,
seat-allocation, historical house-effect, and demographic datasets.

## What it does

- Aggregates Turkish election polls with time decay and pollster effects.
- Reproduces the 2023 parliamentary and presidential baselines.
- Simulates parliament (D'Hondt, 7% threshold, alliances) and presidential
  first round/runoff scenarios.
- Backtests the aggregator against 2023 and reports uncertainty intervals.
- Estimates two-level historical pollster effects from 2015–2024 polls.
- Correlates province-level election results with TÜİK demographics in the
  Demografi explorer.

## Repository layout

```
config/                 election, party, pollster, house-effect metadata
data/                   2023 actuals, YSK/TÜİK province data
data/processed/         cleaned seat and province results
polls/                  2023 polls and historical poll archive
pipeline/               poll scrapers, allocation, site export, house effects
web/                    static site (HTML/CSS/vanilla JS + D3)
web/demographics.html   correlation explorer (scatter + map + table)
```

## Install and test

Requires Python 3.9+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run python -m unittest discover -s pipeline/tests -v
node --test web/modules/*.test.js
```

## Data commands

```bash
uv run python pipeline/validate_polls.py
uv run --with lxml --with beautifulsoup4 --with html5lib python pipeline/scrape_historical_polls.py
uv run python pipeline/house_effects.py --backtest
uv run python pipeline/export_site.py
uv run python pipeline/demographic_correlation.py
```

The demographic correlation script writes `data/analysis/province_demographics.csv`,
`demographic_correlations.csv`, and `demographic_correlations.md`. It reports raw,
electorate-weighted, and region + electorate-controlled partial correlations.

The 2023 backtest fits house effects on 2015–2019 polls only, so 2023 polls do
not leak into the correction. In the current model the two-level correction did
not beat the raw average; `web/data/house_effects_2019.json` records the
leak-free estimates and the site keeps the effect toggle off by default.

## Local preview

```bash
uv run python -m http.server 8000 --directory web
```

Open `http://localhost:8000/`.

## Data sources

- Turkish Wikipedia election-poll tables.
- YSK open-data API for 2023 results and seat counts.
- TÜİK Nüfus İstatistikleri Portalı for province demographics.

This is a scenario and research tool, not an election forecast. It is not
affiliated with any party or institution.
