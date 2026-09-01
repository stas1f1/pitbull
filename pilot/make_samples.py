"""Потоковая нарезка сэмплов RelBench-таблиц для пилота A: первые N строк каждой
таблицы через pyarrow batches, без загрузки файла в память (rel-amazon/review 6.7G)."""
import os, sys
import pyarrow.parquet as pq
import pyarrow as pa

EXT = "/home/stas/Documents/GitHub/pitfall/PITFALL_ext_data"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
N = 50_000

for db in ["rel-f1", "rel-stack", "rel-hm", "rel-event", "rel-amazon"]:
    d = os.path.join(EXT, db, "db")
    od = os.path.join(OUT, db)
    os.makedirs(od, exist_ok=True)
    for f in sorted(os.listdir(d)):
        if not f.endswith(".parquet"):
            continue
        dst = os.path.join(od, f)
        if os.path.exists(dst):
            continue
        pf = pq.ParquetFile(os.path.join(d, f))
        batches, got = [], 0
        for b in pf.iter_batches(batch_size=10_000):
            batches.append(b)
            got += b.num_rows
            if got >= N:
                break
        t = pa.Table.from_batches(batches)[:N] if batches else pf.read()
        pq.write_table(pa.table(t), dst)
        print(db, f, t.num_rows, "rows", flush=True)
print("done")
