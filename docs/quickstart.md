# Quick start

## Install

```bash
git clone https://github.com/AngelaNing1/Hack-Nation.git
cd Hack-Nation
make install
```

`make install` prefers [uv](https://github.com/astral-sh/uv) and falls back to
`venv` + `pip install -e ".[dev]"`.

Optional extras — `torch`, `xgboost`, `imaging` (pydicom, scikit-image),
`speech`, `documents` — are **not required**. Every module has a documented
fallback, and CI runs the entire suite without them.

## Verify

```bash
make validate    # registry cross-references and data contracts
make test        # unit + contract tests
make smoke       # tiny synthetic end-to-end model runs
```

All three run on committed synthetic fixtures. No clinical dataset is needed.

## Run an experiment

```bash
python scripts/train_static_baselines.py \
  --config configs/experiments/exp_static_baselines.yaml
```

This writes a complete artifact directory under
`artifacts/experiments/<experiment_id>/` containing the resolved config, the
environment, the git commit, the data/split/feature manifests, the training log,
metrics, predictions, a checkpoint, figures, and a model card.

To reproduce someone else's result you need their commit and their config.
Nothing else.

## Point it at real data

1. Obtain the dataset under its own access terms — see the
   [dataset registry](datasets/index.md).
2. Store it **outside** the repository tree.
3. Copy `.env.example` to `.env` and set `PRISM_DATA_ROOT`.
4. Set the dataset path in the relevant `configs/data/*.yaml`.
5. Run the prepare script, then the training script:

```bash
python scripts/prepare_pcos_tabular.py --config configs/data/pcos_tabular.yaml
python scripts/train_static_baselines.py --config configs/experiments/exp_static_baselines.yaml
```

The adapter validates the source, records checksums, maps source columns to
canonical variables, normalizes units, and writes a processing manifest before
any model sees a number.

## What you get at the end of Step 9

Five independently exported tokens under one shared envelope:

```text
static_token.json          symptom_token.json      document_token.json
ultrasound_token.json      temporal_state_token.json
```

plus `phenotype_profile.json` and `stability_report.json`.

They share an envelope so they are *comparable*. They are not concatenated into
a fusion model, because they describe different people.
