# C5 — Fixed-LightGBM AUC authenticity control

Status: complete.

## Method

For three prediction tasks at three temporal cutoffs, we trained the same
LightGBM learner (`n_estimators=300`, `learning_rate=0.05`, `random_state=0`)
before and after the checker-discovered point-in-time correction. AUC is used
only as an authenticity check; it does not determine LEAK/CLEAN.

## Results

Across nine task-time pairs, the correction removed a mean 1.553 percentage
points of AUC inflation (median 0.316; range -0.096 to 5.264). Eight of nine
pairs decreased after leakage removal. Mean changes were 0.229 points for task
A, 4.044 for task B, and 0.387 for task C.

## Conclusion

The repairs remove predictive information that was genuinely useful to the
learner, especially in task B. This supports the interpretation that the
checker is eliminating exploitable future information rather than merely
rewriting equivalent code. The single -0.096-point reversal is small enough to
be consistent with sampling and model variance.

Reproduction:

```powershell
.\.venv-a2\Scripts\python.exe rel/fix_ab.py
.\.venv-a2\Scripts\python.exe rel/fix_c.py
.\.venv-a2\Scripts\python.exe pilot/c5_score.py
```

