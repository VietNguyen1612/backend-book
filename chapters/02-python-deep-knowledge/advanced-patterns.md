[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.3 Advanced Patterns

### Decorators & Context Managers

#### Function Decorators: Wrapping Behavior

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

#### Class-Based Decorators

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
# The outermost decorator (timing) runs first, the innermost last.
```

#### Context Managers: Resource Management

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

> **Key Takeaway:** Decorators and context managers are Python's primary composition tools. Always use `@functools.wraps`, prefer generator-based context managers with `@contextlib.contextmanager` for simplicity, and use `ExitStack` when managing a dynamic number of resources.

---

### Generators & Iterators

#### Generator Functions: Lazy Evaluation

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

#### `yield from`: Sub-Generator Delegation

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

#### The Iterator Protocol

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

### Type Hints & Static Analysis

#### Core Type Annotations

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

#### Generics with TypeVar and Protocol

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

#### TypedDict and Literal

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

#### mypy: Static Type Checking

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

#### Pydantic: Runtime Validation

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

### Concurrency Patterns

#### `concurrent.futures`: High-Level Concurrency

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

#### Multiprocessing: Shared State and IPC

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

#### Threading Primitives

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
