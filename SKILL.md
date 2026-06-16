---
name: litriage
description: Use when the user wants to SEARCH and TRIAGE medical/scientific literature on a topic — "文献分诊/文献检索排序/找文献/literature search/screen papers" — and then read them, not auto-write a review. Pipeline - AI plans MeSH-aware queries, searches PubMed (OpenAlex fallback), de-duplicates, scores each paper 1-10 for relevance and tags its study type / evidence level, then emits a ranked, score-tagged BibTeX (.bib) plus a triage table (.md). Stops there and hands off to Zotero → zotero-deepread-bridge → phd-deepread. NOT for writing the review prose, adding a single citation, or producing PDF/Word.
metadata:
  author: Qing Wang (@heleninsights-dot)
  attribution: "Stages 1-4 concept (query-variant search → dedup → 1-10 relevance scoring → high-score-first selection) inspired by research-literature-review by Bensz Conan (@huangwb8). Independent reimplementation; no source copied. PubMed-first retrieval, study-type/evidence tagging, and the Zotero handoff are new."
  version: 0.1.0
  keywords:
    - litriage
    - 文献分诊
    - literature search
    - literature triage
    - 文献检索
    - 文献排序
    - 找文献
    - PubMed
    - MeSH
    - relevance scoring
    - evidence level
    - study type
    - BibTeX
    - Zotero
---

# LitTriage / 文献分诊

> 像分诊病人一样分诊文献，高分先读。
> PubMed-first literature **search + triage**. Scores papers 1–10, tags study
> type & evidence level, and hands a ranked `.bib` to Zotero. **No writing, no
> LaTeX.** Stdlib Python only.

## When to use

- **Use when:** the user wants to find and rank the literature on a topic, then
  read it (in Zotero / Obsidian). Output is a curated, scored citation set.
- **Do not use when:** the user wants the review *prose* written, a single
  reference added, or PDF/Word output. (Writing happens in `phd-deepread`
  after the human reads the PDFs.)
- **Top principle:** triage honestly from title + abstract; never inflate
  scores or claim to have read full text. The deep read comes later.

## Inputs

- `{topic}` — one-line topic (English preferred for PubMed recall).
- Optional scope — year range, study-type preference, extra constraints.
- Optional `--target-candidates` (pool size after dedup; default ~100–200).
- Optional NCBI API key (faster; not required).
- Output directory (default `runs/{safe_topic}/`).

## Outputs (3 deliverables, then stop)

- `{topic}_ranked.bib` — DOI-keyed BibTeX in theme order (reviews first, then by
  score). Each entry's `keywords` carries
  `score-08, topic-…, type-…, evidence-…, litriage`, which Zotero imports as
  sortable **tags**.
- `{topic}_ranked.rdf` — Zotero RDF: a parent collection with **one
  subcollection per theme** (same order as the note). Importing this gives real
  theme **subfolders** in Zotero in a single import.
- `{topic}_ranked.md` — triage note: a "How this was built" provenance funnel
  (queries → hits → deduped → kept) + a score/evidence snapshot, then
  papers **grouped by subtopic** (reviews/meta-analyses first, then by best
  score) in tables of
  score · evidence · year · first author · title · journal · DOI.

Intermediate files (under `{work_dir}/.litriage/`):
`queries.json`, `papers_pubmed.jsonl`, `papers_openalex.jsonl` (if used),
`candidates.jsonl`, `scored_papers.jsonl`.

## Pipeline

### Stage 1 — Query planning  *(AI)*
Read `references/01_query_planning.md`. The AI writes ~10 MeSH-aware PubMed
query variants (aim 8–12) to `.litriage/queries.json` — anchored on a shared
broad core (intervention AND disease) so they deliberately overlap, plus ≥1
high-recall and ≥1 high-precision/study-type-filtered variant.

### Stage 2 — Retrieval  *(script)*
```bash
python3 scripts/pubmed_search.py --queries .litriage/queries.json \
    --out .litriage/papers_pubmed.jsonl --retmax 50 \
    [--mindate 2015 --maxdate 2026] [--api-key KEY]
```
If PubMed coverage is thin (too few candidates, or a device/engineering angle),
add the fallback and merge:
```bash
python3 scripts/openalex_search.py --queries .litriage/queries.json \
    --out .litriage/papers_openalex.jsonl
```

### Stage 3 — De-duplication  *(script)*
```bash
python3 scripts/dedupe.py --in .litriage/papers_pubmed.jsonl \
    [.litriage/papers_openalex.jsonl] --out .litriage/candidates.jsonl
```

### Stage 4 — Scoring & study-type tagging  *(AI)*
Read `references/02_scoring.md`. The AI reads each candidate's title + abstract
+ MeSH, scores 1–10, assigns a subtopic (only if ≥5), and writes
`.litriage/scored_papers.jsonl`.

### Stage 5 — Build deliverables  *(script)*
```bash
python3 scripts/build_outputs.py --scored .litriage/scored_papers.jsonl \
    --topic "{topic}" --out-bib "{topic}_ranked.bib" --out-md "{topic}_ranked.md" \
    --out-rdf "{topic}_ranked.rdf" \
    [--min-score 4] [--headline "one-line synthesis / research-gap insight"]
```
`--out-rdf` writes a Zotero RDF with one subcollection per theme (import it for
real theme subfolders). `--headline` is optional: pass a single AI-written
sentence (e.g. the key gap or takeaway) to fill the note's Headline callout;
omit it to leave the callout out. The funnel counts are read automatically from
the sibling `.litriage/` files.

### Handoff (not part of this skill)
Read `references/03_zotero_handoff.md`: import the `.rdf` into Zotero (one
subcollection per theme) — or the `.bib` (single collection + tags) → *Find
Available PDF* → read by `score-NN` tag → `zotero-deepread-bridge` →
`phd-deepread`.

## Hard constraints

- LitTriage **never writes review prose** and **never produces PDF/Word**. It
  stops at `.bib` + `.md`.
- Scores come from title/abstract/MeSH only; the body must not claim full-text
  reading.
- `keywords` in the `.bib` must keep the `score-NN` zero-padded so Zotero sorts
  it correctly.
- Do not pad the set with low-relevance papers; honest low scores stay low.
- All intermediate files live in `{work_dir}/.litriage/`; only the two
  deliverables go in the work-dir root.

## Environment & scripts

- **Runtime:** Python 3.9+. **No third-party packages** (stdlib `urllib` only).
- **Scripts:** `pubmed_search.py`, `openalex_search.py`, `dedupe.py`,
  `build_outputs.py`, shared `common.py`.
- **References:** `references/01_query_planning.md`,
  `references/02_scoring.md`, `references/03_zotero_handoff.md`.

## Attribution

The stage 1–4 *concept* (query-variant search → dedup → 1–10 relevance scoring
→ high-score-first selection) is inspired by
[`research-literature-review`](https://github.com/huangwb8) by **Bensz Conan
(@huangwb8)**. This is an independent reimplementation — no source copied — and
the PubMed-first retrieval, study-type/evidence tagging, and Zotero handoff are
new. MIT licensed.
