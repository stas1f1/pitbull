"""
Эксперимент 2: обманывает ли утечка отбор по валидации, и ловят ли её дешёвые проверки.
"""
import gzip, warnings, numpy as np, pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, QuantileTransformer
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

DATA = "/home/claude/exp/data"
DS = ["churn", "coil2000", "magic", "phoneme", "spambase", "ionosphere", "chess", "hypothyroid"]
SEEDS = [0, 1, 2]


def load(n):
    with gzip.open(f"{DATA}/{n}.tsv.gz", "rt") as f:
        df = pd.read_csv(f, sep="\t")
    y = df.target.values
    X = df.drop(columns=["target"]).values.astype(float)
    if len(y) > 4000:
        i = np.random.RandomState(0).choice(len(y), 4000, replace=False)
        X, y = X[i], y[i]
    return X, (y == np.unique(y)[-1]).astype(int) if len(np.unique(y)) == 2 else y


MODELS = {
    "rf": RandomForestClassifier(n_estimators=200, n_jobs=1, random_state=0),
    "hgb": HistGradientBoostingClassifier(max_iter=200, random_state=0),
    "logit": LogisticRegression(max_iter=1000),
}

# ---------- дешёвые проверки ----------
def probe_single_feature(Xtr, ytr):
    """Есть ли одиночный признак, дающий подозрительно высокий AUC?"""
    best = 0.5
    for j in range(Xtr.shape[1]):
        v = Xtr[:, j]
        if np.std(v) == 0:
            continue
        a = roc_auc_score(ytr, v)
        best = max(best, max(a, 1 - a))
    return best


def probe_dup_overlap(Xtr, Xva):
    """Доля строк валидации, дословно совпадающих со строкой обучения."""
    tr = set(map(lambda r: hash(r.tobytes()), np.ascontiguousarray(np.round(Xtr, 6))))
    va = np.ascontiguousarray(np.round(Xva, 6))
    hits = sum(1 for r in va if hash(r.tobytes()) in tr)
    return hits / len(va)


def probe_cv_vs_holdout(Xtr, ytr, Xva, yva):
    """Расхождение честной перекрёстной проверки на обучении и оценки на валидации."""
    m = Pipeline([("imp", SimpleImputer(strategy="median")),
                  ("sc", StandardScaler()),
                  ("est", HistGradientBoostingClassifier(max_iter=100, random_state=0))])
    cv = cross_val_score(m, Xtr, ytr, cv=3, scoring="roc_auc", n_jobs=1).mean()
    m.fit(Xtr, ytr)
    ho = roc_auc_score(yva, m.predict_proba(Xva)[:, 1])
    return ho - cv


rows = []
for name in DS:
    X, y = load(name)
    if len(np.unique(y)) != 2:
        continue
    for seed in SEEDS:
        Xtr0, Xtmp, ytr0, ytmp = train_test_split(X, y, test_size=.5, stratify=y, random_state=seed)
        Xva0, Xte0, yva, yte = train_test_split(Xtmp, ytmp, test_size=.5, stratify=ytmp, random_state=seed)
        rs = np.random.RandomState(seed)

        for leak in ["нет", "признак_из_цели", "дубликаты", "предобработка_до_сплита"]:
            Xtr, Xva, Xte = Xtr0.copy(), Xva0.copy(), Xte0.copy()
            ytr = ytr0.copy()

            if leak == "признак_из_цели":
                # колонка, посчитанная задним числом: коррелирует с целью, но в бою недоступна
                def mk(yy, n):
                    return (yy + rs.normal(0, .45, n)).reshape(-1, 1)
                Xtr = np.hstack([Xtr, mk(ytr, len(ytr))])
                Xva = np.hstack([Xva, mk(yva, len(yva))])
                # в тесте (как в реальном применении) признака нет — заполняем шумом
                Xte = np.hstack([Xte, rs.normal(.5, .45, (len(yte), 1))])

            elif leak == "дубликаты":
                k = len(yva) // 4
                idx = rs.choice(len(ytr), k, replace=False)
                Xva[:k] = Xtr[idx]
                yva = yva.copy(); yva[:k] = ytr[idx]

            elif leak == "предобработка_до_сплита":
                # квантильное преобразование обучено на всех данных сразу
                q = QuantileTransformer(output_distribution="normal", n_quantiles=200,
                                        random_state=0).fit(np.vstack([Xtr, Xva, Xte]))
                Xtr, Xva, Xte = q.transform(Xtr), q.transform(Xva), q.transform(Xte)

            for mn, m in MODELS.items():
                p = Pipeline([("imp", SimpleImputer(strategy="median")),
                              ("sc", StandardScaler()), ("est", m)]).fit(Xtr, ytr)
                va = roc_auc_score(yva, p.predict_proba(Xva)[:, 1])
                te = roc_auc_score(yte, p.predict_proba(Xte)[:, 1])
                rows.append(dict(dataset=name, seed=seed, leak=leak, model=mn,
                                 val=va, test=te, gap=va - te))

            rows.append(dict(dataset=name, seed=seed, leak=leak, model="__probes__",
                             p_single=probe_single_feature(Xtr, ytr),
                             p_dup=probe_dup_overlap(Xtr, Xva),
                             p_cvgap=probe_cv_vs_holdout(Xtr, ytr, Xva, yva)))
    print("готов", name, flush=True)

