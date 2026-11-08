"""Leave-one-province-out check for the demographic swing model.

Tests whether demographics improve on a uniform province swing for the
2018→2023 incumbent and party-level changes. This is a diagnostic, not a
2028 forecast.

    python pipeline/demographic_swing_backtest.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.demographic_correlation import DEMOGRAPHICS, SWING_OUTCOMES

ROOT = Path(__file__).resolve().parent.parent
FRAME = ROOT / "data" / "analysis" / "province_demographics.csv"
OUT = ROOT / "data" / "analysis"
TARGET = "incumbent_swing"
LAMBDAS = np.linspace(0, 1, 11)


def design(frame: pd.DataFrame, region_columns: list[str]) -> np.ndarray:
    demographics = frame[DEMOGRAPHICS].to_numpy(dtype=float)
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


def loo_predictions(frame: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    region_columns = sorted(frame["region"].unique())[1:]
    rows = []
    for index in range(len(frame)):
        train = frame.drop(index)
        test = frame.iloc[[index]]
        mean = train[DEMOGRAPHICS].mean()
        std = train[DEMOGRAPHICS].std().replace(0, 1)
        train_z = train.copy()
        test_z = test.copy()
        train_z[DEMOGRAPHICS] = (train[DEMOGRAPHICS] - mean) / std
        test_z[DEMOGRAPHICS] = (test[DEMOGRAPHICS] - mean) / std

        x_train = design(train_z, region_columns)
        x_test = design(test_z, region_columns)
        beta, _, _, _ = np.linalg.lstsq(x_train, train[target].to_numpy(dtype=float), rcond=None)
        demo_prediction = float((x_test @ beta).item())

        rows.append({
            "key": test.iloc[0]["key"],
            "province": test.iloc[0]["province"],
            "actual": float(test.iloc[0][target]),
            "uniform": float(train[target].mean()),
            "demographic": demo_prediction,
        })
    return pd.DataFrame(rows)


def score(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for weight in LAMBDAS:
        blended = predictions["uniform"] + weight * (
            predictions["demographic"] - predictions["uniform"]
        )
        error = blended - predictions["actual"]
        std = float(blended.std())
        correlation = (
            float(np.corrcoef(blended, predictions["actual"])[0, 1])
            if std > 1e-12
            else float("nan")
        )
        rows.append({
            "strength": round(float(weight), 2),
            "mae": float(error.abs().mean()),
            "rmse": float(np.sqrt((error ** 2).mean())),
            "correlation": correlation,
        })
    return pd.DataFrame(rows).sort_values("strength")


def write_report(predictions: pd.DataFrame, scores: pd.DataFrame) -> None:
    lines = [
        "# Demographic swing: leave-one-province-out check",
        "",
        "Each target is the 2018→2023 province-level change. Each province is",
        "held out once; the model is fit on the other 80. `uniform` is the",
        "training mean. `strength` blends the uniform and demographic predictions.",
        "",
    ]
    for target in SWING_OUTCOMES:
        target_predictions = predictions[predictions["target"] == target]
        target_scores = scores[scores["target"] == target]
        best = target_scores.loc[target_scores["mae"].idxmin()]
        uniform = target_scores.loc[target_scores["strength"] == 0].iloc[0]
        full = target_scores.loc[target_scores["strength"] == 1].iloc[0]
        lines += [
            f"## {target}",
            "",
            f"- n: {len(target_predictions)}",
            f"- uniform MAE: {uniform['mae']:.4f}",
            f"- full demographic MAE: {full['mae']:.4f}",
            f"- best strength: {best['strength']:.2f} (MAE {best['mae']:.4f})",
            "",
            "| strength | MAE | RMSE | correlation |",
            "|---:|---:|---:|---:|",
        ]
        for _, row in target_scores.iterrows():
            correlation = (
                "\u2013"
                if not np.isfinite(row["correlation"])
                else f"{row['correlation']:.3f}"
            )
            lines.append(
                f"| {row['strength']:.2f} | {row['mae']:.4f} | "
                f"{row['rmse']:.4f} | {correlation} |"
            )
        lines.append("")
    lines.append("This is a single-election cross-sectional check; it does not")
    lines.append("establish that the demographic tilt will improve 2028 forecasts.")
    (OUT / "demographic_swing_backtest.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    frame = pd.read_csv(FRAME)
    prediction_frames = []
    score_frames = []
    for target in SWING_OUTCOMES:
        predictions = loo_predictions(frame, target)
        predictions["target"] = target
        target_scores = score(predictions)
        target_scores["target"] = target
        prediction_frames.append(predictions)
        score_frames.append(target_scores)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    scores = pd.concat(score_frames, ignore_index=True)
    predictions.to_csv(OUT / "demographic_swing_backtest.csv", index=False)
    scores.to_csv(OUT / "demographic_swing_backtest_scores.csv", index=False)
    write_report(predictions, scores)
    print(f"wrote {OUT.relative_to(ROOT)} (n={len(predictions)})")
    for target in SWING_OUTCOMES:
        target_scores = scores[scores["target"] == target]
        best = target_scores.loc[target_scores["mae"].idxmin()]
        uniform = target_scores.loc[target_scores["strength"] == 0].iloc[0]
        print(
            f"{target:20s} uniform {uniform['mae']:.4f} "
            f"best {best['strength']:.2f} {best['mae']:.4f}"
        )


if __name__ == "__main__":
    main()
