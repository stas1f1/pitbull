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
import numpy as np, pandas as pd

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

    def truncate(self, t):
        out = {}
        for name, df in self.tables.items():
            d = df
            rt = self.row_time.get(name)
            if rt is not None:
                d = d[d[rt] <= t]
            d = d.copy()
            for col, tcol in self.value_time.get(name, {}).items():
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

# ────────────────────────── дифференциальная проверка ──────────────────────────

@dataclass
class Verdict:
    leak: bool
    columns: list
    cells: int
    note: str = ""

    @property
    def label(self):
        return "УТЕЧКА" if self.leak else "ЧИСТО"

def _eq(a, b):
    return a.fillna(NA).round(9).equals(b.fillna(NA).round(9))

def differential_check(program, db, seed, entities):
    """program(db, seed, entities) -> DataFrame, индекс = entities."""
    full = program(db, seed, entities)
    trunc = program(db.truncate(seed), seed, entities)
    if full is None or trunc is None:
        return Verdict(full is not trunc, [], 0, "программа вернула None")
    if list(full.columns) != list(trunc.columns) or full.shape != trunc.shape:
        return Verdict(True, ["<форма выхода>"], 0, f"{full.shape} против {trunc.shape}")
    cols = [c for c in full.columns if not _eq(full[c], trunc[c])]
    cells = int(sum((full[c].fillna(NA) != trunc[c].fillna(NA)).sum() for c in cols))
    return Verdict(bool(cols), cols, cells)

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

def probe_says(a):
    if a >= DATAROBOT[1]: return "автовыброс"
    if a >= DATAROBOT[0]: return "предупреждение"
    return "молчит"

# ───────────────────────────── фиксированная модель ─────────────────────────────

def fixed_model_auc(Xtr, ytr, Xte, yte):
    """Одна и та же модель везде: смена бустера сама по себе даёт до 11.5 п.п."""
    from lightgbm import LGBMClassifier
    Xtr = Xtr.select_dtypes(include=[np.number])
    Xte = Xte.select_dtypes(include=[np.number]).reindex(columns=Xtr.columns)
    m = LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1,
                       random_state=0, n_jobs=2).fit(Xtr, ytr)
    return roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
