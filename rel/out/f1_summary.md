# f1: набор ячеек

Строк в основном кадре: 26,080. Гранулярность меток: mixed: day (<2005) / second (>=2005).

## Побочная временная ось

| column        | time_column   |     n |   median_seconds |   median_days |   p90_days |   max_days |   share_positive |
|:--------------|:--------------|------:|-----------------:|--------------:|-----------:|-----------:|-----------------:|
| position      | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| points        | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| laps          | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| dnf           | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| rank          | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| milliseconds  | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |
| position_gain | avail_ts      | 26080 |                1 |             0 |          0 |          0 |                1 |

## Непроверяемые колонки (нет метки доступности)

- results.statusId для гонок до 2005 г.: точный момент финиша в базе отсутствует, известен только день; берётся нижняя граница «строго позже старта»

## Дифференциальное исполнение

| dataset   | seed             | program   | verdict   | columns                                    |   cells | note   |   seconds |
|:----------|:-----------------|:----------|:----------|:-------------------------------------------|--------:|:-------|----------:|
| f1        | negative_control | naive     | CLEAN     |                                            |       0 |        |      0.02 |
| f1        | negative_control | pit       | CLEAN     |                                            |       0 |        |      0.04 |
| f1        | 1996-03-10       | naive     | LEAK      | position_mean;points_mean;dnf_mean;dnf_sum |      65 |        |      0.02 |
| f1        | 1996-03-10       | pit       | CLEAN     |                                            |       0 |        |      0.03 |
| f1        | 2000-03-12       | naive     | LEAK      | position_mean;points_mean;dnf_mean;dnf_sum |      68 |        |      0.02 |
| f1        | 2000-03-12       | pit       | CLEAN     |                                            |       0 |        |      0.03 |
| f1        | 2004-03-07       | naive     | LEAK      | position_mean;points_mean;dnf_mean;dnf_sum |      66 |        |      0.02 |
| f1        | 2004-03-07       | pit       | CLEAN     |                                            |       0 |        |      0.03 |
| f1        | 2010-03-14       | naive     | CLEAN     |                                            |       0 |        |      0.02 |
| f1        | 2010-03-14       | pit       | CLEAN     |                                            |       0 |        |      0.03 |
| f1        | 2015-03-15       | naive     | CLEAN     |                                            |       0 |        |      0.03 |
| f1        | 2015-03-15       | pit       | CLEAN     |                                            |       0 |        |      0.05 |

## Завышение AUC относительно pit, п.п.

|                                                |   1996-1998 |   1999-2001 |   2002-2004 |   2008-2010 |   2013-2015 |   2018-2020 |
|:-----------------------------------------------|------------:|------------:|------------:|------------:|------------:|------------:|
| ('driver_dnf_day_granularity', 'pit')          |        0    |        0    |        0    |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'naive')        |       -0.45 |        2.45 |        3.27 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'own_only')     |        1.08 |        1.52 |        1.84 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'join_only')    |        1.49 |        1.13 |        0.72 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'naive_nbr')    |        1.56 |        0.6  |        2.08 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'both60')       |        2.31 |        0.94 |        2.91 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta5')       |       -0.45 |        2.45 |        3.27 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta10')      |       -0.53 |        2.14 |        3.45 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta15')      |       -0.17 |        2.24 |        2.87 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta20')      |       -0.17 |        2.24 |        2.87 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta30')      |        4.12 |        1.78 |        2.43 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta45')      |        2.83 |        2.14 |        2.23 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta60')      |        2.31 |        0.94 |        2.91 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'delta90')      |        1.99 |        1.22 |        3.09 |      nan    |      nan    |      nan    |
| ('driver_dnf_day_granularity', 'nocut')        |       -3.38 |       -6.49 |       -2.74 |      nan    |      nan    |      nan    |
| ('driver_dnf_second_granularity', 'pit')       |      nan    |      nan    |      nan    |        0    |        0    |        0    |
| ('driver_dnf_second_granularity', 'naive')     |      nan    |      nan    |      nan    |        0    |        0    |        0    |
| ('driver_dnf_second_granularity', 'own_only')  |      nan    |      nan    |      nan    |        0.26 |        6.89 |        1.17 |
| ('driver_dnf_second_granularity', 'join_only') |      nan    |      nan    |      nan    |        3.85 |        0.23 |        1.39 |
| ('driver_dnf_second_granularity', 'naive_nbr') |      nan    |      nan    |      nan    |        0    |        0    |        0    |
| ('driver_dnf_second_granularity', 'both60')    |      nan    |      nan    |      nan    |        3.16 |        5.54 |        0.22 |
| ('driver_dnf_second_granularity', 'delta5')    |      nan    |      nan    |      nan    |        3.16 |        6.58 |        1.4  |
| ('driver_dnf_second_granularity', 'delta10')   |      nan    |      nan    |      nan    |        3.52 |        4.24 |        2.45 |
| ('driver_dnf_second_granularity', 'delta15')   |      nan    |      nan    |      nan    |        1.52 |        5.35 |        1.13 |
| ('driver_dnf_second_granularity', 'delta20')   |      nan    |      nan    |      nan    |        1.52 |        5.35 |        1.13 |
| ('driver_dnf_second_granularity', 'delta30')   |      nan    |      nan    |      nan    |        3.17 |        6.86 |        0.74 |
| ('driver_dnf_second_granularity', 'delta45')   |      nan    |      nan    |      nan    |        2.56 |        6.06 |        1.37 |
| ('driver_dnf_second_granularity', 'delta60')   |      nan    |      nan    |      nan    |        3.16 |        5.54 |        0.22 |
| ('driver_dnf_second_granularity', 'delta90')   |      nan    |      nan    |      nan    |        3.07 |        5.21 |        1.35 |
| ('driver_dnf_second_granularity', 'nocut')     |      nan    |      nan    |      nan    |       -6.98 |        1.59 |       -1.88 |

