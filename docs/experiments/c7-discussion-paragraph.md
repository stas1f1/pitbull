# C7 — External column taxonomy: Discussion text

Status: complete as a scoped Discussion contribution.

The TravisTorrent and GHALogs artifact provides an independently defined
column-level leakage taxonomy, but not executable feature programs, per-row
availability timestamps, or historical database states. It therefore cannot
validate PITBULL's availability map or differential verdicts. At most, a
comparison with labels inferred from its data dictionaries measures
classification agreement over columns—whether both taxonomies call a field
available before prediction—not point-in-time correctness of a computation.
We use the artifact as external evidence that outcome-derived columns can
materially inflate reported performance, while reserving map validation for
datasets that preserve the program and temporal provenance needed for
executable checks.

