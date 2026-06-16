1# Stage 4 (Translational variant) — Relevance scoring for bench / translational science

> **Drop-in alternative to `02_scoring.md`** for bench and translational research
> (molecular biology, neuroscience, biomarker & pathway work, animal models,
> siRNA/CRISPR perturbation). Use this when your topic is mechanistic/preclinical
> rather than purely clinical-trial focused.
>
> Same I/O contract as `02_scoring.md`: the host AI reads `candidates.jsonl` and
> writes `scored_papers.jsonl`, one JSON object per line. Score from
> **title + abstract + MeSH only** — this is triage, not deep reading.

## What kept the same as `02_scoring.md`

The skeleton is field-agnostic and stays:

- 1–10 relevance scale (not yes/no).
- Four axes, averaged, weakest axis drags the score down.
- Subtopic assigned **only when score ≥ 5.0**; converge to 5–7 clusters.
- Distribution self-check (~20–40% high, ~40–60% mid, ~10–30% low).
- Same quality bar: specific fields, numbers in `key_findings`, no inflation.

## What changed for translational science

- **"Method" now includes the assay/measurement technology**, not just the
  manipulation (HPLC-MS, ELISA, IHC, qPCR, RNA-seq, flow, EEG, clinical scales).
- **Target / pathway** moves into the "what" axis.
- **Model system** becomes its own axis (the translational ladder).
- **Clinical application value** rewards maturity: a target/biomarker already in
  clinical use or in trials scores higher, even when the paper itself is preclinical.
- The single `preclinical` evidence bucket is split by **causal strength + model
  proximity**, and `causality` / `clinical_stage` are tracked as **separate tags**.

## What each scored record must contain

Copy every field from the candidate record, then add:

```json
{
  "score": 8.5,
  "subtopic": "BDNF-CREB signaling",
  "study_type": "animal",
  "model_tier": "rodent",
  "causality": "causal",
  "clinical_stage": "preclinical",
  "rationale": "conditional BDNF KO rescues spatial memory; same pathway + model as topic",
  "extraction": {
    "model_species": "C57BL/6 mouse (M+F)",
    "perturbation": "AAV-shRNA against Bdnf in hippocampus",
    "assay_readout": "Morris water maze + Western blot (pCREB)",
    "design": "KD vs scrambled, n=12/group",
    "key_findings": "pCREB down 40%, latency up 18s (p<0.01)",
    "direction_magnitude": "KD impairs memory; effect large",
    "limitations": "single sex pooled, acute timepoint only"
  }
}
```

`study_type`, `model_tier`, `causality`, `clinical_stage` are optional metadata —
fill them when the abstract makes them obvious. They are recorded in
`scored_papers.jsonl` and may be referenced in the triage table rationale even if
`build_outputs.py` only maps `score` + `study_type`/`evidence` into BibTeX keywords.

## The four scoring axes (score 1–10; weakest axis drags it down)

1. **Question / phenotype / target match** *(the "what")* — same disease,
   phenotype, or biological question, **and** molecular target/pathway
   (e.g. BDNF-CREB, amyloid, CCO/ATP, a named receptor)?
2. **Method + technology match** *(the "how")* — same experimental approach
   (siRNA/shRNA, CRISPR KO, overexpression, rescue, optogenetics) **and**
   measurement technology (HPLC-MS, ELISA, IHC/imaging, qPCR, RNA-seq, flow,
   EEG, clinical scales)?
3. **Model-system match** *(the "where")* — same rung of the translational
   ladder: in vitro / cell line / primary culture / rodent / NHP / human
   (observational) / human (RCT)?
4. **Clinical application value** *(how close to the clinic)* — is the
   target/biomarker/intervention already in clinical use or in trials?
   Clinically validated -> higher; exploratory animal/in-vitro-only -> lower.

## Scoring scale (1–10)

| Band | Meaning |
|---|---|
| 9.0–10.0 | Strong match on all four; clinically established target/biomarker |
| 7.0–8.9  | Same question + technique; minor model-system or clinical-stage gap |
| 5.0–6.9  | Same field, but question/technique/model clearly diverges |
| 3.0–4.9  | Only partial concept or pathway overlap |
| 1.0–2.9  | Essentially unrelated |

## Two things to tag separately (do NOT fold into the score)

Keep **relevance** (the score) apart from **evidence strength** so you can
deliberately balance a subtopic across the ladder instead of citing six mouse
papers and zero human data.

- `model_tier`: `in_vitro` | `cell_line` | `primary` | `rodent` | `nhp` | `human_obs` | `human_rct`
- `causality`: `causal` (perturbation: KO/KD/rescue/intervention) | `correlational` (association/expression)
- `clinical_stage`: `preclinical` | `clinical_trial` | `in_clinical_use`

## Subtopic rule

- Assign `subtopic` **only when score ≥ 5.0**; otherwise `subtopic = ""`.
- Converge to **5–7 clusters**. Cluster by **PATHWAY or MODEL, not by assay technique**:
  - merge KO / KD / rescue / overexpression -> `gene perturbation`
  - merge RNA-seq / proteomics / metabolomics -> `omics profiling`
- Short names (1–3 words), e.g. `BDNF-CREB`, `CCO mechanism`, `gamma entrainment`,
  `glymphatic clearance`.

## Extended evidence hierarchy (replaces the single "preclinical" bucket)

Clinical designs keep the usual hierarchy; bench work is graded by **causal
strength and model proximity** instead of being lumped together:

| Level | Designs |
|---|---|
| L1 | systematic review / meta-analysis / guideline |
| L2 | RCT / clinical trial |
| L3 | human cohort / observational |
| L4 | case-control / cross-sectional / case report |
| P1 | human tissue / iPSC / organoid, causal perturbation |
| P2 | NHP or rodent, causal (KO/KD/rescue, intervention) |
| P3 | rodent / in-vitro, correlational (expression/association) |
| ungraded | narrative review, editorial |

When two papers score similarly, prefer the higher evidence level **and** the one
whose target/biomarker is closer to the clinic. Note this in the `rationale`.

## Distribution self-check

- High (≥7): ~20–40%
- Mid (5–6.9): ~40–60%
- Low (<5): ~10–30%

If everything is 8–9, you are not discriminating — re-read and spread the scores.

## Quality bar

- `perturbation` / `assay_readout` must be specific (not "molecular biology").
- `key_findings` should carry a number (n, effect size, p) when present.
- `limitations`: write "not explicitly stated" rather than inventing one.
- Do not inflate scores to pad the citation set; low relevance stays low.
- **Do not raise the score just because a paper is human/RCT** — that is what the
  `model_tier` and `clinical_stage` tags are for. Relevance and evidence strength
  are scored and tagged separately.
