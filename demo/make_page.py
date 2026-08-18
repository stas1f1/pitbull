# -*- coding: utf-8 -*-
"""Builds the self-contained demo page pitfall_demo.html from demo_results.json.

    python3 make_page.py            English (default)
    python3 make_page.py --lang ru  Russian → pitfall_demo_ru.html
"""
import os as _os, sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
import json, html

LANG = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else _os.environ.get("PITFALL_LANG", "en")
R = json.load(open(_ROOT + "/demo/demo_results.json"))
NAVY, DEEP, ICE, TINT = "#1E2761", "#141B3D", "#CADCFC", "#F1F4FB"
GRN, AMB, RED = "#1F7A55", "#B57314", "#A62B22"

T = {
 "en": dict(
  kicker="PITFALL · demonstration", h1="Point-in-time correctness of feature programs by differential execution",
  claim="A feature program is point-in-time correct if and only if its output does not change when everything "
        "that did not yet exist at the seed time is physically removed from the database. We parse neither code "
        "nor SQL: the program is a black box, called twice. A divergence of the outputs is a <b>proof</b> of "
        "violation, not a suspicion.",
  scene="Scene", leak="VIOLATION", clean="CLEAN", miss="MISSED", caught="caught", ok="correctly silent", fa="FALSE ALARM",
  diff="Differential execution", probe="Industrial probe «max single-feature AUC»",
  meta="{s:.1f} s · diverging columns {c} · diverging cells {n}", same="output identical on the full and on the truncated database",
  pmeta="value {p:.3f} · DataRobot 0.85 / 0.975 → {ds} · H2O DAI 0.80 / 0.95 / 0.999 → {hs}",
  strongest="strongest feature:", th=("seed time", "entities", "AUC", "correct version", "inflation, pp", "probe"),
  sub={1: ("<code>ft.dfs</code> without a cutoff-time table — the form of the library's introductory example. "
           "Task: product demand. featuretools 1.31.0, 13 features, depth 2.",
           "This is the library's behaviour when no cutoff-time table is passed, not our simulation."),
       2: ("History filtered by order time. The review and the delivery outcome carry their own, later "
           "timestamps: median +10 days, 90th percentile +23, maximum +147. Task: seller review quality.",
           "The defect in this code was found by the checker, not by a person. The code was written by the checker's authors."),
       3: ("Every column has its own availability timestamp. Nothing else in the program changed.",
           "Negative control: the method does not fire on correct code.")},
  s4h="LOCATOR: where exactly it leaks, and a patch",
  s4sub="The database is truncated on <b>one availability channel</b> at a time (rows of a table appearing after "
        "<i>t</i>, or a column value becoming known after <i>t</i>); a channel on which the program's output changes "
        "is a leak path. The program is still not read: as many calls as there are channels.",
  s4meta="{p} · {k} channel(s) of {n} · {s:.1f} s", s4th=("availability channel", "affected output columns", "cells"),
  s4patch="patch: the same program, input truncated on the channels found only →",
  s4note="The patch is minimal and does not touch the code: the input is truncated on the channels found, and the "
         "verdict flips to CLEAN. For our own reference code this is exactly the fix made in Scene 3.",
  foot_h="What the scenes show together",
  foot=["<b>The checker fires where the industrial probe is silent.</b> On both violations the maximum single-feature "
        "AUC stays below the DataRobot warning threshold of 0.85 — a clean bill — while the offline estimate is inflated "
        "by 16.3 and 5.3 points. At the H2O threshold of 0.80 the probe warns on scene 1 at two seed times of three, "
        "but also warns on the <i>correct</i> seller-activity pipeline at all three.",
        "<b>And stays silent where the code is correct.</b> Scene 3 is the same program with the availability "
        "relation fixed: the outputs coincide bit for bit; there are no false positives by construction.",
        "<b>The cost of a violation is not implied by the violation.</b> The same defect costs 0.2 points on a churn "
        "task and 3–5 points on a quality task: what matters is how much the target leans on the leaked columns. "
        "Correctness therefore has to be tested separately from the metric.",
        "<b>Localisation uses the same trick.</b> Scene 4: truncating one channel at a time names the table and column "
        "through which the future reaches the output, and the minimal patch after which the verdict is CLEAN."],
  lim_h="Limits of the method — to be named first",
  lim=["<b>A mutable field without history is undecidable.</b> <code>order_status</code> has no timestamp: the moment "
       "an order became cancelled is not in the data. The truncated database is indistinguishable from the full one "
       "for such a column, and the method does not apply.",
       "<b>A non-deterministic program</b> diverges without leaking — a fixed seed is required.",
       "<b>Misses are possible:</b> a violation that does not manifest at the tested seed time is not seen there. "
       "There are no false positives — the asymmetry is deliberate.",
       "<b>One database, three tasks, three seed times.</b> A preliminary result; RelBench was unreachable from the "
       "experiment network, the task structure was reproduced from its description."],
  data="Data: Olist, 7 tables, 112,650 order line items, September 2016 — October 2018. Everything is computed live "
       "on 2 CPU cores: <code>python3 demo.py</code>. One and the same model with a fixed seed everywhere — swapping "
       "the booster alone moves AUC by up to 11.5 pp.",
  title="PITFALL — point-in-time correctness", out="pitfall_demo.html",
 ),
 "ru": dict(
  kicker="PITFALL · демонстрация", h1="Корректность признаков по времени через дифференциальное исполнение",
  claim="Программа признаков корректна тогда и только тогда, когда её выход не меняется, если из базы физически "
        "удалить всё, чего на момент предсказания ещё не существовало. Мы не разбираем ни код, ни SQL: программа — "
        "чёрный ящик, вызываемый дважды. Расхождение выходов есть <b>доказательство</b> нарушения, а не подозрение.",
  scene="Сцена", leak="УТЕЧКА", clean="ЧИСТО", miss="ПРОПУСК", caught="поймала", ok="верно молчит", fa="ЛОЖНАЯ ТРЕВОГА",
  diff="Дифференциальное исполнение", probe="Промышленная проверка «макс AUC одного признака»",
  meta="{s:.1f} с · расходящихся колонок {c} · расхождений в значениях {n}", same="выход побитово совпал на полной и на усечённой базе",
  pmeta="значение {p:.3f} · DataRobot 0.85 / 0.975 → {ds} · H2O DAI 0.80 / 0.95 / 0.999 → {hs}",
  strongest="сильнейший признак:", th=("момент предсказания", "сущностей", "AUC", "корректная версия", "завышение, п.п.", "проверка"),
  sub={1: ("<code>ft.dfs</code> без таблицы моментов предсказания — форма вводного примера библиотеки. "
           "Задача: спрос на товар. featuretools 1.31.0, 13 признаков, глубина 2.",
           "Это поведение библиотеки без таблицы моментов, а не наша симуляция."),
       2: ("Фильтр по времени заказа. У отзыва и у факта доставки собственная, более поздняя метка: "
           "медиана +10 дней, 90-й перцентиль +23, максимум +147. Задача: качество продавца.",
           "Ошибку в этом коде нашёл оракул, а не человек. Код писали авторы проверки."),
       3: ("У каждой колонки собственная метка доступности. Больше в программе не изменено ничего.",
           "Отрицательный контроль: метод не срабатывает на корректном коде.")},
  s4h="LOCATOR: откуда именно течёт, и патч",
  s4sub="База усекается по <b>одному каналу доступности</b> за раз (появление строки таблицы после <i>t</i> или "
        "позднее значение колонки); канал, на котором выход программы меняется, — путь утечки. Код программы "
        "по-прежнему не читается: столько же вызовов, сколько каналов.",
  s4meta="{p} · {k} канал(а) из {n} · {s:.1f} с", s4th=("канал доступности", "затронутые выходные колонки", "ячеек"),
  s4patch="патч: та же программа, вход усечён только по найденным каналам →",
  s4note="Патч минимален и не трогает код: вход усекается по найденным каналам, и вердикт меняется на ЧИСТО. "
         "Для собственного эталона это ровно то исправление, которое сделано в сцене 3.",
  foot_h="Что показывают сцены вместе",
  foot=["<b>Проверка срабатывает там, где промышленная молчит.</b> На обеих утечках максимальный AUC одного признака "
        "не доходит до порога предупреждения DataRobot 0.85 — заключение чистое, а офлайн-оценка завышена на 16.3 и "
        "5.3 пункта. При пороге H2O 0.80 проверка предупреждает на сцене 1 в двух моментах из трёх — но и на "
        "<i>корректном</i> пайплайне задачи про активность продавца во всех трёх.",
        "<b>И молчит там, где код корректен.</b> Сцена 3 — та же программа с исправленным отношением доступности: "
        "выход совпадает побитово, ложных срабатываний нет по построению.",
        "<b>Цена утечки не выводится из факта утечки.</b> Одно и то же нарушение стоит 0.2 пункта на задаче про "
        "отток и 3–5 пунктов на задаче про качество: всё решает, насколько цель опирается на протёкшие колонки. "
        "Поэтому корректность надо проверять отдельно от метрики.",
        "<b>Локализация — тем же приёмом.</b> Сцена 4: усечение по одному каналу за раз называет таблицу и колонку, "
        "через которые будущее попадает в выход, и минимальный патч, после которого вердикт — ЧИСТО."],
  lim_h="Границы метода — их надо называть первыми",
  lim=["<b>Изменяемое поле без истории непроверяемо.</b> У <code>order_status</code> нет метки времени: момента, "
       "когда заказ стал отменённым, в данных нет. Усечённая база для такой колонки неотличима от полной, и метод к "
       "ней неприменим.",
       "<b>Недетерминированная программа</b> даёт расхождение без утечки — нужен фиксированный seed.",
       "<b>Пропуски возможны:</b> утечка, не проявившаяся на конкретном моменте t, на нём не видна. Ложных "
       "срабатываний при этом нет — асимметрия сознательная.",
       "<b>Одна база, три задачи, три момента.</b> Предварительный результат; RelBench недоступен из сети "
       "эксперимента, структура задач воспроизведена по описанию."],
  data="Данные: Olist, 7 таблиц, 112 650 позиций заказов, сентябрь 2016 — октябрь 2018. Всё считается вживую на "
       "2 ядрах CPU: <code>python3 demo.py</code>. Модель везде одна и та же с фиксированным seed — смена бустера "
       "сама по себе даёт до 11.5 п.п.",
  title="PITFALL — корректность признаков по времени", out="pitfall_demo_ru.html",
 )}[LANG]

