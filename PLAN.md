# DATAM — Türkiye Election MRP + Poll Aggregator

Status: **M0–M3 data + aggregator + calculator + backtest done; MRP-lite next.**

## Goal

A static GitHub Pages tool that:

- aggregates Turkish election polls,
- estimates presidential and parliamentary outcomes,
- lets users run scenarios (turnout, undecided allocation, swing, runoff transfers),
- shows uncertainty and backtests against 2018/2023.

The product is a **statistical model**, not the legacy LLM simulator. The LLM
pipeline is kept only as a historical baseline.

## Locked decisions

- **Live tool** for the next election; 2023 is the baseline and backtest.
- **Replace the LLM** in the product path; keep it as a comparison row.
- **Public poll toplines/crosstabs**; no microdata in v1.
- **Presidential + parliament**; parties + alliances.
- **Blocs with user-mapped candidate names** for the president tab.
- **Manual JSON polls**, one file per poll.
- **Runoff transfer sliders**.
- **Swing MRP (Design A)**, not ecological inference, in v1.
- **Tier 0 default**, MRP-lite behind a toggle; promote only if backtests win.
- **Turnout separate**, with sliders and explicit assumptions.
- **President = province margin map; parliament = 600-seat hemicycle.**
- **Vanilla JS + D3**, no build step, Turkish-first.
- **No scraping, no local elections, no true MRP** in v1.

## Data

| File | Contents | Status |
|---|---|---|
| `data/ysk_2023_il.csv` | 2023 presidential first round by province | have |
| `data/actuals_2023.csv` | 2023 presidential shares, electorate, turnout | have |
| `data/prior_2018.csv` | 2018 incumbent alliance share | have |
| `data/tuik_2023.csv` | province × sex/median age/household/education | have |
| `data/raw/ysk/2023_parliament/` | raw YSK parliamentary API snapshots | M0 |
| `data/processed/parliament_2023_districts.csv` | one row per electoral district | M0 |
| `data/processed/parliament_2023_long.csv` | district × party votes | M0 |
| `data/processed/seat_counts_2023.csv` | seats per electoral district | M0 |
| `data/processed/actual_seats_2023.csv` | official 2023 seat totals | M0 |
| `data/processed/party_headers_2023.csv` | YSK party/independent ID map | M0 |
| `data/raw/ysk/2023_president/` | raw first-round/runoff API snapshots | M1 |
| `data/processed/president_2023.csv` | first-round/runoff votes by province | M1 |
| `data/processed/ilce_geo_mapping.csv` | YSK ilçe ↔ ADM2 feature map | M1 |
| `web/geo/tr-provinces.geojson` | 81 province polygons | M1 |
| `web/geo/tr-ilce.geojson` | 973 ilçe polygons | M1 |
| ADNKS province × age × sex | poststratification cells | TODO |
| `polls/schema.json` | poll JSON schema | M3 |
| `polls/2023_president.json` | 82 first-round + 14 runoff polls | M3 |
| `polls/2023_parliament.json` | 49 parliamentary polls | M3 |
| `web/data/polls_2023.json` | combined poll payload for the site | M3 |

### YSK API

- Base: `https://acikveri.ysk.gov.tr/api/`
- 2023 election: `secimId=20230`
- Parliamentary: `secimTuru=8`
- Presidential first round: `secimTuru=9`
- 2023 runoff: `secimId=20240`
- Electoral districts: `getIlList?secimId=20230&secimTuru=8` (87, 600 seats)
- Results: `getSecimSandikSonucList` with `yurtIciDisi=1`
- Party/independent headers: `getIttifakSecimSonucBaslikList`
- Actual seats: `getPartiKazanimSayisi`

## Model

### Aggregator

`weight_i = sample_size_i^0.5 * exp(-ln(2) * age_days / half_life) * reliability_i`

- House effects: hierarchical pollster random effects.
- Undecided: proportional, 2023-pattern, custom.
- Time trend: random walk; 28-day half-life default.

### President

Tier 0 (default):

