#!/usr/bin/env python
"""Memory-bounded, CPU-only baseline for binary RelBench tasks."""

import os

# Set these before importing numerical libraries.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


MAX_TRAIN_ROWS = 400_000
MAX_FEATURE_COLUMNS = 64


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
    """Convert common binary target representations to float labels."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype("float32")
    numeric = pd.to_numeric(series, errors="coerce")
    values = sorted(pd.unique(numeric.dropna()))
    if len(values) == 2 and values != [0, 1]:
        numeric = numeric.map({values[0]: 0.0, values[1]: 1.0})
    if numeric.notna().any():
        return numeric.astype("float32")
    text = series.astype("string").str.strip().str.lower()
    positives = {"1", "true", "yes", "y", "positive", "pos"}
    negatives = {"0", "false", "no", "n", "negative", "neg"}
    mapped = text.map(lambda x: 1.0 if x in positives else (0.0 if x in negatives else np.nan))
    return mapped.astype("float32")


def category_key(series):
    return series.astype("string").fillna("<NA>")


def datetime_parts(train_col, query_col):
    train_dt = pd.to_datetime(train_col, errors="coerce", utc=True)
    query_dt = pd.to_datetime(query_col, errors="coerce", utc=True)

    def parts(values):
        epoch = values.astype("int64", copy=False).to_numpy(dtype="float64") / 86_400_000_000_000.0
        epoch[values.isna().to_numpy()] = np.nan
        return [
            epoch,
            values.dt.month.to_numpy(dtype="float64"),
            values.dt.dayofweek.to_numpy(dtype="float64"),
            values.dt.hour.to_numpy(dtype="float64"),
        ]

    return parts(train_dt), parts(query_dt)


def numeric_feature(train_col, query_col):
    train_num = pd.to_numeric(train_col, errors="coerce").to_numpy(dtype="float64")
    query_num = pd.to_numeric(query_col, errors="coerce").to_numpy(dtype="float64")
    train_num[~np.isfinite(train_num)] = np.nan
    query_num[~np.isfinite(query_num)] = np.nan
    finite = train_num[np.isfinite(train_num)]
    median = float(np.median(finite)) if finite.size else 0.0
    if finite.size > 20:
        low, high = np.quantile(finite, [0.005, 0.995])
        train_num = np.clip(train_num, low, high)
        query_num = np.clip(query_num, low, high)
    return np.nan_to_num(train_num, nan=median), np.nan_to_num(query_num, nan=median)


def encoded_category(train_col, query_col, y, prior):
    """Leave-one-out target rate for train; smoothed full rate for query."""
    train_key = category_key(train_col)
    query_key = category_key(query_col)
    frame = pd.DataFrame({"key": train_key, "y": y})
    stats = frame.groupby("key", sort=False, observed=True)["y"].agg(["sum", "count"])
    sums = train_key.map(stats["sum"]).to_numpy(dtype="float64")
    counts = train_key.map(stats["count"]).to_numpy(dtype="float64")
    smoothing = 12.0
    train_rate = (sums - y + smoothing * prior) / np.maximum(counts - 1.0 + smoothing, 1.0)
    query_sums = query_key.map(stats["sum"]).fillna(0.0).to_numpy(dtype="float64")
    query_counts = query_key.map(stats["count"]).fillna(0.0).to_numpy(dtype="float64")
    query_rate = (query_sums + smoothing * prior) / (query_counts + smoothing)
    train_freq = np.log1p(counts)
    query_freq = np.log1p(query_counts)
    return (train_rate, train_freq), (query_rate, query_freq)


def build_features(train, query, y, target_col, time_col, entity_col):
    common = [c for c in train.columns if c in query.columns and c != target_col]
    ordered = []
    for special in (entity_col, time_col):
        if special in common and special not in ordered:
            ordered.append(special)
    for column in common:
        if column not in ordered:
            ordered.append(column)
    ordered = ordered[:MAX_FEATURE_COLUMNS]

    prior = float(np.mean(y))
    train_features, query_features = [], []
    for column in ordered:
        train_col, query_col = train[column], query[column]
        is_time = column == time_col or pd.api.types.is_datetime64_any_dtype(train_col)
        if is_time:
            left, right = datetime_parts(train_col, query_col)
            train_features.extend(left)
            query_features.extend(right)
        elif pd.api.types.is_numeric_dtype(train_col) and column != entity_col:
            left, right = numeric_feature(train_col, query_col)
            train_features.append(left)
            query_features.append(right)
        else:
            left, right = encoded_category(train_col, query_col, y, prior)
            train_features.extend(left)
            query_features.extend(right)

    if not train_features:
        train_features = [np.zeros(len(train), dtype="float64")]
        query_features = [np.zeros(len(query), dtype="float64")]
    x_train = np.column_stack(train_features).astype("float32", copy=False)
    x_query = np.column_stack(query_features).astype("float32", copy=False)
    return x_train, x_query


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    train = pd.read_parquet(task_dir / "train.parquet")
    query = pd.read_parquet(task_dir / f"{args.split}.parquet")
    if args.target_col not in train.columns:
        raise ValueError(f"target column {args.target_col!r} is absent from train.parquet")

    y_all = binary_target(train[args.target_col])
    valid = y_all.notna().to_numpy()
    train = train.loc[valid].reset_index(drop=True)
    y = y_all.loc[valid].to_numpy(dtype="float64")
    if len(train) > MAX_TRAIN_ROWS:
        if args.time_col in train.columns:
            order = pd.to_datetime(train[args.time_col], errors="coerce", utc=True).argsort(kind="stable")
            keep = np.asarray(order[-MAX_TRAIN_ROWS:])
        else:
            keep = np.arange(len(train) - MAX_TRAIN_ROWS, len(train))
        train = train.iloc[keep].reset_index(drop=True)
        y = y[keep]

    prior = float(np.clip(np.mean(y), 1e-6, 1.0 - 1e-6)) if len(y) else 0.5
    if len(y) < 2 or np.unique(y).size < 2:
        prediction = np.full(len(query), prior, dtype="float64")
    else:
        x_train, x_query = build_features(
            train, query, y, args.target_col, args.time_col, args.entity_col
        )
        model = HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=140,
            max_leaf_nodes=15,
            min_samples_leaf=30,
            l2_regularization=1.0,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=731,
        )
        model.fit(x_train, y.astype("int8"))
        prediction = model.predict_proba(x_query)[:, 1]

    prediction = np.nan_to_num(prediction, nan=prior, posinf=1.0, neginf=0.0)
    prediction = np.clip(prediction, 0.0, 1.0)
    output = pd.DataFrame(
        {"row_id": np.arange(len(query), dtype="int64"), "prediction": prediction}
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()
