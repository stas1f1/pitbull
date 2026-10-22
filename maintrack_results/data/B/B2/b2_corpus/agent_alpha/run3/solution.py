#!/usr/bin/env python3
"""Bounded random-forest solution for binary RelBench task tables."""

import os

for _key in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_key] = "1"

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


MAX_TRAIN_ROWS = 200_000
MAX_SOURCE_COLUMNS = 32
MAX_CATEGORICAL_COLUMNS = 12


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", required=True, choices=["val", "test"])
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def encode_target(series):
    available = series.dropna()
    if available.empty:
        raise ValueError("Training target has no labels")
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).to_numpy(dtype=np.uint8)
    numeric = pd.to_numeric(series, errors="coerce")
    numeric_classes = np.sort(numeric.dropna().unique())
    if 1 <= len(numeric_classes) <= 2:
        return (numeric.fillna(numeric_classes[0]).to_numpy() == numeric_classes[-1]).astype(np.uint8)
    normalized = series.astype("string").str.strip().str.lower()
    positive = {"1", "true", "yes", "y", "positive", "pos"}
    negative = {"0", "false", "no", "n", "negative", "neg"}
    classes = set(normalized.dropna().unique())
    if classes and classes <= positive | negative:
        return normalized.isin(positive).to_numpy(dtype=np.uint8)
    ordered = sorted(classes)
    if len(ordered) != 2:
        raise ValueError("Expected a binary target")
    return (normalized == ordered[-1]).to_numpy(dtype=np.uint8)


def limit_train(frame, time_col):
    if len(frame) <= MAX_TRAIN_ROWS:
        return frame.reset_index(drop=True)
    if time_col in frame:
        times = pd.to_datetime(frame[time_col], errors="coerce", utc=True)
        order = np.argsort(times.astype("int64").to_numpy(), kind="stable")
        return frame.iloc[order[-MAX_TRAIN_ROWS:]].reset_index(drop=True)
    positions = np.linspace(0, len(frame) - 1, MAX_TRAIN_ROWS, dtype=np.int64)
    return frame.iloc[positions].reset_index(drop=True)


class DenseFeatures:
    def __init__(self, time_col, entity_col):
        self.time_col = time_col
        self.entity_col = entity_col
        self.prior = 0.5
        self.specification = []

    @staticmethod
    def keys(series):
        return series.astype("string").fillna("<NA>")

    def fit(self, frame, labels, target_col):
        self.prior = float(labels.mean())
        candidates = [column for column in frame.columns if column != target_col]
        priority = [column for column in (self.time_col, self.entity_col) if column in candidates]
        candidates = (priority + [column for column in candidates if column not in priority])[:MAX_SOURCE_COLUMNS]

        numeric_columns = []
        categorical_columns = []
        for column in candidates:
            if column == self.time_col:
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            identifier = column == self.entity_col or column.lower().endswith("id")
            if numeric.notna().mean() >= 0.98 and not identifier:
                numeric_columns.append(column)
            else:
                categorical_columns.append(column)

        # Keep the entity plus the lowest-cardinality categoricals to bound map memory.
        category_order = []
        if self.entity_col in categorical_columns:
            category_order.append(self.entity_col)
        category_order.extend(
            sorted(
                (column for column in categorical_columns if column != self.entity_col),
                key=lambda column: frame[column].nunique(dropna=True),
            )
        )
        categorical_columns = category_order[:MAX_CATEGORICAL_COLUMNS]

        if self.time_col in candidates:
            self.specification.append((self.time_col, "time", None))
        for column in numeric_columns:
            numeric = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            median = float(numeric.median()) if numeric.notna().any() else 0.0
            low = float(numeric.quantile(0.005)) if numeric.notna().any() else median
            high = float(numeric.quantile(0.995)) if numeric.notna().any() else median
            scale = max(high - low, 1.0)
            self.specification.append((column, "numeric", (median, low, high, scale)))
        for column in categorical_columns:
            keys = self.keys(frame[column])
            stats = pd.DataFrame({"key": keys, "label": labels}).groupby("key", sort=False)["label"].agg(["sum", "count"])
            self.specification.append((column, "categorical", (stats["sum"].to_dict(), stats["count"].to_dict())))
        return self

    def transform(self, frame, train_labels=None):
        output = []
        for column, kind, state in self.specification:
            series = frame[column] if column in frame else pd.Series(pd.NA, index=frame.index)
            if kind == "time":
                dt = pd.to_datetime(series, errors="coerce", utc=True)
                raw = dt.astype("int64").to_numpy(dtype=np.float64)
                raw[dt.isna().to_numpy()] = 0.0
                output.extend(
                    [
                        raw / 86_400_000_000_000.0,
                        dt.dt.year.fillna(0).to_numpy(dtype=np.float64),
                        dt.dt.month.fillna(0).to_numpy(dtype=np.float64),
                        dt.dt.dayofweek.fillna(0).to_numpy(dtype=np.float64),
                        dt.dt.dayofyear.fillna(0).to_numpy(dtype=np.float64),
                    ]
                )
            elif kind == "numeric":
                median, low, high, scale = state
                numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
                values = numeric.fillna(median).clip(low, high).to_numpy(dtype=np.float64)
                output.append((values - median) / scale)
                output.append(numeric.isna().to_numpy(dtype=np.float64))
            else:
                sums_map, counts_map = state
                keys = self.keys(series)
                sums = keys.map(sums_map).fillna(0.0).to_numpy(dtype=np.float64)
                counts = keys.map(counts_map).fillna(0.0).to_numpy(dtype=np.float64)
                if train_labels is not None:
                    sums = sums - train_labels
                    counts = np.maximum(counts - 1.0, 0.0)
                smoothing = 25.0
                output.append((sums + smoothing * self.prior) / (counts + smoothing))
                output.append(np.log1p(counts))
        if not output:
            return np.zeros((len(frame), 1), dtype=np.float32)
        matrix = np.column_stack(output).astype(np.float32, copy=False)
        return np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)


def main():
    args = cli()
    root = Path(args.task_dir)
    train = pd.read_parquet(root / "train.parquet")
    requested = pd.read_parquet(root / f"{args.split}.parquet")
    if args.target_col not in train:
        raise KeyError(f"train.parquet does not contain {args.target_col!r}")

    train = limit_train(train, args.time_col)
    labels = encode_target(train[args.target_col])
    prevalence = float(labels.mean())

    if np.unique(labels).size < 2:
        prediction = np.full(len(requested), prevalence, dtype=np.float64)
    else:
        builder = DenseFeatures(args.time_col, args.entity_col).fit(train, labels, args.target_col)
        x_train = builder.transform(train, train_labels=labels)
        x_requested = builder.transform(requested)
        forest = RandomForestClassifier(
            n_estimators=144,
            criterion="entropy",
            max_depth=13,
            max_leaf_nodes=2048,
            min_samples_leaf=12,
            max_features=0.75,
            bootstrap=True,
            max_samples=0.8,
            n_jobs=1,
            random_state=20261020,
        )
        forest.fit(x_train, labels)
        prediction = forest.predict_proba(x_requested)[:, 1]

    prediction = np.nan_to_num(prediction, nan=prevalence, posinf=1.0, neginf=0.0)
    prediction = np.clip(prediction, 0.0, 1.0)
    result = pd.DataFrame(
        {
            "row_id": np.arange(len(requested), dtype=np.int64),
            "prediction": prediction.astype(np.float64),
        }
    )
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)


if __name__ == "__main__":
    main()
