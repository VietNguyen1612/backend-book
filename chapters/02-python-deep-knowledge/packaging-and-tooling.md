[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.4 Packaging & Tooling

## Dependency Management

### `pyproject.toml`: The Modern Standard

`pyproject.toml` (PEP 621) is the standard for declaring Python project metadata, dependencies, build configuration, and tool settings -- all in one file.

```toml
# pyproject.toml -- complete example

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "myproject"
version = "1.0.0"
description = "A well-configured Python project"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "Alice Developer", email = "alice@example.com"},
]
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "sqlalchemy>=2.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "mypy>=1.5",
    "ruff>=0.1.0",
]
docs = [
    "mkdocs>=1.5",
    "mkdocs-material>=9.0",
]

[project.scripts]
myproject = "myproject.cli:main"

# -- Tool configuration in the same file --

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"
```

### Poetry vs pip-tools vs uv

```bash
# -- Poetry: full dependency management --
# Install:
curl -sSL https://install.python-poetry.org | python3 -

# Create project:
poetry new myproject
cd myproject

# Add dependencies:
poetry add fastapi uvicorn
poetry add --group dev pytest mypy ruff

# Lock and install:
poetry lock          # Generate poetry.lock (exact versions)
poetry install       # Install from lock file

# Run commands in the virtualenv:
poetry run python main.py
poetry run pytest

# -- pip-tools: lightweight locking --
# Install:
pip install pip-tools

# Create requirements.in (loose constraints):
# requirements.in:
#   fastapi>=0.100
#   uvicorn

# Generate locked requirements:
pip-compile requirements.in -o requirements.txt
# Produces requirements.txt with exact versions + all transitive deps

# Install exactly what's locked:
pip-sync requirements.txt

# -- uv: blazing fast (Rust-based) --
# Install:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project:
uv init myproject
cd myproject

# Add dependencies:
uv add fastapi uvicorn
uv add --dev pytest mypy

# Lock and sync:
uv lock              # Generate uv.lock
uv sync              # Install from lock file

# Run:
uv run python main.py
uv run pytest

# uv is 10-100x faster than pip for resolution and installation
# It's becoming the recommended tool for new projects
```

### Virtual Environments

```python
# -- Always use virtual environments! --

# Create with venv (stdlib):
# $ python -m venv .venv

# Activate:
# Linux/Mac: source .venv/bin/activate
# Windows:   .venv\Scripts\activate

# Or use uv (handles venvs automatically):
# $ uv run python main.py  # Creates .venv if needed

# -- Why virtual environments matter --
# Without venv: all projects share global packages
#   Project A needs django==4.2
#   Project B needs django==5.0  --> CONFLICT!
#
# With venv: each project has isolated packages
#   Project A/.venv/  --> django==4.2
#   Project B/.venv/  --> django==5.0  --> No conflict!

# -- .gitignore: never commit your venv --
# .venv/
# __pycache__/
# *.pyc
# .mypy_cache/
# .ruff_cache/
```

> **Key Takeaway:** Use `pyproject.toml` for all project configuration. Choose `uv` for new projects (fastest), `poetry` for established workflows, or `pip-tools` for minimal overhead. Always use virtual environments, never install packages globally.

---

## Code Quality

### Ruff: The All-in-One Linter and Formatter

Ruff is a Rust-based tool that replaces flake8, isort, pyupgrade, black (formatting), and dozens of other linting tools. It is 10-100x faster than the tools it replaces.

```bash
# Install:
pip install ruff
# or: uv tool install ruff

# Lint:
ruff check .                    # Check for issues
ruff check --fix .              # Auto-fix what's possible
ruff check --select ALL .       # Enable ALL rules (educational!)

# Format (replaces black):
ruff format .
ruff format --check .           # Check without modifying

# Configuration in pyproject.toml:
```

Running `ruff check .` on a project with issues prints something like:

```console
$ ruff check .
app/handlers.py:12:1: F401 [*] `os` imported but unused
app/handlers.py:45:5: B006 Do not use mutable data structures for argument defaults
app/models.py:8:1: I001 [*] Import block is un-sorted or un-formatted
Found 3 errors.
[*] 2 fixable with the `--fix` option.
```

**What's happening:** Each line is `file:line:col: RULE message`. The `[*]` marker means ruff can auto-fix it (`ruff check --fix .` would rewrite those two). Codes map to the rule families you enabled in `select` -- `F401` is pyflakes (dead import), `B006` is bugbear (the mutable-default bug), `I001` is isort. In CI this command's non-zero exit code is what fails the build, which is exactly why you wire it into pre-commit and your pipeline rather than relying on developers to run it.

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort (import sorting)
    "N",    # pep8-naming
    "UP",   # pyupgrade (modernize syntax)
    "B",    # flake8-bugbear (common bugs)
    "SIM",  # flake8-simplify
    "ASYNC",# flake8-async
    "S",    # bandit (security)
]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests
```

```python
# Examples of what ruff catches:

