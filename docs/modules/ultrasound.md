# Ultrasound pipeline (Step 8)

Produces semantic ovary and follicle measurements. The target is **not** a PCOS
diagnosis — it is segmentation, counting, morphology, and knowing when not to
measure.

## Pipeline

```text
DICOM or image → de-identification → metadata extraction →
image-quality assessment → ovary localization → ovary segmentation →
follicle segmentation → follicle instance separation → morphology measurement →
large/uncertain structure flagging → structured imaging evidence → token
```

Input priority: 3D DICOM volume › 2D cine loop › multiple stills › single still
(limited) › the ultrasound report, handled separately as a document.

## Segmentation

A 3D U-Net (nnU-Net-like) with semantic classes `0 = background`, `1 = ovary`,
`2 = follicle`. Semantic meaning comes from ovarian labels, not from generic
segmentation. A torch-free threshold segmenter provides the fallback path so the
pipeline and its tests run without torch.

The loss includes an "outside" term that penalizes follicle predictions outside
the ovary:

$$ \mathcal{L}_{outside} = \sum_i P_i(\text{follicle})\left[1-P_i(\text{ovary})\right] $$

alongside ovary and follicle Dice, a boundary term, and the quality-head loss.

## The quality gate

Predicts ovary visible · whole ovary visible · laterality available · pixel
spacing available · follicle counting feasible · ovarian volume feasible ·
overall quality score.

**If quality is insufficient, the module abstains from quantitative
measurement** — `measurement_feasible=False`, `None` measurements, reasons
attached. If pixel spacing is unknown, no physical measurement is emitted at all.
A follicle count from an image where half the ovary is out of plane is not a
low-confidence count; it is a different quantity.

`quality-gate unsafe acceptance rate` is a reported metric: how often the gate
let through an image it should have refused.

## Instances and morphology

Connected components → removal below a documented physical-size threshold →
watershed separation of touching follicles → physical sizing via spacing → 3D
tracking → count and size distribution.

Outputs: ovary dimensions, area, volume, follicle count, size distribution,
density, left–right asymmetry, mask confidence, quality score.

**Large or uncertain cystic structures** above a documented diameter threshold
are flagged, excluded from the small-follicle count, shown in the overlay, and
sent for review. They are never assigned a pathological diagnosis — this version
does not attempt ovarian-mass characterization.

## Model-generated until reviewed

`OvarianMorphologyOutput.clinician_review_status` starts at `model_generated`.
Only a clinician moves it to `clinician_confirmed`, and until then the exported
token carries the warning "Clinician confirmation pending".

## Metrics

Ovary Dice · follicle Dice · follicle instance precision/recall · follicle-count
MAE · ovarian-volume absolute error · false follicle voxels outside the ovary ·
quality-gate sensitivity · quality-gate unsafe acceptance rate.
