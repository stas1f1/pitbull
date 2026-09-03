# PITFALL — план правок перед сабмитом (ICDM 2026 Demo Track)

Версия 2. Объединяет мои замечания и второй отзыв. Ограничение: **сабмит сегодня, новых экспериментов нет** — всё ниже использует только числа, уже напечатанные в статье или на сайте. Разделено на «сегодня» и «camera-ready / постер».

Формальные требования CfD: 4 страницы вкл. ссылки, IEEE 2-column, single-blind, секция про этику данных (есть), ссылки на код/демо приветствуются, видео опционально, на конференции нужен постер.

---

## Диагноз в одном абзаце

Это сильная исследовательская статья, сжатая в формат демо. Демо-рецензент за 10 минут ищет: картинку с идеей, схему системы, таблицу с бейзлайнами, описание того, что посетитель делает у стенда. Ничего из этого в PDF сейчас нет, хотя все данные есть — в прозе и на сайте. Сайт заметно яснее статьи; задача — перенести его ясность в PDF и подчинить всё одной последовательности: **один баг → два прогона → один вердикт → где именно**.

---

## СЕГОДНЯ (по убыванию ROI)

### 1. Новая Fig. 1 — схема «два прогона» на конкретном примере

Полколонки, без формул. Слева временная шкала: заказ 1 янв, seed time 10 янв, отзыв 20 янв. Справа один и тот же φ на полной БД и на БД, обрезанной по t; два числа (взять реальные с сайта, секция 1, например средний отзыв продавца на 2018‑04‑01); знак ≠; вердикт. Подпись одной фразой:

> PITFALL does not infer leakage from code or feature statistics. It tests whether the executed program depends on information that was unavailable at prediction time.

Это должно появиться **раньше** Eq. (1). Саму Eq. (1) оставить, она короткая.

### 2. Первый абзац введения — переписать с человеческого примера

Сейчас статья открывается определением задачи по RelBench. Заменить на «In one breath» с сайта / one‑minute pitch:

> Consider an order placed on January 1 and reviewed on January 20. Predicting as of January 10, the review must not be used, although it belongs to an order that already existed. Filtering by order date admits it. We run the same feature program twice — on the full database and on a copy with everything after January 10 removed — and compare. If the outputs differ, the program peeked.

Термины вводить после примера, и только три: *as‑of / seed time*, *future information*, *two‑run check*; затем «we call this point‑in‑time correctness». «Availability channel» определить в II‑B, а не в II‑C. Оставить одно обозначение для границы в коде (*cutoff*) и одно для момента прогноза (*seed time t*), δ — только сдвиг.

### 3. Fig. 2 убрать из статьи, заменить Table 2

Скаттер с 6 классами, 4 порогами и заливкой требует прочитать V‑D, чтобы его понять. Его содержание — два утверждения (probe молчит на утечках до +18 пп; probe срабатывает на чистом коде). Это Table 2(b) ниже. Интерактивный скаттер с ползунком остаётся на сайте, где он работает.

Если хочется оставить картинку: только три точки с подписями (clean 0.83–0.86 / 0; join leak 0.71 / +3–5; featuretools 0.81 / +16) и два порога. Не богаче.

### 4. Таблицы (числа ниже, LaTeX в `pitfall_tables.tex`)

- **Table 1** — источники нарушений: пять строк, одна на источник.
- **Table 2(a)** — детекторы на expert‑SQL корпусе (14 файлов); **2(b)** — почему probe ошибается в обе стороны.
- **Table 3** — размер утечки vs цена: три строки (сотни ячеек → +0.2; сотни → +3–5; >2·10⁵ → −0.02). Подпись: *Size of the leak is not a proxy for damage.*

После каждой таблицы соответствующие абзацы V‑A, V‑C, V‑D, V‑F сокращаются до утверждения + одно число‑якорь. Освобождается ~¾ страницы под п. 1 и п. 6.

Подпись к Table 2(a) обязательно: *Ground truth is divergence under execution, so PITFALL is correct by construction; the table measures how far the other detectors fall from it. Corpora in Table 1 are not mutually comparable.*

### 5. Снять противоречие про false positives

