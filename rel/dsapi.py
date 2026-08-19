"""
Общий слой для прогона одного и того же набора экспериментов на любой базе.

Три сущности:

  DatasetAdapter  — база: таблицы, отношение доступности, срез истории на момент,
                    список задач, программы признаков для дифференциального исполнения;
  TaskSpec        — задача: сущности и метка на момент, группы признаков;
  MODES           — временная семантика ячейки. Набор признаков во всех режимах
                    один и тот же, меняется ТОЛЬКО то, что видно программе.

Правило, ради которого всё так устроено: между режимами меняется временная
семантика и ничего больше. Модель фиксирована (LightGBM, те же параметры, seed 0),
иначе смена бустера сама по себе даёт до 11.5 п.п. и накрывает измеряемый эффект.

Режим задаётся по группам признаков: группа -> (сдвиг отсечки в днях | "max", pit).
  pit=True   — маска доступности применяется: колонка со своей более поздней меткой
               обнуляется, если эта метка позже отсечки;
  pit=False  — «наивно»: строка допущена по времени своего появления, а колонки
               взяты целиком (дефолтный способ ошибиться).
"""
from dataclasses import dataclass, field
from typing import Callable, Optional
import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)
if _os.path.join(_ROOT, "demo") not in _sys.path:
    _sys.path.insert(0, _os.path.join(_ROOT, "demo"))

import numpy as np, pandas as pd
from pitfall import TemporalDB, differential_check, locate, univariate_probe, \
    fixed_model_auc, DATAROBOT, H2O, probe_says          # noqa: F401  (реэкспорт)
from sklearn.metrics import roc_auc_score

OUT = _os.path.join(_HERE, "out")


# ───────────────────────────────── задача ─────────────────────────────────

@dataclass
class TaskSpec:
    """Одна задача базы.

    label(seed) -> (entities: np.ndarray, y: pd.Series индексом entities)
    groups: имя группы -> fn(seed, entities, shift, pit) -> DataFrame с индексом
            entities. Отсечку из (shift, pit) вычисляет сам адаптер: у баз, где
            момент предсказания один на ячейку, это ad.cut(seed, shift); у баз,
            где ячейка объединяет много моментов (сезон гонок), — своя для каждого.
            Имя "own" — собственная история сущности, "nbr" — признаки, приходящие
            через путь соединения.
    """
    name: str
    label: Callable
    groups: dict          # fn(seed, entities, shift, pit) -> DataFrame по entities
    train_seeds: list
    test_seeds: list
    min_entities: int = 30
    note: str = ""
    max_train_seeds: int = 0      # 0 = все моменты строго раньше тестового

    @property
    def has_join_path(self):
        return "nbr" in self.groups


# ───────────────────────────────── режимы ─────────────────────────────────

MAX = "max"          # отсечки нет: берём максимум временных меток базы

def _mode_all(shift, pit):
    return lambda groups: {g: (shift, pit) for g in groups}

DELTAS = [5, 10, 15, 20, 30, 45, 60, 90]

def build_modes(groups):
    """Режимы для набора групп признаков. Режимы, требующие пути соединения,
    появляются только если группа nbr есть."""
    m = {
        "pit":   {g: (0, True) for g in groups},
        "naive": {g: (0, False) for g in groups},
        "nocut": {g: (MAX, True) for g in groups},
    }
    for d in DELTAS:
        m[f"delta{d}"] = {g: (d, True) for g in groups}
    if "nbr" in groups:
        m["own_only"]  = {g: ((60, True) if g == "own" else (0, True)) for g in groups}
        m["join_only"] = {g: ((60, True) if g == "nbr" else (0, True)) for g in groups}
        m["naive_nbr"] = {g: ((0, False) if g == "nbr" else (0, True)) for g in groups}
        m["both60"]    = {g: (60, True) for g in groups}
    return m

MODE_ORDER = ["pit", "naive", "own_only", "join_only", "naive_nbr", "both60",
              *[f"delta{d}" for d in DELTAS], "nocut"]


# ──────────────────────────────── адаптер ────────────────────────────────

