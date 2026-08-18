"""Try to beat the checker.  Edit this file, then run:

    python3 demo.py --program try_me.py            # task: seller review quality
    python3 demo.py --program try_me.py --task product

Signature: features(db, seed_time, entities) -> DataFrame indexed by entities.
db.tables["flat"] is one row per order line item with columns
  seller_id, product_id, order_id, ts (order time), price, freight_value,
  review_score / review_ts, late, delay_days / deliv_ts, pay_value, pay_inst.
The checker never reads this code: it runs it twice and compares the outputs.
"""
import numpy as np, pandas as pd

def features(db, seed, entities):
    ev = db.tables["flat"]
    h = ev[ev.ts <= seed]                                   # history up to the seed time ...
    g = h[h.seller_id.isin(entities)].groupby("seller_id")
    f = pd.DataFrame({
        "n_orders": g.order_id.nunique(),
        "price_mean": g.price.mean(),
        "review_mean": g.review_score.mean(),               # ... but the review is written later!
        "days_since_last": (seed - g.ts.max()).dt.total_seconds() / 86400,
    })
    return f.reindex(entities)
