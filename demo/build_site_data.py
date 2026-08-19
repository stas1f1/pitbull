#!/usr/bin/env python3
"""Precompute everything the interactive page needs → site_data.json.

Runs the real programs on the real database (≈2 min). The page itself is static and
works offline; this script is the only place numbers come from.
"""
import os as _os, sys, json, time, warnings, textwrap, inspect
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import scenes
from pitfall import differential_check, locate, univariate_probe, DATAROBOT, H2O

T = pd.Timestamp("2018-04-01")
SEEDS = ["2018-01-01", "2018-04-01", "2018-07-01"]
db = scenes.olist_db()
ev = db.tables["flat"]
out = {}

def jl(x):
    if isinstance(x, (np.floating, float)):
        return None if pd.isna(x) else round(float(x), 4)
    if isinstance(x, (np.integer, int)): return int(x)
    if isinstance(x, pd.Timestamp): return None if pd.isna(x) else x.strftime("%Y-%m-%d")
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, (str, bool, list, dict, tuple)) or x is None: return x
    return str(x)

# ── 1. one seller's timeline (the explainer) ─────────────────────────────────
S = "0d85bbda9889ce1f7e63778d24f346eb"
h = ev[(ev.seller_id == S) & (ev.ts > T - pd.Timedelta(days=100)) & (ev.ts <= T + pd.Timedelta(days=45))]
h = h.drop_duplicates("order_id").sort_values("ts")
out["timeline"] = dict(
    seller=S[:8], t=T.strftime("%Y-%m-%d"),
    orders=[dict(order=r.order_id[:6], ts=jl(r.ts), review_ts=jl(r.review_ts), score=jl(r.review_score),
                 deliv_ts=jl(r.deliv_ts), late=jl(r.late), price=jl(r.price)) for r in h.itertuples()])

# ── 2. the four scene programs: verdicts at 3 seeds + sample rows ─────────────
def sample_diff(program, seed, entities, pick, cols):
    full = program(db, seed, entities); tr = program(db.truncate(seed), seed, entities)
    rows = []
    for e in pick:
        rows.append(dict(entity=str(e)[:8],
                         full={c: jl(full.loc[e, c]) for c in cols},
                         trunc={c: jl(tr.loc[e, c]) for c in cols}))
    return rows

def probes(program, labeler, seeds):
    r = []
    for s in seeds:
        sd, ent, y = labeler(db, s)
        X = program(db, sd, ent); a, who = univariate_probe(X, y)
        r.append(dict(seed=s, probe=round(float(a), 3), feature=str(who)))
    return r

progs = {}
sd, sellers, y = scenes.seller_quality_labels(db, T)
pick_s = [S] + [s for s in sellers if s != S][:5]
cols_s = ["n_orders", "price_mean", "review_score_mean", "review_score_min", "late_mean", "delay_days_mean", "days_since_last"]
for key, prog, title in [("seller_v1", scenes.seller_v1, "our reference code, first version"),
                         ("seller_v2", scenes.seller_v2, "the same code after the fix")]:
    ver = []
    for s in SEEDS:
        sd_, ent_, _ = scenes.seller_quality_labels(db, s)
        t0 = time.time(); v = differential_check(prog, db, sd_, ent_)
        ver.append(dict(seed=s, leak=v.leak, columns=v.columns, cells=v.cells, n=int(len(ent_)), seconds=round(time.time() - t0, 2)))
    src = inspect.getsource(prog)
    progs[key] = dict(title=title, verdicts=ver, source=src, cols=cols_s,
                      sample=sample_diff(prog, sd, sellers, pick_s, cols_s), entity="seller")

