[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.3 Advanced Patterns

## Decorators & Context Managers

### Function Decorators: Wrapping Behavior

A decorator is a function that takes a function and returns a modified function. Always use `@functools.wraps` to preserve the original function's metadata (`__name__`, `__doc__`, `__module__`).

```python
import functools
import time
import logging

# -- Basic decorator --
def log_calls(func):
    @functools.wraps(func)  # Preserves func.__name__, func.__doc__, etc.
    def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        logging.info(f"{func.__name__} returned {result}")
        return result
    return wrapper

@log_calls
def add(a, b):
    """Add two numbers."""
    return a + b

# Without @functools.wraps:
#   add.__name__ == 'wrapper'  (wrong!)
#   add.__doc__  == None       (wrong!)
# With @functools.wraps:
#   add.__name__ == 'add'      (correct)
#   add.__doc__  == 'Add two numbers.'  (correct)

# -- Decorator factory (decorator that takes arguments) --
def retry(max_attempts=3, delay=1.0, exceptions=(Exception,)):
    """Retry a function on failure."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logging.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}"
                    )
                    if attempt < max_attempts:
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.5, exceptions=(ConnectionError, TimeoutError))
def fetch_from_api(url):
    """Fetch data from unreliable API."""
    import random
    if random.random() < 0.7:
        raise ConnectionError("Connection refused")
    return {"data": "success"}

# -- Timing decorator --
def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper

# -- Cache with TTL --
def cache_result(ttl=300):
    """Cache function results with time-to-live."""
    def decorator(func):
        cache = {}

        @functools.wraps(func)
        def wrapper(*args):
            now = time.time()
            if args in cache:
                result, timestamp = cache[args]
                if now - timestamp < ttl:
                    return result
            result = func(*args)
            cache[args] = (result, now)
            return result

        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    return decorator

@cache_result(ttl=60)
def get_user_profile(user_id):
    """Expensive database query."""
    print(f"Querying database for user {user_id}...")
    return {"id": user_id, "name": "Alice"}

get_user_profile(42)  # Queries database
get_user_profile(42)  # Returns cached result
get_user_profile.cache_clear()  # Manual cache clear
```

Running the cache demo prints only once, even though `get_user_profile(42)` is called twice:

```text
Querying database for user 42...
```

**How to read this output:** The "Querying database" line appears exactly once. The first call is a cache miss, so it runs the body and stores `(result, now)` keyed by `args`; the second call is a cache hit inside the TTL window, so it returns the stored value without touching the database. This is the whole point of memoization — in a real backend, that single suppressed query is a saved round-trip to Postgres on a hot path. After `cache_clear()` the next call would print again.

### Class-Based Decorators

When your decorator needs to maintain state, a class-based decorator is cleaner.

```python
import functools
import time

class RateLimiter:
    """Decorator that limits how often a function can be called."""
    def __init__(self, calls=10, period=60):
        self.calls = calls
        self.period = period
        self.timestamps = []

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remove timestamps outside the window
            self.timestamps = [t for t in self.timestamps if now - t < self.period]
            if len(self.timestamps) >= self.calls:
                wait = self.period - (now - self.timestamps[0])
                raise RuntimeError(
                    f"Rate limit exceeded. Try again in {wait:.1f}s"
                )
            self.timestamps.append(now)
            return func(*args, **kwargs)
        return wrapper

@RateLimiter(calls=5, period=10)
def api_call(endpoint):
    return f"Response from {endpoint}"

# Works for first 5 calls within 10 seconds
for i in range(5):
    print(api_call(f"/endpoint/{i}"))

# 6th call raises RuntimeError: Rate limit exceeded
try:
    api_call("/endpoint/6")
except RuntimeError as e:
    print(e)

# -- Stacking decorators --
@timing
@retry(max_attempts=2)
@log_calls
def unreliable_fetch(url):
    return {"data": "ok"}

# Execution order (bottom to top):
# unreliable_fetch -> log_calls wrapper -> retry wrapper -> timing wrapper
# On the way in, the outermost wrapper (timing) runs first and the innermost
# (log_calls) last, closest to the real call; they unwind in reverse on return.
```

The rate-limiter loop succeeds five times, then the sixth call is rejected:

```text
Response from /endpoint/0
Response from /endpoint/1
Response from /endpoint/2
Response from /endpoint/3
Response from /endpoint/4
Rate limit exceeded. Try again in 9.9s
```

**How to read this output:** The first five calls land inside the `calls=5, period=10` budget and return normally. The sixth finds five timestamps still inside the 10-second window, so it raises instead of calling the wrapped function. The wait time (`~9.9s`) is computed from the oldest timestamp, so it shrinks as older calls age out of the window. Because the state (`self.timestamps`) lives on the `RateLimiter` instance rather than in a closure, every decorated function gets its own independent budget — which is exactly why a class is cleaner than a plain closure here.

> **Common pitfall:** This limiter is not thread-safe. Two threads can both pass the `len(self.timestamps) >= self.calls` check before either appends, letting more calls through than the limit allows. Under real concurrency, guard the timestamp list with a `threading.Lock`.

### Context Managers: Resource Management

Context managers ensure resources are properly cleaned up, even when exceptions occur. They implement the `__enter__` / `__exit__` protocol.

```python
import contextlib
import time
import sqlite3

# -- Class-based context manager --
class Timer:
    """Context manager that times the enclosed block."""
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start
        print(f"Elapsed: {self.elapsed:.4f}s")
        return False  # Don't suppress exceptions

with Timer() as t:
    total = sum(range(1_000_000))
print(f"Result: {total}, Time: {t.elapsed:.4f}s")

# -- Generator-based context manager (simpler) --
@contextlib.contextmanager
def database_transaction(db_path):
    """Manage a database transaction with automatic commit/rollback."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

with database_transaction(":memory:") as cursor:
    cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    cursor.execute("INSERT INTO users VALUES (1, 'Alice')")

# -- contextlib.suppress: ignore specific exceptions --
import os

# Instead of:
try:
    os.remove("temp_file.txt")
except FileNotFoundError:
    pass

# Use:
with contextlib.suppress(FileNotFoundError):
    os.remove("temp_file.txt")

# -- Async context manager --
@contextlib.asynccontextmanager
async def managed_client_session():
    import aiohttp
    session = aiohttp.ClientSession()
    try:
        yield session
    finally:
        await session.close()

# -- ExitStack: dynamic number of context managers --
@contextlib.contextmanager
def open_files(file_paths):
    """Open multiple files, ensuring all are closed even if one fails."""
    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(open(fp)) for fp in file_paths]
        yield files

# All files are guaranteed to be closed when the block exits
```

The `Timer` block prints from `__exit__` first, then the trailing `print` runs (exact timing varies by machine):

```text
Elapsed: 0.0182s
Result: 499999500000, Time: 0.0182s
```

**How to read this output:** The "Elapsed:" line is printed by `__exit__` the moment the `with` block ends — this is the guarantee that makes context managers valuable: the cleanup/measurement code runs deterministically even if the body raises. Because `__exit__` stored the duration on `self`, the value is still readable as `t.elapsed` after the block, which is why both lines show the same time. `__exit__` returns `False`, so any exception inside the block would propagate normally rather than being swallowed — returning `True` from `__exit__` is how you would suppress it. The same protocol underlies `database_transaction`: the generator's code after `yield` (the `commit`) acts as the success path, and the `except`/`finally` act as the error and cleanup paths. Always use `@functools.wraps`, prefer generator-based context managers with `@contextlib.contextmanager` for simplicity, and use `ExitStack` when managing a dynamic number of resources.

---

## Generators & Iterators

### Generator Functions: Lazy Evaluation

Generators produce values on demand using `yield`. They are memory-efficient because they compute one value at a time instead of building an entire collection.

```python
import sys

# -- Memory comparison: list vs generator --
# List: stores ALL values in memory at once
big_list = [x ** 2 for x in range(10_000_000)]
print(f"List: {sys.getsizeof(big_list) / 1024 / 1024:.1f} MB")

# Generator: computes values one at a time
big_gen = (x ** 2 for x in range(10_000_000))
print(f"Generator: {sys.getsizeof(big_gen)} bytes")  # ~200 bytes always!

# -- Generator function --
def fibonacci(limit=None):
    """Generate Fibonacci numbers, optionally up to a limit."""
    a, b = 0, 1
    while limit is None or a < limit:
        yield a     # Pause here, return 'a', resume on next()
        a, b = b, a + b

# Use with for loop
for n in fibonacci(limit=100):
    print(n, end=" ")
# 0 1 1 2 3 5 8 13 21 34 55 89

# Use with next()
gen = fibonacci()
print(next(gen))  # 0
print(next(gen))  # 1
print(next(gen))  # 1
print(next(gen))  # 2

# -- Processing large files line by line --
def read_large_file(file_path, chunk_size=8192):
    """Read a file in chunks without loading it all into memory."""
    with open(file_path, 'r') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def grep_file(file_path, pattern):
    """Search for pattern in a file, yielding matching lines."""
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if pattern in line:
                yield line_num, line.rstrip()

# Memory-efficient: only one line in memory at a time
for num, line in grep_file("/var/log/syslog", "error"):
    print(f"Line {num}: {line}")

# -- Generator as a data pipeline --
def read_csv_rows(path):
    with open(path) as f:
        header = next(f).strip().split(',')
        for line in f:
            values = line.strip().split(',')
            yield dict(zip(header, values))

def filter_active(rows):
    for row in rows:
        if row.get('status') == 'active':
            yield row

def transform_to_output(rows):
    for row in rows:
        yield {
            'name': row['name'].upper(),
            'email': row['email'],
        }

# Pipeline: each stage is lazy, processes one row at a time
pipeline = transform_to_output(filter_active(read_csv_rows("users.csv")))
for record in pipeline:
    print(record)
```

The memory comparison at the top makes the point starkly:

```text
List: 381.5 MB
Generator: 200 bytes
```

**How to read this output:** The list materializes all 10 million squares up front, so its size scales with the data — hundreds of megabytes. The generator stores only its execution frame and current position, so `getsizeof` reports a small constant (~200 bytes) no matter how many values it will eventually yield. This is the difference between a process that OOM-kills on a large dataset and one that streams it in constant memory. The exact MB figure depends on the platform's pointer size and list over-allocation, but the order-of-magnitude gap is the takeaway: reach for a generator whenever you only iterate once and don't need random access or `len()`.

### `yield from`: Sub-Generator Delegation

`yield from` delegates iteration to another iterable, passing values through transparently in both directions.

```python
# -- Basic delegation --
def chain(*iterables):
    """Like itertools.chain -- yield from each iterable in sequence."""
    for it in iterables:
        yield from it

result = list(chain([1, 2], [3, 4], [5]))
print(result)  # [1, 2, 3, 4, 5]

# -- Flattening nested structures --
def flatten(nested):
    """Recursively flatten nested lists."""
    for item in nested:
        if isinstance(item, (list, tuple)):
            yield from flatten(item)
        else:
            yield item

data = [1, [2, 3, [4, 5]], [6, [7, 8, [9]]]]
print(list(flatten(data)))  # [1, 2, 3, 4, 5, 6, 7, 8, 9]

# -- Tree traversal --
class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

    def __iter__(self):
        """Depth-first traversal using yield from."""
        yield self.value
        for child in self.children:
            yield from child  # Delegates to child.__iter__()

tree = TreeNode("root", [
    TreeNode("A", [TreeNode("A1"), TreeNode("A2")]),
    TreeNode("B", [TreeNode("B1")]),
])

print(list(tree))  # ['root', 'A', 'A1', 'A2', 'B', 'B1']
```

### The Iterator Protocol

Any object implementing `__iter__()` and `__next__()` is an iterator. Understanding this protocol lets you create custom iterables for your domain.

```python
# -- Custom iterator: paginated API results --
class PaginatedAPI:
    """Iterator that fetches paginated API results on demand."""
    def __init__(self, base_url, page_size=100):
        self.base_url = base_url
        self.page_size = page_size
        self.current_page = 0
        self.buffer = []
        self.exhausted = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.buffer:
            if self.exhausted:
                raise StopIteration
            self._fetch_next_page()
        if not self.buffer:
            raise StopIteration
        return self.buffer.pop(0)

    def _fetch_next_page(self):
        # In real code: response = requests.get(...)
        self.current_page += 1
        # Simulate: returns items until page 3
        if self.current_page > 3:
            self.exhausted = True
            return
        self.buffer = [
            {"id": (self.current_page - 1) * self.page_size + i}
            for i in range(self.page_size)
        ]

# Usage -- automatically fetches pages as needed
for item in PaginatedAPI("https://api.example.com/items", page_size=10):
    print(item["id"])
    if item["id"] >= 25:
        break  # Only fetched 3 pages, not all data
```

The loop above prints IDs starting at 0 and stops shortly after 25:

```text
0
1
2
...
25
26
```

**How to read this output:** With `page_size=10`, IDs run 0-9 (page 1), 10-19 (page 2), 20-29 (page 3). The loop breaks once it sees an id `>= 25`, so it prints through 26 (id 25 triggers the condition but the print already happened, and 26 was the next buffered item only if drained — in practice the loop stops right after the first id that meets the threshold). The key insight is in `_fetch_next_page`: the iterator pulled exactly three pages of data, not the entire backing collection, because pages are fetched lazily inside `__next__` only when the buffer empties. In a real client this is the difference between one cheap HTTP call and accidentally paging through a million rows. The iterator never raised `StopIteration` here because the consumer `break`-ed first.

```python
# -- itertools: composable iteration --
import itertools

# Take first N items from infinite generator
first_10_fibs = list(itertools.islice(fibonacci(), 10))
print(first_10_fibs)  # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

# Group consecutive items
data = [1, 1, 2, 2, 2, 3, 1, 1]
for key, group in itertools.groupby(data):
    print(f"{key}: {list(group)}")
# 1: [1, 1]
# 2: [2, 2, 2]
# 3: [3]
# 1: [1, 1]

# Combine iterators
for item in itertools.chain([1, 2], [3, 4]):
    print(item)

# Cartesian product
for combo in itertools.product(['A', 'B'], [1, 2]):
    print(combo)  # ('A', 1), ('A', 2), ('B', 1), ('B', 2)

# Batching (Python 3.12+)
for batch in itertools.batched(range(10), 3):
    print(batch)  # (0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)
```

> **Key Takeaway:** Generators are Python's tool for lazy evaluation and memory-efficient processing. Use them for large files, API pagination, data pipelines, and any scenario where you process items one at a time. Combine with `itertools` for powerful, composable data processing.

---

## Type Hints & Static Analysis

### Core Type Annotations

Type hints make your code self-documenting and enable static analysis tools to catch bugs before runtime. They have zero runtime cost (except when introspected).

```python
from typing import Optional, Union, List, Dict, Tuple, Callable, Any

# -- Basic annotations --
def greet(name: str, excited: bool = False) -> str:
    if excited:
        return f"Hello, {name}!!!"
    return f"Hello, {name}"

# -- Optional: value or None --
def find_user(user_id: int) -> Optional[dict]:
    """Returns user dict or None if not found."""
    # Optional[dict] is equivalent to dict | None (Python 3.10+)
    if user_id == 1:
        return {"id": 1, "name": "Alice"}
    return None

# -- Union: multiple possible types --
def process_input(value: Union[str, int, list]) -> str:
    # Python 3.10+: str | int | list
    return str(value)

# -- Container types --
def analyze_scores(
    scores: Dict[str, List[float]],       # dict of name -> scores
    weights: Tuple[float, float, float],   # exactly 3 floats
    callback: Callable[[str, float], None], # function(str, float) -> None
) -> Dict[str, float]:
    results = {}
    for name, score_list in scores.items():
        weighted = sum(s * w for s, w in zip(score_list, weights))
        results[name] = weighted
        callback(name, weighted)
    return results

# Python 3.9+: use built-in types directly (no import needed)
def modern_style(items: list[str], mapping: dict[str, int]) -> tuple[int, ...]:
    return tuple(mapping.get(item, 0) for item in items)

# Python 3.10+: union syntax with |
def newest_style(value: str | int | None) -> str:
    return str(value) if value is not None else "none"
```

### Generics with TypeVar and Protocol

```python
from typing import TypeVar, Generic, Protocol, runtime_checkable

# -- TypeVar: generic functions --
T = TypeVar('T')

def first(items: list[T]) -> T:
    """Return first element, preserving the type."""
    return items[0]

# mypy knows the result type:
x: int = first([1, 2, 3])        # T = int
y: str = first(["a", "b", "c"])  # T = str

# -- Bounded TypeVar --
from typing import SupportsFloat
N = TypeVar('N', bound=SupportsFloat)

def average(values: list[N]) -> float:
    return sum(float(v) for v in values) / len(values)

# -- Generic classes --
V = TypeVar('V')

class Stack(Generic[V]):
    def __init__(self) -> None:
        self._items: list[V] = []

    def push(self, item: V) -> None:
        self._items.append(item)

    def pop(self) -> V:
        return self._items.pop()

    def peek(self) -> V:
        return self._items[-1]

    def __len__(self) -> int:
        return len(self._items)

int_stack = Stack[int]()
int_stack.push(42)
int_stack.push("hello")  # mypy error: Argument 1 has incompatible type "str"

# -- Protocol: structural subtyping (duck typing + type safety) --
@runtime_checkable
class Drawable(Protocol):
    def draw(self, x: int, y: int) -> None: ...

class Circle:
    def draw(self, x: int, y: int) -> None:
        print(f"Drawing circle at ({x}, {y})")

class Square:
    def draw(self, x: int, y: int) -> None:
        print(f"Drawing square at ({x}, {y})")

def render(shapes: list[Drawable]) -> None:
    for shape in shapes:
        shape.draw(0, 0)

# Works! Circle and Square satisfy the Drawable protocol
# without explicitly inheriting from it.
render([Circle(), Square()])

# runtime_checkable allows isinstance checks
print(isinstance(Circle(), Drawable))  # True
```

### TypedDict and Literal

```python
from typing import TypedDict, Literal, Required, NotRequired

# -- TypedDict: typed dictionaries --
class UserDict(TypedDict):
    id: int
    name: str
    email: str
    role: Literal["admin", "user", "moderator"]
    bio: NotRequired[str]  # Optional key (Python 3.11+)

def create_user(data: UserDict) -> None:
    print(f"Creating user: {data['name']}")

# mypy validates the structure
create_user({
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "role": "admin",
})

# mypy error: "superadmin" is not a valid role
# create_user({"id": 1, "name": "Bob", "email": "...", "role": "superadmin"})

# -- Literal: restrict to specific values --
def set_log_level(level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    print(f"Log level set to {level}")

set_log_level("INFO")     # OK
# set_log_level("TRACE")  # mypy error: unexpected value
```

### mypy: Static Type Checking

```python
# -- Running mypy --
# $ mypy mymodule.py --strict
# $ mypy src/ --ignore-missing-imports

# -- reveal_type: debugging type inference --
x = [1, 2, 3]
reveal_type(x)  # note: Revealed type is "builtins.list[builtins.int]"

# -- cast: tell mypy the type when it can't infer --
from typing import cast

data: Any = get_external_data()
user = cast(UserDict, data)  # No runtime effect -- just tells mypy

# -- Type narrowing --
def process(value: str | int | None) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, int):
        # mypy knows value is int here
        return str(value * 2)
    # mypy knows value is str here
    return value.upper()

# -- Gradual typing: add types incrementally --
# Start with public APIs, then internal functions
# Use # type: ignore for legacy code you haven't typed yet
result = legacy_function()  # type: ignore[no-untyped-call]

# -- pyproject.toml configuration --
# [tool.mypy]
# python_version = "3.11"
# strict = true
# warn_return_any = true
# warn_unused_configs = true
#
# [[tool.mypy.overrides]]
# module = "tests.*"
# disallow_untyped_defs = false
```

### Pydantic: Runtime Validation

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional

class Address(BaseModel):
    street: str
    city: str
    country: str = "US"

class User(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: str
    age: int = Field(..., ge=0, le=150)
    address: Optional[Address] = None
    created_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email address')
        return v.lower()

    @model_validator(mode='after')
    def validate_model(self):
        if self.age < 13 and 'admin' in self.tags:
            raise ValueError('Users under 13 cannot be admins')
        return self

# Valid data -- types are coerced automatically
user = User(
    id="123",         # str "123" -> int 123
    name="Alice",
    email="ALICE@Example.COM",  # -> alice@example.com
    age=30,
    address={"street": "123 Main St", "city": "NYC"},
)
print(user.model_dump())
```

`model_dump()` returns the validated, coerced data as a plain dict (the `created_at` timestamp reflects when the object was built):

```text
{'id': 123, 'name': 'Alice', 'email': 'alice@example.com', 'age': 30,
 'address': {'street': '123 Main St', 'city': 'NYC', 'country': 'US'},
 'created_at': datetime.datetime(2026, 6, 4, 10, 15, 30, 123456),
 'tags': []}
```

**How to read this output:** Notice the values that changed during validation: `id` came in as the string `"123"` and is now the int `123`; `email` was upper-cased input but is stored lower-cased because `validate_email` ran and returned `v.lower()`; `country` was filled in with the `"US"` default the nested `Address` model declared; `created_at` was populated by `default_factory`; and `tags` defaulted to an empty list. This coercion-and-defaulting is exactly why Pydantic is the standard for API boundaries — request JSON arrives as strings and partial objects, and the model is the single place that turns it into clean, typed Python while rejecting anything invalid.

```python
# Invalid data -- raises ValidationError with details
from pydantic import ValidationError
try:
    bad_user = User(id=1, name="", email="invalid", age=200)
except ValidationError as e:
    print(e.json(indent=2))
    # [
    #   {"type": "string_too_short", "loc": ["name"], ...},
    #   {"type": "value_error", "loc": ["email"], ...},
    #   {"type": "less_than_equal", "loc": ["age"], ...}
    # ]
```

> **Key Takeaway:** Type hints catch bugs before runtime and serve as living documentation. Use `mypy --strict` for new projects, `Protocol` for duck typing, and Pydantic for runtime validation (especially in APIs). Adopt types gradually -- start with public function signatures.

---

## Dataclasses, Enums & Modeling

Pydantic (above) is the right tool at *untrusted boundaries* where you parse-don't-validate. For internal value objects and DTOs that you build in trusted code, the standard library's `@dataclass`, `NamedTuple`, and `enum` are lighter and have zero dependencies.

### `@dataclass`: Boilerplate-Free Value Objects

`@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__` from annotated fields. The flags control how strict and how cheap the resulting class is.

```python
from dataclasses import dataclass, field

# -- frozen + slots: an immutable, memory-light value object --
@dataclass(frozen=True, slots=True, order=True)
class Point:
    x: float
    y: float

p = Point(1.0, 2.0)
# p.x = 5.0  -> raises FrozenInstanceError (frozen=True)
print(p)              # repr is auto-generated
print(p < Point(3, 4))  # order=True generates __lt__/__le__/... (tuple compare)
print(hash(p))        # frozen=True makes it hashable -> usable as dict key / in a set

# -- field(default_factory=...) for mutable defaults --
@dataclass
class Order:
    id: int
    items: list[str] = field(default_factory=list)   # NEVER `items: list = []`
    meta: dict[str, str] = field(default_factory=dict)

# -- kw_only forces call-site clarity; __post_init__ derives/validates --
@dataclass(kw_only=True)
class LineItem:
    unit_price_cents: int
    quantity: int
    total_cents: int = field(init=False)   # computed, not passed in

    def __post_init__(self):
        if self.quantity < 1:
            raise ValueError("quantity must be >= 1")
        self.total_cents = self.unit_price_cents * self.quantity

item = LineItem(unit_price_cents=250, quantity=3)
print(item.total_cents)
```

```text
Point(x=1.0, y=2.0)
True
3713081631934410656
750
```

**How to read this output:** The `repr` and the comparison both come for free — `order=True` makes `Point` sort like the tuple `(x, y)`, which is why `Point(1,2) < Point(3,4)` is `True`. The `hash(...)` line only works because `frozen=True` froze the fields; a normal mutable dataclass is *unhashable* (its `__hash__` is set to `None`) precisely so you can't accidentally use a mutable object as a dict key and then mutate it out from under the hash table. The `750` proves `__post_init__` ran after the generated `__init__` populated the simple fields — the canonical place to compute derived fields and validate invariants. `default_factory` is mandatory for `list`/`dict`/`set` defaults because a bare `[]` would be shared across every instance (the same mutable-default bug as in function arguments).

### `NamedTuple` vs `dataclass` vs `dict`

```python
from typing import NamedTuple

class Coord(NamedTuple):
    lat: float
    lng: float

c = Coord(40.7, -74.0)
print(c.lat, c[0])          # attribute OR index access; it IS a tuple
lat, lng = c               # unpacks like a tuple
```

Choose by need: a `NamedTuple` is immutable, indexable, tuple-compatible (great for fixed records, dict keys, and code that already iterates tuples), but you cannot add methods/behavior comfortably and every instance is immutable. A `@dataclass` is the default for anything with behavior or mutation, supports `frozen`/`slots`/`order`, and reads as a real class. A plain `dict` has no fixed schema, no attribute access, and no type checking — fine for truly dynamic data, but reaching for a dataclass turns runtime `KeyError`s and typos into static, autocompleted attributes.

### Enums: Names Instead of Magic Strings

```python
from enum import Enum, IntEnum, StrEnum, Flag, auto

# -- Basic Enum: identity-based named constants --
class Status(Enum):
    PENDING = auto()
    ACTIVE = auto()
    CLOSED = auto()

print(Status.ACTIVE, Status.ACTIVE.name, Status.ACTIVE.value)
print(Status.ACTIVE is Status.ACTIVE)   # identity comparison is the idiom

# -- StrEnum (3.11+): members ARE strings -> JSON/DB-friendly --
class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"

print(Role.ADMIN == "admin")            # True; serializes straight to "admin"

# -- IntEnum: members ARE ints (interop with C APIs, DB int columns) --
class Priority(IntEnum):
    LOW = 1
    HIGH = 3

print(Priority.HIGH > Priority.LOW)     # True; compares as ints

# -- Flag / IntFlag: bitwise-combinable permission sets --
class Perm(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()

access = Perm.READ | Perm.WRITE
print(Perm.WRITE in access)             # True -- membership test on combined flags
print(access)
```

```text
Status.ACTIVE ACTIVE 2
True
True
True
True
Perm.READ|WRITE
```

**How to read this output:** `Status.ACTIVE.value` is `2` because `auto()` numbers members from 1 in definition order — never persist these auto values to a database, since reordering members silently changes them; use explicit values (or a `StrEnum`) for anything stored. The `Role.ADMIN == "admin"` line is the practical payoff of `StrEnum`: the member behaves as a real string, so it serializes to JSON and round-trips through a database column with no custom encoder, while your code still gets autocompletion and a single source of truth. The `Perm.READ|WRITE` repr shows a `Flag` holding two bits at once — this is how you model permission bitmasks cleanly instead of juggling raw integers and remembering that `4` means EXECUTE. The whole section's lesson: replace scattered magic strings/ints (`if status == "active"`) with enums so typos become `AttributeError`s at import time and the valid set is enumerable and documented.

> **Key Takeaway:** Reach for `@dataclass` (with `slots=True`, and `frozen=True` for value objects) as the default container for trusted internal data, `NamedTuple` when you need a lightweight immutable record that behaves like a tuple, and enums (`StrEnum`/`IntEnum` for serialization, `Flag` for bitmasks) instead of magic constants everywhere.

---

## Dates, Times & Time Zones

Date handling is a perennial source of production incidents. One rule prevents most of them: **store and compute in UTC, convert to local only for display.**

### Aware vs Naive, and the `utcnow()` Trap

A *naive* `datetime` has no `tzinfo` and is ambiguous — it could mean any zone. An *aware* datetime carries its zone. Always work with aware datetimes for anything real.

```python
from datetime import datetime, timezone

# WRONG: returns a NAIVE datetime even though the value is in UTC.
# The object claims no timezone, so later arithmetic/comparison silently misbehaves.
bad = datetime.utcnow()           # deprecated in 3.12; classic trap
print(bad.tzinfo)                 # None  <-- naive!

# RIGHT: an AWARE datetime that actually knows it is UTC.
good = datetime.now(timezone.utc)
print(good.tzinfo)                # datetime.timezone.utc

# Mixing aware and naive raises -- a feature, not a bug:
try:
    good - bad
except TypeError as e:
    print(f"TypeError: {e}")
```

```text
None
UTC
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**How to read this output:** The `None` is the entire bug in one line — `utcnow()` gives you a value that *is* UTC but doesn't *say* so, so the moment you compare or subtract it against an aware datetime Python refuses (the `TypeError`). That refusal is protective: the alternative would be silently treating a naive value as local time and producing an answer off by your UTC offset. Use `datetime.now(timezone.utc)` everywhere and the whole class of "off by 5 hours in production but not on my laptop" bugs disappears.

### Zones, DST, and Serialization

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo   # stdlib since 3.9; the modern IANA tz source

utc_now = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)

# Convert UTC -> local for DISPLAY only:
paris = utc_now.astimezone(ZoneInfo("Europe/Paris"))
print(paris.isoformat())        # RFC 3339 / ISO 8601 string

# DST fold: a fall-back hour happens twice. `fold` disambiguates.
ambiguous = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"))
print(ambiguous.utcoffset(), datetime(2026, 11, 1, 1, 30, fold=1,
      tzinfo=ZoneInfo("America/New_York")).utcoffset())

# Round-trip through a string (store/transport ISO 8601):
s = utc_now.isoformat()
print(datetime.fromisoformat(s) == utc_now)
```

```text
2026-06-05T14:00:00+02:00
-1 day, 20:00:00 -1 day, 19:00:00
True
```

**How to read this output:** The Paris time is `14:00+02:00` — the same instant as `12:00Z`, just rendered in a zone that is currently +2 (summer DST). Always serialize with `.isoformat()` and parse with `.fromisoformat()` so the offset travels with the value; the final `True` proves the round-trip is lossless. The middle line shows the same wall-clock `01:30` resolving to two *different* UTC offsets (`-04:00` vs `-05:00`, shown here as the timedelta from UTC) depending on `fold` — that is the fall-back hour that exists twice. The rule that follows: never do arithmetic in local time across a DST boundary; convert to UTC, do the math, convert back. `zoneinfo` is preferred over the older `pytz`, whose error-prone `localize()` API was a frequent source of off-by-an-hour bugs.

For measuring *durations* (timeouts, latency), use `time.monotonic()` instead of `time.time()`/wall-clock: the monotonic clock never goes backward and is immune to NTP steps, manual clock changes, and DST. Wall-clock time can jump backward, making a naive `end - start` negative.

> **Common pitfall:** Persisting a naive "local" datetime and a separate timezone string, then reconstructing across a DST change, can land you in the non-existent spring-forward gap (e.g. `02:30` on a spring-forward night never happens). If you must store a future local time ("9am in their city, forever"), store the wall time plus the IANA zone *name* and resolve to UTC at use time, not at storage time.

---

## Numbers, Precision & Money

### Floats Lie; Use Decimal for Money

`float` is IEEE-754 double-precision binary floating point. Many decimal fractions have no exact binary representation, so arithmetic accumulates tiny errors.

```python
from decimal import Decimal, ROUND_HALF_EVEN

print(0.1 + 0.2)                 # not 0.3
print(0.1 + 0.2 == 0.3)          # False

# Decimal: exact base-10 arithmetic
print(Decimal("0.1") + Decimal("0.2"))      # exactly 0.3
print(Decimal("0.1") + Decimal("0.2") == Decimal("0.3"))

# Banker's rounding (ROUND_HALF_EVEN, the Decimal default) rounds .5 to the
# nearest EVEN digit, which removes the upward bias of always-round-half-up:
print(Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))   # 2
print(Decimal("3.5").quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))   # 4
```

```text
0.30000000000000004
False
0.3
True
2
4
```

**How to read this output:** The `0.30000000000000004` is not a Python quirk — it is what every IEEE-754 language prints, and it is exactly why `0.1 + 0.2 == 0.3` is `False`. For money this is unacceptable: summing thousands of float cents drifts and your ledger won't balance. `Decimal` constructed from *strings* (not from floats, which would inherit the binary error) gives exact base-10 results. The `2.5 -> 2` but `3.5 -> 4` lines show banker's rounding picking the nearer even digit; over many roundings this cancels out instead of systematically inflating totals the way round-half-up does — which is why it is the standard for financial reporting.

The common production pattern: store money as **integer minor units** (cents) in an `INTEGER`/`BIGINT` column, or as SQL `NUMERIC`/`DECIMAL` — never `float`/`double`. Always track the **currency** alongside the amount (a small `Money` value object: `(amount_cents, currency)`), because `100` is meaningless without knowing if it's USD or JPY, and define the rounding policy explicitly rather than letting it happen by accident.

```python
from fractions import Fraction
print(Fraction(1, 3) + Fraction(1, 3) + Fraction(1, 3))   # exactly 1, no drift

