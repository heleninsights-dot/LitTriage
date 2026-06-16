"""Shared helpers for LitTriage scripts.

Zero external dependencies — stdlib only (urllib). This is deliberate: the whole
skill should run with nothing but a Python 3.9+ interpreter and an internet
connection, so it stays trivially shareable and installable.

Contents:
  - HTTP GET with a polite global rate limiter and exponential-backoff retry.
  - A single normalized paper record schema used by every retrieval source.
  - JSONL read/write helpers.
  - Small text helpers (slugify, LaTeX escaping) used when building outputs.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, Iterator, List, Optional

# A contact string is good etiquette for public APIs (NCBI, OpenAlex). Override
# via the --email flag on the search scripts.
DEFAULT_CONTACT = "litriage-skill@users.noreply.github.com"
USER_AGENT = "LitTriage/0.1 (https://github.com/heleninsights-dot; mailto:%s)" % DEFAULT_CONTACT


class RateLimiter:
    """Enforce a minimum interval between requests (a simple token-free limiter)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        gap = self.min_interval - (now - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


def http_get(
    url: str,
    params: Optional[Dict[str, str]] = None,
    *,
    limiter: Optional[RateLimiter] = None,
    retries: int = 4,
    timeout: float = 30.0,
    contact: str = DEFAULT_CONTACT,
) -> bytes:
    """GET a URL with optional query params, rate limiting and retry.

    Retries on transient HTTP (429, 5xx) and network errors with exponential
    backoff. Raises the last error if all attempts fail.
    """
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    ua = USER_AGENT.replace(DEFAULT_CONTACT, contact)

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            last_err = err
            # 4xx other than 429 are not worth retrying.
            if err.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError) as err:
            last_err = err
        backoff = min(2 ** attempt, 16) + 0.1 * attempt
        eprint(f"  retry {attempt + 1}/{retries} after error: {last_err} (sleep {backoff:.1f}s)")
        time.sleep(backoff)
    assert last_err is not None
    raise last_err


# --------------------------------------------------------------------------- #
# Normalized record schema                                                     #
# --------------------------------------------------------------------------- #

RECORD_FIELDS = [
    "id",          # stable dedup id: doi | pmid | title-hash
    "pmid",
    "doi",
    "title",
    "abstract",
    "journal",
    "year",
    "authors",          # list[str], "Last FM"
    "mesh",             # list[str]
    "publication_types",  # list[str], raw from source
    "source",           # "pubmed" | "openalex"
    "queries",          # list[str], which query variants surfaced this paper
    "url",
]


def make_record(**kwargs) -> Dict:
    """Build a normalized record, filling defaults and computing the dedup id."""
    rec = {f: kwargs.get(f) for f in RECORD_FIELDS}
    rec["authors"] = kwargs.get("authors") or []
    rec["mesh"] = kwargs.get("mesh") or []
    rec["publication_types"] = kwargs.get("publication_types") or []
    rec["queries"] = kwargs.get("queries") or []
    rec["id"] = compute_id(rec)
    return rec


def compute_id(rec: Dict) -> str:
    doi = (rec.get("doi") or "").strip().lower()
    if doi:
        return "doi:" + doi
    pmid = (rec.get("pmid") or "").strip()
    if pmid:
        return "pmid:" + pmid
    return "title:" + normalize_title(rec.get("title") or "")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace — for title-based dedup keys."""
    t = re.sub(r"<[^>]+>", "", title or "")          # strip any markup
    t = re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    return t


# --------------------------------------------------------------------------- #
# JSONL IO                                                                      #
# --------------------------------------------------------------------------- #

def read_jsonl(path: str) -> Iterator[Dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str, records: Iterable[Dict]) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Text helpers for output building                                             #
# --------------------------------------------------------------------------- #

def slugify(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:maxlen].strip("-") or "general"


_LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def latex_escape(text: str) -> str:
    if not text:
        return ""
    out = []
    for ch in text:
        out.append(_LATEX_REPLACEMENTS.get(ch, ch))
    return "".join(out)


def eprint(*args, **kwargs) -> None:
    """Print to stderr so stdout stays clean for piping."""
    print(*args, file=sys.stderr, **kwargs)


def load_queries(path: str) -> List[Dict[str, str]]:
    """Load queries.json. Accepts {"queries":[{query,rationale}|str,...]} or a bare list."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("queries", data) if isinstance(data, dict) else data
    out: List[Dict[str, str]] = []
    for it in items:
        if isinstance(it, str):
            out.append({"query": it, "rationale": ""})
        elif isinstance(it, dict) and it.get("query"):
            out.append({"query": it["query"], "rationale": it.get("rationale", "")})
    return out
