# PITFALL — constructive critique and proposed improvements

## Context

Материалы: статья и demo PITFALL, плюс полученная обратная связь:

> «Детально пока не вникал, но из текста и демо как-то сложно сходу понять суть. Возможно нужна наглядная картинка.
>
> Ну и без таблиц со абляцией/бейзлайнами тяжело оценивать подход.
>
> на Fig.2 например очень сложно что-то понять.»

Главный вывод: проблема сейчас не столько в качестве самой идеи, сколько в **подаче demo как истории, которую нужно понять глазами за несколько секунд**.

---

# 1. Главный диагноз

Сейчас работа выглядит как:

> «У нас есть интересный execution-based detector, вот много экспериментов, вот несколько мест, где existing detectors ошибаются».

Для demo лучше, чтобы она читалась как:

> **«Вот очень простой баг, который почти невозможно заметить глазами. PITFALL запускает тот же feature code на полном и прошлом состоянии БД. Если результат меняется — код посмотрел в будущее. Сейчас я могу показать это вживую за 20 секунд».**

Сама идея хорошо приспособлена для demo. В paper уже есть running example с заказом и review: заказ существует на дату `t`, а review появляется позже; наивный feature фильтрует по `order_date` и всё равно использует будущий `review_score`.

Но **paper и demo сейчас эту очень простую историю немного прячут за большим количеством результатов**.

---

# 2. Что сейчас трудно понять

## 2.1. Главная идея спрятана слишком глубоко

Текст начинается с технического определения:

> “Features for multi-table prediction tasks are built by aggregating neighbouring tables at a per-row seed time…”

Для demo это не лучший вход.

Человеку сначала хочется увидеть:

```text
ORDER
Jan 1
  |
  +---- review written Jan 20
```

и вопрос:

> Если я предсказываю seller state на Jan 10, имею ли я право использовать review?

Ответ очевиден: нет.

А потом:

```text
NAIVE CODE
orders[order_date <= Jan 10]
        ↓
average(review_score)
        ↓
   4.7
```

против:

```text
PAST-ONLY DB
orders + only information known by Jan 10
        ↓
average(review_score)
        ↓
   4.2
```

И:

> **4.7 ≠ 4.2 → feature peeks.**

Это и есть весь PITFALL в одной картинке.

На сайте эта логика уже почти есть. Я бы сделал **эту историю центральной и в paper, и в demo**.

---

# 3. Fig. 2 действительно перегружена

Здесь замечание Николая очень точное.

Проблема не в том, что график плохой статистически. Проблема в том, что **он требует предварительно прочитать почти весь Section V-D, чтобы понять, что именно нужно из него извлечь**.

Главный вывод Figure 2 очень простой:

> **x — насколько подозрительна лучшая отдельная feature; y — насколько на самом деле выросла AUC; эти две величины не разделяют leak и clean code.**

Но глазами это сейчас не считывается мгновенно.

График одновременно показывает:

- correct code;
- cutoff shift;
- join-path leak;
- featuretools;
- reference code;
- несколько warning thresholds;
- shaded region;
- дополнительные подписи.

Читатель должен сначала **декодировать легенду**, а потом ещё интерпретировать положение точек.

## Что делать

### Вариант A — самый сильный

Оставить только несколько representative cases:

| Pipeline | Single-feature AUC | True inflation |
|---|---:|---:|
| Correct | 0.83 | 0 |
| Join leak | 0.71 | +4.1 |
| Featuretools leak | 0.81 | +16 |

И рядом визуально показать warning thresholds:

```text
single-feature probe
        ↓
   ┌───────────────┐
   │     CLEAN     │
   │      0 pp     │
   └───────────────┘

   JOIN LEAK       FEATURETOOLS
   0.71 / +4.1      0.81 / +16
       ↓                ↓
    SILENT            SILENT
```

Идея Figure:

> **два разных leak могут сидеть ниже warning threshold.**

---

# 4. Можно перестроить Fig. 2 как “demo figure”

Не обязательно делать её как обычный dense research plot.

Например:

```text
                        TRUE AUC INFLATION
                              ↑
                         +16 ┤         ★ featuretools
                            │
                          +5 ┤    ◆ join leak
                            │
                           0 ┼ ● ● ● ● ● ● clean
                            │
                            └────────────────────────→
                               BEST SINGLE-FEATURE AUC

                               │
                          H2O   │ 0.80
                               │
                   DataRobot   │       0.925
```

Callout 1:

> **Join leak: probe = 0.71, but model gains +5.1 AUC**

Callout 2:

> **Featuretools: probe = 0.81, but model gains +16 AUC**

