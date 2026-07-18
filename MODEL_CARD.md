# PRISM model card

**Human-reviewed.** This file is never overwritten by automation. Generated,
per-experiment cards live in `artifacts/model_cards/`.

**Version:** 0.1.0 · **Date:** 2026-07-18 · **Status:** Research preview

## Non-diagnostic statement

> PRISM is a research artifact. It does not diagnose any condition, does not
> provide medical advice, and is not validated for clinical use.

## What PRISM is

A collection of **seven independently trained modules** sharing a common
evidence substrate and output envelope. It is not one model, and there is no
combined system-level performance number, because such a number would require
patients who have all five modalities — and no such dataset is in use here.

| Module | Trained on | Produces |
|:--|:--|:--|
| Static baselines | Public PCOS tabular cohort | Calibrated binary probability |
| Phenotype domains | Public PCOS tabular cohort | Coverage-aware domain scores + embedding |
| Subtype/stability | Public PCOS tabular cohort (label-positive subset) | Soft profiles + stability + abstention |
| Speech | Synthetic scripted corpus | Structured symptom events |
| Documents | Synthetic report corpus | Grounded lab events |
| Ultrasound | USOVA3D | Segmentation + morphology |
| Temporal state | mcPHASES | Current-state representation |

## Intended use

Research. Methods development for multimodal hormonal-health modeling; analysis
of what evidence is present, absent, or contradictory; investigation of how
stable data-driven phenotype groupings actually are.

## Out-of-scope uses

Every clinical use, without exception. Specifically:

- Diagnosing PCOS or any other condition
- Screening, triage, or risk stratification of real patients
- Guiding, ordering, or withholding any test or treatment
- Fertility counselling or family planning decisions
- Insurance, employment, or eligibility determination
- Any deployment where a person is affected by the output

Also out of scope scientifically: pooling tokens from different datasets into a
fusion model, or reporting smoke-test metrics as performance.

## Limitations

**Data.** The static cohort is single-site, cross-sectional, and modest in size,
with a dataset-provided label that was not re-adjudicated. mcPHASES is small and
densely sampled — excellent for state modeling, not representative of a general
population. Speech and document metrics come from **synthetic** corpora and
support no real-world claim. Ultrasound ground truth is annotator-derived.

**Population.** Demographic coverage of every dataset here is limited and not
representative. Performance in populations under-represented in training is
unknown, and the Ferriman–Gallwey-based hirsutism features carry known ancestry
dependence. Subgroup metrics are reported where sample size permits; where it
does not, that is stated rather than glossed.

**Method.** Discovered clusters have no external validation. Stability metrics
describe internal reproducibility, not clinical validity. The androgenic domain,
when scored without androgen assays, measures **symptoms** and is labelled as
such.

**Structural.** No cross-modal fusion. No prospective evaluation. No clinical
validation of any kind.

## Ethical considerations

PCOS is already routinely under- and mis-diagnosed, with long delays to
diagnosis. That creates a specific hazard here: a tool that appears to offer
resolution can be trusted past its evidence, by patients and clinicians alike.
PRISM's design responses are structural rather than advisory — abstention as a
first-class output, coverage reported with every score, hedged language enforced
in code, and a hard gate keeping unconfirmed model output out of the modeling
path.

Symptom-based androgenic scoring is called out explicitly because the
substitution of clinical for biochemical hyperandrogenism is both common and
unequal in its errors across ancestries.

## Reproducibility

Every result is reproducible from a git commit, a config file, a seed, a dataset
version, a split manifest, an environment lockfile, a checkpoint, and a metrics
artifact. Preprocessing is fitted inside the training fold; longitudinal splits
are grouped by participant. Both have regression tests.

## Contact

Report issues via the repository's issue templates. Report security or data
exposure privately — see `SECURITY.md`.