sdp, prods, yp = scenes.product_labels(db, T)
cols_p = ["COUNT(items)", "MEAN(items.price)", "SUM(items.price)", "MAX(items.freight_value)"]
pick_p = list(prods[:6])
for key, prog, title in [("ft_tutorial", scenes.ft_tutorial, "featuretools, no cutoff-time table"),
                         ("ft_cutoff", scenes.ft_cutoff, "featuretools with a cutoff-time table")]:
    ver = []
    for s in SEEDS:
        sd_, ent_, _ = scenes.product_labels(db, s)
        t0 = time.time(); v = differential_check(prog, db, sd_, ent_)
        ver.append(dict(seed=s, leak=v.leak, columns=v.columns, cells=v.cells, n=int(len(ent_)), seconds=round(time.time() - t0, 2)))
    src = inspect.getsource(prog)
    # pick products that actually diverge for the sample
    full = prog(db, sdp, prods); tr = prog(db.truncate(sdp), sdp, prods)
    diff = (full["COUNT(items)"].fillna(-1) != tr["COUNT(items)"].fillna(-1))
    pick = list(full.index[diff][:4]) + list(full.index[~diff][:2]) if diff.any() else pick_p
    progs[key] = dict(title=title, verdicts=ver, source=src, cols=cols_p,
                      sample=[dict(entity=str(e)[:8], full={c: jl(full.loc[e, c]) for c in cols_p},
                                   trunc={c: jl(tr.loc[e, c]) for c in cols_p}) for e in pick], entity="product")
out["programs"] = progs

# ── 3. AUC / probe / inflation per scene (from demo_results.json, already computed) ─
out["scenes"] = json.load(open(_HERE + "/demo_results.json"))

# ── 4. dose curve I(δ) and probe by δ ─────────────────────────────────────────
R = pd.read_csv(_ROOT + "/rel/delta_auc.csv"); P = pd.read_csv(_ROOT + "/rel/delta_probe.csv")
R["d"] = R.режим.str.replace("δ=", "").astype(int); P["d"] = P.режим.str.replace("δ=", "").astype(int)
M = R.merge(P.drop(columns=["d"]), on=["задача", "тест", "режим"])
out["dose"] = [dict(task=r.задача, seed=r.тест, d=int(r.d), auc=round(float(r.AUC), 4),
                    inflation=round(float(r.завышение), 2), probe=round(float(r.макс_AUC_признака), 3), feature=r.признак)
               for r in M.itertuples()]

# ── 5. blind scatter ─────────────────────────────────────────────────────────
C = pd.read_csv(_ROOT + "/rel/fix_c.csv"); ft = pd.read_csv(_HERE + "/ft_scene.csv")
pts = [dict(kind="shift", task=r.задача, seed=r.тест, d=int(r.d), probe=round(float(r.макс_AUC_признака), 3), infl=round(float(r.завышение), 2)) for r in M.itertuples()]
for r in C[C.режим == "утечка только через соединение"].itertuples():
    pts.append(dict(kind="join", task="C", seed=r.тест, probe=round(float(r.макс_AUC_признака), 3), infl=round(float(r.завышение), 2)))
for r in ft[ft.режим == "туториал"].itertuples():
    pts.append(dict(kind="ft", task="C", seed=r.тест, probe=round(float(r.макс_AUC_признака), 3), infl=round(float(r.завышение), 2)))
for s, p, i in zip(SEEDS, [.623, .687, .657], [3.09, 5.26, 3.78]):
    pts.append(dict(kind="ours", task="B", seed=s, probe=p, infl=i))
out["blind"] = dict(points=pts, datarobot=list(DATAROBOT), h2o=list(H2O))

# ── 6. LOCATOR ────────────────────────────────────────────────────────────────
out["channels"] = [list(c) for c in db.channels()]
out["locator"] = {}
for key, prog, lab in [("seller_v1", scenes.seller_v1, scenes.seller_quality_labels), ("ft_tutorial", scenes.ft_tutorial, scenes.product_labels)]:
    sd_, ent_, _ = lab(db, T)
    bl = locate(prog, db, sd_, ent_)
    out["locator"][key] = [dict(channel=list(b.channel), label=b.label, columns=b.columns, cells=b.cells) for b in bl]

