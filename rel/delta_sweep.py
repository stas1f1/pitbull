"""Задачи A и B, пересчёт с корректным отношением доступности. См. pit_common.py."""
import sys, warnings, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/rel")
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
from pit_common import load, visible, D
warnings.filterwarnings("ignore")

ev = load()
TMAX = ev.ts.max()

AGGS = {"price": ["count", "sum", "mean", "max"], "freight_value": ["mean"],
        "review_score": ["mean", "min"], "pay_value": ["sum", "mean"], "pay_inst": ["max"],
        "late": ["mean"], "delay_days": ["mean"]}   # canceled исключён: метки доступности нет

def features(seed, sellers, row_cut, avail_cut, pit):
    h = visible(ev, row_cut, avail_cut, pit)
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

def labels(seed, task, horizon=90, active=180):
    seed = pd.Timestamp(seed)
    act = ev[(ev.ts > seed - pd.Timedelta(days=active)) & (ev.ts <= seed)]
    sellers = np.sort(act.seller_id.unique())
    if task == "A":
        fut = ev[(ev.ts > seed) & (ev.ts <= seed + pd.Timedelta(days=horizon))]
        y = pd.Series(sellers, index=sellers).isin(fut.seller_id.unique()).astype(int)
        return seed, sellers, y
    # B: качество. Окно метки определено по ВРЕМЕНИ ОТЗЫВА, а не по времени заказа —
    # так метка и признаки не пересекаются по построению.
    fr = ev[(ev.review_ts > seed) & (ev.review_ts <= seed + pd.Timedelta(days=horizon))]
    fr = fr.drop_duplicates("order_id").dropna(subset=["review_score"])
    fr = fr.groupby("seller_id").review_score.agg(["mean", "count"])
    fr = fr[fr["count"] >= 3]
    sellers = np.sort([s for s in sellers if s in fr.index])
    y = (fr.loc[sellers, "mean"] < 4.0).astype(int)
    return seed, sellers, y

# режим -> (сдвиг отсечки строк, сдвиг отсечки доступности, применять ли PIT-маску)
DELTAS = [0, 5, 10, 15, 20, 30, 45, 60, 90]
MODES = {f"δ={d}": ((lambda d: (lambda s: s + pd.Timedelta(days=d)))(d), (lambda d: (lambda s: s + pd.Timedelta(days=d)))(d), True) for d in DELTAS}
_OLD = {}
ALL_SEEDS = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01", "2018-07-01"]
TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]

rows, probes = [], []
for task in ["A", "B"]:
    for test_seed in TESTS:
        tr_seeds = [s for s in ALL_SEEDS if s < test_seed]
        for mode, (rc, ac, pit) in MODES.items():
            Xtr, ytr = [], []
            for s in tr_seeds:
                sd, sel, y = labels(s, task)
                if len(sel) < 30 or y.nunique() < 2: continue
                Xtr.append(features(sd, sel, rc(sd), ac(sd), pit)); ytr.append(y)
            if not Xtr: continue
            Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
            sd, sel, yte = labels(test_seed, task)
            if len(sel) < 30 or yte.nunique() < 2: continue
            Xte = features(sd, sel, rc(sd), ac(sd), pit)
            m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1, random_state=0).fit(Xtr, ytr)
            auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
            rows.append(dict(задача=task, тест=test_seed, режим=mode, n_test=len(yte),
                             доля_1=round(yte.mean(), 3), AUC=round(auc, 6)))
            best, who = 0.5, None
            for c in Xte.columns:
                v = Xte[c].fillna(Xte[c].median())
                if v.std() == 0: continue
                a = roc_auc_score(yte, v); a = max(a, 1 - a)
                if a > best: best, who = a, c
            probes.append(dict(задача=task, тест=test_seed, режим=mode,
                               макс_AUC_признака=round(best, 3), признак=who))
            print(f"{task} {test_seed} {mode:34s} n={len(yte):5d} AUC={auc:.4f} проверка={best:.3f}", flush=True)

R = pd.DataFrame(rows); P = pd.DataFrame(probes)
base = R[R.режим == "δ=0"].set_index(["задача", "тест"]).AUC
R["завышение"] = R.apply(lambda r: (r.AUC - base.loc[(r.задача, r.тест)]) * 100, axis=1)
R.to_csv(D + "delta_auc.csv", index=False); P.to_csv(D + "delta_probe.csv", index=False)

print("\n" + "=" * 92); print("ЗАВЫШЕНИЕ AUC ОТНОСИТЕЛЬНО КОРРЕКТНОЙ PIT-ОТСЕЧКИ (п.п.)"); print("=" * 92)
print(R.pivot_table(index=["задача", "режим"], columns="тест", values="завышение").round(2).to_string())
print("\nБазовое качество при корректной PIT-отсечке:")
print(R[R.режим == "δ=0"].pivot_table(index="задача", columns="тест", values="AUC").round(3).to_string())
print("\n" + "=" * 92); print("МАКС AUC ОДНОГО ПРИЗНАКА (промышленная проверка)"); print("=" * 92)
print(P.pivot_table(index=["задача", "режим"], columns="тест", values="макс_AUC_признака").round(3).to_string())
