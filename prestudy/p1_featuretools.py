"""
P1 — featuretools с настройками по умолчанию.

Три режима автоматического межтабличного построения признаков, всё остальное одинаково:
  D1 «как делает большинство»      cutoff_time=None
  D2 «отсечка, настройка по умолч» cutoff_time=<(сущность, момент)>, include_cutoff_time=True
  D3 «строго корректно»            тот же cutoff_time, include_cutoff_time=False, add_last_time_indexes()

Задачи A (активность продавца) и C (спрос на товар) — метки взяты из leak_multi2.py / leak_multi3.py
без изменений, чтобы числа были сопоставимы с rel/RESULTS.md.
"""
import warnings, sys, json
import numpy as np, pandas as pd
import featuretools as ft
from woodwork.logical_types import Categorical, Double, Datetime
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")
D = "p1_repro/"
OUT = "p1_out/"

# ---------------------------------------------------------------- данные
orders = pd.read_csv(D + "olist_orders_dataset.csv",
                     parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                  "order_estimated_delivery_date"])
items = pd.read_csv(D + "olist_order_items_dataset.csv")
revs = pd.read_csv(D + "olist_order_reviews_dataset.csv",
                   parse_dates=["review_creation_date"])
pays = pd.read_csv(D + "olist_order_payments_dataset.csv")
prods = pd.read_csv(D + "olist_products_dataset.csv")
sells = pd.read_csv(D + "olist_sellers_dataset.csv")

orders = orders.dropna(subset=["order_purchase_timestamp"])
ots = orders.set_index("order_id").order_purchase_timestamp

# --- таблица событий для МЕТОК (идентична leak_multi2/3) ---
rev_m = revs.groupby("order_id", as_index=False).review_score.mean()
ev = (items.merge(orders[["order_id", "order_purchase_timestamp", "order_status"]], on="order_id")
           .merge(rev_m, on="order_id", how="left"))
ev["ts"] = ev.order_purchase_timestamp
ev = ev.dropna(subset=["ts"]).sort_values("ts")

ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]


def labels_A(seed, horizon=90, active=180):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    sellers = np.sort(act.seller_id.unique())
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
    return seed, sellers, y


def labels_C(seed, horizon=90, active=180, min_orders=2):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    cnt = act.groupby("product_id").order_id.nunique()
    p = np.sort(cnt[cnt >= min_orders].index.values)
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(p, index=p).isin(fut.product_id.unique()).astype(int)
    return seed, p, y


TASKS = {"A": ("sellers", "seller_id", labels_A), "C": ("products", "product_id", labels_C)}


# ---------------------------------------------------------------- EntitySet
def build_es():
    it = items.copy()
    it["item_uid"] = it.order_id + "__" + it.order_item_id.astype(str)
    it["ts"] = it.order_id.map(ots)
    it = it.dropna(subset=["ts"])
    it = it[["item_uid", "order_id", "product_id", "seller_id", "price", "freight_value", "ts"]]

    od = orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]].copy()

    rv = revs[["review_id", "order_id", "review_score", "review_creation_date"]].dropna(
        subset=["review_creation_date"]).drop_duplicates("review_id").copy()
    rv = rv[rv.order_id.isin(od.order_id)]

    pv = pays.copy()
    pv["pay_uid"] = pv.order_id + "__" + pv.payment_sequential.astype(str)
    pv["ts"] = pv.order_id.map(ots)
    pv = pv.dropna(subset=["ts"])
    pv = pv[["pay_uid", "order_id", "payment_value", "payment_installments", "payment_type", "ts"]]

    pr = prods[["product_id", "product_category_name", "product_weight_g",
                "product_photos_qty"]].drop_duplicates("product_id").copy()
    sl = sells[["seller_id", "seller_state"]].drop_duplicates("seller_id").copy()
    # держим только те сущности, что реально встречаются
    pr = pr[pr.product_id.isin(it.product_id)]
    sl = sl[sl.seller_id.isin(it.seller_id)]
    it = it[it.product_id.isin(pr.product_id) & it.seller_id.isin(sl.seller_id) & it.order_id.isin(od.order_id)]
    pv = pv[pv.order_id.isin(od.order_id)]
    rv = rv[rv.order_id.isin(od.order_id)]

    es = ft.EntitySet(id="olist")
    es = es.add_dataframe(dataframe_name="sellers", dataframe=sl, index="seller_id",
                          logical_types={"seller_state": Categorical})
    es = es.add_dataframe(dataframe_name="products", dataframe=pr, index="product_id",
                          logical_types={"product_category_name": Categorical})
    es = es.add_dataframe(dataframe_name="orders", dataframe=od, index="order_id", time_index="order_purchase_timestamp",
                          logical_types={"order_status": Categorical, "customer_id": Categorical})
    es = es.add_dataframe(dataframe_name="order_items", dataframe=it, index="item_uid", time_index="ts",
                          logical_types={"price": Double, "freight_value": Double})
    es = es.add_dataframe(dataframe_name="reviews", dataframe=rv, index="review_id", time_index="review_creation_date",
                          logical_types={"review_score": Double})
    es = es.add_dataframe(dataframe_name="payments", dataframe=pv, index="pay_uid", time_index="ts",
                          logical_types={"payment_value": Double, "payment_type": Categorical})

    es = es.add_relationship("sellers", "seller_id", "order_items", "seller_id")
    es = es.add_relationship("products", "product_id", "order_items", "product_id")
    es = es.add_relationship("orders", "order_id", "order_items", "order_id")
    es = es.add_relationship("orders", "order_id", "reviews", "order_id")
    es = es.add_relationship("orders", "order_id", "payments", "order_id")
    return es


AGG = ["count", "sum", "mean", "max", "min", "std"]
TRANS = []


