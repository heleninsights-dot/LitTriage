#!/usr/bin/env python3
"""LitTriage — primary retrieval from PubMed via NCBI E-utilities.

For each query variant: esearch -> PMID list -> efetch (XML) -> normalized
records. PubMed is the primary source because it returns MeSH terms and
publication types, which power the study-type / evidence-level tagging that
makes LitTriage useful for medical students.

Works keyless (3 req/s). Pass --api-key for 10 req/s (free from NCBI).

Usage:
    python3 scripts/pubmed_search.py --queries queries.json --out papers_pubmed.jsonl \
        [--retmax 50] [--mindate 2015] [--maxdate 2026] [--email you@x.com] [--api-key KEY]

Output: one normalized record per line (see common.RECORD_FIELDS).
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
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

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def esearch(query: str, retmax: int, mindate: Optional[str], maxdate: Optional[str],
            limiter: RateLimiter, common_params: Dict[str, str], contact: str) -> List[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
        **common_params,
    }
    if mindate:
        params["mindate"] = mindate
        params["datetype"] = "pdat"
    if maxdate:
        params["maxdate"] = maxdate
        params["datetype"] = "pdat"
    raw = http_get(f"{EUTILS}/esearch.fcgi", params, limiter=limiter, contact=contact)
    import json as _json
    data = _json.loads(raw)
    return data.get("esearchresult", {}).get("idlist", [])


def efetch(pmids: List[str], limiter: RateLimiter, common_params: Dict[str, str],
           contact: str) -> bytes:
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", **common_params}
    return http_get(f"{EUTILS}/efetch.fcgi", params, limiter=limiter, contact=contact)


def _text(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def parse_article(art: ET.Element) -> Optional[Dict]:
    medline = art.find("MedlineCitation")
    if medline is None:
        return None
    article = medline.find("Article")
    if article is None:
        return None

    pmid = _text(medline.find("PMID"))
    title = _text(article.find("ArticleTitle"))

    # Abstract: may be split into labeled sections.
    abstract_parts: List[str] = []
    abs = article.find("Abstract")
    if abs is not None:
        for at in abs.findall("AbstractText"):
            label = at.get("Label")
            txt = _text(at)
            abstract_parts.append(f"{label}: {txt}" if label else txt)
    abstract = "\n".join(p for p in abstract_parts if p)

    journal = _text(article.find("Journal/Title"))

    # Year: prefer ArticleDate, then JournalIssue PubDate Year, then MedlineDate.
    year = None
    for path in ("ArticleDate/Year", "Journal/JournalIssue/PubDate/Year"):
        y = _text(article.find(path))
        if y.isdigit():
            year = int(y)
            break
    if year is None:
        md = _text(article.find("Journal/JournalIssue/PubDate/MedlineDate"))
        for tok in md.replace("-", " ").split():
            if tok.isdigit() and len(tok) == 4:
                year = int(tok)
                break

    authors: List[str] = []
    for a in article.findall("AuthorList/Author"):
        last = _text(a.find("LastName"))
        initials = _text(a.find("Initials"))
        coll = _text(a.find("CollectiveName"))
        if last:
            authors.append(f"{last} {initials}".strip())
        elif coll:
            authors.append(coll)

    # DOI from ELocationID or ArticleIdList.
    doi = ""
    for el in article.findall("ELocationID"):
        if el.get("EIdType") == "doi":
            doi = _text(el)
            break
    if not doi:
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = _text(aid)
                break

    mesh = [_text(d) for d in medline.findall("MeshHeadingList/MeshHeading/DescriptorName")]
    mesh = [m for m in mesh if m]

    pub_types = [_text(p) for p in article.findall("PublicationTypeList/PublicationType")]
    pub_types = [p for p in pub_types if p]

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

    return make_record(
        pmid=pmid, doi=doi.lower(), title=title, abstract=abstract, journal=journal,
        year=year, authors=authors, mesh=mesh, publication_types=pub_types,
        source="pubmed", url=url,
    )


def parse_efetch(xml_bytes: bytes) -> List[Dict]:
    root = ET.fromstring(xml_bytes)
    out: List[Dict] = []
    for art in root.findall("PubmedArticle"):
        rec = parse_article(art)
        if rec:
            out.append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="PubMed retrieval for LitTriage")
    ap.add_argument("--queries", required=True, help="queries.json")
    ap.add_argument("--out", required=True, help="output papers jsonl")
    ap.add_argument("--retmax", type=int, default=50, help="max PMIDs per query")
    ap.add_argument("--mindate", help="earliest publication year, e.g. 2015")
    ap.add_argument("--maxdate", help="latest publication year, e.g. 2026")
    ap.add_argument("--email", default=DEFAULT_CONTACT, help="contact email (NCBI etiquette)")
    ap.add_argument("--api-key", help="NCBI API key (raises rate limit to 10/s)")
    ap.add_argument("--batch", type=int, default=100, help="PMIDs per efetch call")
    args = ap.parse_args()

    queries = load_queries(args.queries)
    if not queries:
        eprint("No queries found in", args.queries)
        return 2

    # Keyless: 3 req/s -> ~0.34s. With key: 10 req/s -> ~0.11s. Stay polite.
    limiter = RateLimiter(0.11 if args.api_key else 0.34)
    common_params: Dict[str, str] = {"tool": "LitTriage", "email": args.email}
    if args.api_key:
        common_params["api_key"] = args.api_key

    by_id: Dict[str, Dict] = {}
    for i, q in enumerate(queries, 1):
        query = q["query"]
        eprint(f"[{i}/{len(queries)}] esearch: {query}")
        try:
            pmids = esearch(query, args.retmax, args.mindate, args.maxdate,
                            limiter, common_params, args.email)
        except Exception as err:  # noqa: BLE001 — keep going on a single bad query
            eprint(f"  esearch failed: {err}")
            continue
        eprint(f"  {len(pmids)} hits")
        for start in range(0, len(pmids), args.batch):
            chunk = pmids[start:start + args.batch]
            try:
                xml_bytes = efetch(chunk, limiter, common_params, args.email)
                recs = parse_efetch(xml_bytes)
            except Exception as err:  # noqa: BLE001
                eprint(f"  efetch failed for {len(chunk)} ids: {err}")
                continue
            for rec in recs:
                existing = by_id.get(rec["id"])
                if existing:
                    if query not in existing["queries"]:
                        existing["queries"].append(query)
                else:
                    rec["queries"] = [query]
                    by_id[rec["id"]] = rec

    n = write_jsonl(args.out, by_id.values())
    eprint(f"Wrote {n} unique PubMed records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