df = pd.DataFrame(rows)
df.to_csv("/home/claude/exp/leaks.csv", index=False)

M = df[df.model != "__probes__"]
P = df[df.model == "__probes__"]

print("\n" + "=" * 84)
print("НАСКОЛЬКО ВАЛИДАЦИЯ ЗАВЫШАЕТ КАЧЕСТВО (val - test, п.п. AUC)")
print("=" * 84)
t = M.groupby("leak").gap.agg(["mean", "median", "max"]).mul(100).round(2)
t.columns = ["среднее", "медиана", "максимум"]
print(t.reindex(["нет", "признак_из_цели", "дубликаты", "предобработка_до_сплита"]).to_string())

print("\n" + "=" * 84)
print("ЧТО ПОКАЗЫВАЮТ ДЕШЁВЫЕ ПРОВЕРКИ (среднее по датасетам и запускам)")
print("=" * 84)
t2 = P.groupby("leak")[["p_single", "p_dup", "p_cvgap"]].mean().round(3)
t2.columns = ["макс_AUC_одного_признака", "доля_дублей_вал/обуч", "разрыв_кросс-вал_и_валид"]
print(t2.reindex(["нет", "признак_из_цели", "дубликаты", "предобработка_до_сплита"]).to_string())

print("\n" + "=" * 84)
print("ЛОВЯТСЯ ЛИ УТЕЧКИ (простые пороги, подобранные ТОЛЬКО на чистом варианте)")
print("=" * 84)
clean = P[P.leak == "нет"]
th_single = clean.p_single.quantile(.95)
th_dup = max(clean.p_dup.max(), 0.01)
th_cv = clean.p_cvgap.abs().quantile(.95)
print(f"пороги: одиночный признак > {th_single:.3f} | дубли > {th_dup:.3f} | разрыв > {th_cv:.3f}\n")
det = []
for lk, g in P.groupby("leak"):
    det.append(dict(утечка=lk,
                    сработал_признак=f"{(g.p_single > th_single).mean()*100:.0f}%",
                    сработали_дубли=f"{(g.p_dup > th_dup).mean()*100:.0f}%",
                    сработал_разрыв=f"{(g.p_cvgap.abs() > th_cv).mean()*100:.0f}%",
                    хоть_один=f"{((g.p_single > th_single) | (g.p_dup > th_dup) | (g.p_cvgap.abs() > th_cv)).mean()*100:.0f}%"))
print(pd.DataFrame(det).set_index("утечка")
      .reindex(["нет", "признак_из_цели", "дубликаты", "предобработка_до_сплита"]).to_string())
print("\n(строка «нет» — ложные срабатывания на чистых данных)")
