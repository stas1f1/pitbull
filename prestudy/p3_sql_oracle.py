"""
Оракул P3 для SQL-программ признаков (RelAgent и родственные агенты).

Тот же принцип, что в oracle.py для Olist/pandas: программу исполняют дважды —
на полной базе и на базе, усечённой моментом предсказания КОНКРЕТНОЙ строки —
и сравнивают результат. Расхождение — доказательство утечки, не подозрение.

Отличие от oracle.py: здесь "программа" — список SQL-запросов (feature_queries_json
формата RelAgent), которые сами ссылаются на `eval_table` (текущие строки на оценку)
и присоединяются к сырым таблицам. Время у каждой строки eval_table своё, поэтому
дифференциальное исполнение делается ПОСТРОЧНО: на каждой проверяемой строке
eval_table сокращается до одной этой строки, сырые таблицы дважды подставляются —
как есть и урезанные по времени этой строки — и сравнивается результат.

Это не требует чтения/понимания сгенерированного SQL: используется тот же
исполнитель запросов (`_run_feature_queries` из RelAgent), что и в самом агенте.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import numpy as np
import pandas as pd


def _import_run_feature_queries(relagent_src: str):
    """Импортировать _run_feature_queries из указанной копии RelAgent (protect/noprotect)."""
    if relagent_src not in sys.path:
        sys.path.insert(0, relagent_src)
    # validation.py не зависит от camel/litellm — импортируется изолированно
    import importlib
    mod = importlib.import_module("relagent.scientist.validation")
    return mod._run_feature_queries


def get_time_cols(dataset_name: str) -> Dict[str, str]:
    """table_name -> time_col для всех таблиц RelBench-датасета (по метаданным, не эвристикой)."""
    from relbench.datasets import get_dataset
    db = get_dataset(dataset_name, download=False).get_db(upto_test_timestamp=False)
    return {name: tbl.time_col for name, tbl in db.table_dict.items() if tbl.time_col}


def frames_equal(a: pd.DataFrame, b: pd.DataFrame, atol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    if a.shape != b.shape:
        return False
    if sorted(a.columns) != sorted(b.columns):
        return False
    b = b[a.columns]
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv = pd.to_numeric(x, errors="coerce").to_numpy(dtype="float64")
            yv = pd.to_numeric(y, errors="coerce").to_numpy(dtype="float64")
            both_nan = np.isnan(xv) & np.isnan(yv)
            diff = np.abs(np.where(both_nan, 0.0, xv - yv))
            if not np.all(np.where(both_nan, True, diff <= atol)):
                return False
        else:
            xs = x.astype(object).where(x.notna(), None)
            ys = y.astype(object).where(y.notna(), None)
            if not xs.reset_index(drop=True).equals(ys.reset_index(drop=True)):
                return False
    return True


class SqlDiffExecOracle:
    """
    con: живое duckdb-соединение с уже материализованными сырыми таблицами
         (та же база, что видел агент — как правило, уже глобально усечена
         RelBench'ем по upto_test_timestamp; это ожидаемо и соответствует
         PITFALL_design.md §2.1a — ловим построчную, не глобальную утечку).
    time_cols: table_name -> time_col, из get_time_cols().
    run_feature_queries: функция _run_feature_queries, импортированная из
         той же копии RelAgent, что породила feature_queries (protect/noprotect
         идентичны по этой функции, но импортировать нужно явно per-run).
    """

    def __init__(self, con: duckdb.DuckDBPyConnection, time_cols: Dict[str, str],
                 run_feature_queries, entity_col: str, time_col: str,
                 sql_timeout_seconds: float = 60.0):
        self.con = con
        self.time_cols = time_cols
        self._run_feature_queries = run_feature_queries
        self.entity_col = entity_col
        self.time_col = time_col
        self.sql_timeout_seconds = sql_timeout_seconds
        self._raw_tables = [t for t in time_cols if self._table_exists(t) or self._table_exists(t + "__raw")]
        for t in self._raw_tables:
            if not self._table_exists(t + "__raw"):
                self.con.execute(f'ALTER TABLE "{t}" RENAME TO "{t}__raw";')
            self.con.execute(f'CREATE OR REPLACE VIEW "{t}" AS SELECT * FROM "{t}__raw";')

    def _table_exists(self, name: str) -> bool:
        rows = self.con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=?",
            [name],
        ).fetchall()
        return bool(rows)

    def _set_cutoff(self, cutoff: Optional[pd.Timestamp]) -> None:
        for t in self._raw_tables:
            tc = self.time_cols[t]
            if cutoff is None:
                self.con.execute(f'CREATE OR REPLACE VIEW "{t}" AS SELECT * FROM "{t}__raw";')
            else:
                self.con.execute(
                    f'CREATE OR REPLACE VIEW "{t}" AS SELECT * FROM "{t}__raw" '
                    f'WHERE "{tc}" <= TIMESTAMP \'{cutoff.isoformat(sep=" ")}\';'
                )

    def _run_one(self, feature_queries: List[Dict[str, str]], row: pd.Series,
                  cutoff: Optional[pd.Timestamp]) -> Optional[Dict[str, pd.DataFrame]]:
        self._set_cutoff(cutoff)
        one_row_df = row.to_frame().T
        if "eval_table" in self.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='eval_table'"
        ).fetchall():
            self.con.unregister("eval_table")
        self.con.register("eval_table", one_row_df)
        return self._run_feature_queries(
            self.con, feature_queries,
            entity_col=self.entity_col,
            allowed_entities=one_row_df[self.entity_col],
            sql_timeout_seconds=self.sql_timeout_seconds,
            n_entities=1,
        )

    def check_row(self, feature_queries: List[Dict[str, str]], row: pd.Series) -> Dict[str, Any]:
        """Одна строка eval_table. Возвращает вердикт + детали по различающимся запросам/колонкам."""
        t_r = pd.Timestamp(row[self.time_col])
        try:
            full = self._run_one(feature_queries, row, cutoff=None)
        except Exception as e:
            return {"status": "full_failed", "error": str(e)}
        try:
            trunc = self._run_one(feature_queries, row, cutoff=t_r)
        except Exception as e:
            return {"status": "trunc_failed", "error": str(e)}

        differing = {}
        for name in full:
            f, t = full.get(name), trunc.get(name)
            if not frames_equal(f, t):
                differing[name] = {
                    "full_shape": None if f is None else list(f.shape),
                    "trunc_shape": None if t is None else list(t.shape),
                }
        return {
            "status": "leak" if differing else "clean",
            "differing_queries": differing,
            "n_queries": len(full),
        }

    def check_sample(self, feature_queries: List[Dict[str, str]], eval_df: pd.DataFrame,
                      n_sample: int = 20, seed: int = 0) -> Dict[str, Any]:
        sample = eval_df.sample(n=min(n_sample, len(eval_df)), random_state=seed)
        results = []
        for _, row in sample.iterrows():
            results.append(self.check_row(feature_queries, row))
        n_leak = sum(1 for r in results if r["status"] == "leak")
        n_clean = sum(1 for r in results if r["status"] == "clean")
        n_error = len(results) - n_leak - n_clean
        return {
            "verdict": "LEAK" if n_leak > 0 else ("CLEAN" if n_clean > 0 else "INCONCLUSIVE"),
            "n_sample": len(sample),
            "n_leak_rows": n_leak,
            "n_clean_rows": n_clean,
            "n_error_rows": n_error,
            "row_results": results,
        }

    def close(self):
        for t in self._raw_tables:
            self._set_cutoff(None)
