"""
Многотабличная утечка: измеряем, насколько завышается офлайн-оценка,
если при построении признаков забыть про временную отсечку.

Данные: Olist (реальный бразильский маркетплейс), 7 таблиц, сентябрь 2016 — октябрь 2018.
Задача в стиле RelBench: для каждого активного продавца на момент T предсказать,
будет ли у него хоть один заказ в следующие 90 дней.
"""
import warnings, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
warnings.filterwarnings("ignore")
D = "/home/claude/rel/"

# ---------- сборка событийной таблицы ----------
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
                          "order_delivered_customer_date", "order_estimated_delivery_date"]],
                  on="order_id")
           .merge(rev, on="order_id", how="left")
           .merge(pay, on="order_id", how="left"))
ev["ts"] = ev.order_purchase_timestamp
ev["delay_days"] = (ev.order_delivered_customer_date - ev.order_estimated_delivery_date).dt.days
ev["late"] = (ev.delay_days > 0).astype(float)
ev["canceled"] = (ev.order_status == "canceled").astype(float)
ev = ev.dropna(subset=["ts"]).sort_values("ts")
print(f"событий (позиций заказа): {len(ev)}, продавцов: {ev.seller_id.nunique()}, "
      f"период {ev.ts.min().date()} — {ev.ts.max().date()}")

AGGS = {"price": ["count", "sum", "mean", "max"], "freight_value": ["mean"],
        "review_score": ["mean", "min"], "pay_value": ["sum", "mean"],
        "pay_inst": ["max"], "late": ["mean"], "canceled": ["mean"],
        "delay_days": ["mean"]}


def features(seed, sellers, cutoff):
    """cutoff = момент, до которого разрешено смотреть события."""
    h = ev[ev.ts <= cutoff]
    h = h[h.seller_id.isin(sellers)]
    g = h.groupby("seller_id")
    f = g.agg(AGGS)
    f.columns = ["_".join(c) for c in f.columns]
    f["n_orders"] = g.order_id.nunique()
    f["n_products"] = g.product_id.nunique()
    f["days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    f["days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
    f["span_days"] = f.days_since_first - f.days_since_last
    f["orders_per_day"] = f.n_orders / f.span_days.clip(lower=1)
    return f.reindex(sellers)


def build(seed, horizon=90, active_window=180):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active_window)) & (ev.ts <= seed)]
    sellers = np.sort(act.seller_id.unique())
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
    return seed, sellers, y


MODES = {
    "корректно (отсечка = момент предсказания)": lambda s: s,
    "утечка: окно шире на 30 дней":              lambda s: s + pd.Timedelta(days=30),
    "утечка: окно шире на 90 дней":              lambda s: s + pd.Timedelta(days=90),
    "утечка: отсечки нет вообще":                lambda s: ev.ts.max(),
}

TRAIN_SEEDS = ["2017-07-01", "2017-10-01", "2018-01-01"]
TEST_SEED = "2018-04-01"

res, imps = [], {}
for mode, cut in MODES.items():
    Xtr, ytr = [], []
    for s in TRAIN_SEEDS:
        seed, sel, y = build(s)
        Xtr.append(features(seed, sel, cut(seed))); ytr.append(y)
    Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
    seed, sel, yte = build(TEST_SEED)
    Xte = features(seed, sel, cut(seed))

    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                       verbose=-1, random_state=0).fit(Xtr, ytr)
    auc_tr = roc_auc_score(ytr, m.predict_proba(Xtr)[:, 1])
    auc_te = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
    res.append(dict(режим=mode, n_train=len(ytr), n_test=len(yte),
                    доля_1_test=round(yte.mean(), 3),
                    AUC_train=round(auc_tr, 4), AUC_test=round(auc_te, 4)))
    imps[mode] = pd.Series(m.feature_importances_, index=Xtr.columns)
    print(f"{mode:44s} AUC_test={auc_te:.4f}", flush=True)

R = pd.DataFrame(res)
base = R.loc[0, "AUC_test"]
R["завышение_пп"] = ((R.AUC_test - base) * 100).round(2)
print()
print("=" * 92)
print("НАСКОЛЬКО ЗАВЫШАЕТСЯ ОЦЕНКА ПРИ НЕПРАВИЛЬНОЙ ВРЕМЕННОЙ ОТСЕЧКЕ")
print("=" * 92)
print(R.to_string(index=False))

print()
print("=" * 92)
print("ЛОВЯТ ЛИ УТЕЧКУ ОБЫЧНЫЕ ОДНОТАБЛИЧНЫЕ ПРОВЕРКИ?")
print("=" * 92)
for mode, cut in MODES.items():
    seed, sel, y = build(TRAIN_SEEDS[-1])
    X = features(seed, sel, cut(seed))
    best, who = 0.5, None
    for c in X.columns:
        v = X[c].fillna(X[c].median())
        if v.std() == 0:
            continue
        a = roc_auc_score(y, v); a = max(a, 1 - a)
        if a > best:
            best, who = a, c
    print(f"{mode:44s} макс AUC одного признака = {best:.3f}  ({who})")

print()
print("Куда уехала важность признаков (топ-5 по приросту при полной утечке):")
d = (imps["утечка: отсечки нет вообще"] - imps["корректно (отсечка = момент предсказания)"]).sort_values(ascending=False)
print(d.head(5).to_string())
R.to_csv("/home/claude/rel/multi_leak.csv", index=False)
