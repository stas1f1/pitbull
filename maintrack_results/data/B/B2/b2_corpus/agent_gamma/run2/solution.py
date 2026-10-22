#!/usr/bin/env python
"""Single-threaded empirical-Bayes predictor for binary RelBench tasks."""

import os

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_variable] = "1"

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


MAX_ROWS = 600_000
MAX_CONTEXT_COLUMNS = 20
RECENT_ENTITY_ROWS = 12


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def labels(series):
    if pd.api.types.is_bool_dtype(series):
        return series.astype("float32")
    numeric = pd.to_numeric(series, errors="coerce")
    unique = sorted(numeric.dropna().unique().tolist())
    if len(unique) == 2 and unique != [0, 1]:
        numeric = numeric.map({unique[0]: 0.0, unique[1]: 1.0})
    if numeric.notna().any():
        return numeric.astype("float32")
    normalized = series.astype("string").str.strip().str.lower()
    positive = {"1", "true", "yes", "y", "positive", "pos"}
    negative = {"0", "false", "no", "n", "negative", "neg"}
    return normalized.map(
        lambda value: 1.0 if value in positive else (0.0 if value in negative else np.nan)
    ).astype("float32")


def keys(series):
    return series.astype("string").fillna("<MISSING>")


def smoothed_lookup(train_key, query_key, y, prior, strength):
    table = pd.DataFrame({"key": keys(train_key), "label": y})
    aggregates = table.groupby("key", sort=False, observed=True)["label"].agg(["sum", "count"])
    query = keys(query_key)
    sums = query.map(aggregates["sum"]).fillna(0.0).to_numpy(dtype="float64")
    counts = query.map(aggregates["count"]).fillna(0.0).to_numpy(dtype="float64")
    rate = (sums + strength * prior) / (counts + strength)
    reliability = counts / (counts + strength)
    return rate, reliability


def numeric_bins(train_col, query_col):
    train_numeric = pd.to_numeric(train_col, errors="coerce")
    query_numeric = pd.to_numeric(query_col, errors="coerce")
    finite = train_numeric[np.isfinite(train_numeric.to_numpy(dtype="float64", na_value=np.nan))]
    if finite.empty or finite.nunique(dropna=True) < 3:
        return keys(train_col), keys(query_col)
    quantiles = np.unique(np.nanquantile(finite.to_numpy(dtype="float64"), np.linspace(0, 1, 17)))
    if len(quantiles) < 3:
        return keys(train_col), keys(query_col)
    quantiles[0], quantiles[-1] = -np.inf, np.inf
    train_bin = pd.cut(train_numeric, bins=quantiles, labels=False, include_lowest=True)
    query_bin = pd.cut(query_numeric, bins=quantiles, labels=False, include_lowest=True)
    return keys(train_bin), keys(query_bin)


def calendar_context(train_time, query_time):
    train_dt = pd.to_datetime(train_time, errors="coerce", utc=True)
    query_dt = pd.to_datetime(query_time, errors="coerce", utc=True)
    return (
        train_dt.dt.month.astype("string") + ":" + train_dt.dt.dayofweek.astype("string"),
        query_dt.dt.month.astype("string") + ":" + query_dt.dt.dayofweek.astype("string"),
    )


def main():
    args = arguments()
    root = Path(args.task_dir)
    train = pd.read_parquet(root / "train.parquet")
    query = pd.read_parquet(root / f"{args.split}.parquet")
    if args.target_col not in train.columns:
        raise ValueError(f"Missing target column: {args.target_col}")

    target = labels(train[args.target_col])
    usable = target.notna().to_numpy()
    train = train.loc[usable].copy()
    target = target.loc[usable].to_numpy(dtype="float64")

    if args.time_col in train.columns:
        chronology = pd.to_datetime(train[args.time_col], errors="coerce", utc=True)
        order = np.asarray(chronology.argsort(kind="stable"))
        train = train.iloc[order].reset_index(drop=True)
        target = target[order]
    else:
        train = train.reset_index(drop=True)

    if len(train) > MAX_ROWS:
        train = train.iloc[-MAX_ROWS:].reset_index(drop=True)
        target = target[-MAX_ROWS:]

    if len(target):
        positives = float(np.sum(target))
        prior = float(np.clip((positives + 1.0) / (len(target) + 2.0), 1e-6, 1 - 1e-6))
    else:
        prior = 0.5
    prediction = np.full(len(query), prior, dtype="float64")
    total_weight = np.ones(len(query), dtype="float64")

    # Full and recent entity histories are the primary signals for all supplied tasks.
    if args.entity_col in train.columns and args.entity_col in query.columns and len(target):
        full_rate, full_reliability = smoothed_lookup(
            train[args.entity_col], query[args.entity_col], target, prior, strength=18.0
        )
        full_weight = 3.0 * full_reliability
        prediction += full_weight * full_rate
        total_weight += full_weight

        recent_index = (
            pd.DataFrame({"entity": keys(train[args.entity_col])})
            .groupby("entity", sort=False, observed=True)
            .cumcount(ascending=False)
            .to_numpy()
            < RECENT_ENTITY_ROWS
        )
        recent_rate, recent_reliability = smoothed_lookup(
            train.loc[recent_index, args.entity_col],
            query[args.entity_col],
            target[recent_index],
            prior,
            strength=7.0,
        )
        recent_weight = 2.0 * recent_reliability
        prediction += recent_weight * recent_rate
        total_weight += recent_weight

    common = [
        column
        for column in train.columns
        if column in query.columns
        and column not in {args.target_col, args.entity_col, args.time_col}
    ][:MAX_CONTEXT_COLUMNS]
    for column in common:
        if pd.api.types.is_numeric_dtype(train[column]):
            train_key, query_key = numeric_bins(train[column], query[column])
        else:
            train_key, query_key = keys(train[column]), keys(query[column])
        rate, reliability = smoothed_lookup(train_key, query_key, target, prior, strength=30.0)
        weight = 0.35 * reliability
        prediction += weight * rate
        total_weight += weight

    if args.time_col in train.columns and args.time_col in query.columns and len(target):
        train_key, query_key = calendar_context(train[args.time_col], query[args.time_col])
        rate, reliability = smoothed_lookup(train_key, query_key, target, prior, strength=50.0)
        weight = 0.25 * reliability
        prediction += weight * rate
        total_weight += weight

    prediction /= total_weight
    prediction = np.clip(np.nan_to_num(prediction, nan=prior, posinf=1.0, neginf=0.0), 0.0, 1.0)
    result = pd.DataFrame(
        {"row_id": np.arange(len(query), dtype="int64"), "prediction": prediction}
    )
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)


if __name__ == "__main__":
    main()
