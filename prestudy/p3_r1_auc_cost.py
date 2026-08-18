"""
PRESTUDY2_runbook.md R1 -- цена утечек в пунктах AUC. Новых генераций не нужно:
берём уже сохранённый код (p3_out/baseline/results.jsonl) и для каждой успешно
запустившейся программы считаем завышение AUC между "как есть" (FULL) и
"как если бы утечки не было" (TRUNCATED -- каждый seed усечён оракульным
truncate() перед вызовом get_features, ровно тот же механизм, что и в
дифференциальном исполнении).

Модель оценки качества фиксирована для ВСЕХ программ и обоих режимов --
LightGBM(n_estimators=300, learning_rate=0.05, random_state=0), как в
p1_repro/leak_multi3.py, чтобы не путать эффект утечки со сменой бустера
(уже измерено: даёт 11.5 п.п. само по себе, см. PRESTUDY_RESULTS.md).
"""
import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from oracle import truncate, TIME_COLS  # noqa: E402
import p3_baseline_run as bl  # noqa: E402

TRAIN_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01"]
TEST_SEED = "2018-07-01"
N_ENTITIES_PER_SEED = 200  # ограничение ради скорости -- фиксирован для всех программ одинаково
MAX_WORKERS = 8


def _features_for_seed(fn, seed_str, truncated: bool, rng_seed=0):
    seed, prods, y = bl.labels(seed_str)
    if len(prods) > N_ENTITIES_PER_SEED:
        idx = np.random.RandomState(rng_seed).choice(len(prods), size=N_ENTITIES_PER_SEED, replace=False)
        prods, y = prods[idx], y.iloc[idx]
    db = truncate(bl.DB, seed, TIME_COLS) if truncated else bl.DB
    X = bl._call_with_timeout(fn, db, prods, seed, timeout=60)
    X = X.reindex(prods)
    return X, y


def _auc_for_mode(fn, truncated: bool):
    Xtr, ytr = [], []
    for s in TRAIN_SEEDS:
        X, y = _features_for_seed(fn, s, truncated)
        Xtr.append(X)
        ytr.append(y)
    Xtr = pd.concat(Xtr, ignore_index=True)
    ytr = pd.concat(ytr, ignore_index=True)
    Xte, yte = _features_for_seed(fn, TEST_SEED, truncated)

    Xtr = Xtr.apply(pd.to_numeric, errors="coerce")
    Xte = Xte.apply(pd.to_numeric, errors="coerce")
    common_cols = [c for c in Xtr.columns if c in Xte.columns]
    if not common_cols:
        raise ValueError("no common numeric columns between train/test features")
    Xtr, Xte = Xtr[common_cols], Xte[common_cols]

    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1, random_state=0)
    m.fit(Xtr, ytr)
    auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
    return auc


def process_one(r: dict) -> dict:
    key = f"{r['tier']}_{r['idx']}"
    try:
        fn = bl._load_program(r["code"])
        auc_full = _auc_for_mode(fn, truncated=False)
        auc_trunc = _auc_for_mode(fn, truncated=True)
        inflation_pp = (auc_full - auc_trunc) * 100
        return {"key": key, "tier": r["tier"], "idx": r["idx"], "verdict": r["verdict"],
                "auc_full": auc_full, "auc_truncated": auc_trunc, "inflation_pp": inflation_pp,
                "status": "ok"}
    except Exception as e:
        return {"key": key, "tier": r["tier"], "idx": r["idx"], "verdict": r.get("verdict"),
                "status": "error", "error": f"{type(e).__name__}: {e}"[:300]}


def main():
    rows = [json.loads(l) for l in open("p3_out/baseline/results.jsonl")]
    seen = {}
    rank = {"ok": 2, "did_not_run": 1}
    for r in rows:
        k = (r["tier"], r["idx"])
        cur = seen.get(k)
        if cur is None or rank.get(r["status"], 0) >= rank.get(cur["status"], 0):
            seen[k] = r
    candidates = [r for r in seen.values() if r["status"] == "ok" and r.get("verdict") in ("LEAK", "CLEAN")]
    print(f"кандидатов для R1: {len(candidates)}", flush=True)

    out_path = Path("p3_out/baseline/r1_auc_cost.jsonl")
    done_keys = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                done_keys.add(json.loads(line)["key"])
            except Exception:
                pass
    candidates = [r for r in candidates if f"{r['tier']}_{r['idx']}" not in done_keys]
    print(f"осталось прогнать: {len(candidates)}", flush=True)

    with out_path.open("a") as out, ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(process_one, r): r for r in candidates}
        for fut in as_completed(futures):
            res = fut.result()
            out.write(json.dumps(res, default=str) + "\n")
            out.flush()
            print(res["key"], res["status"], res.get("verdict"),
                  f"inflation_pp={res.get('inflation_pp')}" if res["status"] == "ok" else res.get("error"),
                  flush=True)


if __name__ == "__main__":
    main()
