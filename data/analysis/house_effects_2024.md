# 2024 local-election house-effect backtest

Pollster effects are trained on 2015–2023 polls only. Each city and
district is aggregated separately and compared with the 31 March 2024
result. The sample covers every 2024 local poll with a matching actual:
129 scopes (51 city, 78 district).

| model | all MAE | winner accuracy | city MAE | district MAE |
|---|---:|---:|---:|---:|
| raw average | 0.02921 | 67.4% | 0.02445 | 0.03232 |
| two-level | 0.02872 | 71.3% | 0.02438 | 0.03156 |
| one-level | 0.02879 | 72.9% | 0.02454 | 0.03157 |
| hierarchical one-level | 0.02888 | 72.9% | 0.02470 | 0.03161 |

One-level effects give the best winner accuracy and are effectively tied
with two-level on district MAE; the production local mode stays one-level.
The 2024 result is used only for this diagnostic; it is not part of the
production house-effect training data.
