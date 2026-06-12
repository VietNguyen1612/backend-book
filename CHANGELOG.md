# Changelog

All notable changes from the audit & improvement pass. Dates are absolute.

## [Unreleased] — 2026-06-12

### Reverted — Gemini "mental model" pass

- Reverted the four 2026-06-12 commits (`9647857`, `6bcaab4`, `94b2620`, `caba46c`) that scattered "Beginner's Mental Model" analogy callouts across 32 files and then duplicated the same analogies again as prose paragraphs (often back-to-back with the callout, sometimes under the wrong heading — e.g. the system-call restaurant analogy under "I/O Models").

### Book-structure pass (DDIA-style)

- **Heading hierarchy**: all 36 section files promoted from the old H1→H3/H4 convention to proper book hierarchy (H1 title, H2 major sections, H3/H4 subsections); fence-aware, anchors unchanged. Re-enabled markdownlint `MD001` (heading-increment) now that the hierarchy is regular; one heading in 9.1 promoted to H2 to satisfy it ("Testing Trophy vs. Pyramid", which sits before the first H2).
- **Narrative scaffolding** (additive only — no existing prose, code, output blocks, or callouts changed): every section file now has
  - a 2–3 paragraph introduction after the title: production stakes, the questions the section answers, and a roadmap of its H2 sections in order;
  - short bridge paragraphs under H2 sections that previously opened abruptly with a definition/subheading/code (~100 bridges total, only where needed);
  - a closing `## Summary` recapping each section's decision rules, ending with a named hand-off to the next section (chapter-closing files wrap up the chapter; 12.2 closes the book);
  - a `**Next:** [N.M Title](…)` link as the last line, so the book reads front-to-back (12.2 links back to the index).
- **Root README**: chapters grouped into five named parts (I Foundations, II Designing the Backend, III Systems at Scale, IV Quality & Trust, V From Engineer to Architect), each with a short framing paragraph explaining the ordering, plus a "How This Book Is Organized" reading guide.
- Search index regenerated; all checks green: markdownlint 0 errors, ruff clean, links/fences/TOC/stamps pass, index fresh.

### Phase 1 — Known fixes

- **chapters/04…/relational-databases.md**
  - `with_advisory_lock` now uses `@contextlib.contextmanager` (+ `import contextlib`) so it works as a context manager; added a usage example.
  - Corrected Django index version notes: partial-index `condition=` is supported since **Django 2.2** (not 5.0); expression indexes need **Django 4.0+**.
  - Added a caveat that the `pg_stat_bgwriter` columns moved to `pg_stat_checkpointer` / `pg_stat_io` in **PostgreSQL 17+**.
  - Reworded the WAL durability rule: the in-memory page is modified first; the WAL record must be durable before the dirty page is **flushed to disk** (and before COMMIT is acknowledged).
- **Removed** the stale root monolith `backend-developer-knowledge-base.md` (orphaned, divergent duplicate that Jekyll published alongside `chapters/`). Confirmed by you before deletion.

### Phase 2 — Audit fixes (see AUDIT.md for the full list)

- **High-severity code/factual fixes** across ch1–ch11, all verified by execution where applicable, e.g.:
  - ch1: corrected `two_sum_sorted`, `max_non_overlapping`, and KMP example outputs; regenerated the list-growth sample to match the code.
  - ch2: `sys.flags.nogil` → `sysconfig`/`sys._is_gil_enabled`; GC "Collected 4"→"2"; `build-backend` → `setuptools.build_meta`; repaired 3 broken code-fence regions in `advanced-patterns.md`.
  - ch4: `ZRANGEBYSCORE` ordering; ziplist→listpack; ES `freeze`→`searchable_snapshot`; Airflow `RAISE EXCEPTION` → PL/pgSQL `DO` block.
  - ch5: removed invalid `from typing import list`; DataLoader `[1,2,1]`→`[1,2]`; fixed RabbitMQ DLX wiring; Celery `.s()`→`.si()`; PKCE `BASE64URL(SHA256(...))`; added refresh-token `jti`.
  - ch6/7/8/9/11: SSD ratio 1,000x→65x; Prometheus alert `status`→`status_code`; EKS 1.29→1.31; pinned `trivy-action`; removed deprecated Compose `version`; `SECURE_BROWSER_XSS_FILTER` off; zero-padded reset code; test-double count four→five; Hypothesis `categories=`; Pact filename typo; Django `queryset.delete()` signals nuance + `max_connections` wording.
