"""
Эталонный адаптер: Olist. Опубликованные числа — rel/fix_ab_auc.csv, rel/fix_c.csv.

Этот файл ничего не пересчитывает заново: он переносит в общий слой ровно ту же
загрузку (pit_common.py), те же агрегаты, те же метки и те же моменты, что и в
fix_ab.py / fix_c.py. Проверка на совпадение — rel/verify_olist.py.
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REL = _os.path.dirname(_HERE)
if _REL not in _sys.path:
    _sys.path.insert(0, _REL)

import numpy as np, pandas as pd
from dsapi import DatasetAdapter, TaskSpec, TemporalDB
from pit_common import load as _load, AVAIL as _AVAIL

ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]

# задачи A и B: агрегаты по продавцу (canceled исключён — метки доступности нет)
AGGS = {"price": ["count", "sum", "mean", "max"], "freight_value": ["mean"],
        "review_score": ["mean", "min"], "pay_value": ["sum", "mean"], "pay_inst": ["max"],
        "late": ["mean"], "delay_days": ["mean"]}
# задача C
OWN = {"price": ["count", "mean", "max"], "freight_value": ["mean"],
       "review_score": ["mean", "min"], "late": ["mean"]}
NBR = {"price": ["count", "sum", "mean"], "review_score": ["mean", "min"], "late": ["mean"]}


class Adapter(DatasetAdapter):
    name = "olist"
    ts_col = "ts"
    AVAIL = _AVAIL
    UNCHECKABLE = ["orders.order_status (canceled): изменяемое поле без истории"]
    granularity = "second"

    def load(self):
        return _load()

    def __init__(self):
        super().__init__()
        self.prod_seller = self.ev.groupby("product_id").seller_id.agg(lambda s: s.mode().iloc[0])

    # ── признаки ────────────────────────────────────────────────────────────
    def _seller_feats(self, seed, sellers, shift, pit):
        row_cut = avail_cut = self.cut(seed, shift)
        h = self.visible(row_cut, avail_cut, pit)
        h = h[h.seller_id.isin(sellers)]
        g = h.groupby("seller_id")
        f = g.agg(AGGS); f.columns = ["_".join(c) for c in f.columns]
        f["n_orders"] = g.order_id.nunique()
        f["n_products"] = g.product_id.nunique()
        f["days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
        f["days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
        f["span_days"] = f.days_since_first - f.days_since_last
        f["orders_per_day"] = f.n_orders / f.span_days.clip(lower=1)
        return f.reindex(sellers)

    def _prod_own(self, seed, prods, shift, pit):
        row_cut = avail_cut = self.cut(seed, shift)
        h = self.visible(row_cut, avail_cut, pit); h = h[h.product_id.isin(prods)]
        g = h.groupby("product_id")
        f = g.agg(OWN); f.columns = ["own_" + "_".join(c) for c in f.columns]
        f["own_n_orders"] = g.order_id.nunique()
        f["own_days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
        f["own_days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
        return f.reindex(prods)

    def _prod_nbr(self, seed, prods, shift, pit):
        row_cut = avail_cut = self.cut(seed, shift)
        h = self.visible(row_cut, avail_cut, pit)
        g = h.groupby("seller_id")
        s = g.agg(NBR); s.columns = ["nbr_" + "_".join(c) for c in s.columns]
        s["nbr_n_products"] = g.product_id.nunique()
        s["nbr_n_orders"] = g.order_id.nunique()
        s["nbr_days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
        sel = self.prod_seller.reindex(prods)
        out = s.reindex(sel.values); out.index = prods
        return out

    # ── метки ───────────────────────────────────────────────────────────────
    def _label_ab(self, seed, task, horizon=90, active=180):
        ev = self.ev
        seed = pd.Timestamp(seed)
        act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
        sellers = np.sort(act.seller_id.unique())
        if task == "A":
            fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
            return sellers, pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
        # B: окно метки определено по времени ОТЗЫВА — метка и признаки не пересекаются
        fr = ev[(ev.review_ts > seed) & (ev.review_ts <= seed + pd.Timedelta(days=horizon))]
        fr = fr.drop_duplicates("order_id").dropna(subset=["review_score"])
        fr = fr.groupby("seller_id").review_score.agg(["mean", "count"])
        fr = fr[fr["count"] >= 3]
        sellers = np.sort([s for s in sellers if s in fr.index])
        return sellers, (fr.loc[sellers, "mean"] < 4.0).astype(int)

    def _label_c(self, seed, horizon=90, active=180, min_orders=2):
        ev = self.ev
        seed = pd.Timestamp(seed)
        act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
        cnt = act.groupby("product_id").order_id.nunique()
        prods = np.sort(cnt[cnt >= min_orders].index.values)
        fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
        return prods, pd.Series(prods, index=prods).isin(fut.product_id.unique()).astype(int)

    def tasks(self):
        return [
            TaskSpec("A_seller_activity", lambda s: self._label_ab(s, "A"),
                     {"own": self._seller_feats}, ALL_SEEDS, TESTS, 30,
                     "активность продавца в ближайшие 90 дней"),
            TaskSpec("B_seller_quality", lambda s: self._label_ab(s, "B"),
                     {"own": self._seller_feats}, ALL_SEEDS, TESTS, 30,
                     "средняя оценка продавца < 4.0 по отзывам ближайших 90 дней"),
            TaskSpec("C_product_demand", self._label_c,
                     {"own": self._prod_own, "nbr": self._prod_nbr}, ALL_SEEDS, TESTS, 50,
                     "будет ли заказан товар в ближайшие 90 дней"),
        ]

    # ── дифференциальное исполнение ─────────────────────────────────────────
    ORACLE_AGGS = {"price": ["count", "mean"], "review_score": ["mean", "min"], "late": ["mean"]}

    def temporal_db(self):
        return TemporalDB(tables={"flat": self.ev},
                          row_time={"flat": "ts"},
                          value_time={"flat": {"review_score": "review_ts",
                                               "late": "deliv_ts", "delay_days": "deliv_ts"}})

    def programs(self):
        A = self.ORACLE_AGGS

        def naive(db, seed, ents):
            h = db.tables["flat"]
            h = h[(h.ts <= seed) & (h.seller_id.isin(ents))]
            g = h.groupby("seller_id"); f = g.agg(A); f.columns = ["_".join(c) for c in f.columns]
            return f.reindex(ents)

        def pit(db, seed, ents):
            h = db.tables["flat"]
            h = h[(h.ts <= seed) & (h.seller_id.isin(ents))].copy()
            for col, tcol in self.AVAIL.items():
                h.loc[~(h[tcol] <= seed), col] = np.nan
            g = h.groupby("seller_id"); f = g.agg(A); f.columns = ["_".join(c) for c in f.columns]
            return f.reindex(ents)

        return {"naive": naive, "pit": pit}

    def oracle_entities(self, seed):
        s = pd.Timestamp(seed)
        return np.sort(self.ev[(self.ev.ts > s - pd.Timedelta(days=180)) & (self.ev.ts <= s)].seller_id.unique())

    ORACLE_SEEDS = TESTS