# Python ints are arbitrary-precision (no overflow):
print(2 ** 200)
```

`fractions.Fraction` gives exact rational arithmetic when even decimals aren't enough (e.g. repeated thirds). Python's own `int` never overflows, but **NumPy** integer types are fixed-width and overflow *silently* — `np.int64(2**63 - 1) + 1` wraps to a negative number with no error — so validate ranges at any boundary where Python ints meet NumPy, C, or a database column with a width limit.

---

## Strings, Bytes & Encoding

`str` is a sequence of Unicode *code points*; `bytes` is a sequence of raw *octets*. They are different types and mixing them raises `TypeError`. The mantra: **encode `str` to `bytes`, decode `bytes` to text — always with an explicit `utf-8`.**

```python
text = "café"                       # str: 4 code points
data = text.encode("utf-8")         # bytes
print(data)                         # the é becomes two bytes in UTF-8
print(len(text), len(data))         # code points vs bytes differ
print(data.decode("utf-8") == text)

# Always pass encoding explicitly; the platform default differs across OSes:
# open(path, encoding="utf-8")   <- not open(path)

# len() counts code points, NOT user-perceived characters:
flag = "\U0001F1FA\U0001F1F8"       # the regional-indicator pair for the US flag
print(len(flag))                    # 2 code points, but renders as ONE glyph
```

```text
b'caf\xc3\xa9'
4 5
True
```

**How to read this output:** `café` is 4 code points but 5 bytes — the `é` encodes to the two bytes `\xc3\xa9` in UTF-8, which is why `len(text)` and `len(data)` disagree. This matters anywhere you size or slice text by bytes (database `VARCHAR` limits, network buffers, truncating a tweet): a byte budget is not a character budget. The flag example drives it home — `len(flag) == 2` even though it renders as a single glyph, so naive truncation can split a grapheme and produce mojibake. Decoding only round-trips when you decode with the *same* encoding you encoded with; relying on the platform default (UTF-8 on Linux/macOS, often cp1252 on Windows) is the classic cause of "works on my machine, garbled in prod."

```python
import unicodedata
a = "é"                              # precomposed (NFC), 1 code point
b = "é"                        # 'e' + combining acute (NFD), 2 code points
print(a == b)                        # False -- same glyph, different bytes!
print(unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b))
```

The two strings above look identical on screen but compare unequal because one is precomposed (NFC) and one decomposed (NFD). **Normalize** (usually to NFC) before comparing, hashing, or storing usernames and identifiers — otherwise you get duplicate-but-different accounts and openings for homograph spoofing. Finally: `base64` is binary-to-text *encoding*, not encryption — it provides zero confidentiality, so never treat a base64 string as if it were a secret in transit.

---

## Serialization

Turning objects into bytes for storage or transport. The right format depends on who reads it back and whether you trust them.

```python
import json
from datetime import datetime
from decimal import Decimal

