#!/usr/bin/env python3
"""
PITFALL — demonstration. Four scenes, every number is computed live.

  Scene 1  featuretools with default settings                 expected VIOLATION
  Scene 2  our own reference code, first version              expected VIOLATION
  Scene 3  the same reference code after the fix              expected CLEAN
  Scene 4  LOCATOR: which channels leak, minimal patch, re-check   expected CLEAN

    python3 demo.py              all scenes
    python3 demo.py 2            one scene
    python3 demo.py --lang ru    Russian labels (default: English)
    python3 demo.py --no-color   plain output for logs
    python3 demo.py --program my_feats.py[:func] [--task seller|product]
                                 check + localise YOUR feature function
                                 signature: func(db, seed_time, entities) -> DataFrame
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import sys, json, time, warnings
if "--lang" in sys.argv:
    _os.environ["PITFALL_LANG"] = sys.argv[sys.argv.index("--lang") + 1]
LANG = _os.environ.get("PITFALL_LANG", "en")
import numpy as np, pandas as pd
sys.path.insert(0, _ROOT + "/demo")
warnings.filterwarnings("ignore")
from pitfall import (differential_check, univariate_probe, probe_says, fixed_model_auc,
                     DATAROBOT, H2O, locate, masked_program)
import scenes

C = dict(r="\033[0m", b="\033[1m", dim="\033[2m", red="\033[91m", grn="\033[92m",
         ylw="\033[93m", blu="\033[94m", cyn="\033[96m", inv="\033[7m")
if not sys.stdout.isatty() or "--no-color" in sys.argv:
    C = {k: "" for k in C}

TESTS = ["2018-01-01", "2018-04-01", "2018-07-01"]
TRAIN_FT = ["2017-07-01", "2017-10-01"]
TRAIN_SQ = ["2017-04-01", "2017-07-01", "2017-10-01", "2018-01-01", "2018-04-01"]

# ───────────────────────────── strings ─────────────────────────────
S = {
 "en": dict(
    banner="PITFALL — point-in-time correctness of feature programs by differential execution",
    banner2="phi(D, t) == phi(D|t, t).  The program is a black box, called twice.",
    data="Data: Olist, 7 tables, 112,650 order line items, 2016-09 — 2018-10",
    scene="SCENE", seed="seed time {seed}, entities {n}",
    verdict="VERDICT", diffexec="differential execution, {s:.1f} s",
    cols="diverging columns ({n}): ", cells="diverging cells: ",
    proof="a proof, not a suspicion: same inputs, different answer",
    same="output identical on the full and on the truncated database",
    hdr=("seed", "AUC", "correct", "inflation", "probe"), pp="pp",
    probe="industrial probe «max single-feature AUC»: {a:.3f}  (strongest: {who})",
    thr="DataRobot {d0} / {d1} → {ds};   H2O DAI {h0} / {h1} / {h2} → {hs}",
    s1=("featuretools with default settings",
        "ft.dfs without a cutoff-time table — the form of the library's introductory example"),
    s2=("our own reference code, first version",
        "history filtered by order time; review and delivery carry their own, later timestamps"),
    s3=("the same reference code after the fix",
        "every column has its own availability timestamp; nothing else changed"),
    s4=("LOCATOR: where exactly it leaks, and a patch",
        "truncate one availability channel at a time; the program is still not read"),
    p1="scene 1: featuretools defaults", p2="scene 2: our reference code, v1",
    chans="{n} availability channels, seed time {seed}",
    patch="patch: truncate the input on the {n} channel(s) found, nothing else  →  ",
    loc="localisation {a:.1f} s, re-check {b:.1f} s", cellsn="({n} cells)",
    summary="SUMMARY", shdr=("scene", "checker", "probe@0.85", "inflation"),
    miss="MISSED", caught="caught", ok="correct", fa="FALSE ALARM", patchto="patch → ",
    tail1="The checker fires where the industrial probe is silent, and stays silent where the code",
    tail2="is correct. It parses nothing — it only compares outputs.",
 ),
 "ru": dict(
    banner="PITFALL — корректность признаков по времени через дифференциальное исполнение",
    banner2="phi(D, t) == phi(D|t, t).  Программа — чёрный ящик, вызываемый дважды.",
    data="Данные: Olist, 7 таблиц, 112 650 позиций заказов, 2016-09 — 2018-10",
    scene="СЦЕНА", seed="момент предсказания {seed}, сущностей {n}",
    verdict="ВЕРДИКТ", diffexec="дифференциальное исполнение, {s:.1f} с",
    cols="расходятся колонки ({n}): ", cells="расхождений в значениях: ",
    proof="это доказательство, а не подозрение: те же входы, другой ответ",
    same="выход побитово совпал на полной и на усечённой базе",
    hdr=("момент", "AUC", "корректно", "завышение", "проверка"), pp="п.п.",
    probe="промышленная проверка «макс AUC одного признака»: {a:.3f}  (сильнейший: {who})",
    thr="DataRobot {d0} / {d1} → {ds};   H2O DAI {h0} / {h1} / {h2} → {hs}",
    s1=("featuretools с настройками по умолчанию",
        "ft.dfs без таблицы моментов предсказания — форма вводного примера библиотеки"),
    s2=("наш собственный эталон, первая версия",
        "фильтр по времени заказа; у отзыва и факта доставки своя, более поздняя метка"),
    s3=("тот же эталон после исправления",
        "у каждой колонки собственная метка доступности; больше ничего не изменено"),
    s4=("LOCATOR: откуда именно течёт, и патч",
        "усечение по одному каналу за раз; код программы по-прежнему не читается"),
    p1="сцена 1: featuretools по умолчанию", p2="сцена 2: наш эталон, первая версия",
    chans="{n} каналов доступности, момент {seed}",
    patch="патч: усечь вход по {n} найденным каналам, больше ничего  →  ",
    loc="локализация {a:.1f} с, перепроверка {b:.1f} с", cellsn="({n} ячеек)",
    summary="ИТОГ", shdr=("сцена", "оракул", "проверка@0.85", "завышение"),
    miss="ПРОПУСК", caught="поймала", ok="верно", fa="ЛОЖНАЯ ТРЕВОГА", patchto="патч → ",
    tail1="Оракул срабатывает там, где промышленная проверка молчит, и молчит",
    tail2="там, где код корректен. Он ничего не разбирает — только сравнивает выход.",
 )}[LANG]

def rule(ch="─", n=78): return ch * n
def head(i, title, sub):
    print(f"\n{C['b']}{C['blu']}{rule('━')}{C['r']}")
    print(f"{C['b']}  {S['scene']} {i}. {title}{C['r']}")
    print(f"{C['dim']}  {sub}{C['r']}")
    print(f"{C['b']}{C['blu']}{rule('━')}{C['r']}")

def verdict_box(v, secs):
    col = C['red'] if v.leak else C['grn']
    print(f"\n  {C['inv']}{col}  {S['verdict']}: {v.label}  {C['r']}   "
          f"{C['dim']}{S['diffexec'].format(s=secs)}{C['r']}")
    if v.leak:
        print(f"  {S['cols'].format(n=len(v.columns))}{C['red']}{', '.join(v.columns[:8])}"
              f"{' …' if len(v.columns) > 8 else ''}{C['r']}")
        print(f"  {S['cells']}{C['red']}{v.cells}{C['r']}")
        print(f"  {C['dim']}{S['proof']}{C['r']}")
    else:
        print(f"  {C['dim']}{S['same']}{C['r']}")

def probe_line(a, who):
    ds, hs = probe_says(a, DATAROBOT), probe_says(a, H2O)
    print(f"  {S['probe'].format(a=a, who=who)}")
    cd = C['red'] if ds == "silent" else C['ylw']; ch = C['red'] if hs == "silent" else C['ylw']
    print(f"  {S['thr'].format(d0=DATAROBOT[0], d1=DATAROBOT[1], ds=cd + C['b'] + ds.upper() + C['r'], h0=H2O[0], h1=H2O[1], h2=H2O[2], hs=ch + C['b'] + hs.upper() + C['r'])}")

def evaluate(program, db, labeler, train_seeds, test_seeds):
    """Fixed-model AUC and the industrial probe value at every test seed time."""
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

def scene(i, key, program, ref_program, db, labeler, train_seeds, oracle_seed, results):
    title, sub = S[key]
    head(i, title, sub)
    sd, ent, _ = labeler(db, oracle_seed)
    print(f"  {S['seed'].format(seed=oracle_seed, n=len(ent))}")
    t0 = time.time(); v = differential_check(program, db, sd, ent); dt = time.time() - t0
    verdict_box(v, dt)
    got = evaluate(program, db, labeler, train_seeds, TESTS)
    ref = evaluate(ref_program, db, labeler, train_seeds, TESTS) if ref_program else None
    h = S['hdr']
    print(f"\n  {C['b']}{h[0]:12s}{h[1]:>9s}{h[2]:>12s}{h[3]:>12s}{h[4]:>11s}{C['r']}")
    for k, g in enumerate(got):
        infl = (g["auc"] - ref[k]["auc"]) * 100 if ref else 0.0
        ic = C['red'] if infl >= 3 else (C['ylw'] if infl >= 1 else C['grn'])
        print(f"  {g['seed']:12s}{g['auc']:9.4f}{(ref[k]['auc'] if ref else g['auc']):12.4f}"
              f"{ic}{infl:+11.2f}{C['r']} {S['pp']}{g['probe']:8.3f}")
    print()
    probe_line(got[1]["probe"], got[1]["feature"])
    results.append(dict(scene=i, key=key, title=title, leak=v.leak, verdict=v.label, columns=v.columns,
                        cells=v.cells, seconds=round(dt, 2), rows=got,
                        inflation=[round((g["auc"] - ref[k]["auc"]) * 100, 2) for k, g in enumerate(got)] if ref else None))
    return v

def scene_locate(i, programs, db, results):
    """LOCATOR: truncate one channel at a time; a channel on which the output changes is a
    leak path. The patch is the same program with its input truncated on those channels only."""
    title, sub = S["s4"]
    head(i, title, sub)
    out = []
    for pkey, program, labeler, oracle_seed in programs:
        sd, ent, _ = labeler(db, oracle_seed)
        print(f"\n  {C['b']}{S[pkey]}{C['r']}  {C['dim']}({S['chans'].format(n=len(db.channels()), seed=oracle_seed)}){C['r']}")
        t0 = time.time(); bl = locate(program, db, sd, ent); dt = time.time() - t0
        for b in bl:
            print(f"    {C['red']}▶ {b.label:42s}{C['r']} → {', '.join(b.columns[:5])}"
                  f"{' …' if len(b.columns) > 5 else ''}  {C['dim']}{S['cellsn'].format(n=b.cells)}{C['r']}")
        chans = [b.channel for b in bl]
        t1 = time.time(); v = differential_check(masked_program(program, chans), db, sd, ent); dp = time.time() - t1
        print(f"    {S['patch'].format(n=len(chans))}{C['grn'] if not v.leak else C['red']}{C['b']}{v.label}{C['r']}  "
              f"{C['dim']}{S['loc'].format(a=dt, b=dp)}{C['r']}")
        out.append(dict(program=S[pkey], key=pkey, seconds=round(dt, 2),
                        blame=[dict(channel=list(b.channel), label=b.label, columns=b.columns, cells=b.cells) for b in bl],
                        patched_leak=v.leak, patched_verdict=v.label, n_channels=len(db.channels())))
    results.append(dict(scene=i, key="s4", title=title, programs=out))

def check_user_program(path, task, db):
    """Try to beat the checker: load func(db, t, entities) from a file, check it, localise."""
    import importlib.util
    file, _, fn = path.partition(":")
    spec = importlib.util.spec_from_file_location("user_program", file)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    program = getattr(mod, fn or "features")
    labeler = scenes.product_labels if task == "product" else scenes.seller_quality_labels
    head("U", f"{file}:{program.__name__}", S["s4"][1])
    sd, ent, _ = labeler(db, "2018-04-01")
    print(f"  {S['seed'].format(seed='2018-04-01', n=len(ent))}")
    t0 = time.time(); v = differential_check(program, db, sd, ent); dt = time.time() - t0
    verdict_box(v, dt)
    if v.leak:
        t0 = time.time(); bl = locate(program, db, sd, ent); dt = time.time() - t0
        for b in bl:
            print(f"    {C['red']}▶ {b.label:42s}{C['r']} → {', '.join(b.columns[:5])}"
                  f"{' …' if len(b.columns) > 5 else ''}  {C['dim']}{S['cellsn'].format(n=b.cells)}{C['r']}")
        chans = [b.channel for b in bl]
        v2 = differential_check(masked_program(program, chans), db, sd, ent)
        print(f"    {S['patch'].format(n=len(chans))}{C['grn'] if not v2.leak else C['red']}{C['b']}{v2.label}{C['r']}  "
              f"{C['dim']}{S['loc'].format(a=dt, b=0)}{C['r']}")
    print()

def main():
    if "--program" in sys.argv:
        path = sys.argv[sys.argv.index("--program") + 1]
        task = sys.argv[sys.argv.index("--task") + 1] if "--task" in sys.argv else "seller"
        check_user_program(path, task, scenes.olist_db()); return
    only = next((a for a in sys.argv[1:] if a.isdigit()), None)
    print(f"{C['b']}{C['cyn']}\n  {S['banner']}{C['r']}")
    print(f"  {C['dim']}{S['banner2']}{C['r']}")
    print(f"  {C['dim']}{S['data']}{C['r']}")
    db = scenes.olist_db()
    res = []
    if only in (None, "1"):
        scene(1, "s1", scenes.ft_tutorial, scenes.ft_cutoff, db, scenes.product_labels, TRAIN_FT, "2018-04-01", res)
    if only in (None, "2"):
        scene(2, "s2", scenes.seller_v1, scenes.seller_v2, db, scenes.seller_quality_labels, TRAIN_SQ, "2018-04-01", res)
    if only in (None, "3"):
        scene(3, "s3", scenes.seller_v2, None, db, scenes.seller_quality_labels, TRAIN_SQ, "2018-04-01", res)
    if only in (None, "4"):
        scene_locate(4, [("p2", scenes.seller_v1, scenes.seller_quality_labels, "2018-04-01"),
                         ("p1", scenes.ft_tutorial, scenes.product_labels, "2018-04-01")], db, res)
    if only is None:
        h = S['shdr']
        print(f"\n{C['b']}{C['blu']}{rule('━')}{C['r']}")
        print(f"{C['b']}  {S['summary']}{C['r']}")
        print(f"{C['b']}{C['blu']}{rule('━')}{C['r']}")
        print(f"  {C['b']}{h[0]:42s}{h[1]:>9s}{h[2]:>15s}{h[3]:>12s}{C['r']}")
        for r in res:
            if "programs" in r:
                for pr in r["programs"]:
                    print(f"  LOCATOR ← {pr['program'][:32]:32s}{'':>9s}{S['patchto'] + pr['patched_verdict']:>15s}"
                          f"  {len(pr['blame'])}: {'; '.join(b['label'].split(':')[0] for b in pr['blame'])}")
                continue
            vc = C['red'] if r["leak"] else C['grn']
            silent = probe_says(r["rows"][1]["probe"]) == "silent"
            if r["leak"]:
                pv, pc = (S['miss'] if silent else S['caught']), (C['red'] if silent else C['ylw'])
            else:
                pv, pc = (S['ok'] if silent else S['fa']), (C['grn'] if silent else C['red'])
            infl = max(r["inflation"]) if r["inflation"] else 0.0
            print(f"  {r['title'][:42]:42s}{vc}{r['verdict']:>9s}{C['r']}{pc}{pv:>15s}{C['r']}"
                  f"{infl:>+9.1f} {S['pp']}")
        print(f"\n  {C['dim']}{S['tail1']}{C['r']}")
        print(f"  {C['dim']}{S['tail2']}{C['r']}\n")
    json.dump(res, open(_ROOT + "/demo/demo_results.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
