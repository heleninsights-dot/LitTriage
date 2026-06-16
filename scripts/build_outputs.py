#!/usr/bin/env python3
"""LitTriage — build the two deliverables from scored papers.

Input: scored_papers.jsonl — each record is a candidate plus the fields the host
AI added during scoring:
    score        float 1-10
    subtopic     str (only meaningful when score >= 5)
    study_type   str (optional; derived from publication_types/MeSH if absent)
    rationale    str (optional)

Outputs:
    {topic}_ranked.bib  — DOI-keyed BibTeX, sorted high-score-first, with
                          score / subtopic / study-type / evidence-level baked
                          into the `keywords` field. Zotero imports `keywords`
                          as TAGS, so after import you sort Zotero by the
                          `score-08`-style tag and read top-down.
    {topic}_ranked.md   — human-readable triage table.

Usage:
    python3 scripts/build_outputs.py --scored scored_papers.jsonl \
        --topic "tPBM in Alzheimer's" --out-bib out.bib --out-md out.md \
        [--min-score 0]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import date
from typing import Dict, List, Optional
from xml.sax.saxutils import escape as _xml_escape

from common import eprint, latex_escape, read_jsonl, slugify

# --------------------------------------------------------------------------- #
# Study type + evidence level                                                  #
# --------------------------------------------------------------------------- #

# Ordered: first matching pattern wins. Higher in the list = stronger evidence.
STUDY_TYPE_RULES = [
    ("meta-analysis", r"meta[- ]?analysis", 1),
    ("systematic-review", r"systematic review", 1),
    ("rct", r"randomized controlled trial|randomised controlled trial|\brandomized\b", 2),
    ("clinical-trial", r"clinical trial", 2),
    ("cohort", r"cohort", 3),
    ("case-control", r"case[- ]control", 4),
    ("cross-sectional", r"cross[- ]sectional", 5),
    ("case-report", r"case reports?|case series", 5),
    ("review", r"\breview\b", 9),  # narrative review -> not graded (9 = ungraded)
    ("guideline", r"guideline|practice guideline", 1),
    ("animal", r"\banimal\b|in vitro|preclinical", 6),
]


def classify_study(rec: Dict) -> tuple:
    """Return (study_type_slug, evidence_level_int). Honors an explicit study_type.

    Sources, in order: an explicit `study_type` from the scorer, then PubMed
    publication_types + MeSH, then the title. The title is included because
    PubMed publication-types are often incomplete (e.g. a paper titled "... : a
    randomized controlled trial" not tagged as RCT). Abstracts are deliberately
    NOT scanned — a review discussing RCTs would be mis-tagged.
    """
    explicit = (rec.get("study_type") or "").strip().lower()
    haystacks = list(rec.get("publication_types") or []) + list(rec.get("mesh") or [])
    if rec.get("title"):
        haystacks.append(rec["title"])
    if explicit:
        haystacks.insert(0, explicit)
    blob = " ; ".join(haystacks).lower()
    for slug, pattern, level in STUDY_TYPE_RULES:
        if re.search(pattern, blob):
            return slug, level
    return "other", 9


EVIDENCE_LABEL = {
    1: "L1 (SR/MA/guideline)", 2: "L2 (RCT/trial)", 3: "L3 (cohort)",
    4: "L4 (case-control)", 5: "L5 (case/cross-sec)", 6: "preclinical",
    9: "ungraded",
}


# --------------------------------------------------------------------------- #
# BibTeX                                                                        #
# --------------------------------------------------------------------------- #

_STOPWORDS = {"the", "a", "an", "of", "in", "on", "for", "and", "to", "with", "via"}


def first_title_word(title: str) -> str:
    for w in re.findall(r"[A-Za-z]+", title or ""):
        if w.lower() not in _STOPWORDS and len(w) > 2:
            return w.lower()
    return "untitled"


def cite_key(rec: Dict, used: set) -> str:
    authors = rec.get("authors") or []
    last = "anon"
    if authors:
        last = re.sub(r"[^A-Za-z]", "", authors[0].split()[0]) or "anon"
    year = str(rec.get("year") or "nd")
    base = f"{last.lower()}{year}{first_title_word(rec.get('title',''))}"
    key = base
    suffix = ord("a")
    while key in used:
        key = base + chr(suffix)
        suffix += 1
    used.add(key)
    return key


def format_authors(authors: List[str]) -> str:
    """Convert 'Last FM' -> 'Last, FM'; join with ' and ' for BibTeX."""
    out = []
    for a in authors:
        parts = a.split()
        if len(parts) >= 2 and parts[-1].isupper() and len(parts[-1]) <= 4:
            out.append(f"{' '.join(parts[:-1])}, {parts[-1]}")
        else:
            out.append(a)
    return " and ".join(latex_escape(a) for a in out)


def make_keywords(rec: Dict, study_slug: str, level: int) -> List[str]:
    kws = []
    score = rec.get("score")
    if isinstance(score, (int, float)):
        kws.append(f"score-{round(score):02d}")          # sortable in Zotero
    sub = rec.get("subtopic")
    if sub:
        kws.append("topic-" + slugify(sub, 30))
    kws.append("type-" + study_slug)
    kws.append(f"evidence-{level if level != 9 else 'x'}")
    kws.append("litriage")                                # so you can find them all
    return kws


def build_bib(records: List[Dict]) -> str:
    used: set = set()
    blocks = []
    for rec in records:
        study_slug, level = classify_study(rec)
        key = cite_key(rec, used)
        fields = []
        if rec.get("title"):
            fields.append(("title", "{" + latex_escape(rec["title"]) + "}"))
        if rec.get("authors"):
            fields.append(("author", format_authors(rec["authors"])))
        if rec.get("journal"):
            fields.append(("journal", latex_escape(rec["journal"])))
        if rec.get("year"):
            fields.append(("year", str(rec["year"])))
        if rec.get("doi"):
            fields.append(("doi", rec["doi"]))
        if rec.get("url"):
            fields.append(("url", rec["url"]))
        if rec.get("abstract"):
            fields.append(("abstract", latex_escape(rec["abstract"])))
        fields.append(("keywords", ", ".join(make_keywords(rec, study_slug, level))))
        note = []
        if isinstance(rec.get("score"), (int, float)):
            note.append(f"LitTriage score {rec['score']:.1f}")
        if rec.get("rationale"):
            note.append(rec["rationale"])
        if note:
            fields.append(("note", latex_escape(" — ".join(note))))

        body = ",\n  ".join(f"{k} = {{{v}}}" if not v.startswith("{") else f"{k} = {v}"
                            for k, v in fields)
        blocks.append(f"@article{{{key},\n  {body}\n}}")
    return "\n\n".join(blocks) + "\n"


# --------------------------------------------------------------------------- #
# Markdown triage table                                                         #
# --------------------------------------------------------------------------- #

def _count_lines(path: str) -> Optional[int]:
    """Count non-blank lines in a jsonl file; None if it is missing."""
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return None


def _count_queries(path: str) -> Optional[int]:
    """Number of search queries planned; None if queries.json is missing."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for value in data.values():            # e.g. {"queries": [...]}
            if isinstance(value, list):
                return len(value)
        return len(data)
    return None


def _raw_hits(litriage_dir: str) -> Optional[int]:
    """True cross-query hit total (before de-duplication).

    pubmed_search.py de-duplicates by PMID *inline*, so papers_pubmed.jsonl is
    already unique — counting its lines would always equal the deduped count and
    hide the duplicates. The raw count is recoverable from each record's
    `queries` list (its multiplicity = how many queries returned it). OpenAlex
    records (if any) are counted directly since they carry no per-record query list.
    """
    total = 0
    found = False
    try:
        with open(os.path.join(litriage_dir, "papers_pubmed.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                found = True
                try:
                    rec = json.loads(line)
                except ValueError:
                    total += 1
                    continue
                q = rec.get("queries")
                total += len(q) if isinstance(q, list) and q else 1
    except OSError:
        pass
    oa = _count_lines(os.path.join(litriage_dir, "papers_openalex.jsonl"))
    if oa:
        total += oa
        found = True
    return total if found else None


def gather_funnel(scored_path: str) -> Dict[str, Optional[int]]:
    """Read the search-funnel counts from the sibling .litriage/ files."""
    d = os.path.dirname(os.path.abspath(scored_path))
    return {
        "queries": _count_queries(os.path.join(d, "queries.json")),
        "hits": _raw_hits(d),
        "deduped": _count_lines(os.path.join(d, "candidates.jsonl")),
    }


def summarize_sources(records: List[Dict]) -> str:
    counts = Counter((r.get("source") or "").strip().lower()
                     for r in records if r.get("source"))
    if not counts:
        return "PubMed (OpenAlex fallback)"
    pretty = {"pubmed": "PubMed", "openalex": "OpenAlex", "crossref": "Crossref"}
    return ", ".join(pretty.get(name, name.title()) for name, _ in counts.most_common())


def first_author_display(rec: Dict) -> str:
    authors = rec.get("authors") or []
    if not authors:
        return "—"
    first = str(authors[0]).strip()
    return f"{first} et al." if len(authors) > 1 else first


def _score_of(rec: Dict) -> float:
    s = rec.get("score")
    return float(s) if isinstance(s, (int, float)) else 0.0


# Reviews / meta-analyses are pinned to the top of the by-theme list: they give
# the lay of the land, so they're the natural first read in a triage note.
_REVIEWS_THEME_RE = re.compile(r"review|meta[- ]?analys", re.IGNORECASE)


def _is_reviews_theme(name: str) -> bool:
    return bool(_REVIEWS_THEME_RE.search(name or ""))


def order_themes(records: List[Dict]) -> List[tuple]:
    """Group records by subtopic and order the themes the canonical way:
    reviews/meta-analyses first, then by each theme's best score (desc).
    Within a theme, records are sorted by score then year (desc). Used by BOTH
    the markdown note and the .bib so the two deliverables stay consistent."""
    groups: Dict[str, List[Dict]] = {}
    for rec in records:
        key = (rec.get("subtopic") or "").strip() or "(unclustered)"
        groups.setdefault(key, []).append(rec)
    for items in groups.values():
        items.sort(key=lambda r: (_score_of(r), r.get("year") or 0), reverse=True)
    return sorted(
        groups.items(),
        key=lambda kv: (0 if _is_reviews_theme(kv[0]) else 1,
                        -max(_score_of(r) for r in kv[1])),
    )


def _yaml_scalar(text: str) -> str:
    return '"' + str(text).replace('"', "'") + '"'


def build_md(
    records: List[Dict],
    topic: str,
    *,
    all_scored: List[Dict],
    funnel: Dict[str, Optional[int]],
    min_score: float,
    bib_name: Optional[str] = None,
    headline: Optional[str] = None,
) -> str:
    """Render the human-facing triage note: provenance + snapshot + by-theme tables."""
    n_kept = len(records)
    n_scored = len(all_scored)
    scores = [_score_of(r) for r in all_scored]
    high = sum(1 for x in scores if x >= 7)
    mid = sum(1 for x in scores if 5 <= x < 7)
    low = sum(1 for x in scores if x < 5)
    sources = summarize_sources(all_scored)

    evidence = Counter()
    for rec in records:
        _, level = classify_study(rec)
        evidence[EVIDENCE_LABEL.get(level, "?")] += 1

    # ---- frontmatter -----------------------------------------------------
    lines = [
        "---",
        f"title: {_yaml_scalar(topic)}",
        f"date: {date.today().isoformat()}",
        f"source: {_yaml_scalar('LitTriage (' + sources + ')')}",
        "tags: [literature-triage, litriage]",
        "---",
        "",
        f"# LitTriage — {topic}",
        "",
    ]

    # ---- "How this was built" funnel ------------------------------------
    funnel_bits = []
    if funnel.get("queries") is not None:
        funnel_bits.append(f"{funnel['queries']} queries")
    if funnel.get("hits") is not None:
        funnel_bits.append(f"{funnel['hits']} hits")
    if funnel.get("deduped") is not None:
        funnel_bits.append(f"{funnel['deduped']} deduped")
    # Scoring drops nothing, so only show this stage when it actually differs
    # from the deduped count (avoids a redundant "164 → 164").
    if funnel.get("deduped") != n_scored:
        funnel_bits.append(f"{n_scored} scored")
    funnel_bits.append(f"**{n_kept} kept** (score ≥ {min_score:g})")
    bib_link = f" BibTeX: [[{bib_name}]]" if bib_name else ""
    lines += [
        "> [!info] How this was built",
        "> " + " → ".join(funnel_bits) + ".",
        f"> Source: {sources}. Scores (1–10) are **abstract-based triage**, "
        f"not full-text judgement.{bib_link}",
        "",
    ]

    # ---- snapshot --------------------------------------------------------
    ev_str = " · ".join(f"{label}: {n}" for label, n in evidence.most_common())
    lines += [
        "> [!tip] Snapshot",
        f"> Scored {n_scored} — High (≥7): {high} · Mid (5–6.9): {mid} · "
        f"Low (<5): {low}. Kept {n_kept}.",
        f"> Evidence (kept): {ev_str or '—'}.",
        "",
    ]

    # ---- optional one-line synthesis (AI-supplied) ----------------------
    if headline:
        lines += ["> [!warning] Headline", "> " + headline.strip(), ""]

    # ---- group by subtopic; reviews first, then by best score -----------
    ordered = order_themes(records)

    lines += ["## By theme", ""]
    for idx, (subtopic, items) in enumerate(ordered, 1):
        top = max(_score_of(r) for r in items)
        lines += [
            f"### {idx}. {subtopic} · {len(items)} papers · top {top:.1f}",
            "",
            "| Score | Evidence | Year | First author | Title | Journal | DOI |",
            "|:--:|:--|:--:|---|---|---|---|",
        ]
        for rec in items:
            _, level = classify_study(rec)
            score = rec.get("score")
            score_s = f"{score:.1f}" if isinstance(score, (int, float)) else "-"
            title = (rec.get("title") or "").replace("|", "\\|")
            journal = (rec.get("journal") or "—").replace("|", "\\|")
            author = first_author_display(rec).replace("|", "\\|")
            doi = rec.get("doi") or ""
            doi_cell = f"[{doi}](https://doi.org/{doi})" if doi else "—"
            lines.append(
                f"| {score_s} | {EVIDENCE_LABEL.get(level, '?')} | "
                f"{rec.get('year') or '—'} | {author} | {title} | {journal} | {doi_cell} |"
            )
        lines.append("")

    lines += [
        "---",
        "_Next: import the `.rdf` into Zotero (creates a subcollection per theme) "
        "or the `.bib` (single collection + tags) → *Find Available PDF* → run "
        "`zotero-deepread-bridge` → `phd-deepread` on the highest-score papers first._",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Zotero RDF — one import, a real subcollection per theme                       #
# --------------------------------------------------------------------------- #

_RDF_HEADER = """<rdf:RDF
 xmlns:z="http://www.zotero.org/namespaces/export#"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:bib="http://purl.org/net/biblio#"
 xmlns:foaf="http://xmlns.com/foaf/0.1/"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:link="http://purl.org/rss/1.0/modules/link/"
 xmlns:prism="http://prismstandard.org/namespaces/1.2/basic/">"""

# XML 1.0 forbids most control chars; strip them so abstracts don't break import.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _x(text) -> str:
    return _xml_escape(_CTRL_RE.sub("", str(text)))


def _split_author(name: str) -> tuple:
    """Split a 'Surname FM' string into (surname, given). PubMed stores authors
    as 'LastName Initials'; a collective name has no initials block."""
    parts = str(name).split()
    if len(parts) >= 2 and parts[-1].isupper() and len(parts[-1]) <= 4:
        return " ".join(parts[:-1]), parts[-1]
    return str(name), ""


def _rdf_item(iid: str, rec: Dict) -> str:
    study_slug, level = classify_study(rec)
    L = [f'    <bib:Article rdf:about="#{iid}">',
         "        <z:itemType>journalArticle</z:itemType>"]
    if rec.get("journal"):
        L += ["        <dcterms:isPartOf>",
              f"            <bib:Journal><dc:title>{_x(rec['journal'])}</dc:title></bib:Journal>",
              "        </dcterms:isPartOf>"]
    authors = rec.get("authors") or []
    if authors:
        L += ["        <bib:authors>", "            <rdf:Seq>"]
        for a in authors:
            surname, given = _split_author(a)
            L += ["                <rdf:li>", "                    <foaf:Person>",
                  f"                        <foaf:surname>{_x(surname)}</foaf:surname>"]
            if given:
                L.append(f"                        <foaf:givenName>{_x(given)}</foaf:givenName>")
            L += ["                    </foaf:Person>", "                </rdf:li>"]
        L += ["            </rdf:Seq>", "        </bib:authors>"]
    for kw in make_keywords(rec, study_slug, level):     # score / topic / type / evidence as tags
        L.append(f"        <dc:subject>{_x(kw)}</dc:subject>")
    if rec.get("title"):
        L.append(f"        <dc:title>{_x(rec['title'])}</dc:title>")
    if rec.get("abstract"):
        L.append(f"        <dcterms:abstract>{_x(rec['abstract'])}</dcterms:abstract>")
    if rec.get("year"):
        L.append(f"        <dc:date>{_x(rec['year'])}</dc:date>")
    doi = rec.get("doi") or ""
    if doi:
        L.append(f"        <dc:identifier>DOI {_x(doi)}</dc:identifier>")
    L.append("        <z:libraryCatalog>LitTriage</z:libraryCatalog>")
    note = []
    if isinstance(rec.get("score"), (int, float)):
        note.append(f"LitTriage score {rec['score']:.1f}")
    if rec.get("rationale"):
        note.append(str(rec["rationale"]))
    if note:
        L.append(f"        <dc:description>{_x(' — '.join(note))}</dc:description>")
    url = rec.get("url") or (f"https://doi.org/{doi}" if doi else "")
    if url:
        L += ["        <dc:identifier>", "            <dcterms:URI>",
              f"                <rdf:value>{_x(url)}</rdf:value>",
              "            </dcterms:URI>", "        </dc:identifier>"]
    L.append("    </bib:Article>")
    return "\n".join(L)


def build_rdf(themed_groups: List[tuple], topic: str) -> str:
    """Zotero RDF: a parent collection 'LitTriage — {topic}' whose subcollections
    are the themes (in the same order as the note), each holding its papers."""
    flat = [rec for _, items in themed_groups for rec in items]
    ids = {id(rec): f"item_{i}" for i, rec in enumerate(flat, 1)}

    out = [_RDF_HEADER]
    # Parent collection points at each theme subcollection.
    out.append('    <z:Collection rdf:about="#collection_root">')
    out.append(f"        <dc:title>{_x('LitTriage — ' + topic)}</dc:title>")
    for idx in range(1, len(themed_groups) + 1):
        out.append(f'        <dcterms:hasPart rdf:resource="#collection_{idx}"/>')
    out.append("    </z:Collection>")
    # One subcollection per theme, holding its items.
    for idx, (subtopic, items) in enumerate(themed_groups, 1):
        out.append(f'    <z:Collection rdf:about="#collection_{idx}">')
        out.append(f"        <dc:title>{_x(subtopic)}</dc:title>")
        for rec in items:
            out.append(f'        <dcterms:hasPart rdf:resource="#{ids[id(rec)]}"/>')
        out.append("    </z:Collection>")
    # The item records themselves.
    for rec in flat:
        out.append(_rdf_item(ids[id(rec)], rec))
    out.append("</rdf:RDF>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build LitTriage .bib + .md deliverables")
    ap.add_argument("--scored", required=True, help="scored_papers.jsonl")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out-bib", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-rdf", default=None,
                    help="optional Zotero RDF with one subcollection per theme "
                         "(import this for real theme subfolders)")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="drop papers below this score from the deliverables")
    ap.add_argument("--headline", default=None,
                    help="optional one-line synthesis for the Headline callout "
                         "(the AI fills this; omit to leave it out)")
    args = ap.parse_args()

    all_scored = list(read_jsonl(args.scored))
    records = [r for r in all_scored
               if (r.get("score") if isinstance(r.get("score"), (int, float)) else 0) >= args.min_score]
    records.sort(key=lambda r: (r.get("score") if isinstance(r.get("score"), (int, float)) else 0),
                 reverse=True)

    funnel = gather_funnel(args.scored)
    bib_name = os.path.basename(args.out_bib)

    # .bib and .rdf follow the SAME theme order as the .md (reviews first, then
    # by score) so all deliverables are consistent.
    themed_groups = order_themes(records)
    themed = [rec for _, items in themed_groups for rec in items]

    with open(args.out_bib, "w", encoding="utf-8") as fh:
        fh.write(build_bib(themed))
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(build_md(records, args.topic, all_scored=all_scored, funnel=funnel,
                          min_score=args.min_score, bib_name=bib_name, headline=args.headline))
    wrote = [args.out_bib, args.out_md]
    if args.out_rdf:
        with open(args.out_rdf, "w", encoding="utf-8") as fh:
            fh.write(build_rdf(themed_groups, args.topic))
        wrote.append(args.out_rdf)

    eprint(f"Wrote {len(records)} entries -> {', '.join(wrote)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
