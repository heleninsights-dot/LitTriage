#!/usr/bin/env python3
"""LitTriage — de-duplicate candidate papers across one or more source files.

Reads one or more papers*.jsonl (e.g. PubMed + OpenAlex), collapses duplicates
by the record's dedup id (doi -> pmid -> normalized title), and merges the
`queries` that surfaced each paper. When the same paper appears from two
sources, the record with the longer abstract wins (PubMed usually), but PMID,
DOI and MeSH are merged in from whichever source has them.

Usage:
    python3 scripts/dedupe.py --in papers_pubmed.jsonl papers_openalex.jsonl \
        --out candidates.jsonl
"""

from __future__ import annotations

import argparse
from typing import Dict, List

from common import compute_id, eprint, read_jsonl, write_jsonl


def merge(into: Dict, other: Dict) -> Dict:
    """Merge `other` into `into`, keeping the richer of conflicting fields."""
    # Prefer the longer abstract / title.
    if len(other.get("abstract") or "") > len(into.get("abstract") or ""):
        into["abstract"] = other["abstract"]
    if len(other.get("title") or "") > len(into.get("title") or ""):
        into["title"] = other["title"]
    # Fill missing scalar identifiers / metadata.
    for f in ("pmid", "doi", "journal", "year", "url"):
        if not into.get(f) and other.get(f):
            into[f] = other[f]
    # Union list fields.
    for f in ("authors", "mesh", "publication_types", "queries"):
        seen = list(into.get(f) or [])
        for v in other.get(f) or []:
            if v not in seen:
                seen.append(v)
        into[f] = seen
    # Track provenance.
    srcs = set((into.get("source") or "").split("+")) | {other.get("source", "")}
    into["source"] = "+".join(sorted(s for s in srcs if s))
    return into


def main() -> int:
    ap = argparse.ArgumentParser(description="De-duplicate LitTriage candidates")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True,
                    help="one or more papers*.jsonl files")
    ap.add_argument("--out", required=True, help="candidates.jsonl")
    args = ap.parse_args()

    by_id: Dict[str, Dict] = {}
    total = 0
    for path in args.inputs:
        for rec in read_jsonl(path):
            total += 1
            # Recompute id in case sources used different rules.
            rec["id"] = compute_id(rec)
            existing = by_id.get(rec["id"])
            if existing:
                merge(existing, rec)
            else:
                by_id[rec["id"]] = rec

    candidates: List[Dict] = list(by_id.values())
    n = write_jsonl(args.out, candidates)
    eprint(f"Deduped {total} records -> {n} unique candidates ({total - n} duplicates collapsed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