# UP: pyupgrade -- modernize syntax
# BAD (old style):
from typing import Optional, List, Dict
x: Optional[int] = None
y: List[Dict[str, int]] = []

# GOOD (modern, ruff --fix auto-converts):
x: int | None = None
y: list[dict[str, int]] = []

# B: bugbear -- common mistakes
# BAD: mutable default argument
def append_to(item, target=[]):  # Bug! Shared across calls
    target.append(item)
    return target

# GOOD:
def append_to(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target

# SIM: simplify -- cleaner code
# BAD:
if x == True:
    pass
# GOOD:
if x:
    pass

# BAD:
if len(my_list) > 0:
    pass
# GOOD:
if my_list:
    pass
```

### Pre-commit: Automated Quality Gates

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: detect-private-key
```

```bash
# Install pre-commit:
pip install pre-commit

# Install hooks:
pre-commit install

# Now every git commit automatically runs:
#   1. ruff (lint + fix)
#   2. ruff format
#   3. mypy (type checking)
#   4. Trailing whitespace removal, etc.

# Run on all files manually:
pre-commit run --all-files
```

A `pre-commit run --all-files` invocation prints one line per hook:

```console
$ pre-commit run --all-files
ruff.....................................................................Passed
ruff-format..............................................................Passed
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

app/service.py:23: error: Argument 1 to "save" has incompatible type "str"; expected "int"  [arg-type]
Found 1 error in 1 file (checked 12 source files)

trailing-whitespace......................................................Passed
detect-private-key.......................................................Passed
```

**How to read this output:** Each hook reports `Passed`, `Failed`, or `Skipped`. A single `Failed` hook aborts the whole run with a non-zero exit, which is what blocks the `git commit`. Note that hooks like `ruff --fix` and `trailing-whitespace` *modify your files* when they fail -- you then `git add` the fixes and re-commit. This is the production value of pre-commit: bad code never reaches the shared branch, so reviewers spend time on logic rather than on formatting nits.

### pytest: Testing Framework

```python
import pytest
from unittest.mock import Mock, patch

# -- Basic test --
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

# -- Fixtures: dependency injection --
@pytest.fixture
def sample_user():
    return {"id": 1, "name": "Alice", "email": "alice@test.com"}

@pytest.fixture
def db_connection():
    conn = create_connection()
    yield conn  # Test runs here
    conn.close()  # Cleanup after test

def test_get_user(sample_user):
    assert sample_user["name"] == "Alice"

# -- Parametrize: test with multiple inputs --
@pytest.mark.parametrize("input_val, expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
    ("123", "123"),
    ("Hello World", "HELLO WORLD"),
])
def test_uppercase(input_val, expected):
    assert input_val.upper() == expected

# -- Testing exceptions --
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

# -- Mocking --
def test_api_call():
    with patch("mymodule.requests.get") as mock_get:
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"users": [{"id": 1}]}
        )
        result = fetch_users()
        assert len(result) == 1
        mock_get.assert_called_once()

# -- Markers --
@pytest.mark.slow
def test_large_computation():
    result = compute_heavy(10_000_000)
    assert result > 0

# Run: pytest -m "not slow"  (skip slow tests)

# -- conftest.py: shared fixtures --
# tests/conftest.py
@pytest.fixture(scope="session")
def app():
    """Create application instance for the entire test session."""
    app = create_app(testing=True)
    yield app

@pytest.fixture
def client(app):
    """Create a test client for each test."""
    return app.test_client()

# -- Coverage --
# $ pytest --cov=mypackage --cov-report=html --cov-report=term-missing
# $ open htmlcov/index.html
```

A `pytest --cov` run with `term-missing` ends with a per-file table:

```console
$ pytest --cov=mypackage --cov-report=term-missing
======================== test session starts ========================
collected 14 items

tests/test_users.py ........                                   [ 57%]
tests/test_api.py ......                                        [100%]

---------- coverage: platform linux, python 3.11.6 -----------
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
mypackage/__init__.py         2      0   100%
mypackage/api.py             48      5    90%   31-34, 67
mypackage/users.py           36      0   100%
-------------------------------------------------------
TOTAL                        86      5    94%

========================= 14 passed in 0.42s =========================
```

**How to read this output:** `Stmts` is executable statements, `Miss` is how many were never run by any test, and `Missing` lists the exact line numbers -- so `api.py` lines 31-34 and 67 are untested. The `Missing` column is the actionable part: it tells you *which branches* to write tests for, far more useful than a single percentage. A common interview point: high coverage proves lines were *executed*, not that behavior was *asserted* -- you can hit 100% with tests that assert nothing, so treat coverage as a floor, not a quality guarantee.

> **Key Takeaway:** Use `ruff` for linting and formatting (replaces multiple tools), `pre-commit` to enforce quality on every commit, and `pytest` with fixtures, parametrize, and coverage for thorough testing. Automate everything -- quality checks that require manual effort do not get done consistently.

---

## Profiling & Optimization

### cProfile: Function-Level Profiling

Always profile before optimizing. Intuition about performance bottlenecks is often wrong.

```python
import cProfile
import pstats
import io

# -- Basic profiling --
def slow_function():
    total = 0
    for i in range(1_000_000):
        total += i ** 0.5
    return total

def medium_function():
    return [i * 2 for i in range(100_000)]

def main():
    slow_function()
    medium_function()
    slow_function()

# Method 1: command line
# $ python -m cProfile -s cumulative main.py

# Method 2: programmatic
profiler = cProfile.Profile()
profiler.enable()
main()
profiler.disable()

# Print results sorted by cumulative time
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream).sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
print(stream.getvalue())

# Output looks like:
#    ncalls  tottime  percall  cumtime  percall filename:lineno(function)
#         2    3.456    1.728    3.456    1.728  <script>:slow_function
#         1    0.012    0.012    0.012    0.012  <script>:medium_function
#         1    0.000    0.000    3.468    3.468  <script>:main

# Method 3: save for visualization
profiler.dump_stats("profile_output.prof")
# $ snakeviz profile_output.prof  (opens interactive flame chart in browser)
# $ pip install snakeviz

# -- Context manager for profiling specific sections --
from contextlib import contextmanager

@contextmanager
def profile_section(label="section"):
    profiler = cProfile.Profile()
    profiler.enable()
    yield
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    print(f"\n--- Profile: {label} ---")
    stats.print_stats(10)

with profile_section("data processing"):
    data = [i ** 2 for i in range(1_000_000)]
    filtered = [x for x in data if x % 2 == 0]
```

Running the `profile_section` context manager prints something like (exact times vary by machine):

```text
--- Profile: data processing ---
         4 function calls in 0.118 seconds

   Ordered by: cumulative time

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.071    0.071    0.118    0.118 <stdin>:1(<module>)
        1    0.047    0.047    0.047    0.047 <stdin>:2(<listcomp>)
```

**How to read this output:** `tottime` is time spent *inside* a function excluding sub-calls; `cumtime` includes everything it calls. You sort by `cumulative` to find which top-level call dominates, then by `tottime` to find where the CPU is actually burned. In a real service, this is how you isolate "the request handler is slow" down to "the JSON serialization inside it is slow" -- the `cumtime`/`tottime` split is the whole point. The context-manager pattern matters in practice because it lets you profile one suspicious block of a long-running process without restarting it under `-m cProfile`.

> **Common pitfall:** `cProfile` adds per-call overhead (it instruments every function call), so absolute times are inflated and call-heavy code looks disproportionately worse. Use it for *relative* comparison to find hot spots, not for reporting real-world latency -- for that, use a sampling profiler like `py-spy`.

### line_profiler: Line-by-Line Analysis

```python
# Install: pip install line_profiler

# Decorate the function you want to profile:
# (use @profile when running with kernprof)

# mymodule.py
def process_data(items):
    results = []                    # Line 1
    for item in items:              # Line 2 -- how many times?
        cleaned = item.strip()      # Line 3
        if cleaned:                 # Line 4
            parsed = int(cleaned)   # Line 5
            results.append(parsed ** 2)  # Line 6
    return sorted(results)          # Line 7 -- is sorting the bottleneck?

# Run with:
# $ kernprof -l -v mymodule.py
#
# Output:
# Line #  Hits    Time    Per Hit  % Time  Line Contents
# =====================================================
#      1     1      2.0      2.0     0.0   results = []
#      2  1001   1234.0      1.2     2.1   for item in items:
#      3  1000   5678.0      5.7     9.5   cleaned = item.strip()
#      4  1000    890.0      0.9     1.5   if cleaned:
#      5   950  12345.0     13.0    20.7   parsed = int(cleaned)
#      6   950  23456.0     24.7    39.3   results.append(parsed ** 2)
#      7     1  16000.0  16000.0    26.8   return sorted(results)
#
# Insight: sorting (line 7) and appending (line 6) are the bottlenecks!
```

### py-spy: Sampling Profiler (No Code Changes)

```bash
# Install: pip install py-spy

# Profile a running script:
py-spy record -o profile.svg -- python myapp.py

# Attach to a running process:
py-spy record -o profile.svg --pid 12345

# Top-like live view:
py-spy top --pid 12345

# Generate flame graph:
py-spy record -o flamegraph.svg --format speedscope -- python myapp.py
# Open flamegraph.svg in a browser

# py-spy advantages:
# - No code modification needed
# - Attach to running production processes
# - Very low overhead (sampling, not tracing)
# - Shows time spent in C extensions too
```

### Optimization: A Practical Approach

```python
import time

# RULE 1: Profile first, optimize later

# RULE 2: Algorithmic improvements >> micro-optimization

# BAD: O(n^2) -- checking membership in a list
def find_duplicates_slow(items):
    """O(n^2) -- for each item, scan the whole list."""
    duplicates = []
    for i, item in enumerate(items):
        if item in items[i+1:]:  # O(n) scan for each item!
            if item not in duplicates:
                duplicates.append(item)
    return duplicates

# GOOD: O(n) -- use a set for O(1) lookups
def find_duplicates_fast(items):
    """O(n) -- single pass with set."""
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:     # O(1) lookup!
            duplicates.add(item)
        seen.add(item)
    return list(duplicates)

# Benchmark
items = list(range(10000)) + list(range(5000))
start = time.perf_counter()
find_duplicates_slow(items)
print(f"Slow: {time.perf_counter() - start:.3f}s")

start = time.perf_counter()
find_duplicates_fast(items)
print(f"Fast: {time.perf_counter() - start:.6f}s")
# Slow: ~2.5s, Fast: ~0.001s -- 2500x faster from algorithm change!

# RULE 3: Use built-in functions and data structures
# Built-ins are implemented in C and are much faster than pure Python

# BAD: manual loop
total = 0
for x in range(1_000_000):
    total += x

# GOOD: built-in sum (C implementation)
total = sum(range(1_000_000))

# BAD: manual string concatenation in loop
result = ""
for s in strings:
    result += s  # Creates a new string EVERY iteration: O(n^2)

# GOOD: str.join (single allocation)
result = "".join(strings)  # O(n)

# RULE 4: Use __slots__ for memory-heavy classes (see Data Model section)

# RULE 5: Use NumPy for numerical work
import numpy as np

# BAD: pure Python
data = list(range(1_000_000))
result = [x ** 2 + 2 * x + 1 for x in data]  # ~200ms

# GOOD: NumPy (vectorized C operations)
data = np.arange(1_000_000)
result = data ** 2 + 2 * data + 1  # ~5ms -- 40x faster

# RULE 6: Use local variables in hot loops
# Local variable lookup is faster than global/attribute lookup
import math

# SLOWER: attribute lookup every iteration
def compute_slow(values):
    result = []
    for v in values:
        result.append(math.sqrt(v))  # 'math.sqrt' = 2 lookups per call
    return result

# FASTER: localize the function reference
def compute_fast(values):
    sqrt = math.sqrt  # One lookup, then it's a local variable
    append = [].append
    result = []
    _append = result.append
    for v in values:
        _append(sqrt(v))  # Local lookup only
    return result

# FASTEST: list comprehension (dedicated bytecode, implicit optimization)
def compute_fastest(values):
    return [math.sqrt(v) for v in values]
```

```
  Optimization Decision Flowchart
  ================================

  Is it slow?
    |
    +--No--> Don't optimize. Ship it.
    |
    +--Yes-> Profile it (cProfile / py-spy)
              |
              v
          Identify the bottleneck (top 1-2 functions)
              |
              v
          Can you fix the algorithm? (O(n^2) -> O(n log n)?)
            |
            +--Yes--> Fix algorithm. Done. (biggest win)
            |
            +--No---> Can you use built-ins/numpy? (C-speed)
                        |
                        +--Yes--> Use them. Done.
                        |
                        +--No---> Micro-optimize (locals, __slots__)
                                    |
                                    v
                                Still not enough?
                                    |
                                    +--No--> Done.
                                    |
                                    +--Yes--> C extension / Cython / Rust (pyo3)
```

> **Key Takeaway:** Always profile before optimizing -- your intuition about bottlenecks is usually wrong. Use `cProfile` to find hot functions, `line_profiler` to find hot lines, and `py-spy` for production profiling. Algorithmic improvements give the biggest gains. Use built-in functions, `str.join`, and NumPy before reaching for C extensions.

---

## Standard Library Essentials

Beyond third-party tooling, two stdlib areas separate throwaway scripts from production services: structured **logging** and safe **filesystem/process** interaction.

### Logging: Never `print` in Production

`print` writes to stdout with no levels, no timestamps, no routing, and no way to silence it per-module. The `logging` module gives you a hierarchy of named loggers, *handlers* (where logs go), *formatters* (how they look), and *levels* (DEBUG/INFO/WARNING/ERROR/CRITICAL).

```python
import logging
import logging.config

# -- Configure ONCE at app startup with dictConfig --
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
})

# -- Module-level logger named after the module path --
logger = logging.getLogger(__name__)   # e.g. "myapp.billing.charge"

def charge(user_id, cents):
    # Lazy %-formatting: the string is only built if INFO is enabled.
    logger.info("charging user %s for %s cents", user_id, cents)
    try:
        if cents < 0:
            raise ValueError("negative amount")
    except ValueError:
        # logger.exception() logs the message AND the traceback, at ERROR level.
        logger.exception("charge failed for user %s", user_id)

charge(42, 1500)
charge(7, -3)
```

```text
2026-06-08 09:15:02,331 INFO myapp.billing: charging user 42 for 1500 cents
2026-06-08 09:15:02,332 INFO myapp.billing: charging user 7 for -3 cents
2026-06-08 09:15:02,332 ERROR myapp.billing: charge failed for user 7
Traceback (most recent call last):
  File "billing.py", line 24, in charge
    raise ValueError("negative amount")
ValueError: negative amount
```

**How to read this output:** Every line carries a timestamp, level, and logger *name* — the name is `myapp.billing` because `getLogger(__name__)` inherits the module path, which lets you later raise just that subsystem to DEBUG without touching the rest of the app. The `logger.exception(...)` call produced both the message *and* the full traceback at ERROR level; this is the correct way to log a caught exception (calling it outside an `except` block logs "NoneType: None"). The `%s` placeholders use lazy formatting: if the level were above INFO, the interpolation would be skipped entirely — measurably cheaper than an f-string that always builds the string even when the log is discarded.

The big rules: configure logging exactly once at startup (libraries should *only* `getLogger`, never configure); for production, emit **structured** logs (a JSON formatter or `structlog`) and attach request context (`request_id`, `user_id`) via `contextvars` so it follows the request across `await` points and threads; and **never log secrets or PII** (tokens, passwords, card numbers) — logs are widely readable and long-lived.

### Filesystem, Processes & OS Interaction

```python
from pathlib import Path
import subprocess
import os, tempfile

# -- pathlib.Path: object-oriented paths (prefer over os.path string juggling) --
config = Path.home() / ".config" / "myapp" / "settings.toml"
print(config.exists(), config.suffix, config.parent.name)
# config.read_text(encoding="utf-8"); config.write_text(...); Path(".").glob("*.py")

# -- subprocess.run: the right way to shell out --
result = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],   # args as a LIST, not a string
    check=True,            # raise CalledProcessError on non-zero exit
    capture_output=True,   # capture stdout/stderr
    text=True,             # decode bytes -> str
    timeout=10,
)
print(result.stdout.strip())
# NEVER do subprocess.run(f"git log {user_input}", shell=True) with untrusted
# input -> shell injection. Pass a list and shell=False (the default).

# -- Atomic write: write to a temp file, then os.replace (atomic on same fs) --
def atomic_write(path: Path, data: str):
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)   # atomic rename: readers never see a half file
    except BaseException:
        os.unlink(tmp)
        raise
```

```text
True .toml myapp
a1b2c3d
```

**How to read this output:** `pathlib` turns path manipulation into typed object operations — `config.suffix` (`.toml`) and `config.parent.name` (`myapp`) replace brittle string splitting and work identically across OSes (the `/` operator emits the right separator). The `subprocess.run` line returned the short commit hash because `check=True` would have raised on failure and `capture_output=True, text=True` handed back decoded stdout; passing the command as a *list* with the default `shell=False` is what makes it injection-proof — there is no shell to interpret metacharacters in user input. The atomic-write helper exists because a plain `open(path, "w")` truncates the file *first*, so a crash mid-write leaves a corrupted file; writing to a temp file and `os.replace`-ing it means any reader sees either the complete old file or the complete new one, never a partial one.

For configuration and CLIs: `argparse` (stdlib) handles command-line parsing (or `click`/`typer` for richer interfaces); `tomllib` (stdlib, 3.11+) reads TOML config (read-only), and `configparser` reads INI-style files. Use `os`/`shutil` for environment variables and high-level file operations (`shutil.copy`, `shutil.rmtree`), and `tempfile` for scratch files that clean themselves up.

> **Key Takeaway:** Replace `print` with a configured `logging` setup (module loggers, lazy `%s` formatting, `logger.exception()` for tracebacks, structured logs in prod, no secrets). Use `pathlib.Path` over `os.path`, call external programs with `subprocess.run([...], check=True)` and never `shell=True` on untrusted input, and make file writes crash-safe with a temp file plus atomic `os.replace`.

*Last reviewed: 2026-06-08*