- **Homework:** fixed `hw_patterns.py` `@retry()` import-time `TypeError`.

### Homework consolidation (per your decision)

- Folded the 7 richer "named" skeletons into the `hw_*.py` file each chapter's `questions.md` already referenced, then deleted the redundant named files: `lru_cache.py`, `query_builder.py`, `consistent_hashing.py`, `blue_green.py`, `adr_generator.py`, `n_plus_one.py`, `review_bot.py`. (`hw_leadership.generate_adr` now has the 4th `consequences` param.)
- The 5 *distinct* exercises with no `hw_*` counterpart were kept and given a `questions.md` entry each (no longer orphaned): `custom_orm.py`, `refactoring.py`, `rate_limiter.py` (sliding-window), `secure_app.py`, `test_payment.py`.
- Added missing hint imports/scaffolding to bare stubs (`hw_algorithms`, `hw_async`, `hw_nosql`, `hw_rate_limit`, `hw_observability`).
- Verified: every homework `.py` compiles **and** imports cleanly; `questions.md` ↔ files are perfectly aligned (no dangling references, no unreferenced files); ruff clean.

### Repo hygiene / tooling

- Added **`.markdownlint-cli2.yaml`** tuned to the book's style; auto-fixed 148 whitespace issues. `markdownlint-cli2` now reports 0 errors.
- Added **`ruff.toml`** relaxing `F401/F841/E401` for `chapters/**/homework/**` (intentional scaffolding). `ruff` is clean.
- Added Python artifacts (`__pycache__/`, `*.py[cod]`, `.ruff_cache/`, `.pytest_cache/`) to **.gitignore**.
- Added **AUDIT.md** (full findings report).

### Phase 3 — repo/site features (you selected: all)

- **CI** (`.github/workflows/ci.yml`): on every push & PR, runs markdownlint-cli2, ruff, `py_compile`, and the structure checks below — commands mirror the local runs exactly.
- **Structure check scripts** (`scripts/`): `check_links.py` (internal links + anchors), `check_fences.py` (code-fence balance — catches the bug class found in ch2), `check_toc.py` (README + chapter-README ↔ files, plus questions.md ↔ skeleton alignment), `check_last_reviewed.py` (+ `stamp_reviewed.py` to add/update stamps).
- **"Last reviewed" stamps**: every section file now ends with `*Last reviewed: 2026-06-08*`; `check_last_reviewed.py` verifies presence (and optional staleness).
- **Client-side search**: `search.md` (lunr.js via a pinned CDN) over `assets/search-index.json`, generated by `scripts/build_search_index.py` and kept fresh by a CI freshness check; linked from the README. Uses baseurl-independent relative paths so it works regardless of the deploy prefix.
- Verified locally: markdownlint 0 errors, ruff clean, all `.py` compile, all four check scripts pass, search index fresh, the search page's inline JS passes `node --check`. **Not** verifiable in this environment: the live Jekyll render (no Ruby here) — `search.md` deliberately mirrors the chapter pages' structure (no front matter, relative links) so it renders the same way; verify with `bundle exec jekyll serve` or on the deployed site.

### Phase 3 — new content (you selected: Caching & CDN, WebAuthn/Passkeys)

- **5.4 WebAuthn & Passkeys** (`chapters/05-api-design/webauthn-and-passkeys.md`): the WebAuthn/FIDO2 model, registration (attestation) and authentication (assertion) ceremonies with `py_webauthn` + `@simplewebauthn/browser` snippets, synced vs device-bound passkeys, usernameless login, and the operational gotchas (sign counter, recovery, attestation, RP ID scoping). New homework `hw_webauthn.py` + questions.md entry.
- **6.5 Caching & CDN Deep-Dive** (`chapters/06-system-design/caching-and-cdn.md`): cache hierarchy + effective-latency math, HTTP caching semantics (Cache-Control/validators/`stale-while-revalidate`/Vary), CDN mechanics (PoPs, origin shield, purge vs versioned URLs), invalidation strategies, and stampede (single-flight, XFetch) + hot-key defenses. New homework `hw_caching.py` + questions.md entry.
- Both written in the book's style (ASCII diagrams, "How to read this output", Django notes, Key Takeaway), wired into the root README + chapter READMEs, stamped, and indexed for search. All checks pass.

### Open (awaiting your decision)

- 6 lower-severity audit items left as recommendations (see AUDIT.md, status OPEN).
- Other proposed-but-unselected content gaps remain available to draft on request: Git/version control, LLM/AI integration.