# JSON has no native datetime/Decimal/set/bytes -- this RAISES:
try:
    json.dumps({"when": datetime.now(), "price": Decimal("9.99")})
except TypeError as e:
    print(f"TypeError: {e}")

# Provide a custom default to serialize the unsupported types:
def encode(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"not serializable: {type(obj)}")

print(json.dumps({"when": "2026-06-05", "price": Decimal("9.99")}, default=encode))
```

```text
TypeError: Object of type datetime is not JSON serializable
```

**How to read this output:** JSON's type system is deliberately tiny (objects, arrays, strings, numbers, booleans, null), so anything richer — `datetime`, `Decimal`, `set`, `bytes` — raises until you supply a `default` encoder. The fix shown serializes `datetime` as an ISO 8601 string and `Decimal` as a string (not a float, to preserve exactness). A related gotcha: JSON numbers are IEEE-754 doubles in JavaScript consumers, so a 64-bit integer ID can lose precision past 2^53 — send large IDs as strings.

`pickle` can serialize almost any Python object, but **it executes arbitrary code on load** — unpickling attacker-controlled data is a remote-code-execution hole, so never unpickle anything you didn't produce yourself, and treat it as an unstable cross-version format unsuitable for long-term storage. For packed binary records (network protocols, file headers) use `struct` with explicit byte order and field widths. For anything crossing a process, service, or language boundary, prefer a schema-driven cross-language format — **Protocol Buffers**, **Avro**, or **MessagePack** — which are compact, versionable, and safe, rather than pickling.

> **Key Takeaway:** JSON for human-readable interchange (with custom encoders for dates/Decimals); never `pickle` untrusted input (RCE); `struct` for fixed binary layouts; Protobuf/Avro/MessagePack for typed, versioned, cross-language messaging.

---

## Pattern Matching (3.10+)

`match`/`case` is structural pattern matching — far more than a `switch`. It *destructures* the subject and can bind variables while it matches, which makes it ideal for parsing variant/tagged data, command dispatch, and walking ASTs.

```python
def handle(event: dict):
    match event:
        # Mapping pattern: matches a dict containing these keys, binds `uid`
        case {"type": "login", "user_id": uid}:
            return f"login by {uid}"
        # Sequence pattern with capture of the rest
        case {"type": "batch", "items": [first, *rest]}:
            return f"batch starting with {first}, +{len(rest)} more"
        # Guard: extra boolean condition with `if`
        case {"type": "payment", "cents": c} if c > 100_00:
            return "large payment -> manual review"
        case {"type": "payment", "cents": c}:
            return f"payment {c} cents"
        # Wildcard -- the default
        case _:
            return "unknown event"

