# 2023 province-level demographic correlations

81 provinces. Pearson and Spearman correlations use unweighted province
rows; `weighted_r` weights by electorate. `partial_r` controls for region
fixed effects and log(electorate). `p_approx` is a two-sided normal
approximation, not a multiple-testing correction. Correlations are
descriptive and do not identify causal effects.

TÜİK age bands, employment, and settlement are national-only in the
current scrape; province-level predictors are sex, median age,
household size, and education.

## erdogan

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| female_share | 0.537 | 0.362 | 0.216 | 0.481 | 0.0000 |
| median_age | 0.230 | 0.088 | 0.028 | -0.073 | 0.0386 |
| hh_1_2 | 0.217 | 0.088 | 0.025 | -0.078 | 0.0515 |
| hh_5plus | -0.210 | 0.087 | 0.037 | 0.001 | 0.0599 |
| hh_3_4 | 0.178 | -0.111 | -0.082 | 0.074 | 0.1119 |
| edu_primary | 0.097 | 0.096 | 0.277 | 0.128 | 0.3910 |

## kilicdaroglu

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| female_share | -0.562 | -0.397 | -0.256 | -0.482 | 0.0000 |
| median_age | -0.288 | -0.128 | -0.104 | 0.063 | 0.0090 |
| hh_5plus | 0.280 | -0.025 | 0.051 | 0.029 | 0.0110 |
| hh_1_2 | -0.276 | -0.137 | -0.098 | 0.065 | 0.0123 |
| hh_3_4 | -0.251 | 0.046 | -0.004 | -0.114 | 0.0237 |
| edu_secondary | 0.122 | 0.087 | -0.096 | -0.157 | 0.2801 |

## ogan

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_3_4 | 0.603 | 0.470 | 0.621 | 0.336 | 0.0000 |
| hh_5plus | -0.590 | -0.422 | -0.632 | -0.225 | 0.0000 |
| hh_1_2 | 0.502 | 0.358 | 0.528 | 0.072 | 0.0000 |
| median_age | 0.498 | 0.312 | 0.555 | 0.046 | 0.0000 |
| edu_university | 0.395 | 0.358 | 0.296 | 0.197 | 0.0002 |
| female_share | 0.384 | 0.446 | 0.395 | 0.105 | 0.0004 |

## ince

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_1_2 | 0.557 | 0.590 | 0.599 | 0.298 | 0.0000 |
| median_age | 0.531 | 0.583 | 0.516 | 0.262 | 0.0000 |
| hh_5plus | -0.526 | -0.613 | -0.388 | -0.278 | 0.0000 |
| hh_3_4 | 0.434 | 0.464 | 0.153 | 0.212 | 0.0000 |
| female_share | 0.354 | 0.309 | 0.018 | 0.236 | 0.0011 |
| edu_secondary | -0.184 | -0.220 | -0.017 | 0.124 | 0.0998 |

## turnout

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_3_4 | 0.797 | 0.829 | 0.856 | 0.634 | 0.0000 |
| hh_5plus | -0.786 | -0.731 | -0.820 | -0.591 | 0.0000 |
| median_age | 0.718 | 0.584 | 0.715 | 0.471 | 0.0000 |
| hh_1_2 | 0.677 | 0.547 | 0.624 | 0.443 | 0.0000 |
| edu_university | 0.631 | 0.629 | 0.666 | 0.523 | 0.0000 |
| female_share | 0.579 | 0.503 | 0.600 | 0.187 | 0.0000 |

## incumbent_swing

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_5plus | 0.471 | 0.402 | 0.595 | 0.159 | 0.0000 |
| hh_3_4 | -0.463 | -0.412 | -0.593 | -0.232 | 0.0000 |
| hh_1_2 | -0.420 | -0.365 | -0.487 | -0.056 | 0.0001 |
| median_age | -0.402 | -0.322 | -0.494 | -0.018 | 0.0002 |
| edu_university | -0.291 | -0.279 | -0.357 | -0.138 | 0.0082 |
| edu_secondary | 0.278 | 0.251 | 0.423 | 0.002 | 0.0117 |

## AKP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| female_share | 0.433 | 0.323 | 0.169 | 0.353 | 0.0000 |
| median_age | 0.174 | 0.091 | -0.028 | -0.086 | 0.1203 |
| hh_1_2 | 0.140 | 0.063 | -0.051 | -0.114 | 0.2135 |
| hh_5plus | -0.137 | 0.095 | 0.084 | 0.023 | 0.2248 |
| hh_3_4 | 0.117 | -0.122 | -0.098 | 0.069 | 0.2985 |
| edu_primary | 0.106 | 0.144 | 0.227 | 0.110 | 0.3484 |

