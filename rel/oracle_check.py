"""
Дифференциальное исполнение на нашем собственном эталоне.
Программа признаков запускается дважды: на полной базе и на базе, физически
усечённой на момент предсказания. Любое расхождение — доказательство нарушения.
"""
import sys, warnings, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/rel")
from pit_common import load, AVAIL, D
warnings.filterwarnings("ignore")

ev = load()

def truncate(ev, seed):
    """Физическое усечение базы: ничего с меткой позже seed не существует."""
    h = ev[ev.ts <= seed].copy()
    for col, tcol in AVAIL.items():
        h.loc[~(h[tcol] <= seed), col] = np.nan
    for tcol in set(AVAIL.values()):
        h.loc[~(h[tcol] <= seed), tcol] = pd.NaT
    return h

AGGS = {"price": ["count", "mean"], "review_score": ["mean", "min"], "late": ["mean"]}

def prog_old(db, seed, sellers):
    """ПРЕЖНЯЯ реализация: фильтр только по времени заказа."""
    h = db[(db.ts <= seed) & (db.seller_id.isin(sellers))]
    g = h.groupby("seller_id"); f = g.agg(AGGS); f.columns = ["_".join(c) for c in f.columns]
    return f.reindex(sellers)

def prog_fixed(db, seed, sellers):
    """ИСПРАВЛЕННАЯ: у каждой колонки своя метка доступности."""
    h = db[(db.ts <= seed) & (db.seller_id.isin(sellers))].copy()
    for col, tcol in AVAIL.items():
        h.loc[~(h[tcol] <= seed), col] = np.nan
    g = h.groupby("seller_id"); f = g.agg(AGGS); f.columns = ["_".join(c) for c in f.columns]
    return f.reindex(sellers)

def frames_equal(a, b):
    if a is None and b is None: return True          # <- баг, найденный R3
    if a is None or b is None: return False
    if a.shape != b.shape or list(a.columns) != list(b.columns): return False
    return a.fillna(-987654321.0).round(9).equals(b.fillna(-987654321.0).round(9))

def diff_cols(a, b):
    return [c for c in a.columns
            if not a[c].fillna(-987654321.0).round(9).equals(b[c].fillna(-987654321.0).round(9))]

print(f"{'момент':12s} {'программа':10s} {'вердикт':8s}  расходящиеся колонки")
print("-" * 78)
for seed in ["2018-01-01", "2018-04-01", "2018-07-01"]:
    s = pd.Timestamp(seed)
    sellers = np.sort(ev[(ev.ts > s - pd.Timedelta(days=180)) & (ev.ts <= s)].seller_id.unique())
    tr = truncate(ev, s)
    for name, prog in [("прежняя", prog_old), ("исправл.", prog_fixed)]:
        full = prog(ev, s, sellers); trunc = prog(tr, s, sellers)
        ok = frames_equal(full, trunc)
        cols = [] if ok else diff_cols(full, trunc)
        nrows = 0 if ok else int(sum((full[c].fillna(-9e18) != trunc[c].fillna(-9e18)).sum() for c in cols))
        print(f"{seed:12s} {name:10s} {'ЧИСТО' if ok else 'УТЕЧКА':8s}  {', '.join(cols) if cols else '—'}"
              + (f"   ({nrows} расхождений в значениях)" if cols else ""))
