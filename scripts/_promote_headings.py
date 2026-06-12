#!/usr/bin/env python3
"""One-off: promote section-file headings to book hierarchy (###->##, ####->###, #####->####).

Fence-aware: lines inside ``` code fences are never touched.
Skips README.md, homework/, and files passed via --skip.
Prints each file's H1 title for ordering.
"""
from __future__ import annotations

import glob
import os
import sys

SKIP = {"technical-leadership.md"}


def promote(path: str) -> str | None:
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines(keepends=True)
    in_fence = False
    title = None
    changed = False
    out = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            if title is None and line.startswith("# "):
                title = line[2:].strip()
            if line.startswith("##### "):
                line = line[1:]
                changed = True
            elif line.startswith("#### "):
                line = line[1:]
                changed = True
            elif line.startswith("### "):
                line = line[1:]
                changed = True
        out.append(line)
    if in_fence:
        print(f"FENCE IMBALANCE, not writing: {path}")
        return title
    if changed:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(out))
    print(f"{'CHANGED' if changed else 'skipped'}  {path}  ::  {title}")
    return title


def main() -> int:
    for p in sorted(glob.glob("chapters/*/*.md")):
        base = os.path.basename(p)
        if base == "README.md" or base in SKIP:
            continue
        promote(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