print(handle({"type": "login", "user_id": 42}))
print(handle({"type": "batch", "items": [1, 2, 3, 4]}))
print(handle({"type": "payment", "cents": 50000}))
print(handle({"type": "noise"}))
```

```text
login by 42
batch starting with 1, +3 more
large payment -> manual review
unknown event
```

**How to read this output:** Each line shows a different *kind* of pattern doing both a test and an extraction in one step. The login case matched the mapping shape and bound `uid=42` simultaneously — no manual `event["user_id"]` with a `KeyError` risk. The batch case used `[first, *rest]` to split a sequence inside the dict. The payment guard (`if c > 100_00`) fired first because cases are tried top-to-bottom and `50000 > 10000`, so the more specific guarded case wins over the plain one below it — ordering matters. `case _` caught the unrecognized event. This reads dramatically cleaner than a chain of `if event.get("type") == ...` with nested index access.

```python
from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

def describe(c, color):
    GREEN = "captured!"        # a bare name in a pattern is NOT compared to this
    match c:
        case color:            # BUG: bare `color` is a CAPTURE, matches anything
            return f"captured {color}"

# To match a CONSTANT, use a dotted name so it's treated as a value, not a capture:
def classify(c: Color):
    match c:
        case Color.RED:        # dotted -> value pattern (equality check)
            return "stop"
        case Color.GREEN:
            return "go"
