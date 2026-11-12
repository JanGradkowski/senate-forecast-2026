# 2026 forecast scorecard

The forecast of 01 Nov 2026 scored against the results. Results are unofficial: Wikipedia revision 1385260610 (last edited 12 November 2026). Margins are two-party, non-Republican minus Republican, in points.

- **Alaska:** Ranked-choice tabulation pending; a Democratic win (Peltola) is assumed. It counts in the win/loss scores and the seat total, but has no margin.

## Summary

- **Control:** the forecast gave Democrats + independents an 80% chance of control. They won it, 56–44.
- **Seats:** 56 Democratic + independent seats, against a forecast median of 52 and an 80% range of 49–55. The forecast gave 56 or more seats a 6.3% chance. The result sits at the 96% point of the seat distribution. Without the Alaska assumption the count is 55, the top of the 80% range.
- **Winners:** the favourite won 31 of 35 races. The forecast expected 2.8 upsets; 4 happened.
- **Margins:** Democrats and independents beat their projected margin in 25 of 34 races. The average error was +3.6 points toward them; the typical miss was 6.1 points (RMSE 7.7). Democrats beat their projection in 24 of 30 races (on average by +4.4). Of the 4 independents, 3 fell short of their projection (Montana -7.0, Nebraska -5.4, South Dakota -4.1, Idaho +7.8).
- **80% ranges:** 31 of 34 results (91%) fell inside their 80% range.

## Scores

| | Brier (lower is better) | Log loss (lower is better) |
|---|---|---|
| Model | **0.084** | **0.318** |
| Forecaster ratings consensus (not used by the model) | 0.078 | 0.257 |
| Coin flip | 0.250 | 0.693 |

Probabilities are clipped to 0.5–99.5% for log loss, as in the backtest.

One race dominates: the model gave Mississippi's winner 0.5% (the ratings consensus 6.1%), and that race alone is 48% of the model's log loss. Without it, the model scores 0.172 against the consensus's 0.182.

## Against the 14 backtest years

The same scores for each year of the leave-one-year-out validation, with 2026 ranked among the 15 years.

| | 2026 | Backtest mean | Backtest range | 2026 rank (of 15) |
|---|---|---|---|---|
| Winners called | **88.6%** | 93.9% | 87.9% to 100.0% | 12 |
| Brier | **0.084** | 0.041 | 0.009 to 0.073 | 15 |
| Log loss | **0.318** | 0.129 | 0.040 to 0.233 | 15 |
| 80% range coverage | **91.2%** | 80.3% | 64.7% to 97.1% | 10 |
| Mean margin error (+ = toward D/I) | **+3.6** | -1.2 | -5.7 to +4.3 | 10 |

Rank 1 is the best year: the smallest miss for the mean error, and the closest to 80% for coverage.

## Polls, fundamentals and the blend

In the 24 polled races with a result, root-mean-square error of the margin:

| Estimate | RMSE (points) |
|---|---|
| Poll average | 6.2 |
| Fundamentals only | 10.5 |
| Blend (the forecast) | **7.3** |

The poll averages themselves missed by +2.4 points on average (+ = Democrats and independents did better than their polls). In 2026 the polls alone beat the blend: the fundamentals leaned further toward Republicans than the result did, and the blend inherited part of that lean. One year is not enough to change the weighting, which the backtest chose over 14 elections.

## Race by race

Sorted by the forecast margin. Error is result minus forecast (+ = toward the Democrat or independent). ✓ means the favourite won.

