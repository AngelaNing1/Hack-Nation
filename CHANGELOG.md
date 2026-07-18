# Changelog

All notable changes are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/) and semantic versioning.

Schema changes are always listed explicitly — a schema is never changed
silently (see `registry/schema_versions.yaml`).

## [Unreleased]

### Changed — BREAKING: ultrasound is now 2D-primary

The ultrasound module was built 3D-first. That did not match clinical reality:
routine PCOS assessment uses **2D transvaginal imaging**, and the 2023
international guideline is written around follicle number per ovary, follicle
number per cross-section, and ovarian volume — it does not require a 3D
acquisition. USOVA3D was driving the design purely because it is one of the few
public datasets with expert ovary *and* per-follicle labels.

- **Input priority inverted.** 2D cine loop / multi-frame is now the primary
  pathway; a single 2D frame is a limited-output fallback; a 3D volume is an
  optional enhanced mode.
- **`schemas.imaging` 1.0.0 → 2.0.0 (not backward compatible).** The single
  `follicle_count` field is replaced by three non-interchangeable quantities —
  `follicle_number_per_section`, `estimated_follicle_number_per_ovary`, and
  `follicle_number_per_ovary` — plus `follicle_count_method`. Added
  `acquisition_mode`, `ovary_area_mm2`, `frames_analyzed`, `tracking_coverage`,
  and a `reportable_follicle_count` property that returns the count *with* its
  method.

  **Why it had to break:** one integer let a single cross-section silently
  claim a whole-ovary count. A `model_validator` now refuses any measurement the
  acquisition cannot support — a single frame cannot report a per-ovary count or
  an ovarian volume, and 2D frames cannot report a *true* per-ovary count.
- **Variable registry 1.0.0 → 1.1.0.** Added `follicle_number_per_section`,
  `estimated_follicle_number_per_ovary`, and `ovary_area_mm2`.
- **Dataset registry.** USOVA3D is reclassified as a pretraining/label resource
  and optional 3D benchmark, with a new prohibited claim of
  `independent_2d_evaluation` — a 2D test set carved from the same volumes used
  for pretraining is not independent. Added an `ovarian_ultrasound_2d`
  placeholder for the primary 2D pathway, which prohibits
  `follicle_instance_segmentation` because class-level labels cannot supervise
  per-follicle masks.
- **Modules.** `models/ultrasound/` reorganized around a 2D-primary layout
  (`qc_2d`, `ovary_detector_2d`, `segmenter_2d`, `cine_tracking`,
  `morphology_2d`) with the prior 3D work preserved as `segmenter_3d` /
  `morphology_3d`. Cine tracking matches follicles across adjacent frames so a
  follicle spanning frames 3–7 counts once, not five times.

### Does this alter a scientific claim?

Yes, and in the restrictive direction. The module previously could emit a
per-ovary follicle count from acquisitions incapable of supporting one. It now
reports the weaker quantity the data actually supports, labelled with the method
that produced it.

## [0.1.0] - 2026-07-18

Initial research preview covering Steps 1–9.

### Added

- **Schemas (1.0.0)** — `HormonalHealthEvent`, `ModalityToken`,
  `PatientSnapshot`, `EvidenceConflict`, `PhenotypeProfile`, `StabilityReport`,
  `OvarianMorphologyOutput`, `ParticipantDay`, `TemporalStateOutput`,
  `ExperimentResult`, `SplitManifest`.
- **Registries** — 6 datasets with allowed uses and prohibited claims, 65
  canonical variables, unit-conversion tables with per-factor tests, 4 phenotype
  domains, and a schema-version ledger.
- **Event store** — append-only storage, conflict detection that preserves both
  sides, provenance tracing, and parameterized model-ready snapshots.
- **Ingestion** — adapters for the public PCOS tabular cohort, NHANES, mcPHASES,
  speech, documents, and ultrasound.
- **Step 3** — static baselines (logistic regression, random forest, gradient
  boosting, MLP, majority-class and rule baselines) with repeated stratified
  patient-level cross-validation and full calibration reporting.
- **Step 4** — transparent coverage-aware phenotype-domain scores and a masked
  tabular autoencoder embedding.
- **Step 5** — clustering benchmark across representations, algorithms and
  K ∈ {2..6}; bootstrap, ablation and perturbation stability; indeterminate and
  abstention logic; hedged prototype mapping with a banned-phrase guard.
- **Step 6** — speech pipeline with offline scripted transcription, rule-based
  extraction with negation/temporality/uncertainty handling, evidence-span
  linking, a confirmation state machine, and a synthetic scripted corpus.
- **Step 7** — document pipeline with table extraction, registry-driven unit
  normalization preserving original and canonical values, reference-range
  parsing, page grounding, and a synthetic report corpus.
- **Step 8** — ultrasound pipeline with de-identification checks, quality gating
  with abstention, ovary/follicle segmentation, instance extraction, and
  morphology measurement in physical units.
- **Step 9** — GRU current-state model with hormone, cycle-phase, symptom and
  masked-reconstruction heads, grouped participant-level splits, and
  missing-modality ablations.
- **Repository** — CI (including a no-optional-dependencies job and a
  no-clinical-data guard), data-contract validation, model smoke tests, MkDocs
  documentation, ADRs 001–004, and issue/PR templates.

### Security

- `.gitignore`, a pre-commit hook, and a CI job independently block raw clinical
  data, imaging, audio and credentials from being committed.

### Known limitations

- No cross-modal fusion model. The datasets describe different people; see
  ADR-002.
- Speech and document metrics come from synthetic corpora and support no claim
  about real-world performance.
- No external validation of discovered phenotype profiles.
- Nothing in this release is validated for clinical use.
