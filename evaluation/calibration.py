"""Calibration: is a predicted 0.7 actually 70%?

Discrimination and calibration are independent failures. A model can rank
patients perfectly (AUROC 0.9) while systematically over-stating risk, which is
exactly the failure that makes a research score dangerous if it is ever read as
a probability of having a condition.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression

from schemas.model_output import CalibrationMetrics

_EPS = 1e-12


def _clean(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float)
    keep = np.isfinite(y_true_arr) & np.isfinite(y_prob_arr)
    return y_true_arr[keep], np.clip(y_prob_arr[keep], 0.0, 1.0)


def brier_score(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
) -> float:
    """Mean squared error of the predicted probabilities."""
    y_true_arr, y_prob_arr = _clean(y_true, y_prob)
    if y_true_arr.size == 0:
        return float("nan")
    return float(np.mean((y_prob_arr - y_true_arr) ** 2))


def expected_calibration_error(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    *,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> float:
    """Binned |confidence - accuracy|, weighted by bin population."""
    y_true_arr, y_prob_arr = _clean(y_true, y_prob)
    if y_true_arr.size == 0:
        return float("nan")

    edges = _bin_edges(y_prob_arr, n_bins=n_bins, strategy=strategy)
    bins = np.clip(np.digitize(y_prob_arr, edges[1:-1], right=False), 0, len(edges) - 2)

    error, total = 0.0, float(y_true_arr.size)
    for b in range(len(edges) - 1):
        mask = bins == b
        if not mask.any():
            continue
        error += mask.sum() / total * abs(y_prob_arr[mask].mean() - y_true_arr[mask].mean())
    return float(error)


def _bin_edges(y_prob: np.ndarray, *, n_bins: int, strategy: str) -> np.ndarray:
    if strategy == "quantile":
        quantiles = np.linspace(0, 1, n_bins + 1)
        edges = np.unique(np.quantile(y_prob, quantiles))
        if edges.size < 2:
            return np.array([0.0, 1.0])
        return edges
    if strategy != "uniform":
        raise ValueError(f"Unknown binning strategy '{strategy}'.")
    return np.linspace(0.0, 1.0, n_bins + 1)


def calibration_curve_points(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    *,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> list[dict[str, float]]:
    """Per-bin (mean predicted, observed rate, count) — the reliability diagram data."""
    y_true_arr, y_prob_arr = _clean(y_true, y_prob)
    if y_true_arr.size == 0:
        return []

    edges = _bin_edges(y_prob_arr, n_bins=n_bins, strategy=strategy)
    bins = np.clip(np.digitize(y_prob_arr, edges[1:-1], right=False), 0, len(edges) - 2)

    points: list[dict[str, float]] = []
    for b in range(len(edges) - 1):
        mask = bins == b
        if not mask.any():
            continue
        points.append(
            {
                "bin": float(b),
                "bin_lower": float(edges[b]),
                "bin_upper": float(edges[b + 1]),
                "mean_predicted": float(y_prob_arr[mask].mean()),
                "observed_rate": float(y_true_arr[mask].mean()),
                "count": float(mask.sum()),
            }
        )
    return points


def calibration_slope_intercept(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
) -> tuple[float, float]:
    """Slope and intercept of a logistic recalibration of ``logit(p)``.

    Perfect calibration is slope 1, intercept 0. Slope < 1 means predictions are
    too extreme; a negative intercept means systematic over-prediction.
    """
    y_true_arr, y_prob_arr = _clean(y_true, y_prob)
    if y_true_arr.size < 3 or len(np.unique(y_true_arr)) < 2:
        return float("nan"), float("nan")

    logits = _logit(y_prob_arr)
    if not np.isfinite(logits).all() or np.std(logits) < _EPS:
        return float("nan"), float("nan")

    # Effectively unpenalized (C -> inf): any regularization would shrink the
    # slope and make a miscalibrated model look better calibrated than it is.
    model = LogisticRegression(C=1e12, solver="lbfgs", max_iter=1000)
    model.fit(logits.reshape(-1, 1), y_true_arr.astype(int))
    return float(model.coef_[0][0]), float(model.intercept_[0])


def _logit(p: np.ndarray, *, eps: float = 1e-6) -> np.ndarray:
    clipped = np.clip(p, eps, 1 - eps)
    return np.log(clipped / (1 - clipped))


def calibration_report(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    *,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> CalibrationMetrics:
    """The full calibration block written into ``metrics.json``."""
    slope, intercept = calibration_slope_intercept(y_true, y_prob)
    return CalibrationMetrics(
        brier=brier_score(y_true, y_prob),
        ece=expected_calibration_error(y_true, y_prob, n_bins=n_bins, strategy=strategy),
        calibration_slope=None if not np.isfinite(slope) else slope,
        calibration_intercept=None if not np.isfinite(intercept) else intercept,
        n_bins=n_bins,
    )


def calibration_metrics_dict(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    *,
    n_bins: int = 10,
) -> dict[str, float]:
    """Flat calibration metrics, for merging into a fold's metric dict."""
    slope, intercept = calibration_slope_intercept(y_true, y_prob)
    return {
        "brier": brier_score(y_true, y_prob),
        "ece": expected_calibration_error(y_true, y_prob, n_bins=n_bins),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
    }


__all__ = [
    "brier_score",
    "calibration_curve_points",
    "calibration_metrics_dict",
    "calibration_report",
    "calibration_slope_intercept",
    "expected_calibration_error",
]
