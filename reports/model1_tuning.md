# Model 1 tuning

Grid searches scored leave-one-year-out on 1998-2024 (see scripts/tune_model1.py for the rules).
`logloss` is the race-weighted mean over held-out years; `joint` the mean per-year -log P(observed count of non-R wins among races within 15 points); `upsets_exp/obs` count underdog wins (forecast below 35%).

## Stage 1: poll averaging

Current: `tau_days=14 house_ridge=20`. Nested (tuned procedure, scored on years it did not tune on): log loss 0.1442 vs current 0.1448 (difference -0.0005 ± 0.0022).
One-SE pick on all years: `tau_days=14 house_ridge=5`. **Adopted.**

Nested picks by held-out year: 1998: `tau_days=7 house_ridge=5`, 2000: `tau_days=14 house_ridge=5`, 2002: `tau_days=14 house_ridge=5`, 2004: `tau_days=14 house_ridge=5`, 2006: `tau_days=14 house_ridge=5`, 2008: `tau_days=14 house_ridge=5`, 2010: `tau_days=14 house_ridge=5`, 2012: `tau_days=14 house_ridge=5`, 2014: `tau_days=14 house_ridge=5`, 2016: `tau_days=14 house_ridge=5`, 2018: `tau_days=14 house_ridge=5`, 2020: `tau_days=14 house_ridge=5`, 2022: `tau_days=14 house_ridge=5`, 2024: `tau_days=14 house_ridge=5`

| candidate                  |   logloss |   vs_best |     se |   joint |   joint_vs_current |   joint_se |   upsets_exp |   upsets_obs |   changed |
|:---------------------------|----------:|----------:|-------:|--------:|-------------------:|-----------:|-------------:|-------------:|----------:|
| tau_days=14 house_ridge=5  |    0.1425 |    0      | 0      |  2.0003 |            -0.0239 |     0.0171 |      22.924  |           11 |         1 |
| tau_days=28 house_ridge=5  |    0.1438 |    0.0014 | 0.0015 |  2.0352 |             0.0116 |     0.03   |      21.9627 |           12 |         2 |
| tau_days=7 house_ridge=5   |    0.1442 |    0.0017 | 0.0028 |  1.9942 |            -0.0304 |     0.0296 |      25.4724 |           14 |         2 |
| tau_days=14 house_ridge=20 |    0.1448 |    0.0023 | 0.001  |  2.0247 |             0      |     0      |      23.5201 |           13 |         0 |
| tau_days=28 house_ridge=20 |    0.1457 |    0.0032 | 0.0018 |  2.0564 |             0.0321 |     0.0209 |      23.0609 |           12 |         1 |
| tau_days=14 house_ridge=80 |    0.1464 |    0.0039 | 0.0016 |  2.0477 |             0.0228 |     0.0101 |      23.6625 |           13 |         1 |
| tau_days=7 house_ridge=20  |    0.1471 |    0.0046 | 0.0029 |  2.0267 |             0.0018 |     0.0269 |      24.832  |           13 |         1 |
| tau_days=28 house_ridge=80 |    0.1473 |    0.0048 | 0.0022 |  2.0777 |             0.0531 |     0.0211 |      23.6464 |           14 |         2 |
| tau_days=7 house_ridge=80  |    0.1484 |    0.0059 | 0.003  |  2.0442 |             0.0191 |     0.0272 |      25.2398 |           14 |         2 |

## Stage 2: error model

Current: `t_df=5 sigma_nat_floor=2.5 calibrate=coverage`. Nested (tuned procedure, scored on years it did not tune on): log loss 0.1321 vs current 0.1425 (difference -0.0104 ± 0.0045).
One-SE pick on all years: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`. **Adopted.**

Nested picks by held-out year: 1998: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2000: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`, 2002: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`, 2004: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2006: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2008: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2010: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2012: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2014: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2016: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`, 2018: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`, 2020: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`, 2022: `t_df=10 sigma_nat_floor=3.5 calibrate=logloss`, 2024: `t_df=5 sigma_nat_floor=2.5 calibrate=logloss`

