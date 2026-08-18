import numpy as np, pandas as pd
from scipy.stats import spearmanr

df = pd.read_csv("/home/claude/exp/results.csv")
rng = np.random.RandomState(0)
KS = [3, 5, 10, 15, 20, 30, 40, 50, 63]
NREP = 400

print("=" * 96)
print("A. СХОДИТСЯ ЛИ ВСЁ К «МАСШТАБИРОВАНИЕ + СЛУЧАЙНЫЙ ЛЕС»?")
print("=" * 96)
rows = []
for (ds, seed), g in df.groupby(["dataset", "seed"]):
    g = g.reset_index(drop=True)
    best_te = g.loc[g.test.idxmax()]
    best_rf = g[g.family.isin(["rf", "et"])].test.max()
    best_gbdt = g[g.family == "gbdt"].test.max()
    top5 = g.nlargest(5, "test")
    rows.append(dict(dataset=ds, seed=seed,
                     winner_family=best_te.family, best_test=best_te.test,
                     rf_best=best_rf, gbdt_best=best_gbdt,
                     gap_to_rf=best_te.test - best_rf,
                     spread=g.test.max() - g.test.min(),
                     n_fam_top5=top5.family.nunique()))
W = pd.DataFrame(rows)
agg = W.groupby("dataset").agg(
    best=("best_test", "mean"), rf=("rf_best", "mean"), gbdt=("gbdt_best", "mean"),
    gap_to_rf=("gap_to_rf", "mean"), fam_top5=("n_fam_top5", "mean")).round(4)
agg["winner"] = W.groupby("dataset").winner_family.agg(lambda s: s.mode()[0])
print(agg.to_string())
print()
print("Кто выигрывает по тесту (доля запусков):")
print((W.winner_family.value_counts(normalize=True) * 100).round(1).to_string())
print(f"\nСреднее число разных семейств в топ-5 по тесту: {W.n_fam_top5.mean():.2f} из 5")
print(f"Медианный отрыв лучшего пайплайна от лучшего леса: {W.gap_to_rf.median()*100:+.2f} п.п. AUC")
print(f"Доля запусков, где лес/ExtraTrees — уже оптимум: {(W.gap_to_rf <= 0.001).mean()*100:.0f}%")

print()
print("=" * 96)
print("B. ЧТО ПРОИСХОДИТ С РОСТОМ БЮДЖЕТА ПОИСКА (K = число оценённых пайплайнов)")
print("=" * 96)
out = []
for (ds, seed), g in df.groupby(["dataset", "seed"]):
    v, t = g.val.values, g.test.values
    P = len(v)
    for K in KS:
        if K > P:
            continue
        pick_test, oracle = [], []
        for _ in range(NREP):
            idx = rng.choice(P, K, replace=False)
            pick_test.append(t[idx[np.argmax(v[idx])]])
            oracle.append(t[idx].max())
        out.append(dict(dataset=ds, seed=seed, K=K,
                        test_of_val_winner=np.mean(pick_test),
                        oracle_test=np.mean(oracle),
                        regret=np.mean(oracle) - np.mean(pick_test)))
C = pd.DataFrame(out)
curve = C.groupby("K").agg(
    выбор_по_валидации=("test_of_val_winner", "mean"),
    оракул_по_тесту=("oracle_test", "mean"),
    потеря_на_отборе=("regret", "mean")).round(4)
curve["потеря_пп"] = (curve["потеря_на_отборе"] * 100).round(2)
curve["прирост_выбора_vs_K3"] = ((curve["выбор_по_валидации"] - curve["выбор_по_валидации"].iloc[0]) * 100).round(2)
curve["прирост_оракула_vs_K3"] = ((curve["оракул_по_тесту"] - curve["оракул_по_тесту"].iloc[0]) * 100).round(2)
print(curve.to_string())

print()
print("Потеря на отборе (п.п. AUC) по датасетам, K=5 -> K=63:")
piv = C.pivot_table(index="dataset", columns="K", values="regret").mul(100).round(2)
cols = [c for c in [5, 10, 20, 40, 63] if c in piv.columns]
piv = piv[cols]
piv["рост"] = (piv[cols[-1]] - piv[cols[0]]).round(2)
print(piv.to_string())
print(f"\nДатасетов, где потеря выросла при K 5->63: "
      f"{(piv['рост'] > 0).sum()} из {len(piv)}")

print()
print("=" * 96)
print("C. СВЯЗЬ ВАЛИДАЦИИ И ТЕСТА")
print("=" * 96)
sp = []
for (ds, seed), g in df.groupby(["dataset", "seed"]):
    r = spearmanr(g.val, g.test).statistic
    top10 = g.nlargest(10, "val")
    r_top = spearmanr(top10.val, top10.test).statistic
    sp.append(dict(dataset=ds, seed=seed, rho_all=r, rho_top10=r_top))
S = pd.DataFrame(sp).groupby("dataset").mean(numeric_only=True).round(3)
print(S.to_string())
print(f"\nМедиана по всему пулу:        rho = {S.rho_all.median():.3f}")
print(f"Медиана внутри топ-10 по вал.: rho = {S.rho_top10.median():.3f}")

print()
print("=" * 96)
print("D. ЦЕНА ОДНОЙ ОЦЕНКИ (секунды обучения)")
print("=" * 96)
ft = df.groupby("family").fit_s.agg(["median", "mean", "max"]).round(2).sort_values("median")
print(ft.to_string())
print(f"\nМедианное время полного перебора пула (63 пайплайна), сек: "
      f"{df.groupby(['dataset','seed']).fit_s.sum().median():.0f}")
print(f"Максимум по датасетам, сек: {df.groupby(['dataset','seed']).fit_s.sum().max():.0f}")

C.to_csv("/home/claude/exp/curve.csv", index=False)
W.to_csv("/home/claude/exp/winners.csv", index=False)
