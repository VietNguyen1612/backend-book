[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.2 Async Programming

## asyncio

### The Event Loop: Cooperative Multitasking

The event loop is the heart of `asyncio`. It runs in a single thread and manages the execution of coroutines cooperatively. When a coroutine hits an `await`, it yields control back to the event loop, which can then run other coroutines. This is fundamentally different from threading (preemptive multitasking).

```python
import asyncio
import time

async def fetch_data(name, delay):
    """Simulate an I/O operation (e.g., HTTP request, database query)."""
    print(f"[{time.strftime('%X')}] {name}: starting fetch")
    await asyncio.sleep(delay)  # Non-blocking sleep -- yields to event loop
    print(f"[{time.strftime('%X')}] {name}: done")
    return f"{name}_result"

async def main():
    # Sequential: takes 1 + 2 + 3 = 6 seconds
    start = time.perf_counter()
    r1 = await fetch_data("A", 1)
    r2 = await fetch_data("B", 2)
    r3 = await fetch_data("C", 3)
    print(f"Sequential: {time.perf_counter() - start:.1f}s")

    # Concurrent: takes max(1, 2, 3) = 3 seconds
    start = time.perf_counter()
    r1, r2, r3 = await asyncio.gather(
        fetch_data("A", 1),
        fetch_data("B", 2),
        fetch_data("C", 3),
    )
    print(f"Concurrent: {time.perf_counter() - start:.1f}s")

asyncio.run(main())

# CRITICAL MISTAKE: blocking the event loop
async def bad_example():
    time.sleep(5)  # BLOCKS the entire event loop! Nothing else can run!
    # Use await asyncio.sleep(5) instead

async def good_example():
    await asyncio.sleep(5)  # Non-blocking: event loop runs other tasks
```

Running this prints something like (timestamps reflect wall-clock time, so they advance as the program runs):

```text
[14:02:01] A: starting fetch
[14:02:02] A: done
[14:02:02] B: starting fetch
[14:02:04] B: done
[14:02:04] C: starting fetch
[14:02:07] C: done
Sequential: 6.0s
[14:02:07] A: starting fetch
[14:02:07] B: starting fetch
[14:02:07] C: starting fetch
[14:02:08] A: done
[14:02:09] B: done
[14:02:10] C: done
Concurrent: 3.0s
```

**How to read this output:** In the sequential block each `await fetch_data(...)` runs to completion before the next starts, so the timestamps step forward one fetch at a time and the wall-clock total is 1+2+3 = 6s. In the concurrent block all three "starting fetch" lines print at the *same* second because `gather` schedules them together; they then finish in delay order, and the total collapses to `max(1,2,3) = 3s`. This is the entire value proposition of async I/O: the 6s of "work" is mostly idle waiting, and overlapping that idle time is free. The same pattern is why one async worker can hold thousands of slow database or HTTP calls open at once where a thread-per-request server would exhaust memory.

> **Common pitfall:** Replacing `asyncio.sleep` with a blocking call like `time.sleep`, a synchronous `requests.get`, or a CPU-bound loop inside a coroutine freezes the *entire* event loop — every other task stalls until it returns, and the "concurrent" version degrades back to sequential (or worse). If you must call blocking code, push it to a thread with `asyncio.to_thread` (covered below).

```
  Event Loop Execution Model
  ==========================

  Single thread, cooperative scheduling:

  Time -->
  Event Loop: [run A][run B][run C][run A][run B][run C]...

  Task A: [start]---await(I/O)---[resume]---await---[done]
  Task B:          [start]---await(I/O)---[resume]---[done]
  Task C:                   [start]---await(I/O)---[resume]---[done]

  When a task hits 'await', it VOLUNTARILY yields control.
  The event loop picks the next ready task.
  No preemption, no locks needed (single-threaded).

  vs. Threading (preemptive):

  OS Thread 1: [===run===][preempted][===run===][preempted]
  OS Thread 2: [preempted][===run===][preempted][===run===]
  OS decides when to switch. Need locks for shared state.
```

### `asyncio.gather()`, `asyncio.wait()`, and `asyncio.create_task()`

These are the three main ways to run coroutines concurrently. They serve different purposes.

```python
import asyncio

async def task(name, delay, should_fail=False):
    await asyncio.sleep(delay)
    if should_fail:
        raise ValueError(f"{name} failed!")
    return f"{name} completed in {delay}s"

async def main():
    # -- gather: run all, collect results in order --
    results = await asyncio.gather(
        task("A", 2),
        task("B", 1),
        task("C", 3),
    )
    print(results)  # ['A completed in 2s', 'B completed in 1s', 'C completed in 3s']

    # gather with return_exceptions=True: don't crash on failure
    results = await asyncio.gather(
        task("A", 1),
        task("B", 1, should_fail=True),
        task("C", 1),
        return_exceptions=True,
    )
    print(results)
    # ['A completed in 1s', ValueError('B failed!'), 'C completed in 1s']

    # -- wait: more control over completion --
    tasks = {
        asyncio.create_task(task("A", 3)),
        asyncio.create_task(task("B", 1)),
        asyncio.create_task(task("C", 2)),
    }
    # Return when first completes
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    print(f"First done: {[t.result() for t in done]}")
    print(f"Still pending: {len(pending)}")

    # Cancel remaining
    for t in pending:
        t.cancel()

    # -- create_task: fire-and-forget (but keep a reference!) --
    t = asyncio.create_task(task("background", 2))
    # Do other work while background task runs...
    await asyncio.sleep(1)
    print(f"Background done? {t.done()}")
    result = await t  # Wait for completion
    print(result)

asyncio.run(main())
```

The first two `print(results)` calls produce exactly the lists shown in their inline comments. The `wait` and `create_task` sections add this:

```text
First done: ['B completed in 1s']
Still pending: 2
Background done? False
background completed in 2s
```

**How to read this output:** `asyncio.wait(..., return_when=FIRST_COMPLETED)` returns the moment any one task finishes — here task `B` (1s delay) wins, so `done` holds just its result and `pending` still has `A` and `C`, which the code then cancels. This is the building block for "race the fastest replica" or "give up on stragglers" patterns. The `create_task` section shows the fire-and-forget shape: at the 1s mark the background task (2s) reports `done() == False`, then `await t` blocks until it actually finishes and yields its result.

> **Common pitfall:** A bare `asyncio.create_task(...)` whose return value you don't store can be garbage-collected mid-flight, silently cancelling the task. Always keep a reference (assign it, or hold it in a set) until the task completes — this is exactly the bug `TaskGroup` is designed to prevent.

### Async Synchronization Primitives

```python
import asyncio

# -- Semaphore: limit concurrency --
async def fetch_with_limit(sem, url):
    async with sem:
        print(f"Fetching {url} (concurrency: limited)")
        await asyncio.sleep(1)
        return f"Result from {url}"

async def main_semaphore():
    sem = asyncio.Semaphore(3)  # Max 3 concurrent fetches
    urls = [f"https://api.example.com/{i}" for i in range(10)]
    results = await asyncio.gather(*[fetch_with_limit(sem, url) for url in urls])
    # Only 3 URLs are fetched simultaneously, batched in groups

# -- Queue: async producer-consumer --
async def producer(queue, n):
    for i in range(n):
        await asyncio.sleep(0.1)
        item = f"item_{i}"
        await queue.put(item)
        print(f"Produced: {item}")
    await queue.put(None)  # Sentinel to signal completion

async def consumer(queue, name):
    while True:
        item = await queue.get()
        if item is None:
            await queue.put(None)  # Pass sentinel to other consumers
            break
        print(f"  {name} consumed: {item}")
        await asyncio.sleep(0.3)  # Simulate processing
        queue.task_done()

async def main_queue():
    queue = asyncio.Queue(maxsize=5)  # Bounded queue for backpressure
    await asyncio.gather(
        producer(queue, 10),
        consumer(queue, "Worker-1"),
        consumer(queue, "Worker-2"),
    )

asyncio.run(main_queue())
```

`asyncio.run(main_queue())` interleaves the producer and the two workers. The exact ordering varies slightly between runs, but it looks something like:

```text
Produced: item_0
  Worker-1 consumed: item_0
Produced: item_1
  Worker-2 consumed: item_1
Produced: item_2
Produced: item_3
  Worker-1 consumed: item_2
  Worker-2 consumed: item_3
Produced: item_4
...
Produced: item_9
  Worker-1 consumed: item_8
  Worker-2 consumed: item_9
```

**How to read this output:** Production and consumption are *interleaved*, not batched — the producer emits an item every 0.1s while each worker takes 0.3s to process, so two workers roughly keep pace with one producer. The two consumer lines never appear truly simultaneously because this is a single thread cooperatively switching at each `await`. In production this is the canonical job-queue shape: a fast ingest path feeding a bounded `Queue(maxsize=5)` that applies backpressure (the producer's `await queue.put(...)` blocks once five items are buffered), with a pool of workers draining it. The semaphore example above caps concurrency the same way — only 3 of the 10 URLs are in-flight at any instant.

### `asyncio.to_thread()` and `asyncio.run()`

```python
import asyncio
import time

def blocking_io_operation():
    """Simulate a blocking operation (e.g., legacy library, file I/O)."""
    time.sleep(2)
    return "blocking result"

async def main():
    # BAD: blocks the event loop
    # result = blocking_io_operation()

    # GOOD: run blocking code in a thread pool
    result = await asyncio.to_thread(blocking_io_operation)
    print(result)

    # You can also use loop.run_in_executor for more control
    loop = asyncio.get_running_loop()
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=4)
    result = await loop.run_in_executor(executor, blocking_io_operation)

# Entry point
asyncio.run(main())  # Creates event loop, runs main(), closes loop
```

After roughly 2 seconds (the blocking sleep, now off the event loop), this prints:

```text
blocking result
```

**What's happening:** `blocking_io_operation()` calls `time.sleep(2)`, which would freeze the loop if called directly. `asyncio.to_thread(...)` hands it to a worker thread and `await`s the result, so the event loop stays free to run other coroutines during those 2 seconds. This is the standard escape hatch for legacy synchronous libraries (a sync DB driver, `requests`, file I/O, a CPU-light C extension) inside an otherwise-async service. Note it only helps for *blocking I/O*; CPU-bound work still contends for the GIL and belongs in a process pool instead.

### Structured Concurrency with TaskGroup (Python 3.11+)

`TaskGroup` provides structured concurrency: tasks are managed as a group, and if any task raises an exception, all other tasks in the group are cancelled. This is much safer than loose `create_task()` calls where exceptions can be silently lost.

```python
import asyncio

async def process_item(item):
    await asyncio.sleep(0.5)
    if item == "bad":
        raise ValueError(f"Bad item: {item}")
    return f"Processed {item}"

# -- GOOD: TaskGroup (structured concurrency) --
async def main_taskgroup():
    try:
        async with asyncio.TaskGroup() as tg:
            task1 = tg.create_task(process_item("a"))
            task2 = tg.create_task(process_item("b"))
            task3 = tg.create_task(process_item("c"))
        # All tasks are guaranteed to be done when we exit the 'async with'
        print(task1.result(), task2.result(), task3.result())
    except* ValueError as eg:
        # ExceptionGroup handling (Python 3.11+)
        for exc in eg.exceptions:
            print(f"Caught: {exc}")

# -- DANGEROUS: loose create_task (unstructured) --
async def main_loose():
    t1 = asyncio.create_task(process_item("a"))
    t2 = asyncio.create_task(process_item("bad"))  # This will fail
    t3 = asyncio.create_task(process_item("c"))
    # If t2 fails, t1 and t3 keep running. Exception might be lost.
    # You need manual try/except and cleanup.

asyncio.run(main_taskgroup())
```

With the three "good" items, `main_taskgroup()` prints:

```text
Processed a Processed b Processed c
```

**What's happening:** All three tasks ran concurrently inside the `async with` block, and the group waited for every one of them before exiting — so calling `.result()` afterward is always safe. The `except*` clause never fires here because nothing failed. Had one task raised (e.g. `process_item("bad")`), the TaskGroup would immediately cancel its siblings and re-raise the failure(s) as an `ExceptionGroup`, which the `except* ValueError as eg` clause unpacks — printing `Caught: Bad item: bad`. That cancel-the-siblings-on-first-error guarantee is why structured concurrency is the interview-correct answer for "how do you fan out work without leaking tasks": no orphaned coroutines, no swallowed exceptions.

> **Key Takeaway:** `asyncio` enables high-concurrency I/O without threads. Never block the event loop. Use `asyncio.gather()` for simple concurrency, `TaskGroup` for structured concurrency with proper error handling, `asyncio.to_thread()` for integrating blocking code, and semaphores for rate limiting.

---

## Async Frameworks

### FastAPI: Async-First API Framework

FastAPI is built on Starlette and Pydantic, offering async-first design with automatic data validation and OpenAPI documentation.

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import asyncio

app = FastAPI()

# -- Pydantic model for request/response validation --
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w.-]+@[\w.-]+\.\w+$')
    age: int = Field(..., ge=0, le=150)

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

# -- Async endpoint --
@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    # Pydantic validates input automatically
    # Invalid data returns 422 with details
    user_id = await save_to_database(user)
    return UserResponse(id=user_id, name=user.name, email=user.email)

# -- Dependency injection --
async def get_db_session():
    session = await create_session()
    try:
        yield session
    finally:
        await session.close()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_db_session)):
    user = await db.fetch_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# -- Sync endpoints are automatically run in a thread pool --
