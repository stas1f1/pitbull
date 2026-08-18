import json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.linewidth": .7,
                     "xtick.major.width": .7, "ytick.major.width": .7, "axes.grid": True,
                     "grid.color": "#e3e8f4", "grid.linewidth": .6, "axes.axisbelow": True})
NAVY, RED, AMB, GRN, GREY = "#1E2761", "#A62B22", "#B57314", "#1F7A55", "#7d87a3"

# ── Рис. 2: I(delta) ─────────────────────────────────────────────────────────
R = pd.read_csv("/home/claude/rel/delta_auc.csv"); R["d"] = R.режим.str.replace("δ=", "").astype(int)
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5), sharey=True)
for ax, (task, name) in zip(axes, [("A", "A. seller activity"), ("B", "B. seller review quality")]):
    S = R[R.задача == task]
    for c, ts in zip([NAVY, AMB, RED], sorted(S.тест.unique())):
        g = S[S.тест == ts].sort_values("d")
        ax.plot(g.d, g.завышение, "-o", ms=3, lw=1.3, color=c, label=ts)
    ax.set_title(name, fontsize=8.5, pad=4)
    ax.set_xlabel("cutoff shift δ, days"); ax.set_xlim(-2, 92)
axes[0].set_ylabel("AUC inflation, pp"); axes[0].legend(frameon=False, fontsize=7, title="seed time",
                                                        title_fontsize=7, loc="upper left")
fig.tight_layout(); fig.savefig("/home/claude/fig/fig2_delta.pdf"); fig.savefig("/home/claude/fig/fig2_delta.png", dpi=220)

# ── Рис. 3: дозозависимость ──────────────────────────────────────────────────
DOSE = {"deepseek-v4-flash":            [(53.3, 36.1, 69.8), (48.0, 30.0, 66.5), (19.2, 8.5, 37.9)],
        "bytedance-seed/seed-2.0-code": [(35.3, 17.3, 58.7), (22.2, 6.3, 54.7), (6.7, 1.2, 29.8)],
        "both pooled":                  [(46.8, 33.3, 60.8), (41.2, 26.4, 57.8), (14.6, 6.9, 28.4)]}
fig, ax = plt.subplots(figsize=(3.45, 2.5))
x = np.arange(3); w = .26
for k, (name, vals) in enumerate(DOSE.items()):
    v = np.array(vals); col = [AMB, GRN, NAVY][k]; hat = ["//", "\\\\", None][k]
    ax.bar(x + (k - 1) * w, v[:, 0], w, color=col, alpha=1 if k == 2 else .40,
           hatch=hat, edgecolor=col, linewidth=.6, label=name, zorder=3)
    ax.errorbar(x + (k - 1) * w, v[:, 0], yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]],
                fmt="none", ecolor="#141B3D", elinewidth=.8, capsize=2, zorder=4)
ax.set_xticks(x); ax.set_xticklabels(["G0\nneutral", "G1\nmention", "G2\nper-aggregate"], fontsize=7.5)
ax.set_ylabel("programs violating PIT, %"); ax.set_ylim(0, 75)
ax.legend(frameon=False, fontsize=6.8, loc="upper right")
ax.set_title("Wilson 95% CI; n=30 per cell", fontsize=7.5, color=GREY, pad=4)
fig.tight_layout(); fig.savefig("/home/claude/fig/fig3_dose.pdf"); fig.savefig("/home/claude/fig/fig3_dose.png", dpi=220)

# ── Рис. 4: слепота проверки ─────────────────────────────────────────────────
P = pd.read_csv("/home/claude/rel/delta_probe.csv"); P["d"] = P.режим.str.replace("δ=", "").astype(int)
M = R.merge(P, on=["задача", "тест", "режим"])
C = pd.read_csv("/home/claude/rel/fix_c.csv")
ft = pd.read_csv("/home/claude/demo/ft_scene.csv")
fig, ax = plt.subplots(figsize=(3.45, 2.7))
ax.axvspan(0, .85, color="#fdecea", zorder=0)
ax.axvline(.85, color=RED, lw=.9, ls="--"); ax.axvline(.975, color=RED, lw=.7, ls=":")
ax.scatter(M.макс_AUC_признака, M.завышение, s=14, color=GREY, alpha=.75, lw=0,
           label="cutoff shift, tasks A/B", zorder=3)
c2 = C[C.режим == "утечка только через соединение"]
ax.scatter(c2.макс_AUC_признака, c2.завышение, s=42, marker="D", color=RED, lw=0,
           label="leak through join only", zorder=5)
ftl = ft[ft.режим == "туториал"]
ax.scatter(ftl.макс_AUC_признака, ftl.завышение, s=52, marker="*", color=NAVY, lw=0,
           label="featuretools defaults", zorder=5)
ax.scatter([.623, .687, .657], [3.09, 5.26, 3.78], s=34, marker="^", color=AMB, lw=0,
           label="our own expert code", zorder=5)
ax.text(.857, .2, "DataRobot 0.85", fontsize=6.2, color=RED, rotation=90, va="bottom")
ax.text(.982, .2, "H2O 0.975", fontsize=6.2, color=RED, rotation=90, va="bottom")
ax.text(.565, 27.6, "probe SILENT\n→ leak missed", fontsize=7, color=RED, va="top", weight="bold")
ax.set_xlabel("industrial probe: max single-feature AUC")
ax.set_ylabel("true AUC inflation, pp")
ax.set_xlim(.55, 1.02); ax.set_ylim(-1.5, 29)
ax.legend(frameon=False, fontsize=6.4, loc="upper left", bbox_to_anchor=(0.015, .86))
fig.tight_layout(); fig.savefig("/home/claude/fig/fig4_blind.pdf"); fig.savefig("/home/claude/fig/fig4_blind.png", dpi=220)
print("figures written")
