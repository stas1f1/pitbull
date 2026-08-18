"""
PRESTUDY2_runbook.md R3 -- отрицательный контроль. Тот же нейтральный промпт,
та же задача, те же модели -- НО момент предсказания для проверки оракулом
выставлен в максимальную временную метку по ВСЕМ отслеживаемым таблицам
(orders/order_items/reviews/payments), а не только order_items, как раньше.
При этом моменте "будущего" не существует физически ни в одной из таблиц --
truncate() при таком seed оставляет ВСЕ строки без исключений, то есть
full и truncated база совпадают побитово. Любой LEAK-вердикт здесь -- либо
баг оракула, либо баг харнесса, не находка про модель.

n=20 новых генераций (10 на ярус) -- намеренно НЕ переиспользуем код из G0,
чтобы получить независимую проверку механизма.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from oracle import is_pit_correct, TIME_COLS  # noqa: E402
import p3_baseline_run as bl  # noqa: E402

N_PER_TIER = 10
N_SAMPLE_PRODUCTS = 15
OUT_PATH = Path("p3_out/baseline/r3_negative_control.jsonl")

GLOBAL_TMAX = max(
    bl.orders.order_purchase_timestamp.max(),
    bl.items.ts.max(),
    bl.reviews.review_creation_date.max(),
    bl.payments.ts.max(),
)


def check_at_global_tmax(code: str) -> dict:
    try:
        fn = bl._load_program(code)
    except Exception as e:
        return {"status": "did_not_run", "stage": "load", "error": f"{type(e).__name__}: {e}"[:500]}

    seed, prods, _y = bl.labels(str(GLOBAL_TMAX.date()), horizon=1, active=99999, min_orders=1)
    if len(prods) < N_SAMPLE_PRODUCTS:
        prods = np.union1d(prods, bl.items.product_id.dropna().unique()[:N_SAMPLE_PRODUCTS])
    sample = np.random.RandomState(0).choice(prods, size=min(N_SAMPLE_PRODUCTS, len(prods)), replace=False)

    def prog(db, entity, seed_time, _fn=fn):
        return bl._call_with_timeout(_fn, db, entity, seed_time)

    try:
        ok, detail = is_pit_correct(prog, bl.DB, sample, GLOBAL_TMAX, TIME_COLS, return_detail=True)
        return {"status": "ok", "verdict": "CLEAN" if ok else "LEAK", "detail": detail}
    except Exception as e:
        return {"status": "did_not_run", "stage": "execute", "error": f"{type(e).__name__}: {e}"[:500]}


def main():
    print("GLOBAL_TMAX:", GLOBAL_TMAX, flush=True)
    done = set()
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["tier"], r["idx"]))
            except Exception:
                pass

    with OUT_PATH.open("a") as out:
        for tier, model_id in bl.MODELS.items():
            for idx in range(1, N_PER_TIER + 1):
                if (tier, idx) in done:
                    continue
                r = bl.run_one(tier, model_id, idx)
                # заменяем проверку G0-оракула (по TEST_SEEDS) на проверку при GLOBAL_TMAX
                if r.get("code"):
                    check = check_at_global_tmax(r["code"])
                    r.update({k: v for k, v in check.items() if k not in ("stage",) or check["status"] != "ok"})
                    r["stage"] = check.get("stage")
                out.write(json.dumps(r, default=str) + "\n")
                out.flush()
                print(f"[{tier:12s} {idx:02d}] status={r.get('status')} verdict={r.get('verdict')}", flush=True)


if __name__ == "__main__":
    main()
