# PITFALL — замечания к статье и демо перед подачей на ICDM 2026 Demo Track

Источники: `pitfall.pdf`, https://stas1f1.github.io/pitfall/, CfD https://icdm2026.neu.edu.cn/CallforDemos/list.htm, отзыв Н. Никитина (19.08.26).

**Общий вывод.** Критика справедлива. Это сильная *исследовательская* статья, сжатая в 4 страницы демо-трека без артефактов, по которым демо-рецензент за 10 минут принимает решение: концептуальная картинка, архитектурная схема, таблица с бейзлайнами, развёрнутое описание самого демо. Почти все нужные цифры в тексте уже есть — они растворены в прозе.

Формальное: по CfD дедлайн — 20 августа AoE, 4 страницы включая ссылки, IEEE 2-column, single-blind, обязательна секция про этику данных (есть), опциональное видео, на конференции нужен постер.

---

## 1. Нет картинки «в чём суть» — добавить Fig. 1

Демо-страница это делает (секция 1: заказы, звёздочки-отзывы, ползунок даты), а в статье первой картинкой идёт график инфляции, до которого читатель ещё не понял, что такое «peek».

Нужна одна схема на полколонки: временная шкала одного продавца, заказы до seed time, отзыв на заказ прилетает после seed time; два ответа — что вычисляет `filter by order_date` и что было реально известно. Рядом стрелки φ(D,t) и φ(D|t,t) со знаком ≠. Это вся идея, и она должна быть видна раньше Eq. (1).

Абзац «In one breath» с сайта — лучший первый абзац введения, чем текущий (который начинается с определения задачи по RelBench).

## 2. Fig. 2 перегружен — разбить или заменить таблицей

На одном скаттере: 6 категорий в легенде, 4 вертикальных порога, заливка, подписи внутри поля, две оси с разной семантикой. Содержит два отдельных утверждения:

- **Миссы**: утечки с inflation 3–17 пп при probe < 0.925.
- **Ложные срабатывания**: чистый код с inflation 0 при probe > 0.80.

Варианты:
- (а) два панеля — слева только утечки + линия DataRobot, справа только чистый код + линия H2O;
- (б) один скаттер, легенда из трёх классов (корректно / утечка через один признак / утечка, размазанная по многим), один порог сплошной, второй пунктиром;
- (в) убрать скаттер из статьи, заменить Table 2(b); скаттер с ползунком оставить на сайте, где он работает как интерактив.

Рекомендация: (в).

## 3. Таблицы с бейзлайнами — главный упрёк рецензента

Ни одного нового эксперимента не нужно.

**Table 1. Источники нарушений (Sec. V-C).** Строки: featuretools default, our reference code, RelBench expert SQL, LLM-generated (2 модели), agent corpus. Столбцы: БД/задача, программ, исполняется, diverge, затронутые колонки, inflation, max single-feature AUC, вердикт DataRobot, вердикт H2O, время. См. раздел «Таблицы» ниже.

**Table 2. Сравнение детекторов на expert-SQL корпусе (14 файлов).** Строки: ручной аудит [8], статический сканер, probe @0.925, probe @0.80, «спросить LLM» [5], PITFALL. Столбцы: найдено / реальных / ложных / пропущено. PITFALL тут и судья, и участник — это честно сказать одной фразой в подписи.

**Table 3. Абляции.** Фактически три уже описаны как анекдоты:
- truncation только по строкам vs строки + per-column availability: первый вариант *не ловит* утечку через `review_score` — центральный кейс;
- точное равенство vs допуск по шумовому порогу (rel-amazon: 4 ложных вердикта → 0);
- seed time = test split vs середина train (rel-event: 0 из 1 vs 23 из 24);
- `≤` vs `<` на rel-f1 до/после 2005 — абляция по данным.

Каждая таблица забирает текст: соответствующий абзац сокращается до 2–3 предложений с утверждением, а не числами.

## 4. Противоречие, за которое зацепятся

Абстракт и Sec. II-C: «no false positives by construction». Sec. III Validation: «Four leak verdicts were false». Формально правы (ошибка толеранса, не метода), но читается как противоречие на одной странице.

Переформулировать: «при точном сравнении ложных срабатываний нет; на плавающей точке требуется допуск, который мы выставляем по шумовому порогу негативного контроля (1.7×10⁻¹¹); без этого шага — 4 ложных вердикта на rel-amazon». Сделать частью описания метода, а не прятать в «Validation».

## 5. Секция «Демонстрация» слишком короткая для демо-трека

Sec. VI — шесть строк, Fig. 3 нечитаема в печати. Нужно:
- **архитектурная схема** SCOUT / BUILDER / GUARD / LOCATOR (Sec. III вводит имена компонентов, как будто схема есть);
- сценарий посетителя по шагам: 1) двигает дату, видит расхождение; 2) выбирает программу, видит вердикт и колонки; 3) «guess the peek», 8 функций; 4) локализация по каналам; 5) ползунок порога probe — и что посетитель узнаёт на каждом шаге;
- Fig. 3 крупнее: один скриншот секции 2 сайта на всю ширину колонки с читаемым вердиктом. Место — за счёт Fig. 2.

Место освободится, если Sec. V-A, V-B, V-D ужать до таблиц.

## 6. Плотность прозы

Стиль «каждое предложение — три числа» читается как лог эксперимента («costs −0.45, +2.45 and +3.27 points on the day-stamped cells and exactly 0.00 on all three second-stamped cells»; абзац про `stack/post-votes`). Правило: в тексте утверждение и одно число-якорь, остальное в таблицу.

