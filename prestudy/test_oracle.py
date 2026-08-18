"""
Валидация оракула на эталонах из rel/ (требование §11: корректный генератор проходит,
утёкший падает). Без этого остальное бессмысленно.

Отдельно проверяем режим «утечка только через соединение» — тот самый, на котором
промышленная одномерная проверка не меняет значение ни на тысячную (rel/RESULTS.md, задача C2).
Оракул обязан его поймать.
"""
import warnings
import numpy as np, pandas as pd
from oracle import is_pit_correct, truncate, TIME_COLS

warnings.filterwarnings("ignore")
D = "p1_repro/"

orders = pd.read_csv(D + "olist_orders_dataset.csv",
                     parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                  "order_estimated_delivery_date"])
items = pd.read_csv(D + "olist_order_items_dataset.csv")
revs = pd.read_csv(D + "olist_order_reviews_dataset.csv", parse_dates=["review_creation_date"])
pays = pd.read_csv(D + "olist_order_payments_dataset.csv")

orders = orders.dropna(subset=["order_purchase_timestamp"])
ots = orders.set_index("order_id").order_purchase_timestamp
items = items.copy(); items["ts"] = items.order_id.map(ots); items = items.dropna(subset=["ts"])
pays = pays.copy(); pays["ts"] = pays.order_id.map(ots); pays = pays.dropna(subset=["ts"])

DB = {"orders": orders, "order_items": items, "reviews": revs, "payments": pays}
TMAX = items.ts.max()

# основной продавец товара — фиксируется один раз, без временной информации (как в leak_multi3)
PROD_SELLER = items.groupby("product_id").seller_id.agg(lambda s: s.mode().iloc[0])


def _ev(db):
    rv = db["reviews"].groupby("order_id", as_index=False).review_score.mean()
    e = (db["order_items"].merge(db["orders"][["order_id", "order_status"]], on="order_id")
                          .merge(rv, on="order_id", how="left"))
    e["canceled"] = (e.order_status == "canceled").astype(float)
    return e


def make_own(shift_days=None, no_cutoff=False):
    """Признаки по собственной истории товара."""
    def prog(db, prods, seed):
        seed = pd.Timestamp(seed)
        cut = TMAX if no_cutoff else (seed if shift_days is None else seed + pd.Timedelta(days=shift_days))
        e = _ev(db)
        h = e[(e.ts <= cut) & (e.product_id.isin(prods))]
        g = h.groupby("product_id")
        f = pd.DataFrame({
            "own_price_count": g.price.count(), "own_price_mean": g.price.mean(),
            "own_review_mean": g.review_score.mean(), "own_canceled_mean": g.canceled.mean(),
            "own_days_since_last": (seed - g.ts.max()).dt.total_seconds() / 86400,
        })
        return f.reindex(prods)
    return prog


def make_nbr(shift_days=None, no_cutoff=False):
    """Агрегаты по всей истории ПРОДАВЦА — путь соединения товар -> продавец."""
    def prog(db, prods, seed):
        seed = pd.Timestamp(seed)
        cut = TMAX if no_cutoff else (seed if shift_days is None else seed + pd.Timedelta(days=shift_days))
        e = _ev(db)
        h = e[e.ts <= cut]
        g = h.groupby("seller_id")
        s = pd.DataFrame({
            "nbr_price_count": g.price.count(), "nbr_price_sum": g.price.sum(),
            "nbr_review_mean": g.review_score.mean(), "nbr_canceled_mean": g.canceled.mean(),
            "nbr_days_since_last": (seed - g.ts.max()).dt.total_seconds() / 86400,
        })
        sel = PROD_SELLER.reindex(prods)
        out = s.reindex(sel.values); out.index = prods
        return out
    return prog


def combine(own, nbr):
    def prog(db, prods, seed):
        return pd.concat([own(db, prods, seed), nbr(db, prods, seed)], axis=1)
    return prog


def _ev_review_fixed(db, seed):
    """Отзыв учитывается, только если НАПИСАН до момента предсказания."""
    r = db["reviews"].dropna(subset=["review_creation_date"])
    r = r[r.review_creation_date <= pd.Timestamp(seed)]
    rv = r.groupby("order_id", as_index=False).review_score.mean()
    e = (db["order_items"].merge(db["orders"][["order_id", "order_status"]], on="order_id")
                          .merge(rv, on="order_id", how="left"))
    e["canceled"] = (e.order_status == "canceled").astype(float)
    return e


