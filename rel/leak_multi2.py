"""
Две задачи, три момента предсказания — чтобы получить разброс, а не одну точку.

Задача A: будет ли у продавца хоть один заказ в следующие 90 дней (активность).
Задача B: будет ли средняя оценка отзывов продавца в следующие 90 дней ниже 4 (качество).

Задача B важна тем, что её цель НЕ про давность заказа — значит утечка не тавтологична.
"""
import warnings, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
warnings.filterwarnings("ignore")
D = "/home/claude/rel/"

orders = pd.read_csv(D + "olist_orders_dataset.csv",
                     parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                  "order_estimated_delivery_date"])
items = pd.read_csv(D + "olist_order_items_dataset.csv")
rev = pd.read_csv(D + "olist_order_reviews_dataset.csv", usecols=["order_id", "review_score"])
pay = pd.read_csv(D + "olist_order_payments_dataset.csv",
                  usecols=["order_id", "payment_value", "payment_installments"])
rev = rev.groupby("order_id", as_index=False).review_score.mean()
pay = pay.groupby("order_id", as_index=False).agg(pay_value=("payment_value", "sum"),
                                                  pay_inst=("payment_installments", "max"))
ev = (items.merge(orders[["order_id", "order_purchase_timestamp", "order_status",
                          "order_delivered_customer_date", "order_estimated_delivery_date"]], on="order_id")
           .merge(rev, on="order_id", how="left").merge(pay, on="order_id", how="left"))
ev["ts"] = ev.order_purchase_timestamp
ev["delay_days"] = (ev.order_delivered_customer_date - ev.order_estimated_delivery_date).dt.days
ev["late"] = (ev.delay_days > 0).astype(float)
ev["canceled"] = (ev.order_status == "canceled").astype(float)
ev = ev.dropna(subset=["ts"]).sort_values("ts")
TMAX = ev.ts.max()

AGGS = {"price": ["count", "sum", "mean", "max"], "freight_value": ["mean"],
        "review_score": ["mean", "min"], "pay_value": ["sum", "mean"], "pay_inst": ["max"],
        "late": ["mean"], "canceled": ["mean"], "delay_days": ["mean"]}


def features(seed, sellers, cutoff):
    h = ev[(ev.ts <= cutoff) & (ev.seller_id.isin(sellers))]
    g = h.groupby("seller_id")
    f = g.agg(AGGS); f.columns = ["_".join(c) for c in f.columns]
    f["n_orders"] = g.order_id.nunique()
    f["n_products"] = g.product_id.nunique()
    f["days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    f["days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
    f["span_days"] = f.days_since_first - f.days_since_last
    f["orders_per_day"] = f.n_orders / f.span_days.clip(lower=1)
    return f.reindex(sellers)


def labels(seed, task, horizon=90, active=180):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    sellers = np.sort(act.seller_id.unique())
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    if task == "A":
        y = pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
        return seed, sellers, y
    # задача B: качество. Берём только продавцов с >=3 отзывами в окне.
    fr = fut.dropna(subset=["review_score"]).groupby("seller_id").review_score.agg(["mean", "count"])
    fr = fr[fr["count"] >= 3]
    sellers = np.sort([s for s in sellers if s in fr.index])
    y = (fr.loc[sellers, "mean"] < 4.0).astype(int)
    return seed, sellers, y


MODES = {
    "корректно":            lambda s: s,
    "окно шире на 30 дней": lambda s: s + pd.Timedelta(days=30),
    "окно шире на 60 дней": lambda s: s + pd.Timedelta(days=60),
    "отсечки нет":          lambda s: TMAX,
}
ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]

rows, probes = [], []
for task in ["A", "B"]:
    for test_seed in TESTS:
        tr_seeds = [s for s in ALL_SEEDS if s < test_seed]
        for mode, cut in MODES.items():
            Xtr, ytr = [], []
            for s in tr_seeds:
                sd, sel, y = labels(s, task)
                if len(sel) < 30 or y.nunique() < 2:
                    continue
                Xtr.append(features(sd, sel, cut(sd))); ytr.append(y)
            if not Xtr:
                continue
            Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
            sd, sel, yte = labels(test_seed, task)
            if len(sel) < 30 or yte.nunique() < 2:
                continue
            Xte = features(sd, sel, cut(sd))
            m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                               random_state=0).fit(Xtr, ytr)
            auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
            rows.append(dict(задача=task, тест=test_seed, режим=mode,
                             n_test=len(yte), доля_1=round(yte.mean(), 3), AUC=round(auc, 4)))
            # однотабличная проверка на признаках теста
            best, who = 0.5, None
            for c in Xte.columns:
                v = Xte[c].fillna(Xte[c].median())
                if v.std() == 0: continue
                a = roc_auc_score(yte, v); a = max(a, 1 - a)
                if a > best: best, who = a, c
            probes.append(dict(задача=task, тест=test_seed, режим=mode,
                               макс_AUC_признака=round(best, 3), признак=who))
            print(f"{task} {test_seed} {mode:22s} n={len(yte):5d} AUC={auc:.4f}", flush=True)

R = pd.DataFrame(rows); P = pd.DataFrame(probes)
R.to_csv(D + "multi_leak2.csv", index=False); P.to_csv(D + "multi_probe2.csv", index=False)

print("\n" + "=" * 88)
print("ЗАВЫШЕНИЕ AUC ОТНОСИТЕЛЬНО КОРРЕКТНОЙ ОТСЕЧКИ (п.п.)")
print("=" * 88)
base = R[R.режим == "корректно"].set_index(["задача", "тест"]).AUC
R["завышение"] = R.apply(lambda r: (r.AUC - base.loc[(r.задача, r.тест)]) * 100, axis=1)
piv = R.pivot_table(index=["задача", "режим"], columns="тест", values="завышение").round(2)
print(piv.to_string())
print()
print("Сводка по задачам (медиана завышения по трём моментам предсказания):")
print(R[R.режим != "корректно"].groupby(["задача", "режим"]).завышение
      .agg(медиана="median", мин="min", макс="max").round(2).to_string())
print()
print("Базовое качество при корректной отсечке:")
print(R[R.режим == "корректно"].pivot_table(index="задача", columns="тест", values="AUC").round(3).to_string())

print("\n" + "=" * 88)
print("ЧТО ВИДИТ ОБЫЧНАЯ ОДНОТАБЛИЧНАЯ ПРОВЕРКА (макс AUC одного признака)")
print("=" * 88)
print(P.pivot_table(index=["задача", "режим"], columns="тест", values="макс_AUC_признака").round(3).to_string())
print()
print("Порог DataRobot: 0.85 предупреждение / 0.975 автовыброс. Порог H2O: 0.8 / 0.95 / 0.999.")
for t in ["A", "B"]:
    ok = P[(P.задача == t) & (P.режим == "корректно")].макс_AUC_признака
    leak30 = P[(P.задача == t) & (P.режим == "окно шире на 30 дней")].макс_AUC_признака
    print(f"  задача {t}: корректно {ok.min():.3f}–{ok.max():.3f}, "
          f"утечка 30 дней {leak30.min():.3f}–{leak30.max():.3f}  -> "
          f"{'РАЗЛИЧИМЫ порогом' if leak30.min() > max(0.85, ok.max()) else 'ПОРОГОМ НЕ РАЗЛИЧИМЫ'}")
