#!/usr/bin/env python3
"""Verify the table of contents / indexes match the files on disk.

Guards against index drift:
  * every chapter directory has a README and is linked from the root README;
  * every section file (chapters/NN-*/<name>.md, excluding README) is linked
    from BOTH the root README and its own chapter README;
  * every chapter has a homework/questions.md;
  * within each homework/, every .py referenced by questions.md exists and
    every .py present is referenced by questions.md.

Usage:  python scripts/check_toc.py
Exit:   0 if the indexes are consistent with the files, 1 otherwise.
"""
from __future__ import annotations

import glob
import os
import re
import sys

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
PY_REF_RE = re.compile(r"([A-Za-z0-9_]+\.py)")


def norm(path: str) -> str:
    return os.path.normpath(path).replace(os.sep, "/")


def link_targets(md_path: str) -> set[str]:
    """Root-relative, fragment-stripped targets of relative links in a file."""
    base = os.path.dirname(md_path)
    out: set[str] = set()
    with open(md_path, encoding="utf-8") as fh:
        text = re.sub(r"```.*?```", "", fh.read(), flags=re.DOTALL)
    for target in LINK_RE.findall(text):
        target = target.strip().split(" ", 1)[0].split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        out.add(norm(os.path.join(base, target)))
    return out


def main() -> int:
    problems: list[str] = []

    if not os.path.exists("README.md"):
        print("README.md missing")
        return 1
    root_links = link_targets("README.md")

    for chapter in sorted(glob.glob("chapters/*/")):
        chapter = chapter.rstrip("/")
        ch_readme = f"{chapter}/README.md"
        if not os.path.exists(ch_readme):
            problems.append(f"{chapter}: missing README.md")
            ch_links: set[str] = set()
        else:
            ch_links = link_targets(ch_readme)
            if norm(ch_readme) not in root_links:
                problems.append(f"root README does not link to {ch_readme}")

        for section in sorted(glob.glob(f"{chapter}/*.md")):
            if os.path.basename(section) == "README.md":
                continue
            nsec = norm(section)
            if nsec not in root_links:
                problems.append(f"section not listed in root README: {nsec}")
            if nsec not in ch_links:
                problems.append(f"section not listed in {ch_readme}: {nsec}")

        questions = f"{chapter}/homework/questions.md"
        if not os.path.exists(questions):
            problems.append(f"{chapter}: missing homework/questions.md")
            continue
        with open(questions, encoding="utf-8") as fh:
            qtext = fh.read()
        referenced = set(PY_REF_RE.findall(qtext))
        present = {os.path.basename(p)
                   for p in glob.glob(f"{chapter}/homework/*.py")}
        for miss in sorted(referenced - present):
            problems.append(f"{questions}: references missing file {miss}")
        for unref in sorted(present - referenced):
            problems.append(f"{questions}: skeleton not referenced -> {unref}")

    if problems:
        print(f"TOC / index drift: {len(problems)} issue(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("TOC and indexes are consistent with the files on disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
