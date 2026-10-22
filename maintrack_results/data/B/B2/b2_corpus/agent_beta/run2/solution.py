#!/usr/bin/env python
"""Single-threaded, leakage-safe predictor for binary RelBench task tables."""

from __future__ import annotations

import argparse
import os

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_variable] = "1"

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", required=True, choices=["val", "test"])
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def load_labeled(path: Path, time_col: str, entity_col: str, target_col: str) -> pd.DataFrame:
    result = pd.read_parquet(path, columns=[time_col, entity_col, target_col]).copy()
    result[time_col] = pd.to_datetime(result[time_col], errors="coerce")
    if result[time_col].isna().any():
        raise ValueError(f"invalid or missing timestamps in {path}")
    result[target_col] = pd.to_numeric(result[target_col], errors="raise")
    if not result[target_col].isin([0, 1]).all():
        raise ValueError(f"{target_col!r} must contain only 0 and 1")
    return result


def load_query(path: Path, time_col: str, entity_col: str) -> pd.DataFrame:
    result = pd.read_parquet(path, columns=[time_col, entity_col]).copy()
    result[time_col] = pd.to_datetime(result[time_col], errors="coerce")
    if result[time_col].isna().any():
        raise ValueError(f"invalid or missing timestamps in {path}")
    return result


def entity_key(value: object) -> object:
    return ("missing",) if pd.isna(value) else value


class SnapshotHistory:
    """History updated by complete timestamp snapshots to prevent leakage."""

    def __init__(self, prior: float) -> None:
        self.prior = float(prior)
        self.global_count = 0
        self.global_sum = 0.0
        self.snapshot_rates: deque[float] = deque(maxlen=32)
        self.count: dict[object, int] = defaultdict(int)
        self.total: dict[object, float] = defaultdict(float)
        self.recent: dict[object, deque[float]] = defaultdict(lambda: deque(maxlen=16))
        self.first_seen: dict[object, pd.Timestamp] = {}
        self.last_seen: dict[object, pd.Timestamp] = {}

    def describe(self, entity: object, timestamp: pd.Timestamp) -> list[float]:
        key = entity_key(entity)
        count = self.count[key]
        total = self.total[key]
        recent = self.recent[key]
        bayes_rate = (total + 12.0 * self.prior) / (count + 12.0)
        global_rate = (self.global_sum + 32.0 * self.prior) / (
            self.global_count + 32.0
        )
        last_time = self.last_seen.get(key)
        first_time = self.first_seen.get(key)
        recency_days = (
            (timestamp - last_time).total_seconds() / 86400.0
            if last_time is not None
            else np.nan
        )
        age_days = (
            max((timestamp - first_time).total_seconds() / 86400.0, 0.0)
            if first_time is not None
            else np.nan
        )
        activity = count / (1.0 + age_days / 365.25) if first_time is not None else 0.0
        features = [
            np.log1p(count),
            bayes_rate,
            global_rate,
            recency_days,
            activity,
            float(recent[-1]) if recent else self.prior,
        ]
        recent_rates = []
        for width in (2, 4, 8, 16):
            tail = list(recent)[-width:]
            rate = (sum(tail) + 2.0 * self.prior) / (len(tail) + 2.0)
            recent_rates.append(rate)
            features.extend([rate, float(len(tail))])
        features.append(recent_rates[1] - bayes_rate)
        for width in (1, 3, 8, 16):
            tail = list(self.snapshot_rates)[-width:]
            features.append(float(np.mean(tail)) if tail else self.prior)
        return features

    def add_snapshot(
        self,
        timestamp: pd.Timestamp,
        rows: list[tuple[object, float]],
    ) -> None:
        if not rows:
            return
        self.snapshot_rates.append(float(np.mean([target for _, target in rows])))
        for entity, target_value in rows:
            key = entity_key(entity)
            target = float(target_value)
            self.global_count += 1
            self.global_sum += target
            self.count[key] += 1
            self.total[key] += target
            self.recent[key].append(target)
            if key not in self.first_seen:
                self.first_seen[key] = timestamp
            self.last_seen[key] = timestamp


def time_features(timestamp: pd.Timestamp, origin: pd.Timestamp) -> list[float]:
    days = (timestamp - origin).total_seconds() / 86400.0
    year_phase = 2.0 * np.pi * timestamp.dayofyear / 365.25
    month_phase = 2.0 * np.pi * timestamp.month / 12.0
    return [
        days / 365.25,
        np.sin(year_phase),
        np.cos(year_phase),
        np.sin(month_phase),
        np.cos(month_phase),
    ]


