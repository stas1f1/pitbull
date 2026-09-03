"""
Контроль: выживает ли разрыв «валидация против теста», если валидация честная —
не одиночная отложенная выборка, а перекрёстная проверка.
"""
import gzip, warnings, numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
import sys
sys.path.insert(0, "/home/claude/exp")
from run import make_pool, build, load, score

warnings.filterwarnings("ignore")
DS = ["ionosphere", "sonar", "churn", "coil2000", "phoneme", "magic"]
SEEDS = [0, 1, 2]
pool = make_pool()


def one(cfg, Xd, yd, Xte, yte, classes, seed):
    """Возвращает две оценки валидации: отложенная и 3-кратная перекрёстная."""
    try:
        # отложенная: делим Xd пополам
        Xtr, Xva, ytr, yva = train_test_split(Xd, yd, test_size=.5, stratify=yd, random_state=seed)
        m = build(cfg).fit(Xtr, ytr)
        ho = score(yva, m.predict_proba(Xva), classes)

        # перекрёстная по всему Xd
        cv = StratifiedKFold(3, shuffle=True, random_state=seed)
        oof = cross_val_predict(build(cfg), Xd, yd, cv=cv, method="predict_proba", n_jobs=1)
        cvs = score(yd, oof, classes)

        # тест: обучаем на всём Xd
        mf = build(cfg).fit(Xd, yd)
        te = score(yte, mf.predict_proba(Xte), classes)
        return dict(name=cfg["name"], family=cfg["family"], holdout=ho, cv=cvs, test=te)
    except Exception:
        return None


rows = []
for nm in DS:
    X, y = load(nm)
    if len(y) > 3000:
        i = np.random.RandomState(0).choice(len(y), 3000, replace=False)
        X, y = X[i], y[i]
    classes = np.unique(y)
    for seed in SEEDS:
        Xd, Xte, yd, yte = train_test_split(X, y, test_size=.3, stratify=y, random_state=seed)
        res = Parallel(n_jobs=2)(delayed(one)(c, Xd, yd, Xte, yte, classes, seed) for c in pool)
        for r in res:
            if r:
                r.update(dataset=nm, seed=seed)
                rows.append(r)
    print("готов", nm, flush=True)

df = pd.DataFrame(rows)
df.to_csv("/home/claude/exp/cv_control.csv", index=False)

out = []
for (ds, sd), g in df.groupby(["dataset", "seed"]):
    for kind in ["holdout", "cv"]:
        top = g.nlargest(10, kind)
        pick = g.loc[g[kind].idxmax()].test
        out.append(dict(dataset=ds, seed=sd, валидация=kind,
                        rho_all=spearmanr(g[kind], g.test).statistic,
                        rho_top10=spearmanr(top[kind], top.test).statistic,
                        потеря=g.test.max() - pick))
R = pd.DataFrame(out)
print("\n" + "=" * 78)
print("ОТЛОЖЕННАЯ ВЫБОРКА ПРОТИВ ПЕРЕКРЁСТНОЙ ПРОВЕРКИ")
print("=" * 78)
t = R.groupby("валидация").agg(
    rho_по_всем=("rho_all", "median"),
    rho_в_топ10=("rho_top10", "median"),
    потеря_пп=("потеря", "median")).round(3)
t["потеря_пп"] = (t["потеря_пп"] * 100).round(2)
print(t.to_string())
print()
print(R.pivot_table(index="dataset", columns="валидация",
                    values=["rho_top10", "потеря"]).round(3).to_string())
