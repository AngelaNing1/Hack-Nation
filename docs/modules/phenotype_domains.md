# Phenotype domains (Step 4)

Moves beyond a single binary prediction to continuous, domain-level
representations. Concepts and the androgenic caveat are in
[phenotype profiles](../concepts/phenotype_profiles.md); this page is the
implementation.

## A. Transparent composite scores

Deterministic, registry-driven, auditable:

$$ s_d = \frac{\sum_{j \in d} w_j z_j m_j}{\sum_{j \in d} w_j m_j} $$

Weights, directions and evidence classes live in
`registry/phenotype_domains.yaml` — changing the scoring means editing a
reviewed config file, not hunting for a constant in Python.

Every output reports coverage:

```json
{
  "domain": "metabolic",
  "score": 0.72,
  "coverage": 0.60,
  "observed_features": ["BMI", "fasting_glucose", "blood_pressure"],
  "missing_features": ["fasting_insulin", "lipids"]
}
```

Below `min_coverage_to_report`, `score` is `None`. Refusing to score is a valid
output.

## B. Learned tabular representation

A masked/denoising autoencoder over clinical features + missingness mask +
variable identities. 10–30% of observed variables are randomly masked and
reconstructed:

$$ \mathcal{L}_{MAE} = \sum_{j \in M_c} \alpha_j (x_j-\hat{x}_j)^2 + \sum_{j \in M_k} \beta_j \operatorname{CE}(x_j,\hat{x}_j) $$

The acceptance bar is explicit: the embedding must reconstruct withheld
variables **better than mean imputation**. If it does not, it is adding
parameters and nothing else.

## Exported token

```json
{
  "modality": "static_clinical",
  "embedding": [0.12, -0.31, 0.44],
  "structured_features": {
    "metabolic_score": 0.72, "reproductive_score": 0.81,
    "androgenic_score": 0.54, "ovarian_score": 0.62
  },
  "quality_score": 0.78,
  "confidence_score": 0.69,
  "missing_fields": ["fasting_insulin", "SHBG"]
}
```

Scores and embeddings are exported **separately**. They answer different
questions and combining them would hide which one is doing the work.
