# -*- coding: utf-8 -*-
"""Собирает самодостаточную HTML-страницу демо из demo_results.json."""
import json, html

R = json.load(open("/home/claude/demo/demo_results.json"))
NAVY, DEEP, ICE, TINT = "#1E2761", "#141B3D", "#CADCFC", "#F1F4FB"
GRN, AMB, RED = "#1F7A55", "#B57314", "#A62B22"

SUB = {
 1: ("ft.dfs без таблицы моментов предсказания — ровно так написано в туториале библиотеки. "
     "Задача: спрос на товар. featuretools 1.31.0, 13 признаков, глубина 2.",
     "Это поведение библиотеки по умолчанию, а не наша симуляция."),
 2: ("Фильтр по времени заказа. У отзыва и у факта доставки собственная, более поздняя метка: "
     "медиана +10 дней, 90-й перцентиль +23, максимум +147. Задача: качество продавца.",
     "Ошибку в этом коде нашёл оракул, а не человек. Код писали авторы проверки."),
 3: ("У каждой колонки собственная метка доступности. Больше в программе не изменено ничего.",
     "Отрицательный контроль: метод не срабатывает на корректном коде."),
}
def chip(v):
    c = RED if v == "УТЕЧКА" else GRN
    return f'<span class="chip" style="background:{c}">{v}</span>'

def probe_verdict(r):
    silent = r["rows"][1]["probe"] < 0.85
    if r["verdict"] == "УТЕЧКА":
        return ("ПРОПУСК", RED) if silent else ("поймала", AMB)
    return ("верно молчит", GRN) if silent else ("ЛОЖНАЯ ТРЕВОГА", RED)

cards = []
for r in R:
    body, note = SUB[r["scene"]]
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
        "<div class='cols dim'>выход побитово совпал на полной и на усечённой базе</div>"
    cards.append(f"""
    <section class="card">
      <div class="hdr"><span class="num">Сцена {r['scene']}</span>
        <h2>{html.escape(r['title'])}</h2>{chip(r['verdict'])}</div>
      <p class="sub">{body}</p>
      <div class="grid">
        <div class="panel">
          <div class="lbl">Дифференциальное исполнение</div>
          <div class="big" style="color:{RED if r['verdict']=='УТЕЧКА' else GRN}">{r['verdict']}</div>
          <div class="meta">{r['seconds']:.1f} с · расходящихся колонок {len(r['columns'])}
             · расхождений в значениях {r['cells']}</div>
          {cols}
        </div>
        <div class="panel">
          <div class="lbl">Промышленная проверка «макс AUC одного признака»</div>
          <div class="big" style="color:{pc}">{pv}</div>
          <div class="meta">значение {r['rows'][1]['probe']:.3f} · порог DataRobot 0.85 / 0.975
             · H2O 0.80 / 0.95 / 0.999</div>
          <div class="cols dim">сильнейший признак: <code>{html.escape(str(r['rows'][1]['feature']))}</code></div>
        </div>
      </div>
      <table><thead><tr><th>момент предсказания</th><th class="n">сущностей</th>
        <th class="n">AUC</th><th class="n">корректная версия</th>
        <th class="n">завышение, п.п.</th><th class="n">проверка</th></tr></thead>
        <tbody>{rows}</tbody></table>
      <p class="note">{note}</p>
    </section>""")

page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PITFALL — корректность признаков по времени</title>
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
.cols code{{background:#fff;border:1px solid #dde3f0;border-radius:5px;padding:2px 7px;
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
  <div class="kicker">PITFALL · демонстрация</div>
  <h1>Корректность признаков по времени через дифференциальное исполнение</h1>
  <div class="claim">Программа признаков корректна тогда и только тогда, когда её выход
   не меняется, если из базы физически удалить всё, чего на момент предсказания ещё
   не существовало. Мы не разбираем ни код, ни SQL: программа — чёрный ящик, вызываемый дважды.
   Расхождение выходов есть <b>доказательство</b> нарушения, а не подозрение.</div>
  <div class="formula">φ(D, t) = φ(D|t, t),&nbsp;&nbsp; D|t = {{ r ∈ D : avail(r) ≤ t }}</div>
</div></header>
<div class="wrap">
{''.join(cards)}
<section class="foot">
  <h3>Что показывают три сцены вместе</h3>
  <ul>
    <li><b>Проверка срабатывает там, где промышленная молчит.</b> На обеих утечках максимальный
      AUC одного признака не доходит до порога предупреждения DataRobot 0.85 — заключение чистое,
      а офлайн-оценка завышена на 16.3 и 5.3 пункта.</li>
    <li><b>И молчит там, где код корректен.</b> Сцена 3 — та же программа с исправленным
      отношением доступности: выход совпадает побитово, ложных срабатываний нет по построению.</li>
    <li><b>Цена утечки не выводится из факта утечки.</b> Одно и то же нарушение стоит 0.2 пункта
      на задаче про отток и 3–5 пунктов на задаче про качество: всё решает, насколько цель
      опирается на протёкшие колонки. Поэтому корректность надо проверять отдельно от метрики.</li>
  </ul>
  <h3>Границы метода — их надо называть первыми</h3>
  <ul>
    <li><b>Изменяемое поле без истории непроверяемо.</b> У <code>order_status</code> нет метки
      времени: момента, когда заказ стал отменённым, в данных нет. Усечённая база для такой
      колонки неотличима от полной, и метод к ней неприменим.</li>
    <li><b>Недетерминированная программа</b> даёт расхождение без утечки — нужен фиксированный seed.</li>
    <li><b>Пропуски возможны:</b> утечка, не проявившаяся на конкретном моменте t, на нём не видна.
      Ложных срабатываний при этом нет — асимметрия сознательная.</li>
    <li><b>Одна база, три задачи, три момента.</b> Предварительный результат; RelBench недоступен
      из сети эксперимента, структура задач воспроизведена по описанию.</li>
  </ul>
  <p class="note">Данные: Olist, 7 таблиц, 112 650 позиций заказов, сентябрь 2016 — октябрь 2018.
   Всё считается вживую на 2 ядрах CPU: <code>python3 demo.py</code>. Модель везде одна и та же
   с фиксированным seed — смена бустера сама по себе даёт до 11.5 п.п.</p>
</section>
</div></body></html>"""
open("/home/claude/demo/pitfall_demo.html", "w").write(page)
print("ok", len(page))
