"""
Задача C: спрос на товар. Для каждого товара, продававшегося до момента T,
предсказать, будет ли он заказан в следующие 90 дней.

Смысл задачи: признаки делятся на две группы.
  1) собственная история товара;
  2) признаки продавца, к которому товар привязан — то есть агрегаты, полученные
     ПО ПУТИ СОЕДИНЕНИЯ товар -> позиция заказа -> продавец -> вся история продавца.

Это позволяет развести две разные утечки:
  - утечка по времени внутри собственной истории (бывает и в одной таблице);
  - утечка через соседнюю сущность по пути соединения (бывает только в многотабличных данных).
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import warnings, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
warnings.filterwarnings("ignore")
D = _DATA  # Olist CSVs

orders = pd.read_csv(D + "olist_orders_dataset.csv",
                     parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                  "order_estimated_delivery_date"])
items = pd.read_csv(D + "olist_order_items_dataset.csv")
rev = pd.read_csv(D + "olist_order_reviews_dataset.csv", usecols=["order_id", "review_score"])
rev = rev.groupby("order_id", as_index=False).review_score.mean()
ev = (items.merge(orders[["order_id", "order_purchase_timestamp", "order_status",
                          "order_delivered_customer_date", "order_estimated_delivery_date"]], on="order_id")
           .merge(rev, on="order_id", how="left"))
ev["ts"] = ev.order_purchase_timestamp
ev["late"] = ((ev.order_delivered_customer_date - ev.order_estimated_delivery_date).dt.days > 0).astype(float)
ev["canceled"] = (ev.order_status == "canceled").astype(float)
ev = ev.dropna(subset=["ts"]).sort_values("ts")
TMAX = ev.ts.max()

# основной продавец товара (по большинству продаж) — фиксируем один раз, без временной информации
prod_seller = ev.groupby("product_id").seller_id.agg(lambda s: s.mode().iloc[0])

OWN = {"price": ["count", "mean", "max"], "freight_value": ["mean"],
       "review_score": ["mean", "min"], "late": ["mean"], "canceled": ["mean"]}
NBR = {"price": ["count", "sum", "mean"], "review_score": ["mean", "min"],
       "late": ["mean"], "canceled": ["mean"]}


def own_features(seed, prods, cutoff):
    h = ev[(ev.ts <= cutoff) & (ev.product_id.isin(prods))]
    g = h.groupby("product_id")
    f = g.agg(OWN); f.columns = ["own_" + "_".join(c) for c in f.columns]
    f["own_n_orders"] = g.order_id.nunique()
    f["own_days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    f["own_days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
    return f.reindex(prods)


def nbr_features(seed, prods, cutoff):
    """Агрегаты по всей истории продавца — путь соединения товар -> продавец."""
    h = ev[ev.ts <= cutoff]
    g = h.groupby("seller_id")
    s = g.agg(NBR); s.columns = ["nbr_" + "_".join(c) for c in s.columns]
    s["nbr_n_products"] = g.product_id.nunique()
    s["nbr_n_orders"] = g.order_id.nunique()
    s["nbr_days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    sel = prod_seller.reindex(prods)
    out = s.reindex(sel.values); out.index = prods
    return out


def labels(seed, horizon=90, active=180, min_orders=2):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    cnt = act.groupby("product_id").order_id.nunique()
    prods = np.sort(cnt[cnt >= min_orders].index.values)
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(prods, index=prods).isin(fut.product_id.unique()).astype(int)
    return seed, prods, y


# режим = (отсечка для собственной истории, отсечка для соседа по соединению)
MODES = {
    "корректно (обе отсечки верны)":       (lambda s: s,                          lambda s: s),
    "утечка только в своей истории":       (lambda s: s + pd.Timedelta(days=60),   lambda s: s),
    "утечка только через соединение":      (lambda s: s,                          lambda s: s + pd.Timedelta(days=60)),
    "утечка в обеих группах":              (lambda s: s + pd.Timedelta(days=60),   lambda s: s + pd.Timedelta(days=60)),
    "отсечки нет нигде":                   (lambda s: TMAX,                        lambda s: TMAX),
}
ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]

rows = []
for test_seed in TESTS:
    tr_seeds = [s for s in ALL_SEEDS if s < test_seed]
    for mode, (co, cn) in MODES.items():
        Xtr, ytr = [], []
        for s in tr_seeds:
            sd, pr, y = labels(s)
            if len(pr) < 50 or y.nunique() < 2:
                continue
            Xtr.append(pd.concat([own_features(sd, pr, co(sd)), nbr_features(sd, pr, cn(sd))], axis=1))
            ytr.append(y)
        if not Xtr:
            continue
        Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
        sd, pr, yte = labels(test_seed)
        Xte = pd.concat([own_features(sd, pr, co(sd)), nbr_features(sd, pr, cn(sd))], axis=1)
        m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1, random_state=0).fit(Xtr, ytr)
        auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
        best, who = 0.5, None
        for c in Xte.columns:
            v = Xte[c].fillna(Xte[c].median())
            if v.std() == 0: continue
            a = roc_auc_score(yte, v); a = max(a, 1 - a)
            if a > best: best, who = a, c
        rows.append(dict(тест=test_seed, режим=mode, n=len(yte), доля_1=round(yte.mean(), 3),
                         AUC=round(auc, 4), макс_AUC_признака=round(best, 3), признак=who))
        print(f"{test_seed} {mode:32s} n={len(yte):5d} AUC={auc:.4f} проверка={best:.3f}", flush=True)

R = pd.DataFrame(rows)
base = R[R.режим == "корректно (обе отсечки верны)"].set_index("тест").AUC
R["завышение"] = R.apply(lambda r: (r.AUC - base.loc[r.тест]) * 100, axis=1)
R.to_csv(_HERE + "/multi_leak3.csv", index=False)

print("\n" + "=" * 86)
print("ЗАДАЧА C: ЗАВЫШЕНИЕ AUC, п.п.")
print("=" * 86)
print(R.pivot_table(index="режим", columns="тест", values="завышение").round(2).to_string())
print()
print("Базовое качество при корректных отсечках:", R[R.режим == "корректно (обе отсечки верны)"].AUC.round(3).tolist())
print()
print("=" * 86)
print("ЧТО ВИДИТ ОДНОТАБЛИЧНАЯ ПРОВЕРКА (макс AUC одного признака)")
print("=" * 86)
print(R.pivot_table(index="режим", columns="тест", values="макс_AUC_признака").round(3).to_string())
print()
for m in MODES:
    sub = R[R.режим == m]
    print(f"  {m:32s} проверка {sub.макс_AUC_признака.min():.3f}–{sub.макс_AUC_признака.max():.3f}"
          f"  порог 0.85 {'ПРЕВЫШЕН' if sub.макс_AUC_признака.min() > 0.85 else 'не превышен'}")
