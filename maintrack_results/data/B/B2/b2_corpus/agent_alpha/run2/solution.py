#!/usr/bin/env python3
"""Sparse, single-threaded baseline for binary RelBench task tables."""

import os

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_variable] = "1"

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import SGDClassifier


MAX_TRAIN_ROWS = 250_000
MAX_FEATURE_COLUMNS = 48
HASH_DIMENSION = 1 << 18


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def labels_to_binary(series):
    if series.dropna().empty:
        raise ValueError("train.parquet has no non-null target values")
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(np.uint8).to_numpy()
    numeric = pd.to_numeric(series, errors="coerce")
    numeric_values = np.sort(numeric.dropna().unique())
    if 1 <= len(numeric_values) <= 2:
        return (numeric.fillna(numeric_values[0]).to_numpy() == numeric_values[-1]).astype(np.uint8)
    text = series.astype("string").str.strip().str.lower()
    positives = {"1", "true", "yes", "y", "positive", "pos"}
    negatives = {"0", "false", "no", "n", "negative", "neg"}
    observed = set(text.dropna().unique())
    if observed and observed <= positives | negatives:
        return text.isin(positives).to_numpy(dtype=np.uint8)
    ordered = sorted(observed)
    if len(ordered) != 2:
        raise ValueError("Target must contain exactly two classes")
    return (text == ordered[-1]).to_numpy(dtype=np.uint8)


def bounded_training_frame(frame, time_col):
    if len(frame) <= MAX_TRAIN_ROWS:
        return frame.reset_index(drop=True)
    if time_col in frame:
        timestamps = pd.to_datetime(frame[time_col], errors="coerce", utc=True)
        order = np.argsort(timestamps.astype("int64").to_numpy(), kind="stable")
        return frame.iloc[order[-MAX_TRAIN_ROWS:]].reset_index(drop=True)
    positions = np.linspace(0, len(frame) - 1, MAX_TRAIN_ROWS, dtype=np.int64)
    return frame.iloc[positions].reset_index(drop=True)


class SparseFeatures:
    def __init__(self, time_col, entity_col):
        self.time_col = time_col
        self.entity_col = entity_col
        self.columns = []
        self.kinds = {}
        self.numeric_stats = {}
        self.entity_sum = {}
        self.entity_count = {}
        self.prior = 0.5
        self.smoothing = 20.0

    @staticmethod
    def string_values(series):
        return series.astype("string").fillna("<NA>").astype(str).to_numpy()

    def fit(self, frame, labels, target_col):
        candidates = [column for column in frame.columns if column != target_col]
        priority = [column for column in (self.time_col, self.entity_col) if column in candidates]
        self.columns = (priority + [column for column in candidates if column not in priority])[:MAX_FEATURE_COLUMNS]
        self.prior = float(labels.mean())

        for column in self.columns:
            if column == self.time_col:
                self.kinds[column] = "time"
                continue
            values = frame[column]
            numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
            is_identifier = column == self.entity_col or column.lower().endswith("id")
            if numeric.notna().mean() >= 0.98 and not is_identifier:
                center = float(numeric.median()) if numeric.notna().any() else 0.0
                low = float(numeric.quantile(0.01)) if numeric.notna().any() else center
                high = float(numeric.quantile(0.99)) if numeric.notna().any() else center
                scale = max(high - low, 1.0)
                self.kinds[column] = "numeric"
                self.numeric_stats[column] = (center, scale)
            else:
                self.kinds[column] = "categorical"

        if self.entity_col in frame:
            keys = self.string_values(frame[self.entity_col])
            stats = pd.DataFrame({"entity": keys, "label": labels}).groupby("entity", sort=False)["label"].agg(["sum", "count"])
            self.entity_sum = stats["sum"].to_dict()
            self.entity_count = stats["count"].to_dict()
        return self

    def entity_rates(self, frame, labels=None):
        if self.entity_col not in frame:
            return np.full(len(frame), self.prior, dtype=np.float32)
        keys = self.string_values(frame[self.entity_col])
        sums = np.fromiter((self.entity_sum.get(key, 0.0) for key in keys), dtype=np.float64, count=len(keys))
        counts = np.fromiter((self.entity_count.get(key, 0.0) for key in keys), dtype=np.float64, count=len(keys))
        if labels is not None:
            # Leave-one-out encoding prevents each training label from encoding itself.
            sums = sums - labels
            counts = np.maximum(counts - 1.0, 0.0)
        return ((sums + self.smoothing * self.prior) / (counts + self.smoothing)).astype(np.float32)

    def records(self, frame, entity_rates):
        prepared = {}
        for column in self.columns:
            kind = self.kinds[column]
            series = frame[column] if column in frame else pd.Series(pd.NA, index=frame.index)
            if kind == "time":
                dt = pd.to_datetime(series, errors="coerce", utc=True)
                prepared[column] = (
                    dt,
                    dt.astype("int64").to_numpy(dtype=np.float64) / 86_400_000_000_000.0,
                )
            elif kind == "numeric":
                center, scale = self.numeric_stats[column]
                values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
                prepared[column] = ((values.fillna(center).to_numpy(dtype=np.float64) - center) / scale).clip(-10.0, 10.0)
            else:
                prepared[column] = self.string_values(series)

        for row in range(len(frame)):
            record = {
                "bias": 1.0,
                "entity_history": float(entity_rates[row] - self.prior),
            }
            for column in self.columns:
                kind = self.kinds[column]
                if kind == "time":
                    dt, days = prepared[column]
                    stamp = dt.iloc[row]
                    if not pd.isna(stamp):
                        record[f"num:{column}:days"] = float(days[row] / 20_000.0)
                        record[f"cat:{column}:year={stamp.year}"] = 1.0
                        record[f"cat:{column}:month={stamp.month}"] = 1.0
                        record[f"cat:{column}:weekday={stamp.dayofweek}"] = 1.0
                elif kind == "numeric":
                    record[f"num:{column}"] = float(prepared[column][row])
                else:
                    record[f"cat:{column}={prepared[column][row]}"] = 1.0
            yield record

    def transform(self, frame, hasher, labels=None):
        rates = self.entity_rates(frame, labels=labels)
        return hasher.transform(self.records(frame, rates))


