"""
Оракул корректности по времени — дифференциальное исполнение (§4 шаг 1 runbook).

Свойство: расхождение выходов на полной и усечённой базе есть ДОКАЗАТЕЛЬСТВО того,
что программа прочитала строку с временем > момента предсказания. Не подозрение.

Обратное неверно: совпадение не доказывает корректность (программа могла прочитать
будущее и не использовать его). Это осознанная односторонность, она нам и нужна:
все вердикты «нарушение» — железные.
"""
import numpy as np
import pandas as pd

# какие таблицы Olist по какой колонке живут во времени
TIME_COLS = {
    "orders": "order_purchase_timestamp",
    "order_items": "ts",
    "reviews": "review_creation_date",
    "payments": "ts",
    # sellers / products / customers — справочники без времени
}


def truncate(db: dict, seed_time, time_cols=TIME_COLS) -> dict:
    """Оставить только строки с time <= seed_time. Справочники не трогаем."""
    seed_time = pd.Timestamp(seed_time)
    out = {}
    for name, df in db.items():
        tc = time_cols.get(name)
        if tc is None or tc not in df.columns:
            out[name] = df
        else:
            out[name] = df[df[tc] <= seed_time]
    return out


def frames_equal(a: pd.DataFrame, b: pd.DataFrame, atol=1e-9, nan_equal=True) -> bool:
    # ВАЖНО (найдено R3 PRESTUDY2_runbook.md, отрицательный контроль): было
    # `return False` безусловно при любом None -- значит функция, которая
    # детерминированно ничего не возвращает (например, забыла return), давала
    # False on None even in identical calls и всегда получала LEAK, хотя полный
    # и усечённый вызов физически не могли разойтись. a is b корректно уравнивает
    # два None между собой, оставляя одиночный None как расхождение (законный LEAK/ошибка).
    if a is None or b is None:
        return a is b
    if a.shape != b.shape:
        return False
    if list(a.columns) != list(b.columns):
        return False
    a = a.sort_index(axis=0)
    b = b.reindex(a.index)
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(dtype="float64"), y.to_numpy(dtype="float64")
            both_nan = np.isnan(xv) & np.isnan(yv)
            if not nan_equal and both_nan.any():
                return False
            diff = np.abs(np.where(both_nan, 0.0, xv - yv))
            if not np.all(np.where(both_nan, True, diff <= atol)):
                return False
        else:
            xs, ys = x.astype(object).where(x.notna(), None), y.astype(object).where(y.notna(), None)
            if not xs.equals(ys):
                return False
    return True


def is_pit_correct(program, db, entity, seed_time, time_cols=TIME_COLS, return_detail=False):
    """program(db, entity, seed_time) -> DataFrame признаков, индекс = сущности."""
    full = program(db, entity, seed_time)
    trunc = program(truncate(db, seed_time, time_cols), entity, seed_time)
    ok = frames_equal(full, trunc)
    if not return_detail:
        return ok
    detail = {}
    if not ok and full is not None and trunc is not None and full.shape == trunc.shape \
            and list(full.columns) == list(trunc.columns):
        bad = []
        for c in full.columns:
            if not frames_equal(full[[c]], trunc[[c]]):
                bad.append(c)
        detail["differing_columns"] = bad
        detail["n_differing"] = len(bad)
        detail["n_total"] = full.shape[1]
    return ok, detail
