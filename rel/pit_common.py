"""
Общий загрузчик Olist с ЯВНЫМИ метками доступности для каждой колонки.

Ключевое отличие от leak_multi2/3.py: там строка события фильтровалась по времени
ЗАКАЗА, а колонки, приходящие из связанных таблиц со своей временной осью
(отзыв, факт доставки), брались целиком. Это утечка того же класса, ради которого
затевается вся работа.

Здесь у каждой колонки есть своя метка доступности:
  price, freight_value, product_id, seller_id  -> order_purchase_timestamp
  review_score                                 -> review_creation_date
  late, delay_days                             -> order_delivered_customer_date
  canceled (order_status)                      -> метки нет вообще (см. ниже)

order_status — изменяемое поле без истории. Момент, когда заказ стал canceled,
в данных отсутствует. Отношение доступности для него не определено, поэтому
признак canceled исключён из всех режимов (а не только из корректного), чтобы
набор признаков был одинаков и менялась только временная семантика.
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import numpy as np, pandas as pd

D = _DATA  # Olist CSVs

def load():
    orders = pd.read_csv(D + "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                      "order_estimated_delivery_date"])
    items = pd.read_csv(D + "olist_order_items_dataset.csv")
    rev = pd.read_csv(D + "olist_order_reviews_dataset.csv",
                      usecols=["order_id", "review_score", "review_creation_date"],
                      parse_dates=["review_creation_date"])
    pay = pd.read_csv(D + "olist_order_payments_dataset.csv",
                      usecols=["order_id", "payment_value", "payment_installments"])

    # у заказа может быть несколько отзывов: берём среднюю оценку и время ПОСЛЕДНЕГО,
    # т.к. агрегат целиком становится известен только тогда
    rev = rev.groupby("order_id", as_index=False).agg(
        review_score=("review_score", "mean"),
        review_ts=("review_creation_date", "max"))
    pay = pay.groupby("order_id", as_index=False).agg(pay_value=("payment_value", "sum"),
                                                      pay_inst=("payment_installments", "max"))
    ev = (items.merge(orders[["order_id", "order_purchase_timestamp", "order_status",
                              "order_delivered_customer_date", "order_estimated_delivery_date"]],
                      on="order_id")
               .merge(rev, on="order_id", how="left")
               .merge(pay, on="order_id", how="left"))
    ev["ts"] = ev.order_purchase_timestamp                       # метка доступности строки
    ev["deliv_ts"] = ev.order_delivered_customer_date            # метка доступности late/delay
    ev["delay_days"] = (ev.order_delivered_customer_date - ev.order_estimated_delivery_date).dt.days
    ev["late"] = (ev.delay_days > 0).astype(float)
    ev = ev.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return ev

# колонка -> имя колонки с меткой её доступности (None = доступна вместе со строкой)
AVAIL = {"review_score": "review_ts", "late": "deliv_ts", "delay_days": "deliv_ts"}

def visible(ev, row_cutoff, avail_cutoff=None, pit=True):
    """Срез истории на момент. pit=False воспроизводит прежнее (протекающее) поведение."""
    if avail_cutoff is None:
        avail_cutoff = row_cutoff
    h = ev[ev.ts <= row_cutoff].copy()
    if pit:
        for col, tcol in AVAIL.items():
            if col in h.columns:
                h.loc[~(h[tcol] <= avail_cutoff), col] = np.nan
    return h
