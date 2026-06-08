#!/usr/bin/env python3
"""Add or update the "Last reviewed" footer on section files.

Adds (or updates) a footer line:

    *Last reviewed: YYYY-MM-DD*

to each section file (chapters/NN-*/<name>.md, excluding README.md). When a file
already has a stamp, its date is updated in place; otherwise the stamp is
appended as a trailing paragraph.

Usage:
    python scripts/stamp_reviewed.py 2026-06-08            # all section files
    python scripts/stamp_reviewed.py 2026-06-08 a.md b.md  # specific files
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import sys

STAMP_RE = re.compile(r"[_*]Last reviewed:\s*\d{4}-\d{2}-\d{2}[_*]")


def section_files() -> list[str]:
    return [p for p in sorted(glob.glob("chapters/*/*.md"))
            if os.path.basename(p) != "README.md"]


def stamp(path: str, date: str) -> str:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new_line = f"*Last reviewed: {date}*"
    if STAMP_RE.search(text):
        text = STAMP_RE.sub(new_line, text)
        action = "updated"
    else:
        text = text.rstrip("\n") + f"\n\n{new_line}\n"
        action = "added"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return action


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    date = sys.argv[1]
    dt.date.fromisoformat(date)  # validate
    targets = sys.argv[2:] or section_files()
    added = updated = 0
    for path in targets:
        if stamp(path, date) == "added":
            added += 1
        else:
            updated += 1
    print(f"Stamped {len(targets)} file(s): {added} added, {updated} updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
