"""
Дифференциальное исполнение по ЧУЖОМУ опубликованному SQL.

  python3 sqloracle.py                 # все файлы, для которых есть данные
  python3 sqloracle.py f1_driver-dnf   # один файл
  python3 sqloracle.py --seeds 3       # сколько моментов предсказания на задачу

Корпус: 15 файлов экспертного SQL из snap-stanford/relbench-user-study (каталог
`audit/`). До сих пор мы разбирали их статически — это было ограничение №20.
Здесь они исполняются.

Схема ровно та же, что в demo/pitfall.py, только программа — не функция на
pandas, а запрос duckdb:

    phi(D, t) == phi(D|t, t),   D|t = { r in D : время_строки(r) <= t }

Отношение доступности берётся из объявлений самого RelBench (Table(time_col=...)
в relbench/datasets/*.py), а не придумывается нами. Таблица без time_col
(справочник: drivers, circuits, article, customer) не усекается.

Для каждого файла:
  1. контроль детерминированности — один и тот же запрос на одной и той же полной
     базе дважды. Расхождение означает, что программа недетерминирована и вердикт
     о ней недействителен (any_value, group by all без сортировки и т.п.);
  2. отрицательный контроль — момент позже всех временных меток базы: усечение
     ничего не удаляет, ожидание ЧИСТО;
  3. основные моменты — по одному запуску на момент предсказания.

Метки задачи в обоих запусках ОДНИ И ТЕ ЖЕ (строки тестовой выборки с этим
моментом). Меняется только база.
"""
import os as _os, sys as _sys, glob, json, time, argparse, re
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)

import numpy as np, pandas as pd, duckdb
from jinja2 import Template

DATA = _os.environ.get("PITFALL_EXT_DATA", _os.path.join(_ROOT, "PITFALL_ext_data"))
AUDIT = _os.path.join(_ROOT, "audit")
OUT = _os.path.join(_HERE, "out")
NA = -987654321.0

# Отношение доступности — из relbench/datasets/*.py (Table(..., time_col=...)).
# None означает справочник без времени: не усекается.
TIME_COLS = {
    "f1": {"races": "date", "results": "date", "standings": "date",
           "constructor_results": "date", "constructor_standings": "date",
           "qualifying": "date", "circuits": None, "drivers": None, "constructors": None},
    "stack": {"posts": "CreationDate", "comments": "CreationDate", "votes": "CreationDate",
              "badges": "Date", "users": "CreationDate", "postHistory": "CreationDate",
              "postLinks": "CreationDate"},
    "hm": {"transactions": "t_dat", "customer": None, "article": None},
    "event": {"users": "joinedAt", "events": "start_time", "event_attendees": "start_time",
              "event_interest": "timestamp", "user_friends": None},
    "amazon": {"product": None, "customer": None, "review": "review_time"},
}
DBDIR = {"f1": "rel-f1", "stack": "rel-stack", "hm": "rel-hm",
         "event": "rel-event", "amazon": "rel-amazon"}
# колонка момента предсказания в таблице меток
LABEL_TIME = {"f1": "date"}          # у остальных — "timestamp"


def label_time_col(ds):
    return LABEL_TIME.get(ds, "timestamp")


def parse_name(path):
    """audit/f1_driver-dnf.sql -> ('f1', 'driver-dnf', 'driver_dnf')"""
    base = _os.path.basename(path)[:-4]
    ds, task = base.split("_", 1)
    m = re.search(r"create or replace table\s+([a-z0-9_]+)_\{\{ set \}\}_feats",
                  open(path).read())
    return ds, task, (m.group(1) if m else task.replace("-", "_"))


def available(ds, task):
    db = _os.path.join(DATA, DBDIR[ds], "db")
    d = _os.path.join(DATA, "tasks", f"{DBDIR[ds]}__{task}", task)
    labs = [_os.path.join(d, f"{x}.parquet") for x in ("train", "val", "test")]
    return _os.path.isdir(db) and _os.path.isfile(labs[-1]), db, labs


def _snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def ts(x):
    """Момент в виде, который понимает duckdb (numpy.datetime64 сам по себе не годится)."""
    return pd.Timestamp(x).strftime("%Y-%m-%d %H:%M:%S")


