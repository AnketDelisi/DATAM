# Demographic confounding diagnostics

81 provinces. VIF is the variance inflation factor within the nine
demographic variables (1 = no collinearity). The swing model also
controls for region fixed effects and log(electorate). High VIF or a
low leave-one-region-out sign stability means the coefficient should
not be read as a stable causal effect.

## Variance inflation

Household shares and education shares each sum to one, so their
individual coefficients are not identified by OLS. The fitted values
are still identified, but individual coefficients should not be read.

| demographic | R² | VIF |
|---|---:|---:|
| hh_1_2 | 1.000 | ∞ |
| edu_high_school | 1.000 | ∞ |
| hh_3_4 | 1.000 | ∞ |
| hh_5plus | 1.000 | ∞ |
| edu_primary | 1.000 | ∞ |
| edu_university | 1.000 | ∞ |
| edu_secondary | 1.000 | ∞ |
| median_age | 0.947 | 18.84 |
| female_share | 0.479 | 1.92 |

## Strongest pairwise correlations

| pair | Pearson r |
|---|---:|
| median_age / hh_1_2 | 0.964 |
| hh_3_4 / hh_5plus | -0.942 |
| median_age / hh_5plus | -0.941 |
| hh_1_2 / hh_5plus | -0.936 |
| edu_primary / edu_high_school | -0.872 |
| edu_secondary / edu_university | -0.822 |
| median_age / hh_3_4 | 0.807 |
| edu_primary / edu_university | -0.802 |
| hh_5plus / edu_secondary | 0.793 |
| hh_1_2 / edu_secondary | -0.788 |

## Swing-model fit

| outcome | R² | adjusted R² |
|---|---:|---:|
| incumbent_swing | 0.431 | 0.310 |
| AKP_swing | 0.410 | 0.284 |
| CHP_swing | 0.316 | 0.171 |
| MHP_swing | 0.237 | 0.076 |
| IYI_swing | 0.305 | 0.158 |
| HDP_DEM_swing | 0.470 | 0.358 |

## Leave-one-region-out sign stability

Share of region folds where the incumbent-swing coefficient keeps the
full-sample sign.

| demographic | stability | folds |
|---|---:|---:|
| edu_secondary | 71.4% | 7 |
| edu_primary | 71.4% | 7 |
| female_share | 85.7% | 7 |
| median_age | 85.7% | 7 |
| edu_high_school | 85.7% | 7 |
| hh_1_2 | 85.7% | 7 |
| edu_university | 85.7% | 7 |
| hh_3_4 | 100.0% | 7 |
| hh_5plus | 100.0% | 7 |