Абстракт и II‑C: «no false positives by construction»; III: «Four leak verdicts were false». Заменить везде на:

> A detected divergence is a witness of a point‑in‑time violation under the declared availability map; the test is one‑sided, and no divergence at the tested seed times does not prove correctness. With floating‑point aggregates a tolerance is required; we set it from the noise floor of a negative control (1.7×10⁻¹¹ relative); without it, four verdicts on rel‑amazon would be false.

И перенести это из «Validation» в описание метода (II‑C).

### 6. Секция VI — walkthrough вместо шести строк и нечитаемого скриншота

- **Fig. 3**: один скриншот секции 2 сайта на ширину колонки с читаемым вердиктом, поверх — цифры **1 choose seed date → 2 run twice → 3 divergence → 4 localize**.
- Текст: сценарий посетителя в три акта (см. ниже), по 2–3 предложения на акт, и что он узнаёт в каждом.
- Если место позволяет: маленькая схема SCOUT → BUILDER → GUARD → LOCATOR (сейчас имена компонентов вводятся, как будто схема есть). Если не влезает — одно предложение с потоком данных.

### 7. Мелкие правки текста

- Contributions (i)–(iv) → три: check + localisation; evidence on 5 sources / 6 DBs; interactive demo (LLM‑измерение — часть evidence).
- Limitation (vi) «Final‑program metric undercounts» — раскрыть одним предложением или убрать. Limitation (iii) про rel‑f1 calendar — одна фраза.
- Цифры prompt guards: статья 46.2→14.6 %, сайт 46→41→15 % — привести к одному виду.
- Заголовок демо/лендинга: «Did the feature peek?», полное название — подзаголовок. В статье можно оставить как есть.

### Целевая раскладка 4 страниц

| Стр. | Содержание |
|---|---|
| 1 | Проблема с примером, Fig. 1 (два прогона), метод и гарантия (п. 5), Eq. (1) |
| 2 | Система (одна схема или абзац), демо: Fig. 3 walkthrough + три акта |
| 3 | Evidence: Table 1, Table 2, Table 3, сжатый текст |
| 4 | Гранулярность таймстемпов, rel‑event / выбор seed time, LLM/agent кратко, лимиты, этика, ссылки |

---

## Сценарий живого демо (три акта, ~1 минута; также структура постера)

**Акт 1. Catch this bug (20 с).** Секция 1 сайта: один продавец, ползунок даты. Наивный средний отзыв vs то, что было известно. Числа расходятся → «feature peeked».

**Акт 2. Why not just look at the feature? (20 с).** «Guess the peek»: четыре признака, посетитель выбирает безопасный (avg price / avg review / count orders / avg delivery delay). Промах на review → «order existed before t, review_score did not». Затем: поймал бы probe? — нет (0.71 < 0.80); PITFALL? — да.

**Акт 3. Where did it leak? (20 с).** Секция 6: отключаем каналы по одному, два столбца двигаются, остальные нет. «Locates, does not repair».

Секции про LLM, expert SQL, rel‑event, гранулярность — только если спросят. Именно это и описать в Sec. VI.

---

## ПОСЛЕ СДАЧИ (camera‑ready, постер, видео)

- **Абляции** как отдельная таблица: row‑only vs per‑column truncation (reference code проходит row‑only по построению, так как сам фильтрует по order time — т.е. результат выводится без нового прогона, но лучше подтвердить одним запуском); точное равенство vs допуск (rel‑amazon 4 → 0); seed time = test split vs середина train (rel‑event 0/1 vs 23/24); `≤` vs `<` на rel‑f1.
- Архитектурная схема, если не вошла.
- Визуал гранулярности таймстемпов — на сайт, не в статью.
- Опциональное видео по сценарию трёх актов.
- Заполнить `?` в таблицах из логов (probe AUC для reference code и LLM‑программ; H2O на task B без cutoff).

---

## Таблицы (черновик с числами из текста)

Ячейки `?` — чисел нет в тексте: заполнить из логов или убрать столбец.

### Table 1. Sources of point‑in‑time violations (Sec. V‑C)