@app.get("/sync-endpoint")
def sync_handler():
    # FastAPI detects this is sync (no 'async') and runs it in a thread
    import time
    time.sleep(1)  # Won't block the event loop
    return {"status": "ok"}
```

### ASGI Servers

ASGI (Asynchronous Server Gateway Interface) is the async evolution of WSGI. Multiple servers implement the ASGI spec.

```python
# Run FastAPI with Uvicorn (most common):
# $ uvicorn myapp:app --host 0.0.0.0 --port 8000 --workers 4

# Uvicorn: fastest, uses uvloop (libuv-based event loop)
# Hypercorn: supports HTTP/2 and HTTP/3
# Daphne: Django Channels server

# Production configuration example (uvicorn):
# $ uvicorn myapp:app \
#     --host 0.0.0.0 \
#     --port 8000 \
#     --workers 4 \          # Multiple worker processes
#     --loop uvloop \         # Fast event loop
#     --http httptools \      # Fast HTTP parser
#     --access-log \
#     --log-level info
```

### Django Async Support

Django has been adding async support incrementally since version 3.1.

```python
# -- Async views (Django 3.1+) --
from django.http import JsonResponse
import asyncio
import httpx

async def dashboard_view(request):
    """Fetch multiple APIs concurrently."""
    async with httpx.AsyncClient() as client:
        users, orders, stats = await asyncio.gather(
            client.get("https://api.internal/users"),
            client.get("https://api.internal/orders"),
            client.get("https://api.internal/stats"),
        )
    return JsonResponse({
        "users": users.json(),
        "orders": orders.json(),
        "stats": stats.json(),
    })

