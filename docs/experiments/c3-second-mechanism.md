# C3 — Second leakage mechanism for RQ2b

Status: complete, descriptive small-n result.

## Method and results

We reused the three independent A4 repair repetitions and separated the two
rare mechanisms identified by the A1 annotation. `VAR_MIXUP` was repaired in
3/3 repetitions, always in the first iteration. `PAYMENTS_NO_FILTER` was
repaired in 1/3 repetitions, in the second iteration; the other two attempts
remained unsuccessful after the iteration budget.

## Conclusion

Repair repeatability depends on the leakage mechanism. A wrong timestamp
variable produced a stable, local correction, whereas the missing payments
cutoff was substantially less reliable. This is evidence of mechanism-level
heterogeneity, not a population estimate: each mechanism is represented by one
underlying program repeated three times.

Reproduction:

```powershell
.\.venv-a2\Scripts\python.exe pilot/c3_score.py
```

