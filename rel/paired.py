"""
Парный бутстрэп разницы AUC: python3 paired.py <адаптер> [--pairs naive:pit,...]

Зачем отдельно от suite.py. Интервалы для AUC каждого режима по отдельности
широкие и перекрываются — на rel-f1 в тестовой ячейке около 1100 строк. Но нас
интересует не AUC каждого режима, а РАЗНИЦА между ними на ОДНИХ И ТЕХ ЖЕ
тестовых строках. Парная статистика убирает общую для обоих режимов долю шума,
и интервал получается в несколько раз уже.

Схема: обе модели обучаются один раз, предсказания снимаются на одном и том же
тесте, затем бутстрэп по строкам теста — на каждой выборке считаются оба AUC и
берётся их разность. Интервал перцентильный, seed фиксирован.
"""
import os as _os, sys as _sys, time, argparse, warnings
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
import adapters
from dsapi import build_modes, OUT

B = 2000


def fit_predict(Xtr, ytr, Xte, cols=None):
    Xtr = Xtr.select_dtypes(include=[np.number])
    Xte = Xte.select_dtypes(include=[np.number]).reindex(columns=Xtr.columns)
    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                       random_state=0, n_jobs=2).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def build(ad, task, mode, seed_str):
    seed = ad.to_seed(seed_str)
    ents, y = task.label(seed)
    if ents is None or len(ents) < task.min_entities or y.nunique() < 2:
        return None, None
    parts = [fn(seed, ents, *mode[g]) for g, fn in task.groups.items()]
    return pd.concat(parts, axis=1), y


def cell(ad, task, mode_name, mode, test_seed):
    tr = [s for s in task.train_seeds if s < test_seed]
    if task.max_train_seeds:
        tr = tr[-task.max_train_seeds:]
    Xs, ys = [], []
    for s in tr:
        X, y = build(ad, task, mode, s)
        if X is not None:
            Xs.append(X); ys.append(y)
    Xte, yte = build(ad, task, mode, test_seed)
    if not Xs or Xte is None:
        return None, None
    return fit_predict(pd.concat(Xs), pd.concat(ys), Xte), np.asarray(yte)


def paired(ad, task, a, b, test_seed, modes):
    pa, y = cell(ad, task, a, modes[a], test_seed)
    pb, y2 = cell(ad, task, b, modes[b], test_seed)
    if pa is None or pb is None:
        return None
    assert (y == y2).all(), "тестовые метки разошлись между режимами"
    d = roc_auc_score(y, pa) - roc_auc_score(y, pb)
    rng = np.random.default_rng(0)
    n, out = len(y), []
    for _ in range(B):
        i = rng.integers(0, n, n)
        if len(np.unique(y[i])) < 2:
            continue
        out.append(roc_auc_score(y[i], pa[i]) - roc_auc_score(y[i], pb[i]))
    out = np.array(out)
    return dict(dataset=ad.name, task=task.name, test_seed=test_seed, contrast=f"{a} - {b}",
                n_test=int(n), delta_pp=round(float(d) * 100, 3),
                lo_pp=round(float(np.percentile(out, 2.5)) * 100, 3),
                hi_pp=round(float(np.percentile(out, 97.5)) * 100, 3),
                p_gt0=round(float((out > 0).mean()), 4), B=len(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter")
    ap.add_argument("--pairs", default="naive:pit,nocut:pit,join_only:pit,own_only:pit")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()

    _os.makedirs(OUT, exist_ok=True)
    ad = adapters.get(a.adapter)
    rows = []
    for task in ad.tasks():
        modes = build_modes(task.groups)
        for pr in a.pairs.split(","):
            x, y_ = pr.split(":")
            if x not in modes or y_ not in modes:
                continue
            for ts_ in task.test_seeds:
                t0 = time.time()
                r = paired(ad, task, x, y_, ts_, modes)
                if r is None:
                    continue
                r["seconds"] = round(time.time() - t0, 1)
                rows.append(r)
                print(f"  {task.name:32s} {ts_:10s} {r['contrast']:18s} "
                      f"Δ={r['delta_pp']:+6.2f} п.п. [{r['lo_pp']:+6.2f}, {r['hi_pp']:+6.2f}]",
                      flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(f"{OUT}/{ad.name}{a.suffix}_paired.csv", index=False)
    print(f"\n→ out/{ad.name}{a.suffix}_paired.csv")
