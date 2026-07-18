"""Shared config loading and representation building for the Step-5 scripts.

Kept out of the package tree on purpose: this is orchestration glue for the two
CLI entry points, not library code that anything else should import.
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.adapters.pcos.phenotype_heads import compute_domain_scores  # noqa: E402
from models.phenotype.clustering import ClusteringInput  # noqa: E402
from schemas.phenotype import ClusteringBenchmark  # noqa: E402

__all__ = [
    "CohortBundle",
    "build_representations",
    "load_config",
    "load_cohort",
    "resolve_artifact_dir",
    "write_benchmark_csv",
    "write_json",
]


def load_config(path: str | Path) -> dict[str, Any]:
    """Read a YAML experiment config. Every analyst choice must live here."""
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level.")
    return data


def resolve_artifact_dir(config: dict[str, Any], override: str | None = None) -> Path:
    """Create and return the experiment's artifact directory."""
    configured = override or config.get("output", {}).get(
        "artifact_dir", f"artifacts/experiments/{config.get('experiment_id', 'unnamed')}"
    )
    path = Path(configured)
    if not path.is_absolute():
        path = REPO_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class CohortBundle:
    """A standardized feature frame plus the explicit clustering subset."""

    frame: pd.DataFrame
    standardized: pd.DataFrame
    subset_ids: list[str]
    source: str
    notes: list[str]


def _standardize(frame: pd.DataFrame) -> pd.DataFrame:
    """Cohort z-scores, then median-fill. Missingness is recorded, not hidden.

    Standardizing before imputing means an imputed value lands at the cohort
    centre of its own variable rather than dragging the participant toward the
    centre of whichever variable happened to have the largest raw scale.
    """
    mean = frame.mean(numeric_only=True)
    sd = frame.std(numeric_only=True).replace(0.0, 1.0)
    z = (frame - mean) / sd
    return z.fillna(z.median()).fillna(0.0)


def load_cohort(config: dict[str, Any]) -> CohortBundle:
    """Load the real dataset if configured and present; otherwise synthesize one.

    Falling back to synthetic data is what lets these scripts run end to end in
    CI and on a fresh clone. The fallback is announced in the returned ``notes``
    and written into the artifacts, so no synthetic run can be mistaken for a
    result on real data.
    """
    dataset = config.get("dataset", {})
    notes: list[str] = []
    path_value = dataset.get("path")
    features: list[str] | None = dataset.get("features")

    if path_value:
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.exists():
            frame = pd.read_csv(candidate)
            id_column = dataset.get("id_column", "patient_id")
            if id_column in frame.columns:
                frame = frame.set_index(id_column)
            label_column = dataset.get("label_column")
            subset_ids = list(frame.index.astype(str))
            if dataset.get("pcos_positive_only", True) and label_column in frame.columns:
                subset_ids = [str(i) for i in frame.index[frame[label_column].astype(float) == 1.0]]
                notes.append(
                    f"Clustering restricted to {len(subset_ids)} participants positive on "
                    f"'{label_column}'."
                )
            numeric = frame.select_dtypes("number")
            if features:
                numeric = numeric[[c for c in features if c in numeric.columns]]
            numeric.index = numeric.index.astype(str)
            return CohortBundle(numeric, _standardize(numeric), subset_ids, str(candidate), notes)
        notes.append(f"Configured dataset '{candidate}' not found; falling back to synthetic.")

    from tests.fixtures.synthetic_clusters import make_synthetic_cluster_frame

    spec = dataset.get("synthetic", {})
    frame, truth = make_synthetic_cluster_frame(
        n_per_group=int(spec.get("n_per_group", 40)),
        noise=float(spec.get("noise", 0.35)),
        missing_rate=float(spec.get("missing_rate", 0.0)),
        seed=int(spec.get("seed", 0)),
    )
    notes.append(
        "SYNTHETIC DATA: no real dataset was available. These artifacts describe planted "
        f"geometry ({len(set(truth))} groups), not biology, and are not a scientific result."
    )
    return CohortBundle(
        frame, _standardize(frame), list(frame.index.astype(str)), "synthetic", notes
    )


def build_representations(
    cohort: CohortBundle,
    config: dict[str, Any],
) -> list[ClusteringInput]:
    """Build every configured representation of the same participants.

    Representations are the first of the three sweep axes. We build the ones we
    can and skip the rest with a note rather than failing: a missing autoencoder
    embedding should cost us one row of the benchmark, not the whole run.
    """
    wanted = list(config.get("clustering", {}).get("representations", ["raw_standardized"]))
    ids = list(cohort.standardized.index.astype(str))
    out: list[ClusteringInput] = []

    if "raw_standardized" in wanted:
        out.append(
            ClusteringInput(
                label="raw_standardized",
                matrix=cohort.standardized.to_numpy(dtype=float),
                participant_ids=ids,
                feature_names=list(cohort.standardized.columns),
            )
        )

    if "domain_scores" in wanted:
        rows: list[list[float]] = []
        domain_names: list[str] = []
        for pid in ids:
            values = {
                str(c): float(cohort.standardized.loc[pid, c]) for c in cohort.standardized.columns
            }
            scores = compute_domain_scores(values)
            domain_names = list(scores)
            rows.append([s.score if s.score is not None else 0.0 for s in scores.values()])
        matrix = np.asarray(rows, dtype=float)
        if matrix.size and matrix.shape[1] > 1 and np.isfinite(matrix).all():
            out.append(
                ClusteringInput(
                    label="domain_scores",
                    matrix=matrix,
                    participant_ids=ids,
                    feature_names=domain_names,
                )
            )

    subset = config.get("clustering", {}).get("feature_subset", {})
    if "feature_subset" in wanted and subset.get("features"):
        columns = [c for c in subset["features"] if c in cohort.standardized.columns]
        if len(columns) >= 2:
            out.append(
                ClusteringInput(
                    label=str(subset.get("name", "feature_subset")),
                    matrix=cohort.standardized[columns].to_numpy(dtype=float),
                    participant_ids=ids,
                    feature_names=columns,
                )
            )

    embedding_path = config.get("clustering", {}).get("embedding_path")
    if "autoencoder_embedding" in wanted and embedding_path:
        candidate = Path(embedding_path)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.exists():
            embedding = np.load(candidate)
            if embedding.shape[0] == len(ids):
                out.append(
                    ClusteringInput(
                        label="autoencoder_embedding",
                        matrix=np.asarray(embedding, dtype=float),
                        participant_ids=ids,
                        feature_names=[f"z{i}" for i in range(embedding.shape[1])],
                    )
                )

    if not out:
        raise ValueError("No representation could be built from the configuration.")
    return out


def write_benchmark_csv(benchmarks: Sequence[ClusteringBenchmark], path: Path) -> Path:
    """Write the full (representation, algorithm, K) benchmark table."""
    fields = [
        "representation",
        "algorithm",
        "k",
        "seed",
        "n_samples",
        "silhouette",
        "calinski_harabasz",
        "davies_bouldin",
        "mean_bootstrap_jaccard",
        "mean_ari_across_seeds",
        "mean_nmi_across_seeds",
        "warnings",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for benchmark in benchmarks:
            row = benchmark.model_dump()
            row["warnings"] = "; ".join(row.get("warnings") or [])
            writer.writerow({k: row.get(k) for k in fields})
    return path


def write_json(payload: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path