# ── 7. the game: short feature functions, verdict computed here ───────────────
GAME_SRC = {}
def _reg(f): GAME_SRC[f.__name__] = f; return f

@_reg
def order_count(db, t, sellers):
    """How many orders did the seller receive before the seed time?"""
    h = db.tables["flat"]
    h = h[h.ts <= t]
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    return g.order_id.nunique().to_frame("n_orders").reindex(sellers)

@_reg
def average_review(db, t, sellers):
    """Average review score of the seller's orders placed before the seed time."""
    h = db.tables["flat"]
    h = h[h.ts <= t]
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    return g.review_score.mean().to_frame("review_mean").reindex(sellers)

@_reg
def average_review_known(db, t, sellers):
    """Average of the reviews that had been *written* by the seed time."""
    h = db.tables["flat"]
    h = h[(h.ts <= t) & (h.review_ts <= t)]
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    return g.review_score.mean().to_frame("review_mean").reindex(sellers)

@_reg
def late_share(db, t, sellers):
    """Share of the seller's orders (placed before t) that were delivered late."""
    h = db.tables["flat"]
    h = h[h.ts <= t]
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    return g.late.mean().to_frame("late_share").reindex(sellers)

@_reg
def price_zscore(db, t, sellers):
    """Seller's mean price, standardised by the mean and std of price over the whole table."""
    h = db.tables["flat"]
    mu, sd = h.price.mean(), h.price.std()          # over the whole table
    h = h[h.ts <= t]
    m = h[h.seller_id.isin(sellers)].groupby("seller_id").price.mean()
    return ((m - mu) / sd).to_frame("price_z").reindex(sellers)

@_reg
def days_since_last(db, t, sellers):
    """Days between the seller's last order before t and t."""
    h = db.tables["flat"]
    h = h[h.ts <= t]
    last = h[h.seller_id.isin(sellers)].groupby("seller_id").ts.max()
    days = (t - last).dt.total_seconds() / 86400
    return days.to_frame("days_since_last").reindex(sellers)

@_reg
def recent_orders(db, t, sellers):
    """Orders in the 30 days before the seed time."""
    h = db.tables["flat"]
    h = h[(h.ts <= t) & (h.ts > t - pd.Timedelta(days=30))]
    g = h[h.seller_id.isin(sellers)].groupby("seller_id")
    return g.order_id.nunique().to_frame("orders_30d").reindex(sellers)

@_reg
def delivered_count(db, t, sellers):
    """How many of the seller's orders have a delivery date."""
    h = db.tables["flat"]
    h = h[h.ts <= t]
    h = h[h.seller_id.isin(sellers)]
    n = h.deliv_ts.notna().groupby(h.seller_id).sum()
    return n.to_frame("n_delivered").reindex(sellers)

game = []
for name, f in GAME_SRC.items():
    v = differential_check(f, db, T, sellers)
    src = inspect.getsource(f)
    src = "\n".join(l for l in src.splitlines() if not l.startswith("@_reg"))
    game.append(dict(name=name, doc=f.__doc__, source=textwrap.dedent(src), leak=v.leak, columns=v.columns, cells=v.cells))
    print(name, v.label, v.columns, v.cells)
out["game"] = game

# ── 8. a few global facts ─────────────────────────────────────────────────────
o = ev.drop_duplicates("order_id")
lag = (o.review_ts - o.ts).dt.days.dropna()
dl = (o.deliv_ts - o.ts).dt.days.dropna()
out["facts"] = dict(n_items=int(len(ev)), n_orders=int(o.order_id.nunique()), n_sellers=int(ev.seller_id.nunique()),
                    n_products=int(ev.product_id.nunique()), review_lag_median=int(lag.median()), review_lag_p90=int(lag.quantile(.9)),
                    review_lag_max=int(lag.max()), deliv_lag_median=int(dl.median()), deliv_lag_max=int(dl.max()),
                    share_review_after=[round(float((( (ev.ts <= pd.Timestamp(s)) & (ev.review_ts > pd.Timestamp(s))).sum() / (ev.ts <= pd.Timestamp(s)).sum()) * 100), 2) for s in SEEDS])