```

> **Common pitfall:** A *bare* name in a `case` (like `case color:` or `case GREEN:`) is a **capture pattern** — it always matches and *binds* the subject to that name, shadowing any same-named variable; it is never an equality test. To compare against a constant you must use a dotted/attribute name (`case Color.RED:`, `case status.ACTIVE:`) or a literal (`case 200:`). This is the single most common pattern-matching bug for newcomers.

---

## Concurrency Patterns

### `concurrent.futures`: High-Level Concurrency

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from concurrent.futures import as_completed, wait, FIRST_COMPLETED
import time

# -- ThreadPoolExecutor: I/O-bound tasks --
def fetch_url(url):
    """Simulate fetching a URL (I/O-bound)."""
    import urllib.request
    response = urllib.request.urlopen(url)
    return url, len(response.read())

urls = [
    "https://example.com",
    "https://httpbin.org/get",
    "https://jsonplaceholder.typicode.com/posts/1",
]

# executor.map: ordered results
with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(fetch_url, urls)
    for url, size in results:
        print(f"{url}: {size} bytes")

# executor.submit + as_completed: first-available results
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_url, url): url for url in urls}
    for future in as_completed(futures):
        url = futures[future]
        try:
            _, size = future.result(timeout=10)
            print(f"Completed: {url} ({size} bytes)")
        except Exception as e:
            print(f"Failed: {url} ({e})")
```

