#!/usr/bin/env python3
"""LitTriage — fallback retrieval from OpenAlex.

Used when PubMed returns too few candidates, or for topics that are not
well-indexed in PubMed (e.g. engineering / device work alongside clinical
literature). OpenAlex has no MeSH, so study-type tagging falls back to its
`type` field. Output uses the same normalized schema as pubmed_search.py so
the two can be concatenated before dedup.

Usage:
    python3 scripts/openalex_search.py --queries queries.json --out papers_openalex.jsonl \
        [--per-page 50] [--from-year 2015] [--to-year 2026] [--email you@x.com]
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

from common import (
    DEFAULT_CONTACT,
    RateLimiter,
    eprint,
    http_get,
    load_queries,
    make_record,
    write_jsonl,
)

OPENALEX = "https://api.openalex.org/works"


def reconstruct_abstract(inv_index: Optional[Dict[str, List[int]]]) -> str:
    """OpenAlex stores abstracts as an inverted index; rebuild linear text."""
    if not inv_index:
        return ""
    positions: List[tuple] = []
    for word, idxs in inv_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def parse_work(w: Dict) -> Dict:
    doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
    pmid = ""
    ids = w.get("ids") or {}
    if ids.get("pmid"):
        pmid = ids["pmid"].rstrip("/").split("/")[-1]

    authors = []
    for a in w.get("authorships", []) or []:
        name = (a.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    host = (w.get("primary_location") or {}).get("source") or {}
    journal = host.get("display_name") or ""

    pub_types = [w.get("type")] if w.get("type") else []
    # OpenAlex sometimes flags retractions / types of works; include subtype hints.
    if w.get("type_crossref") and w.get("type_crossref") != w.get("type"):
        pub_types.append(w["type_crossref"])

    return make_record(
        pmid=pmid,
        doi=doi,
        title=w.get("title") or "",
        abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        journal=journal,
        year=w.get("publication_year"),
        authors=authors,
        mesh=[],  # OpenAlex has no MeSH
        publication_types=[p for p in pub_types if p],
        source="openalex",
        url=w.get("id") or "",
    )


def search(query: str, per_page: int, from_year: Optional[str], to_year: Optional[str],
           limiter: RateLimiter, contact: str) -> List[Dict]:
    filters = []
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    if to_year:
        filters.append(f"to_publication_date:{to_year}-12-31")
    params = {
        "search": query,
        "per-page": str(min(per_page, 200)),
        "mailto": contact,
    }
    if filters:
        params["filter"] = ",".join(filters)
    raw = http_get(OPENALEX, params, limiter=limiter, contact=contact)
    data = json.loads(raw)
    return [parse_work(w) for w in data.get("results", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenAlex fallback retrieval for LitTriage")
    ap.add_argument("--queries", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument("--from-year")
    ap.add_argument("--to-year")
    ap.add_argument("--email", default=DEFAULT_CONTACT)
    args = ap.parse_args()

    queries = load_queries(args.queries)
    if not queries:
        eprint("No queries found in", args.queries)
        return 2

    limiter = RateLimiter(0.12)  # OpenAlex polite pool is generous; stay courteous.
    by_id: Dict[str, Dict] = {}
    for i, q in enumerate(queries, 1):
        query = q["query"]
        eprint(f"[{i}/{len(queries)}] openalex: {query}")
        try:
            recs = search(query, args.per_page, args.from_year, args.to_year,
                          limiter, args.email)
        except Exception as err:  # noqa: BLE001
            eprint(f"  failed: {err}")
            continue
        eprint(f"  {len(recs)} hits")
        for rec in recs:
            existing = by_id.get(rec["id"])
            if existing:
                if query not in existing["queries"]:
                    existing["queries"].append(query)
            else:
                rec["queries"] = [query]
                by_id[rec["id"]] = rec

    n = write_jsonl(args.out, by_id.values())
    eprint(f"Wrote {n} unique OpenAlex records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
