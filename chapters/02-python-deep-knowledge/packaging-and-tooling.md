[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.4 Packaging & Tooling

### Dependency Management

#### `pyproject.toml`: The Modern Standard

`pyproject.toml` (PEP 621) is the standard for declaring Python project metadata, dependencies, build configuration, and tool settings -- all in one file.

```toml
# pyproject.toml -- complete example

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

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

#### Poetry vs pip-tools vs uv

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

#### Virtual Environments

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

### Code Quality

#### Ruff: The All-in-One Linter and Formatter

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

#### Pre-commit: Automated Quality Gates

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

#### pytest: Testing Framework

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

> **Key Takeaway:** Use `ruff` for linting and formatting (replaces multiple tools), `pre-commit` to enforce quality on every commit, and `pytest` with fixtures, parametrize, and coverage for thorough testing. Automate everything -- quality checks that require manual effort do not get done consistently.

---

### Profiling & Optimization

#### cProfile: Function-Level Profiling

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

#### line_profiler: Line-by-Line Analysis

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

#### py-spy: Sampling Profiler (No Code Changes)

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

#### Optimization: A Practical Approach

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