| candidate                                      |   logloss |   vs_best |     se |   joint |   joint_vs_current |   joint_se |   upsets_exp |   upsets_obs |   changed |
|:-----------------------------------------------|----------:|----------:|-------:|--------:|-------------------:|-----------:|-------------:|-------------:|----------:|
| t_df=10 sigma_nat_floor=3.5 calibrate=logloss  |    0.1281 |    0      | 0      |  1.9818 |            -0.015  |     0.099  |      15.1314 |           13 |         3 |
| t_df=5 sigma_nat_floor=2.5 calibrate=logloss   |    0.1281 |    0      | 0.0024 |  1.919  |            -0.08   |     0.068  |      14.9287 |           17 |         1 |
| t_df=30 sigma_nat_floor=3.0 calibrate=logloss  |    0.1283 |    0.0002 | 0.001  |  1.9413 |            -0.0559 |     0.0856 |      14.0395 |           14 |         3 |
| t_df=10 sigma_nat_floor=3.0 calibrate=logloss  |    0.1283 |    0.0002 | 0.0011 |  1.9501 |            -0.0474 |     0.0861 |      14.2096 |           15 |         3 |
| t_df=30 sigma_nat_floor=3.5 calibrate=logloss  |    0.1284 |    0.0003 | 0.0005 |  1.9938 |            -0.0029 |     0.0988 |      14.8494 |           13 |         3 |
| t_df=5 sigma_nat_floor=3.5 calibrate=logloss   |    0.1285 |    0.0004 | 0.0007 |  1.977  |            -0.0202 |     0.0938 |      15.5757 |           15 |         2 |
| t_df=4 sigma_nat_floor=3.5 calibrate=logloss   |    0.1286 |    0.0005 | 0.001  |  1.9529 |            -0.0447 |     0.0897 |      15.4522 |           16 |         3 |
| t_df=30 sigma_nat_floor=2.0 calibrate=logloss  |    0.1286 |    0.0005 | 0.0026 |  1.9103 |            -0.0885 |     0.0633 |      13.0453 |           15 |         3 |
| t_df=5 sigma_nat_floor=3.0 calibrate=logloss   |    0.1287 |    0.0006 | 0.0017 |  1.9402 |            -0.0577 |     0.0796 |      14.3879 |           16 |         2 |
| t_df=10 sigma_nat_floor=2.5 calibrate=logloss  |    0.1288 |    0.0007 | 0.0021 |  1.9185 |            -0.0796 |     0.0716 |      13.5921 |           16 |         2 |
| t_df=10 sigma_nat_floor=2.0 calibrate=logloss  |    0.1292 |    0.0011 | 0.0025 |  1.9307 |            -0.0679 |     0.0655 |      13.0335 |           16 |         3 |
| t_df=4 sigma_nat_floor=3.0 calibrate=logloss   |    0.1292 |    0.0011 | 0.0018 |  1.9376 |            -0.0602 |     0.0819 |      15.805  |           16 |         3 |
| t_df=4 sigma_nat_floor=2.5 calibrate=logloss   |    0.1292 |    0.0011 | 0.0026 |  1.9301 |            -0.0691 |     0.0715 |      15.4818 |           18 |         2 |
| t_df=30 sigma_nat_floor=2.5 calibrate=logloss  |    0.1294 |    0.0013 | 0.0023 |  1.9051 |            -0.0931 |     0.0706 |      13.3835 |           15 |         2 |
| t_df=5 sigma_nat_floor=2.0 calibrate=logloss   |    0.1295 |    0.0014 | 0.0029 |  1.9348 |            -0.0641 |     0.0677 |      14.9644 |           18 |         2 |
| t_df=4 sigma_nat_floor=2.0 calibrate=logloss   |    0.1299 |    0.0018 | 0.003  |  1.9439 |            -0.0556 |     0.0728 |      15.1753 |           18 |         3 |
| t_df=30 sigma_nat_floor=2.5 calibrate=coverage |    0.1405 |    0.0124 | 0.0043 |  1.9871 |            -0.0126 |     0.0178 |      21.6613 |           11 |         1 |
| t_df=30 sigma_nat_floor=3.5 calibrate=coverage |    0.1407 |    0.0126 | 0.0042 |  2.0245 |             0.026  |     0.0507 |      21.924  |           11 |         2 |
| t_df=30 sigma_nat_floor=3.0 calibrate=coverage |    0.1407 |    0.0126 | 0.0043 |  2      |             0.0009 |     0.0338 |      22.0622 |           11 |         2 |
| t_df=10 sigma_nat_floor=3.5 calibrate=coverage |    0.1408 |    0.0127 | 0.0041 |  2.0161 |             0.0175 |     0.044  |      22.4879 |           11 |         2 |
| t_df=30 sigma_nat_floor=2.0 calibrate=coverage |    0.1408 |    0.0127 | 0.0043 |  2.0016 |             0.0017 |     0.014  |      21.2761 |           11 |         2 |
| t_df=10 sigma_nat_floor=2.5 calibrate=coverage |    0.1409 |    0.0128 | 0.0042 |  1.9964 |            -0.0035 |     0.0131 |      22.2951 |           11 |         1 |
| t_df=10 sigma_nat_floor=3.0 calibrate=coverage |    0.1409 |    0.0128 | 0.0042 |  2.0001 |             0.0009 |     0.0301 |      22.2574 |           11 |         2 |
| t_df=10 sigma_nat_floor=2.0 calibrate=coverage |    0.141  |    0.0129 | 0.0043 |  2.0052 |             0.0051 |     0.0114 |      22.1814 |           11 |         2 |
| t_df=5 sigma_nat_floor=3.5 calibrate=coverage  |    0.1422 |    0.0141 | 0.004  |  2.0111 |             0.0118 |     0.0321 |      23.0464 |           11 |         1 |
| t_df=5 sigma_nat_floor=3.0 calibrate=coverage  |    0.1424 |    0.0143 | 0.0041 |  2.0002 |             0.0006 |     0.0173 |      23.5545 |           12 |         1 |
| t_df=5 sigma_nat_floor=2.5 calibrate=coverage  |    0.1425 |    0.0144 | 0.0042 |  2.0003 |             0      |     0      |      22.924  |           11 |         0 |
| t_df=5 sigma_nat_floor=2.0 calibrate=coverage  |    0.1425 |    0.0144 | 0.0042 |  2.0133 |             0.013  |     0.0073 |      22.7853 |           11 |         1 |
| t_df=4 sigma_nat_floor=3.5 calibrate=coverage  |    0.1428 |    0.0147 | 0.004  |  2.0079 |             0.0084 |     0.0253 |      23.6388 |           12 |         2 |
| t_df=4 sigma_nat_floor=3.0 calibrate=coverage  |    0.1428 |    0.0147 | 0.0041 |  2.0022 |             0.0023 |     0.0102 |      23.7484 |           12 |         2 |
| t_df=4 sigma_nat_floor=2.5 calibrate=coverage  |    0.1428 |    0.0147 | 0.0041 |  2.0018 |             0.0012 |     0.0105 |      23.7866 |           13 |         1 |
| t_df=4 sigma_nat_floor=2.0 calibrate=coverage  |    0.143  |    0.0148 | 0.0042 |  2.0123 |             0.0117 |     0.0149 |      23.6859 |           13 |         2 |

