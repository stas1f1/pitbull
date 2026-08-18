import sys, json, time
sys.path.insert(0, "p2_repos/RelAgent/src")

import duckdb
import pandas as pd
from relagent.scientist.validation import _run_feature_queries
from p3_sql_oracle import SqlDiffExecOracle, get_time_cols

DB_PATH = sys.argv[1]
TRIALS_PATH = sys.argv[2]
LABEL = sys.argv[3] if len(sys.argv) > 3 else "?"
N_SAMPLE = int(sys.argv[4]) if len(sys.argv) > 4 else 10

time_cols = get_time_cols("rel-stack")
con = duckdb.connect(DB_PATH, read_only=False)
eval_df = con.execute('SELECT "OwnerUserId", "timestamp" FROM train_table USING SAMPLE %d' % N_SAMPLE).df()

oracle = SqlDiffExecOracle(
    con, time_cols, _run_feature_queries,
    entity_col="OwnerUserId", time_col="timestamp", sql_timeout_seconds=30,
)

trials = [json.loads(l) for l in open(TRIALS_PATH)]
print(f"=== {LABEL}: {len(trials)} trials ===")

results = []
for t in trials:
    tid = t["trial_id"]
    fq = t.get("feature_queries")
    if not fq:
        print(f"trial {tid}: no feature_queries, skip")
        continue
    t0 = time.time()
    try:
        r = oracle.check_sample(fq, eval_df, n_sample=N_SAMPLE, seed=0)
        verdict = r["verdict"]
        detail = f"leak_rows={r['n_leak_rows']}/{r['n_sample']} err_rows={r['n_error_rows']}"
    except Exception as e:
        verdict = "ORACLE_ERROR"
        detail = str(e)[:200]
    dt = time.time() - t0
    print(f"trial {tid:3d}: {verdict:12s} {detail}  ({dt:.1f}s)")
    results.append({"trial_id": tid, "verdict": verdict, "detail": detail})

n_leak = sum(1 for r in results if r["verdict"] == "LEAK")
n_clean = sum(1 for r in results if r["verdict"] == "CLEAN")
n_other = len(results) - n_leak - n_clean
print(f"\n{LABEL} SUMMARY: {len(results)} checked | LEAK={n_leak} CLEAN={n_clean} OTHER={n_other}")

json.dump(results, open(f"p3_out/pilot/{LABEL}_oracle_results.json", "w"), indent=2)