Терминология: seed time / cutoff / «as-of date» / δ — четыре обозначения для двух сущностей. Определить один раз в Sec. II: *seed time t* — момент прогноза; *cutoff* — граница, которую проводит программа (в идеале = t). «Availability channel» ввести в II-B, а не в II-C.

## 7. Что упростить или убрать

- Limitation (vi) «Final-program metric undercounts» — непонятно без контекста: раскрыть одним предложением или убрать.
- Limitation (iii) про rel-f1 calendar — одной фразы достаточно.
- Цифры про prompt guards: в статье 46.2→14.6 %, на сайте 46→41→15 % — оставить одну формулировку.
- Contributions (i)–(iv) → три: check + localisation; evidence on 5 sources / 6 DBs; interactive demo. LLM-измерение — часть evidence.

## Приоритеты, если времени мало

1. Table 1 + Table 2 — закрывают главный упрёк.
2. Концептуальная Fig. 1 с сайта.
3. Убрать/упростить Fig. 2; на место — архитектура и крупный скриншот демо.
4. Снять противоречие про false positives.
5. Развернуть Sec. VI до сценария.

Сайт как демо в хорошем состоянии и заметно яснее статьи; основная работа — перенести его ясность в PDF.

---

## Таблицы (черновик с числами из текста)

Ячейки `?` — числа, которых нет в тексте: заполнить из логов или убрать столбец. LaTeX-версия: `pitfall_tables.tex`.

### Table 1. Sources of point-in-time violations (Sec. V-C)

| Source | Database(s) / task | Programs | Execute | Diverge (PITFALL) | Scope of leak | True inflation (AUC pp) | Best single-feature AUC | DataRobot ≥ .925 | H2O ≥ .80 |
|---|---|---|---|---|---|---|---|---|---|
| featuretools 1.31 default (`ft.dfs`, no cutoff table) | Olist, A/B | 1 | 1 | 1 | 11 columns, all 3 seed times | +14.8 – +16.3 | 0.81 | silent | fires |
| Our reference code | Olist, A/B | 1 | 1 | 1 | 4 columns (review, delivery) | A: +0.2; B: +3.1 – +5.3 | ? (< .925) | silent | ? |
| RelBench expert SQL [8] | rel-f1, -stack, -event, -hm, -amazon; 15 tasks | 15 | 14 | 8 | e.g. 9 cols (user-badge); 2,730 future `users` rows (post-votes); 87.5 % of label rows (rel-event) | −0.33 (driver-dnf), +0.95 (driver-top3), −0.02 (user-badge) | identical to 6 s.f. with/without leak | silent | silent |
| LLM-generated Python (2 models) | Olist, C | 233 | 132 | 61 (62 % / 22 %) | entity history filtered by order time, joined timestamp ignored | median +0.11 | ? | silent | ? |
| LLM-agent SQL corpus | rel-stack, user-engagement | 37 (32 trials) | 34 | 2 | missing cutoff on `users` join; 57 / 25,233 rows; in 31 / 32 trials | not measured | – | – | – |

Подпись: *Verdict time: seconds per program on Olist and rel-f1 (0.02 s per seed time); 19 min for the full agent corpus. Inflation measured with one fixed LightGBM, paired bootstrap, 2,000 resamples.*

Если не влезает в `table*`: первым убрать столбец «Best single-feature AUC» (дублируется в 2b), вторым — «Scope of leak» (в текст).

### Table 2. Detectors compared

**(a) Executed RelBench expert SQL, 14 files; ground truth = divergence under execution**

| Detector | Flagged | Real | False alarms | Missed (of 8) |
|---|---|---|---|---|
| Manual audit [8] | 2 | 2 | 0 | 6 |
| Static scanner (ours, earlier) | 8 | 2 | 6 | 6 |
| Univariate probe, DataRobot .925 | 0 | 0 | 0 | 8 |
| Univariate probe, H2O .80 | 0 | 0 | 0 | 8 |
| Asking an LLM [5] (other corpus) | – | – | P = 0.19 | R = 0.52 |
| **PITFALL** | 8 | 8 | 0 | 0 |

На agent-корпусе: статический скан 5 кандидатов → 2 реальных, 3 ложных; PITFALL → 2.

Подпись: *Ground truth is divergence under execution, so PITFALL is correct by construction; the table measures how far the other detectors fall from it.*

**(b) Why the probe fails in both directions (controlled runs)**

| Run | True inflation | Best single-feature AUC | DataRobot | H2O |
|---|---|---|---|---|
| Correct code, task A | 0 | 0.83 – 0.86 | silent | **false alarm** |
| Join-path leak only, task C | +3.0 – +5.1 | 0.71 (unchanged by leak) | **miss** | **miss** |
| featuretools default, task A | +14.8 – +16.3 | 0.81 | **miss** | fires |
| No cutoff at all, task B | +18.0 | < 0.925 | **miss** | ? |
| Same leak, `≤` vs `<`, rel-f1 | day-stamped: −0.45 / +2.45 / +3.27; second-stamped: 0.00 | moves ≤ 0.015 | silent | silent |

Часть (b) заменяет Fig. 2 в статье.

### Проверить по логам

- Строка H2O для featuretools (0.81 > 0.80 → fires) не противоречит «below DataRobot's threshold on every one», но противоречит общему тону «probe silent». Если так — оставить: усиливает аргумент про нестабильность порога.
- Probe AUC для reference code и LLM-generated программ.
