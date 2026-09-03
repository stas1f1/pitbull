import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({"font.size": 7.2, "font.family": "DejaVu Sans", "axes.linewidth": .6,
                     "xtick.major.width": .6, "ytick.major.width": .6, "axes.grid": True,
                     "grid.color": "#e3e8f4", "grid.linewidth": .5, "axes.axisbelow": True,
                     "xtick.labelsize": 6.8, "ytick.labelsize": 6.8})
NAVY, RED, AMB, GRN, GREY = "#1E2761", "#A62B22", "#B57314", "#1F7A55", "#7d87a3"
W = 3.4   # одна колонка IEEE

# ── Рис. 1: архитектура ───────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(W, 2.35)); ax.set_axis_off()
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.grid(False)
def box(x, y, w, h, t, fc, ec, fs=6.8, tc="white", bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12,rounding_size=.2",
                                fc=fc, ec=ec, lw=.8, zorder=2))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=tc,
            zorder=3, weight="bold" if bold else "normal")
def arrow(x1, y1, x2, y2, lbl=None, dx=.12):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=7,
                                 lw=.8, color="#3b4460", zorder=1))
    if lbl: ax.text(x1 + dx, (y1 + y2) / 2, lbl, fontsize=5.9, color="#3b4460", ha="left", va="center")
box(1.2, 8.7, 7.6, 1.0, "schema  +  (entity, seed time, label)", "#eef2fb", "#c9d3ea", tc=NAVY)
arrow(5, 8.7, 5, 7.9)
box(1.2, 6.9, 7.6, 1.0, "SCOUT   availability map\n(hand-written or LLM-proposed, checked by GUARD)", "#eef2fb", NAVY, tc=NAVY, bold=True, fs=6.0)
arrow(5, 6.9, 5, 6.1)
box(1.2, 5.1, 7.6, 1.0, "BUILDER   featuretools / agent / hand-written\n(black box to us)", "#ffffff", GREY, tc="#3b4460")
arrow(5, 5.1, 5, 4.3, "  program φ")
box(1.2, 2.9, 7.6, 1.4, "GUARD    φ(D,t)  vs  φ(D|t,t)\ndifferential execution", "#fdecea", RED, tc=RED, bold=True)
arrow(2.6, 2.9, 2.6, 2.1, "violation")
arrow(7.4, 2.9, 7.4, 2.1, "clean")
box(.2, 1.0, 4.0, 1.1, "LOCATOR  truncate one channel\nat a time → blame → patch", "#fff6e8", AMB, tc=AMB, fs=6.0)
box(5.8, 1.0, 4.0, 1.1, "FLATTEN →\ntabular AutoML", "#eaf5f0", GRN, tc=GRN, fs=6.4)
ax.add_patch(FancyArrowPatch((.6, 2.1), (.35, 3.6), connectionstyle="arc3,rad=.45",
                             arrowstyle="-|>", mutation_scale=6, lw=.7, color=AMB, zorder=1))
fig.tight_layout(pad=.15); fig.savefig(_ROOT + "/fig/fig1_arch.pdf"); fig.savefig(_ROOT + "/fig/fig1_arch.png", dpi=240)

# ── Рис. 3 компактно: I(delta), среднее по моментам с диапазоном ───────────────
R = pd.read_csv(_ROOT + "/rel/delta_auc.csv"); R["d"] = R.режим.str.replace("δ=", "").astype(int)
fig, ax = plt.subplots(figsize=(W, 2.05))
for task, name, col in [("A", "A. seller activity", NAVY), ("B", "B. review quality", RED)]:
    g = R[R.задача == task].groupby("d").завышение
    m, lo, hi = g.mean(), g.min(), g.max()
    ax.fill_between(m.index, lo, hi, color=col, alpha=.15, lw=0)
    ax.plot(m.index, m.values, "-o", ms=2.8, lw=1.3, color=col, label=name)
ax.axhline(0, color="#c9d3ea", lw=.7)
ax.set_xlabel("cutoff shift δ, days"); ax.set_ylabel("AUC inflation, pp")
ax.set_xlim(-2, 92); ax.legend(frameon=False, fontsize=6.5, loc="upper left")
ax.set_title("mean over three seed times, band = min–max", fontsize=6.4, color=GREY, pad=3)
fig.tight_layout(pad=.2); fig.savefig(_ROOT + "/fig/fig3_delta_c.pdf"); fig.savefig(_ROOT + "/fig/fig3_delta_c.png", dpi=240)
print("ok")