## Stage 3: polling bias

Current: `lam=0.0`. Nested (tuned procedure, scored on years it did not tune on): log loss 0.1212 vs current 0.1186 (difference +0.0025 ± 0.0025).
One-SE pick on all years: `lam=0.0`. **Kept the current config.**

Nested picks by held-out year: 2004: `lam=0.5`, 2006: `lam=0.0`, 2008: `lam=0.0`, 2010: `lam=0.0`, 2012: `lam=0.0`, 2014: `lam=0.0`, 2016: `lam=0.0`, 2018: `lam=0.0`, 2020: `lam=0.0`, 2022: `lam=0.0`, 2024: `lam=0.0`

| candidate   |   logloss |   vs_best |     se |   joint |   joint_vs_current |   joint_se |   upsets_exp |   upsets_obs |   changed |
|:------------|----------:|----------:|-------:|--------:|-------------------:|-----------:|-------------:|-------------:|----------:|
| lam=0.0     |    0.1186 |    0      | 0      |  1.8432 |             0      |     0      |      12.0053 |           12 |         0 |
| lam=0.25    |    0.1198 |    0.0012 | 0.0015 |  1.8577 |             0.0142 |     0.0214 |      10.9231 |           12 |         1 |
| lam=0.5     |    0.1207 |    0.0021 | 0.0031 |  1.8679 |             0.0241 |     0.0429 |      11.2859 |           12 |         1 |
| lam=1.0     |    0.1243 |    0.0056 | 0.0067 |  1.9099 |             0.0645 |     0.0996 |      11.4677 |           11 |         1 |

## Result

```json
{
 "polls": {
  "tau_days": 14,
  "house_ridge": 5
 },
 "errors": {
  "t_df": 5,
  "sigma_nat_floor": 2.5,
  "calibrate": "logloss"
 },
 "bias_lambda": 0.0
}
```