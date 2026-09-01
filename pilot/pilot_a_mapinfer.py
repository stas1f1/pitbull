"""
Пилот A (FSE RQ1): вывод карты доступности эвристиками, без LLM.

Вопрос: какую долю ручной карты доступности (per-table time_col) можно восстановить
из схемы и данных автоматически?

Ground truth:
  - 5 баз RelBench: rel/sqloracle.py TIME_COLS (взято из объявлений RelBench, не наше);
  - Olist (сырые CSV): orders -> order_purchase_timestamp, reviews -> review_creation_date,
    order_items и payments -> время РОДИТЕЛЬСКОГО заказа через FK order_id (в
    prestudy/oracle.py это derived-колонка ts), products/sellers/customers -> None.

Эвристики (пре-регистрированы до прогона):
  v0 (in-table): среди timestamp-колонок таблицы выбрать ту, что per-row самая ранняя
      (семантика "создание строки"); нет timestamp-колонок -> None.
  v1 (v0 + FK-наследование): если своя кандидатка отсутствует ИЛИ ведёт себя как
      "не время создания" (дальше медианного лага 0 от родителя), а таблица имеет
      join-ключ на таблицу с временем -> наследуем время родителя через FK.
  Порог решения из proposal: сквозное согласие вердиктов меряется отдельно (пилот B);
  здесь per-table точность. < 0.8 на v1 -> RQ1 в статье переформулируется в таксономию.
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXT = os.environ.get("PILOT_EXT", os.path.join(ROOT, "PITFALL_ext_data"))
OLIST = os.environ.get("PILOT_OLIST", os.path.join(ROOT, "prestudy", "p1_repro"))

# ---------------- ground truth ----------------
GT = {
    "f1": {"races": "date", "results": "date", "standings": "date",
           "constructor_results": "date", "constructor_standings": "date",
           "qualifying": "date", "circuits": None, "drivers": None, "constructors": None},
    "stack": {"posts": "CreationDate", "comments": "CreationDate", "votes": "CreationDate",
              "badges": "Date", "users": "CreationDate", "postHistory": "CreationDate",
              "postLinks": "CreationDate"},
    "hm": {"transactions": "t_dat", "customer": None, "article": None},
    "event": {"users": "joinedAt", "events": "start_time", "event_attendees": "start_time",
              "event_interest": "timestamp", "user_friends": None},
    "amazon": {"product": None, "customer": None, "review": "review_time"},
    # Olist: FK@orders означает "время родительского заказа через order_id"
    "olist": {"orders": "order_purchase_timestamp", "reviews": "review_creation_date",
              "order_items": "FK@orders", "payments": "FK@orders",
              "products": None, "sellers": None, "customers": None},
}
DBDIR = {"f1": "rel-f1", "stack": "rel-stack", "hm": "rel-hm",
         "event": "rel-event", "amazon": "rel-amazon"}

N_SAMPLE = 50_000  # строк на таблицу достаточно для порядковых статистик


def load_tables(ds):
    out = {}
    if ds == "olist":
        for f in os.listdir(OLIST):
            if f.startswith("olist_") and f.endswith(".csv"):
                name = f.replace("olist_", "").replace("_dataset.csv", "")
                name = {"order_reviews": "reviews", "order_payments": "payments"}.get(name, name)
                out[name] = pd.read_csv(os.path.join(OLIST, f), nrows=N_SAMPLE)
        return out
    d = os.path.join(EXT, DBDIR[ds], "db")
    if not os.path.isdir(d):
        d = os.path.join(EXT, DBDIR[ds])
    for f in os.listdir(d):
        if f.endswith(".parquet"):
            name = f[:-8]
            try:
                df = pd.read_parquet(os.path.join(d, f))
            except Exception as e:
                print(f"  !! {ds}/{name}: {e}")
                continue
            out[name] = df.head(N_SAMPLE)
    return out


def ts_cols(df):
    """Колонки, похожие на время: datetime dtype или объектные, парсящиеся в дату >50% строк."""
    res = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            if s.notna().mean() > 0.05:
                res.append(c)
            continue
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            sample = s.dropna().astype(str).head(500)
            if len(sample) == 0:
                continue
            looks = sample.str.match(r"^\d{4}-\d{2}-\d{2}").mean()
            if looks > 0.5:
                parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().mean() > 0.5:
                    res.append(c)
    return res


def to_dt(df, c):
    return pd.to_datetime(df[c], errors="coerce")


def v0_pick(df):
    """Per-row самая ранняя timestamp-колонка (семантика создания)."""
    cands = ts_cols(df)
    if not cands:
        return None, cands
    if len(cands) == 1:
        return cands[0], cands
    mat = pd.DataFrame({c: to_dt(df, c) for c in cands})
    # доля строк, где колонка равна построчному минимуму (среди непустых)
    row_min = mat.min(axis=1)
    share_min = {c: (mat[c] == row_min).mean() for c in cands}
    # штраф за пропуски: колонка, которой часто нет, не может быть временем строки
    score = {c: share_min[c] * mat[c].notna().mean() for c in cands}
    return max(score, key=score.get), cands


def find_fk(tables, name):
    """join-ключи: колонка с тем же именем, являющаяся ключом другой таблицы."""
    df = tables[name]
    links = []
    for other, odf in tables.items():
        if other == name:
            continue
        for c in df.columns:
            if c in odf.columns and odf[c].is_unique and not df[c].is_unique:
                links.append((c, other))
    return links


def run(ds):
    tables = load_tables(ds)
    gt = GT[ds]
    rows = []
    picks = {}
    for name, df in tables.items():
        pick, cands = v0_pick(df)
        picks[name] = (pick, cands)
    for name, df in tables.items():
        pick, cands = picks[name]
        v1 = pick
        note = ""
        if pick is None:
            fks = [(c, o) for c, o in find_fk(tables, name) if picks.get(o, (None,))[0]]
            if fks:
                v1 = f"FK@{fks[0][1]}"
                note = f"наследование через {fks[0][0]}"
        truth = gt.get(name, "___нет_в_GT___")
        rows.append({"db": ds, "table": name, "n_ts_cols": len(cands),
                     "v0": pick, "v1": v1, "truth": truth,
                     "v0_ok": pick == truth, "v1_ok": v1 == truth, "note": note})
    return rows


def main():
    all_rows = []
    for ds in ["olist", "f1", "stack", "hm", "event", "amazon"]:
        print(f"== {ds}")
        all_rows += run(ds)
    df = pd.DataFrame(all_rows)
    df.to_csv(os.path.join(HERE, "pilot_a_results.csv"), index=False)
    print(df.to_string(index=False))
    n = len(df)
    print(f"\nv0 accuracy: {df.v0_ok.sum()}/{n} = {df.v0_ok.mean():.2f}")
    print(f"v1 accuracy: {df.v1_ok.sum()}/{n} = {df.v1_ok.mean():.2f}")
    for _, r in df[~df.v1_ok].iterrows():
        print(f"  MISS {r.db}/{r.table}: v1={r.v1} truth={r.truth}")


if __name__ == "__main__":
    main()