class DatasetAdapter:
    """Пять мест, которые заполняет новая база. См. adapters/_template.py."""

    name: str = "?"
    #: колонка-метка появления строки в основном событийном кадре
    ts_col: str = "ts"
    #: колонка значения -> колонка с её собственной, более поздней меткой доступности
    AVAIL: dict = {}
    #: колонки без метки доступности вообще (изменяемое поле без истории)
    UNCHECKABLE: list = []
    #: гранулярность временных меток: "second" | "day"
    granularity: str = "second"

    # 1. загрузка ------------------------------------------------------------
    def load(self):
        """-> плоский событийный кадр ev с колонкой self.ts_col и колонками
        меток доступности из AVAIL."""
        raise NotImplementedError

    # 2. срез истории --------------------------------------------------------
    def visible(self, row_cut, avail_cut=None, pit=True):
        """История, видимая на момент. pit=False воспроизводит наивное поведение:
        строка допущена по времени появления, колонки взяты целиком."""
        ev = self.ev
        if avail_cut is None:
            avail_cut = row_cut
        h = ev[ev[self.ts_col] <= row_cut].copy()
        if pit:
            for col, tcol in self.AVAIL.items():
                if col in h.columns:
                    h.loc[~(h[tcol] <= avail_cut), col] = np.nan
        return h

    # 3. задачи --------------------------------------------------------------
    def tasks(self):
        """-> [TaskSpec]"""
        raise NotImplementedError

    # 4. база для дифференциального исполнения --------------------------------
    def temporal_db(self):
        """-> TemporalDB с отношением доступности (для оракула и локализации)."""
        raise NotImplementedError

    # 5. программы признаков для оракула --------------------------------------
    def programs(self):
        """-> {имя: program(db, seed, entities) -> DataFrame}. Обязательно
        должны быть 'naive' (протекает) и 'pit' (не протекает) — на этом стоят ворота."""
        raise NotImplementedError

    def oracle_entities(self, seed):
        """Сущности, на которых гоняется оракул."""
        raise NotImplementedError

    # ── общее ──────────────────────────────────────────────────────────────
    def __init__(self):
        self.ev = self.load()
        self.TMAX = self.ev[self.ts_col].max()
        # Момент отрицательного контроля — максимум по ВСЕМ временным меткам, а не
        # только по времени строки. На Olist доставка приходит позже последнего заказа,
        # поэтому при seed = max(ts) усечение всё ещё маскирует late/delay_days,
        # и наивная программа расходится — срабатывание верное, а контроль неверный.
        ts = [self.ev[self.ts_col].max()]
        for tcol in set(self.AVAIL.values()):
            if tcol in self.ev.columns:
                ts.append(self.ev[tcol].max())
        self.TMAX_ALL = max(t for t in ts if pd.notna(t))

    def to_seed(self, seed_str):
        """Ключ ячейки -> момент. По умолчанию это метка времени; у баз, где
        ячейка объединяет много моментов, — сам ключ (например, номер сезона)."""
        return pd.Timestamp(seed_str)

    def cut(self, seed, shift):
        """Отсечка режима для момента seed."""
        if shift == MAX:
            return self.TMAX
        return seed + pd.Timedelta(days=shift)

    def side_axis_report(self):
        """Побочная временная ось: лаг каждой колонки со своей меткой."""
        rows = []
        for col, tcol in self.AVAIL.items():
            lag = (self.ev[tcol] - self.ev[self.ts_col]).dt.total_seconds() / 86400
            lag = lag.dropna()
            if not len(lag):
                continue
            rows.append(dict(column=col, time_column=tcol, n=len(lag),
                             median_seconds=round(float(lag.median()) * 86400, 1),
                             median_days=round(float(lag.median()), 2),
                             p90_days=round(float(lag.quantile(0.9)), 2),
                             max_days=round(float(lag.max()), 2),
                             share_positive=round(float((lag > 0).mean()), 4)))
        return pd.DataFrame(rows)


# ────────────────────── отрицательный контроль ──────────────────────

