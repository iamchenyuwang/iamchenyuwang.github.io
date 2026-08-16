#!/usr/bin/env python3
"""Add newly discovered Chenyu Wang publications to the homepage.

The arXiv author search contains many researchers with the same name. To avoid
publishing someone else's work, a result is accepted only when it contains the
exact author name and at least one trusted collaborator from Chenyu's existing
publication record. Existing titles are normalized and de-duplicated.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = "http://www.w3.org/2005/Atom"
SITE_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = SITE_ROOT / "index.html"

# A conservative identity check for the many researchers named Chenyu Wang.
# Keep this list in normalized form and extend it when a new collaboration starts.
TRUSTED_COAUTHORS = {
    "vijay janapa reddi",
    "vijay reddi",
    "yilun du",
    "zishen wan",
    "tushar krishna",
    "jiahe caroline shi",
    "jiahe shi",
    "jeffrey ma",
    "jeffrey jian ma",
    "shvetank prakash",
    "andrew cheng",
    "andy cheng",
    "arya tschand",
    "zhenting qi",
    "hao kang",
    "emma chen",
    "zhiqiang xie",
    "zhenhua zhu",
    "xuefei ning",
    "yu wang",
    "yihan wang",
    "kai li",
    "zhen dong",
    "daquan zhou",
    "hanbo sun",
}


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    authors: tuple[str, ...]
    published: datetime

    @property
    def year(self) -> int:
        return self.published.year

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def fetch_arxiv_papers() -> list[Paper]:
    params = urllib.parse.urlencode(
        {
            "search_query": 'au:"Chenyu Wang"',
            "start": 0,
            "max_results": 200,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    request = urllib.request.Request(
        f"{ARXIV_API}?{params}",
        headers={
            "User-Agent": "iamchenyuwang-site/1.0 (mailto:chenyu_wang@seas.harvard.edu)"
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        root = ET.parse(response).getroot()

    papers: list[Paper] = []
    namespace = {"atom": ARXIV_NS}
    for entry in root.findall("atom:entry", namespace):
        title = " ".join(entry.findtext("atom:title", "", namespace).split())
        entry_id = entry.findtext("atom:id", "", namespace)
        arxiv_id = entry_id.rstrip("/").split("/")[-1].split("v")[0]
        published_text = entry.findtext("atom:published", "", namespace)
        authors = tuple(
            author.findtext("atom:name", "", namespace).strip()
            for author in entry.findall("atom:author", namespace)
        )
        if not title or not arxiv_id or not published_text:
            continue
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                published=datetime.fromisoformat(published_text.replace("Z", "+00:00")),
            )
        )
    return papers


def is_verified_author_match(paper: Paper) -> bool:
    normalized_authors = {normalize(author) for author in paper.authors}
    if "chenyu wang" not in normalized_authors:
        return False
    coauthors = normalized_authors - {"chenyu wang"}
    return bool(coauthors & TRUSTED_COAUTHORS)


def existing_titles(document: str) -> set[str]:
    matches = re.findall(
        r'<p class="paper-title">.*?</p>', document, flags=re.IGNORECASE | re.DOTALL
    )
    return {normalize(re.sub(r"<[^>]+>", " ", match)) for match in matches}


def format_authors(authors: tuple[str, ...]) -> str:
    def formatted(name: str) -> str:
        escaped = html.escape(name)
        return f"<strong>{escaped}</strong>" if normalize(name) == "chenyu wang" else escaped

    if len(authors) <= 12:
        return ", ".join(formatted(author) for author in authors)

    selected = list(authors[:6])
    if not any(normalize(author) == "chenyu wang" for author in selected):
        selected.append("Chenyu Wang")
    tail = authors[-1]
    return ", ".join(formatted(author) for author in selected) + f", et al., {formatted(tail)}"


def render_paper(paper: Paper) -> str:
    return (
        "                    <li>\n"
        f'                        <p class="paper-title"><a href="{paper.url}" target="_blank" rel="noopener">{html.escape(paper.title)}</a></p>\n'
        f'                        <p class="authors">{format_authors(paper.authors)}</p>\n'
        f'                        <p class="venue">arXiv preprint, {paper.year}. <a href="{paper.url}" target="_blank" rel="noopener">[paper]</a></p>\n'
        "                    </li>\n"
    )


def insert_papers(document: str, papers: list[Paper]) -> str:
    papers_by_year: dict[int, list[Paper]] = {}
    for paper in papers:
        papers_by_year.setdefault(paper.year, []).append(paper)

    for year in sorted(papers_by_year, reverse=True):
        entries = "".join(
            render_paper(paper)
            for paper in sorted(papers_by_year[year], key=lambda item: item.published, reverse=True)
        )
        year_pattern = re.compile(
            rf'(<div class="year-group">\s*<h3>{year}</h3>\s*<ol class="publication-list">\s*)'
        )
        if year_pattern.search(document):
            document = year_pattern.sub(lambda match: match.group(1) + entries, document, count=1)
            continue

        new_group = (
            '            <div class="year-group">\n'
            f"                <h3>{year}</h3>\n"
            '                <ol class="publication-list">\n'
            f"{entries}"
            "                </ol>\n"
            "            </div>\n\n"
        )
        first_group = '            <div class="year-group">'
        if first_group not in document:
            raise RuntimeError("Could not find the publication year groups in index.html")
        document = document.replace(first_group, new_group + first_group, 1)

    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report additions without editing index.html")
    args = parser.parse_args()

    document = INDEX_PATH.read_text(encoding="utf-8")
    known_titles = existing_titles(document)
    cutoff = datetime.now(timezone.utc) - timedelta(days=730)

    candidates = [
        paper
        for paper in fetch_arxiv_papers()
        if paper.published >= cutoff
        and is_verified_author_match(paper)
        and normalize(paper.title) not in known_titles
    ]

    if not candidates:
        print("No new verified publications found.")
        return 0

    print(f"Found {len(candidates)} new verified publication(s):")
    for paper in candidates:
        print(f"  - {paper.title} ({paper.arxiv_id})")

    if args.dry_run:
        return 0

    updated = insert_papers(document, candidates)
    INDEX_PATH.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Publication update failed: {error}", file=sys.stderr)
        raise