Это существенно сильнее нынешнего Figure 2.

---

# 5. Нужна таблица ablation/baseline

Замечание про таблицы тоже правильное. Но я бы не делал огромную academic benchmark table.

Нужна **одна компактная таблица**, отвечающая на вопрос:

> “Почему мне вообще нужен PITFALL?”

## Existing safeguards vs PITFALL

| Safeguard | What it checks | Failure shown in our experiments |
|---|---|---|
| Univariate probe | suspicious single features | misses join-distributed leakage |
| Static scan | source-level patterns | misses runtime dependence on future data |
| **PITFALL** | dependence on unavailable information | detects output divergence directly |

Важно: не превращать это в формальную benchmark table, если нет одинакового experimental setup для всех методов. Лучше честно показать различие возможностей.

---

# 6. Нужна ещё одна компактная таблица с empirical evidence

Сейчас много сильных чисел раскидано по тексту:

- featuretools: 11 columns, +14.8–16.3 pp;
- own reference code: +3.1–5.3;
- expert SQL: 8/14 executable files diverge;
- agent SQL: 2/34 execute diverge;
- LLM-generated feature code: 26–70% overall bound.

У читателя возникает ощущение:

> “Interesting, but where is the scoreboard?”

Поэтому полезна таблица:

| Source | Executable | Violating | Clean | Max inflation |
|---|---:|---:|---:|---:|
| Featuretools | 1 | 1 | 0 | 16.3 pp |
| Our reference | 1 | 1 | 0 | 5.3 pp |
| Expert SQL | 14 | 8 | 6 | — |
| LLM-generated | 132 | 5 confirmed | — | — |
| Agent SQL | 34 | 2 | 32 | — |

Сделать footnote о том, что эти corpora не полностью сопоставимы.

---

# 7. Сильный результат, который стоит подчеркнуть сильнее

Особенно хороший вывод:

> **hundreds of thousands of diverging cells can cost essentially nothing**

Это сильный результат против интуиции.

В paper есть более общий вывод:

> **Neither the fact of a violation nor its size predicts its cost.**

Можно показать компактной таблицей:

| Case | Diverging cells | AUC inflation |
|---|---:|---:|
| Own code / task A | hundreds | +0.2 |
| Own code / task B | hundreds | +3–5 |
| Expert SQL / stack | >200k | −0.02 |

И подпись:

> **Size of the leak is not a proxy for damage.**

Не добавлять ещё один scatter plot только ради этого.

---

# 8. Demo сейчас пытается показать слишком много

Сейчас сайт последовательно охватывает:

1. explain peeking;
2. draggable Olist;
3. two-run check;
4. guess-the-peek game;
5. LLM code;
6. published expert SQL;
7. cost;
8. blind spot;
9. localization;
10. other datasets;
11. cutoff semantics;
12. limitations.

Это хороший research website, но не обязательно хороший conference demo.

Для живого demo лучше сделать **3 акта**.

---

## Act 1 — “Catch this bug”

15–20 секунд.

Пользователь двигает дату:

```text
Seed date: Jan 10
```

Timeline:

```text
Jan 1 ───── Order
            │
Jan 10 ─────│──── PREDICTION
            │
Jan 20 ────────── Review
```

Потом:

```text
Naive feature: 4.73
Past-only:     4.21

❌ FEATURE PEEKS INTO THE FUTURE
```

Это должна быть самая важная часть demo.

---

## Act 2 — “Why not just look at the feature?”

Показывается слабость обычного single-feature detector:

```text
Naive leakage detector
best single-feature AUC = 0.71
threshold = 0.80

→ CLEAN
```

Но PITFALL говорит:

```text
PITFALL
full output != truncated output

→ LEAK
```

Здесь естественно появляется Fig. 2.

---

## Act 3 — “Where did it leak?”

Показывается localization:

```text
Detected channels

✓ orders.review_score
✓ orders.delivery_date
✗ other channels
```

И interaction заканчивается.

Не нужно во время live demo подробно рассказывать про все пять источников, LLMs, RelBench и т. д.

---

# 9. “Guess the peek” можно превратить в сильную demo-фичу

Сейчас это просто одна из секций.

Лучше сделать короткий audience interaction:

```text
Which feature is safe?

A. avg(price) over orders before t
B. avg(review_score) over orders before t
C. count(orders) before t
D. avg(delivery_delay) over orders before t
```

После выбора:

```text
❌ B

Why?
The order existed before t,
but review_score did not.
```

И затем:

> “Now let's see whether a static detector catches it.”

Ответ: нет.

> “PITFALL?”

Ответ: да.

