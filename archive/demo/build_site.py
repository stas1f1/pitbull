#!/usr/bin/env python3
"""Inline site_data.json into site_template.html → index.html (self-contained, offline)."""
import os, json
H = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(H + "/site_data.json"))
t = open(H + "/site_template.html").read()
f = d["facts"]
rep = {"{{review_lag_median}}": str(f["review_lag_median"]), "{{review_lag_p90}}": str(f["review_lag_p90"]),
       "{{review_lag_max}}": str(f["review_lag_max"]), "{{share_review_after}}": f"{f['share_review_after'][1]:.0f}",
       "{{n_orders}}": f"{f['n_orders']:,}", "{{n_sellers}}": f"{f['n_sellers']:,}", "{{n_products}}": f"{f['n_products']:,}"}
for k, v in rep.items(): t = t.replace(k, v)
t = t.replace("/*DATA*/{}/*END*/", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
open(H + "/index.html", "w").write(t)
print("ok", H + "/index.html", len(t))
