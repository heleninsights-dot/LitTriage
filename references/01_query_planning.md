# Stage 1 — MeSH-aware query planning

> The host AI reads this, then writes `queries.json`. No script generates
> queries — the model does, because it reasons about synonyms and MeSH better
> than any keyword expander.

## Goal

Turn one topic into **~10 PubMed query variants (aim 8–12)** that together give
broad-but-relevant coverage. PubMed is the primary engine, so think in MeSH +
field tags, not bare keywords.

**Design for overlap, not orthogonality.** Most variants should share a broad
core (intervention AND disease) and differ only on a *second* axis. Overlapping
queries are a feature: they confirm the core papers from several angles and let
de-duplication do real work. A healthy run de-dupes roughly **25–50%** of raw
hits. If you expect almost no overlap (every paper found by a single query),
your queries are too narrow/orthogonal — broaden them.

## Build concept blocks first

Before writing queries, draft 2–4 **concept blocks**, each an OR'd synonym group
(MeSH + free text). Example for a tPBM-in-AD topic:

- **Intervention:** `("Photobiomodulation Therapy"[Mesh] OR "photobiomodulation" OR "low-level light therapy" OR "tPBM" OR "near-infrared light")`
- **Disease/population:** `("Alzheimer Disease"[Mesh] OR "mild cognitive impairment" OR "MCI" OR "dementia" OR "cognitive decline")`
- **Mechanism (optional):** `("gamma" OR "40 Hz" OR "cytochrome c oxidase" OR "mitochond*" OR "amyloid")`
- **Outcome (optional):** `("cognition" OR "memory" OR "EEG" OR "connectivity")`

Then form queries mainly by AND-ing **two broad blocks** (Intervention AND
Disease). Keep blocks broad so each query plausibly returns tens of results.

## Prompt

```text
You are a medical librarian building a PubMed search strategy.

Topic: {topic}
Scope (optional): {time_range}, {study_types}, {extra_constraints}
Target candidate pool: ~{target_candidates} papers after dedup.

First draft 2–4 OR'd concept blocks (intervention, disease/population, and
optionally mechanism / outcome). Then produce ~10 PubMed query strings
(aim 8–12) that balance recall and precision AND deliberately overlap.

Rules:
1. Use MeSH terms with [Mesh] where a well-established heading exists,
   e.g. "Photobiomodulation Therapy"[Mesh]. Do NOT invent [Mesh] headings.
2. Anchor MOST queries on the SAME broad core: (Intervention block) AND
   (Disease/population block). This shared core is what makes variants overlap.
3. Generate variants by changing ONE second axis at a time while keeping the
   broad core — e.g. add a mechanism block, add an outcome block, swap the
   synonym emphasis, narrow the population subtype, or add a time slice. Aim for
   ~10 queries this way.
4. Keep queries BROAD: prefer AND-ing TWO blocks. Each query should plausibly
   return tens of papers. Do NOT AND together 3+ narrow blocks — that returns
   almost nothing and destroys overlap.
5. Include at least one HIGH-RECALL variant (free text only, no MeSH) so you
   don't miss very recent papers not yet MeSH-indexed.
6. Include at least one HIGH-PRECISION variant that adds a study-type filter,
   e.g. AND (randomized controlled trial[pt] OR systematic review[pt]).
7. Use English standard terminology.

Output strict JSON only:
{
  "queries": [
    {"query": "...", "rationale": "core | mechanism-axis | outcome-axis | synonym-variant | population-subtype | high-recall | high-precision | time-slice"}
  ]
}
```

## Self-check before saving queries.json

- **~8–12 queries** (not 3–4, not 20).
- Most queries share the broad Intervention AND Disease core, so you EXPECT
  meaningful overlap (a healthy run de-dupes ~25–50% of raw hits). If you'd
  expect near-zero overlap, the queries are too orthogonal — broaden them.
- Each query should plausibly return tens of results, not single digits. No
  query AND-s 3+ narrow blocks.
- At least one high-recall (no MeSH) and one high-precision (study-type filtered).
- MeSH headings actually exist (don't invent `[Mesh]` terms).
- If the AI cannot produce good MeSH, fall back to clean free-text — never emit
  zero queries. Worst case: one solid free-text query.

## Save

Write the JSON to `{work_dir}/.litriage/queries.json`, then run
`pubmed_search.py --queries .litriage/queries.json`.

`pubmed_search.py` defaults to `--retmax 50` per query, so ~10 broad queries
yield a few hundred raw hits that de-dupe down toward your target pool. Raise
`--retmax` only if individual queries are hitting the cap; if queries return far
fewer than 50, they're too narrow — fix the queries, not the cap.