| Source | Database(s) / task | Programs | Execute | Diverge (PITFALL) | Scope of leak | True inflation (AUC pp) | Best single‑feature AUC | DataRobot ≥ .925 | H2O ≥ .80 |
|---|---|---|---|---|---|---|---|---|---|
| featuretools 1.31 default (`ft.dfs`, no cutoff table) | Olist, A/B | 1 | 1 | 1 | 11 columns, all 3 seed times | +14.8 – +16.3 | 0.81 | silent | fires |
| Our reference code | Olist, A/B | 1 | 1 | 1 | 4 columns (review, delivery) | A: +0.2; B: +3.1 – +5.3 | ? (< .925) | silent | ? |
| RelBench expert SQL [8] | rel‑f1, ‑stack, ‑event, ‑hm, ‑amazon; 15 tasks | 15 | 14 | 8 | e.g. 9 cols (user‑badge); 2,730 future `users` rows (post‑votes); 87.5 % of label rows (rel‑event) | −0.33 (driver‑dnf), +0.95 (driver‑top3), −0.02 (user‑badge) | identical to 6 s.f. | silent | silent |
| LLM‑generated Python (2 models) | Olist, C | 233 | 132 | 61 (62 % / 22 %); 5 manually confirmed | entity history by order time, joined timestamp ignored | median +0.11 | ? | silent | ? |
| LLM‑agent SQL corpus | rel‑stack, user‑engagement | 37 (32 trials) | 34 | 2 | missing cutoff on `users` join; 57 / 25,233 rows; in 31 / 32 trials | not measured | – | – | – |

Подпись: *Verdict time: seconds per program on Olist and rel‑f1 (0.02 s per seed time); 19 min for the agent corpus. One fixed LightGBM; paired bootstrap, 2,000 resamples. Corpora are not mutually comparable.*

Если не влезает: убрать «Best single‑feature AUC» (есть в 2b), затем «Scope of leak» (в текст).

### Table 2. Detectors compared

**(a) Executed RelBench expert SQL, 14 files, 8 violations**

| Detector | Flagged | Real | False alarms | Missed (of 8) |
|---|---|---|---|---|
| Manual audit [8] | 2 | 2 | 0 | 6 |
| Static scanner (ours, earlier) | 8 | 2 | 6 | 6 |
| Univariate probe, DataRobot .925 | 0 | 0 | 0 | 8 |
| Univariate probe, H2O .80 | 0 | 0 | 0 | 8 |
| Asking an LLM [5] (other corpus) | – | – | P = 0.19 | R = 0.52 |
| **PITFALL** | 8 | 8 | 0 | 0 |

Agent‑корпус: static scan 5 кандидатов → 2 реальных, 3 ложных; PITFALL → 2.

**(b) The probe fails in both directions**

| Run | True inflation | Best single‑feature AUC | DataRobot | H2O |
|---|---|---|---|---|
| Correct code, task A | 0 | 0.83 – 0.86 | silent | **false alarm** |
| Join‑path leak only, task C | +3.0 – +5.1 | 0.71 (unchanged by leak) | **miss** | **miss** |
| featuretools default, task A | +14.8 – +16.3 | 0.81 | **miss** | fires |
| No cutoff at all, task B | +18.0 | < .925 | **miss** | ? |
| `≤ t` vs `< t`, rel‑f1 | day‑stamped: −0.45 / +2.45 / +3.27; second‑stamped: 0.00 | moves ≤ 0.015 | silent | silent |

### Table 3. Size of the violation does not predict its cost

| Case | Diverging cells | AUC inflation |
|---|---|---|
| Reference code, Olist task A | 4 columns (hundreds of cells) | +0.2 |
| Reference code, Olist task B | same cells | +3.1 – +5.3 |
| Expert SQL, stack/user‑badge | > 2·10⁵ | −0.02 |
| Expert SQL, f1/driver‑top3 | race rows after seed time | +0.95 |

Подпись: *Same defect, same code: damage is decided by the task and the timestamps, not by the defect.*

### Проверить по логам

- H2O для featuretools (0.81 > 0.80 → fires): не противоречит «below DataRobot's threshold on every one», но противоречит тону «probe silent». Если так — оставить, это усиливает довод о нестабильности порога.
- Точное число diverging cells для reference code (в тексте — «четыре агрегата», число ячеек не названо).
