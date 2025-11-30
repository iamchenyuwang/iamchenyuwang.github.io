#!/usr/bin/env python3
"""
Fetch Google Scholar profile metrics via SerpAPI and write them to
assets/data/scholar_metrics.json so the site can display fresh numbers.

Requirements:
  - SERPAPI_API_KEY environment variable set (GitHub Secret recommended)
  - Internet access from the runner
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import urllib.request
import urllib.parse


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def fetch_author_metrics(author_id: str, api_key: str) -> Dict[str, int]:
    params = {
        "engine": "google_scholar_author",
        "author_id": author_id,
        "hl": "en",
        "api_key": api_key,
    }
    url = f"{SERPAPI_ENDPOINT}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)

    # Defensive parsing for different response shapes
    author = data.get("author", {})
    cited_by = author.get("cited_by", {})

    citations: int | None = None
    h_index: int | None = None
    i10_index: int | None = None

    # Try common shapes
    total = cited_by.get("total")
    if isinstance(total, (int, str)):
        try:
            citations = int(total)
        except Exception:
            pass

    table = cited_by.get("table") or []
    # table is often a list of dicts: [{"citations": {"all": "123"}}, {"h_index": {"all": "10"}}, {"i10_index": {"all": "5"}}]
    def _extract_from_table(key: str) -> int | None:
        for entry in table:
            if key in entry:
                all_val = entry[key].get("all") if isinstance(entry[key], dict) else None
                try:
                    return int(all_val) if all_val is not None else None
                except Exception:
                    return None
        return None

    if citations is None:
        citations = _extract_from_table("citations")
    if h_index is None:
        h_index = _extract_from_table("h_index")
    if i10_index is None:
        i10_index = _extract_from_table("i10_index")

    if citations is None or h_index is None or i10_index is None:
        raise RuntimeError(f"Failed to parse metrics from SerpAPI response: {json.dumps(data)[:500]}...")

    return {"citations": citations, "h_index": h_index, "i10_index": i10_index}


def main() -> int:
    api_key = os.environ.get("SERPAPI_API_KEY")
    author_id = os.environ.get("SCHOLAR_AUTHOR_ID", "QI96hfoAAAAJ")
    if not api_key:
        print("SERPAPI_API_KEY is required", file=sys.stderr)
        return 2

    metrics = fetch_author_metrics(author_id=author_id, api_key=api_key)

    output_path = Path(__file__).resolve().parents[1] / "assets" / "data" / "scholar_metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        **metrics,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Updated {output_path} → {payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