def make_own_fixed():
    def prog(db, prods, seed):
        seed = pd.Timestamp(seed); e = _ev_review_fixed(db, seed)
        h = e[(e.ts <= seed) & (e.product_id.isin(prods))]; g = h.groupby("product_id")
        return pd.DataFrame({
            "own_price_count": g.price.count(), "own_price_mean": g.price.mean(),
            "own_review_mean": g.review_score.mean(), "own_canceled_mean": g.canceled.mean(),
            "own_days_since_last": (seed - g.ts.max()).dt.total_seconds() / 86400,
        }).reindex(prods)
    return prog


def make_nbr_fixed():
    def prog(db, prods, seed):
        seed = pd.Timestamp(seed); e = _ev_review_fixed(db, seed)
        h = e[e.ts <= seed]; g = h.groupby("seller_id")
        s = pd.DataFrame({
            "nbr_price_count": g.price.count(), "nbr_price_sum": g.price.sum(),
            "nbr_review_mean": g.review_score.mean(), "nbr_canceled_mean": g.canceled.mean(),
            "nbr_days_since_last": (seed - g.ts.max()).dt.total_seconds() / 86400,
        })
        sel = PROD_SELLER.reindex(prods); out = s.reindex(sel.values); out.index = prods
        return out
    return prog


ETALONS = {
    # эталон «чисто»: отзыв фильтруется по дате НАПИСАНИЯ, а не по дате заказа
    "корректно (отзыв по дате написания)": (combine(make_own_fixed(), make_nbr_fixed()),        True),
    # исходный эталон из rel/: отзыв приджойнен по order_id и отфильтрован по времени ЗАКАЗА.
    # 5% отзывов по заказам до момента написаны ПОСЛЕ него -> настоящая утечка через соединение.
    "исходный «корректно» из rel/":    (combine(make_own(), make_nbr()),                       False),
    "утечка только в своей истории":   (combine(make_own(shift_days=60), make_nbr()),          False),
    "утечка ТОЛЬКО через соединение":  (combine(make_own(), make_nbr(shift_days=60)),          False),
    "утечка в обеих группах":          (combine(make_own(shift_days=60), make_nbr(60)),        False),
    "отсечки нет нигде":               (combine(make_own(no_cutoff=True), make_nbr(no_cutoff=True)), False),
}

SEEDS = ["2018-01-01", "2018-04-01", "2018-07-01"]


def prods_at(seed, active=180, min_orders=2):
    seed = pd.Timestamp(seed)
    e = _ev(DB)
    act = e[(e.ts > seed - pd.Timedelta(days=active)) & (e.ts <= seed)]
    cnt = act.groupby("product_id").order_id.nunique()
    return np.sort(cnt[cnt >= min_orders].index.values)


if __name__ == "__main__":
    print("=" * 84)
    print("ВАЛИДАЦИЯ ОРАКУЛА НА ЭТАЛОНАХ (дифференциальное исполнение)")
    print("=" * 84)
    print(f"{'эталон':36s}{'ожидаем':10s}{'момент':12s}{'вердикт':10s}{'разошлось колонок'}")
    all_ok = True
    for name, (prog, expect_pass) in ETALONS.items():
        for seed in SEEDS:
            prods = prods_at(seed)
            ok, det = is_pit_correct(prog, DB, prods, seed, return_detail=True)
            good = (ok == expect_pass)
            all_ok &= good
            nd = det.get("n_differing", "-") if not ok else "-"
            tot = det.get("n_total", "-") if not ok else "-"
            mark = "" if good else "   <<< НЕ СОВПАЛО С ОЖИДАНИЕМ"
            print(f"{name[:35]:36s}{'ЧИСТО' if expect_pass else 'НАРУШЕНИЕ':10s}{seed:12s}"
                  f"{'ЧИСТО' if ok else 'НАРУШЕНИЕ':10s}{nd}/{tot}{mark}")
    print()
    print("ИТОГ:", "оракул работает — все эталоны размечены верно" if all_ok
          else "ОРАКУЛ НЕИСПРАВЕН, дальше идти нельзя")