The two retrieval strategies print the same data in different orders:

```text
# executor.map (ordered, matches input order):
https://example.com: 1256 bytes
https://httpbin.org/get: 312 bytes
https://jsonplaceholder.typicode.com/posts/1: 292 bytes

# as_completed (completion order -- fastest response first):
Completed: https://httpbin.org/get (312 bytes)
Completed: https://jsonplaceholder.typicode.com/posts/1 (292 bytes)
Completed: https://example.com (1256 bytes)
```

**How to read this output:** `executor.map` yields results in the order the URLs were submitted, even if a later URL finishes first — convenient, but you wait on the slowest request before consuming the next result. `as_completed` yields each future the instant it finishes, so the ordering reflects real network latency and varies run to run. The byte counts depend on live responses, so exact numbers differ. In production, prefer `as_completed` when you want to start processing the first available response immediately (e.g. streaming results to a user) and `map` when downstream code needs results aligned with the input list. Because these are I/O-bound HTTP calls, threads (not processes) are the right tool — the GIL is released while waiting on the socket.

```python
# -- ProcessPoolExecutor: CPU-bound tasks --
def compute_heavy(n):
    """CPU-intensive computation."""
    return sum(i * i for i in range(n))

with ProcessPoolExecutor(max_workers=4) as executor:
    # Distribute work across CPU cores
    chunks = [10_000_000] * 4
    results = list(executor.map(compute_heavy, chunks))
    total = sum(results)
    print(f"Total: {total}")

# -- wait with FIRST_COMPLETED for responsive processing --
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(fetch_url, url) for url in urls}
    while futures:
        done, futures = wait(futures, return_when=FIRST_COMPLETED)
        for f in done:
            print(f"Got result: {f.result()[0]}")
```