`share[p,c] = baseline_2023[p,c] + (national_poll[c] - national_2023[c])`

Tier 1 (MRP-lite, toggle):

- Unit `u` = province (upgrade to district if ADNKS district age-sex exists).
- Cell `j = (u, age, sex, education)`.
- Baseline ALR: `b[j,c] = log(s[u,c]^2023) - log(s[u,ref]^2023)`.
- Swing: `delta[j,c] = gamma[c] + alpha[age,c] + beta[sex,c] + delta_edu[edu,c] + rho[region,c] + w[u,c] + epsilon`.
- `pi[j,c] = softmax(b[j,c] + delta[j,c])`.
- Poststratify with `W[j] = N[j] * T[j]`.
- Anchor `w[u,c]` on 2023; fit to poll crosstabs.

Runoff: top two blocs; eliminated blocs split by user-controlled transfers.

### Parliament

Tier 0 (default):

`share[d,p] = baseline_2023[d,p] + (national_poll[p] - national_2023[p])`

Then:

1. National threshold: party ≥7%, or alliance total ≥7%.
2. D'Hondt per electoral district among qualifying parties/independents.
3. Sum to 600.

Tier 1: MRP-lite party shares by cell, aggregated to district; then the same
seat allocation.

Validation target: reproduce the official 2023 600-seat total. The current
domestic-vote D'Hondt model matches 84/87 districts exactly; the remaining
3 provinces are one seat off each because YSK does not publish the
province-level assignment of overseas votes. Max national party error: 2 seats.

## Repo layout

```
data/
  raw/ysk/
  processed/
polls/
config/
  alliances_2023.yaml
  election_2028.yaml
pipeline/
  fetch_ysk.py
  allocate.py
  build_cells.py
  aggregate.py
  fit_mrp.py
  export_site.py
  tests/
web/
  index.html
  app.js
  modules/
  lib/d3.min.js
  data/
  geo/
legacy/            # existing FlockVote code, later
PLAN.md
```

## Milestones

### M0 — data + seat math (done)

- [x] Locate YSK open-data API.
- [x] Identify 87 electoral districts and 600 seats.
- [x] Fetch all district results and headers.
- [x] Build processed CSV files.
- [x] Implement D'Hondt + threshold + alliance + joint-list rule.
- [x] Reproduce the 600-seat total; 84/87 districts exact.
- [x] Add unit tests and a self-check.

Known M0 limitation: Batman, Isparta, and Kahramanmaraş are one seat off each.
The residual is consistent with overseas votes, which the YSK API exposes only
as a national total, not by province. `allocate.py --strict` fails on this;
the default run reports it and passes with max party error 2.

### M1 — static web scaffold (first slice done)

- [x] `web/index.html`, `styles.css`, `app.js`
- [x] Province GeoJSON (geoBoundaries ADM1, CC BY-SA 2.0).
- [x] 973 ilçe polygons (geoBoundaries ADM2, ODbL 1.0) with parent-province
      join and YSK ilçe matching (`pipeline/build_ilce_mapping.py`).
- [x] JS D'Hondt allocator + Node test; matches the Python 2023 model
      (P9 266, P11 51, P12 62, P21 168, P22 44, P10 5, P13 4).
- [x] Interactive province/ilçe map toggle, 600-seat hemicycle, party sliders,
      threshold input, alliance toggle, shareable URL state.
- [x] GitHub Pages workflow (`.github/workflows/pages.yml`) and `web/.nojekyll`.
- [x] Verified in headless Chrome (province and ilçe modes).
- [x] Presidential tab (`web/president.html`): first-round swing, runoff
      transfer sliders, editable candidate names, province map, result bars,
      shareable URL state.
- [x] YSK first-round/runoff data by province (`pipeline/fetch_president.py`,
      `data/processed/president_2023.csv`). Domestic ballots only.

Acceptance: the site loads from `web/`, the 2023 baseline produces 600 seats,
the presidential baseline reproduces the domestic 2023 first round/runoff, and
the Pages workflow deploys `web/` from `main`.

### M2 — parliament Tier 0 + UI (core done)