def run_dfs(es, target, ct, mode):
    kw = dict(entityset=es, target_dataframe_name=target, agg_primitives=AGG,
              trans_primitives=TRANS, max_depth=2, verbose=False, n_jobs=1)
    if mode == "D1":
        fm, fd = ft.dfs(**kw)                      # cutoff_time=None — «как делает большинство»
        return fm, fd
    kw["cutoff_time"] = ct
    kw["include_cutoff_time"] = (mode == "D2")     # D2: True (по умолчанию); D3: False
    fm, fd = ft.dfs(**kw)
    return fm, fd


def align(fm, instances):
    """dfs с cutoff_time возвращает матрицу с индексом = instance_id (по одной строке
    на сущность, так как в каждом прогоне ровно один момент). Выравниваем по списку сущностей."""
    m = fm[~fm.index.duplicated(keep="last")].reindex(instances)
    m.index = range(len(instances))
    return m


def numeric(df):
    d = df.select_dtypes(include=[np.number]).copy()
    d = d.loc[:, d.notna().any()]
    return d


def probe(X, y):
    best, who = 0.5, None
    for c in X.columns:
        v = X[c]
        if v.notna().sum() < 10 or v.std(skipna=True) in (0, np.nan) or not np.isfinite(v.std(skipna=True)):
            continue
        v = v.fillna(v.median())
        if v.std() == 0:
            continue
        try:
            a = roc_auc_score(y, v)
        except Exception:
            continue
        a = max(a, 1 - a)
        if a > best:
            best, who = a, c
    return best, who


def main():
    es = build_es()
    es_lti = build_es()
    es_lti.add_last_time_indexes()
    print("EntitySet построен:", {n: len(es[n]) for n in
          ["sellers", "products", "orders", "order_items", "reviews", "payments"]}, flush=True)

    rows = []
    for task, (target, idx_col, lab) in TASKS.items():
        # собираем cutoff_time по всем seed'ам сразу
        per_seed = {}
        for s in ALL_SEEDS:
            sd, inst, y = lab(s)
            per_seed[s] = (sd, inst, y)
        fms = {}
        # D1 — один прогон на всю базу, без момента: «посчитали признаки один раз и приджойнили»
        print(f"[{task}] dfs D1 …", flush=True)
        fms[("D1", None)], _ = run_dfs(es, target, None, "D1")
        print(f"[{task}] D1: {fms[('D1', None)].shape} ", flush=True)
        # D2/D3 — отдельный прогон на каждый момент, чтобы выравнивание было однозначным
        for mode in ["D2", "D3"]:
            e = es_lti if mode == "D3" else es
            for s in ALL_SEEDS:
                sd, inst, _ = per_seed[s]
                ct = pd.DataFrame({"instance_id": inst, "time": sd})
                fm, _ = run_dfs(e, target, ct, mode)
                fms[(mode, s)] = fm
                print(f"[{task}] {mode} {s}: {fm.shape}", flush=True)

        for test_seed in TESTS:
            tr = [s for s in ALL_SEEDS if s < test_seed]
            for mode in ["D1", "D2", "D3"]:
                Xtr, ytr = [], []
                for s in tr:
                    sd, inst, y = per_seed[s]
                    fm = fms[("D1", None)] if mode == "D1" else fms[(mode, s)]
                    Xtr.append(align(fm, inst)); ytr.append(y.values)
                sd, inst, yte = per_seed[test_seed]
                fm = fms[("D1", None)] if mode == "D1" else fms[(mode, test_seed)]
                Xte = align(fm, inst)
                Xtr = pd.concat(Xtr, ignore_index=True); ytr = np.concatenate(ytr)

                cols = sorted(set(numeric(Xtr).columns) & set(numeric(Xte).columns))
                Xtr, Xte = Xtr[cols].astype(float), Xte[cols].astype(float)
                m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                                   random_state=0).fit(Xtr, ytr)
                auc = roc_auc_score(yte.values, m.predict_proba(Xte)[:, 1])
                pb, who = probe(Xte, yte.values)
                rows.append(dict(задача=task, тест=test_seed, режим=mode, n=len(yte),
                                 доля_1=round(float(yte.mean()), 3), n_признаков=len(cols),
                                 AUC=round(auc, 4), проверка=round(pb, 3), признак=who))
                print(f"  {task} {test_seed} {mode}  n={len(yte):5d} feats={len(cols):4d} "
                      f"AUC={auc:.4f} проверка={pb:.3f}", flush=True)

    R = pd.DataFrame(rows)
    base = R[R.режим == "D3"].set_index(["задача", "тест"]).AUC
    R["завышение_vs_D3"] = R.apply(lambda r: round((r.AUC - base.loc[(r.задача, r.тест)]) * 100, 2), axis=1)
    R.to_csv(OUT + "p1_results.csv", index=False)

    print("\n" + "=" * 78)
    print("P1: ЗАВЫШЕНИЕ AUC ОТНОСИТЕЛЬНО D3, п.п.")
    print("=" * 78)
    print(R.pivot_table(index=["задача", "режим"], columns="тест", values="завышение_vs_D3").round(2).to_string())
    print("\nAUC:")
    print(R.pivot_table(index=["задача", "режим"], columns="тест", values="AUC").round(4).to_string())
    print("\nОДНОМЕРНАЯ ПРОВЕРКА (пороги 0.85 / 0.95):")
    print(R.pivot_table(index=["задача", "режим"], columns="тест", values="проверка").round(3).to_string())
    print("\nВклад ОДНОГО ТОЛЬКО include_cutoff_time (D2 минус D3), п.п.:")
    d = R[R.режим == "D2"].set_index(["задача", "тест"]).завышение_vs_D3
    print(d.round(2).to_string())


if __name__ == "__main__":
    main()
