#!/usr/bin/env python3
"""Gate an automated edit to index.html before it is published.

Usage: validate_publication_diff.py CURRENT_INDEX PROPOSED_INDEX OUTPUT_PATH

The monthly publication agent works on untrusted web content, so its edit is
treated as untrusted too. The proposed page is accepted only when:

* everything outside the News and Publications sections is byte-identical;
* those sections use only the markup vocabulary the page already uses
  (no scripts, styles, embeds, forms, event handlers, or non-HTTPS links);
* the change is small enough to be a few papers or news items.

On success the validated bytes are written to OUTPUT_PATH and the exit status
is 0. Otherwise the reasons are printed and the exit status is 1.
"""

from __future__ import annotations

import difflib
import os
import re
import stat
import sys
from html.parser import HTMLParser

REGION_START = '<section class="section" id="news"'
REGION_END = '<section class="section" id="service"'

ALLOWED_TAGS = {
    "section", "h2", "h3", "ul", "ol", "li", "div", "p",
    "span", "a", "strong", "em", "time", "br",
}
VOID_TAGS = {"br"}
ALLOWED_ATTRIBUTES = {
    "class", "id", "href", "target", "rel", "datetime", "aria-labelledby",
}
MAX_FILE_BYTES = 512 * 1024
MAX_ADDED_LINES = 80
MAX_REMOVED_LINES = 40
SUSPICIOUS_CHARACTERS = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f‪-‮⁦-⁩]"
)


class RegionChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.open_tags: list[str] = []

    def error_at(self, message: str) -> None:
        line, _ = self.getpos()
        self.errors.append(f"line {line} of the edited region: {message}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self.error_at(f"tag <{tag}> is not allowed")
        values = {}
        for name, value in attrs:
            value = (value or "").strip()
            values[name] = value
            if name not in ALLOWED_ATTRIBUTES:
                self.error_at(f"attribute {name!r} on <{tag}> is not allowed")
            if name == "href" and not (value.startswith("https://") or value.startswith("#")):
                self.error_at(f"link {value!r} is not an https:// or in-page link")
            if name == "target" and value != "_blank":
                self.error_at(f"target {value!r} is not allowed")
        if values.get("target") == "_blank" and "noopener" not in values.get("rel", "").split():
            self.error_at("links that open a new tab must use rel=\"noopener\"")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS and self.open_tags and self.open_tags[-1] == tag:
            self.open_tags.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if not self.open_tags or self.open_tags[-1] != tag:
            self.error_at(f"unbalanced closing tag </{tag}>")
            return
        self.open_tags.pop()

    def handle_comment(self, data: str) -> None:
        self.error_at("HTML comments are not allowed")

    def handle_decl(self, decl: str) -> None:
        self.error_at("declarations are not allowed")

    def handle_pi(self, data: str) -> None:
        self.error_at("processing instructions are not allowed")

    def unknown_decl(self, data: str) -> None:
        self.error_at("CDATA or unknown declarations are not allowed")


def read_regular_file(path: str) -> str:
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{path} is not a regular file")
    if info.st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path} is larger than {MAX_FILE_BYTES} bytes")
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def split_page(text: str) -> tuple[str, str, str]:
    if text.count(REGION_START) != 1 or text.count(REGION_END) != 1:
        raise ValueError("the News or Service section marker is missing or duplicated")
    start = text.index(REGION_START)
    end = text.index(REGION_END)
    if end < start:
        raise ValueError("the Service section appears before the News section")
    return text[:start], text[start:end], text[end:]


def validate(current: str, proposed: str) -> list[str]:
    errors: list[str] = []
    try:
        current_head, current_region, current_tail = split_page(current)
        proposed_head, proposed_region, proposed_tail = split_page(proposed)
    except ValueError as exc:
        return [str(exc)]

    if proposed_head != current_head:
        errors.append("content before the News section changed")
    if proposed_tail != current_tail:
        errors.append("content from the Service section onward changed")
    if SUSPICIOUS_CHARACTERS.search(proposed_region):
        errors.append("the edited region contains control or bidirectional-override characters")

    diff = list(difflib.unified_diff(
        current_region.splitlines(), proposed_region.splitlines(), lineterm="", n=0
    ))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    if added > MAX_ADDED_LINES:
        errors.append(f"{added} lines added; the limit is {MAX_ADDED_LINES}")
    if removed > MAX_REMOVED_LINES:
        errors.append(f"{removed} lines removed; the limit is {MAX_REMOVED_LINES}")

    checker = RegionChecker()
    checker.feed(proposed_region)
    checker.close()
    errors.extend(checker.errors)
    if checker.open_tags:
        errors.append("unclosed tags in the edited region: " + ", ".join(checker.open_tags))
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    current_path, proposed_path, output_path = argv[1:]
    try:
        current = read_regular_file(current_path)
        proposed = read_regular_file(proposed_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"REJECTED: {exc}")
        return 1

    errors = validate(current, proposed)
    if errors:
        print("REJECTED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(proposed)
    print("ACCEPTED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
