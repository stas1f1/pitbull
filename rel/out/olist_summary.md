# olist: набор ячеек

Строк в основном кадре: 112,650. Гранулярность меток: second.

## Побочная временная ось

| column       | time_column   |      n |   median_seconds |   median_days |   p90_days |   max_days |   share_positive |
|:-------------|:--------------|-------:|-----------------:|--------------:|-----------:|-----------:|-----------------:|
| review_score | review_ts     | 111708 |           914771 |         10.59 |      23.26 |     147.9  |                1 |
| late         | deliv_ts      | 110196 |           879922 |         10.18 |      22.92 |     209.63 |                1 |
| delay_days   | deliv_ts      | 110196 |           879922 |         10.18 |      22.92 |     209.63 |                1 |

## Непроверяемые колонки (нет метки доступности)

- orders.order_status (canceled): изменяемое поле без истории

## Дифференциальное исполнение

| dataset   | seed             | program   | verdict   | columns                                      |   cells | note   |   seconds |
|:----------|:-----------------|:----------|:----------|:---------------------------------------------|--------:|:-------|----------:|
| olist     | negative_control | naive     | LEAK      | late_mean                                    |     478 |        |      0.15 |
| olist     | negative_control | pit       | CLEAN     |                                              |       0 |        |      0.14 |
| olist     | 2018-01-01       | naive     | LEAK      | review_score_mean;review_score_min;late_mean |    1222 |        |      0.07 |
| olist     | 2018-01-01       | pit       | CLEAN     |                                              |       0 |        |      0.08 |
| olist     | 2018-04-01       | naive     | LEAK      | review_score_mean;review_score_min;late_mean |    1679 |        |      0.09 |
| olist     | 2018-04-01       | pit       | CLEAN     |                                              |       0 |        |      0.12 |
| olist     | 2018-07-01       | naive     | LEAK      | review_score_mean;review_score_min;late_mean |    1462 |        |      0.15 |
| olist     | 2018-07-01       | pit       | CLEAN     |                                              |       0 |        |      0.13 |

## Завышение AUC относительно pit, п.п.

|                                   |   2018-01-01 |   2018-04-01 |   2018-07-01 |
|:----------------------------------|-------------:|-------------:|-------------:|
| ('A_seller_activity', 'pit')      |         0    |         0    |         0    |
| ('A_seller_activity', 'naive')    |         0.16 |         0.21 |         0.32 |
| ('A_seller_activity', 'delta5')   |         3.35 |         2.52 |         3.06 |
| ('A_seller_activity', 'delta10')  |         5.78 |         4.45 |         4.54 |
| ('A_seller_activity', 'delta15')  |         6.81 |         5.57 |         6.48 |
| ('A_seller_activity', 'delta20')  |         8.73 |         6.69 |         8.61 |
| ('A_seller_activity', 'delta30')  |        10.74 |         8.7  |        11.47 |
| ('A_seller_activity', 'delta45')  |        12.56 |        10.86 |        15.25 |
| ('A_seller_activity', 'delta60')  |        13.7  |        11.96 |        16.89 |
| ('A_seller_activity', 'delta90')  |        16.12 |        13.97 |        16.89 |
| ('A_seller_activity', 'nocut')    |        13.95 |        12.32 |        16.89 |
| ('B_seller_quality', 'pit')       |         0    |         0    |         0    |
| ('B_seller_quality', 'naive')     |         3.09 |         5.26 |         3.78 |
| ('B_seller_quality', 'delta5')    |         2.24 |        -0.32 |         0.55 |
| ('B_seller_quality', 'delta10')   |         2.25 |         3.42 |         5.12 |
| ('B_seller_quality', 'delta15')   |         3    |         3.63 |         4.83 |
| ('B_seller_quality', 'delta20')   |         5.26 |         5.48 |         4.13 |
| ('B_seller_quality', 'delta30')   |         7.66 |         8.67 |         5.83 |
| ('B_seller_quality', 'delta45')   |        11.96 |        13.17 |        13.24 |
| ('B_seller_quality', 'delta60')   |        13.45 |        17.09 |        17    |
| ('B_seller_quality', 'delta90')   |        25.09 |        21.73 |        19.86 |
| ('B_seller_quality', 'nocut')     |        16.61 |        13.41 |        18.03 |
| ('C_product_demand', 'pit')       |         0    |         0    |         0    |
| ('C_product_demand', 'naive')     |         0.99 |         0.27 |        -0.1  |
| ('C_product_demand', 'delta5')    |         3.52 |         4.03 |         3.03 |
| ('C_product_demand', 'delta10')   |         7.12 |         6.95 |         4.93 |
| ('C_product_demand', 'delta15')   |         9.6  |         8.67 |         6.52 |
| ('C_product_demand', 'delta20')   |        12.21 |        11.05 |         9.82 |
| ('C_product_demand', 'delta30')   |        15.33 |        14.3  |        14.76 |
| ('C_product_demand', 'delta45')   |        19.47 |        18.09 |        22.08 |
| ('C_product_demand', 'delta60')   |        23.24 |        20.27 |        25.83 |
| ('C_product_demand', 'delta90')   |        28.62 |        25.47 |        25.83 |
| ('C_product_demand', 'nocut')     |        26.99 |        24.66 |        25.83 |
| ('C_product_demand', 'own_only')  |        22.83 |        20.31 |        25.83 |
| ('C_product_demand', 'join_only') |         5.06 |         3.2  |         3.03 |
| ('C_product_demand', 'naive_nbr') |         0.79 |         0.01 |         0.15 |
| ('C_product_demand', 'both60')    |        23.24 |        20.27 |        25.83 |

