# DATAM

Türkiye election poll aggregator and scenario simulator. The static application
lives in `web/` and deploys to GitHub Pages. The data pipeline builds the poll,
seat-allocation, historical house-effect, and demographic datasets.

## What it does

- Aggregates Turkish election polls with time decay and pollster effects.
- Reproduces the 2023 parliamentary and presidential baselines.
- Simulates parliament (D'Hondt, 7% threshold, alliances) and presidential
  first round/runoff scenarios.
- Drills from the 81-province map into a smoothly zoomed ilçe map with actual
  parliamentary votes.
- Backtests the aggregator against 2023 and reports uncertainty intervals.
- Estimates two-level historical pollster effects from 2015–2024 polls.
- Correlates province-level election results with TÜİK demographics in the
  Demografi explorer.

## Typography

The interface uses the self-hosted **Tomorrow** typeface (Google Fonts, SIL Open Font License). Font files and the license live in `web/assets/fonts/`.

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
cd web && node --test modules
cd web && npm ci && npx playwright install chromium && node e2e/smoke.mjs
```

## Data commands

```bash
uv run python pipeline/validate_polls.py
uv run python pipeline/scrape_2028_polls.py
uv run python pipeline/scrape_2028_president_polls.py
uv run --with lxml --with beautifulsoup4 --with html5lib python pipeline/scrape_historical_polls.py
uv run python pipeline/house_effects.py --backtest
uv run python pipeline/house_effects_hierarchical.py
uv run --no-project --python 3.13 --with ysk --with pyyaml python pipeline/build_2024_local.py
uv run python pipeline/backtest_2024_local.py
uv run python pipeline/export_site.py
uv run python pipeline/scrape_2018_parties.py
uv run python pipeline/demographic_correlation.py
uv run python pipeline/demographic_confounding.py
uv run python pipeline/demographic_swing.py
uv run python pipeline/demographic_swing_backtest.py
uv run python pipeline/scrape_kurdish_support.py
uv run python pipeline/project_2028_seats.py
```

The demographic correlation script writes `data/analysis/province_demographics.csv`,
`demographic_correlations.csv`, and `demographic_correlations.md`. It reports raw,
electorate-weighted, and region + electorate-controlled partial correlations.
`pipeline/scrape_2018_parties.py` writes province-level 2018 party shares from
the YSK-derived Wikipedia table. `demographic_correlation.py` uses these to add
2018→2023 swing outcomes for AKP, CHP, MHP, İYİ, and HDP/DEM. The experimental
demographic-swing control uses those party swings; parties without a 2018 result
are left untilted. It is off by default; the suggested global strength is 60%.
The 60% control scales each party toward its own best leave-one-province-out
strength: AKP 0.60, CHP 0.40, MHP/İYİ 0.20, HDP/DEM 0.70. Incumbent-swing MAE
improves from 0.0254 to 0.0218. This is a diagnostic, not a 2028 guarantee.

`pipeline/scrape_kurdish_support.py` builds the HDP/YSP political-support
index (2015–2023). It is a political-support measure, not a Kurdish population
estimate. The simulator clips its `index_z` at ±2 before applying it to
HDP/DEM. An ilçe approximation is also exported, scaled by 2023 HDP/DEM ilçe
votes; it is for exploration and is not used in seat allocation.

`config/parties_2028.yaml` registers the 2028-only parties. YENİ inherits the
CHP district profile; A uses a 70% İYİ, 20% AKP, 10% MHP mix. The app filters
parties by `active_from`, so they are hidden in the 2023 view, then uses the
lineage mix as the district baseline and rakes to the national poll targets.

`pipeline/scrape_2028_polls.py` loads the Turkish Wikipedia 2028 polling
tables into `polls/2028_parliament.json` (2023–2026 polls, including YENİ and
A when listed). `pipeline/scrape_2028_president_polls.py` fills
`polls/2028_president.json` with multi-candidate polls using
`config/candidates_2028.yaml`; pairwise candidate polls are excluded for now.
Each candidate has a 2023 `baseline` (candidate A/B/C/D or parliamentary
profile P12/P10/P22) so new candidates inherit a geographic profile.
`config/alliances_2028.yaml` is intentionally empty until the 2028 alliances
are known; edit it then to activate the alliance threshold.

`web/data/elections.json` defines the 2023 baseline and the 2028 scenario.
`config/2028_seats.yaml` contains the 2028 district seat numbers imported
from the 600 repo's Turkey model (`prDistricts`, 87 districts, 600 seats).
`project_2028_seats.py` preserves those counts in
`web/data/seat_projection_2028.json`; the old growth model remains as a
fallback. Map provinces use full hexagon tiles plus a horizontal remainder
tile when needed; the 600-seat chamber is a clipped hex-lattice half-donut of
100 hexagonal tiles, each split into six triangular seats. `polls/2028_*.json` are
ready for next-election polls; `export_site.py` combines them into
`polls_2028.json`.

The 2023 backtest fits house effects on 2015–2019 polls only, so 2023 polls do
not leak into the correction. The two-level correction did not beat the raw
average. Presidential races now use hierarchical one-level effects, with party
effects partially pooled toward the cross-pollster mean. The president check
improves from 2.41 to 2.34 points. Parliament stays on one-level effects damped
to 50%, because hierarchical pooling is slightly worse there (1.18 vs 1.17).
The effect toggle stays off by default, and
`web/data/house_effects_2019.json` records the leak-free estimates.

`pipeline/build_2024_local.py` uses the `ysk` package to build complete
31 March 2024 actuals: 81 city mayors and 973 district mayors. It requires
Python 3.13 because of that package, so it is run outside the project
environment. The 2024 backtest trains on 2015–2023 polls only and scores all
129 scopes with matching polls: 51 city and 78 district. One-level improves
overall MAE from 2.921 to 2.879 points and winner accuracy from 67.4% to 72.9%;
two-level is marginally better on MAE but worse on winners. The production
local-race mode stays one-level. The 2024 result is diagnostic only, not
production training data.

`pipeline/demographic_confounding.py` reports VIF, pairwise demographic
correlations, swing-model fit, and leave-one-region-out coefficient stability.
Household shares and education shares each sum to one, so their individual OLS
coefficients are not identified even though the composite tilt is; the report
flags this explicitly.

## Local preview

```bash
uv run python -m http.server 8000 --directory web
```

Open `http://localhost:8000/`.

## Data sources and licensing

- Turkish Wikipedia election-poll tables. Poll JSON inherits Wikipedia's
  CC BY-SA terms; verify attribution before redistribution. These are toplines,
  not primary pollster reports.
- YSK open-data API for 2023 results and seat counts. Check YSK's open-data
  terms before commercial use.
- TÜİK Nüfus İstatistikleri Portalı for province demographics. Check TÜİK's
  terms before redistribution.
- Geographic boundaries: geoBoundaries ADM1 (CC BY-SA 2.0) and ADM2 (ODbL 1.0);
  license files are under `web/geo/`.

This is a scenario and research tool, not an election forecast. It is not
affiliated with any party or institution.
