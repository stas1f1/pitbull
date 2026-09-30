# C2 — Alternate repair model (Qwen)

Status: `in_process; not_finished`; stopped by user at the saved checkpoint.

The A4 repair protocol was rerun with `qwen/qwen3-coder` on the same 62-program
corpus. Repetitions 1 and 2 completed all five iterations: 55/62 (88.7%) and
50/62 (80.6%) programs were clean, respectively. Across these two completed
repetitions, CLEAN@5 is 105/124 (84.7%).

Repetition 3 was stopped during validation of iteration 2. At the checkpoint,
49 programs were clean and 13 remained pending. Pending cases are neither
counted as clean nor converted to failures. Across the nominal 186 pairs, the
observed lower-bound counts are 129 CLEAN@1, 149 CLEAN@2, 150 CLEAN@3/4, and
154 CLEAN@5; these are provisional and must not be presented as a completed
three-repetition estimate.

The run used 1,705,454 tokens across 313 successful API calls, with recorded
cost of approximately $1.294 and no API errors. The partial result suggests
that repair transfers to a third model family, but Qwen underperforms the GLM
A4 result (97.8%) on the two completed repetitions. Because the third
repetition is incomplete, no final between-model significance claim is made.

