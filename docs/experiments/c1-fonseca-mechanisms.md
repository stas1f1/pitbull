# C1 — Clean-room reimplementation of Fonseca mechanisms

Status: complete.

## Method

We independently implemented the three false-negative mechanisms described in
Section 8.3 of Fonseca et al.: incomplete temporal coverage (M1),
perturbation-insensitivity (M2), and re-stamping a future-derived value with an
admissible timestamp (M3). Each mechanism has five small deterministic cases.
These are mechanism demonstrations, not a reproduction of the authors'
benchmark, so their rates are not compared with the paper's reported numbers.

## Results

- **M1:** the fixed sampled times detected 0/5 cases, while exhaustive temporal
  probing detected 5/5. The leak existed only between sampled epochs.
- **M2:** full-versus-past witness execution detected 5/5, while the fixed
  canary perturbation detected 0/5 because the thresholded output did not flip.
- **M3:** physical past-only execution and the canary detected 5/5, but a
  stamp-only policy accepted all 5 future-derived, re-stamped values.

## Conclusion

The mechanisms reproduce the expected qualitative boundaries. Sampling can
miss narrow temporal windows, a particular perturbation can be observationally
silent, and timestamps supplied by the program are not reliable evidence of
provenance. PITBULL's physical past-only witness addresses M2 and M3 in these
examples, but finite temporal coverage remains a one-sided test rather than a
proof of correctness.

Reproduction:

```powershell
.\.venv-a2\Scripts\python.exe pilot/c1_fonseca_mechanisms.py
```

