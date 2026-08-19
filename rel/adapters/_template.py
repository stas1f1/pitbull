"""
Шаблон адаптера новой базы. Пять мест, помеченных ЗАПОЛНИТЬ.

Порядок работы (docs/EXTENSION_plan.md §4):

    python3 gate.py  <имя>     ворота приёмки, около минуты — ОБЯЗАТЕЛЬНО первыми
    python3 suite.py <имя>     весь набор ячеек

Ворота не пройдены — ничего на этой базе не публикуем. Правило выведено из провала:
на Olist наш «корректный» эталон протекал, и мы узнали об этом через неделю.

Два способа задать временную опасность базы — достаточно любого:

  а) побочная временная ось: колонка дописывается к строке позже её появления и
     имеет собственную метку (Olist: отзыв через 10 дней, доставка через 10 дней).
     Задаётся через AVAIL: {колонка_значения: колонка_её_метки};
  б) совпадение момента с меткой события: метка хранится с точностью, при которой
     отсечка `<=` впускает само предсказываемое событие (rel-f1: гонки до 2005 г.
     записаны полночью дня гонки). Задаётся тем же AVAIL: метка доступности исхода
     ставится строго позже метки строки.
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REL = _os.path.dirname(_HERE)
if _REL not in _sys.path:
    _sys.path.insert(0, _REL)

import numpy as np, pandas as pd
from dsapi import DatasetAdapter, TaskSpec, TemporalDB

TRAIN_SEEDS = ["...", "..."]      # все моменты обучения
TEST_SEEDS = ["...", "..."]       # моменты, на которых меряем


class Adapter(DatasetAdapter):
    name = "ЗАПОЛНИТЬ"
    ts_col = "ts"
    #: (1) отношение доступности: колонка значения -> колонка с её меткой
    AVAIL = {}
    #: колонки без метки доступности вообще — идут в ограничения, а не в признаки
    UNCHECKABLE = []
    granularity = "second"        # "second" | "day" | "mixed: ..."

    # (2) загрузка: плоский событийный кадр с колонкой ts и колонками меток из AVAIL
    def load(self):
        raise NotImplementedError

    # (3) признаки. Группа "own" — собственная история сущности, "nbr" — то, что
    #     приходит через путь соединения. Отсечку из (shift, pit) считает адаптер:
    #     обычно cut = self.cut(seed, shift).
    def _own(self, seed, ents, shift, pit):
        cut = self.cut(seed, shift)
        h = self.visible(cut, cut, pit)
        raise NotImplementedError

    def _nbr(self, seed, ents, shift, pit):
        cut = self.cut(seed, shift)
        h = self.visible(cut, cut, pit)
        raise NotImplementedError

    # (4) метки: (entities, y) на момент. Метке будущее знать можно — признакам нельзя.
    def _label(self, seed):
        raise NotImplementedError

    def tasks(self):
        return [TaskSpec("ЗАПОЛНИТЬ", self._label, {"own": self._own, "nbr": self._nbr},
                         TRAIN_SEEDS, TEST_SEEDS, 30, "описание задачи")]

    # (5) дифференциальное исполнение: база с отношением доступности и две программы.
    #     'pit' обязана быть ЧИСТО на всех моментах, 'naive' — протекать хотя бы на одном.
    def temporal_db(self):
        return TemporalDB(tables={"flat": self.ev}, row_time={"flat": self.ts_col},
                          value_time={"flat": self.AVAIL})

    def programs(self):
        def naive(db, seed, ents):
            raise NotImplementedError

        def pit(db, seed, ents):
            raise NotImplementedError

        return {"naive": naive, "pit": pit}

    def oracle_entities(self, seed):
        raise NotImplementedError

    ORACLE_SEEDS = TEST_SEEDS
