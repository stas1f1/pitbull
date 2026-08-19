"""
Цена нарушения в чужом опубликованном SQL: python3 sqlcost.py f1_driver-dnf [...]

Оракул (sqloracle.py) отвечает на вопрос «зависит ли выход от строк, которых на
момент предсказания ещё нет». Это факт, а не величина. Здесь измеряется величина:
тот же самый запрос строит признаки в двух режимах —

  as_published — на базе как она есть (так его и запускали авторы);
  corrected    — база физически усечена на момент предсказания каждой строки меток,
                 сам SQL не изменён ни на символ,

— после чего обучается ОДНА И ТА ЖЕ модель (LightGBM, те же параметры, seed 0) и
сравниваются AUC на тесте. Разница и есть завышение.

Правило §3.5 HANDOVER: цена не выводится из факта. Ноль здесь — такой же результат,
как и три пункта, и пишется первой строкой.
"""
import os as _os, sys as _sys, time, argparse, warnings
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
import sqloracle as SO
from dsapi import fixed_model_auc, univariate_probe, probe_says, DATAROBOT, H2O, OUT

# задача -> (колонка метки, бинарная ли)
TARGET = {
    "driver-dnf": ("did_not_finish", True),
    "driver-top3": ("qualifying", True),
    "user-badge": ("WillGetBadge", True),
    "user-churn": ("churn", True),
    "item-churn": ("churn", True),
    "user-repeat": ("target", True),
    "user-ignore": ("target", True),
    "user-attendance": ("target", False),
    "post-votes": ("popularity", False),
    "user-engagement": ("contribution", False),
    "item-sales": ("sales", False),
    "item-ltv": ("ltv", False),
    "user-ltv": ("ltv", False),
    "driver-position": ("position", False),
}


def build_split(sql_text, db_dir, ds, labs, ltab, tcol, out_table, split_parquet,
                truncated, max_moments=None, tag=""):
    """Признаки для одной выборки: по одному запуску запроса на момент предсказания."""
    ts_all = np.sort(pd.read_parquet(split_parquet, columns=[tcol])[tcol].dropna().unique())
    if max_moments and len(ts_all) > max_moments:
        idx = np.linspace(0, len(ts_all) - 1, max_moments).round().astype(int)
        ts_all = ts_all[idx]
    parts = []
    for i, t in enumerate(ts_all):
        con = SO.make_con(db_dir, ds, t if truncated else None)
        parts.append(SO.run_sql(con, sql_text, [split_parquet], ltab, tcol, t, out_table))
        con.close()
        if (i + 1) % 25 == 0:
            print(f"      {tag} {i+1}/{len(ts_all)}", flush=True)
    return pd.concat(parts, ignore_index=True) if parts else None


def numeric(X, cols=None):
    X = X.select_dtypes(include=[np.number])
    return X if cols is None else X.reindex(columns=cols)


def cost(sql_name, max_train=60, max_test=None):
    path = _os.path.join(SO.AUDIT, sql_name + ".sql")
    ds, task, ltab = SO.parse_name(path)
    ok, db_dir, labs = SO.available(ds, task)
    if not ok:
        return [dict(file=sql_name, verdict="NO_DATA")]
    if task not in TARGET:
        return [dict(file=sql_name, verdict="NO_TARGET")]
    tgt, binary = TARGET[task]
    if not binary:
        return [dict(file=sql_name, verdict="NOT_BINARY",
                     note=f"метка {tgt} не бинарная — AUC неприменим")]
    sql_text = open(path).read()
    tcol = SO.label_time_col(ds)
    out_table = f"{ltab}_test_feats"
    train_p, val_p, test_p = labs
    keys = [c for c in pd.read_parquet(test_p).columns if c != tgt]

    rows = []
    for regime, trunc in [("as_published", False), ("corrected", True)]:
        t0 = time.time()
        Xtr = build_split(sql_text, db_dir, ds, labs, ltab, tcol, out_table, train_p,
                          trunc, max_train, f"{regime}/train")
        Xte = build_split(sql_text, db_dir, ds, labs, ltab, tcol, out_table, test_p,
                          trunc, max_test, f"{regime}/test")
        if Xtr is None or Xte is None:
            rows.append(dict(file=sql_name, regime=regime, verdict="EMPTY")); continue
        ytr = pd.read_parquet(train_p).merge(Xtr[keys], on=keys, how="right")[tgt]
        yte = pd.read_parquet(test_p).merge(Xte[keys], on=keys, how="right")[tgt]
        m = ytr.notna() & np.isfinite(ytr.fillna(0))
        Xtr_, ytr_ = numeric(Xtr[m.values]), ytr[m].astype(int)
        cols = list(Xtr_.columns)
        m2 = yte.notna()
        Xte_, yte_ = numeric(Xte[m2.values], cols), yte[m2].astype(int)
        if ytr_.nunique() < 2 or yte_.nunique() < 2:
            rows.append(dict(file=sql_name, regime=regime, verdict="DEGENERATE")); continue
        auc = fixed_model_auc(Xtr_, ytr_, Xte_, yte_)
        probe, who = univariate_probe(Xte_, yte_)
        rows.append(dict(file=sql_name, dataset=ds, task=task, regime=regime,
                         n_train=int(len(ytr_)), n_test=int(len(yte_)),
                         pos_rate=round(float(yte_.mean()), 3), n_features=len(cols),
                         auc=round(float(auc), 6), probe=round(float(probe), 6),
                         probe_feature=who, probe_datarobot=probe_says(probe, DATAROBOT),
                         probe_h2o=probe_says(probe, H2O), seconds=round(time.time() - t0, 1)))
        print(f"  {sql_name:26s} {regime:13s} n_tr={len(ytr_):6d} n_te={len(yte_):6d} "
              f"AUC={auc:.4f} проверка={probe:.3f}", flush=True)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-train", type=int, default=60)
    ap.add_argument("--max-test", type=int, default=None)
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()

    _os.makedirs(OUT, exist_ok=True)
    rows = []
    for f in a.files:
        rows += cost(f, a.max_train, a.max_test)
    R = pd.DataFrame(rows)
    if "auc" in R.columns:
        base = R[R.regime == "corrected"].set_index("file").auc
        R["inflation_pp"] = [round((r.auc - base.loc[r.file]) * 100, 4)
                             if getattr(r, "file", None) in base.index and pd.notna(getattr(r, "auc", np.nan))
                             else np.nan for r in R.itertuples()]
    R.to_csv(f"{OUT}/sql_cost{a.suffix}.csv", index=False)
    print("\n" + R.to_string(index=False))
    print(f"\n→ out/sql_cost{a.suffix}.csv")
