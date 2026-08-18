"""
Валидация SQL-оракула (p3_sql_oracle.py) на синтетических программах с известным
вердиктом: корректная (фильтр по eval_table.time_col) обязана пройти чисто,
утёкшая (без фильтра вовсе) обязана дать нарушение. Требование §11 runbook,
перенесённое на SQL-случай (была валидация только для pandas/Olist).
"""
import sys
sys.path.insert(0, "p2_repos/RelAgent/src")

import duckdb
import pandas as pd
import numpy as np

from p3_sql_oracle import SqlDiffExecOracle, frames_equal
from relagent.scientist.validation import _run_feature_queries


def build_db():
    con = duckdb.connect(":memory:")
    users = pd.DataFrame({
        "UserId": [1, 2, 3],
        # user 3 создан ПОСЛЕ seed_time (2020-06-01) — контрольный случай для
        # ловушки "своя дата создания вместо момента предсказания" (P3_spec §1,
        # строка 61 prompts.py): фиксированная CreationDate не равна per-row seed_time.
        "CreationDate": pd.to_datetime(["2020-01-01", "2020-01-05", "2020-09-01"]),
    })
    # events: some before, some after each user's "prediction time" (2020-06-01)
    events = pd.DataFrame({
        "EventId": range(1, 9),
        "UserId": [1, 1, 1, 2, 2, 3, 3, 3],
        "EventTime": pd.to_datetime([
            "2020-02-01", "2020-05-01", "2020-07-01",   # user 1: 2 past, 1 future
            "2020-03-01", "2020-08-01",                  # user 2: 1 past, 1 future
            "2020-04-01", "2020-07-01", "2020-10-01",   # user 3: 1 past, 2 future
        ]),
    })
    con.register("users_src", users)
    con.register("events_src", events)
    con.execute("CREATE TABLE users AS SELECT * FROM users_src")
    con.execute("CREATE TABLE events AS SELECT * FROM events_src")
    return con


TIME_COLS = {"users": "CreationDate", "events": "EventTime"}

eval_df = pd.DataFrame({
    "UserId": [1, 2, 3],
    "seed_time": pd.to_datetime(["2020-06-01", "2020-06-01", "2020-06-01"]),
})

CORRECT_Q = [{
    "name": "event_count",
    "sql": """
        SELECT e.UserId AS UserId, COUNT(ev.EventId) AS n_events
        FROM eval_table e
        LEFT JOIN events ev ON ev.UserId = e.UserId AND ev.EventTime < e.seed_time
        GROUP BY e.UserId
    """,
}]

LEAKY_Q = [{
    "name": "event_count",
    "sql": """
        SELECT e.UserId AS UserId, COUNT(ev.EventId) AS n_events
        FROM eval_table e
        LEFT JOIN events ev ON ev.UserId = e.UserId
        GROUP BY e.UserId
    """,
}]

# классическая ловушка из спеки: подставить собственную дату создания сущности
# вместо момента предсказания
OWNCREATE_Q = [{
    "name": "event_count",
    "sql": """
        SELECT e.UserId AS UserId, COUNT(ev.EventId) AS n_events
        FROM eval_table e
        JOIN users u ON u.UserId = e.UserId
        LEFT JOIN events ev ON ev.UserId = e.UserId AND ev.EventTime < u.CreationDate
        GROUP BY e.UserId
    """,
}]


def run_case(name, feature_queries, expect_clean):
    con = build_db()
    oracle = SqlDiffExecOracle(
        con, TIME_COLS, _run_feature_queries,
        entity_col="UserId", time_col="seed_time", sql_timeout_seconds=30,
    )
    result = oracle.check_sample(feature_queries, eval_df, n_sample=3, seed=0)
    oracle.close()
    con.close()
    ok = (result["verdict"] == "CLEAN") == expect_clean
    print(f"{name:20s} ожидали={'ЧИСТО' if expect_clean else 'НАРУШЕНИЕ':10s} "
          f"получили={result['verdict']:12s} {'OK' if ok else 'FAIL'}  "
          f"(leak_rows={result['n_leak_rows']}/{result['n_sample']})")
    if not ok:
        print("  детали:", result["row_results"])
    return ok


if __name__ == "__main__":
    print("=" * 70)
    print("ВАЛИДАЦИЯ SQL-ОРАКУЛА P3 (RelAgent-стиль feature_queries)")
    print("=" * 70)
    r1 = run_case("корректный фильтр", CORRECT_Q, expect_clean=True)
    r2 = run_case("без фильтра вовсе", LEAKY_Q, expect_clean=False)
    r3 = run_case("своя дата создания", OWNCREATE_Q, expect_clean=False)
    print("=" * 70)
    print("ИТОГ:", "оракул работает — все случаи размечены верно" if (r1 and r2 and r3)
          else "ЕСТЬ РАСХОЖДЕНИЯ — оракул чинить, не звонить в продакшен")
