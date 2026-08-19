"""
rel-f1 (Ergast, из RelBench). Даёт то, чего Olist проверить не мог: ошибку на
единицу на данных, где момент предсказания совпадает с меткой события.

Что здесь устроено иначе, чем на Olist
--------------------------------------
Побочной временной оси в духе «отзыв приходит через 10 дней» в Формуле-1 нет.
Зато есть другое: **исход гонки записан меткой старта гонки, а не финиша.**
В базе `results.date` равно `races.date`, то есть моменту, когда гонка ТОЛЬКО
НАЧАЛАСЬ. Отношение доступности, записанное честно: результат гонки доступен
строго позже её старта. Никакой длительности гонки мы не выдумываем — берём
минимальную добавку, потому что важно только «строго позже».

Отсюда естественный момент предсказания: **полночь дня гонки** — ровно то, что
пишет практик, соединяя по дате, а не по метке времени. И тогда:

  * гонки до 2005 года хранятся с точностью до дня (метка = полночь), поэтому
    при отсечке `<=` в историю попадает сама предсказываемая гонка — со своим
    исходом, то есть с меткой;
  * гонки с 2005 года хранят время старта (медиана 12:00), поэтому та же самая
    ошибка `<=` не даёт ничего: строка гонки просто не проходит по времени.

Одна и та же ошибка в одном и том же коде на одной и той же базе: разрушительная
на дневной гранулярности и безвредная на секундной. На Olist эта ошибка дала
ровно 0.00 (§4.3 HANDOVER), и мы записали гипотезу «опасна на дневных данных».
Здесь она проверяется.

Соответствие режимов общего слоя:
  pit    — исход маскируется, если он ещё не наступил (корректно);
  naive  — исход берётся у всякой строки, прошедшей по времени (ошибка на единицу);
  delta* — отсечка сдвинута вперёд на d дней;
  own    — история самого гонщика; nbr — история его команды (путь соединения).

Стартовая позиция `grid` известна до гонки (из квалификации) и поэтому доступна
вместе со строкой — маскируется только то, что определяется в самой гонке.
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REL = _os.path.dirname(_HERE)
_ROOT = _os.path.dirname(_REL)
if _REL not in _sys.path:
    _sys.path.insert(0, _REL)

import numpy as np, pandas as pd
from dsapi import DatasetAdapter, TaskSpec, TemporalDB

DATA = _os.environ.get("PITFALL_EXT_DATA", _os.path.join(_ROOT, "PITFALL_ext_data"))
DB = _os.path.join(DATA, "rel-f1", "db")

# колонки, определяющиеся в самой гонке: доступны строго позже её старта
OUTCOME = ["position", "points", "laps", "dnf", "rank", "milliseconds", "position_gain"]

# Две эры одной базы. Гонки до 2005 г. записаны полночью дня гонки, с 2005 г. —
# временем старта (проверено: доля меток с ненулевым временем суток 0.0 до 2004 г.
# и 1.0 начиная с 2005 г.). Обучение и тест ВСЕГДА внутри одной эры: иначе утечка
# в обучающих моментах меняет модель и смешивается с эффектом на тесте.
DAY_ERA_TESTS = ["1996-1998", "1999-2001", "2002-2004"]
SEC_ERA_TESTS = ["2008-2010", "2013-2015", "2018-2020"]
DAY_ERA_TRAIN = [str(y) for y in range(1986, 2005)]
SEC_ERA_TRAIN = [str(y) for y in range(2005, 2021)]
TRAIN_WINDOW = 10            # сезонов перед тестовым блоком

OWN_AGG = {"position": ["mean", "min"], "points": ["mean", "sum"], "laps": ["mean"],
           "dnf": ["mean", "sum"], "grid": ["mean", "min"]}
NBR_AGG = {"position": ["mean"], "points": ["mean", "sum"], "dnf": ["mean"], "grid": ["mean"]}


class Adapter(DatasetAdapter):
    name = "f1"
    ts_col = "ts"
    AVAIL = {c: "avail_ts" for c in OUTCOME}
    UNCHECKABLE = [
        "results.statusId для гонок до 2005 г.: точный момент финиша в базе отсутствует, "
        "известен только день; берётся нижняя граница «строго позже старта»",
    ]
    granularity = "mixed: day (<2005) / second (>=2005)"

    def load(self):
        res = pd.read_parquet(_os.path.join(DB, "results.parquet"))
        races = pd.read_parquet(_os.path.join(DB, "races.parquet"))[
            ["raceId", "year", "round", "circuitId", "date"]].rename(columns={"date": "race_ts"})
        ev = res.merge(races, on="raceId", how="left")
        ev["ts"] = ev.race_ts                       # метка строки: старт гонки
        # исход известен строго позже старта; длительность гонки не выдумываем
        ev["avail_ts"] = ev.ts + pd.Timedelta(seconds=1)
        ev["dnf"] = (ev.statusId != 1).astype(float)
        ev["position"] = pd.to_numeric(ev.position, errors="coerce")
        ev["position_gain"] = ev.position - ev.grid
        ev["seed_ts"] = ev.ts.dt.normalize()        # момент предсказания: полночь дня гонки
        ev = ev.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        return ev

    def __init__(self):
        super().__init__()
        self.races = (self.ev[["raceId", "year", "ts", "seed_ts"]]
                      .drop_duplicates("raceId").sort_values("ts").reset_index(drop=True))
        self._ts = self.ev.ts.values
        self._avail = self.ev.avail_ts.values
        self._hist_cache = {}

    # Срез истории через searchsorted: копия кадра на каждый момент недопустима —
    # моментов тысячи. Маскируемые строки лежат непрерывным хвостом, потому что
    # avail_ts = ts + 1 с и кадр отсортирован по ts.
    def visible(self, row_cut, avail_cut=None, pit=True):
        if avail_cut is None:
            avail_cut = row_cut
        ev = self.ev
        k = int(np.searchsorted(self._ts, np.datetime64(pd.Timestamp(row_cut)), side="right"))
        h = ev.iloc[:k]
        if not pit or not k:
            return h
        k2 = int(np.searchsorted(self._avail, np.datetime64(pd.Timestamp(avail_cut)), side="right"))
        if k2 >= k:
            return h                      # маскировать нечего
        h = h.copy()
        h.iloc[k2:, [h.columns.get_loc(c) for c in OUTCOME]] = np.nan
        return h

    def _hist(self, moment, shift, pit):
        key = (moment, shift, pit)
        if key not in self._hist_cache:
            if len(self._hist_cache) > 64:
                self._hist_cache.clear()
            cut = self.cut(moment, shift)
            self._hist_cache[key] = self.visible(cut, cut, pit)
        return self._hist_cache[key]

    def to_seed(self, seed_str):
        """Ячейка — блок сезонов: одна гонка даёт 20–25 сущностей, а один сезон
        340–460 строк; для устойчивого AUC этого мало, поэтому тестовая ячейка —
        три сезона (около 1100 строк). Формат: "1996" или "1996-1998"."""
        a, _, b = seed_str.partition("-")
        return tuple(range(int(a), int(b or a) + 1))

    def _season_races(self, block):
        r = self.races[self.races.year.isin(block)]
        return list(zip(r.raceId, r.seed_ts))

    # ── признаки ────────────────────────────────────────────────────────────
    def _own(self, season, ents, shift, pit):
        out = []
        for rid, moment in self._season_races(season):
            drivers = [d for (r, d) in ents if r == rid]
            if not drivers:
                continue
            h = self._hist(moment, shift, pit)
            h = h[h.driverId.isin(drivers)]
            g = h.groupby("driverId")
            f = g.agg(OWN_AGG); f.columns = ["own_" + "_".join(c) for c in f.columns]
            f["own_n_races"] = g.raceId.nunique()
            f["own_days_since_last"] = (moment - g.ts.max()).dt.total_seconds() / 86400
            f["own_days_since_first"] = (moment - g.ts.min()).dt.total_seconds() / 86400
            f = f.reindex(drivers)
            f.index = pd.MultiIndex.from_product([[rid], drivers], names=["raceId", "driverId"])
            out.append(f)
        return pd.concat(out).reindex(ents) if out else pd.DataFrame(index=ents)

    def _nbr(self, season, ents, shift, pit):
        """Путь соединения: гонщик -> команда его последней гонки до момента ->
        история этой команды. Команда берётся из видимой истории, не из будущего."""
        out = []
        for rid, moment in self._season_races(season):
            drivers = [d for (r, d) in ents if r == rid]
            if not drivers:
                continue
            h = self._hist(moment, shift, pit)
            last = (h[h.driverId.isin(drivers)].sort_values("ts")
                    .drop_duplicates("driverId", keep="last").set_index("driverId").constructorId)
            g = h.groupby("constructorId")
            s = g.agg(NBR_AGG); s.columns = ["nbr_" + "_".join(c) for c in s.columns]
            s["nbr_n_races"] = g.raceId.nunique()
            s["nbr_n_drivers"] = g.driverId.nunique()
            s["nbr_days_since_last"] = (moment - g.ts.max()).dt.total_seconds() / 86400
            key = last.reindex(drivers)
            f = s.reindex(key.values); f.index = pd.MultiIndex.from_product(
                [[rid], drivers], names=["raceId", "driverId"])
            out.append(f)
        return pd.concat(out).reindex(ents) if out else pd.DataFrame(index=ents)

    # ── метки ───────────────────────────────────────────────────────────────
    def _label_dnf(self, season):
        """Сущности — стартовый состав гонки (он публикуется заранее), метка — сход.
        Из results берётся только ключ (какие гонщики заявлены), исход идёт в метку."""
        rids = [r for r, _ in self._season_races(season)]
        d = self.ev[self.ev.raceId.isin(rids)]
        if not len(d):
            return None, None
        idx = pd.MultiIndex.from_arrays([d.raceId.values, d.driverId.values],
                                        names=["raceId", "driverId"])
        y = pd.Series(d.dnf.values.astype(int), index=idx)
        y = y[~y.index.duplicated()]
        return y.index, y

    def tasks(self):
        note = ("сойдёт ли гонщик с дистанции; момент предсказания — полночь дня гонки. "
                "Сущности — стартовый состав (публикуется заранее), метка — исход")
        return [
            TaskSpec("driver_dnf_day_granularity", self._label_dnf,
                     {"own": self._own, "nbr": self._nbr},
                     DAY_ERA_TRAIN, DAY_ERA_TESTS, 50,
                     note + ". Метка гонки — полночь: отсечка `<=` впускает саму гонку",
                     max_train_seeds=TRAIN_WINDOW),
            TaskSpec("driver_dnf_second_granularity", self._label_dnf,
                     {"own": self._own, "nbr": self._nbr},
                     SEC_ERA_TRAIN, SEC_ERA_TESTS, 50,
                     note + ". Метка гонки — время старта: та же отсечка её не впускает",
                     max_train_seeds=TRAIN_WINDOW),
        ]

    # ── дифференциальное исполнение ─────────────────────────────────────────
    ORACLE_AGGS = {"position": ["mean"], "points": ["mean"], "dnf": ["mean", "sum"]}

    def temporal_db(self):
        return TemporalDB(tables={"flat": self.ev}, row_time={"flat": "ts"},
                          value_time={"flat": {c: "avail_ts" for c in OUTCOME}})

    def programs(self):
        A = self.ORACLE_AGGS

        def naive(db, seed, ents):
            h = db.tables["flat"]
            h = h[(h.ts <= seed) & (h.driverId.isin(ents))]
            g = h.groupby("driverId"); f = g.agg(A); f.columns = ["_".join(c) for c in f.columns]
            return f.reindex(ents)

        def pit(db, seed, ents):
            h = db.tables["flat"]
            h = h[(h.ts <= seed) & (h.driverId.isin(ents))].copy()
            for col in OUTCOME:
                h.loc[~(h.avail_ts <= seed), col] = np.nan
            g = h.groupby("driverId"); f = g.agg(A); f.columns = ["_".join(c) for c in f.columns]
            return f.reindex(ents)

        return {"naive": naive, "pit": pit}

    def oracle_entities(self, seed):
        s = pd.Timestamp(seed)
        h = self.ev[(self.ev.ts > s - pd.Timedelta(days=365)) & (self.ev.ts <= s)]
        return np.sort(h.driverId.unique())

    # моменты оракула: по одному дню гонки из каждой гранулярности плюс общий
    ORACLE_SEEDS = ["1996-03-10", "2000-03-12", "2004-03-07",   # день гонки, метка = полночь
                    "2010-03-14", "2015-03-15"]                 # день гонки, метка = время старта
