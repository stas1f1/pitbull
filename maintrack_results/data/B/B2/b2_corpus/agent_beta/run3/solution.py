#!/usr/bin/env python
"""Sparse temporal classifier for the supplied binary task-table interface."""

from __future__ import annotations

import argparse
import os

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction import FeatureHasher
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--time-col", required=True)
    parser.add_argument("--entity-col", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--split", required=True, choices=("val", "test"))
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def labeled_table(path: Path, time_col: str, entity_col: str, target_col: str) -> pd.DataFrame:
    table = pd.read_parquet(path, columns=[time_col, entity_col, target_col]).copy()
    table[time_col] = pd.to_datetime(table[time_col], errors="coerce")
    table[target_col] = pd.to_numeric(table[target_col], errors="raise")
    if table[time_col].isna().any():
        raise ValueError(f"missing or invalid timestamps in {path}")
    if not table[target_col].isin([0, 1]).all():
        raise ValueError(f"column {target_col!r} is not binary")
    return table


def query_table(path: Path, time_col: str, entity_col: str) -> pd.DataFrame:
    table = pd.read_parquet(path, columns=[time_col, entity_col]).copy()
    table[time_col] = pd.to_datetime(table[time_col], errors="coerce")
    if table[time_col].isna().any():
        raise ValueError(f"missing or invalid timestamps in {path}")
    return table


def key_for(value: object) -> object:
    return "<missing>" if pd.isna(value) else value


def token_for(value: object) -> str:
    value = key_for(value)
    return f"{type(value).__name__}:{value}"


class Past:
    """Compact state containing labels from strictly earlier timestamps."""

    def __init__(self, prior: float) -> None:
        self.prior = float(prior)
        self.n: dict[object, int] = defaultdict(int)
        self.s: dict[object, float] = defaultdict(float)
        self.recent: dict[object, deque[float]] = defaultdict(lambda: deque(maxlen=12))
        self.last_time: dict[object, pd.Timestamp] = {}
        self.global_n = 0
        self.global_s = 0.0
        self.global_recent: deque[float] = deque(maxlen=512)

    def numbers(self, entity: object, timestamp: pd.Timestamp, origin: pd.Timestamp) -> list[float]:
        key = key_for(entity)
        count = self.n[key]
        total = self.s[key]
        history = self.recent[key]
        entity_rate = (total + 10.0 * self.prior) / (count + 10.0)
        global_rate = (self.global_s + 50.0 * self.prior) / (self.global_n + 50.0)
        global_recent = (
            float(np.mean(self.global_recent)) if self.global_recent else self.prior
        )
        if key in self.last_time:
            gap = (timestamp - self.last_time[key]).total_seconds() / 86400.0
            log_gap = np.log1p(max(gap, 0.0))
        else:
            log_gap = np.nan
        rates = []
        for width in (2, 5, 10):
            tail = list(history)[-width:]
            rates.append((sum(tail) + 3.0 * self.prior) / (len(tail) + 3.0))
        elapsed = (timestamp - origin).total_seconds() / (86400.0 * 365.25)
        phase = 2.0 * np.pi * timestamp.dayofyear / 365.25
        return [
            np.log1p(count),
            entity_rate,
            float(history[-1]) if history else self.prior,
            rates[0],
            rates[1],
            rates[2],
            rates[1] - entity_rate,
            log_gap,
            global_rate,
            global_recent,
            elapsed,
            np.sin(phase),
            np.cos(phase),
        ]

    def add_group(
        self,
        timestamp: pd.Timestamp,
        observations: list[tuple[object, float]],
    ) -> None:
        for entity, target_value in observations:
            key = key_for(entity)
            target = float(target_value)
            self.n[key] += 1
            self.s[key] += target
            self.recent[key].append(target)
            self.last_time[key] = timestamp
            self.global_n += 1
            self.global_s += target
            self.global_recent.append(target)


def categorical_tokens(entity: object, timestamp: pd.Timestamp) -> list[str]:
    entity_text = token_for(entity)
    season = (timestamp.month - 1) // 3
    return [
        f"entity={entity_text}",
        f"entity_season={entity_text}|{season}",
        f"month={timestamp.month}",
        f"quarter={season}",
    ]


def training_features(
    table: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> tuple[np.ndarray, list[list[str]]]:
    work = table.reset_index(drop=True).copy()
    work["__position"] = np.arange(len(work))
    numeric: list[list[float] | None] = [None] * len(work)
    tokens: list[list[str] | None] = [None] * len(work)
    state = Past(prior)
    for timestamp, group in work.sort_values(time_col, kind="stable").groupby(
        time_col, sort=True
    ):
        rows = list(
            group[[entity_col, target_col, "__position"]].itertuples(
                index=False, name=None
            )
        )
        for entity, _target, position in rows:
            numeric[position] = state.numbers(entity, timestamp, origin)
            tokens[position] = categorical_tokens(entity, timestamp)
        state.add_group(timestamp, [(entity, target) for entity, target, _ in rows])
    return np.asarray(numeric, dtype=np.float64), tokens  # type: ignore[arg-type]


def prediction_features(
    reference: pd.DataFrame,
    query: pd.DataFrame,
    time_col: str,
    entity_col: str,
    target_col: str,
    prior: float,
    origin: pd.Timestamp,
) -> tuple[np.ndarray, list[list[str]]]:
    work = query.reset_index(drop=True).copy()
    work["__position"] = np.arange(len(work))
    numeric: list[list[float] | None] = [None] * len(work)
    tokens: list[list[str] | None] = [None] * len(work)
    ordered_reference = reference.sort_values(time_col, kind="stable")
    reference_groups = []
    for timestamp, group in ordered_reference.groupby(time_col, sort=True):
        observations = list(
            group[[entity_col, target_col]].itertuples(index=False, name=None)
        )
        reference_groups.append((timestamp, observations))
    state = Past(prior)
    cursor = 0
    for timestamp, group in work.sort_values(time_col, kind="stable").groupby(
        time_col, sort=True
    ):
        while cursor < len(reference_groups) and reference_groups[cursor][0] < timestamp:
            past_time, observations = reference_groups[cursor]
            state.add_group(past_time, observations)
            cursor += 1
        for entity, position in group[[entity_col, "__position"]].itertuples(
            index=False, name=None
        ):
            numeric[position] = state.numbers(entity, timestamp, origin)
            tokens[position] = categorical_tokens(entity, timestamp)
    return np.asarray(numeric, dtype=np.float64), tokens  # type: ignore[arg-type]


def sparse_matrices(
    train_numeric: np.ndarray,
    train_tokens: list[list[str]],
    query_numeric: np.ndarray,
    query_tokens: list[list[str]],
):
    imputer = SimpleImputer(strategy="median", add_indicator=True)
    train_dense = imputer.fit_transform(train_numeric)
    query_dense = imputer.transform(query_numeric)
    center = train_dense.mean(axis=0)
    scale = train_dense.std(axis=0)
    scale[scale < 1e-8] = 1.0
    train_dense = np.clip((train_dense - center) / scale, -12.0, 12.0)
    query_dense = np.clip((query_dense - center) / scale, -12.0, 12.0)
    hasher = FeatureHasher(n_features=32768, input_type="string", alternate_sign=False)
    train_hash = hasher.transform(train_tokens)
    query_hash = hasher.transform(query_tokens)
    train_sparse = hstack([csr_matrix(train_dense), train_hash], format="csr")
    query_sparse = hstack([csr_matrix(query_dense), query_hash], format="csr")
    return train_sparse, query_sparse


def main() -> None:
    args = cli()
    train = labeled_table(
        args.task_dir / "train.parquet", args.time_col, args.entity_col, args.target_col
    )
    if args.split == "test":
        validation = labeled_table(
            args.task_dir / "val.parquet",
            args.time_col,
            args.entity_col,
            args.target_col,
        )
        reference = pd.concat([train, validation], ignore_index=True)
    else:
        reference = train
    query = query_table(
        args.task_dir / f"{args.split}.parquet", args.time_col, args.entity_col
    )
    target = reference[args.target_col].to_numpy(dtype=np.int8)
    prior = float(np.clip(target.mean(), 1e-6, 1.0 - 1e-6))
    origin = min(reference[args.time_col].min(), query[args.time_col].min())
    train_numeric, train_tokens = training_features(
        reference,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    query_numeric, query_tokens = prediction_features(
        reference,
        query,
        args.time_col,
        args.entity_col,
        args.target_col,
        prior,
        origin,
    )
    if np.unique(target).size < 2:
        probability = np.full(len(query), prior)
    else:
        train_x, query_x = sparse_matrices(
            train_numeric, train_tokens, query_numeric, query_tokens
        )
        latest = reference[args.time_col].max()
        ages = (latest - reference[args.time_col]).dt.total_seconds().to_numpy() / 86400.0
        span = max(float(np.max(ages)), 1.0)
        weights = 0.35 + 0.65 * np.exp(-ages / max(span / 3.0, 1.0))
        classifier = LogisticRegression(
            C=0.6,
            solver="liblinear",
            max_iter=500,
            random_state=31415,
        )
        classifier.fit(train_x, target, sample_weight=weights)
        learned = classifier.predict_proba(query_x)[:, 1]
        # A small empirical-Bayes component stabilizes unseen and very rare entities.
        probability = 0.85 * learned + 0.15 * query_numeric[:, 1]
    probability = np.clip(probability, 1e-6, 1.0 - 1e-6)
    if not np.isfinite(probability).all():
        raise RuntimeError("non-finite predictions")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"row_id": np.arange(len(query), dtype=np.int64), "prediction": probability}
    ).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
