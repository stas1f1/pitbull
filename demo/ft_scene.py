"""
Сцена 1: featuretools с настройками по умолчанию.
Один и тот же EntitySet, один и тот же набор примитивов, одна и та же модель.
Различие только в том, передана ли таблица моментов предсказания в dfs.
"""
import sys, time, warnings, numpy as np, pandas as pd, featuretools as ft
sys.path.insert(0, "/home/claude/rel")
from woodwork.logical_types import Categorical, Double, Datetime
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
warnings.filterwarnings("ignore")
D = "/home/claude/rel/"

orders = pd.read_csv(D + "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
orders = orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]].dropna(
    subset=["order_purchase_timestamp"])
items = pd.read_csv(D + "olist_order_items_dataset.csv")
items["oi_id"] = items.order_id + "_" + items.order_item_id.astype(str)
items = items.merge(orders[["order_id", "order_purchase_timestamp"]], on="order_id")
rev = pd.read_csv(D + "olist_order_reviews_dataset.csv",
                  usecols=["review_id", "order_id", "review_score", "review_creation_date"],
                  parse_dates=["review_creation_date"]).drop_duplicates("review_id")
rev = rev[rev.order_id.isin(orders.order_id)]
prods = pd.read_csv(D + "olist_products_dataset.csv")[["product_id", "product_category_name",
                                                       "product_weight_g", "product_photos_qty"]]
sell = pd.read_csv(D + "olist_sellers_dataset.csv")[["seller_id", "seller_state"]]

es = ft.EntitySet("olist")
es = es.add_dataframe(dataframe_name="orders", dataframe=orders.copy(), index="order_id", time_index="order_purchase_timestamp",
                      logical_types={"order_status": Categorical, "customer_id": Categorical})
es = es.add_dataframe(dataframe_name="items", dataframe=items[["oi_id", "order_id", "product_id", "seller_id", "price",
                                      "freight_value", "order_purchase_timestamp"]].copy(),
                      index="oi_id", time_index="order_purchase_timestamp",
                      logical_types={"product_id": Categorical, "seller_id": Categorical})
es = es.add_dataframe(dataframe_name="reviews", dataframe=rev.copy(), index="review_id", time_index="review_creation_date",
                      logical_types={"review_score": Double})
es = es.add_dataframe(dataframe_name="products", dataframe=prods.copy(), index="product_id",
                      logical_types={"product_category_name": Categorical})
es = es.add_dataframe(dataframe_name="sellers", dataframe=sell.copy(), index="seller_id",
                      logical_types={"seller_state": Categorical})
es = es.add_relationship("orders", "order_id", "items", "order_id")
es = es.add_relationship("orders", "order_id", "reviews", "order_id")
es = es.add_relationship("products", "product_id", "items", "product_id")
es = es.add_relationship("sellers", "seller_id", "items", "seller_id")

AGG = ["count", "sum", "mean", "max", "min", "std"]
TRANS = []

evts = items[["product_id", "seller_id", "order_id", "order_purchase_timestamp"]].rename(
    columns={"order_purchase_timestamp": "ts"})

def labels(seed, horizon=90, active=180, min_orders=2):
    seed = pd.Timestamp(seed)
    act = evts[(evts.ts > seed - pd.Timedelta(days=active)) & (evts.ts <= seed)]
    cnt = act.groupby("product_id").order_id.nunique()
    pr = np.sort(cnt[cnt >= min_orders].index.values)
    fut = evts[(evts.ts > seed) & (evts.ts <= seed + pd.Timedelta(days=horizon))]
    y = pd.Series(pd.Series(pr, index=pr).isin(fut.product_id.unique()).astype(int), index=pr)
    return seed, pr, y

def build(seed, pr, mode):
    if mode == "туториал":            # cutoff_time не передан вовсе — база видна целиком
        fm, _ = ft.dfs(entityset=es, target_dataframe_name="products", agg_primitives=AGG,
                       trans_primitives=TRANS, max_depth=2, verbose=0)
        return fm.reindex(pr)
    ct = pd.DataFrame({"product_id": pr, "time": seed})
    fm, _ = ft.dfs(entityset=es, target_dataframe_name="products", agg_primitives=AGG,
                   trans_primitives=TRANS, max_depth=2, cutoff_time=ct,
                   cutoff_time_in_index=False, include_cutoff_time=(mode == "включая границу"),
                   verbose=0)
    return fm.reindex(pr)

MODES = ["туториал", "с отсечкой", "включая границу"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]
TRAIN = ["2017-07-01", "2017-10-01"]

def numeric(X):
    return X.select_dtypes(include=[np.number]).copy()

rows = []
for mode in MODES:
    for test_seed in TESTS:
        t0 = time.time()
        Xtr, ytr = [], []
        for s in TRAIN:
            sd, pr, y = labels(s)
            Xtr.append(numeric(build(sd, pr, mode))); ytr.append(y)
        Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
        sd, pr, yte = labels(test_seed)
        Xte = numeric(build(sd, pr, mode)).reindex(columns=Xtr.columns)
        m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1, random_state=0).fit(Xtr, ytr)
        auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
        best, who = 0.5, None
        for c in Xte.columns:
            v = Xte[c].fillna(Xte[c].median())
            if v.std() == 0 or v.isna().all(): continue
            a = roc_auc_score(yte, v); a = max(a, 1 - a)
            if a > best: best, who = a, c
        rows.append(dict(режим=mode, тест=test_seed, n=len(pr), признаков=Xte.shape[1],
                         AUC=round(auc, 4), макс_AUC_признака=round(best, 3), признак=who))
        print(f"{mode:16s} {test_seed} n={len(pr):5d} d={Xte.shape[1]:3d} AUC={auc:.4f} "
              f"проверка={best:.3f} ({time.time()-t0:.0f}s)", flush=True)

R = pd.DataFrame(rows)
base = R[R.режим == "с отсечкой"].set_index("тест").AUC
R["завышение"] = R.apply(lambda r: (r.AUC - base.loc[r.тест]) * 100, axis=1)
R.to_csv("/home/claude/demo/ft_scene.csv", index=False)
print("\nЗАВЫШЕНИЕ, п.п.")
print(R.pivot_table(index="режим", columns="тест", values="завышение").round(2).to_string())
print("\nМАКС AUC ОДНОГО ПРИЗНАКА")
print(R.pivot_table(index="режим", columns="тест", values="макс_AUC_признака").round(3).to_string())