### Multiprocessing: Shared State and IPC

```python
import multiprocessing as mp
import os

# -- Basic multiprocessing --
def worker(name, queue):
    """Worker process that puts results into a queue."""
    pid = os.getpid()
    result = f"Worker {name} (PID {pid}) computed {sum(range(1000000))}"
    queue.put(result)

if __name__ == "__main__":
    queue = mp.Queue()
    processes = []
    for i in range(4):
        p = mp.Process(target=worker, args=(f"W{i}", queue))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    while not queue.empty():
        print(queue.get())

# -- Shared state: Value and Array --
def increment(shared_counter, lock, n):
    for _ in range(n):
        with lock:
            shared_counter.value += 1

if __name__ == "__main__":
    counter = mp.Value('i', 0)  # 'i' = signed int
    lock = mp.Lock()

    procs = [
        mp.Process(target=increment, args=(counter, lock, 100_000))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    print(f"Counter: {counter.value}")  # Exactly 400,000

# -- Pool: simpler parallel map --
def square(x):
    return x * x

if __name__ == "__main__":
    with mp.Pool(processes=4) as pool:
        results = pool.map(square, range(20))
        print(results)

        # imap_unordered: returns results as they complete
        for result in pool.imap_unordered(square, range(20)):
            print(result, end=" ")
```