def make_con(db_dir, ds, cutoff):
    """Виды над parquet. cutoff=None — полная база; иначе усечённая на момент.
    Фильтр проталкивается в чтение parquet, физической копии базы не делается."""
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    for f in sorted(glob.glob(_os.path.join(db_dir, "*.parquet"))):
        t = _os.path.basename(f)[:-8]
        tcol = TIME_COLS[ds].get(t, "__missing__")
        if tcol == "__missing__":
            raise KeyError(f"{ds}: у таблицы {t} не объявлена метка времени")
        src = "read_parquet('" + f.replace("'", "''") + "')"
        if cutoff is None or tcol is None:
            body = f"SELECT * FROM {src}"
        else:
            body = f"SELECT * FROM {src} WHERE \"{tcol}\" <= TIMESTAMP '{ts(cutoff)}'"
        for alias in {t, _snake(t)}:      # SQL зовёт post_history, в базе postHistory
            con.execute(f'CREATE VIEW "{alias}" AS {body}')
    return con


def run_sql(con, sql_text, label_parquets, label_table, tcol, seed, out_table):
    files = ", ".join("'" + p.replace("'", "''") + "'"
                      for p in label_parquets if _os.path.isfile(p))
    src = f"read_parquet([{files}], union_by_name=true)"
    con.execute(f'CREATE OR REPLACE TABLE "{label_table}_test" AS '
                f'SELECT * FROM {src} WHERE "{tcol}" = TIMESTAMP \'{ts(seed)}\'')
    body = Template(sql_text).render(set="test", subsample=0)
    for stmt in [s for s in body.split(";\n") if s.strip()]:
        con.execute(stmt)
    return con.execute(f'SELECT * FROM "{out_table}"').fetch_df()


def compare(a, b, keys):
    """Возврат: (есть ли расхождение, список колонок, число расходящихся ячеек)."""
    if a is None or b is None:
        return (a is None) != (b is None), {"<none>": 0}, 0
    if list(a.columns) != list(b.columns):
        return True, {"<набор колонок>": 0}, 0
    ks = [k for k in keys if k in a.columns]
    a = a.sort_values(ks).reset_index(drop=True) if ks else a.reset_index(drop=True)
    b = b.sort_values(ks).reset_index(drop=True) if ks else b.reset_index(drop=True)
    if a.shape != b.shape:
        return True, {"<число строк>": abs(a.shape[0] - b.shape[0])}, abs(a.shape[0] - b.shape[0])
    cols = {}
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_float_dtype(x) and pd.api.types.is_float_dtype(y):
            x, y = x.round(9), y.round(9)
        # x == y на nullable-типах даёт NA, а NA в sum() пропускается — расхождение
        # молча теряется. Тот же класс, что баг frames_equal(None, None) в оракуле.
        same = (x.isna() & y.isna()) | x.eq(y).fillna(False)
        k = int((~same.astype(bool)).sum())
        if k:
            cols[c] = k
    return bool(cols), cols, sum(cols.values())


def seeds_for(label_parquets, tcol, n):
    """Моменты предсказания. У большинства задач RelBench в тестовой выборке ровно
    ОДИН момент, поэтому берём объединение train/val/test и раскладываем n моментов
    равномерно — последний всегда тестовый."""
    vals = []
    for p in label_parquets:
        if _os.path.isfile(p):
            vals.append(pd.read_parquet(p, columns=[tcol])[tcol].dropna().unique())
    v = np.sort(np.unique(np.concatenate(vals)))
    if len(v) <= n:
        return list(v)
    idx = np.linspace(0, len(v) - 1, n).round().astype(int)
    return list(v[idx])


def db_tmax(db_dir, ds):
    mx = None
    for f in sorted(glob.glob(_os.path.join(db_dir, "*.parquet"))):
        t = _os.path.basename(f)[:-8]
        tcol = TIME_COLS[ds].get(t)
        if not tcol:
            continue
        v = duckdb.sql(f"SELECT max(\"{tcol}\") FROM read_parquet('{f}')").fetchone()[0]
        if v is not None:
            mx = v if mx is None else max(mx, v)
    return mx


