"""
Набор ячеек для любого адаптера: python3 suite.py <имя> [--modes a,b,c] [--tasks x,y]

Выход:
  out/<база>_auc.csv     AUC, промышленная проверка, завышение относительно pit
  out/<база>_oracle.csv  дифференциальное исполнение: программа × момент
  out/<база>_summary.md  сводка

Между режимами меняется только временная семантика. Модель одна и та же везде.
"""
import os as _os, sys as _sys, time, warnings, argparse
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
import adapters
from dsapi import build_modes, MODE_ORDER, run_cell, differential_check, restrict_defined, OUT


def run_auc(ad, only_modes=None, only_tasks=None):
    rows = []
    for task in ad.tasks():
        if only_tasks and task.name not in only_tasks:
            continue
        modes = build_modes(task.groups)
        names = [m for m in MODE_ORDER if m in modes]
        if only_modes:
            names = [m for m in names if m in only_modes]
        for test_seed in task.test_seeds:
            for mode_name in names:
                t0 = time.time()
                r = run_cell(ad, task, mode_name, modes[mode_name], test_seed)
                if r is None:
                    print(f"  {task.name:22s} {test_seed} {mode_name:10s} вырождена", flush=True)
                    continue
                r["seconds"] = round(time.time() - t0, 1)
                rows.append(r)
                print(f"  {task.name:22s} {test_seed} {mode_name:10s} "
                      f"n={r['n_test']:6d} AUC={r['auc']:.4f} проверка={r['probe']:.3f} "
                      f"({r['probe_datarobot']}/{r['probe_h2o']})", flush=True)
    R = pd.DataFrame(rows)
    if len(R):
        base = R[R["mode"] == "pit"].set_index(["task", "test_seed"]).auc
        R["inflation_pp"] = [round((r.auc - base.loc[(r.task, r.test_seed)]) * 100, 4)
                             if (r.task, r.test_seed) in base.index else np.nan
                             for r in R.itertuples()]
        pb = R[R["mode"] == "pit"].set_index(["task", "test_seed"]).probe
        R["probe_delta"] = [round(r.probe - pb.loc[(r.task, r.test_seed)], 4)
                            if (r.task, r.test_seed) in pb.index else np.nan
                            for r in R.itertuples()]
    return R


def run_oracle(ad, negative_control=True):
    """Дифференциальное исполнение. Отрицательный контроль (момент = максимум
    временных меток базы) запускается ПЕРВЫМ: на Olist именно он поймал баг оракула."""
    db = ad.temporal_db()
    progs = ad.programs()
    rows = []
    seeds = []
    if negative_control:
        seeds.append(("negative_control", ad.TMAX_ALL))
    seeds += [(s, pd.Timestamp(s)) for s in getattr(ad, "ORACLE_SEEDS", ad.tasks()[0].test_seeds)]

    for label, seed in seeds:
        ents = ad.oracle_entities(seed)
        for pname, prog in progs.items():
            t0 = time.time()
            v = differential_check(prog, db, seed, ents)
            rows.append(dict(dataset=ad.name, seed=label, program=pname,
                             verdict="LEAK" if v.leak else "CLEAN",
                             columns=";".join(v.columns), cells=v.cells,
                             note=v.note, seconds=round(time.time() - t0, 2)))
            print(f"  {label:18s} {pname:8s} {'УТЕЧКА' if v.leak else 'ЧИСТО':7s} "
                  f"{', '.join(v.columns) if v.columns else '—'}"
                  f"{f'  ({v.cells} расхождений)' if v.cells else ''}", flush=True)
    return pd.DataFrame(rows)


def summary_md(ad, R, O):
    L = [f"# {ad.name}: набор ячеек\n"]
    L.append(f"Строк в основном кадре: {len(ad.ev):,}. Гранулярность меток: {ad.granularity}.\n")
    L.append("## Побочная временная ось\n")
    sa = ad.side_axis_report()
    L.append(sa.to_markdown(index=False) if len(sa) else "_нет колонок со своей меткой_")
    if ad.UNCHECKABLE:
        L.append("\n## Непроверяемые колонки (нет метки доступности)\n")
        L += [f"- {c}" for c in ad.UNCHECKABLE]
    L.append("\n## Дифференциальное исполнение\n")
    L.append(O.to_markdown(index=False) if len(O) else "_нет_")
    if len(R):
        L.append("\n## Завышение AUC относительно pit, п.п.\n")
        L.append(R.pivot_table(index=["task", "mode"], columns="test_seed",
                               values="inflation_pp", sort=False).round(2).to_markdown())
        L.append("\n## Промышленная проверка «максимальный AUC одного признака»\n")
        L.append(R.pivot_table(index=["task", "mode"], columns="test_seed",
                               values="probe", sort=False).round(3).to_markdown())
        L.append("\n## Базовое качество (pit)\n")
        L.append(R[R["mode"] == "pit"].pivot_table(index="task", columns="test_seed",
                                                   values="auc").round(3).to_markdown())
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter")
    ap.add_argument("--modes", default=None)
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--skip-auc", action="store_true")
    ap.add_argument("--skip-oracle", action="store_true")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()

    _os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ad = adapters.get(a.adapter)
    print(f"[{ad.name}] загружено: {len(ad.ev):,} строк, {time.time()-t0:.1f} с\n")

    O = pd.DataFrame()
    if not a.skip_oracle:
        print("── дифференциальное исполнение ──")
        O = run_oracle(ad)
        O.to_csv(f"{OUT}/{ad.name}{a.suffix}_oracle.csv", index=False)
        print()

    R = pd.DataFrame()
    if not a.skip_auc:
        print("── ячейки ──")
        R = run_auc(ad, a.modes.split(",") if a.modes else None,
                    a.tasks.split(",") if a.tasks else None)
        R.to_csv(f"{OUT}/{ad.name}{a.suffix}_auc.csv", index=False)

    open(f"{OUT}/{ad.name}{a.suffix}_summary.md", "w").write(summary_md(ad, R, O))
    print(f"\nГотово за {time.time()-t0:.0f} с → out/{ad.name}{a.suffix}_*.csv/.md")