def main():
    args = arguments()
    task_dir = Path(args.task_dir)
    train = pd.read_parquet(task_dir / "train.parquet")
    requested = pd.read_parquet(task_dir / f"{args.split}.parquet")
    if args.target_col not in train.columns:
        raise KeyError(f"Missing target column: {args.target_col}")

    train = bounded_training_frame(train, args.time_col)
    labels = labels_to_binary(train[args.target_col])
    prevalence = float(labels.mean())

    if np.unique(labels).size < 2:
        probabilities = np.full(len(requested), prevalence, dtype=np.float64)
    else:
        builder = SparseFeatures(args.time_col, args.entity_col).fit(train, labels, args.target_col)
        hasher = FeatureHasher(n_features=HASH_DIMENSION, input_type="dict", alternate_sign=False, dtype=np.float32)
        x_train = builder.transform(train, hasher, labels=labels)
        x_requested = builder.transform(requested, hasher)

        positives = max(int(labels.sum()), 1)
        negatives = max(int(len(labels) - positives), 1)
        sample_weight = np.where(
            labels == 1,
            len(labels) / (2.0 * positives),
            len(labels) / (2.0 * negatives),
        ).astype(np.float32)
        classifier = SGDClassifier(
            loss="log_loss",
            penalty="elasticnet",
            alpha=2e-5,
            l1_ratio=0.05,
            max_iter=80,
            tol=1e-4,
            shuffle=True,
            random_state=20261019,
            average=True,
            n_jobs=1,
        )
        classifier.fit(x_train, labels, sample_weight=sample_weight)
        probabilities = classifier.predict_proba(x_requested)[:, 1]

    probabilities = np.nan_to_num(probabilities, nan=prevalence, posinf=1.0, neginf=0.0)
    probabilities = np.clip(probabilities, 0.0, 1.0)
    result = pd.DataFrame(
        {
            "row_id": np.arange(len(requested), dtype=np.int64),
            "prediction": probabilities.astype(np.float64),
        }
    )
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)


if __name__ == "__main__":
    main()
