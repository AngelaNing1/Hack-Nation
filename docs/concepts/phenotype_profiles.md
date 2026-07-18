# Phenotype profiles

PRISM does not assign a subtype. It reports how a participant's evidence is
organized across domains, which discovered profile that pattern most
**resembles**, how confident and how stable that resemblance is, and when it
should decline to answer. Language rules are fixed by
[ADR-003](../decisions/ADR-003-subtype-language.md).

## Two representations, deliberately both

**A. Transparent composite scores.** Deterministic, auditable, driven entirely
by `registry/phenotype_domains.yaml`:

$$ s_d = \frac{\sum_{j \in d} w_j z_j m_j}{\sum_{j \in d} w_j m_j} $$

where \(z_j\) is the standardized feature, \(w_j\) a documented weight, and
\(m_j\) an availability indicator. Every score reports its coverage.

**B. Learned tabular embedding.** A masked autoencoder over clinical features +
missingness mask + variable identities, trained by masking 10–30% of observed
variables and reconstructing them. Exported as a latent embedding, and required
to beat mean imputation on withheld values — otherwise it is adding nothing.

Both are exported. The composite score is what a clinician can argue with; the
embedding is what clusters well. Neither is asked to be the other.

## The four domains

| Domain | Captures | Note |
|:--|:--|:--|
| Reproductive / ovulatory | Cycle pattern, LH/FSH, progesterone | — |
| Metabolic | Adiposity, glycemia, lipids, blood pressure | — |
| Androgenic | Testosterone, DHEAS, SHBG, hirsutism, acne | see below |
| Ovarian / LH–AMH | AMH, follicle count, ovarian volume | Imaging-dependent |

**The androgenic caveat is not decoration.** When no androgen assay is observed
and the score rests on hirsutism, acne and alopecia alone, the export is
qualified as **androgenic-symptom evidence**. Symptoms are not biochemical
hyperandrogenism — the correlation is real but far from identity, and it varies
by ancestry in ways that make the substitution actively unfair. The qualifier is
set from the registry and carried in `DomainScore.evidence_qualifier`.

## Coverage, and refusing to score

```json
{
  "domain": "metabolic",
  "score": 0.72,
  "coverage": 0.60,
  "observed_features": ["BMI", "fasting_glucose", "blood_pressure"],
  "missing_features": ["fasting_insulin", "lipids"]
}
```

Below the domain's `min_coverage_to_report`, `score` is `None`. A score computed
from one of nine features is not a weak score — it is a different quantity, and
reporting it as 0.72 invites it to be read as comparable to a well-covered one.

## Soft membership with an escape hatch

```json
{
  "phenotype_probabilities": {
    "cluster_1": 0.55,
    "cluster_2": 0.25,
    "cluster_3": 0.12,
    "indeterminate": 0.08
  }
}
```

`indeterminate` is assigned when the maximum probability is below threshold,
models disagree, bootstrap assignment is unstable, removing a single variable
flips the dominant cluster, the participant sits far from every cluster center,
or too few defining variables were observed.

## Stability travels with the answer

```json
{
  "dominant_profile": "metabolic_leaning",
  "dominant_probability": 0.61,
  "stability_score": 0.73,
  "subtype_flip_rate": 0.21,
  "highest_fragility_feature": "fasting_insulin",
  "abstain": false,
  "warnings": ["SHBG unavailable", "Only one glucose measurement available"]
}
```

Read that as: *the profile resembles a metabolic-leaning pattern, but one in five
resamples assigns it elsewhere, and fasting insulin is doing most of the work.*
That is a more useful sentence than a subtype label, and it is the one the data
supports.
