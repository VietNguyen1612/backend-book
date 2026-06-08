#!/usr/bin/env python3
"""Verify every section file carries a "Last reviewed" date stamp.

Each section file (chapters/NN-*/<name>.md, excluding README.md) should end
with a footer line of the form:

    *Last reviewed: YYYY-MM-DD*

Run `python scripts/stamp_reviewed.py YYYY-MM-DD [files...]` to add or update
stamps. This checker only validates presence and format (and, with --max-age-days,
warns about stamps older than a threshold). It never fails on staleness unless
--fail-stale is given, so it is safe to run in CI for presence only.

Usage:
    python scripts/check_last_reviewed.py
    python scripts/check_last_reviewed.py --max-age-days 365 --fail-stale --today 2026-06-08
Exit:   0 if every section file has a valid stamp (and, with --fail-stale, none
        are stale), 1 otherwise.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import sys

STAMP_RE = re.compile(r"[_*]Last reviewed:\s*(\d{4}-\d{2}-\d{2})[_*]")


def section_files() -> list[str]:
    out = []
    for p in sorted(glob.glob("chapters/*/*.md")):
        if os.path.basename(p) != "README.md":
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=None)
    ap.add_argument("--fail-stale", action="store_true")
    ap.add_argument("--today", default=None,
                    help="YYYY-MM-DD reference date (default: skip age check)")
    args = ap.parse_args()

    today = None
    if args.today:
        today = dt.date.fromisoformat(args.today)

    missing: list[str] = []
    stale: list[str] = []
    ok = 0
    for path in section_files():
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        m = STAMP_RE.search(text)
        if not m:
            missing.append(path)
            continue
        ok += 1
        if today and args.max_age_days is not None:
            stamped = dt.date.fromisoformat(m.group(1))
            if (today - stamped).days > args.max_age_days:
                stale.append(f"{path} (reviewed {m.group(1)})")

    print(f"{ok} section file(s) carry a valid Last-reviewed stamp.")
    rc = 0
    if missing:
        print(f"\nMissing/invalid stamp: {len(missing)}")
        for p in missing:
            print(f"  - {p}")
        rc = 1
    if stale:
        print(f"\nStale (> {args.max_age_days} days): {len(stale)}")
        for p in stale:
            print(f"  - {p}")
        if args.fail_stale:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
