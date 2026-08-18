"""
PRESTUDY2_runbook.md R5 -- вторая задача, "трудная для ошибки" (контраст к
задаче C из p3_baseline_run.py). По P3_spec.md §4:
  - один момент предсказания на сущность (не много, как в задаче C);
  - только собственная история сущности (без пути через соединение);
  - без побочной временной оси (reviews/payments исключены из схемы вовсе).

Сущность -- seller_id (аналог задачи A из P1, p1_repro/leak_multi.py).
Таблицы -- только orders + order_items, у обеих один и тот же временной
ориентир (order_purchase_timestamp), никакой скрытой второй оси времени.

Всё остальное идентично G0: нейтральный промпт по тем же критериям §1, те же
2 модели, температура 0.7, тот же оракул дифференциального исполнения.
n=30 на модель = 60 генераций.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import p3_baseline_run as bl  # noqa: E402
from oracle import is_pit_correct  # noqa: E402

N_REPEATS = 30
MAX_CONCURRENT = 8
TEST_SEEDS = ["2018-01-01", "2018-04-01", "2018-07-01"]
SAMPLE_SEED_FOR_PROMPT = "2018-01-01"  # один момент -- показываем модели только его
N_SAMPLE_SELLERS = 15

DB_HARD = {"orders": bl.orders, "order_items": bl.items}
TIME_COLS_HARD = {"orders": "order_purchase_timestamp", "order_items": "ts"}

OUT_PATH = Path("p3_out/baseline/r5_hard_task.jsonl")


def labels_seller(seed, horizon=90, active=180, min_orders=2):
    seed = pd.Timestamp(seed)
    ev = bl.items
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    cnt = act.groupby("seller_id").order_id.nunique()
    sellers = np.sort(cnt[cnt >= min_orders].index.values)
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
    return seed, sellers, y


def _schema_block():
    def col_info(df):
        return ", ".join(f"{c} ({df[c].dtype})" for c in df.columns)
    return f"""
Таблица `orders` ({len(bl.orders)} строк, ключ order_id):
  {col_info(bl.orders)}

Таблица `order_items` ({len(bl.items)} строк, ключ order_id+order_item_id, внешний ключ product_id, seller_id):
  {col_info(bl.items)}
  (столбец ts = момент покупки заказа, к которому относится позиция)
""".strip()


def _train_table_sample():
    seed, sellers, y = labels_seller(SAMPLE_SEED_FOR_PROMPT)
    idx = np.random.RandomState(0).choice(len(sellers), size=min(10, len(sellers)), replace=False)
    rows = [{"seller_id": sellers[i], "seed_time": str(seed.date()), "label": int(y.iloc[i])} for i in idx]
    return pd.DataFrame(rows).to_string(index=False)


HARD_PROMPT = f"""
Датасет: интернет-магазин Olist (Бразилия), реляционная база из двух таблиц.

{_schema_block()}

Обучающая таблица для задачи: столбцы `seller_id` (сущность), `seed_time`
(момент предсказания) и `label` (целевая переменная). Пример строк:

{_train_table_sample()}

Задача: предсказать `label` -- получит ли продавец seller_id хотя бы один
заказ в ближайшие 90 дней после seed_time. Тебе нужно написать функцию,
которая ДЛЯ ДАННОГО МОМЕНТА seed_time и списка seller_id возвращает матрицу
признаков (не сами предсказания, не финальную модель -- только признаки,
которые потом пойдут в классификатор).

Требования к коду:
- Язык: Python, доступны pandas (как pd) и numpy (как np), больше ничего не импортируй.
- Функция должна называться `get_features` и иметь сигнатуру:
  def get_features(db: dict, entity_ids, seed_time) -> pd.DataFrame
  где db = {{"orders": DataFrame, "order_items": DataFrame}} (ровно те две
  таблицы со схемой выше), entity_ids -- список/массив seller_id,
  seed_time -- pandas.Timestamp.
- Результат: DataFrame, индексированный по entity_ids (все значения из entity_ids,
  в любом порядке допустимо, но реиндексируй под entity_ids перед возвратом),
  с произвольным числом числовых столбцов-признаков.
- Используй любые из двух таблиц и любые объединения между ними, если считаешь
  это полезным для качества предсказания.
- Верни ТОЛЬКО код функции (и вспомогательных функций при необходимости) в одном
  блоке ```python ... ```, без пояснений до или после блока.
""".strip()


def check_hard(code: str) -> dict:
    try:
        fn = bl._load_program(code)
    except Exception as e:
        return {"status": "did_not_run", "stage": "load", "error": f"{type(e).__name__}: {e}"[:500]}

    seed_results = []
    for s in TEST_SEEDS:
        seed, sellers, y = labels_seller(s)
        if len(sellers) < N_SAMPLE_SELLERS:
            continue
        sample = np.random.RandomState(0).choice(sellers, size=N_SAMPLE_SELLERS, replace=False)

        def prog(db, entity, seed_time, _fn=fn):
            return bl._call_with_timeout(_fn, db, entity, seed_time)

        try:
            ok, detail = is_pit_correct(prog, DB_HARD, sample, seed, TIME_COLS_HARD, return_detail=True)
            seed_results.append({"seed": s, "status": "ran", "clean": ok, "detail": detail})
        except bl._Timeout:
            seed_results.append({"seed": s, "status": "timeout"})
        except Exception as e:
            seed_results.append({"seed": s, "status": "error", "error": f"{type(e).__name__}: {e}"[:500]})

    ran = [r for r in seed_results if r["status"] == "ran"]
    if not ran:
        return {"status": "did_not_run", "stage": "execute", "seed_results": seed_results}
    n_leak = sum(1 for r in ran if not r["clean"])
    verdict = "LEAK" if n_leak > 0 else "CLEAN"
    return {"status": "ok", "verdict": verdict, "n_seeds_ran": len(ran),
            "n_seeds_leak": n_leak, "seed_results": seed_results}


def run_one_hard(tier: str, model_id: str, idx: int) -> dict:
    r = bl.run_one(tier, model_id, idx, prompt=HARD_PROMPT)
    if r.get("code"):
        check = check_hard(r["code"])
        r.update(check)
    return r


def main():
    done = set()
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["tier"], r["idx"]))
            except Exception:
                pass

    tasks = [(tier, model_id, idx) for tier, model_id in bl.MODELS.items()
             for idx in range(1, N_REPEATS + 1) if (tier, idx) not in done]
    print(f"всего задач: {len(tasks)}", flush=True)

    with OUT_PATH.open("a") as out, ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = {pool.submit(run_one_hard, tier, model_id, idx): (tier, idx) for tier, model_id, idx in tasks}
        for fut in as_completed(futures):
            tier, idx = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"tier": tier, "idx": idx, "status": "driver_error", "error": str(e)[:300]}
            out.write(json.dumps(res, default=str) + "\n")
            out.flush()
            print(f"[{tier:12s} {idx:02d}] status={res.get('status')} verdict={res.get('verdict')}", flush=True)


if __name__ == "__main__":
    main()
