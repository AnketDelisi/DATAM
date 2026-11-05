# Demographic swing: leave-one-province-out check

Target: 2018→2023 incumbent share change. Each province is held out
once; the model is fit on the other 80. `uniform` is the training mean.
`strength` blends the uniform and demographic predictions.

- n: 81
- uniform MAE: 0.0254
- full demographic MAE: 0.0231
- best strength: 0.60 (MAE 0.0218)

| strength | MAE | RMSE | correlation |
|---:|---:|---:|---:|
| 0.00 | 0.0254 | 0.0358 | -1.000 |
| 0.10 | 0.0245 | 0.0348 | 0.289 |
| 0.20 | 0.0239 | 0.0339 | 0.374 |
| 0.30 | 0.0232 | 0.0332 | 0.401 |
| 0.40 | 0.0226 | 0.0326 | 0.414 |
| 0.50 | 0.0221 | 0.0322 | 0.421 |
| 0.60 | 0.0218 | 0.0320 | 0.426 |
| 0.70 | 0.0219 | 0.0320 | 0.430 |
| 0.80 | 0.0221 | 0.0321 | 0.433 |
| 0.90 | 0.0226 | 0.0325 | 0.435 |
| 1.00 | 0.0231 | 0.0330 | 0.436 |

This is a single-election cross-sectional check; it does not
establish that the demographic tilt will improve 2028 forecasts.