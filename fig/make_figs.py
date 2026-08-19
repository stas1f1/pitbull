import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _ROOT = _os.path.dirname(_HERE)
_DATA = _os.environ.get("PITFALL_DATA", _os.path.join(_ROOT, "PITFALL_olist_data")) + "/"
import json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.linewidth": .7,
                     "xtick.major.width": .7, "ytick.major.width": .7, "axes.grid": True,
                     "grid.color": "#e3e8f4", "grid.linewidth": .6, "axes.axisbelow": True})
NAVY, RED, AMB, GRN, GREY = "#1E2761", "#A62B22", "#B57314", "#1F7A55", "#7d87a3"

# ── Рис. 2: I(delta) ─────────────────────────────────────────────────────────
R = pd.read_csv(_ROOT + "/rel/delta_auc.csv"); R["d"] = R.режим.str.replace("δ=", "").astype(int)
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
fig.tight_layout(); fig.savefig(_ROOT + "/fig/fig2_delta.pdf"); fig.savefig(_ROOT + "/fig/fig2_delta.png", dpi=220)

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
ax.set_title("Wilson 95% CI over programs that ran (n = 9–30 per cell)", fontsize=7.2, color=GREY, pad=4)
fig.tight_layout(); fig.savefig(_ROOT + "/fig/fig3_dose.pdf"); fig.savefig(_ROOT + "/fig/fig3_dose.png", dpi=220)

# ── Рис. 4: проверка ошибается в обе стороны ─────────────────────────────────
# Слева от 0.80 промышленная проверка молчит на настоящих нарушениях; справа от
# 0.80 она предупреждает на КОРРЕКТНОМ коде. Одной вертикали, разделяющей эти два
# множества, не существует — в этом и довод.
P = pd.read_csv(_ROOT + "/rel/delta_probe.csv"); P["d"] = P.режим.str.replace("δ=", "").astype(int)
M = R.merge(P, on=["задача", "тест", "режим"])
C = pd.read_csv(_ROOT + "/rel/fix_c.csv")
ft = pd.read_csv(_ROOT + "/demo/ft_scene.csv")
AB = pd.read_csv(_ROOT + "/rel/fix_ab_probe.csv")
F1 = pd.read_csv(_ROOT + "/rel/out/f1_auc.csv")
SQ = pd.read_csv(_ROOT + "/rel/out/sql_cost.csv")

# корректный код: завышение ровно 0 по построению
ok_x = (list(AB[AB.режим == "корректно (PIT)"].макс_AUC_признака)
        + list(C[C.режим == "корректно (PIT, обе группы)"].макс_AUC_признака)
        + list(F1[F1["mode"] == "pit"].probe)
        + list(SQ[SQ.regime == "corrected"].probe))
ok_y = [0.0] * len(ok_x)

# Широкий формат на обе колонки: по горизонтали умещаются четыре порога с
# подписями, легенда уходит вправо и не наезжает на точки.
# Одна колонка. Легенда вынесена полосой над осями в два столбца: внутри поля
# она накрывала самую плотную группу точек слева.
fig, ax = plt.subplots(figsize=(3.5, 2.95))
ax.axvspan(.55, .80, color="#fbdcd8", zorder=0)         # молчит при любом развёрнутом пороге
ax.axvspan(.80, .925, color="#fdecea", zorder=0)        # DataRobot молчит, H2O уведомляет
ax.axvline(.925, color=RED, lw=.9, ls="--"); ax.axvline(.9875, color=RED, lw=.7, ls=":")
ax.axvline(.80, color=GREY, lw=.8, ls="--"); ax.axvline(.95, color=GREY, lw=.7, ls=":")
ax.axhline(0, color="#9aa4c0", lw=.6, zorder=1)

ax.scatter(M.макс_AUC_признака, M.завышение, s=11, color=GREY, alpha=.7, lw=0,
           label="cutoff shift, Olist", zorder=3)
viol = F1[F1["mode"].isin(["naive", "join_only", "both60"])]
ax.scatter(viol.probe, viol.inflation_pp, s=11, color="#5c6a99", alpha=.85, lw=0,
           label="violations, rel-f1", zorder=3)
c2 = C[C.режим == "утечка только через соединение"]
ax.scatter(c2.макс_AUC_признака, c2.завышение, s=34, marker="D", color=RED, lw=0,
           label="join-path leak", zorder=5)
ftl = ft[ft.режим == "туториал"]
ax.scatter(ftl.макс_AUC_признака, ftl.завышение, s=52, marker="*", color=NAVY, lw=0,
           label="featuretools", zorder=5)
ax.scatter([.623, .687, .657], [3.09, 5.26, 3.78], s=28, marker="^", color=AMB, lw=0,
           label="our reference code", zorder=5)
ax.scatter(ok_x, ok_y, s=30, marker="o", facecolors="none", edgecolors=GRN, linewidths=1.0,
           label="correct code", zorder=6)

for x_, txt, col in [(.792, "H2O .80", GREY), (.917, "DataRobot .925", RED),
                     (.942, "H2O .95", GREY), (.9795, "DataRobot .99", RED)]:
    ax.text(x_, 26.5, txt, fontsize=6.0, color=col, rotation=90, va="top", ha="right")
ax.text(.565, 27.0, "probe SILENT here", fontsize=7.4, color=RED, va="top", weight="bold")
ax.annotate("correct code, inflation 0:\nH2O warns right of .80", xy=(.848, -.5),
            xytext=(.86, -6.2), fontsize=6.6, color=GRN, weight="bold", ha="center",
            va="center", arrowprops=dict(arrowstyle="->", color=GRN, lw=.9))
ax.set_xlabel("univariate probe: best single-feature AUC")
ax.set_ylabel("true AUC inflation, pp")
ax.set_xlim(.55, 1.02); ax.set_ylim(-8.5, 28)
ax.legend(frameon=False, fontsize=6.1, ncol=3, loc="lower left", borderaxespad=0,
          bbox_to_anchor=(-.02, 1.0, 1.04, .14), mode="expand",
          handletextpad=.25, columnspacing=.8, borderpad=0)
fig.tight_layout(); fig.savefig(_ROOT + "/fig/fig4_blind.pdf"); fig.savefig(_ROOT + "/fig/fig4_blind.png", dpi=220)
# Статья собирается из paper/fig, а не из fig в корне. Держим копии
# синхронными: рассинхрон уже один раз стоил нам вёрстки со старым рисунком.
import shutil, glob as _glob
_PF = _os.path.join(_ROOT, "paper", "fig")
if _os.path.isdir(_PF):
    for _f in _glob.glob(_os.path.join(_ROOT, "fig", "*.pdf")):
        shutil.copy2(_f, _os.path.join(_PF, _os.path.basename(_f)))
    print("figures written and synced to paper/fig")
else:
    print("figures written")