def restrict_defined(db):
    """База без строк, у которых метка доступности не определена (NaT).

    Зачем: строка с неопределённой меткой маскируется усечением ПРИ ЛЮБОМ t,
    включая бесконечность, — метод считает её непроверяемой по построению.
    Такая строка даёт срабатывание и на отрицательном контроле, и это верное
    срабатывание, а не ложное. Чтобы контроль проверял то, ради чего он нужен
    («оракул молчит, когда будущего нет»), эти строки из него исключаются,
    а сам факт их наличия выносится в непроверяемый класс.
    """
    out = {}
    for name, dfr in db.tables.items():
        d = dfr
        vt = db.value_time.get(name, {})
        if vt:
            m = pd.Series(True, index=d.index)
            for tcol in set(vt.values()):
                m &= d[tcol].notna()
            d = d[m]
        rt = db.row_time.get(name)
        if rt is not None:
            d = d[d[rt].notna()]
        out[name] = d
    return TemporalDB(out, db.row_time, db.value_time)


def undefined_availability_report(db):
    """Сколько строк непроверяемы из-за отсутствующей метки доступности."""
    rows = []
    for name, d in db.tables.items():
        for col, tcol in db.value_time.get(name, {}).items():
            k = int(d[tcol].isna().sum())
            if k:
                rows.append(dict(table=name, column=col, time_column=tcol,
                                 rows_without_stamp=k, share=round(k / max(len(d), 1), 4)))
    return pd.DataFrame(rows)


# ──────────────────────── прогон одной ячейки ────────────────────────

def auc_ci(Xtr, ytr, Xte, yte, B=200, seed=0):
    """Бутстрэп-интервал AUC по тестовым строкам. Модель обучается один раз:
    интервал отражает шум тестовой выборки, а не переобучение. Нужен там, где
    сущностей на момент мало (rel-f1: 20–25 гонщиков в гонке)."""
    from lightgbm import LGBMClassifier
    Xtr_ = Xtr.select_dtypes(include=[np.number])
    Xte_ = Xte.select_dtypes(include=[np.number]).reindex(columns=Xtr_.columns)
    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                       random_state=0, n_jobs=2).fit(Xtr_, ytr)
    p = m.predict_proba(Xte_)[:, 1]
    y = np.asarray(yte)
    rng = np.random.default_rng(seed)
    n, out = len(y), []
    for _ in range(B):
        i = rng.integers(0, n, n)
        if len(np.unique(y[i])) < 2:
            continue
        out.append(roc_auc_score(y[i], p[i]))
    if not out:
        return np.nan, np.nan
    return round(float(np.percentile(out, 2.5)), 4), round(float(np.percentile(out, 97.5)), 4)



def run_cell(ad, task, mode_name, mode, test_seed):
    """Одна ячейка: обучение на всех моментах строго раньше тестового, оценка на нём.
    Возвращает dict со строкой результата либо None, если ячейка вырождена."""
    tr_seeds = [s for s in task.train_seeds if s < test_seed]
    if task.max_train_seeds:
        tr_seeds = tr_seeds[-task.max_train_seeds:]

    def build(seed_str):
        seed = ad.to_seed(seed_str)
        ents, y = task.label(seed)
        if ents is None or len(ents) < task.min_entities or y.nunique() < 2:
            return None, None
        parts = []
        for g, fn in task.groups.items():
            shift, pit = mode[g]
            parts.append(fn(seed, ents, shift, pit))
        return pd.concat(parts, axis=1), y

    Xtr, ytr = [], []
    for s in tr_seeds:
        X, y = build(s)
        if X is None:
            continue
        Xtr.append(X); ytr.append(y)
    if not Xtr:
        return None
    Xtr = pd.concat(Xtr); ytr = pd.concat(ytr)
    Xte, yte = build(test_seed)
    if Xte is None:
        return None

    auc = fixed_model_auc(Xtr, ytr, Xte, yte)
    lo, hi = auc_ci(Xtr, ytr, Xte, yte)
    probe, who = univariate_probe(Xte, yte)
    return dict(dataset=ad.name, task=task.name, test_seed=test_seed, mode=mode_name,
                n_test=int(len(yte)), pos_rate=round(float(yte.mean()), 3),
                auc=round(float(auc), 6), auc_lo=lo, auc_hi=hi,
                probe=round(float(probe), 6), probe_feature=who,
                probe_datarobot=probe_says(probe, DATAROBOT),
                probe_h2o=probe_says(probe, H2O))