def check_file(path, n_seeds=3, verbose=True):
    ds, task, ltab = parse_name(path)
    ok, db_dir, labs = available(ds, task)
    name = _os.path.basename(path)
    if not ok:
        return [dict(file=name, dataset=ds, task=task, seed="", phase="skip",
                     verdict="NO_DATA", columns="", cells=0, n_rows=0, seconds=0)]
    sql_text = open(path).read()
    tcol = label_time_col(ds)
    keys = list(pd.read_parquet(labs[-1]).columns)
    out_table = f"{ltab}_test_feats"
    rows = []

    def run(seed, cutoff):
        cf = make_con(db_dir, ds, None)
        full = run_sql(cf, sql_text, labs, ltab, tcol, seed, out_table)
        ct = make_con(db_dir, ds, cutoff)
        other = run_sql(ct, sql_text, labs, ltab, tcol, seed, out_table)
        ct.close(); cf.close()
        return full, other

    def one(seed, phase, cutoff, nondet=()):
        """seed — момент, по которому отбираются метки (в обоих запусках одни и те же);
        cutoff — момент усечения базы; None означает «не усекать» (контроль
        детерминированности). nondet — колонки, уже признанные недетерминированными:
        вердикт выносится по расхождениям ЗА ИХ ВЫЧЕТОМ."""
        t0 = time.time()
        try:
            full, other = run(seed, cutoff)
            diff, cols, cells = compare(full, other, keys)
            net = {c: k for c, k in cols.items() if c not in set(nondet)}
            if phase == "determinism":
                v = "NONDETERMINISTIC" if cols else "DETERMINISTIC"
            else:
                v = "LEAK" if net else "CLEAN"
            # cells считаются ТОЛЬКО по колонкам, попавшим в вердикт: расхождения
            # в недетерминированных колонках к утечке отношения не имеют
            r = dict(file=name, dataset=ds, task=task, seed=ts(seed), phase=phase,
                     verdict=v, columns=";".join(map(str, net)), cells=sum(net.values()),
                     columns_nondet=";".join(c for c in cols if c in set(nondet)),
                     cells_nondet=cells - sum(net.values()),
                     n_rows=0 if full is None else len(full),
                     seconds=round(time.time() - t0, 1))
        except Exception as e:
            r = dict(file=name, dataset=ds, task=task, seed=ts(seed), phase=phase,
                     verdict="ERROR", columns=f"{type(e).__name__}: {str(e)[:200]}",
                     columns_nondet="", cells=0, cells_nondet=0, n_rows=0,
                     seconds=round(time.time() - t0, 1))
        if verbose:
            print(f"  {name:26s} {phase:16s} {ts(seed):19s} {r['verdict']:16s} "
                  f"{r['columns'][:64]}", flush=True)
        rows.append(r)
        return r

    ss = seeds_for(labs, tcol, n_seeds)
    tmax = pd.Timestamp(db_tmax(db_dir, ds)) + pd.Timedelta(days=1)
    nondet = set()
    for s_ in ss:                                   # 1. детерминированность на каждом моменте
        d = one(s_, "determinism", None)
        if d["verdict"] == "NONDETERMINISTIC":
            nondet |= set(d["columns"].split(";"))
    one(ss[-1], "negative_control", tmax, nondet)    # 2. отрицательный контроль
    for s_ in ss:                                   # 3. основные моменты
        one(s_, "main", s_, nondet)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="имена без .sql, напр. f1_driver-dnf")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()

    paths = sorted(glob.glob(_os.path.join(AUDIT, "*.sql")))
    if a.files:
        paths = [p for p in paths if _os.path.basename(p)[:-4] in a.files]
    _os.makedirs(OUT, exist_ok=True)

    all_rows = []
    for p in paths:
        all_rows += check_file(p, a.seeds)
    R = pd.DataFrame(all_rows)
    R.to_csv(f"{OUT}/sql_oracle{a.suffix}.csv", index=False)

    print("\n" + "=" * 92)
    print("ВЕРДИКТЫ ПО ФАЙЛАМ (основные моменты)")
    print("=" * 92)
    M = R[R.phase == "main"]
    if len(M):
        piv = M.pivot_table(index="file", columns="seed", values="verdict",
                            aggfunc="first").fillna("")
        print(piv.to_string())
    print(f"\n→ out/sql_oracle{a.suffix}.csv")
