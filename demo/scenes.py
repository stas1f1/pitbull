"""Три сцены демонстрации PITFALL. Все числа считаются вживую при запуске."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/demo")
from pitfall import TemporalDB
D = "/home/claude/rel/"

# ══════════════════════════ данные ══════════════════════════

def olist_db():
    orders = pd.read_csv(D + "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                      "order_estimated_delivery_date"])
    orders = orders.dropna(subset=["order_purchase_timestamp"])
    items = pd.read_csv(D + "olist_order_items_dataset.csv")
    items["oi_id"] = items.order_id + "_" + items.order_item_id.astype(str)
    items = items.merge(orders[["order_id", "order_purchase_timestamp",
                                "order_delivered_customer_date", "order_estimated_delivery_date"]],
                        on="order_id")
    items["ts"] = items.order_purchase_timestamp
    items["deliv_ts"] = items.order_delivered_customer_date
    items["delay_days"] = (items.order_delivered_customer_date -
                           items.order_estimated_delivery_date).dt.days
    items["late"] = (items.delay_days > 0).astype(float)   # как в первой версии: недоставленный = «не опоздал»
    rev = pd.read_csv(D + "olist_order_reviews_dataset.csv",
                      usecols=["review_id", "order_id", "review_score", "review_creation_date"],
                      parse_dates=["review_creation_date"]).drop_duplicates("review_id")
    rev = rev[rev.order_id.isin(orders.order_id)].rename(columns={"review_creation_date": "review_ts"})
    prods = pd.read_csv(D + "olist_products_dataset.csv")[
        ["product_id", "product_category_name", "product_weight_g", "product_photos_qty"]]
    sell = pd.read_csv(D + "olist_sellers_dataset.csv")[["seller_id", "seller_state"]]
    pay = pd.read_csv(D + "olist_order_payments_dataset.csv",
                      usecols=["order_id", "payment_value", "payment_installments"])
    pay = pay.groupby("order_id", as_index=False).agg(pay_value=("payment_value", "sum"),
                                                      pay_inst=("payment_installments", "max"))

    # плоское представление для сцен 2-3 берём ровно тем же загрузчиком, что и rel/fix_ab.py,
    # чтобы числа демо и числа статьи были одними и теми же
    sys.path.insert(0, "/home/claude/rel")
    import pit_common
    flat = pit_common.load()

    return TemporalDB(
        tables={"orders": orders[["order_id", "order_purchase_timestamp"]],
                "items": items[["oi_id", "order_id", "product_id", "seller_id", "price",
                                "freight_value", "order_purchase_timestamp"]],
                "reviews": rev, "products": prods, "sellers": sell, "flat": flat},
        row_time={"orders": "order_purchase_timestamp", "items": "order_purchase_timestamp",
                  "reviews": "review_ts", "flat": "ts"},
        value_time={"flat": {"review_score": "review_ts", "late": "deliv_ts", "delay_days": "deliv_ts"}})

# ══════════════════════════ сцена 1: featuretools ══════════════════════════

AGG = ["count", "sum", "mean", "max", "min", "std"]

def _es(db):
    import featuretools as ft
    from woodwork.logical_types import Categorical, Double
    es = ft.EntitySet("olist")
    es = es.add_dataframe(dataframe_name="orders", dataframe=db.tables["orders"].copy(),
                          index="order_id", time_index="order_purchase_timestamp")
    es = es.add_dataframe(dataframe_name="items", dataframe=db.tables["items"].copy(),
                          index="oi_id", time_index="order_purchase_timestamp",
                          logical_types={"product_id": Categorical, "seller_id": Categorical})
    es = es.add_dataframe(dataframe_name="reviews", dataframe=db.tables["reviews"].copy(),
                          index="review_id", time_index="review_ts",
                          logical_types={"review_score": Double})
    es = es.add_dataframe(dataframe_name="products", dataframe=db.tables["products"].copy(),
                          index="product_id", logical_types={"product_category_name": Categorical})
    es = es.add_dataframe(dataframe_name="sellers", dataframe=db.tables["sellers"].copy(),
                          index="seller_id", logical_types={"seller_state": Categorical})
    es = es.add_relationship("orders", "order_id", "items", "order_id")
    es = es.add_relationship("orders", "order_id", "reviews", "order_id")
    es = es.add_relationship("products", "product_id", "items", "product_id")
    es = es.add_relationship("sellers", "seller_id", "items", "seller_id")
    return es

def ft_tutorial(db, seed, entities):
    """Как в туториале: dfs без cutoff_time. Это поведение библиотеки по умолчанию."""
    import featuretools as ft
    fm, _ = ft.dfs(entityset=_es(db), target_dataframe_name="products", agg_primitives=AGG,
                   trans_primitives=[], max_depth=2, verbose=0)
    return fm.reindex(entities).select_dtypes(include=[np.number])

def ft_cutoff(db, seed, entities):
    """То же самое плюс таблица моментов предсказания."""
    import featuretools as ft
    ct = pd.DataFrame({"product_id": entities, "time": seed})
    fm, _ = ft.dfs(entityset=_es(db), target_dataframe_name="products", agg_primitives=AGG,
                   trans_primitives=[], max_depth=2, cutoff_time=ct, cutoff_time_in_index=False,
                   verbose=0)
    return fm.reindex(entities).select_dtypes(include=[np.number])

def product_labels(db, seed, horizon=90, active=180, min_orders=2):
    ev = db.tables["flat"]; seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    cnt = act.groupby("product_id").order_id.nunique()
    pr = np.sort(cnt[cnt >= min_orders].index.values)
    fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
    return seed, pr, pd.Series(pd.Series(pr, index=pr).isin(fut.product_id.unique()).astype(int), index=pr)

# ══════════════════════ сцены 2-3: наш собственный эталон ══════════════════════

AGGS = {"price": ["count", "sum", "mean", "max"], "freight_value": ["mean"],
        "review_score": ["mean", "min"], "pay_value": ["sum", "mean"], "pay_inst": ["max"],
        "late": ["mean"], "delay_days": ["mean"]}

def _seller_feats(h, seed, sellers):
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    f = g.agg(AGGS); f.columns = ["_".join(c) for c in f.columns]
    f["n_orders"] = g.order_id.nunique()
    f["n_products"] = g.product_id.nunique()
    f["days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    f["days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
    f["span_days"] = f.days_since_first - f.days_since_last
    f["orders_per_day"] = f.n_orders / f.span_days.clip(lower=1)
    return f.reindex(sellers)

def seller_v1(db, seed, sellers):
    """Наш первый эталон. Фильтр по времени ЗАКАЗА, колонки строки берутся целиком."""
    ev = db.tables["flat"]
    return _seller_feats(ev[ev.ts <= seed], seed, sellers)

def seller_v2(db, seed, sellers):
    """Исправленный эталон: у отзыва и факта доставки своя метка доступности."""
    ev = db.tables["flat"].copy()
    ev.loc[~(ev.review_ts <= seed), "review_score"] = np.nan
    ev.loc[~(ev.deliv_ts <= seed), ["late", "delay_days"]] = np.nan
    return _seller_feats(ev[ev.ts <= seed], seed, sellers)

def seller_quality_labels(db, seed, horizon=90, active=180):
    ev = db.tables["flat"]; seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    sellers = np.sort(act.seller_id.unique())
    fr = ev[(ev.review_ts > seed) & (ev.review_ts <= seed + pd.Timedelta(days=horizon))]
    fr = fr.drop_duplicates("order_id").dropna(subset=["review_score"])
    fr = fr.groupby("seller_id").review_score.agg(["mean", "count"])
    fr = fr[fr["count"] >= 3]
    sellers = np.sort([s for s in sellers if s in fr.index])
    return seed, sellers, (fr.loc[sellers, "mean"] < 4.0).astype(int)