| State | Forecast | 80% range | Win prob. (D/I) | Result | Error | In range | Favourite won |
|---|---|---|---|---|---|---|---|
| West Virginia | R +37.7 | R +56.5 to R +18.8 | 0% | R +21.2 (Capito) | +16.5 | yes | ✓ |
| Idaho | R +33.3 | R +52.2 to R +14.3 | 0% | R +25.5 (Risch) | +7.8 | yes | ✓ |
| Wyoming | R +27.9 | R +46.8 to R +9.0 | 0% | R +30.5 (Hageman) | -2.6 | yes | ✓ |
| Tennessee | R +27.7 | R +46.4 to R +8.8 | 0% | R +12.4 (Hagerty) | +15.2 | yes | ✓ |
| Mississippi | R +22.4 | R +41.3 to R +3.8 | 0% | D +0.5 (Colom) | +22.9 | **no** | **✗ upset** |
| Oklahoma | R +19.1 | R +38.0 to R +0.3 | 1% | R +18.6 (Hern) | +0.5 | yes | ✓ |
| Arkansas | R +17.0 | R +28.9 to R +5.3 | 0% | R +12.3 (Cotton) | +4.8 | yes | ✓ |
| South Dakota | R +16.9 | R +26.8 to R +7.1 | 0% | R +21.0 (Rounds) | -4.1 | yes | ✓ |
| Kentucky | R +15.5 | R +34.3 to D +3.2 | 2% | R +12.3 (Barr) | +3.1 | yes | ✓ |
| Alabama | R +15.3 | R +34.0 to D +3.7 | 2% | R +9.4 (Moore) | +5.8 | yes | ✓ |
| Louisiana | R +9.2 | R +28.0 to D +9.5 | 9% | R +1.8 (Letlow) | +7.4 | yes | ✓ |
| Florida | R +5.8 | R +12.3 to D +0.6 | 4% | R +2.9 (Moody) | +2.9 | yes | ✓ |
| Montana | R +5.4 | R +15.5 to I +4.6 | 10% | R +12.4 (Alme) | -7.0 | yes | ✓ |
| South Carolina | R +3.0 | R +12.7 to D +6.8 | 23% | D +4.6 (Andrews) | +7.6 | yes | **✗ upset** |
| Kansas | R +2.6 | R +12.3 to D +7.3 | 26% | D +5.2 (Hamilton) | +7.8 | yes | **✗ upset** |
| Nebraska | R +1.3 | R +14.1 to I +11.5 | 39% | R +6.6 (Ricketts) | -5.4 | yes | ✓ |
| Alaska | R +0.2 | R +12.1 to D +11.5 | 48% | Peltola wins (assumed) | – | – | **✗ upset** |
| Iowa | D +0.1 | R +6.4 to D +6.5 | 51% | D +4.2 (Turek) | +4.2 | yes | ✓ |
| Maine | D +1.9 | R +4.9 to D +8.6 | 73% | D +6.3 (Jackson) | +4.4 | yes | ✓ |
| Texas | D +3.0 | R +2.4 to D +8.5 | 85% | D +12.3 (Talarico) | +9.3 | **no** | ✓ |
| Ohio | D +3.7 | R +2.8 to D +10.1 | 88% | D +5.1 (Brown) | +1.4 | yes | ✓ |
| Michigan | D +4.7 | R +2.1 to D +11.5 | 92% | D +7.2 (El-Sayed) | +2.5 | yes | ✓ |
| New Hampshire | D +8.0 | D +0.6 to D +15.4 | 98% | D +14.0 (Pappas) | +6.0 | yes | ✓ |
| Minnesota | D +9.7 | D +1.0 to D +18.3 | 99% | D +10.4 (Flanagan) | +0.8 | yes | ✓ |
| Georgia | D +11.0 | D +1.4 to D +20.5 | 99% | D +18.0 (Ossoff) | +7.1 | yes | ✓ |
| North Carolina | D +12.6 | D +5.4 to D +19.7 | 100% | D +20.1 (Cooper) | +7.5 | **no** | ✓ |
| Illinois | D +16.8 | D +6.1 to D +27.4 | 100% | D +24.7 (Stratton) | +7.9 | yes | ✓ |
| New Mexico | D +21.9 | D +10.6 to D +33.3 | 100% | D +26.5 (Lujan) | +4.6 | yes | ✓ |
| Virginia | D +25.4 | D +6.7 to D +44.2 | 100% | D +22.7 (Warner) | -2.7 | yes | ✓ |
| New Jersey | D +26.6 | D +7.9 to D +45.3 | 100% | D +28.0 (Booker) | +1.4 | yes | ✓ |
| Colorado | D +29.1 | D +10.5 to D +47.9 | 100% | D +26.5 (Hickenlooper) | -2.7 | yes | ✓ |
| Oregon | D +31.7 | D +13.0 to D +50.6 | 100% | D +20.1 (Merkley) | -11.6 | yes | ✓ |
| Delaware | D +32.2 | D +13.4 to D +51.0 | 100% | D +27.2 (Coons) | -5.1 | yes | ✓ |
| Rhode Island | D +32.7 | D +23.5 to D +41.8 | 100% | D +39.0 (Reed) | +6.3 | yes | ✓ |
| Massachusetts | D +33.8 | D +25.6 to D +41.9 | 100% | D +32.7 (Markey) | -1.1 | yes | ✓ |

Results source: Wikipedia revision 1385260610 (last edited 12 November 2026). Regenerate with `python -W ignore -m scripts.results_2026`.
