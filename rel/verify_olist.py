"""
Ворота на сам общий слой: обобщённый набор обязан воспроизвести опубликованные
числа Olist знак в знак. Сверяются AUC и «максимальный AUC одного признака»
из rel/fix_ab_auc.csv, rel/fix_c.csv, rel/delta_auc.csv против out/olist_auc.csv.

Если хоть одна ячейка разошлась — общий слой считать негодным и не публиковать
на нём ничего нового.
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
import pandas as pd

OUT = _HERE + "/out"

# режим в старых файлах -> режим общего слоя
AB = {"корректно (PIT)": "pit", "прежний эталон (отзыв+доставка)": "naive",
      "окно шире на 30 дней": "delta30", "окно шире на 60 дней": "delta60",
      "отсечки нет": "nocut"}
C = {"корректно (PIT, обе группы)": "pit", "прежний эталон (отзыв+доставка)": "naive",
     "утечка только в своей истории": "own_only", "утечка только через соединение": "join_only",
     "утечка по доступности, только nbr": "naive_nbr", "утечка в обеих группах": "both60",
     "отсечки нет нигде": "nocut"}
DELTA = {f"δ={d}": ("pit" if d == 0 else f"delta{d}") for d in [0, 5, 10, 15, 20, 30, 45, 60, 90]}
TASK = {"A": "A_seller_activity", "B": "B_seller_quality"}

new = pd.read_csv(f"{OUT}/olist_auc.csv")
key = new.set_index(["task", "test_seed", "mode"])

rows, bad = [], 0
def check(task, seed, mode, what, old_val, tol):
    global bad
    k = (task, seed, mode)
    if k not in key.index:
        rows.append((task, seed, mode, what, old_val, None, "НЕТ ЯЧЕЙКИ")); bad += 1; return
    got = float(key.loc[k, "auc" if what == "AUC" else "probe"])
    ok = abs(got - float(old_val)) <= tol
    if not ok: bad += 1
    rows.append((task, seed, mode, what, round(float(old_val), 6), round(got, 6),
                 "ok" if ok else "РАСХОЖДЕНИЕ"))

ab = pd.read_csv(f"{_HERE}/fix_ab_auc.csv")
for r in ab.itertuples():
    check(TASK[r.задача], r.тест, AB[r.режим], "AUC", r.AUC, 1e-6)
abp = pd.read_csv(f"{_HERE}/fix_ab_probe.csv")
for r in abp.itertuples():
    check(TASK[r.задача], r.тест, AB[r.режим], "probe", r.макс_AUC_признака, 5.5e-4)

c = pd.read_csv(f"{_HERE}/fix_c.csv")
for r in c.itertuples():
    check("C_product_demand", r.тест, C[r.режим], "AUC", r.AUC, 1e-6)
    check("C_product_demand", r.тест, C[r.режим], "probe", r.макс_AUC_признака, 5.5e-4)

d = pd.read_csv(f"{_HERE}/delta_auc.csv")
for r in d.itertuples():
    check(TASK[r.задача], r.тест, DELTA[r.режим], "AUC", r.AUC, 1e-6)

T = pd.DataFrame(rows, columns=["task", "seed", "mode", "what", "published", "generic", "status"])
T.to_csv(f"{OUT}/olist_verify.csv", index=False)
print(T[T.status != "ok"].to_string(index=False) if bad else "все ячейки совпали")
print(f"\nсверено {len(T)}, расхождений {bad}")
print("ВОРОТА ПРОЙДЕНЫ" if bad == 0 else "ВОРОТА НЕ ПРОЙДЕНЫ")
_sys.exit(0 if bad == 0 else 1)