## Промышленная проверка «максимальный AUC одного признака»

|                                   |   2018-01-01 |   2018-04-01 |   2018-07-01 |
|:----------------------------------|-------------:|-------------:|-------------:|
| ('A_seller_activity', 'pit')      |        0.837 |        0.861 |        0.833 |
| ('A_seller_activity', 'naive')    |        0.837 |        0.861 |        0.833 |
| ('A_seller_activity', 'delta5')   |        0.874 |        0.89  |        0.865 |
| ('A_seller_activity', 'delta10')  |        0.898 |        0.912 |        0.883 |
| ('A_seller_activity', 'delta15')  |        0.915 |        0.924 |        0.901 |
| ('A_seller_activity', 'delta20')  |        0.93  |        0.939 |        0.922 |
| ('A_seller_activity', 'delta30')  |        0.95  |        0.957 |        0.952 |
| ('A_seller_activity', 'delta45')  |        0.969 |        0.975 |        0.986 |
| ('A_seller_activity', 'delta60')  |        0.983 |        0.985 |        1     |
| ('A_seller_activity', 'delta90')  |        1     |        1     |        1     |
| ('A_seller_activity', 'nocut')    |        0.933 |        0.928 |        1     |
| ('B_seller_quality', 'pit')       |        0.572 |        0.61  |        0.602 |
| ('B_seller_quality', 'naive')     |        0.623 |        0.687 |        0.657 |
| ('B_seller_quality', 'delta5')    |        0.582 |        0.643 |        0.641 |
| ('B_seller_quality', 'delta10')   |        0.606 |        0.669 |        0.652 |
| ('B_seller_quality', 'delta15')   |        0.622 |        0.686 |        0.67  |
| ('B_seller_quality', 'delta20')   |        0.646 |        0.699 |        0.676 |
| ('B_seller_quality', 'delta30')   |        0.673 |        0.723 |        0.709 |
| ('B_seller_quality', 'delta45')   |        0.706 |        0.769 |        0.778 |
| ('B_seller_quality', 'delta60')   |        0.744 |        0.789 |        0.819 |
| ('B_seller_quality', 'delta90')   |        0.839 |        0.819 |        0.834 |
| ('B_seller_quality', 'nocut')     |        0.796 |        0.804 |        0.834 |
| ('C_product_demand', 'pit')       |        0.714 |        0.722 |        0.717 |
| ('C_product_demand', 'naive')     |        0.714 |        0.722 |        0.717 |
| ('C_product_demand', 'delta5')    |        0.749 |        0.763 |        0.758 |
| ('C_product_demand', 'delta10')   |        0.777 |        0.791 |        0.781 |
| ('C_product_demand', 'delta15')   |        0.809 |        0.818 |        0.799 |
| ('C_product_demand', 'delta20')   |        0.835 |        0.843 |        0.833 |
| ('C_product_demand', 'delta30')   |        0.872 |        0.881 |        0.885 |
| ('C_product_demand', 'delta45')   |        0.915 |        0.927 |        0.96  |
| ('C_product_demand', 'delta60')   |        0.95  |        0.952 |        1     |
| ('C_product_demand', 'delta90')   |        1     |        1     |        1     |
| ('C_product_demand', 'nocut')     |        0.871 |        0.917 |        1     |
| ('C_product_demand', 'own_only')  |        0.95  |        0.952 |        1     |
| ('C_product_demand', 'join_only') |        0.714 |        0.722 |        0.717 |
| ('C_product_demand', 'naive_nbr') |        0.714 |        0.722 |        0.717 |
| ('C_product_demand', 'both60')    |        0.95  |        0.952 |        1     |

## Базовое качество (pit)

| task              |   2018-01-01 |   2018-04-01 |   2018-07-01 |
|:------------------|-------------:|-------------:|-------------:|
| A_seller_activity |        0.839 |        0.86  |        0.831 |
| B_seller_quality  |        0.576 |        0.592 |        0.589 |
| C_product_demand  |        0.714 |        0.745 |        0.742 |
