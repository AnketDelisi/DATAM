# Two-layer proportional house effects — experiment

Bloc effects are proportional relative odds versus the leave-one-pollster-out consensus.
Party effects are proportional within-bloc composition residuals. Effects are shrunk.

## parliament

Polls: 49

| model | MAE |
|---|---:|
| raw average | 0.01172 |
| two-layer log | 0.01210 |
| two-layer proportional | 0.01215 |

## president_first

Polls: 81

| model | MAE |
|---|---:|
| raw average | 0.02407 |
| two-layer log | 0.02415 |
| two-layer proportional | 0.02357 |

## Conclusion

The proportional variant is not a clear improvement. It is slightly better
than the log model for the presidential race but worse for parliament, and
neither beats the raw average. Because log-ratio and relative-proportional
effects are nearly equivalent for small biases, the limiting factor is the
signal in historical pollster behaviour, not the link function.

Keep this as an experiment; do not promote it to the production export
unless a later validation run shows a consistent gain in both races.
