# Data contracts

Every module boundary in PRISM is typed. A schema change is a scientific change:
bump the version in `registry/schema_versions.yaml`, add a CHANGELOG entry, and
the `data-contracts` workflow will block the PR if either is missing.

## The universal event

`HormonalHealthEvent` is the unit of evidence — see
[provenance](concepts/provenance.md) for the full field list. Its validation
rules are the ones worth knowing:

| Rule | Why |
|:--|:--|
| `observed` requires a value; non-observed forbids one | No half-present cells |
| Laboratory events require a unit | A unitless lab value is uninterpretable |
| `document_extracted` / `model_measured` / `model_inferred` cannot be `confirmed` without `reviewed_by` | Models do not confirm themselves |
| Speech / document / ultrasound-report events require an evidence span or source location | Confirmation without evidence is rubber-stamping |
| `raw_value` and `raw_unit` are preserved | Normalization is a model, and models are wrong |

## The token envelope

All five encoders export the same `ModalityToken` shape:

```json
{
  "patient_id": "P001",
  "modality": "static_clinical",
  "embedding": [],
  "structured_features": {},
  "quality_score": 0.0,
  "confidence_score": 0.0,
  "observed_at": null,
  "model_version": "0.1.0",
  "source_dataset": null,
  "provenance_ids": [],
  "missing_fields": [],
  "warnings": []
}
```

Shared envelope, separate lives — see
[ADR-002](decisions/ADR-002-no-fake-pairing.md).

## Canonical variables

<!-- AUTO-GENERATED: VARIABLE-REGISTRY START -->
Total canonical variables: **68**

| Domain | Count | Variables |
|:--|--:|:--|
| androgenic | 4 | `dheas`, `free_testosterone`, `shbg`, `total_testosterone` |
| androgenic_symptom | 6 | `acne`, `androgenic_alopecia`, `ferriman_gallwey_score`, `hair_growth_face`, `hirsutism`, `skin_darkening` |
| anthropometric | 5 | `bmi`, `height`, `hip_circumference`, `waist_circumference`, `weight` |
| cgm | 3 | `cgm_glucose_sd`, `cgm_mean_glucose`, `cgm_time_in_range` |
| demographic | 1 | `age` |
| history | 2 | `family_history_diabetes`, `family_history_pcos` |
| label | 1 | `pcos_binary` |
| longitudinal | 5 | `cycle_phase`, `e3g`, `menstrual_flow`, `pdg`, `urinary_lh` |
| medication | 1 | `medication_current` |
| metabolic | 16 | `bmi`, `cgm_glucose_sd`, `cgm_mean_glucose`, `cgm_time_in_range`, `diastolic_blood_pressure`, `fasting_glucose`, `fasting_insulin`, `hdl_cholesterol`, `hip_circumference`, `homa_ir`, `ldl_cholesterol`, `systolic_blood_pressure`, `triglycerides`, `waist_circumference`, `waist_hip_ratio`, `weight_gain` |
| ovarian | 4 | `anti_mullerian_hormone`, `follicle_stimulating_hormone`, `lh_fsh_ratio`, `luteinizing_hormone` |
| ovarian_morphology | 9 | `estimated_follicle_number_per_ovary`, `follicle_count_left`, `follicle_count_right`, `follicle_number_per_ovary`, `follicle_number_per_section`, `large_or_uncertain_cystic_structure`, `ovarian_morphology_evidence`, `ovary_area_mm2`, `ovary_volume_ml` |
| reproductive | 17 | `amenorrhea`, `cycle_irregularity`, `cycle_length`, `cycle_phase`, `cycle_regularity`, `e3g`, `estradiol`, `follicle_stimulating_hormone`, `infertility_history`, `lh_fsh_ratio`, `luteinizing_hormone`, `menstrual_flow`, `menstrual_frequency_per_year`, `pdg`, `pregnancy_history_count`, `progesterone`, `urinary_lh` |
| symptom | 4 | `fatigue`, `mood_change`, `pelvic_pain`, `weight_gain` |
| wearable | 5 | `activity_steps`, `hrv_rmssd`, `resting_heart_rate`, `skin_temperature`, `sleep_duration_hours` |
<!-- AUTO-GENERATED: VARIABLE-REGISTRY END -->

## Phenotype domains

<!-- AUTO-GENERATED: PHENOTYPE-DOMAINS START -->
| Domain | Features | Min coverage to report | Qualifier |
|:--|--:|--:|:--|
| **reproductive** — Reproductive / ovulatory | 9 | 0.34 | — |
| **metabolic** — Metabolic | 11 | 0.34 | — |
| **androgenic** — Androgenic | 10 | 0.25 | androgenic-symptom evidence |
| **ovarian** — Ovarian / LH-AMH | 7 | 0.25 | — |
<!-- AUTO-GENERATED: PHENOTYPE-DOMAINS END -->

## Units

`registry/units.yaml` holds every conversion factor. Molar conversions are
analyte-specific (they depend on molecular weight) and are therefore never
applied generically. `convert_to_canonical()` **raises** on an unknown unit
rather than guessing — a wrong silent conversion is far more damaging than a
loud failure. Every factor has a unit test.