## CHP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_3_4 | 0.727 | 0.740 | 0.762 | 0.668 | 0.0000 |
| hh_5plus | -0.714 | -0.756 | -0.765 | -0.715 | 0.0000 |
| median_age | 0.641 | 0.623 | 0.660 | 0.661 | 0.0000 |
| edu_university | 0.632 | 0.650 | 0.654 | 0.509 | 0.0000 |
| hh_1_2 | 0.611 | 0.601 | 0.625 | 0.639 | 0.0000 |
| edu_secondary | -0.517 | -0.525 | -0.621 | -0.397 | 0.0000 |

## MHP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| female_share | 0.454 | 0.412 | 0.205 | 0.432 | 0.0000 |
| hh_1_2 | 0.336 | 0.251 | 0.264 | 0.002 | 0.0020 |
| hh_5plus | -0.292 | -0.098 | -0.129 | -0.040 | 0.0079 |
| median_age | 0.290 | 0.190 | 0.210 | -0.048 | 0.0085 |
| hh_3_4 | 0.215 | 0.029 | -0.003 | 0.070 | 0.0533 |
| edu_secondary | -0.122 | -0.127 | 0.054 | 0.150 | 0.2806 |

## IYI

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_5plus | -0.503 | -0.471 | -0.659 | 0.000 | 0.0000 |
| hh_1_2 | 0.485 | 0.459 | 0.638 | 0.096 | 0.0000 |
| hh_3_4 | 0.460 | 0.432 | 0.574 | -0.094 | 0.0000 |
| median_age | 0.440 | 0.399 | 0.605 | -0.024 | 0.0000 |
| female_share | 0.364 | 0.285 | 0.383 | 0.084 | 0.0008 |
| edu_secondary | -0.356 | -0.393 | -0.490 | -0.053 | 0.0010 |

## HDP_DEM

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_5plus | 0.818 | 0.491 | 0.785 | 0.579 | 0.0000 |
| hh_3_4 | -0.789 | -0.283 | -0.737 | -0.595 | 0.0000 |
| median_age | -0.762 | -0.671 | -0.730 | -0.436 | 0.0000 |
| hh_1_2 | -0.746 | -0.666 | -0.698 | -0.460 | 0.0000 |
| female_share | -0.719 | -0.578 | -0.586 | -0.538 | 0.0000 |
| edu_secondary | 0.532 | 0.437 | 0.525 | 0.172 | 0.0000 |

## YRP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| female_share | 0.207 | 0.207 | 0.070 | 0.292 | 0.0631 |
| edu_high_school | 0.097 | 0.047 | 0.020 | 0.124 | 0.3919 |
| hh_1_2 | -0.062 | -0.145 | -0.212 | -0.074 | 0.5852 |
| hh_3_4 | 0.057 | -0.110 | -0.042 | 0.122 | 0.6144 |
| edu_university | -0.047 | -0.073 | -0.075 | -0.092 | 0.6803 |
| edu_secondary | -0.025 | 0.035 | 0.097 | 0.030 | 0.8278 |

## TIP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| edu_university | 0.380 | 0.621 | 0.490 | 0.205 | 0.0004 |
| hh_3_4 | 0.293 | 0.635 | 0.339 | -0.002 | 0.0077 |
| edu_primary | -0.241 | -0.402 | -0.462 | -0.163 | 0.0297 |
| hh_5plus | -0.234 | -0.559 | -0.232 | -0.046 | 0.0354 |
| edu_secondary | -0.223 | -0.531 | -0.313 | -0.125 | 0.0452 |
| median_age | 0.172 | 0.484 | 0.129 | 0.046 | 0.1255 |

## ZP

| demographic | Pearson r | Spearman rho | weighted r | partial r | p |
|---|---:|---:|---:|---:|---:|
| hh_3_4 | 0.710 | 0.690 | 0.766 | 0.432 | 0.0000 |
| hh_5plus | -0.595 | -0.475 | -0.590 | -0.338 | 0.0000 |
| edu_university | 0.588 | 0.592 | 0.687 | 0.336 | 0.0000 |
| female_share | 0.572 | 0.470 | 0.514 | 0.178 | 0.0000 |
| median_age | 0.463 | 0.309 | 0.377 | 0.150 | 0.0000 |
| edu_primary | -0.439 | -0.421 | -0.693 | -0.366 | 0.0000 |
