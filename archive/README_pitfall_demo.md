# PITBULL

**P**oint-**i**n-**T**ime **B**oundary **U**nderstanding & **L**eakage **L**imiter:
zero-configuration differential checking of generated feature code, and closing the
loop — the availability map is inferred automatically (boundary understanding), and
the witness is fed back to the agent that wrote the code until it comes out clean
(leakage limiter).

Target: **FSE 2027 research track, full-paper deadline October 2, 2026.**
Research plan: [`proposals/fse2027_proposal.md`](proposals/fse2027_proposal.md);
literature scan: [`proposals/lit_scan_2026-08.md`](proposals/lit_scan_2026-08.md).

This repository is a fork of [PITFALL](https://github.com/stas1f1/pitfall) (ICDM 2026
demo, full history preserved, forked at `d65ced9`). Everything below documents the
inherited core — harness, corpora, data, results — on which the two new modules
(`mapinfer/`, `repairloop/`) will be built. Heavy untracked data stays in `../pitfall`
and is reached via local symlinks (`PITFALL_ext_data`, `prestudy/p3_scratch`,
`prestudy/p2_repos`); recreate them after a fresh clone, and put an OpenRouter key in
`.env` for generation experiments.

---

## The inherited PITFALL core

Point-in-time correctness of feature pipelines for multi-table machine learning,
checked by **differential execution**.

```
φ(D, t) = φ(D|t, t),   D|t = { r ∈ D : avail(r) ≤ t }
```

The feature program is run twice: on the full database and on a copy physically
truncated at the prediction time. A divergence is a witness of a violation under the
declared availability map, not a suspicion. The code is never parsed: the program is a
black box. The guarantee is one-sided (no divergence at the tested seed times does not
prove correctness), and floating-point aggregates need a tolerance, which is set from the
noise floor of a negative control.

- Paper (ICDM 2026 demo track, 4 pages): [`paper/pitfall.pdf`](paper/pitfall.pdf)
- Interactive demo: <https://stas1f1.github.io/pitfall/>
- Project state, every number with its source, methodological rules and open questions:
  [`HANDOVER.md`](HANDOVER.md) (in Russian). Plain-language walkthrough of the paper:
  [`docs/PAPER_EXPLAINED.md`](docs/PAPER_EXPLAINED.md).

## Quick start

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements.txt
#   (or: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt)
cd demo && ../.venv/bin/python demo.py                 # console, four scenes, about a minute on two CPU cores
../.venv/bin/python demo.py --program try_me.py        # check a feature function of your own
../.venv/bin/python build_site_data.py && ../.venv/bin/python build_site.py   # → demo/index.html
```

The interactive page is `demo/index.html` (open it in a browser; it is self-contained).
`build_site_data.py` recomputes every number on the page from the real database (~1.5 min).

Data are read from `PITFALL_olist_data/` at the repository root (included in the
repository); another location can be given in `PITFALL_DATA`. All paths in the scripts are
relative to the repository, so they run from any directory.

Console scenes (no network, no GPU):

| | scene | checker | univariate probe (DataRobot / H2O) | inflation |
|---|---|---|---|---|
| 1 | featuretools with default settings | VIOLATION, 11 columns | **miss** / notifies at 2 of 3 seed times (0.809) | +16.3 pp |
| 2 | our own reference code, first version | VIOLATION, 4 columns | **miss** / **miss** (0.687) | +5.3 pp |
| 3 | the same code after the fix | CLEAN | correctly silent | 0.00 |
| 4 | LOCATOR on the programs of scenes 1–2 | channels `items` / `review_score`, `late`, `delay_days` | — | patch → CLEAN |

Thresholds: DataRobot — Gini Norm 0.85 / 0.975 (= AUC 0.925 / 0.9875); H2O Driverless AI — AUC 0.80 / 0.95 / 0.999.

## Reproducing the numbers in the paper

```bash
cd rel   # interpreter: ../.venv/bin/python
python3 fix_ab.py        # tasks A and B        → fix_ab_auc.csv, fix_ab_probe.csv
python3 fix_c.py         # task C               → fix_c.csv
python3 delta_sweep.py   # the I(δ) curve       → delta_auc.csv, delta_probe.csv
python3 oracle_check.py  # old reference program against the fixed one (reduced feature set:
                         # 3 diverging columns; the demo uses the full set: 4)
