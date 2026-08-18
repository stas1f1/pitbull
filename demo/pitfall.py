"""
PITFALL — проверка корректности признаков по времени дифференциальным исполнением.

Идея в одну строку: программа признаков корректна тогда и только тогда, когда её
выход не меняется, если из базы физически удалить всё, чего на момент предсказания
ещё не существовало.

    phi(D, t) == phi(D|t, t),  где D|t = { r in D : avail(r) <= t }

Мы ничего не разбираем в коде программы: ни AST, ни SQL, ни имена колонок.
Программа — чёрный ящик, вызываемый дважды. Расхождение — доказательство нарушения,
а не подозрение. Ложных срабатываний нет по построению; пропуски возможны (см. ниже).

Границы применимости:
  * колонка без метки доступности (изменяемый статус без истории) непроверяема —
    усечённая база для неё неотличима от полной;
  * недетерминированная программа даёт расхождение без утечки — требуется
    фиксированный seed;
  * утечка, не проявившаяся на конкретном моменте t, не будет замечена на нём.
"""
from dataclasses import dataclass, field
import os
import numpy as np, pandas as pd

LANG = os.environ.get("PITFALL_LANG", "en")   # "en" | "ru" — язык подписей

NA = -987654321.0

# ─────────────────────────────── база ───────────────────────────────

@dataclass
class TemporalDB:
    """Таблицы + отношение доступности.

    row_time[table]   — колонка, задающая момент появления СТРОКИ;
    value_time[table] — {колонка значения: колонка с её собственной меткой}, для
                        полей, которые дописываются к строке позже её появления.
    """
    tables: dict
    row_time: dict = field(default_factory=dict)
    value_time: dict = field(default_factory=dict)

    def channels(self):
        """Каналы, по которым будущее может попасть в выход: появление строки таблицы
        («row», таблица) и позднее значение колонки («val», таблица, колонка)."""
        ch = [("row", n) for n in self.tables if self.row_time.get(n) is not None]
        ch += [("val", n, c) for n, m in self.value_time.items() for c in m]
        return ch

    def truncate(self, t, only=None):
        """База, усечённая на момент t. only=None — по всем каналам; иначе только по
        перечисленным (для локализации утечки по каналам)."""
        out = {}
        for name, df in self.tables.items():
            d = df
            rt = self.row_time.get(name)
            if rt is not None and (only is None or ("row", name) in only):
                d = d[d[rt] <= t]
            d = d.copy()
            for col, tcol in self.value_time.get(name, {}).items():
                if only is not None and ("val", name, col) not in only:
                    continue
                mask = ~(d[tcol] <= t)
                d.loc[mask, col] = np.nan
                d.loc[mask, tcol] = pd.NaT
            out[name] = d
        return TemporalDB(out, self.row_time, self.value_time)

    def unchecked_columns(self):
        """Колонки, у которых нет метки доступности вообще: метод к ним неприменим."""
        bad = []
        for name, df in self.tables.items():
            rt = self.row_time.get(name)
            if rt is None:
                bad += [f"{name}.{c}" for c in df.columns]
        return bad

def masked_program(program, channels):
    """Патч LOCATOR-а: та же программа, но перед вызовом входная база усекается по
    найденным каналам. Ничего в коде программы не меняется."""
    def patched(db, t, entities):
        return program(db.truncate(t, only=frozenset(channels)), t, entities)
    patched.__name__ = getattr(program, "__name__", "program") + "_patched"
    return patched

# ────────────────────────── дифференциальная проверка ──────────────────────────

@dataclass
class Verdict:
    leak: bool
    columns: list
    cells: int
    note: str = ""

    @property
    def label(self):
        if LANG == "ru":
            return "УТЕЧКА" if self.leak else "ЧИСТО"
        return "VIOLATION" if self.leak else "CLEAN"

def _eq(a, b):
    return a.fillna(NA).round(9).equals(b.fillna(NA).round(9))

def differential_check(program, db, seed, entities):
    """program(db, seed, entities) -> DataFrame, индекс = entities."""
    full = program(db, seed, entities)
    trunc = program(db.truncate(seed), seed, entities)
    if full is None or trunc is None:
        return Verdict(full is not trunc, [], 0, "program returned None")
    if list(full.columns) != list(trunc.columns) or full.shape != trunc.shape:
        return Verdict(True, ["<output shape>"], 0, f"{full.shape} vs {trunc.shape}")
    cols = [c for c in full.columns if not _eq(full[c], trunc[c])]
    cells = int(sum((full[c].fillna(NA) != trunc[c].fillna(NA)).sum() for c in cols))
    return Verdict(bool(cols), cols, cells)

# ─────────────────────────── локализация: LOCATOR ───────────────────────────

@dataclass
class Blame:
    channel: tuple      # ("row", таблица) или ("val", таблица, колонка)
    columns: list       # выходные колонки, которые меняются, если усечь только этот канал
    cells: int

    @property
    def label(self):
        if LANG == "ru":
            return (f"{self.channel[1]}: строки после t" if self.channel[0] == "row"
                    else f"{self.channel[1]}.{self.channel[2]}: значение позже t")
        return (f"{self.channel[1]}: rows after t" if self.channel[0] == "row"
                else f"{self.channel[1]}.{self.channel[2]}: value known after t")

def locate(program, db, seed, entities, full=None):
    """Через какие каналы будущее попадает в выход. Усекаем базу по ОДНОМУ каналу за раз
    и смотрим, какие выходные колонки меняются. Столько же вызовов, сколько каналов;
    код программы по-прежнему не читается."""
    if full is None:
        full = program(db, seed, entities)
    out = []
    for ch in db.channels():
        part = program(db.truncate(seed, only=frozenset([ch])), seed, entities)
        if part is None or full is None or list(part.columns) != list(full.columns) or part.shape != full.shape:
            out.append(Blame(ch, ["<output shape>"], 0)); continue
        cols = [c for c in full.columns if not _eq(full[c], part[c])]
        if cols:
            cells = int(sum((full[c].fillna(NA) != part[c].fillna(NA)).sum() for c in cols))
            out.append(Blame(ch, cols, cells))
    return out

# ───────────────────── промышленная эвристика для сравнения ─────────────────────

from sklearn.metrics import roc_auc_score

DATAROBOT = (0.85, 0.975)
H2O = (0.80, 0.95, 0.999)

def univariate_probe(X, y):
    """«Максимальный AUC одного признака» — то, что делают DataRobot и H2O DAI."""
    best, who = 0.5, None
    for c in X.columns:
        v = pd.to_numeric(X[c], errors="coerce")
        v = v.fillna(v.median())
        if v.isna().all() or v.std() == 0:
            continue
        a = roc_auc_score(y, v); a = max(a, 1 - a)
        if a > best:
            best, who = a, c
    return best, who

def probe_says(a, thresholds=DATAROBOT):
    """Вердикт одномерной проверки при данных порогах: 'silent' | 'warning' | 'auto-drop'."""
    if a >= thresholds[-1]: return "auto-drop"
    if a >= thresholds[0]: return "warning"
    return "silent"

# ───────────────────────────── фиксированная модель ─────────────────────────────

def fixed_model_auc(Xtr, ytr, Xte, yte):
    """Одна и та же модель везде: смена бустера сама по себе даёт до 11.5 п.п."""
    from lightgbm import LGBMClassifier
    Xtr = Xtr.select_dtypes(include=[np.number])
    Xte = Xte.select_dtypes(include=[np.number]).reindex(columns=Xtr.columns)
    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                       random_state=0, n_jobs=2).fit(Xtr, ytr)
    return roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