Это очень хороший интерактивный narrative.

---

# 10. Название demo

`Did the feature peek?` — очень хорошее **demo title**.

`PITFALL: Catching Point-in-Time Violations in Multi-Table Feature Pipelines by Differential Execution` — хорошее **paper title**, но не лучшее первое сообщение пользователю.

Для UI/landing page можно использовать:

### DID THE FEATURE PEEK?
**PITFALL: Differential execution for point-in-time correctness**

Это значительно demo-friendly.

---

# 11. Упростить терминологию в начале

Сейчас слишком рано появляются:

- point-in-time correctness;
- seed time;
- availability relation;
- availability channel;
- differential execution.

Это правильные термины, но они создают высокий cognitive load.

Лучше в начале вводить только три понятия:

### 1. “as-of time”

> What did we know on Jan 10?

### 2. “future information”

Review on Jan 20.

### 3. “two-run check”

Same code + full DB vs past-only DB.

После этого уже:

> We call this point-in-time correctness.

---

# 12. Главная формулировка метода уже есть — её нужно сделать центральной

Очень хорошая формулировка на сайте:

> “We run the feature code twice, once on the whole database and once on a copy with everything after the date physically removed, and compare.”

Я бы сделал именно это **главной conceptual figure всей работы**.

```text
                 SAME FEATURE PROGRAM
                    ┌────────────┐
                    │ φ(DB, t)   │
                    └────────────┘
                         │
                 ┌───────┴────────┐
                 │                │
                 ▼                ▼
            FULL DATABASE    PAST-ONLY DB
                              (cut at t)
                 │                │
                 ▼                ▼
               4.73             4.21
                 │                │
                 └───────┬────────┘
                         ▼
                    4.73 ≠ 4.21
                         │
                         ▼
                 🚨 FUTURE DATA USED
```

Подпись:

> **PITFALL does not infer leakage from code or feature statistics. It tests whether the executed program depends on information that was unavailable at prediction time.**

Это хорошее single-sentence explanation.

---

# 13. Осторожнее с “no false positives by construction”

Фраза:

> **“no false positives by construction”**

может вызвать у reviewer вопрос: при каких именно assumptions?

У paper уже есть важные оговорки: one-sided guarantee, deterministic program, declared availability map, tested seed times, etc.

Я бы в наиболее заметных местах писал:

> **A detected divergence is a witness of a point-in-time violation under the declared availability map.**

А ниже:

> **The test is one-sided: no divergence at tested seed times does not prove correctness.**

Это научно аккуратнее.

---

# 14. Предлагаемая композиция 4-страничного paper

## Page 1
**Problem + one concrete failure + method**

Большая schematic figure.

## Page 2
**System + interactive demo**

Большой screenshot сайта вместо слишком маленькой Fig. 3.

На screenshot явно подписать:

1. choose seed date;
2. run twice;
3. detect divergence;
4. localize leak.

## Page 3
**Evidence**

Одна compact benchmark/evidence table + simplified Fig. 2.

## Page 4
**Limitations + broader evidence + conclusion**

Здесь оставить:

- RelBench;
- LLM;
- agent;
- timestamp granularity;
- undecidable fields;
- limitations.

---

# 15. Fig. 3 нужно сделать walkthrough, а не просто screenshot

Сейчас Figure 3 — скорее screenshot интерфейса.

Лучше сделать annotated walkthrough:

```text
┌─────────────────────────────────────────────────────────┐
│  1. Choose seed date:  2018-04-01                     │
│                                                         │
│  2. Run feature program                                │
│                                                         │
│  FULL DB                  PAST-ONLY DB                  │
│  avg_review = 4.73        avg_review = 4.21             │
│                                                         │
│                       ❌ DIVERGENCE                     │
│                                                         │
│  3. Localize                                             │
│     review_score  █████████████████                     │
│     delivery_date █████████                             │
└─────────────────────────────────────────────────────────┘
```

И поверх стрелками:

**1. choose time → 2. run twice → 3. detect → 4. localize**

Так reviewer мгновенно понимает interaction flow.

---

# 16. Сильный результат с timestamp granularity тоже стоит визуализировать

В paper есть важное наблюдение на rel-f1:

- тот же inclusive cutoff;
- day timestamps → leakage;
- second timestamps → no measurable effect.

Можно сделать маленькую visual:

```text
Timestamp granularity

DAY
2010-06-14
    ↓
≤ t  → race included
    ↓
🚨 leak

SECOND
2010-06-14 14:32
    ↓
≤ midnight
    ↓
race excluded
    ↓
✓ no effect
```

Подпись:

