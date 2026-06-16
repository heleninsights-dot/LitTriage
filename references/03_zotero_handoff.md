# Stage 5 — Handoff to Zotero → Obsidian deep reading

> LitTriage stops here. Its job is done once you have a ranked, score-tagged
> `.bib`. This page is the bridge to the reading workflow.

## What you have

- `{topic}_ranked.rdf` — Zotero RDF: a parent collection with **one
  subcollection per theme** (reviews first), papers already inside. Import this
  for real theme subfolders in one go.
- `{topic}_ranked.bib` — every entry's `keywords` field carries:
  `score-08, topic-gamma-entrainment, type-rct, evidence-2, litriage`. Use this
  if you'd rather have one flat collection + theme *tags*.
- `{topic}_ranked.md` — the triage note to eyeball first.

## Why the score survives: BibTeX `keywords` → Zotero tags

Zotero imports the BibTeX `keywords` field as **tags**. So after import every
paper is tagged with its score, subtopic, study type and evidence level. The
score is zero-padded (`score-08`, not `score-8`) so it **sorts correctly** in
Zotero's tag selector.

## Steps

1. **Import**:
   - For **theme subfolders** (recommended): File → Import → `{topic}_ranked.rdf`.
     Zotero recreates the parent collection and a subcollection per theme, with
     each paper already filed under its theme.
   - For a **flat collection + tags**: File → Import → `{topic}_ranked.bib`
     (or drag the file into a new collection).
2. **Fetch PDFs**: select the imported items → right-click →
   *Find Available PDF*. (DOIs are present, so most open-access PDFs attach
   automatically. For paywalled ones, attach via your library/proxy.)
3. **Triage by score**: open the tag selector, sort, and start from the
   `score-09` / `score-08` tags. For ties, prefer the higher `evidence-N`.
4. **Deep read**: run the existing skills on the top papers —
   - `zotero-deepread-bridge` → pulls the PDFs from the Zotero collection into
     Obsidian.
   - `phd-deepread` → produces the markdown literature note + 9-node JSON
     canvas per paper.

## Tag cheatsheet

| Tag prefix | Meaning | Example |
|---|---|---|
| `score-NN` | LitTriage relevance, 01–10, sortable | `score-09` |
| `topic-…` | subtopic cluster | `topic-cco-mechanism` |
| `type-…` | study design | `type-meta-analysis` |
| `evidence-N` | evidence level (1 strongest, x ungraded) | `evidence-1` |
| `litriage` | everything LitTriage imported (easy cleanup/filter) | — |

## Tip

Make a saved search in Zotero: `tag is score-09 OR score-08` → your "read first"
shelf. Re-running LitTriage on a refined topic just adds more tagged items to
the same collection.