## Промышленная проверка «максимальный AUC одного признака»

|                                                |   1996-1998 |   1999-2001 |   2002-2004 |   2008-2010 |   2013-2015 |   2018-2020 |
|:-----------------------------------------------|------------:|------------:|------------:|------------:|------------:|------------:|
| ('driver_dnf_day_granularity', 'pit')          |       0.805 |       0.764 |       0.805 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'naive')        |       0.807 |       0.769 |       0.82  |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'own_only')     |       0.809 |       0.77  |       0.825 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'join_only')    |       0.805 |       0.766 |       0.813 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'naive_nbr')    |       0.805 |       0.764 |       0.813 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'both60')       |       0.809 |       0.77  |       0.825 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta5')       |       0.807 |       0.769 |       0.82  |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta10')      |       0.807 |       0.77  |       0.82  |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta15')      |       0.807 |       0.769 |       0.822 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta20')      |       0.807 |       0.769 |       0.822 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta30')      |       0.808 |       0.769 |       0.822 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta45')      |       0.808 |       0.768 |       0.824 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta60')      |       0.809 |       0.77  |       0.825 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'delta90')      |       0.808 |       0.771 |       0.828 |     nan     |     nan     |     nan     |
| ('driver_dnf_day_granularity', 'nocut')        |       0.78  |       0.753 |       0.769 |     nan     |     nan     |     nan     |
| ('driver_dnf_second_granularity', 'pit')       |     nan     |     nan     |     nan     |       0.728 |       0.748 |       0.722 |
| ('driver_dnf_second_granularity', 'naive')     |     nan     |     nan     |     nan     |       0.728 |       0.748 |       0.722 |
| ('driver_dnf_second_granularity', 'own_only')  |     nan     |     nan     |     nan     |       0.728 |       0.793 |       0.739 |
| ('driver_dnf_second_granularity', 'join_only') |     nan     |     nan     |     nan     |       0.751 |       0.758 |       0.731 |
| ('driver_dnf_second_granularity', 'naive_nbr') |     nan     |     nan     |     nan     |       0.728 |       0.748 |       0.722 |
| ('driver_dnf_second_granularity', 'both60')    |     nan     |     nan     |     nan     |       0.751 |       0.793 |       0.739 |
| ('driver_dnf_second_granularity', 'delta5')    |     nan     |     nan     |     nan     |       0.748 |       0.792 |       0.741 |
| ('driver_dnf_second_granularity', 'delta10')   |     nan     |     nan     |     nan     |       0.748 |       0.791 |       0.741 |
| ('driver_dnf_second_granularity', 'delta15')   |     nan     |     nan     |     nan     |       0.749 |       0.789 |       0.735 |
| ('driver_dnf_second_granularity', 'delta20')   |     nan     |     nan     |     nan     |       0.749 |       0.789 |       0.735 |
| ('driver_dnf_second_granularity', 'delta30')   |     nan     |     nan     |     nan     |       0.75  |       0.793 |       0.736 |
| ('driver_dnf_second_granularity', 'delta45')   |     nan     |     nan     |     nan     |       0.751 |       0.793 |       0.738 |
| ('driver_dnf_second_granularity', 'delta60')   |     nan     |     nan     |     nan     |       0.751 |       0.793 |       0.739 |
| ('driver_dnf_second_granularity', 'delta90')   |     nan     |     nan     |     nan     |       0.753 |       0.793 |       0.739 |
| ('driver_dnf_second_granularity', 'nocut')     |     nan     |     nan     |     nan     |       0.694 |       0.762 |       0.728 |

## Базовое качество (pit)

| task                          |   1996-1998 |   1999-2001 |   2002-2004 |   2008-2010 |   2013-2015 |   2018-2020 |
|:------------------------------|------------:|------------:|------------:|------------:|------------:|------------:|
| driver_dnf_day_granularity    |       0.839 |       0.859 |       0.854 |     nan     |     nan     |     nan     |
| driver_dnf_second_granularity |     nan     |     nan     |     nan     |       0.817 |       0.778 |       0.809 |
