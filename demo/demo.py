#!/usr/bin/env python3
"""
PITFALL — демонстрация. Три сцены, все числа считаются вживую.

  Сцена 1  featuretools с настройками по умолчанию   ожидается УТЕЧКА
  Сцена 2  наш собственный эталон, первая версия     ожидается УТЕЧКА
  Сцена 3  тот же эталон после исправления           ожидается ЧИСТО

    python3 demo.py            все сцены
    python3 demo.py 1          одна сцена
    python3 demo.py --json     без оформления, машинный вывод
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import sys, json, time, warnings, numpy as np, pandas as pd
sys.path.insert(0, _ROOT + "/demo")
warnings.filterwarnings("ignore")
from pitfall import differential_check, univariate_probe, probe_says, fixed_model_auc, DATAROBOT
import scenes

C = dict(r="\033[0m", b="\033[1m", dim="\033[2m", red="\033[91m", grn="\033[92m",
         ylw="\033[93m", blu="\033[94m", cyn="\033[96m", inv="\033[7m")
if not sys.stdout.isatty() or "--no-color" in sys.argv:
    C = {k: "" for k in C}

TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]
TRAIN_FT = ["2017-07-01", "2017-10-01"]
TRAIN_SQ = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01"]

def rule(ch="─", n=78): return ch * n
def head(i, title, sub):
    print(f"\n{C['b']}{C['blu']}{rule('━')}{C['r']}")
    print(f"{C['b']}  СЦЕНА {i}. {title}{C['r']}")
    print(f"{C['dim']}  {sub}{C['r']}")
    print(f"{C['b']}{C['blu']}{rule('━')}{C['r']}")

def verdict_box(v, secs):
    if v.leak:
        print(f"\n  {C['inv']}{C['red']}  ВЕРДИКТ: УТЕЧКА  {C['r']}   "
              f"{C['dim']}дифференциальное исполнение, {secs:.1f} с{C['r']}")
        print(f"  расходятся колонки ({len(v.columns)}): {C['red']}{', '.join(v.columns[:8])}"
              f"{' …' if len(v.columns) > 8 else ''}{C['r']}")
        print(f"  расхождений в значениях: {C['red']}{v.cells}{C['r']}")
        print(f"  {C['dim']}это доказательство, а не подозрение: те же входы, другой ответ{C['r']}")
    else:
        print(f"\n  {C['inv']}{C['grn']}  ВЕРДИКТ: ЧИСТО  {C['r']}   "
              f"{C['dim']}дифференциальное исполнение, {secs:.1f} с{C['r']}")
        print(f"  {C['dim']}выход побитово совпал на полной и на усечённой базе{C['r']}")

def probe_line(a, who):
    s = probe_says(a)
    col = C['red'] if s == "молчит" else C['ylw']
    print(f"  промышленная проверка «макс AUC одного признака»: {a:.3f}"
          f"  ({C['dim']}сильнейший: {who}{C['r']})")
    print(f"  порог DataRobot {DATAROBOT[0]} / {DATAROBOT[1]}  →  {col}{C['b']}{s.upper()}{C['r']}")

def evaluate(program, db, labeler, train_seeds, test_seeds):
    """AUC фиксированной модели и значение промышленной проверки на каждом моменте."""
    out = []
    for ts in test_seeds:
        Xtr, ytr = [], []
        for s in [x for x in train_seeds if x < ts]:
            sd, ent, y = labeler(db, s)
            if len(ent) < 30 or y.nunique() < 2: continue
            Xtr.append(program(db, sd, ent)); ytr.append(y)
        Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
        sd, ent, yte = labeler(db, ts)
        Xte = program(db, sd, ent)
        auc = fixed_model_auc(Xtr, ytr, Xte, yte)
        pa, who = univariate_probe(Xte, yte)
        out.append(dict(seed=ts, n=int(len(ent)), auc=float(auc), probe=float(pa), feature=who))
    return out

def scene(i, title, sub, program, ref_program, db, labeler, train_seeds, oracle_seed, results):
    head(i, title, sub)
    sd, ent, _ = labeler(db, oracle_seed)
    print(f"  момент предсказания {oracle_seed}, сущностей {len(ent)}")
    t0 = time.time(); v = differential_check(program, db, sd, ent); dt = time.time() - t0
    verdict_box(v, dt)
    got = evaluate(program, db, labeler, train_seeds, TESTS)
    ref = evaluate(ref_program, db, labeler, train_seeds, TESTS) if ref_program else None
    print()
    print(f"  {C['b']}{'момент':12s}{'AUC':>9s}{'корректно':>12s}{'завышение':>12s}{'проверка':>11s}{C['r']}")
    for k, g in enumerate(got):
        infl = (g["auc"] - ref[k]["auc"]) * 100 if ref else 0.0
        ic = C['red'] if infl >= 3 else (C['ylw'] if infl >= 1 else C['grn'])
        print(f"  {g['seed']:12s}{g['auc']:9.4f}"
              f"{(ref[k]['auc'] if ref else g['auc']):12.4f}"
              f"{ic}{infl:+11.2f}{C['r']} п.п.{g['probe']:8.3f}")
    print()
    probe_line(got[1]["probe"], got[1]["feature"])
    results.append(dict(scene=i, title=title, verdict=v.label, columns=v.columns,
                        cells=v.cells, seconds=round(dt, 2), rows=got,
                        inflation=[round((g["auc"] - ref[k]["auc"]) * 100, 2) for k, g in enumerate(got)] if ref else None))
    return v

def main():
    only = next((a for a in sys.argv[1:] if a.isdigit()), None)
    print(f"{C['b']}{C['cyn']}\n  PITFALL — корректность признаков по времени через дифференциальное исполнение{C['r']}")
    print(f"  {C['dim']}phi(D, t) == phi(D|t, t).  Программа — чёрный ящик, вызываемый дважды.{C['r']}")
    print(f"  {C['dim']}Данные: Olist, 7 таблиц, 112 650 позиций заказов, 2016-09 — 2018-10{C['r']}")
    db = scenes.olist_db()
    res = []
    if only in (None, "1"):
        scene(1, "featuretools с настройками по умолчанию",
              "ft.dfs без таблицы моментов предсказания — так написано в туториале библиотеки",
              scenes.ft_tutorial, scenes.ft_cutoff, db, scenes.product_labels, TRAIN_FT, "2018-04-01", res)
    if only in (None, "2"):
        scene(2, "наш собственный эталон, первая версия",
              "фильтр по времени заказа; у отзыва и факта доставки своя, более поздняя метка",
              scenes.seller_v1, scenes.seller_v2, db, scenes.seller_quality_labels, TRAIN_SQ, "2018-04-01", res)
    if only in (None, "3"):
        scene(3, "тот же эталон после исправления",
              "у каждой колонки собственная метка доступности; больше ничего не изменено",
              scenes.seller_v2, None, db, scenes.seller_quality_labels, TRAIN_SQ, "2018-04-01", res)
    if only is None:
        print(f"\n{C['b']}{C['blu']}{rule('━')}{C['r']}")
        print(f"{C['b']}  ИТОГ{C['r']}")
        print(f"{C['b']}{C['blu']}{rule('━')}{C['r']}")
        print(f"  {C['b']}{'сцена':42s}{'оракул':>9s}{'проверка':>15s}{'завышение':>12s}{C['r']}")
        for r in res:
            vc = C['red'] if r["verdict"] == "УТЕЧКА" else C['grn']
            silent = probe_says(r["rows"][1]["probe"]) == "молчит"
            if r["verdict"] == "УТЕЧКА":
                pv, pc = ("ПРОПУСК" if silent else "поймала"), (C['red'] if silent else C['ylw'])
            else:
                pv, pc = ("верно" if silent else "ЛОЖНАЯ ТРЕВОГА"), (C['grn'] if silent else C['red'])
            infl = max(r["inflation"]) if r["inflation"] else 0.0
            print(f"  {r['title'][:42]:42s}{vc}{r['verdict']:>9s}{C['r']}{pc}{pv:>15s}{C['r']}"
                  f"{infl:>+9.1f} п.п.")
        print(f"\n  {C['dim']}Оракул срабатывает там, где промышленная проверка молчит, и молчит{C['r']}")
        print(f"  {C['dim']}там, где код корректен. Он ничего не разбирает — только сравнивает выход.{C['r']}\n")
    json.dump(res, open(_ROOT + "/demo/demo_results.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
