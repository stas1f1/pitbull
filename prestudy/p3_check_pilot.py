import sys, json
sys.path.insert(0, "p2_repos/RelAgent/src")

import duckdb
import pandas as pd
from relagent.scientist.validation import _run_feature_queries
from p3_sql_oracle import SqlDiffExecOracle, get_time_cols

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else None
PROGRAM_PATH = sys.argv[2]
N_SAMPLE = int(sys.argv[3]) if len(sys.argv) > 3 else 20

time_cols = get_time_cols("rel-stack")
print("time_cols:", time_cols)

con = duckdb.connect(DB_PATH, read_only=False)
eval_df = con.execute(
    'SELECT "OwnerUserId", "timestamp" FROM train_table USING SAMPLE %d' % N_SAMPLE
).df()

program = json.load(open(PROGRAM_PATH))
feature_queries = program["feature_queries"]
print(f"programa: {len(feature_queries)} queries")

oracle = SqlDiffExecOracle(
    con, time_cols, _run_feature_queries,
    entity_col="OwnerUserId", time_col="timestamp", sql_timeout_seconds=60,
)
result = oracle.check_sample(feature_queries, eval_df, n_sample=N_SAMPLE, seed=0)
print(json.dumps({k: v for k, v in result.items() if k != "row_results"}, indent=2))
for r in result["row_results"]:
    if r["status"] != "clean":
        print(r)
