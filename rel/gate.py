"""
Ворота приёмки новой базы: python3 gate.py <адаптер>

Пять проверок из §4 плана расширения. Правило выведено из провала: на Olist наш
«корректный» эталон протекал, и мы узнали об этом через неделю. Ворота ловят такое
за минуту.

  1. объём — ≥20 тыс. строк в основном кадре;
  2. побочная временная ось — есть ли колонка со своей, более поздней меткой,
     и каков лаг (медиана, p90, максимум, доля строк с положительным лагом);
  3. непроверяемые колонки — изменяемое поле без истории;
  4. размер и баланс задач на каждом моменте;
  5. отрицательный контроль, затем: наивная программа протекает, PIT-корректная — нет.
     Если PIT протекает, адаптер сломан. Если наивная не протекает, показывать нечего.

Отрицательный контроль запускается ДО основных измерений — на Olist именно он
поймал баг оракула.
"""
import os as _os, sys as _sys, time, warnings, argparse
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
import adapters
from dsapi import differential_check, restrict_defined, undefined_availability_report, OUT

MIN_ROWS = 20_000
verdicts = []

def say(ok, name, detail=""):
    verdicts.append((ok, name))
    print(f"[{'ПРОШЛО' if ok else 'НЕ ПРОШЛО':9s}] {name}" + (f"\n            {detail}" if detail else ""))


def main(adapter_name):
    t0 = time.time()
    ad = adapters.get(adapter_name)
    print(f"=== ворота приёмки: {ad.name} ===\n")

    # 1. объём
    n = len(ad.ev)
    say(n >= MIN_ROWS, f"объём: {n:,} строк в основном кадре (порог {MIN_ROWS:,})")

    # 2. побочная временная ось
    print()
    sa = ad.side_axis_report()
    if len(sa):
        print(sa.to_string(index=False))
        has = bool((sa.share_positive > 0.001).any())
        say(has, "побочная временная ось: есть колонка, дописываемая к строке позже её появления")
    else:
        say(False, "побочная временная ось: НЕТ — база не проверяет основное утверждение")

    # 3. непроверяемые колонки
    print()
    if ad.UNCHECKABLE:
        for c in ad.UNCHECKABLE:
            print(f"  непроверяемо: {c}")
    else:
        print("  непроверяемых колонок не заявлено")
    print("  (это ограничение метода, а не провал ворот)")

    # 4. задачи
    print()
    trows = []
    for task in ad.tasks():
        for s in task.test_seeds:
            ents, y = task.label(ad.to_seed(s))
            trows.append(dict(task=task.name, seed=s, n=0 if ents is None else len(ents),
                              pos_rate=None if ents is None or not len(ents) else round(float(y.mean()), 3),
                              n_classes=0 if ents is None or not len(ents) else int(y.nunique())))
    T = pd.DataFrame(trows)
    print(T.to_string(index=False))
    ok = bool(len(T)) and bool((T.n >= [t.min_entities for t in ad.tasks() for _ in t.test_seeds]).all()
                               and (T.n_classes >= 2).all())
    say(ok, "задачи: на каждом моменте достаточно сущностей и оба класса присутствуют")

    # 5. отрицательный контроль, затем оракул
    print()
    db = ad.temporal_db()
    progs = ad.programs()
    nc_seed = ad.TMAX_ALL
    ua = undefined_availability_report(db)
    print(f"  отрицательный контроль: момент = максимум всех временных меток = {nc_seed}")
    db_strict = restrict_defined(db)
    nc_bad = []
    for pname, prog in progs.items():
        v = differential_check(prog, db_strict, nc_seed, ad.oracle_entities(nc_seed))
        print(f"    {pname:8s} {'УТЕЧКА' if v.leak else 'ЧИСТО'}  {', '.join(v.columns) or '—'}")
        if v.leak:
            nc_bad.append(pname)
    say(not nc_bad, "отрицательный контроль: ноль срабатываний на всех программах",
        f"сработало: {', '.join(nc_bad)} — разбирать ДО основных измерений" if nc_bad else "")

    # диагностика: то же на полной базе. Остаточное срабатывание объясняется
    # строками с неопределённой меткой доступности — они непроверяемы при любом t.
    if len(ua):
        print("\n  строки с неопределённой меткой доступности (непроверяемый класс):")
        print("   " + ua.to_string(index=False).replace("\n", "\n   "))
        for pname, prog in progs.items():
            v = differential_check(prog, db, nc_seed, ad.oracle_entities(nc_seed))
            print(f"    контроль на полной базе: {pname:8s} "
                  f"{'УТЕЧКА' if v.leak else 'ЧИСТО'}  {', '.join(v.columns) or '—'}")
        ua.to_csv(f"{OUT}/{ad.name}_gate_undefined.csv", index=False)

    print()
    orows = []
    for s in getattr(ad, "ORACLE_SEEDS", ad.tasks()[0].test_seeds):
        seed = pd.Timestamp(s)
        ents = ad.oracle_entities(seed)
        for pname, prog in progs.items():
            v = differential_check(prog, db, seed, ents)
            orows.append(dict(seed=s, program=pname, leak=v.leak, columns=";".join(v.columns), cells=v.cells))
            print(f"    {s:12s} {pname:8s} {'УТЕЧКА' if v.leak else 'ЧИСТО':7s} "
                  f"{', '.join(v.columns) or '—'}{f'  ({v.cells})' if v.cells else ''}")
    O = pd.DataFrame(orows)
    if len(O):
        nv = O[O.program == "naive"]
        k, n = int(nv.leak.sum()), len(nv)
        pit_clean = bool((~O[O.program == "pit"].leak).all()) if (O.program == "pit").any() else False
        say(pit_clean, "PIT-корректная программа: ЧИСТО на всех моментах",
            "" if pit_clean else "адаптер протекает — чинить, не публиковать")
        # Требование — «хотя бы на одном моменте»: на rel-f1 та же самая ошибка
        # протекает на дневной гранулярности и безвредна на секундной, и это
        # измеряемый результат, а не провал ворот.
        say(k > 0, f"наивная программа: УТЕЧКА на {k} из {n} моментов",
            "" if k else "показывать нечего: дефолтный способ ошибиться здесь безвреден")

    _os.makedirs(OUT, exist_ok=True)
    T.to_csv(f"{OUT}/{ad.name}_gate_tasks.csv", index=False)
    if len(sa):
        sa.to_csv(f"{OUT}/{ad.name}_gate_sideaxis.csv", index=False)

    bad = [n for ok_, n in verdicts if not ok_]
    print(f"\n=== {'ВОРОТА ПРОЙДЕНЫ' if not bad else 'ВОРОТА НЕ ПРОЙДЕНЫ'} "
          f"({len(verdicts)-len(bad)}/{len(verdicts)}), {time.time()-t0:.0f} с ===")
    for b in bad:
        print(f"  провал: {b}")
    return 0 if not bad else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter")
    _sys.exit(main(ap.parse_args().adapter))
