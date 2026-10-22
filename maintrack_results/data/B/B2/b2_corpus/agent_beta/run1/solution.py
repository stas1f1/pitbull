#!/usr/bin/env python
"""Leakage-safe tabular baseline for binary RelBench forecast task tables."""

from __future__ import annotations

import argparse
import os

# Set thread limits before importing numerical libraries.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


EPS = 1.0e-6
HISTORY = 32


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def read_frame(path: Path, time_col: str, entity_col: str, target_col: str) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=[time_col, entity_col, target_col]).copy()
    frame[time_col] = pd.to_datetime(frame[time_col], errors="coerce")
    if frame[time_col].isna().any():
        raise ValueError(f"{path} contains missing or invalid values in {time_col!r}")
    return frame


def safe_key(value: object) -> object:
    return "__MISSING_ENTITY__" if pd.isna(value) else value


class HistoryState:
    """Sufficient statistics updated only after a timestamp is completed."""

    def __init__(self, prior: float) -> None:
        self.prior = float(prior)
        self.total_n = 0
        self.total_y = 0.0
        self.global_recent: deque[float] = deque(maxlen=512)
        self.entity_n: dict[object, int] = defaultdict(int)
        self.entity_y: dict[object, float] = defaultdict(float)
        self.entity_recent: dict[object, deque[float]] = defaultdict(
            lambda: deque(maxlen=HISTORY)
        )
        self.entity_last_time: dict[object, pd.Timestamp] = {}

    def features(self, entity: object, timestamp: pd.Timestamp) -> list[float]:
        key = safe_key(entity)
        n = self.entity_n[key]
        successes = self.entity_y[key]
        hist = self.entity_recent[key]
        # Stronger shrinkage for rare entities keeps unseen/one-off users stable.
        smoothed = (successes + 8.0 * self.prior) / (n + 8.0)
        global_rate = (self.total_y + 32.0 * self.prior) / (self.total_n + 32.0)
        recent_global = (
            float(np.mean(self.global_recent)) if self.global_recent else self.prior
        )
        last_time = self.entity_last_time.get(key)
        days_since = (
            float((timestamp - last_time).total_seconds() / 86400.0)
            if last_time is not None
            else np.nan
        )
        values: list[float] = [
            np.log1p(n),
            smoothed,
            global_rate,
            recent_global,
            days_since,
            float(hist[-1]) if hist else self.prior,
        ]
        for window in (3, 5, 10, 20):
            tail = list(hist)[-window:]
            values.append(float(np.mean(tail)) if tail else self.prior)
            values.append(float(len(tail)))
        return values

    def update(self, entity: object, timestamp: pd.Timestamp, target: float) -> None:
        key = safe_key(entity)
        y = float(target)
        self.total_n += 1
        self.total_y += y
        self.global_recent.append(y)
        self.entity_n[key] += 1
        self.entity_y[key] += y
        self.entity_recent[key].append(y)
        self.entity_last_time[key] = timestamp


def calendar_features(timestamp: pd.Timestamp, origin: pd.Timestamp) -> list[float]:
    elapsed = float((timestamp - origin).total_seconds() / 86400.0)
    day = float(timestamp.dayofyear)
    month = float(timestamp.month)
    return [
        elapsed / 365.25,
        np.sin(2.0 * np.pi * day / 365.25),
        np.cos(2.0 * np.pi * day / 365.25),
        np.sin(2.0 * np.pi * month / 12.0),
        np.cos(2.0 * np.pi * month / 12.0),
    ]


def causal_training_features(
    frame: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> np.ndarray:
    ordered = frame.reset_index(drop=True).copy()
    ordered["__position"] = np.arange(len(ordered))
    ordered = ordered.sort_values([time_col, "__position"], kind="stable")
    output = np.empty((len(frame), 19), dtype=np.float64)
    state = HistoryState(prior)
    for timestamp, group in ordered.groupby(time_col, sort=True):
        # All rows at the same timestamp see the same past, never one another's labels.
        rows = list(
            group[[entity_col, target_col, "__position"]].itertuples(
                index=False, name=None
            )
        )
        for entity, _target, pos in rows:
            output[pos] = state.features(entity, timestamp) + calendar_features(timestamp, origin)
        for entity, target, _pos in rows:
            state.update(entity, timestamp, target)
    return output


def prediction_features(
    reference: pd.DataFrame,
    query: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> np.ndarray:
    refs = reference.sort_values(time_col, kind="stable")
    queries = query.reset_index(drop=True).copy()
    queries["__position"] = np.arange(len(queries))
    queries = queries.sort_values([time_col, "__position"], kind="stable")
    output = np.empty((len(query), 19), dtype=np.float64)
    state = HistoryState(prior)
    ref_rows = list(refs[[time_col, entity_col, target_col]].itertuples(index=False, name=None))
    cursor = 0
    for timestamp, group in queries.groupby(time_col, sort=True):
        while cursor < len(ref_rows) and ref_rows[cursor][0] < timestamp:
            ref_time, entity, target = ref_rows[cursor]
            state.update(entity, ref_time, target)
            cursor += 1
        for entity, pos in group[[entity_col, "__position"]].itertuples(
            index=False, name=None
        ):
            output[pos] = state.features(entity, timestamp) + calendar_features(timestamp, origin)
    return output


def fit_predict(x_train: np.ndarray, y: np.ndarray, x_query: np.ndarray, prior: float) -> np.ndarray:
    if len(np.unique(y)) < 2:
        return np.full(len(x_query), prior, dtype=np.float64)

    # A smooth linear model is robust on small tasks; a shallow boosting model
    # captures recency/rate thresholds. Their average reduces variance.
    linear = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(C=0.5, max_iter=400, solver="liblinear", random_state=1729),
    )
    tree = HistGradientBoostingClassifier(
        learning_rate=0.045,
        max_iter=140,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=2.0,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=15,
        random_state=1729,
    )
    linear.fit(x_train, y)
    tree.fit(x_train, y)
    p_linear = linear.predict_proba(x_query)[:, 1]
    p_tree = tree.predict_proba(x_query)[:, 1]
    return 0.45 * p_linear + 0.55 * p_tree


def main() -> None:
    args = parse_args()
    train = read_frame(
        args.task_dir / "train.parquet", args.time_col, args.entity_col, args.target_col
    )
    if args.split == "test":
        validation = read_frame(
            args.task_dir / "val.parquet", args.time_col, args.entity_col, args.target_col
        )
        reference = pd.concat([train, validation], ignore_index=True)
    else:
        reference = train
    query = read_frame(
        args.task_dir / f"{args.split}.parquet",
        args.time_col,
        args.entity_col,
        args.target_col,
    )

    y = pd.to_numeric(reference[args.target_col], errors="raise").to_numpy(dtype=np.int8)
    if not np.isin(y, [0, 1]).all():
        raise ValueError("target column must contain binary values 0 and 1")
    prior = float(np.clip(np.mean(y), EPS, 1.0 - EPS))
    origin = min(reference[args.time_col].min(), query[args.time_col].min())
    x_train = causal_training_features(
        reference,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    x_query = prediction_features(
        reference,
        query,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    prediction = np.clip(fit_predict(x_train, y, x_query, prior), EPS, 1.0 - EPS)
    if not np.isfinite(prediction).all():
        raise RuntimeError("model produced non-finite predictions")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"row_id": np.arange(len(query), dtype=np.int64), "prediction": prediction}
    ).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
