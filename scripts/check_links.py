#!/usr/bin/env python3
"""Verify internal Markdown links resolve.

Checks every relative link in the book's Markdown files:
  * the target file exists (resolved relative to the linking file), and
  * if the link has a #fragment, a heading with that slug exists in the target.

This mirrors how GitHub Pages' jekyll-relative-links plugin resolves the
".md" links the book uses for navigation, so a green run here means the
published site's internal links work. External http(s) links are listed but
not fetched (the book intentionally has none).

Usage:  python scripts/check_links.py
Exit:   0 if all internal links resolve, 1 otherwise.
"""
from __future__ import annotations

import glob
import os
import re
import sys

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"(#{1,6})\s+(.*)")
FENCE_RE = re.compile(r"^\s*```")


def slugify(text: str) -> str:
    text = text.replace("`", "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def norm(path: str) -> str:
    return os.path.normpath(path).replace(os.sep, "/")


def markdown_files() -> list[str]:
    files = sorted(glob.glob("chapters/**/*.md", recursive=True))
    if os.path.exists("README.md"):
        files.append("README.md")
    return files


def collect_anchors(files: list[str]) -> dict[str, set[str]]:
    anchors: dict[str, set[str]] = {}
    for path in files:
        found: set[str] = set()
        in_fence = False
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if FENCE_RE.match(line):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                m = HEADING_RE.match(line)
                if m:
                    found.add(slugify(m.group(2)))
        anchors[norm(path)] = found
    return anchors


def main() -> int:
    files = markdown_files()
    anchors = collect_anchors(files)
    broken: list[tuple[str, str, str]] = []
    external: set[str] = set()
    checked = 0

    for path in files:
        base = os.path.dirname(path)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        # Ignore links that live inside fenced code samples.
        content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        for target in LINK_RE.findall(content):
            target = target.strip().split(" ", 1)[0]  # drop optional "title"
            if target.startswith(("http://", "https://")):
                external.add(target)
                continue
            if target.startswith("mailto:"):
                continue
            if target.startswith("#"):
                if target[1:] and slugify(target[1:]) not in anchors[norm(path)]:
                    broken.append((path, target, "missing same-file anchor"))
                continue
            checked += 1
            filepart, _, frag = target.partition("#")
            if not filepart:
                continue
            resolved = norm(os.path.join(base, filepart))
            if not os.path.exists(resolved):
                broken.append((path, target, f"file not found -> {resolved}"))
            elif frag and resolved in anchors and slugify(frag) not in anchors[resolved]:
                broken.append((path, target, f"missing anchor #{frag} in {resolved}"))

    print(f"Scanned {len(files)} files; checked {checked} internal links; "
          f"{len(external)} external link(s) (not fetched).")
    if broken:
        print(f"\nBROKEN internal links: {len(broken)}")
        for path, target, why in broken:
            print(f"  {path}: [{target}] -> {why}")
        return 1
    print("All internal links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
