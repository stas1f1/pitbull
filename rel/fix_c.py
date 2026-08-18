"""Задача C, пересчёт с корректным отношением доступности. См. pit_common.py."""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import sys, warnings, numpy as np, pandas as pd
sys.path.insert(0, _ROOT + "/rel")
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
from pit_common import load, visible, D
warnings.filterwarnings("ignore")

ev = load()
TMAX = ev.ts.max()
prod_seller = ev.groupby("product_id").seller_id.agg(lambda s: s.mode().iloc[0])

OWN = {"price": ["count", "mean", "max"], "freight_value": ["mean"],
       "review_score": ["mean", "min"], "late": ["mean"]}
NBR = {"price": ["count", "sum", "mean"], "review_score": ["mean", "min"], "late": ["mean"]}

def own_features(seed, prods, row_cut, avail_cut, pit):
    h = visible(ev, row_cut, avail_cut, pit); h = h[h.product_id.isin(prods)]
    g = h.groupby("product_id")
    f = g.agg(OWN); f.columns = ["own_" + "_".join(c) for c in f.columns]
    f["own_n_orders"] = g.order_id.nunique()
    f["own_days_since_last"] = (seed - g.ts.max()).dt.total_seconds() / 86400
    f["own_days_since_first"] = (seed - g.ts.min()).dt.total_seconds() / 86400
    return f.reindex(prods)

def nbr_features(seed, prods, row_cut, avail_cut, pit):
    h = visible(ev, row_cut, avail_cut, pit)
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

SH = lambda d: (lambda s: s + pd.Timedelta(days=d))
ID = lambda s: s
# режим -> (own: row,avail,pit) , (nbr: row,avail,pit)
MODES = {
    "корректно (PIT, обе группы)":        ((ID, ID, True),      (ID, ID, True)),
    "прежний эталон (отзыв+доставка)":    ((ID, ID, False),     (ID, ID, False)),
    "утечка только в своей истории":      ((SH(60), SH(60), True), (ID, ID, True)),
    "утечка только через соединение":     ((ID, ID, True),      (SH(60), SH(60), True)),
    "утечка по доступности, только nbr":  ((ID, ID, True),      (ID, ID, False)),
    "утечка в обеих группах":             ((SH(60), SH(60), True), (SH(60), SH(60), True)),
    "отсечки нет нигде":                  ((lambda s: TMAX, lambda s: TMAX, True), (lambda s: TMAX, lambda s: TMAX, True)),
}
ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]

rows = []
for test_seed in TESTS:
    tr_seeds = [s for s in ALL_SEEDS if s < test_seed]
    for mode, (o, n) in MODES.items():
        Xtr, ytr = [], []
        for s in tr_seeds:
            sd, pr, y = labels(s)
            if len(pr) < 50 or y.nunique() < 2: continue
            Xtr.append(pd.concat([own_features(sd, pr, o[0](sd), o[1](sd), o[2]),
                                  nbr_features(sd, pr, n[0](sd), n[1](sd), n[2])], axis=1))
            ytr.append(y)
        if not Xtr: continue
        Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
        sd, pr, yte = labels(test_seed)
        Xte = pd.concat([own_features(sd, pr, o[0](sd), o[1](sd), o[2]),
                         nbr_features(sd, pr, n[0](sd), n[1](sd), n[2])], axis=1)
        m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1, random_state=0).fit(Xtr, ytr)
        auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
        best, who = 0.5, None
        for c in Xte.columns:
            v = Xte[c].fillna(Xte[c].median())
            if v.std() == 0: continue
            a = roc_auc_score(yte, v); a = max(a, 1 - a)
            if a > best: best, who = a, c
        rows.append(dict(тест=test_seed, режим=mode, n=len(yte), доля_1=round(yte.mean(), 3),
                         AUC=round(auc, 6), макс_AUC_признака=round(best, 3), признак=who))
        print(f"{test_seed} {mode:34s} n={len(yte):5d} AUC={auc:.4f} проверка={best:.3f}", flush=True)

R = pd.DataFrame(rows)
base = R[R.режим == "корректно (PIT, обе группы)"].set_index("тест").AUC
R["завышение"] = R.apply(lambda r: (r.AUC - base.loc[r.тест]) * 100, axis=1)
R.to_csv(_HERE + "/fix_c.csv", index=False)
print("\n" + "=" * 92); print("ЗАДАЧА C: ЗАВЫШЕНИЕ AUC, п.п."); print("=" * 92)
print(R.pivot_table(index="режим", columns="тест", values="завышение").round(2).to_string())
print("\nБазовое качество (PIT):", R[R.режим == "корректно (PIT, обе группы)"].AUC.round(3).tolist())
print("\n" + "=" * 92); print("МАКС AUC ОДНОГО ПРИЗНАКА"); print("=" * 92)
print(R.pivot_table(index="режим", columns="тест", values="макс_AUC_признака").round(3).to_string())
