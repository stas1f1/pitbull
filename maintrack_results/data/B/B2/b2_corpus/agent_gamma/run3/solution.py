#!/usr/bin/env python
"""Bounded-memory hashed linear model for binary RelBench tasks."""

import os

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
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import SGDClassifier


MAX_TRAIN_ROWS = 500_000
MAX_COLUMNS = 32
BATCH_SIZE = 16_384
HASH_DIMENSION = 2**18


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def make_labels(series):
    if pd.api.types.is_bool_dtype(series):
        return series.astype("float32")
    numeric = pd.to_numeric(series, errors="coerce")
    values = sorted(numeric.dropna().unique().tolist())
    if len(values) == 2 and values != [0, 1]:
        numeric = numeric.map({values[0]: 0.0, values[1]: 1.0})
    if numeric.notna().any():
        return numeric.astype("float32")
    text = series.astype("string").str.strip().str.lower()
    positive = {"1", "true", "yes", "y", "positive", "pos"}
    negative = {"0", "false", "no", "n", "negative", "neg"}
    return text.map(
        lambda item: 1.0 if item in positive else (0.0 if item in negative else np.nan)
    ).astype("float32")


def select_columns(train, query, target_col, entity_col, time_col):
    common = [column for column in train.columns if column in query.columns and column != target_col]
    selected = []
    for column in (entity_col, time_col):
        if column in common and column not in selected:
            selected.append(column)
    for column in common:
        if column not in selected:
            selected.append(column)
    return selected[:MAX_COLUMNS]


def numeric_scales(frame, columns, entity_col, time_col):
    scales = {}
    for column in columns:
        if column in {entity_col, time_col} or not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype="float64")
        values = values[np.isfinite(values)]
        if values.size:
            median = float(np.median(values))
            q25, q75 = np.quantile(values, [0.25, 0.75])
            scale = float(max(q75 - q25, np.std(values), 1e-6))
        else:
            median, scale = 0.0, 1.0
        scales[column] = (median, scale)
    return scales


def records(frame, columns, scales, entity_col, time_col):
    time_values = (
        pd.to_datetime(frame[time_col], errors="coerce", utc=True)
        if time_col in frame.columns
        else pd.Series(pd.NaT, index=frame.index)
    )
    arrays = {column: frame[column].to_numpy() for column in columns if column != time_col}
    for position in range(len(frame)):
        features = {}
        entity_value = None
        for column, values in arrays.items():
            value = values[position]
            if column == entity_col:
                entity_value = "<NA>" if pd.isna(value) else str(value)
                features[f"{column}={entity_value}"] = 1.0
            elif column in scales:
                numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(numeric) or not np.isfinite(float(numeric)):
                    features[f"{column}:missing"] = 1.0
                else:
                    center, scale = scales[column]
                    features[f"{column}:numeric"] = float(np.clip((float(numeric) - center) / scale, -12, 12))
            else:
                token = "<NA>" if pd.isna(value) else str(value)
                features[f"{column}={token}"] = 1.0

        timestamp = time_values.iloc[position]
        if pd.isna(timestamp):
            features["time:missing"] = 1.0
        else:
            month_angle = 2.0 * np.pi * (timestamp.month - 1) / 12.0
            weekday_angle = 2.0 * np.pi * timestamp.dayofweek / 7.0
            features["time:year"] = float(np.clip((timestamp.year - 2000) / 20.0, -5, 5))
            features["time:month_sin"] = float(np.sin(month_angle))
            features["time:month_cos"] = float(np.cos(month_angle))
            features["time:weekday_sin"] = float(np.sin(weekday_angle))
            features["time:weekday_cos"] = float(np.cos(weekday_angle))
            if entity_value is not None:
                features[f"entity_month={entity_value}|{timestamp.month}"] = 1.0
        yield features


def batches(length, batch_size=BATCH_SIZE):
    for start in range(0, length, batch_size):
        yield start, min(start + batch_size, length)


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    train = pd.read_parquet(task_dir / "train.parquet")
    query = pd.read_parquet(task_dir / f"{args.split}.parquet")
    if args.target_col not in train.columns:
        raise ValueError(f"Target column {args.target_col!r} not found")

    target = make_labels(train[args.target_col])
    keep = target.notna().to_numpy()
    train = train.loc[keep].reset_index(drop=True)
    y = target.loc[keep].to_numpy(dtype="int8")
    if len(train) > MAX_TRAIN_ROWS:
        if args.time_col in train.columns:
            order = np.asarray(
                pd.to_datetime(train[args.time_col], errors="coerce", utc=True).argsort(kind="stable")
            )
            chosen = order[-MAX_TRAIN_ROWS:]
        else:
            chosen = np.arange(len(train) - MAX_TRAIN_ROWS, len(train))
        train = train.iloc[chosen].reset_index(drop=True)
        y = y[chosen]

    prior = float(np.clip((float(y.sum()) + 1.0) / (len(y) + 2.0), 1e-6, 1 - 1e-6)) if len(y) else 0.5
    if len(y) < 2 or np.unique(y).size < 2:
        probabilities = np.full(len(query), prior, dtype="float64")
    else:
        columns = select_columns(train, query, args.target_col, args.entity_col, args.time_col)
        scales = numeric_scales(train, columns, args.entity_col, args.time_col)
        hasher = FeatureHasher(
            n_features=HASH_DIMENSION, input_type="dict", alternate_sign=False, dtype=np.float32
        )
        model = SGDClassifier(
            loss="log_loss",
            penalty="elasticnet",
            alpha=2e-5,
            l1_ratio=0.05,
            learning_rate="optimal",
            average=True,
            random_state=202603,
        )
        rng = np.random.default_rng(202603)
        for epoch in range(3):
            permutation = rng.permutation(len(train))
            for start, stop in batches(len(train)):
                index = permutation[start:stop]
                batch = train.iloc[index]
                matrix = hasher.transform(
                    records(batch, columns, scales, args.entity_col, args.time_col)
                )
                if epoch == 0 and start == 0:
                    model.partial_fit(matrix, y[index], classes=np.array([0, 1], dtype="int8"))
                else:
                    model.partial_fit(matrix, y[index])

        probabilities = np.empty(len(query), dtype="float64")
        for start, stop in batches(len(query)):
            batch = query.iloc[start:stop]
            matrix = hasher.transform(records(batch, columns, scales, args.entity_col, args.time_col))
            probabilities[start:stop] = model.predict_proba(matrix)[:, 1]
        probabilities = 0.97 * probabilities + 0.03 * prior

    probabilities = np.clip(
        np.nan_to_num(probabilities, nan=prior, posinf=1.0, neginf=0.0), 0.0, 1.0
    )
    result = pd.DataFrame(
        {"row_id": np.arange(len(query), dtype="int64"), "prediction": probabilities}
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)


if __name__ == "__main__":
    main()
