"""
Предварительный эксперимент.
Вопрос: правда ли, что при большем бюджете поиска отбор перестаёт быть проблемой,
и всё сходится к «скейлинг + случайный лес»?

Логика: пул из ~100 пайплайнов = пространство поиска. Случайное подмножество размера K =
поиск с бюджетом K оценок. Смотрим, что происходит с ростом K.
"""
import os, gzip, time, json, warnings, itertools
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, QuantileTransformer, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed

warnings.filterwarnings("ignore")
DATA = "/home/claude/exp/data"
MAXN = 5000
SEEDS = [0, 1, 2]


def load(name):
    with gzip.open(f"{DATA}/{name}.tsv.gz", "rt") as f:
        df = pd.read_csv(f, sep="\t")
    y = df["target"].values
    X = df.drop(columns=["target"]).values.astype(float)
    return X, y


def make_pool():
    """Пул пайплайнов: (масштабирование) x (модель с гиперпараметрами)."""
    P = []
    def add(family, name, scaler, est):
        P.append(dict(family=family, name=name, scaler=scaler, est=est))

    # линейные — чувствительны к масштабу
    for C in [0.01, 0.1, 1, 10, 100]:
        for sc in ["std", "quant"]:
            add("linear", f"logreg_C{C}_{sc}", sc,
                LogisticRegression(C=C, max_iter=1000))
    # случайный лес
    for md in [None, 4, 8, 16]:
        for mf in ["sqrt", 0.3, 0.7]:
            add("rf", f"rf_d{md}_f{mf}", "none",
                RandomForestClassifier(n_estimators=200, max_depth=md, max_features=mf,
                                       n_jobs=1, random_state=0))
    # extra trees
    for md in [None, 8]:
        for mf in ["sqrt", 0.5]:
            add("et", f"et_d{md}_f{mf}", "none",
                ExtraTreesClassifier(n_estimators=200, max_depth=md, max_features=mf,
                                     n_jobs=1, random_state=0))
    # бустинг
    for lr in [0.03, 0.1, 0.3]:
        for ln in [15, 31, 63]:
            for l2 in [0.0, 1.0]:
                add("gbdt", f"hgb_lr{lr}_ln{ln}_l2{l2}", "none",
                    HistGradientBoostingClassifier(learning_rate=lr, max_leaf_nodes=ln,
                                                   l2_regularization=l2, max_iter=200,
                                                   early_stopping=True, random_state=0))
    # kNN
    for k in [1, 5, 15, 31]:
        for sc in ["std", "quant"]:
            add("knn", f"knn{k}_{sc}", sc, KNeighborsClassifier(n_neighbors=k, n_jobs=1))
    # SVM
    for C in [0.1, 1, 10]:
        add("svm", f"svc_C{C}", "std", SVC(C=C, probability=True, random_state=0))
    # нейросеть
    for h in [(64,), (128, 64)]:
        for a in [1e-4, 1e-2]:
            add("mlp", f"mlp_{h}_a{a}", "std",
                MLPClassifier(hidden_layer_sizes=h, alpha=a, max_iter=250, random_state=0))
    # простые
    add("nb", "gaussiannb", "std", GaussianNB())
    for md in [3, 6, None]:
        add("tree", f"dt_d{md}", "none", DecisionTreeClassifier(max_depth=md, random_state=0))
    return P


SCALERS = {
    "none": FunctionTransformer(),
    "std": StandardScaler(),
    "quant": QuantileTransformer(output_distribution="normal", n_quantiles=200, random_state=0),
}


def build(cfg):
    from sklearn.base import clone
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", clone(SCALERS[cfg["scaler"]])),
        ("est", clone(cfg["est"])),
    ])


def score(y_true, proba, classes):
    if len(classes) == 2:
        return roc_auc_score(y_true, proba[:, 1])
    return roc_auc_score(y_true, proba, multi_class="ovr", average="macro")


def eval_one(cfg, Xtr, ytr, Xva, yva, Xte, yte, classes):
    t0 = time.time()
    try:
        p = build(cfg).fit(Xtr, ytr)
        va = score(yva, p.predict_proba(Xva), classes)
        te = score(yte, p.predict_proba(Xte), classes)
    except Exception:
        return None
    return dict(name=cfg["name"], family=cfg["family"], val=va, test=te,
                fit_s=round(time.time() - t0, 3))


def run_dataset(name, pool):
    X, y = load(name)
    if len(y) > MAXN:
        idx = np.random.RandomState(0).choice(len(y), MAXN, replace=False)
        X, y = X[idx], y[idx]
    classes = np.unique(y)
    rows = []
    for seed in SEEDS:
        Xtr, Xtmp, ytr, ytmp = train_test_split(X, y, test_size=0.5, stratify=y, random_state=seed)
        Xva, Xte, yva, yte = train_test_split(Xtmp, ytmp, test_size=0.5, stratify=ytmp, random_state=seed)
        res = Parallel(n_jobs=2, backend="loky")(
            delayed(eval_one)(c, Xtr, ytr, Xva, yva, Xte, yte, classes) for c in pool)
        for r in res:
            if r:
                r.update(dataset=name, seed=seed, n=len(y), d=X.shape[1], n_classes=len(classes))
                rows.append(r)
    return rows


if False:
    pool = make_pool()
    print(f"размер пула: {len(pool)} пайплайнов", flush=True)
    names = sorted(f[:-7] for f in os.listdir(DATA) if f.endswith(".tsv.gz"))
    print("датасеты:", names, flush=True)
    allrows = []
    for nm in names:
        t0 = time.time()
        try:
            r = run_dataset(nm, pool)
            allrows += r
            print(f"  {nm:22s} n={r[0]['n']:5d} d={r[0]['d']:3d} cls={r[0]['n_classes']} "
                  f"конфигов_ок={len(r)//len(SEEDS):3d}  {time.time()-t0:6.1f}s", flush=True)
        except Exception as e:
            print(f"  {nm}: ОШИБКА {e}", flush=True)
    pd.DataFrame(allrows).to_csv("/home/claude/exp/results.csv", index=False)
    print("сохранено", len(allrows), "строк")
