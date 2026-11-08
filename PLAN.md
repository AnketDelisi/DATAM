# DATAM — Türkiye Election Poll Aggregator

Status: **M0–M3 done; demographic correlation explorer integrated.**

## Goal

A static GitHub Pages tool that:

- aggregates Turkish election polls,
- simulates presidential and parliamentary outcomes,
- lets users run scenarios (turnout, undecided allocation, swing, runoff
  transfers),
- shows uncertainty and backtests against 2023,
- estimates pollster house effects from 2015–2024 historical polls,
- supports province-level correlation with demographics.

## Decisions

- Live tool for the next election; 2023 is the baseline and backtest.
- Public poll toplines; no microdata.
- Presidential + parliament; parties + alliances.
- National swing and per-province baselines.
- Turnout is separate, with explicit assumptions.
- President = province margin map; parliament = 600-seat hemicycle.
- Vanilla JS + D3, no build step, Turkish-first.
- Historical polls and local elections are used only for house effects.

## Data

| File | Contents | Status |
|---|---|---|
| `data/ysk_2023_il.csv` | 2023 presidential first round by province | have |
| `data/actuals_2023.csv` | 2023 presidential shares, electorate, turnout | have |
| `data/prior_2018.csv` | 2018 incumbent alliance share | have |
| `data/tuik_2023.csv` | province × sex/median age/household/education | have |
| `data/processed/parliament_2023_districts.csv` | one row per electoral district | have |
| `data/processed/parliament_2023_long.csv` | district × party votes | have |
| `data/processed/seat_counts_2023.csv` | seats per electoral district | have |
| `data/processed/actual_seats_2023.csv` | official 2023 seat totals | have |
| `data/processed/president_2023.csv` | first-round/runoff votes by province | have |
| `polls/2023_president.json` | 82 first-round + 14 runoff polls | have |
| `polls/2023_parliament.json` | 49 parliamentary polls | have |
| `polls/historical/` | 2015–2024 polls for house effects | have |
| `web/data/house_effects.json` | full historical two-level + one-level effects | have |
| `web/data/house_effects_2019.json` | leak-free 2023 backtest effects | have |
| `data/analysis/kurdish_support.csv` | HDP/YSP political-support index, 2015–2023 | have |

## Model

### Aggregator

`weight_i = sample_size_i^0.5 * exp(-ln(2) * age_days / half_life) * reliability_i`

- Default half-life: 28 days.
- Undecided: proportional, 2023-pattern, custom.
- Pollster effects: two-level log-ratio model, estimated offline from
  2015–2024 polls. Bloc bias is estimated first; within-bloc party residuals
  are estimated second. Effects are weighted by election type, race type, and
  a three-year recency half-life, then shrunk toward zero.
- The site applies the exported effects when the toggle is on. The 2023
  leak-free backtest did not beat the raw average, so the default is off.

### President

`share[p,c] = baseline_2023[p,c] + (national_poll[c] - national_2023[c])`

Runoff: top two blocs; eliminated blocs split by user-controlled transfers.

### Parliament

`share[d,p] = baseline_2023[d,p] + (national_poll[p] - national_2023[p])`

Then:

1. National threshold: party ≥7%, or alliance total ≥7%.
2. D'Hondt per electoral district among qualifying parties/independents.
3. Sum to 600.

Validation: the domestic-vote D'Hondt model matches 84/87 districts exactly;
the remaining three are one seat off because YSK does not publish the
province-level assignment of overseas votes. Max national party error: 2 seats.

## Milestones

### M0 — data + seat math (done)

- [x] YSK district results, headers, and processed CSVs.
- [x] D'Hondt + threshold + alliance + joint-list rule.
- [x] 600-seat total reproduced; unit tests.

### M1 — static web scaffold (done)

- [x] Province and ilçe GeoJSON, maps, hemicycle, sliders.
- [x] Presidential tab with runoff transfers.
- [x] GitHub Pages workflow.

### M2 — parliament UI and backtest (done)

- [x] Hemicycle, party table, threshold and alliance toggles.
- [x] Province/ilçe maps and 2023 backtest.
- [x] Province click → smoothly zoomed ilçe drilldown.

### M3 — polls + historical house effects (done)

- [x] Poll schema and validator.
- [x] 145 2023 polls; 31 pollsters.
- [x] Aggregator, trend chart, poll table, calculator presets.
- [x] Backtest page: error over time, leaderboard, leave-one-out.
- [x] Bootstrap 90% intervals.
- [x] 2015–2024 historical poll archive and pollster/party aliases.
- [x] Two-level bloc + within-bloc party house-effect model.
- [x] Leak-free 2015–2019 effects for the 2023 backtest.
- [x] Race-specific one-level damping; parliament 50%, president hierarchical.

### M4 — demographics + polish (started)

- [x] Province-level demographic correlation with election shares/swing.
- [x] Region + electorate-controlled partial correlations.
- [x] Scatter, choropleth, and correlation-table explorer.
- [x] Experimental demographic swing control (default off; suggested 60% when enabled).
- [x] Leave-one-province-out diagnostic for the 2018→2023 incumbent and party swings.
- [x] 2018 province-level party shares for party swing targets.
- [x] 2028 scenario scaffold (2023 baseline, configurable seat projection).
- [x] 2028 poll ingestion files and export/validation path.
- [x] HDP/YSP political-support index, 2015–2023 (not a population estimate).
- [x] Poll table shows raw values with adjusted subtext and winner highlight.
- [ ] 2024 extensions and fuller confounding diagnostics.
- [ ] Final 2028 election calendar and official seat map.
- [x] Browser smoke test in CI.
- [ ] Accessibility and shareable scenario polish.

## Commands

```bash
uv sync
uv run python -m unittest discover -s pipeline/tests -v
cd web; node --test modules
uv run python pipeline/validate_polls.py
uv run --with lxml --with beautifulsoup4 --with html5lib python pipeline/scrape_historical_polls.py
uv run python pipeline/house_effects.py --backtest
uv run python pipeline/house_effects_hierarchical.py
uv run python pipeline/export_site.py
uv run python pipeline/scrape_2018_parties.py
uv run python pipeline/demographic_correlation.py
uv run python pipeline/demographic_swing.py
uv run python pipeline/demographic_swing_backtest.py
uv run python pipeline/scrape_kurdish_support.py
uv run python pipeline/project_2028_seats.py
```

## Deployment

Local preview:

```bash
uv run python -m http.server 8000 --directory web
```

GitHub Pages: Settings → Pages → Build and deployment → Source: GitHub
Actions. The workflow runs tests, rebuilds `web/data`, and deploys `web/` on
every push to `main`.

## Open issues

- Overseas votes affect the national threshold; verify YSK treatment.
- Joint lists: v1 treats guest parties as part of the host list.
- 2028 seat counts need a population projection and manual override.
- Legal poll-publication blackout: add a freeze flag.
- Wikipedia polls are toplines only; crosstabs need pollster PDFs.
- Demographic correlation is descriptive; causal inference needs more design.