- [x] Hemicycle, party table, threshold and alliance toggles.
- [x] Province/ilçe maps and 2023 backtest.
- [ ] Threshold sensitivity chart (optional).

Acceptance: manual national shares produce plausible seats; 2023 backtest matches.

### M3 — polls + MRP-lite (data + aggregator done, MRP-lite next)

- [x] Poll schema (`polls/schema.json`) and validator
      (`pipeline/validate_polls.py`).
- [x] Turkish Wikipedia scraper (`pipeline/scrape_wikipedia_polls.py`).
- [x] 145 polls ingested: 82 first round, 14 runoff, 49 parliamentary;
      31 pollsters; 2023-03-15 to 2023-05-26.
- [x] Combined site payload (`web/data/polls_2023.json`).
- [x] Aggregator (`web/polls.html`, `web/polls.js`,
      `web/modules/aggregate.js`): time decay, pollster effects, normalize
      toggle, trend chart, poll table, inline 2023 comparison.
- [x] Calculator integration: “Anket ortalaması” applies the 28-day,
      no-house-effect aggregate to the president and parliament sliders
      (`web/modules/poll_preset.js`).
- [x] Dedicated backtest page (`web/backtest.html`, `web/backtest.js`,
      `web/modules/backtest.js`): error over time, pollster leaderboard,
      leave-one-pollster-out.
- [ ] MRP-lite (needs crosstabs; the Wikipedia tables are toplines only).

Poll source: Turkish Wikipedia's post-calendar tables. The pre-calendar
hypothetical-candidate tables are excluded in v1. Aggregator defaults: 28-day
half-life, house effects off, normalize on.

Commands:

```bash
uv run --with lxml --with beautifulsoup4 --with html5lib python pipeline/scrape_wikipedia_polls.py
uv run python pipeline/validate_polls.py
```

Acceptance: the validator passes and the backtest decides the default model.

### M4 — CI, docs, polish

- GitHub Actions validate polls, run tests, build JSON, deploy Pages.
- Turkish/English toggle if desired; accessibility; shareable scenarios.

## Deployment

- Local preview: `uv run python -m http.server 8000 --directory web`, then
  open `http://localhost:8000/`.
- GitHub Pages: **Settings → Pages → Build and deployment → Source:
  GitHub Actions**. The workflow runs tests, rebuilds `web/data`, and deploys
  `web/` on every push to `main`.
- Commit `web/`, `data/processed/`, `polls/`, `pipeline/`,
  `config/alliances_2023.yaml`, and `.github/workflows/pages.yml`.
- Poll JSON is committed; the Wikipedia scraper is not run in CI. The test
  suite validates the committed poll files.
- The province GeoJSON is geoBoundaries CC BY-SA 2.0. The ilçe GeoJSON is
  geoBoundaries ADM2, ODbL 1.0. License files live beside the assets.
- After replacing the province GeoJSON, run
  `uv run python pipeline/rewind_geojson.py`; d3-geo expects the opposite ring
  winding from the source file.
- After replacing the ilçe GeoJSON, run
  `uv run --with shapely python pipeline/build_ilce_mapping.py`; it adds the
  parent province, matches YSK ilçe names, rewinds rings, and writes
  `data/processed/ilce_geo_mapping.csv`. Commit both the GeoJSON and the mapping.
- `web/.nojekyll` is included so Pages serves the files as-is.

## Open issues

- ADNKS province × age × sex is the main data gap.
- Overseas votes affect the national threshold; verify YSK treatment.
- Joint lists: v1 treats guest parties as part of the host list.
- 2028 seat counts: project from population and allow manual override.
- Legal poll-publication blackout: add a freeze flag.
- Wikipedia polls are toplines only; crosstabs need pollster PDFs. Fall back to
  national swing when absent.

## Backtest metrics

- National share error.
- Province/district MAE.
- Winner accuracy.
- Seat MAE and total absolute deviation.
- 80%/95% interval coverage.
- Compare Tier 0, Tier 1, persistence, and the legacy LLM.
