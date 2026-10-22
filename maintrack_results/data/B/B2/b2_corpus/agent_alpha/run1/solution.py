#!/usr/bin/env python3
"""Memory-conscious CPU baseline for binary RelBench task tables."""

import os

# Set these before importing numerical libraries so the process remains single-threaded.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


MAX_TRAIN_ROWS = 300_000
MAX_COLUMNS = 96


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", required=True, choices=("val", "test"))
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def binary_target(series):
    """Convert common binary label representations to uint8."""
    non_null = series.dropna()
    if non_null.empty:
        raise ValueError("Training target contains no labels")
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype("uint8").to_numpy()
    numeric = pd.to_numeric(series, errors="coerce")
    unique_numeric = np.sort(numeric.dropna().unique())
    if 1 <= len(unique_numeric) <= 2:
        positive = unique_numeric[-1]
        return (numeric.fillna(unique_numeric[0]).to_numpy() == positive).astype("uint8")
    text = series.astype("string").str.strip().str.lower()
    positive_words = {"1", "true", "yes", "y", "positive", "pos"}
    negative_words = {"0", "false", "no", "n", "negative", "neg"}
    values = set(text.dropna().unique())
    if values and values <= positive_words | negative_words:
        return text.isin(positive_words).to_numpy(dtype="uint8")
    ordered = sorted(values)
    if len(ordered) != 2:
        raise ValueError("Training target must be binary")
    return (text == ordered[-1]).to_numpy(dtype="uint8")


def stable_sample(frame, time_col):
    """Keep a deterministic, recent-biased sample if training is unusually large."""
    if len(frame) <= MAX_TRAIN_ROWS:
        return frame.reset_index(drop=True)
    if time_col in frame:
        parsed = pd.to_datetime(frame[time_col], errors="coerce", utc=True)
        order = np.argsort(parsed.astype("int64").to_numpy(), kind="stable")
        return frame.iloc[order[-MAX_TRAIN_ROWS:]].reset_index(drop=True)
    step = len(frame) / MAX_TRAIN_ROWS
    positions = (np.arange(MAX_TRAIN_ROWS) * step).astype(np.int64)
    return frame.iloc[positions].reset_index(drop=True)


class FeatureBuilder:
    def __init__(self, time_col, entity_col):
        self.time_col = time_col
        self.entity_col = entity_col
        self.specs = []
        self.global_mean = 0.5

    @staticmethod
    def _keys(series):
        return series.astype("string").fillna("<NA>")

    def fit(self, frame, labels, excluded):
        self.global_mean = float(np.mean(labels))
        candidates = [c for c in frame.columns if c not in excluded]
        # Required semantic columns are retained even when a wide table is truncated.
        priority = [c for c in (self.time_col, self.entity_col) if c in candidates]
        rest = [c for c in candidates if c not in priority]
        columns = (priority + rest)[:MAX_COLUMNS]

        for column in columns:
            series = frame[column]
            if column == self.time_col:
                self.specs.append((column, "datetime", None))
                continue
            numeric = pd.to_numeric(series, errors="coerce")
            numeric_fraction = float(numeric.notna().mean())
            unique_count = int(series.nunique(dropna=True))
            looks_like_id = column == self.entity_col or column.lower().endswith("id")
            if numeric_fraction >= 0.98 and not looks_like_id:
                finite = numeric.replace([np.inf, -np.inf], np.nan)
                median = float(finite.median()) if finite.notna().any() else 0.0
                q_low = float(finite.quantile(0.005)) if finite.notna().any() else median
                q_high = float(finite.quantile(0.995)) if finite.notna().any() else median
                if not math.isfinite(q_low):
                    q_low = median
                if not math.isfinite(q_high):
                    q_high = median
                if q_high < q_low:
                    q_low, q_high = q_high, q_low
                self.specs.append((column, "numeric", (median, q_low, q_high)))
            else:
                keys = self._keys(series)
                stats = pd.DataFrame({"key": keys, "y": labels}).groupby("key", sort=False)["y"].agg(["sum", "count"])
                # Stronger shrinkage for extremely high-cardinality identifiers.
                smoothing = 20.0 if unique_count < 50_000 else 50.0
                target_map = ((stats["sum"] + smoothing * self.global_mean) / (stats["count"] + smoothing)).to_dict()
                frequency_map = (stats["count"] / len(frame)).to_dict()
                self.specs.append((column, "categorical", (target_map, frequency_map)))
        return self

    def transform(self, frame):
        features = []
        for column, kind, state in self.specs:
            series = frame[column] if column in frame else pd.Series(pd.NA, index=frame.index)
            if kind == "datetime":
                dt = pd.to_datetime(series, errors="coerce", utc=True)
                raw = dt.astype("int64").to_numpy(dtype=np.float64)
                raw[dt.isna().to_numpy()] = np.nan
                days = raw / 86_400_000_000_000.0
                features.extend(
                    [
                        days,
                        dt.dt.year.fillna(0).to_numpy(dtype=np.float64),
                        dt.dt.month.fillna(0).to_numpy(dtype=np.float64),
                        dt.dt.dayofweek.fillna(0).to_numpy(dtype=np.float64),
                    ]
                )
            elif kind == "numeric":
                median, q_low, q_high = state
                values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
                values = values.fillna(median).clip(q_low, q_high).to_numpy(dtype=np.float64)
                scale = max(q_high - q_low, 1.0)
                features.append((values - median) / scale)
            else:
                target_map, frequency_map = state
                keys = self._keys(series)
                features.append(keys.map(target_map).fillna(self.global_mean).to_numpy(dtype=np.float64))
                features.append(keys.map(frequency_map).fillna(0.0).to_numpy(dtype=np.float64))
        if not features:
            return np.zeros((len(frame), 1), dtype=np.float32)
        matrix = np.column_stack(features).astype(np.float32, copy=False)
        return np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    train = pd.read_parquet(task_dir / "train.parquet")
    predict_frame = pd.read_parquet(task_dir / f"{args.split}.parquet")
    if args.target_col not in train:
        raise KeyError(f"Missing target column in train.parquet: {args.target_col}")

    train = stable_sample(train, args.time_col)
    labels = binary_target(train[args.target_col])
    builder = FeatureBuilder(args.time_col, args.entity_col).fit(
        train,
        labels,
        excluded={args.target_col},
    )
    x_train = builder.transform(train)
    x_predict = builder.transform(predict_frame)

    prevalence = float(np.mean(labels))
    if np.unique(labels).size < 2:
        predictions = np.full(len(predict_frame), prevalence, dtype=np.float64)
    else:
        positive = max(int(labels.sum()), 1)
        negative = max(int(len(labels) - positive), 1)
        weights = np.where(labels == 1, len(labels) / (2.0 * positive), len(labels) / (2.0 * negative))
        model = HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=180,
            max_leaf_nodes=31,
            max_depth=8,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=20261018,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=15,
        )
        model.fit(x_train, labels, sample_weight=weights)
        predictions = model.predict_proba(x_predict)[:, 1]

    predictions = np.nan_to_num(predictions, nan=prevalence, posinf=1.0, neginf=0.0)
    predictions = np.clip(predictions, 0.0, 1.0)
    output = pd.DataFrame(
        {
            "row_id": np.arange(len(predict_frame), dtype=np.int64),
            "prediction": predictions.astype(np.float64),
        }
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()
