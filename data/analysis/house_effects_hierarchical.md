# Hierarchical house effects — experiment

One-level party effects are partially pooled toward the cross-pollster
party mean, then shrunk toward that group mean by effective sample size.

| test | raw | current one-level | hierarchical one-level |
|---|---:|---:|---:|
| 2018 parliament | 0.02077 | 0.02058 | 0.02058 |
| 2018 president | 0.03300 | 0.03300 | 0.03300 |
| 2023 parliament | 0.01172 | 0.01177 | 0.01202 |
| 2023 president | 0.02407 | 0.02380 | 0.02336 |

## Conclusion

Hierarchical pooling is used for the presidential races: it improves
2023 first-round MAE from 2.41 to 2.34 points and is neutral in 2018.
Parliament stays on the current one-level model because hierarchical
pooling worsens 2023 to 1.20 points. The production payload carries both
effect sets and selects the mode per race.
