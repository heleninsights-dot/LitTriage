# Stage 4 — Relevance scoring & study-type tagging

> The host AI reads `candidates.jsonl` and writes `scored_papers.jsonl`, one
> JSON object per line. Score from **title + abstract + MeSH only** — this is
> triage, not deep reading. The full-text reading happens later in
> `phd-deepread`; do not pretend to have read the PDF.

## What each scored record must contain

Copy every field from the candidate record, then add:

```json
{
  "score": 8.5,
  "subtopic": "gamma entrainment",
  "study_type": "rct",
  "rationale": "tPBM RCT in MCI patients; same population and intervention",
  "extraction": {
    "design": "double-blind RCT, n=60",
    "key_findings": "ADAS-Cog improved 2.3 pts vs sham (p<0.05)",
    "limitations": "small sample, 8-week follow-up only"
  }
}
```

`study_type` is optional — if you leave it out, `build_outputs.py` derives it
from the paper's `publication_types`/`mesh`. Fill it when the abstract makes the
design obvious but PubMed's publication types are vague.

## Scoring scale (1–10)

| Band | Meaning |
|---|---|
| 9.0–10.0 | Same population + same intervention + same outcome as the topic |
| 7.0–8.9 | Same core question; intervention or population slightly different |
| 5.0–6.9 | Same field, but task/method/population clearly diverges |
| 3.0–4.9 | Only partial concept or mechanism overlap |
| 1.0–2.9 | Essentially unrelated |

Score on four axes and let the weakest drag it down: **population match,
intervention/method match, outcome/modality match, clinical value.**

## Subtopic rule

- Assign `subtopic` **only when score ≥ 5.0**; otherwise `subtopic = ""`.
- Converge to **5–7 clusters total**. Merge singletons into the nearest cluster.
- Keep names short (1–3 words), e.g. `gamma entrainment`, `CCO mechanism`,
  `clinical RCT`, `sleep/glymphatic`.

## Distribution self-check

A healthy triage spread (sanity check, not a hard rule):

- High (≥7): ~20–40%
- Mid (5–6.9): ~40–60%
- Low (<5): ~10–30%

If everything is 8–9, you are not discriminating — re-read and spread the scores.

## Evidence hierarchy (why study_type matters here)

LitTriage is built for medical students, so the study type is a first-class
triage signal, not decoration. `build_outputs.py` maps it to an evidence level:

| Level | Designs |
|---|---|
| L1 | systematic review, meta-analysis, guideline |
| L2 | RCT / clinical trial |
| L3 | cohort |
| L4 | case-control |
| L5 | cross-sectional, case report/series |
| preclinical | animal / in vitro |
| ungraded | narrative review, editorial, other |

When two papers score similarly, the higher evidence level should be read first.
Mention this in the rationale when relevant.

## Quality bar

- `design` must be specific (not just "deep learning" / "a study").
- `key_findings` should carry a number (sample size or effect) when present.
- `limitations`: write "not explicitly stated" rather than inventing one.
- Do not inflate scores to pad the citation set; low relevance stays low.
