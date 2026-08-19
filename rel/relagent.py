"""
Дифференциальное исполнение по корпусу запросов, написанных агентом:
    python3 relagent.py [--seeds 2] [--limit N]

Корпус — 37 уникальных SQL из траекторий RelAgent на задаче `stack/user-engagement`
(`prestudy/p2_out/unique_queries.json`). До сих пор по ним был только статический скан:
5 подсветок, все 5 ложные, то есть **0 из 37 вердиктов получено исполнением** —
ограничение №20 статьи. Здесь они исполняются против опубликованной базы rel-stack.

Схема та же, что в sqloracle.py. Отношение доступности — из объявлений самого RelBench.
Метки (`eval_table`) в обоих запусках одни и те же, меняется только база.

Фазы на каждый запрос: контроль детерминированности (тот же запрос дважды на полной
базе), отрицательный контроль (усечение отнесено за пределы всех меток), основные
моменты. Запрос, не исполнившийся из-за диалекта или отсутствующей колонки, получает
вердикт ERROR и в знаменатель вердиктов не идёт — причина записывается.

Отдельный вердикт TIMEOUT. Часть корпуса написана без предагрегации: три `LEFT JOIN`
к одной строке меток дают декартово произведение posts x comments x votes на
пользователя, и запрос не заканчивается за разумное время. Это свойство самого
корпуса, а не нашей проверки, поэтому такой запрос получает TIMEOUT и в знаменатель
вердиктов тоже не идёт. Порог вынесен в параметр, чтобы он был виден, а не спрятан.
"""
import os as _os, sys as _sys, json, time, argparse, warnings, threading
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
import sqloracle as SO

CORPUS = _os.path.join(_os.path.dirname(_HERE), "prestudy", "p2_out", "unique_queries.json")
DS, TASK, LTAB = "stack", "user-engagement", "user_engagement"
KEYS = ["OwnerUserId", "timestamp"]


class Timeout(Exception):
    pass


def run_one(con, sql, label_parquets, seed, limit=None):
    files = ", ".join("'" + p.replace("'", "''") + "'"
                      for p in label_parquets if _os.path.isfile(p))
    con.execute(f'CREATE OR REPLACE TABLE eval_table AS SELECT * FROM '
                f'read_parquet([{files}], union_by_name=true) '
                f'WHERE "timestamp" = TIMESTAMP \'{SO.ts(seed)}\'')
    if not limit:
        return con.execute(sql).fetch_df()
    fired = []
    t = threading.Timer(limit, lambda: (fired.append(1), con.interrupt()))
    t.start()
    try:
        return con.execute(sql).fetch_df()
    except Exception:
        if fired:
            raise Timeout(f"не уложился в {limit} с")
        raise
    finally:
        t.cancel()


def check(qid, q, db_dir, labs, seeds, tmax, limit):
    rows, nondet = [], set()

    def one(seed, phase, cutoff, nd):
        t0 = time.time()
        try:
            cf = SO.make_con(db_dir, DS, None)
            full = run_one(cf, q["sql"], labs, seed, limit)
            ct = SO.make_con(db_dir, DS, cutoff)
            other = run_one(ct, q["sql"], labs, seed, limit)
            ct.close(); cf.close()
            _, cols, _ = SO.compare(full, other, KEYS)
            net = {c: k for c, k in cols.items() if c not in nd}
            if phase == "determinism":
                v = "NONDETERMINISTIC" if cols else "DETERMINISTIC"
            elif net:
                v = "LEAK"
            elif phase == "main" and SO.removed_rows(db_dir, DS, cutoff) == 0:
                v = "VACUOUS"      # за отсечкой пусто — момент ничего не проверяет
            else:
                v = "CLEAN"
            r = dict(query=qid, name=q.get("name", ""), seed=SO.ts(seed), phase=phase,
                     verdict=v, columns=";".join(net), cells=sum(net.values()),
                     columns_nondet=";".join(c for c in cols if c in nd),
                     n_rows=0 if full is None else len(full),
                     seconds=round(time.time() - t0, 1))
        except Exception as e:
            r = dict(query=qid, name=q.get("name", ""), seed=SO.ts(seed), phase=phase,
                     verdict="TIMEOUT" if isinstance(e, Timeout) else "ERROR",
                     columns=f"{type(e).__name__}: {str(e)[:160]}",
                     cells=0, columns_nondet="", n_rows=0, seconds=round(time.time() - t0, 1))
        rows.append(r)
        return r

    d = one(seeds[-1], "determinism", None, set())
    if d["verdict"] in ("TIMEOUT", "ERROR"):
        return rows           # не исполнился или не уложился — остальные фазы бессмысленны
    if d["verdict"] == "NONDETERMINISTIC":
        nondet |= set(d["columns"].split(";"))
    one(seeds[-1], "negative_control", tmax, nondet)
    for s in seeds:
        one(s, "main", s, nondet)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--limit-seconds", type=int, default=300,
                    help="потолок на одно исполнение; превышение — вердикт TIMEOUT")
    a = ap.parse_args()

    corpus = json.load(open(CORPUS))
    ok, db_dir, labs = SO.available(DS, TASK)
    assert ok, "нет базы rel-stack или таблицы меток user-engagement"
    seeds = SO.seeds_for(labs, "timestamp", a.seeds)
    tmax = pd.Timestamp(SO.db_tmax(db_dir, DS)) + pd.Timedelta(days=1)
    print(f"корпус: {len(corpus)} запросов, моменты: {[SO.ts(s) for s in seeds]}\n")

    rows = []
    items = list(corpus.items())[: a.limit or None]
    for i, (qid, q) in enumerate(items, 1):
        rr = check(qid, q, db_dir, labs, seeds, tmax, a.limit_seconds)
        m = [r for r in rr if r["phase"] == "main"]
        det = [r for r in rr if r["phase"] == "determinism"][0]["verdict"]
        ncr = [r for r in rr if r["phase"] == "negative_control"]
        nc = ncr[0]["verdict"] if ncr else "-"
        print(f"  {i:2d}/{len(items)} {qid} {q.get('name',''):24s} "
              f"det={det:16s} nc={nc:8s} main={','.join(r['verdict'] for r in m):20s} "
              f"{m[0]['columns'][:60] if m else ''}", flush=True)
        rows += rr
    R = pd.DataFrame(rows)
    R.to_csv(f"{SO.OUT}/relagent_oracle{a.suffix}.csv", index=False)

    def verdict_of(g):
        d = g[g.phase == "determinism"].verdict.iloc[0]
        if d in ("TIMEOUT", "ERROR"):
            return d
        m = g[g.phase == "main"].verdict
        if (m == "ERROR").all():
            return "ERROR"
        if (m == "LEAK").any():
            return "LEAK"
        return "VACUOUS" if (m == "VACUOUS").all() else "CLEAN"
    per = R.groupby("query").apply(verdict_of, include_groups=False)
    print("\n" + "=" * 70)
    print(per.value_counts().to_string())
    print(f"\n→ out/relagent_oracle{a.suffix}.csv")
