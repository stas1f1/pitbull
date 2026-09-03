"""
Эксперимент 3: что реально отдают наружу AutoGluon и LightAutoML,
соблюдают ли они бюджет, и есть ли внутри их собственного набора кандидатов
тот же разрыв «валидация против теста».
"""
import gzip, time, warnings, os, sys, json
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import train_test_split
warnings.filterwarnings("ignore")
os.environ["OMP_NUM_THREADS"] = "2"

DATA = "/home/claude/exp/data"
DS = ["ionosphere", "sonar", "churn", "coil2000", "phoneme", "spambase", "magic"]
TIME_LIMITS = [300, 900]
MAXN = 4000


def load(n):
    with gzip.open(f"{DATA}/{n}.tsv.gz", "rt") as f:
        df = pd.read_csv(f, sep="\t")
    if len(df) > MAXN:
        df = df.sample(MAXN, random_state=0).reset_index(drop=True)
    return df


rows, board = [], []
from autogluon.tabular import TabularPredictor

for name in DS:
    df = load(name)
    tr, te = train_test_split(df, test_size=0.3, stratify=df.target, random_state=0)
    for tl in TIME_LIMITS:
        t0 = time.time()
        try:
            p = TabularPredictor(label="target", verbosity=0, eval_metric="roc_auc",
                                 path=f"/tmp/ag/{name}_{tl}").fit(
                tr, time_limit=tl, hyperparameters="zeroshot", presets="medium_quality")
            elapsed = time.time() - t0
            lb = p.leaderboard(te, silent=True)
            lb = lb[["model", "score_test", "score_val", "fit_time"]].copy()
            lb["dataset"], lb["time_limit"] = name, tl
            board.append(lb)
            # исключаем ансамбли, оставляем только базовые кандидаты
            base = lb[~lb.model.str.contains("WeightedEnsemble")]
            r_all = spearmanr(base.score_val, base.score_test).statistic if len(base) > 3 else np.nan
            top = base.nlargest(min(10, len(base)), "score_val")
            r_top = spearmanr(top.score_val, top.score_test).statistic if len(top) > 3 else np.nan
            pick = base.loc[base.score_val.idxmax()].score_test
            oracle = base.score_test.max()
            rows.append(dict(fw="AutoGluon", dataset=name, time_limit=tl,
                             elapsed=round(elapsed, 1), overrun=round(elapsed / tl, 2),
                             n_models=len(base), rho_all=r_all, rho_top10=r_top,
                             pick_test=pick, oracle_test=oracle, regret=oracle - pick,
                             ens_test=lb[lb.model.str.contains("WeightedEnsemble")].score_test.max()))
            print(f"AG {name:10s} tl={tl:4d} факт={elapsed:6.1f}s x{elapsed/tl:.2f} "
                  f"моделей={len(base):2d} rho_all={r_all:.3f} rho_top={r_top if not np.isnan(r_top) else float('nan'):.3f} "
                  f"потеря={100*(oracle-pick):.2f}пп", flush=True)
        except Exception as e:
            print(f"AG {name} tl={tl} ОШИБКА: {type(e).__name__}: {str(e)[:120]}", flush=True)

pd.DataFrame(rows).to_csv("/home/claude/exp/fw_summary.csv", index=False)
if board:
    pd.concat(board).to_csv("/home/claude/exp/fw_leaderboards.csv", index=False)
print("\nсохранено")
