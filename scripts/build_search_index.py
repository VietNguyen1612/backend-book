#!/usr/bin/env python3
"""Generate the client-side search index (assets/search-index.json).

GitHub Pages does not allow custom Jekyll plugins, so the index is built here
from the Markdown sources and committed. CI re-runs this with --check to fail
if the committed index is stale.

Each entry is {"title", "url", "body"}:
  * url is a plain root-relative path (".md" -> ".html"; README -> index.html)
    so it resolves from /search.html regardless of the site's baseurl.
  * body is the prose with code blocks and Markdown syntax stripped.

Usage:
    python scripts/build_search_index.py            # write the index
    python scripts/build_search_index.py --check     # fail if stale (CI)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

OUT = "assets/search-index.json"
FENCE = re.compile(r"```.*?```", re.DOTALL)
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def sources() -> list[str]:
    files = sorted(glob.glob("chapters/**/*.md", recursive=True))
    if os.path.exists("README.md"):
        files.insert(0, "README.md")
    return files


def to_url(path: str) -> str:
    path = path.replace(os.sep, "/")
    if path == "README.md":
        return "index.html"
    return path[:-3] + ".html" if path.endswith(".md") else path


def clean_body(text: str) -> str:
    text = FENCE.sub(" ", text)                 # drop code samples
    text = LINK.sub(r"\1", text)                # links -> link text
    text = re.sub(r"^\[Back to .*$", " ", text, flags=re.MULTILINE)  # nav line
    text = re.sub(r"[#>*_`|]", " ", text)       # markdown punctuation
    text = re.sub(r"\s+", " ", text)            # collapse whitespace
    return text.strip()


def title_of(text: str, path: str) -> str:
    m = HEADING.search(text)
    return m.group(1).strip() if m else os.path.basename(path)


def build() -> str:
    index = []
    for path in sources():
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        index.append({
            "title": title_of(raw, path),
            "url": to_url(path),
            "body": clean_body(raw),
        })
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    data = build()
    if "--check" in sys.argv[1:]:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != data:
            print(f"{OUT} is stale. Run: python scripts/build_search_index.py")
            return 1
        print(f"{OUT} is up to date ({data.count(chr(10))} lines).")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    print(f"Wrote {OUT} with {len(json.loads(data))} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
