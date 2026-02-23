#!/usr/bin/env python3
"""
Fetch citation metrics from Semantic Scholar (free, no API key required)
and write them to assets/data/scholar_metrics.json.

Also searches for each known paper title to get per-paper citation counts.
Falls back to SerpAPI if SERPAPI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.parse

# Semantic Scholar author ID for Chenyu Wang
S2_AUTHOR_ID = "2210291379"

# Known paper titles from the publications page — used for per-paper lookup
KNOWN_PAPERS = [
    "Slm-mux: Orchestrating small language models for reasoning",
    "QuArch: A Benchmark for Evaluating LLM Reasoning in Computer Architecture",
    "Optimizing Efficiency of Cognitive Agents With Improved Performance",
    "Evaluating Zero-Shot Long-Context LLM Compression",
    "EPIM: Efficient Processing-In-Memory Accelerators based on Epitome",
    "Gibbon: An Efficient Co-Exploration Framework of NN Model and Processing-In-Memory Architecture",
    "Gibbon: Efficient Co-Exploration of NN Model and Processing-In-Memory Architecture",
    "DeepGuiser: Learning to disguise neural architectures for impeding adversarial transfer attacks",
]


def _api_get(url: str) -> Optional[dict]:
    """GET a JSON endpoint, return parsed dict or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScholarMetricsBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"  Warning: GET {url[:80]}… failed: {e}", file=sys.stderr)
        return None


def fetch_s2_author(author_id: str) -> Dict[str, Any]:
    """Fetch overall author metrics from Semantic Scholar."""
    url = (
        f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
        f"?fields=name,citationCount,hIndex,paperCount"
    )
    data = _api_get(url)
    if not data:
        raise RuntimeError("Failed to fetch Semantic Scholar author profile")

    return {
        "citations": data.get("citationCount", 0),
        "h_index": data.get("hIndex", 0),
        "paper_count": data.get("paperCount", 0),
    }


def fetch_s2_author_papers(author_id: str) -> List[Dict[str, Any]]:
    """Fetch all papers from an author's Semantic Scholar profile."""
    url = (
        f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
        f"?fields=title,citationCount,year&limit=100"
    )
    data = _api_get(url)
    if not data:
        return []
    articles = []
    for paper in data.get("data", []):
        title = paper.get("title", "").strip()
        citations = paper.get("citationCount", 0) or 0
        if title:
            articles.append({"title": title, "citations": citations})
    return articles


def search_s2_paper(title: str) -> Optional[Dict[str, Any]]:
    """Search Semantic Scholar for a paper by title."""
    params = urllib.parse.urlencode({
        "query": title,
        "fields": "title,citationCount,year",
        "limit": "3",
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    data = _api_get(url)
    if not data:
        return None

    # Find best title match
    target = _normalize(title)
    for paper in data.get("data", []):
        candidate = _normalize(paper.get("title", ""))
        if target == candidate or target in candidate or candidate in target:
            return {
                "title": paper.get("title", "").strip(),
                "citations": paper.get("citationCount", 0) or 0,
            }
    return None


def _normalize(s: str) -> str:
    """Normalize a title for comparison."""
    import re
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def compute_i10_index(articles: List[Dict[str, Any]]) -> int:
    """Compute i10-index: number of papers with >= 10 citations."""
    return sum(1 for a in articles if a.get("citations", 0) >= 10)


def main() -> int:
    print("Fetching author metrics from Semantic Scholar...")
    metrics = fetch_s2_author(S2_AUTHOR_ID)
    print(f"  Author metrics: {metrics}")

    # Fetch papers from author profile
    time.sleep(3)  # Rate limit courtesy
    print("Fetching author papers...")
    articles = fetch_s2_author_papers(S2_AUTHOR_ID)
    print(f"  Found {len(articles)} papers from author profile")

    # Also search for known papers that might not be linked to this author profile
    seen_titles = {_normalize(a["title"]) for a in articles}
    for title in KNOWN_PAPERS:
        if _normalize(title) in seen_titles:
            continue
        time.sleep(3)  # Rate limit courtesy
        print(f"  Searching for: {title[:60]}...")
        result = search_s2_paper(title)
        if result:
            articles.append(result)
            seen_titles.add(_normalize(result["title"]))
            print(f"    Found: {result['citations']} citations")
        else:
            print(f"    Not found on Semantic Scholar")

    # Compute i10-index from all articles
    i10_index = compute_i10_index(articles)

    output_path = Path(__file__).resolve().parents[1] / "assets" / "data" / "scholar_metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "citations": metrics["citations"],
        "h_index": metrics["h_index"],
        "i10_index": i10_index,
        "articles": articles,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nUpdated {output_path}")
    print(f"  Citations: {metrics['citations']}, h-index: {metrics['h_index']}, "
          f"i10-index: {i10_index}, articles: {len(articles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