# -- Async ORM (Django 4.1+) --
from myapp.models import User

async def get_active_users(request):
    # Async ORM methods are prefixed with 'a'
    users = [user async for user in User.objects.filter(is_active=True)]
    count = await User.objects.acount()
    exists = await User.objects.filter(email="test@example.com").aexists()
    user = await User.objects.aget(pk=1)
    return JsonResponse({"count": count, "users": [u.name for u in users]})

# -- Mixing sync and async (sync_to_async / async_to_sync) --
from asgiref.sync import sync_to_async, async_to_sync

# Call sync code from async context
@sync_to_async
def get_user_sync(user_id):
    return User.objects.get(pk=user_id)  # Sync ORM call

async def my_async_view(request):
    user = await get_user_sync(1)
    return JsonResponse({"name": user.name})
```

> **Key Takeaway:** FastAPI is the go-to for new async APIs with its automatic validation and documentation. Use Uvicorn in production with multiple workers. Django's async support is maturing -- start with async views and use `sync_to_async` for gradual migration.

---

## Common Async Patterns

### Connection Pooling

Reusing connections avoids the overhead of establishing new TCP connections for every request.

```python
import asyncio
import aiohttp
import asyncpg

# -- aiohttp: reuse a single ClientSession --
async def fetch_many_urls():
    # BAD: new session (and TCP connection) per request
    async def bad_fetch(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.text()

    # GOOD: share one session (connection pool)
    async with aiohttp.ClientSession() as session:
        urls = [f"https://api.example.com/item/{i}" for i in range(100)]
        tasks = []
        for url in urls:
            tasks.append(fetch_one(session, url))
        results = await asyncio.gather(*tasks)

async def fetch_one(session, url):
    async with session.get(url) as resp:
        return await resp.json()

# -- asyncpg: PostgreSQL connection pool --
async def main():
    pool = await asyncpg.create_pool(
        dsn="postgresql://user:pass@localhost/mydb",
        min_size=5,     # Minimum connections to keep open
        max_size=20,    # Maximum connections in the pool
    )

    # Acquire a connection from the pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE active = $1", True)
        for row in rows:
            print(dict(row))

    # Pool handles connection lifecycle
    await pool.close()

asyncio.run(main())
```

Assuming the `users` table has a couple of active rows, the `print(dict(row))` loop emits something like:

```text
{'id': 1, 'name': 'Alice', 'active': True}
{'id': 2, 'name': 'Bob', 'active': True}
```

**How to read this output:** `conn.fetch(...)` returns a list of `asyncpg.Record` objects; wrapping each in `dict(row)` turns it into a plain mapping so you can see every column. The important detail is invisible in the output but central in production: `pool.acquire()` borrowed an *existing* connection rather than opening a new TCP+TLS+auth handshake (often 20-100ms), and returned it to the pool when the `async with` block exited. Under load this is the difference between reusing 20 warm connections and hammering Postgres with thousands of short-lived ones until it hits `max_connections` and starts refusing clients. The `$1` placeholder also keeps the query parameterized, so it is immune to SQL injection.

### Backpressure: Preventing Memory Exhaustion

When a producer creates work faster than consumers can process it, memory grows unboundedly. Backpressure mechanisms throttle the producer.

```python
import asyncio

# -- BAD: unbounded concurrency --
async def fetch_all_bad(urls):
    """Launches ALL requests simultaneously. 10,000 URLs = 10,000 connections!"""
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks)  # OOM or connection refused