def says(a, th):
    return "auto-drop" if a >= th[-1] else ("warning" if a >= th[0] else "silent")

def chip(leak):
    return f'<span class="chip" style="background:{RED if leak else GRN}">{T["leak"] if leak else T["clean"]}</span>'

def probe_verdict(r):
    silent = r["rows"][1]["probe"] < 0.85
    if r["leak"]:
        return (T["miss"], RED) if silent else (T["caught"], AMB)
    return (T["ok"], GRN) if silent else (T["fa"], RED)

def scene_title(r):
    # titles are stored in the language demo.py was run with; re-map by key for the page
    key = r.get("key")
    m = {"s1": {"en": "featuretools with default settings", "ru": "featuretools с настройками по умолчанию"},
         "s2": {"en": "our own reference code, first version", "ru": "наш собственный эталон, первая версия"},
         "s3": {"en": "the same reference code after the fix", "ru": "тот же эталон после исправления"},
         "p1": {"en": "scene 1: featuretools defaults", "ru": "сцена 1: featuretools по умолчанию"},
         "p2": {"en": "scene 2: our reference code, v1", "ru": "сцена 2: наш эталон, первая версия"}}
    return m.get(key, {}).get(LANG, r.get("title", ""))

cards = []
for r in R:
    if "programs" in r:      # LOCATOR scene
        blocks = ""
        for pr in r["programs"]:
            rows = "".join(
                f"<tr><td><b>{html.escape(b['label'])}</b></td>"
                f"<td>{' '.join('<code>' + html.escape(c) + '</code>' for c in b['columns'][:6])}"
                f"{' …' if len(b['columns']) > 6 else ''}</td><td class='n'>{b['cells']}</td></tr>"
                for b in pr["blame"])
            ok = not pr["patched_leak"]
            blocks += f"""
      <div class="panel" style="margin-bottom:14px">
        <div class="lbl">{T['s4meta'].format(p=html.escape(scene_title(pr)), k=len(pr['blame']), n=pr.get('n_channels', 7), s=pr['seconds'])}</div>
        <table><thead><tr><th>{T['s4th'][0]}</th><th>{T['s4th'][1]}</th><th class="n">{T['s4th'][2]}</th></tr></thead>
        <tbody>{rows}</tbody></table>
        <div class="meta" style="margin-top:10px">{T['s4patch']}
          <b style="color:{GRN if ok else RED}">{T['clean'] if ok else T['leak']}</b></div>
      </div>"""
        cards.append(f"""
    <section class="card">
      <div class="hdr"><span class="num">{T['scene']} {r['scene']}</span>
        <h2>{T['s4h']}</h2>{chip(False)}</div>
      <p class="sub">{T['s4sub']}</p>
      {blocks}
      <p class="note">{T['s4note']}</p>
    </section>""")
        continue
    body, note = T["sub"][r["scene"]]
    pv, pc = probe_verdict(r)
    rows = ""
    for k, g in enumerate(r["rows"]):
        infl = r["inflation"][k] if r["inflation"] else 0.0
        ic = RED if infl >= 3 else (AMB if infl >= 1 else "#5b6478")
        base = g["auc"] - infl / 100
        rows += (f"<tr><td>{g['seed']}</td><td class='n'>{g['n']}</td>"
                 f"<td class='n'>{g['auc']:.4f}</td><td class='n dim'>{base:.4f}</td>"
                 f"<td class='n' style='color:{ic};font-weight:600'>{infl:+.2f}</td>"
                 f"<td class='n'>{g['probe']:.3f}</td></tr>")
    cols = ("<div class='cols'>" + " ".join(
        f"<code>{html.escape(c)}</code>" for c in r["columns"]) + "</div>") if r["columns"] else \
        f"<div class='cols dim'>{T['same']}</div>"
    p = r["rows"][1]["probe"]
    th = T["th"]
    cards.append(f"""
    <section class="card">
      <div class="hdr"><span class="num">{T['scene']} {r['scene']}</span>
        <h2>{html.escape(scene_title(r))}</h2>{chip(r['leak'])}</div>
      <p class="sub">{body}</p>
      <div class="grid">
        <div class="panel">
          <div class="lbl">{T['diff']}</div>
          <div class="big" style="color:{RED if r['leak'] else GRN}">{T['leak'] if r['leak'] else T['clean']}</div>
          <div class="meta">{T['meta'].format(s=r['seconds'], c=len(r['columns']), n=r['cells'])}</div>
          {cols}
        </div>
        <div class="panel">
          <div class="lbl">{T['probe']}</div>
          <div class="big" style="color:{pc}">{pv}</div>
          <div class="meta">{T['pmeta'].format(p=p, ds=says(p, (0.85, 0.975)), hs=says(p, (0.80, 0.95, 0.999)))}</div>
          <div class="cols dim">{T['strongest']} <code>{html.escape(str(r['rows'][1]['feature']))}</code></div>
        </div>
      </div>
      <table><thead><tr><th>{th[0]}</th><th class="n">{th[1]}</th>
        <th class="n">{th[2]}</th><th class="n">{th[3]}</th>
        <th class="n">{th[4]}</th><th class="n">{th[5]}</th></tr></thead>
        <tbody>{rows}</tbody></table>
      <p class="note">{note}</p>
    </section>""")