cd ../demo && python3 ft_scene.py   # featuretools in three regimes → ft_scene.csv
cd ../fig && python3 make_figs.py && python3 make_figs2.py
```

A summary of all numbers: `rel/RESULTS.md`.

## Other databases and other people's code

A shared layer runs the same set of experiments on any database: a new database is one
file in `rel/adapters/`, modelled on `_template.py`. Results and verdicts against all
pre-registered criteria: `docs/EXTENSION_RESULTS.md`; the plan: `docs/EXTENSION_plan.md`.

```bash
cd rel   # interpreter: ../.venv/bin/python
python3 verify_olist.py       # gate on the shared layer itself: 156 Olist values reproduced to the digit
python3 gate.py f1            # acceptance gate for a database (size, secondary time axis, checker, control)
python3 suite.py f1           # the whole grid of cells   → out/f1_auc.csv, _oracle.csv, _summary.md
python3 paired.py f1          # paired bootstrap of the AUC difference → out/f1_paired.csv
python3 sqloracle.py          # the check on the published expert SQL of the RelBench user study (audit/)
python3 sqlcost.py f1_driver-dnf f1_driver-top3 stack_user-badge   # what those violations cost
python3 relagent.py           # the check on the 37-query corpus written by an LLM agent (rel-stack)
```

External databases (RelBench: rel-f1, rel-stack, rel-event, rel-hm, rel-amazon) go into
`PITFALL_ext_data/` (or `PITFALL_EXT_DATA`) and are not part of the repository:

```bash
mkdir -p PITFALL_ext_data && cd PITFALL_ext_data
for d in rel-f1 rel-stack rel-event rel-hm rel-amazon; do
  curl -L -o $d.zip https://relbench.stanford.edu/download/$d/db.zip && unzip -q $d.zip -d $d; done
mkdir -p tasks && for t in driver-dnf driver-top3 driver-position; do
  curl -L -o tasks/rel-f1__$t.zip https://relbench.stanford.edu/download/rel-f1/tasks/$t.zip
  unzip -q tasks/rel-f1__$t.zip -d tasks/rel-f1__$t; done
```

The acceptance gate is mandatory before any measurement on a new database: it checks the
size, the presence of a secondary time axis, the undecidable columns, the task sizes and,
above all, that the correct program comes out CLEAN while the naive one leaks. On Olist
the gate caught a mis-specified negative control and a second undecidable column.

## Paper

```bash
cd paper && pdflatex pitfall.tex && bibtex pitfall && pdflatex pitfall.tex && pdflatex pitfall.tex
```

Four pages, IEEE conference format. `IEEEtran.cls` and `IEEEtran.bst` are bundled in
`paper/`, so no extra TeX packages are needed; references live in `paper/pitfall.bib`.

## Data

Olist is a public Brazilian marketplace dataset (Kaggle `olistbr/brazilian-ecommerce`,
CC BY-NC-SA 4.0): 7 tables, 112,650 order line items, September 2016 – October 2018.
The seven `olist_*.csv` files are in `PITFALL_olist_data/`. The scripts use
`olist_orders_dataset.csv`, `olist_order_items_dataset.csv`,
`olist_order_reviews_dataset.csv`, `olist_order_payments_dataset.csv`,
`olist_products_dataset.csv`, `olist_sellers_dataset.csv` and
`olist_customers_dataset.csv`.

## Limits of the method

- A column with no availability timestamp (a mutable status kept without history) is
  **undecidable**: the truncated database is identical to the full one for it.
- A non-deterministic program diverges without leaking; it needs a fixed seed, and columns
  that differ between identical reruns carry no verdict.
- The guarantee is one-sided: the tool finds violations and cannot certify their absence.
  A clean verdict covers only the seed times that were tested; the rel-event files in the
  paper are clean at one seed time out of 24.
- The check decides code against the declared availability map; whether that map matches
  intent is a modelling question.