# -- GOOD: semaphore-based concurrency limiting --
async def fetch_all_good(urls, max_concurrent=50):
    """Limit to max_concurrent simultaneous requests."""
    sem = asyncio.Semaphore(max_concurrent)

    async def fetch_limited(url):
        async with sem:
            return await fetch(url)

    return await asyncio.gather(*[fetch_limited(url) for url in urls])

# -- GOOD: bounded queue for producer-consumer --
async def producer(queue):
    for i in range(10000):
        data = await generate_data(i)
        await queue.put(data)  # Blocks if queue is full (backpressure!)
    await queue.put(None)

async def consumer(queue):
    while True:
        data = await queue.get()  # Blocks if queue is empty
        if data is None:
            break
        await process(data)

async def main():
    queue = asyncio.Queue(maxsize=100)  # Bounded! Producer waits when full
    await asyncio.gather(
        producer(queue),
        consumer(queue),
        consumer(queue),  # Multiple consumers
    )
```

### Cancellation and Timeouts

```python
import asyncio

async def long_running_task():
    try:
        print("Task started")
        await asyncio.sleep(100)
        print("Task completed")  # Never reached if cancelled
    except asyncio.CancelledError:
        print("Task was cancelled -- cleaning up")
        # Perform cleanup (close files, connections, etc.)
        raise  # Re-raise to properly propagate cancellation

