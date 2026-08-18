# PITFALL

Проверка корректности признаков по времени **дифференциальным исполнением**
для многотабличных задач машинного обучения.

```
φ(D, t) = φ(D|t, t),   D|t = { r ∈ D : avail(r) ≤ t }
```

Программа признаков вызывается дважды: на полной базе и на базе, физически усечённой
на момент предсказания. Расхождение — доказательство нарушения, а не подозрение.
Код не разбирается: программа — чёрный ящик. Ложных срабатываний нет по построению.

**Начните с `HANDOVER.md`** — там состояние проекта, все числа с источниками,
методические правила и открытые вопросы.

## Быстрый старт

```bash
pip install pandas numpy scikit-learn lightgbm featuretools --break-system-packages
cd demo && python3 demo.py
```

Три сцены, около минуты на двух ядрах CPU, без сети и без GPU:

| | сцена | оракул | промышленная проверка | завышение |
|---|---|---|---|---|
| 1 | featuretools с настройками по умолчанию | УТЕЧКА, 11 колонок | **пропуск** (0.809 < 0.85) | +16.3 п.п. |
| 2 | наш собственный эталон, первая версия | УТЕЧКА, 4 колонки | **пропуск** (0.687 < 0.85) | +5.3 п.п. |
| 3 | тот же эталон после исправления | ЧИСТО | верно молчит | 0.00 |

## Воспроизведение чисел статьи

```bash
cd rel
python3 fix_ab.py        # задачи A и B      → fix_ab_auc.csv, fix_ab_probe.csv
python3 fix_c.py         # задача C          → fix_c.csv
python3 delta_sweep.py   # кривая I(δ)       → delta_auc.csv, delta_probe.csv
python3 oracle_check.py  # прежняя программа против исправленной
cd ../demo && python3 ft_scene.py   # featuretools в трёх режимах → ft_scene.csv
cd ../fig && python3 make_figs.py && python3 make_figs2.py
```

Сводка всех чисел — `rel/RESULTS.md`.

## Статья

```bash
apt-get install -y texlive-publishers
cd paper && pdflatex pitfall.tex && pdflatex pitfall.tex
```

Четыре страницы, IEEE conference. Перед подачей заполнить авторов и URL репозитория
(помечен красным в разделе Availability).

## Данные

Olist — публичный набор бразильского маркетплейса, 7 таблиц, 112 650 позиций заказов,
сентябрь 2016 — октябрь 2018. Семь файлов `olist_*.csv` кладутся в `rel/`.

Из-за размера они поставляются отдельным архивом `PITFALL_olist_data.tar.gz`:

```bash
mkdir -p rel && tar xzf PITFALL_olist_data.tar.gz -C rel
```

Либо скачать с Kaggle: `olistbr/brazilian-ecommerce`. Нужны файлы
`olist_orders_dataset.csv`, `olist_order_items_dataset.csv`,
`olist_order_reviews_dataset.csv`, `olist_order_payments_dataset.csv`,
`olist_products_dataset.csv`, `olist_sellers_dataset.csv`,
`olist_customers_dataset.csv`.

## Границы метода

- Колонка без метки доступности (изменяемый статус без истории) **непроверяема**:
  усечённая база для неё неотличима от полной.
- Недетерминированная программа даёт расхождение без утечки — нужен фиксированный seed.
- Гарантия односторонняя: инструмент находит утечки, но не сертифицирует их отсутствие.
