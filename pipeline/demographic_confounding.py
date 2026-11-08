"""Diagnostics for confounding in the demographic swing model.

Outputs:
  data/analysis/demographic_confounding.md
  data/analysis/demographic_confounding.csv

    python pipeline/demographic_confounding.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.demographic_correlation import (
    DEMOGRAPHICS,
    SWING_OUTCOMES,
    load_regions,
)

ROOT = Path(__file__).resolve().parent.parent
FRAME = ROOT / "data" / "analysis" / "province_demographics.csv"
OUT = ROOT / "data" / "analysis"


def design(frame: pd.DataFrame, region_columns: list[str]) -> np.ndarray:
    demographics = frame[DEMOGRAPHICS].to_numpy(dtype=float)
    demographics = (demographics - demographics.mean(axis=0)) / demographics.std(axis=0)
    regions = (
        pd.get_dummies(frame["region"], dtype=float)
        .reindex(columns=region_columns, fill_value=0)
        .to_numpy()
    )
    return np.column_stack([
        np.ones(len(frame)),
        demographics,
        regions,
        np.log(frame["electorate"].to_numpy(dtype=float)),
    ])


def vif_table(frame: pd.DataFrame) -> pd.DataFrame:
    matrix = frame[DEMOGRAPHICS].to_numpy(dtype=float)
    rows = []
    for index, name in enumerate(DEMOGRAPHICS):
        y = matrix[:, index]
        others = np.delete(matrix, index, axis=1)
        design_matrix = np.column_stack([np.ones(len(frame)), others])
        beta, _, _, _ = np.linalg.lstsq(design_matrix, y, rcond=None)
        residual = y - design_matrix @ beta
        total = ((y - y.mean()) ** 2).sum()
        r2 = 1 - (residual ** 2).sum() / total if total > 0 else 0.0
        vif = float("inf") if 1 - r2 <= 1e-12 else 1 / (1 - r2)
        rows.append({"demographic": name, "r2": r2, "vif": vif})
    return pd.DataFrame(rows).sort_values("vif", ascending=False)


def fit_table(frame: pd.DataFrame, region_columns: list[str]) -> pd.DataFrame:
    x = design(frame, region_columns)
    rank = np.linalg.matrix_rank(x)
    rows = []
    for outcome in SWING_OUTCOMES:
        y = frame[outcome].to_numpy(dtype=float)
        beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ beta
        total = ((y - y.mean()) ** 2).sum()
        r2 = 1 - (residual ** 2).sum() / total if total > 0 else 0.0
        adjusted = 1 - (1 - r2) * (len(y) - 1) / max(1, len(y) - rank)
        rows.append({
            "outcome": outcome,
            "r2": r2,
            "adjusted_r2": adjusted,
            "rank": rank,
        })
    return pd.DataFrame(rows)


def region_stability(frame: pd.DataFrame, region_columns: list[str]) -> pd.DataFrame:
    full = design(frame, region_columns)
    full_beta, _, _, _ = np.linalg.lstsq(
        full, frame["incumbent_swing"].to_numpy(dtype=float), rcond=None
    )
    signs = np.sign(full_beta[1:1 + len(DEMOGRAPHICS)])
    counts = {name: 0 for name in DEMOGRAPHICS}
    totals = {name: 0 for name in DEMOGRAPHICS}
    regions = sorted(frame["region"].unique())
    for region in regions:
        train = frame[frame["region"] != region]
        if train["region"].nunique() < 2:
            continue
        train_regions = sorted(train["region"].unique())[1:]
        x_train = design(train, train_regions)
        beta, _, _, _ = np.linalg.lstsq(
            x_train, train["incumbent_swing"].to_numpy(dtype=float), rcond=None
        )
        for index, name in enumerate(DEMOGRAPHICS):
            totals[name] += 1
            counts[name] += int(np.sign(beta[1 + index]) == signs[index])
    return pd.DataFrame([
        {
            "demographic": name,
            "stable_folds": counts[name],
            "folds": totals[name],
            "stability": counts[name] / totals[name] if totals[name] else 0.0,
        }
        for name in DEMOGRAPHICS
    ]).sort_values("stability")


def build_diagnostics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    region_columns = sorted(frame["region"].unique())[1:]
    correlations = frame[DEMOGRAPHICS].corr()
    pairs = []
    for left in range(len(DEMOGRAPHICS)):
        for right in range(left + 1, len(DEMOGRAPHICS)):
            pairs.append({
                "left": DEMOGRAPHICS[left],
                "right": DEMOGRAPHICS[right],
                "pearson_r": float(correlations.iloc[left, right]),
            })
    pairwise = pd.DataFrame(pairs).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)
    return vif_table(frame), pairwise, fit_table(frame, region_columns), region_stability(frame, region_columns)


def main() -> None:
    frame = pd.read_csv(FRAME)
    regions = load_regions()
    if set(frame["region"]) != set(regions.values()):
        raise SystemExit("region mapping does not match the frame")
    vif, pairwise, fits, stability = build_diagnostics(frame)
    vif.to_csv(OUT / "demographic_confounding.csv", index=False)

    lines = [
        "# Demographic confounding diagnostics",
        "",
        "81 provinces. VIF is the variance inflation factor within the nine",
        "demographic variables (1 = no collinearity). The swing model also",
        "controls for region fixed effects and log(electorate). High VIF or a",
        "low leave-one-region-out sign stability means the coefficient should",
        "not be read as a stable causal effect.",
        "",
        "## Variance inflation",
        "",
        "Household shares and education shares each sum to one, so their",
        "individual coefficients are not identified by OLS. The fitted values",
        "are still identified, but individual coefficients should not be read.",
        "",
        "| demographic | R² | VIF |",
        "|---|---:|---:|",
    ]
    for _, row in vif.iterrows():
        vif_text = "∞" if not np.isfinite(row["vif"]) else f"{row['vif']:.2f}"
        lines.append(f"| {row['demographic']} | {row['r2']:.3f} | {vif_text} |")
    lines += [
        "",
        "## Strongest pairwise correlations",
        "",
        "| pair | Pearson r |",
        "|---|---:|",
    ]
    for _, row in pairwise.head(10).iterrows():
        lines.append(f"| {row['left']} / {row['right']} | {row['pearson_r']:.3f} |")
    lines += [
        "",
        "## Swing-model fit",
        "",
        "| outcome | R² | adjusted R² |",
        "|---|---:|---:|",
    ]
    for _, row in fits.iterrows():
        lines.append(
            f"| {row['outcome']} | {row['r2']:.3f} | {row['adjusted_r2']:.3f} |"
        )
    lines += [
        "",
        "## Leave-one-region-out sign stability",
        "",
        "Share of region folds where the incumbent-swing coefficient keeps the",
        "full-sample sign.",
        "",
        "| demographic | stability | folds |",
        "|---|---:|---:|",
    ]
    for _, row in stability.iterrows():
        lines.append(
            f"| {row['demographic']} | {row['stability']:.1%} | {row['folds']} |"
        )
    lines.append("")
    (OUT / "demographic_confounding.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