> **Whether the same bug matters is decided by the data timestamps, not by the code alone.**

---

# 17. Что упростить и что не пытаться одновременно продавать

Не нужно одинаково подробно продвигать:

- LLM-generated feature code;
- autonomous agent SQL;
- published expert SQL;
- commercial AutoML;
- timestamp granularity;
- mutable fields;
- benchmark test-seed blindness;
- model-dependent AUC cost.

Все они интересны, но вместе начинают конкурировать за центральный message.

Для demo лучше сделать primary message:

> **PITFALL detects future-information dependence by running the same feature program against full and past-only data.**

И secondary messages:

1. Existing single-feature detectors can miss it.
2. It can localize the offending availability channel.
3. It works on real code from multiple sources.

Остальное — supporting evidence.

---

# 18. Что точно не делать

### 1. Не добавлять ещё 5 графиков

Проблема сейчас не в недостатке результатов, а в signal-to-noise.

### 2. Не делать большую ablation table на 20 строк

Для demo лучше одна компактная таблица с 3–5 строками.

### 3. Не объяснять весь formalism в demo UI

Уравнение

\[
\phi(D,t)=\phi(D|_t,t)
\]

нужно в paper, но не должно быть первым, что видит человек.

### 4. Не показывать исходный Python-код слишком долго

Код имеет смысл только после того, как зритель уже понял, какой баг ищется.

### 5. Не делать Fig. 2 “богаче”

Её надо сделать **проще**, а не информативнее.

---

# 19. One-minute pitch

> **Feature leakage in relational ML is surprisingly hard to see.**
>
> Consider an order placed on January 1 and reviewed on January 20. If we predict what was known on January 10, the review must not be used—even though it belongs to an order that already existed.
>
> **PITFALL catches this without reading or parsing the feature code.**
>
> We run the same feature program twice: once on the full database and once on a copy where all information after the prediction date has been removed. If the outputs differ, the program depended on future information.
>
> The demo shows this on real data, compares the result with standard single-feature leakage probes, and localizes which availability channel caused the violation.

Это звучит больше как **Demo Track paper**, а не как condensed research paper.

---

# 20. Приоритет изменений по ROI

## P0 — обязательно

### 1. Переделать Fig. 2

Убрать визуальный шум, оставить 2–3 representative leak cases + clean cases.

### 2. Сделать большую “two runs” картинку

Она должна визуально объяснять весь метод.

### 3. Добавить компактную baseline/evidence table

### 4. Перестроить demo вокруг одного Olist failure

`Order → review after t → naive feature → divergence.`

### 5. Увеличить и аннотировать screenshot demo в paper

## P1 — очень желательно

### 6. Сократить paper narrative вокруг трёх claims

### 7. Упростить terminology в начале

### 8. Перенести LLM/agent/RelBench material в supporting evidence

## P2 — nice-to-have

### 9. Добавить one-click “Show me why” localization

### 10. Добавить короткую live animation

`FULL DB → 4.73` / `PAST DB → 4.21`.

---

# Итог

**Не нужно переделывать саму идею.** Она достаточно простая и demo-friendly.

Проблема в том, что сейчас у тебя очень сильный **research payload**, но недостаточно агрессивно выделен **one killer interaction**.

Я бы сформулировал центральную пару так:

> **One bug. Two runs. One verdict.**

И дальше всё подчинить этой последовательности.

У тебя уже есть для этого всё содержательно: конкретный review/order example, differential execution, localization, silent univariate probe, реальные violations в library/reference/expert/LLM/agent code.

Самая важная новая картинка — условная **Fig. 0**, которой сейчас фактически нет:

```text
            Can this feature see the future?

                  ORDER             REVIEW
                   │                  │
              Jan 1 ●───────────────● Jan 20
                        │
                     Jan 10
                    seed time

        naive code:  review = 4.73   ❌
        past-only:   review = 4.21   ✓

                 4.73 ≠ 4.21
                    ↓
              PITFALL: LEAK
```

А уже после этого:

> “Now let’s see why the usual detector misses it.”

И тогда Fig. 2 становится **ответом на естественный второй вопрос**, а не картинкой, которую сначала приходится расшифровывать.

---

# Самое важное в трёх пунктах

Если переделывать только **3 вещи**, я бы выбрал:

1. **Новая главная schematic figure** — `full DB vs past-only DB`.
2. **Сильно упрощённая Fig. 2** — показать, что probe не разделяет leak и clean.
3. **Одна компактная baseline/evidence table** — чтобы reviewer сразу увидел empirical coverage.

Это, на мой взгляд, даст самый большой прирост воспринимаемой ясности без переписывания всей работы.