def grouped_rows(
    frame: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
) -> list[tuple[pd.Timestamp, list[tuple[object, float]]]]:
    ordered = frame.sort_values(time_col, kind="stable")
    groups = []
    for timestamp, group in ordered.groupby(time_col, sort=True):
        rows = list(group[[entity_col, target_col]].itertuples(index=False, name=None))
        groups.append((timestamp, rows))
    return groups


def training_matrix(
    frame: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> np.ndarray:
    work = frame.reset_index(drop=True).copy()
    work["__row_number"] = np.arange(len(work))
    state = SnapshotHistory(prior)
    matrix: list[list[float] | None] = [None] * len(work)
    for timestamp, group in work.sort_values(time_col, kind="stable").groupby(
        time_col, sort=True
    ):
        rows = list(
            group[[entity_col, target_col, "__row_number"]].itertuples(
                index=False, name=None
            )
        )
        for entity, _target, row_number in rows:
            matrix[row_number] = state.describe(entity, timestamp) + time_features(
                timestamp, origin
            )
        state.add_snapshot(timestamp, [(entity, target) for entity, target, _ in rows])
    return np.asarray(matrix, dtype=np.float64)


def query_matrix(
    reference: pd.DataFrame,
    query: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> np.ndarray:
    work = query.reset_index(drop=True).copy()
    work["__row_number"] = np.arange(len(work))
    history_groups = grouped_rows(reference, time_col, entity_col, target_col)
    cursor = 0
    state = SnapshotHistory(prior)
    matrix: list[list[float] | None] = [None] * len(work)
    for timestamp, group in work.sort_values(time_col, kind="stable").groupby(
        time_col, sort=True
    ):
        while cursor < len(history_groups) and history_groups[cursor][0] < timestamp:
            history_time, history_rows = history_groups[cursor]
            state.add_snapshot(history_time, history_rows)
            cursor += 1
        for entity, row_number in group[[entity_col, "__row_number"]].itertuples(
            index=False, name=None
        ):
            matrix[row_number] = state.describe(entity, timestamp) + time_features(
                timestamp, origin
            )
    return np.asarray(matrix, dtype=np.float64)


def model_probabilities(
    train_x: np.ndarray,
    train_y: np.ndarray,
    query_x: np.ndarray,
    prior: float,
) -> np.ndarray:
    if np.unique(train_y).size < 2:
        return np.full(len(query_x), prior, dtype=np.float64)

    imputer = SimpleImputer(strategy="median", add_indicator=True)
    clean_train = imputer.fit_transform(train_x)
    clean_query = imputer.transform(query_x)
    forest = ExtraTreesClassifier(
        n_estimators=256,
        max_depth=10,
        min_samples_leaf=6,
        max_features=0.75,
        n_jobs=1,
        random_state=2718,
    )
    linear = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=0.35,
            solver="liblinear",
            max_iter=400,
            random_state=2718,
        ),
    )
    forest.fit(clean_train, train_y)
    linear.fit(clean_train, train_y)
    return (
        0.65 * forest.predict_proba(clean_query)[:, 1]
        + 0.35 * linear.predict_proba(clean_query)[:, 1]
    )


def main() -> None:
    args = arguments()
    train = load_labeled(
        args.task_dir / "train.parquet",
        args.time_col,
        args.entity_col,
        args.target_col,
    )
    if args.split == "test":
        validation = load_labeled(
            args.task_dir / "val.parquet",
            args.time_col,
            args.entity_col,
            args.target_col,
        )
        reference = pd.concat([train, validation], ignore_index=True)
    else:
        reference = train
    query = load_query(
        args.task_dir / f"{args.split}.parquet", args.time_col, args.entity_col
    )
    target = reference[args.target_col].to_numpy(dtype=np.int8)
    prior = float(np.clip(target.mean(), 1e-6, 1.0 - 1e-6))
    origin = min(reference[args.time_col].min(), query[args.time_col].min())
    train_x = training_matrix(
        reference,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    query_x = query_matrix(
        reference,
        query,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    probabilities = np.clip(
        model_probabilities(train_x, target, query_x, prior), 1e-6, 1.0 - 1e-6
    )
    if not np.isfinite(probabilities).all():
        raise RuntimeError("non-finite model output")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "row_id": np.arange(len(query), dtype=np.int64),
            "prediction": probabilities,
        }
    ).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
