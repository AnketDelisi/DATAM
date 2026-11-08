"""Province-level correlations between 2023 outcomes and TÜİK demographics.

    python pipeline/demographic_correlation.py

Outputs:
  data/analysis/province_demographics.csv
  data/analysis/demographic_correlations.csv
  data/analysis/demographic_correlations.md
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "analysis"
TUIK = ROOT / "data" / "tuik_2023.csv"
ACTUALS = ROOT / "data" / "actuals_2023.csv"
PRIOR = ROOT / "data" / "prior_2018.csv"
PRIOR_PARTIES = ROOT / "data" / "2018_party_shares.csv"
PARLIAMENT = ROOT / "web" / "data" / "parliament_2023.json"
WEB_OUT = ROOT / "web" / "data" / "demographics.json"
REGIONS = ROOT / "config" / "regions.yaml"

TR = {
    "\u0130": "I", "\u0131": "i",
    "\u015e": "S", "\u015f": "s",
    "\u011e": "G", "\u011f": "g",
    "\u00c7": "C", "\u00e7": "c",
    "\u00d6": "O", "\u00f6": "o",
    "\u00dc": "U", "\u00fc": "u",
    "\u00c2": "A", "\u00e2": "a",
}

PARTY_IDS = {
    "P9": "AKP",
    "P21": "CHP",
    "P11": "MHP",
    "P22": "IYI",
    "P12": "HDP_DEM",
    "P10": "YRP",
    "P13": "TIP",
    "P24": "ZP",
    "P8": "BBP",
}

PARTY_SWINGS = ["AKP", "CHP", "MHP", "IYI", "HDP_DEM"]
SWING_OUTCOMES = ["incumbent_swing", *(f"{party}_swing" for party in PARTY_SWINGS)]

OUTCOMES = [
    "erdogan",
    "kilicdaroglu",
    "ogan",
    "ince",
    "turnout",
    *SWING_OUTCOMES,
    "AKP",
    "CHP",
    "MHP",
    "IYI",
    "HDP_DEM",
    "YRP",
    "TIP",
    "ZP",
]

DEMOGRAPHICS = [
    "female_share",
    "median_age",
    "hh_1_2",
    "hh_3_4",
    "hh_5plus",
    "edu_primary",
    "edu_secondary",
    "edu_high_school",
    "edu_university",
]


def normalize_province(value) -> str:
    text = str(value).strip()
    for source, target in TR.items():
        text = text.replace(source, target)
    return re.sub(r"[^A-Z]", "", text.upper())


def load_demographics() -> pd.DataFrame:
    raw = pd.read_csv(TUIK, skiprows=1)
    raw["key"] = raw["province"].map(normalize_province)
    raw["value"] = raw["value"].astype(str).str.strip()

    sex = raw[raw["attribute"] == "Sex"].pivot_table(
        index="key", columns="value", values="count", aggfunc="sum"
    )
    sex["female_share"] = sex["Female"] / (sex["Female"] + sex["Male"])

    median = (
        raw[raw["attribute"] == "Median_Age"][["key", "count"]]
        .drop_duplicates("key")
        .set_index("key")
        .rename(columns={"count": "median_age"})
    )

    household = raw[raw["attribute"] == "Household_Size"].pivot_table(
        index="key", columns="value", values="count", aggfunc="sum"
    )
    household = household.div(household.sum(axis=1), axis=0)
    household = household.rename(columns={
        "1-2 persons": "hh_1_2",
        "3-4 persons": "hh_3_4",
        "5+ persons": "hh_5plus",
    })

    education = raw[raw["attribute"] == "Education"].pivot_table(
        index="key", columns="value", values="count", aggfunc="sum"
    )
    education = education.div(education.sum(axis=1), axis=0)
    education = education.rename(columns={
        "Primary or below": "edu_primary",
        "Secondary": "edu_secondary",
        "High school": "edu_high_school",
        "University": "edu_university",
    })

    frame = pd.concat(
        [sex[["female_share"]], median, household, education], axis=1
    )
    return frame[DEMOGRAPHICS]


def load_regions() -> dict[str, str]:
    payload = yaml.safe_load(REGIONS.read_text(encoding="utf-8"))
    mapping = {}
    for region, provinces in payload["regions"].items():
        for province in provinces:
            mapping[province] = region
    return mapping


def load_parliament() -> pd.DataFrame:
    payload = json.loads(PARLIAMENT.read_text(encoding="utf-8"))
    rows = []
    for province in payload["provinces"]:
        row = {"key": normalize_province(province["name"])}
        for party_id, name in PARTY_IDS.items():
            row[name] = province["shares"].get(party_id, 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


def load_prior_parties() -> pd.DataFrame:
    frame = pd.read_csv(PRIOR_PARTIES)
    return frame[["key", *PARTY_SWINGS]].rename(
        columns={party: f"{party}_2018" for party in PARTY_SWINGS}
    )


def build_dataset() -> pd.DataFrame:
    actuals = pd.read_csv(ACTUALS)
    actuals["key"] = actuals["province"].map(normalize_province)

    prior = pd.read_csv(PRIOR)
    prior["key"] = prior["province"].map(normalize_province)
    prior = prior[["key", "incumbent_share"]]

    frame = actuals.merge(prior, on="key", how="left", validate="one_to_one")
    frame = frame.merge(load_parliament(), on="key", how="left", validate="one_to_one")
    frame = frame.merge(load_prior_parties(), on="key", how="left", validate="one_to_one")
    frame = frame.merge(load_demographics(), on="key", how="left", validate="one_to_one")
    regions = load_regions()
    frame["region"] = frame["key"].map(regions)
    frame["incumbent_swing"] = frame["erdogan"] - frame["incumbent_share"]
    for party in PARTY_SWINGS:
        frame[f"{party}_swing"] = frame[party] - frame[f"{party}_2018"]

    missing = frame[DEMOGRAPHICS + OUTCOMES + ["region"]].isna().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        raise SystemExit(f"missing province data:\n{missing}")

    return frame.sort_values("key").reset_index(drop=True)


def weighted_corr(x: pd.Series, y: pd.Series, weights: pd.Series) -> float:
    w = weights.astype(float)
    mx = (w * x).sum() / w.sum()
    my = (w * y).sum() / w.sum()
    cov = (w * (x - mx) * (y - my)).sum()
    vx = (w * (x - mx) ** 2).sum()
    vy = (w * (y - my) ** 2).sum()
    if vx <= 0 or vy <= 0:
        return float("nan")
    return float(cov / math.sqrt(vx * vy))


def residualize(values: pd.Series, controls: pd.DataFrame) -> np.ndarray:
    matrix = np.column_stack([
        np.ones(len(controls)),
        controls.to_numpy(dtype=float),
    ])
    beta, _, _, _ = np.linalg.lstsq(matrix, values.to_numpy(dtype=float), rcond=None)
    return values.to_numpy(dtype=float) - matrix @ beta


def partial_correlation(
    frame: pd.DataFrame, outcome: str, demographic: str
) -> tuple[float, float, int]:
    pair = frame[[outcome, demographic, "electorate", "region"]].dropna().copy()
    pair["log_electorate"] = np.log(pair["electorate"].astype(float))
    dummies = pd.get_dummies(pair["region"], drop_first=True, dtype=float)
    controls = pd.concat([pair[["log_electorate"]], dummies], axis=1)
    residual_outcome = residualize(pair[outcome], controls)
    residual_demographic = residualize(pair[demographic], controls)
    r = float(np.corrcoef(residual_outcome, residual_demographic)[0, 1])
    df = len(pair) - np.linalg.matrix_rank(np.column_stack([
        np.ones(len(controls)), controls.to_numpy(dtype=float)
    ])) - 1
    return r, p_value_approx(r, max(df, 4)), len(pair)


def p_value_approx(r: float, n: int) -> float:
    if n < 4 or not math.isfinite(r) or abs(r) >= 1:
        return 0.0 if abs(r) >= 1 else float("nan")
    z = math.atanh(r) * math.sqrt(n - 3)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def compute_correlations(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in OUTCOMES:
        if outcome not in frame:
            continue
        for demographic in DEMOGRAPHICS:
            pair = frame[[outcome, demographic, "electorate"]].dropna()
            n = len(pair)
            if n < 3:
                continue
            r = float(pair[outcome].corr(pair[demographic]))
            rho = float(
                pair[outcome].rank().corr(pair[demographic].rank())
            )
            wr = weighted_corr(
                pair[outcome], pair[demographic], pair["electorate"]
            )
            partial_r, partial_p, partial_n = partial_correlation(
                frame, outcome, demographic
            )
            rows.append({
                "outcome": outcome,
                "demographic": demographic,
                "n": n,
                "pearson_r": r,
                "spearman_rho": rho,
                "weighted_r": wr,
                "p_approx": p_value_approx(r, n),
                "partial_r": partial_r,
                "partial_p_approx": partial_p,
                "partial_n": partial_n,
                "controls": "region + log(electorate)",
            })
    result = pd.DataFrame(rows)
    result["abs_r"] = result["pearson_r"].abs()
    return result.sort_values(["outcome", "abs_r"], ascending=[True, False])


def build_web_payload(frame: pd.DataFrame, correlations: pd.DataFrame) -> dict:
    province_columns = [
        "key", "province", "region", "electorate", *OUTCOMES, *DEMOGRAPHICS
    ]
    correlations = correlations.drop(columns=["abs_r"], errors="ignore")
    return {
        "meta": {
            "source": "T\u00dc\u0130K 2023 + YSK 2023",
            "n": len(frame),
            "outcomes": OUTCOMES,
            "demographics": DEMOGRAPHICS,
            "controls": "region + log(electorate)",
        },
        "correlations": json.loads(
            correlations.to_json(orient="records", force_ascii=False)
        ),
        "provinces": json.loads(
            frame[province_columns].to_json(orient="records", force_ascii=False)
        ),
    }


def write_report(correlations: pd.DataFrame) -> None:
    lines = [
        "# 2023 province-level demographic correlations",
        "",
        "81 provinces. Pearson and Spearman correlations use unweighted province",
        "rows; `weighted_r` weights by electorate. `partial_r` controls for region",
        "fixed effects and log(electorate). `p_approx` is a two-sided normal",
        "approximation, not a multiple-testing correction. Correlations are",
        "descriptive and do not identify causal effects.",
        "",
        "TÜİK age bands, employment, and settlement are national-only in the",
        "current scrape; province-level predictors are sex, median age,",
        "household size, and education.",
        "",
    ]
    for outcome in OUTCOMES:
        subset = correlations[correlations["outcome"] == outcome].head(6)
        if subset.empty:
            continue
        lines.append(f"## {outcome}")
        lines.append("")
        lines.append("| demographic | Pearson r | Spearman rho | weighted r | partial r | p |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for _, row in subset.iterrows():
            lines.append(
                f"| {row['demographic']} | {row['pearson_r']:.3f} | "
                f"{row['spearman_rho']:.3f} | {row['weighted_r']:.3f} | "
                f"{row['partial_r']:.3f} | {row['p_approx']:.4f} |"
            )
        lines.append("")
    (OUT / "demographic_correlations.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = build_dataset()
    correlations = compute_correlations(frame)

    frame.to_csv(OUT / "province_demographics.csv", index=False)
    correlations.to_csv(OUT / "demographic_correlations.csv", index=False)
    write_report(correlations)
    WEB_OUT.write_text(
        json.dumps(build_web_payload(frame, correlations), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"wrote {OUT.relative_to(ROOT)} ({len(frame)} provinces, "
          f"{len(correlations)} correlations)")
    top = correlations.sort_values("abs_r", ascending=False).head(12)
    print(top[["outcome", "demographic", "pearson_r", "spearman_rho"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