async def main():
    # -- Timeout: cancel if too slow --
    try:
        result = await asyncio.wait_for(long_running_task(), timeout=2.0)
    except asyncio.TimeoutError:
        print("Task timed out!")

    # -- Manual cancellation --
    task = asyncio.create_task(long_running_task())
    await asyncio.sleep(1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Confirmed: task was cancelled")

    # -- Timeout context manager (Python 3.11+) --
    try:
        async with asyncio.timeout(2.0):
            await long_running_task()
    except TimeoutError:
        print("Timed out via context manager")

asyncio.run(main())
```

Running this prints:

```text
Task started
Task timed out!
Task started
Task was cancelled -- cleaning up
Confirmed: task was cancelled
Task started
Task was cancelled -- cleaning up
Timed out via context manager
```

**How to read this output:** Each of the three sections starts the task ("Task started") but the `await asyncio.sleep(100)` never finishes — the task is always cut short, so "Task completed" never appears. `wait_for` raises `TimeoutError` after 2s; manual `task.cancel()` injects a `CancelledError` into the coroutine, which the `except` block catches, runs cleanup, and re-raises so cancellation propagates correctly; the 3.11 `asyncio.timeout` context manager does the same thing more ergonomically. The load-bearing detail is the `raise` after cleanup: swallowing `CancelledError` instead of re-raising it is a classic bug that leaves a task looking alive after it was cancelled and breaks `TaskGroup`/timeout semantics.

> **Common pitfall:** Cleanup inside an `except asyncio.CancelledError` block must not itself `await` something slow without its own timeout — if the surrounding scope is being torn down (e.g. a shutdown timeout), a long cleanup `await` can be cancelled again or hang the shutdown. Keep cancellation cleanup fast and bounded.

### Testing Async Code

```python
import pytest
import asyncio

# -- pytest-asyncio: test async functions directly --
@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_data("test", delay=0.1)
    assert result == "test_result"

# -- Mocking async functions --
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_service():
    mock_client = AsyncMock()
    mock_client.get.return_value = {"id": 1, "name": "Alice"}

    service = UserService(client=mock_client)
    user = await service.get_user(1)

    assert user["name"] == "Alice"
    mock_client.get.assert_called_once_with("/users/1")

# -- aioresponses: mock HTTP requests --
from aioresponses import aioresponses

@pytest.mark.asyncio
async def test_api_call():
    with aioresponses() as m:
        m.get("https://api.example.com/data", payload={"key": "value"})

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.example.com/data") as resp:
                data = await resp.json()
                assert data == {"key": "value"}

# -- Testing with fixtures --
@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(dsn="postgresql://localhost/testdb")
    yield pool
    await pool.close()

@pytest.mark.asyncio
async def test_database_query(db_pool):
    async with db_pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1
```

> **Key Takeaway:** Always use connection pools, never create connections per-request. Use bounded queues and semaphores for backpressure. Handle cancellation with `try/except CancelledError` and always clean up in `finally`. Use `pytest-asyncio` and `AsyncMock` for testing.

*Last reviewed: 2026-06-08*
