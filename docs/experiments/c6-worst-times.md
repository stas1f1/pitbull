# C6 — Prediction-time selection strategies

Status: complete.

## Method

Using the A5 matrix of 62 leaking programs by 20 monthly prediction times, we
compared expected random selection, fixed calendar-stratified selection,
greedy worst-time selection learned on other programs in five folds, and a
global-oracle upper bound. Missing or errored observations count as misses.

## Results

| k | Random | Calendar | Cross-program worst | Global oracle |
|---:|---:|---:|---:|---:|
| 1 | 91.29% | 98.39% | 95.24% | 98.39% |
| 2 | 97.64% | 96.77% | 97.24% | 100.00% |
| 3 | 98.61% | 98.39% | 98.67% | 100.00% |
| 4 | 99.13% | 100.00% | 98.67% | 100.00% |
| 5 | 99.44% | 100.00% | 98.67% | 100.00% |

## Conclusion

A corpus-specific oracle can cover every observed program with two moments,
but the learned worst-time strategy does not consistently beat random or simple
calendar spacing on held-out programs. With leakage already dense across time,
selection policy matters mainly at k=1; adding independent times is the more
robust gain. The oracle is an upper bound, not an deployable estimate.

Reproduction:

```powershell
.\.venv-a2\Scripts\python.exe pilot/c6_worst_times.py
```