# ── 8. за пределами Olist: вторая база и чужой код ───────────────────────────
# Читается из готовых выгрузок rel/out, а не считается заново: эти прогоны идут
# минуты-часы и требуют скачанных баз RelBench. Если выгрузок нет, блок
# опускается и страница просто не показывает последнюю секцию.
def _beyond():
    import glob
    R = _ROOT + "/rel/out/"
    b = {}

    # 8.1 одна и та же ошибка на единицу, оценённая дважды внутри одной базы
    fp = R + "f1_paired.csv"
    if _os.path.isfile(fp):
        P = pd.read_csv(fp)
        P = P[P.contrast == "naive - pit"]
        b["granularity"] = [dict(task=("day" if "day" in r.task else "second"),
                                 seed=r.test_seed, d=round(float(r.delta_pp), 2),
                                 lo=round(float(r.lo_pp), 2), hi=round(float(r.hi_pp), 2))
                            for r in P.itertuples()]

    # 8.2 корпус опубликованного экспертного SQL: вердикт на файл
    # порядок по времени записи: если один и тот же файл прогонялся дважды,
    # берётся последний прогон, а не оба сразу (на этом уже один раз обожглись)
    files = sorted(glob.glob(R + "sql_oracle_*.csv"), key=_os.path.getmtime)
    if files:
        A = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        A = A[A.phase == "main"].drop_duplicates(subset=["file", "seed"], keep="last")
        rows = []
        for name, g in A.groupby("file"):
            v = ("ERROR" if (g.verdict == "ERROR").all()
                 else ("LEAK" if (g.verdict == "LEAK").any() else "CLEAN"))
            rows.append(dict(file=name.replace(".sql", ""), db=str(g.dataset.iloc[0]),
                             verdict=v, seeds=int(len(g)),
                             leaks=int((g.verdict == "LEAK").sum()),
                             cols=sorted({c for s_ in g["columns"] if isinstance(s_, str)
                                          for c in s_.split(";")})[:6]))
        b["corpus"] = sorted(rows, key=lambda r: (r["db"], r["file"]))

    # 8.3 rel-event: доля строк меток, ссылающихся на пользователя из будущего
    ev_dir = _os.environ.get("PITFALL_EXT_DATA", _ROOT + "/PITFALL_ext_data")
    up = ev_dir + "/rel-event/db/users.parquet"
    lab = sorted(glob.glob(ev_dir + "/tasks/rel-event__user-attendance/user-attendance/*.parquet"))
    if _os.path.isfile(up) and lab:
        import duckdb
        con = duckdb.connect(); con.execute("SET TimeZone='UTC'")
        fl = ", ".join("'" + x + "'" for x in lab)
        q = con.execute(f'''SELECT e."timestamp"::DATE d, COUNT(*) n,
              SUM(CASE WHEN u.joinedAt > e."timestamp" THEN 1 ELSE 0 END) fut
              FROM read_parquet([{fl}], union_by_name=true) e
              LEFT JOIN read_parquet('{up}') u ON e."user" = u.user_id
              GROUP BY 1 ORDER BY 1''').fetch_df()
        con.close()
        b["event"] = [dict(date=str(r.d), n=int(r.n), fut=int(r.fut),
                           share=round(100.0 * r.fut / r.n, 1)) for r in q.itertuples()]
        b["event_test_seed"] = str(q.d.iloc[-1])
    return b

try:
    bey = _beyond()
    if bey:
        out["beyond"] = bey
        print("beyond:", {k: (len(v) if hasattr(v, "__len__") else v) for k, v in bey.items()})
except Exception as e:
    print("beyond пропущен:", type(e).__name__, e)

json.dump(out, open(_HERE + "/site_data.json", "w"), ensure_ascii=False, indent=0, default=jl)
print("ok", _HERE + "/site_data.json")
