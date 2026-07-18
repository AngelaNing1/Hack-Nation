#!/usr/bin/env python
"""Tiny runnable demo of the ovarian ultrasound pipeline.

Encodes one synthetic phantom with known ground truth, prints the measurements
next to the truth, then demonstrates the two abstention paths that matter:
a study with no visible ovary, and a perfectly good study whose physical spacing
is unknown. Writes ``ultrasound_token.json`` next to this file.

Run:  python examples/ultrasound_example/run_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.ultrasound.loader import load_study  # noqa: E402
from models.ultrasound.encoder import UltrasoundEncoder  # noqa: E402
from tests.fixtures.synthetic_ultrasound import (  # noqa: E402
    make_phantom,
    make_poor_quality_volume,
)

HERE = Path(__file__).resolve().parent


def main() -> int:
    """Run the demo."""
    encoder = UltrasoundEncoder(segmenter_kind="auto")

    print("=" * 72)
    print("1. A measurable study (synthetic phantom with known ground truth)")
    print("=" * 72)
    phantom = make_phantom(seed=0)
    _, metadata = load_study(
        phantom.volume,
        patient_id="DEMO001",
        study_id="DEMO001_LEFT",
        spacing_mm=phantom.spacing,
        laterality="left",
        route="transvaginal",
        source_dataset="synthetic_phantom",
    )
    encoding = encoder.encode(phantom.volume, metadata, observed_at="2024-01-15")
    morphology = encoding.morphology

    print(f"  spacing (mm)          : {metadata.spacing_mm}")
    print(f"  quality score         : {morphology.quality_score:.3f}")
    print(f"  measurement feasible  : {morphology.measurement_feasible}")
    print(
        f"  ovary volume (ml)     : {morphology.ovary_volume_ml:.2f}"
        f"   [true {phantom.true_ovary_volume_ml:.2f}]"
    )
    print(f"  follicle count        : {morphology.follicle_count}      [true {phantom.true_count}]")
    print(
        f"  follicle diameters mm : {[round(d, 1) for d in morphology.follicle_diameters_mm]}"
        f"\n                          [true {phantom.true_diameters_mm}]"
    )
    print(f"  review status         : {morphology.clinician_review_status}")
    print(f"  follicle voxels outside ovary: {morphology.false_follicle_voxels_outside_ovary}")

    token_path = encoding.token.write_json(HERE / "ultrasound_token.json")
    print(f"\n  token written to      : {token_path}")
    print("  token warnings        :")
    for warning in encoding.token.warnings:
        print(f"    - {warning}")

    print()
    print("=" * 72)
    print("2. Abstention: no ovary visible")
    print("=" * 72)
    noise = make_poor_quality_volume(seed=7)
    _, noise_metadata = load_study(
        noise,
        patient_id="DEMO002",
        study_id="DEMO002_NOISE",
        spacing_mm=(1.0, 0.6, 0.6),
        laterality="left",
        route="transvaginal",
    )
    noise_encoding = encoder.encode(noise, noise_metadata)
    print(f"  measurement feasible  : {noise_encoding.morphology.measurement_feasible}")
    print(f"  ovary volume          : {noise_encoding.morphology.ovary_volume_ml}")
    print(f"  follicle count        : {noise_encoding.morphology.follicle_count}")
    for reason in noise_encoding.quality.reasons:
        print(f"    - {reason}")

    print()
    print("=" * 72)
    print("3. Abstention: good image, but physical spacing is unknown")
    print("=" * 72)
    _, unspaced = load_study(
        phantom.volume, patient_id="DEMO003", study_id="DEMO003_NOSPACING", spacing_mm=None
    )
    unspaced_encoding = encoder.encode(phantom.volume, unspaced)
    print(f"  measurement feasible  : {unspaced_encoding.morphology.measurement_feasible}")
    print(f"  ovary volume          : {unspaced_encoding.morphology.ovary_volume_ml}")
    print("  a follicle diameter in pixels is not a clinical measurement, so nothing is emitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