### Threading Primitives

```python
import threading
import time

# -- Lock: mutual exclusion --
class ThreadSafeCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:  # Acquire and release automatically
            self._count += 1

    @property
    def value(self):
        with self._lock:
            return self._count

counter = ThreadSafeCounter()
threads = [
    threading.Thread(target=lambda: [counter.increment() for _ in range(100_000)])
    for _ in range(10)
]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Counter: {counter.value}")  # Exactly 1,000,000

# -- RLock: reentrant lock (same thread can acquire multiple times) --
class RecursiveResource:
    def __init__(self):
        self._lock = threading.RLock()

    def method_a(self):
        with self._lock:
            print("method_a acquired lock")
            self.method_b()  # Would deadlock with Lock, works with RLock

    def method_b(self):
        with self._lock:
            print("method_b acquired lock (reentrant)")

# -- thread-local storage --
local_data = threading.local()

def worker(name):
    local_data.name = name  # Each thread has its own 'name'
    time.sleep(0.1)
    print(f"Thread {threading.current_thread().name}: local_data.name = {local_data.name}")

threads = [threading.Thread(target=worker, args=(f"Worker-{i}",)) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
# Each thread sees its own value, not other threads' values

# 3 threads run with their own value; line order may vary, but the mapping never crosses:
#   Thread Thread-1: local_data.name = Worker-0
#   Thread Thread-2: local_data.name = Worker-1
#   Thread Thread-3: local_data.name = Worker-2

# -- Condition: wait for a condition to be met --
class BoundedBuffer:
    def __init__(self, capacity):
        self.buffer = []
        self.capacity = capacity
        self.condition = threading.Condition()

    def produce(self, item):
        with self.condition:
            while len(self.buffer) >= self.capacity:
                self.condition.wait()  # Release lock and wait
            self.buffer.append(item)
            self.condition.notify()  # Wake up a consumer

    def consume(self):
        with self.condition:
            while not self.buffer:
                self.condition.wait()
            item = self.buffer.pop(0)
            self.condition.notify()  # Wake up a producer
            return item
```

> **Key Takeaway:** Use `concurrent.futures` for simple parallelism (it abstracts away the thread/process complexity). Use `multiprocessing` with `Pool` for CPU-bound batch processing. Use `threading.Lock` (not `RLock` unless you need reentrancy) and thread-local storage to manage shared state safely.

*Last reviewed: 2026-06-08*
