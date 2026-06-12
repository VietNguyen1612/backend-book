#!/usr/bin/env python3
"""Verify Markdown code fences are balanced and well-formed.

Catches the specific failure mode where a closing ``` is missing and an
info-string fence (e.g. ```text) opens *inside* an already-open block, which
silently swallows prose and renders output markers as literal code on the
published site. (This class of bug was found in advanced-patterns.md.)

Usage:  python scripts/check_fences.py
Exit:   0 if all fences are balanced, 1 otherwise.
"""
from __future__ import annotations

import glob
import os
import sys


def markdown_files() -> list[str]:
    files = sorted(glob.glob("chapters/**/*.md", recursive=True))
    for extra in ("README.md", "AUDIT.md"):
        if os.path.exists(extra):
            files.append(extra)
    return files


def main() -> int:
    problems = 0
    for path in markdown_files():
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        in_fence = False
        opened_at = 0
        for i, raw in enumerate(lines, 1):
            stripped = raw.lstrip()
            if stripped.startswith("```"):
                info = stripped[3:].strip()
                if not in_fence:
                    in_fence, opened_at = True, i
                else:
                    if info:
                        print(f"{path}:{i}: info-string fence '```{info}' opened "
                              f"inside the block opened at line {opened_at}")
                        problems += 1
                    in_fence = False
        if in_fence:
            print(f"{path}: file ends inside a code block opened at line {opened_at}")
            problems += 1

    if problems:
        print(f"\nTotal fence problems: {problems}")
        return 1
    print("All code fences are balanced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
