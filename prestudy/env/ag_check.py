import numpy as np, pandas as pd
from sklearn.datasets import make_classification
from autogluon.tabular import TabularPredictor
X, y = make_classification(n_samples=2000, n_features=12, n_informative=6, random_state=0)
df = pd.DataFrame(X, columns=[f"f{i}" for i in range(12)]); df["label"] = y
p = TabularPredictor(label="label", verbosity=1, path="env/ag_tmp").fit(df, time_limit=60, presets="medium")
lb = p.leaderboard(silent=True) if "silent" in p.leaderboard.__code__.co_varnames else p.leaderboard()
print("\n=== N_MODELS =", len(lb), "===")
print(lb[["model"]].to_string())
fams = set()
for m in lb["model"]:
    for k in ["LightGBM","XGBoost","CatBoost","NeuralNet","RandomForest","ExtraTrees","KNeighbors","Linear"]:
        if k.lower() in m.lower(): fams.add(k)
print("FAMILIES:", sorted(fams))
print("LGB/XGB/CAT visible:", {"LightGBM","XGBoost","CatBoost"} <= fams)