li = lambda xs: "".join(f"<li>{x}</li>" for x in xs)
page = f"""<!doctype html><html lang="{LANG}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{T['title']}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:{TINT};color:{DEEP};
 font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px 64px}}
header{{background:{DEEP};color:{ICE};padding:48px 0 40px;margin-bottom:32px}}
header .wrap{{padding-bottom:0}}
h1{{margin:0 0 8px;font-size:34px;letter-spacing:-.5px;color:#fff}}
.kicker{{font-size:13px;letter-spacing:2.4px;text-transform:uppercase;opacity:.72;margin-bottom:14px}}
.claim{{font-size:19px;max-width:760px;opacity:.94}}
.formula{{display:inline-block;margin-top:20px;padding:10px 16px;border:1px solid rgba(202,220,252,.35);
 border-radius:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:15px}}
.card{{background:#fff;border:1px solid #dde3f0;border-radius:14px;padding:26px 28px;margin-bottom:22px;
 box-shadow:0 1px 2px rgba(20,27,61,.05)}}
.hdr{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:6px}}
.num{{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#7d87a3}}
h2{{margin:0;font-size:21px;letter-spacing:-.2px;flex:1;min-width:260px}}
.chip{{color:#fff;font-size:12px;font-weight:700;letter-spacing:1.4px;padding:5px 12px;border-radius:20px}}
.sub{{color:#4a5474;margin:8px 0 20px;max-width:850px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
.panel{{background:{TINT};border:1px solid #e3e8f4;border-radius:10px;padding:16px 18px}}
.lbl{{font-size:11.5px;letter-spacing:1.3px;text-transform:uppercase;color:#7d87a3;margin-bottom:8px}}
.big{{font-size:25px;font-weight:700;letter-spacing:-.3px}}
.meta{{font-size:13px;color:#5b6478;margin-top:6px}}
.cols{{margin-top:10px;line-height:2}}
.cols code, .sub code, .foot code{{background:#fff;border:1px solid #dde3f0;border-radius:5px;padding:2px 7px;
 font-size:12.5px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
.dim{{color:#7d87a3}}
table{{width:100%;border-collapse:collapse;font-size:14.5px}}
th{{text-align:left;font-size:11.5px;letter-spacing:1.1px;text-transform:uppercase;color:#7d87a3;
 border-bottom:1px solid #dde3f0;padding:0 10px 8px}}
td{{padding:9px 10px;border-bottom:1px solid #f0f3fa}}
.n{{text-align:right;font-variant-numeric:tabular-nums}}
.note{{margin:16px 0 0;padding:2px 0 2px 14px;border-left:3px solid {NAVY};color:#3b4460;font-size:14.5px}}
.foot{{background:#fff;border:1px solid #dde3f0;border-radius:14px;padding:26px 28px}}
.foot h3{{margin:0 0 10px;font-size:17px}}
.foot ul{{margin:0 0 18px;padding-left:20px;color:#3b4460}}
.foot li{{margin-bottom:7px}}
</style></head><body>
<header><div class="wrap">
  <div class="kicker">{T['kicker']}</div>
  <h1>{T['h1']}</h1>
  <div class="claim">{T['claim']}</div>
  <div class="formula">φ(D, t) = φ(D|t, t),&nbsp;&nbsp; D|t = {{ r ∈ D : avail(r) ≤ t }}</div>
</div></header>
<div class="wrap">
{''.join(cards)}
<section class="foot">
  <h3>{T['foot_h']}</h3>
  <ul>{li(T['foot'])}</ul>
  <h3>{T['lim_h']}</h3>
  <ul>{li(T['lim'])}</ul>
  <p class="note">{T['data']}</p>
</section>
</div></body></html>"""
out = _ROOT + "/demo/" + T["out"]
open(out, "w").write(page)
print("ok", out, len(page))
