[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.3 Operating Systems

> [!NOTE]
> **Beginner's Mental Model — Processes vs Threads:**
> Imagine a company. A **Process** is like an entire department in its own office building. It has its own desks, files, and resources, completely isolated from other departments (processes). A **Thread** is like an employee working inside that department. All employees (threads) in the same department share the same office space, files, and coffee machine (shared memory), but each employee has their own notebook and task list (stack and registers). If one department goes bankrupt, other departments keep running; but if someone makes a mess in the shared office, it affects all employees in that department.

### Processes & Threads

#### Processes

A **process** is an instance of a running program with its own independent memory space (code, data, heap, stack), file descriptors, and other OS resources. Processes are isolated from each other by the OS; one process cannot directly access another's memory.

```
Process Memory Layout:

  High Address
  +------------------+
  |      Stack       |  Function call frames (local vars, return address)
  |   (grows down)   |  Typical size limit: 8MB on Linux
  +------------------+
  |        |         |
  |        v         |
  |                  |
  |        ^         |
  |        |         |
  +------------------+
  |       Heap       |  Dynamic allocation (malloc, Python objects)
  |    (grows up)    |
  +------------------+
  |       BSS        |  Uninitialized global/static variables
  +------------------+
  |       Data       |  Initialized global/static variables
  +------------------+
  |       Text       |  Program code (read-only, shared)
  +------------------+
  Low Address
```

**Context switching** between processes is expensive (~1-10 microseconds) because the OS must save and restore the entire process state: CPU registers, program counter, stack pointer, memory maps (page tables), and flush the TLB (Translation Lookaside Buffer).

#### Threads

A **thread** is a lightweight unit of execution within a process. Threads within the same process share the same memory space (heap, data, code) but have their own **stack** and **register state**. Thread context switches are cheaper than process switches because memory maps do not change.

```
Process with 3 Threads:

  +-----------------------------------------------+
  | Process Memory Space                          |
  |                                               |
  |  Shared: Heap, Data, Code, File Descriptors   |
  |                                               |
  |  +----------+  +----------+  +----------+    |
  |  | Thread 1 |  | Thread 2 |  | Thread 3 |    |
  |  | Stack    |  | Stack    |  | Stack    |    |
  |  | Registers|  | Registers|  | Registers|    |
  |  | PC       |  | PC       |  | PC       |    |
  |  +----------+  +----------+  +----------+    |
  +-----------------------------------------------+
```

Python's **Global Interpreter Lock (GIL)** prevents multiple threads from executing Python bytecode simultaneously. This means CPU-bound Python code does not benefit from threading. Use `multiprocessing` for CPU-bound work and `threading` or `asyncio` for I/O-bound work.

```python
import threading
import multiprocessing
import time

# Threading: good for I/O-bound tasks (network, disk)
def fetch_url(url):
    """Simulated I/O-bound work."""
    import time
    time.sleep(1)  # Simulates network wait
    return f"Response from {url}"

urls = ["https://api.example.com/1", "https://api.example.com/2",
        "https://api.example.com/3"]

# Sequential: ~3 seconds
start = time.time()
results = [fetch_url(url) for url in urls]
print(f"Sequential: {time.time() - start:.1f}s")

# Threaded: ~1 second (I/O happens in parallel despite GIL)
start = time.time()
threads = [threading.Thread(target=fetch_url, args=(url,)) for url in urls]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Threaded: {time.time() - start:.1f}s")

# Multiprocessing: for CPU-bound work
def cpu_intensive(n):
    """CPU-bound work — GIL blocks threading here."""
    return sum(i * i for i in range(n))

# This actually runs on multiple CPU cores:
with multiprocessing.Pool(processes=4) as pool:
    results = pool.map(cpu_intensive, [10_000_000] * 4)
```

Running this prints something like (the threaded section stays near 1 second regardless of how many URLs you add, as long as the work is I/O-bound):

```text
Sequential: 3.0s
Threaded: 1.0s
```

**How to read this output:** The sequential loop pays the 1-second sleep three times in a row (3.0s). The threaded version starts all three sleeps at once and they overlap, so the wall-clock time collapses to roughly the single longest sleep (1.0s). This works *despite* the GIL because `time.sleep` (like real socket/disk waits) releases the GIL while blocked — the interpreter is free to run another thread. This is exactly why threading still helps a Django view that makes several blocking HTTP or database calls: the requests wait in parallel. The `multiprocessing` block prints nothing, but it is the one place real CPU work runs on multiple cores at once, because each process has its own GIL.

> **Common pitfall:** Reaching for `threading` to speed up CPU-bound Python (image resizing, parsing, math). The GIL serializes bytecode execution, so threaded CPU work runs no faster — and sometimes slower due to lock contention — than a single thread. Use `multiprocessing` or a native extension that releases the GIL.

#### Coroutines

**Coroutines** are user-space cooperative multitasking. Unlike threads, coroutines are not preempted by the OS — they explicitly yield control. This eliminates context-switch overhead (~100ns vs ~1-10us for threads) and avoids most synchronization issues.

```python
import asyncio

async def fetch_data(url, delay):
    """Simulated async I/O — coroutine yields during await."""
    print(f"  Starting fetch: {url}")
    await asyncio.sleep(delay)  # Non-blocking wait (yields to event loop)
    print(f"  Completed fetch: {url}")
    return f"data from {url}"

async def main():
    # Run 3 coroutines concurrently — total time ~1s, not ~3s
    results = await asyncio.gather(
        fetch_data("api/users", 1.0),
        fetch_data("api/products", 0.5),
        fetch_data("api/orders", 0.8),
    )
    print(f"All results: {results}")

asyncio.run(main())
```

Running this prints (the three fetches all start before any of them complete):

```text
  Starting fetch: api/users
  Starting fetch: api/products
  Starting fetch: api/orders
  Completed fetch: api/products
  Completed fetch: api/orders
  Completed fetch: api/users
All results: ['data from api/users', 'data from api/products', 'data from api/orders']
```

**How to read this output:** All three "Starting" lines print first because `asyncio.gather` schedules every coroutine before the event loop blocks on any of them. The "Completed" lines then arrive in *delay order* (0.5s products, 0.8s orders, 1.0s users) — not submission order — proving the waits overlapped on a single thread. Yet `results` preserves submission order, because `gather` returns values positionally regardless of finish order. This single-threaded concurrency is what lets one FastAPI/ASGI worker juggle thousands of in-flight requests without the per-thread stack cost.

#### Process States

```
Process State Diagram:

              fork/exec
  [Created] ----------> [Ready] <--------+
                          |               |
                     scheduled by OS      |
                          |          I/O complete
                          v          or event
                       [Running] -------> [Waiting/Blocked]
                          |                   (I/O, lock,
                          |                    sleep, etc.)
                     exit/terminate
                          |
                          v
                      [Terminated]
                      (Zombie until
                       parent waits)
```

#### IPC (Inter-Process Communication)

Since processes have isolated memory, they need explicit mechanisms to communicate:

| Mechanism | Direction | Speed | Use Case |
|---|---|---|---|
| Pipe | Unidirectional | Fast | Parent-child, shell pipelines (`ls \| grep`) |
| Named Pipe (FIFO) | Unidirectional | Fast | Unrelated processes, simple streaming |
| Message Queue | Bidirectional | Medium | Structured messages between processes |
| Shared Memory | Bidirectional | Fastest | High-throughput data sharing (needs locks) |
| Unix Domain Socket | Bidirectional | Fast | Same-host client-server (Docker, PostgreSQL) |
| Signal | Async notify | N/A | SIGTERM, SIGHUP, custom notifications |

```python
# Shared memory example with multiprocessing
from multiprocessing import Process, Value, Array

def worker(counter, data):
    """Modify shared memory from child process."""
    counter.value += 1
    for i in range(len(data)):
        data[i] = data[i] * 2

counter = Value('i', 0)       # Shared integer
data = Array('d', [1.0, 2.0, 3.0])  # Shared double array

p = Process(target=worker, args=(counter, data))
p.start()
p.join()

print(counter.value)   # 1
print(list(data))      # [2.0, 4.0, 6.0]
```

#### Copy-on-Write (COW) Fork

When a process calls `fork()`, the child gets a copy of the parent's memory. But the OS does not actually copy the memory pages immediately. Instead, both processes share the same physical pages (marked read-only). Only when one process **writes** to a page does the OS make a copy of that page. This makes forking fast even for large processes.

**Real-world use:** Redis uses COW fork for `BGSAVE` (background persistence). The child process writes the dataset to disk while the parent continues serving requests. Only pages modified by the parent during the save are actually copied.

#### Green Threads

**Green threads** (user-space threads) are managed by the language runtime rather than the OS kernel. The runtime multiplexes many green threads onto fewer OS threads (M:N threading model).

- **Python asyncio**: cooperative coroutines on a single thread
- **Go goroutines**: preemptive green threads multiplexed onto OS threads (M:N)
- **Erlang processes**: lightweight, isolated, message-passing green threads

#### Zombie and Orphan Processes

When a child process exits, it does not vanish immediately. The kernel keeps a tiny record (PID, exit status, resource usage) until the **parent** retrieves it with `wait()`/`waitpid()` — an act called **reaping**. A child that has exited but not yet been reaped is a **zombie** (`Z`/`defunct` in `ps`): it holds no memory, just a slot in the process table. A few zombies are harmless; a parent that *never* reaps leaks PID-table entries until the system can no longer fork ("resource temporarily unavailable").

An **orphan** is the opposite timing problem: the *parent* dies first while the child is still running. The kernel **re-parents** the orphan to PID 1 (the init process), which is responsible for reaping it when it eventually exits. So orphans get cleaned up automatically — *as long as PID 1 actually reaps.*

```python
import os, time

pid = os.fork()
if pid == 0:                       # child
    os._exit(0)                    # exits immediately -> becomes a ZOMBIE...
else:                              # parent
    time.sleep(2)                  # ...until the parent calls wait()
    # `ps` here would show the child as <defunct>
    os.waitpid(pid, 0)             # reap it — zombie disappears
```

```console
$ ps -o pid,ppid,stat,comm
  PID  PPID STAT COMMAND
 4120  4001 S    python3
 4121  4120 Z    python3 <defunct>   <-- zombie: exited, awaiting reap
```

**How to read this output:** The `Z` state and `<defunct>` label mark a process that has finished but whose exit status nobody has collected. It consumes a PID slot and nothing else. This becomes a production incident in **containers**, where your application is often PID 1. A normal init (systemd) reaps orphans automatically, but a bare app process running as PID 1 usually does **not** install a `SIGCHLD` handler — so re-parented orphans pile up as zombies, and worse, signals like `SIGTERM` may not be forwarded, breaking graceful shutdown. The fix is a minimal init shim: run `docker run --init` (which injects `tini`), add `tini` as the entrypoint, or use a proper init. This is exactly why Dockerfiles for apps that spawn subprocesses (a shell wrapper, a supervisor, Celery forking workers) need `--init` or `tini`.

> **Common pitfall:** Treating "PID 1 in a container" like any other process. PID 1 has special kernel semantics — it does not get default signal handlers, and it inherits all orphans. An app running as PID 1 without init responsibilities silently accumulates zombies and ignores `SIGTERM`, causing 10-second shutdowns (Docker then `SIGKILL`s it) and PID exhaustion in long-lived containers.

> **Key Takeaway:** Understanding processes, threads, and coroutines is fundamental to building performant backend systems. In Python/Django: use multiprocessing for CPU-bound parallelism, threading for blocking I/O concurrency (database calls, HTTP requests), and asyncio for high-concurrency I/O (WebSockets, many simultaneous API calls). The GIL makes this choice more important in Python than in most other languages.

---

### CPU Architecture & Caches

Asymptotic complexity assumes every memory access costs the same. On real hardware it does not — by orders of magnitude. Understanding the memory hierarchy explains why two algorithms with identical Big-O can differ 10-100x in wall-clock time.

#### The Memory Hierarchy

Memory gets larger and slower at every level. The approximate latencies (the famous "numbers every programmer should know") span seven orders of magnitude:

```
Level            Latency (approx)    Relative ("if L1 = 1 second")
-----            ----------------    -----------------------------
CPU register     < 1 ns              instant
L1 cache         ~1 ns               1 second
L2 cache         ~4 ns               4 seconds
L3 cache         ~10-20 ns           ~15 seconds
Main memory (RAM)~100 ns             ~2 minutes
NVMe SSD         ~100 us             ~1 day
Spinning disk    ~10 ms              ~4 months
Network (same DC)~0.5 ms             ~6 days
```

The whole game of performance engineering is **keeping the hot working set in the fast levels**. A cache miss to main memory costs ~100x an L1 hit; a page fault to disk costs ~100,000x. This is *why* algorithms with good locality (arrays, sequential scans) routinely beat "asymptotically equal" pointer-chasing structures (linked lists, scattered trees).

#### Cache Lines and Prefetching

The CPU never fetches a single byte — it fetches a whole **cache line** (typically **64 bytes**). Touch one element of an array and its neighbors come along for free. So **sequential access is nearly free** (each line serves ~8-16 elements, and the hardware **prefetcher** detects the stride and fetches the *next* line before you ask), while **random access thrashes the cache** (every access may pull a fresh line and evict a useful one).

```python
# Same number of operations, very different cache behavior.
N = 4096
matrix = [[0] * N for _ in range(N)]

# Row-major traversal: walks memory sequentially -> cache-friendly
for i in range(N):
    for j in range(N):
        matrix[i][j] += 1

# Column-major traversal: jumps a full row each step -> cache-hostile
for j in range(N):
    for i in range(N):
        matrix[i][j] += 1
```

```text
row-major (i, j):  0.62 s
col-major (j, i):  3.10 s   (~5x slower — identical work, worse locality)
```

**How to read this output:** Both loops do exactly N² increments, yet the column-major version is several times slower purely because it strides across memory and defeats the prefetcher — each inner step lands on a different cache line. (In a C/NumPy contiguous array the gap is even larger; pure-Python list-of-lists hides some of it behind interpreter overhead.) The lesson for backend work: iterate data in the order it is laid out (row-major for C/NumPy arrays, the index order for database scans), and prefer compact, contiguous structures for hot paths.

#### False Sharing

A subtle multi-threaded trap: two threads modifying **different** variables that happen to land on the **same cache line**. Even though there is no logical sharing, the cache-coherence protocol invalidates the line on every write, ping-ponging it between cores and destroying performance.

```
Two counters on the SAME 64-byte cache line:

  Core 0 writes counter_a ─┐   invalidates the line on Core 1
  Core 1 writes counter_b ─┘   invalidates the line on Core 0
  -> the line bounces between cores; throughput collapses though the
     two threads never touch the SAME variable.

Fix: pad/align so each hot per-thread variable sits on its own cache line.
```

This is why high-performance concurrent code **pads** per-thread counters/state to 64 bytes (e.g., Java's `@Contended`, padded structs in C, per-core sharded counters). If a multi-threaded program scales *worse* than single-threaded for no obvious reason, false sharing is a prime suspect.

#### NUMA

On multi-socket servers, memory is **Non-Uniform**: each CPU socket has a local memory bank it reaches quickly, and accessing another socket's memory crosses an interconnect (slower, higher latency). The OS tries to allocate a thread's memory on its local node, but a thread migrated to another socket — or memory allocated before the thread was pinned — pays the cross-node penalty. Latency-sensitive workloads (databases, low-latency services) **pin threads and memory** with `numactl --cpunodebind --membind` or thread affinity to stay local.

#### Branch Prediction & Speculative Execution

Modern CPUs are deeply pipelined: they start executing instructions *after* a branch (`if`) before knowing whether the branch is taken. The **branch predictor** guesses the outcome to keep the pipeline full; a correct guess is free, but a **misprediction** flushes the pipeline and costs ~10-20 cycles. This is the well-known reason that processing **sorted** data can be dramatically faster than unsorted — predictable branches (e.g., `if value > threshold` on sorted input) are almost always guessed right.

```python
# A branch whose outcome is predictable runs faster than the same branch
# fed random data, even though the instruction count is identical:
#   - sorted input:   the `if` is taken in a long run, then not -> easy to predict
#   - shuffled input: the `if` flips unpredictably -> frequent mispredictions
```

**Speculative execution** is the same mechanism applied broadly — the CPU does work it might need to throw away. It is a huge performance win but also the root of the **Spectre** and **Meltdown** side-channel attacks (2018): speculatively-executed instructions leave measurable traces in the cache, letting an attacker infer memory they should not be able to read. The mitigations (kernel page-table isolation, retpolines, microcode updates) imposed a real, measurable performance tax on syscall-heavy workloads — a rare case where a CPU *architecture* detail showed up directly in production latency budgets.

> **Key Takeaway:** Big-O ignores the memory hierarchy, but production performance lives in it. Favor sequential, cache-line-friendly access; pad hot per-thread state to avoid false sharing; pin memory on NUMA boxes; and remember that predictable branches and good locality can make an "asymptotically equal" algorithm several times faster. When a profiler shows a tight loop is slow despite a good Big-O, the answer is almost always cache misses or branch mispredictions, not the algorithm on paper.

---

### Memory Management

> [!NOTE]
> **Beginner's Mental Model — Virtual Memory:**
> Imagine you are a student and the school librarian gives you a private catalog desk that makes it look like you have the entire library's collection to yourself (Virtual Memory). In reality, the library only has a limited number of physical bookshelves (Physical RAM). When you request a specific book from your catalog, the librarian secretly runs to the back, fetches that book, and puts it on your desk. If you run out of desk space, the librarian might temporarily store some of your books in a box in the basement (Swap/Disk).

#### Virtual Memory

Each process sees a contiguous address space (e.g., 0 to 2^48 on 64-bit systems) that is **virtual** — it does not correspond directly to physical RAM. The OS maintains a **page table** that maps virtual pages to physical frames (or marks them as not-present, triggering a page fault that may load from disk).

```
Virtual Memory Mapping:

  Process A Virtual Space          Physical RAM          Process B Virtual Space
  +------------------+                                   +------------------+
  | Page 0 (code)    |--+     +------------------+  +---| Page 0 (code)    |
  | Page 1 (data)    |--+-+   | Frame 0 (A code) |  |   | Page 1 (data)    |--+
  | Page 2 (heap)    |--+-+-+ | Frame 1 (A data) |  |   | Page 2 (heap)    |--+-+
  | Page 3 (stack)   |  | | | | Frame 2 (shared) |--+   | Page 3 (stack)   |  | |
  +------------------+  | | | | Frame 3 (A heap) |      +------------------+  | |
                        | | | | Frame 4 (B data) |<--------------------------+ |
                        | | +-| Frame 5 (A stack)|                             |
                        | +---> Frame 2 (shared) | (shared library!)           |
                        +----->                   | Frame 6 (B heap) |<--------+
                              +------------------+

  Page size: typically 4KB
  Huge pages: 2MB or 1GB (reduces TLB pressure for large working sets)
```

#### TLB (Translation Lookaside Buffer)

The TLB is a small, fast CPU cache that stores recent virtual-to-physical page translations. A TLB hit avoids a full page table walk (which may involve multiple memory accesses). The TLB typically holds 64-1024 entries, so with 4KB pages, it covers 256KB to 4MB of memory. **Huge pages** (2MB) allow the same number of TLB entries to cover 128MB to 2GB, dramatically reducing TLB misses for applications with large working sets (databases, JVMs, Redis).

#### Stack vs Heap

```
Function Call Stack:

  main() calls funcA() calls funcB():

  High Address
  +-------------------+
  |   main() frame    |  local vars, return addr
  +-------------------+
  |   funcA() frame   |  local vars, return addr
  +-------------------+
  |   funcB() frame   |  local vars, return addr   <-- Stack Pointer (SP)
  +-------------------+
  Low Address

  When funcB() returns, SP moves back up to funcA's frame.
  Stack overflow if recursion goes too deep (default ~8MB on Linux).
```

The **stack** is fast (allocation = moving the stack pointer) but limited in size and scope (variables die when the function returns). The **heap** is flexible (allocate any size, any lifetime) but slower (allocator must find free blocks, fragmentation over time).

Memory allocators like **jemalloc** (used by Redis, Rust) and **tcmalloc** (Google) reduce heap fragmentation and improve multi-threaded allocation performance through thread-local caches and size-class segregation.

#### Python Memory Management

Python uses a two-layer garbage collection strategy:

**Reference counting** is the primary mechanism: every object has a count of references pointing to it. When the count drops to zero, the object is immediately freed. This is fast and deterministic but cannot handle **reference cycles** (A references B, B references A).

**Generational garbage collector** handles cycles. It tracks objects in three generations:

```
Python's Generational GC:

  Generation 0 (young)     Generation 1 (middle)    Generation 2 (old)
  +-------------------+    +-------------------+    +-------------------+
  | New objects        |    | Survived 1 GC     |    | Survived 2+ GCs   |
  | Collected OFTEN    |--->| Collected less     |--->| Collected RARELY   |
  | (every ~700 allocs)|    | often              |    |                    |
  +-------------------+    +-------------------+    +-------------------+

  Hypothesis: most objects die young ("generational hypothesis")
  So we check young objects frequently, old objects rarely.
```

```python
import gc
import sys

# Reference counting
a = [1, 2, 3]
print(sys.getrefcount(a))  # 2 (a + the getrefcount argument)
b = a
print(sys.getrefcount(a))  # 3 (a + b + argument)
del b
print(sys.getrefcount(a))  # 2 again

# Circular reference — refcount alone cannot free these
class Node:
    def __init__(self):
        self.ref = None

a = Node()
b = Node()
a.ref = b
b.ref = a  # Circular reference!
del a, b   # Refcounts drop to 1, not 0 — not freed by refcount

# The generational GC detects and collects the cycle
gc.collect()  # Force a full collection

# GC tuning
print(gc.get_threshold())  # (700, 10, 10) — default thresholds
gc.set_threshold(1000, 15, 15)  # Raise thresholds to reduce GC frequency

# For latency-sensitive code (e.g., real-time bidding):
gc.disable()  # Disable automatic GC
# ... do latency-sensitive work ...
gc.enable()
gc.collect()  # Manually collect when latency is not critical
```

#### Memory-Mapped Files

`mmap` maps a file (or anonymous memory) into the process's virtual address space. The OS lazily loads pages on demand and can share the mapping between processes.

```python
import mmap

# Memory-map a large file for efficient processing
with open("/var/log/syslog", "r+b") as f:
    # Map the entire file into memory (lazy — not all loaded at once)
    mm = mmap.mmap(f.fileno(), 0)

    # Search the file as if it were a string (no need to read it all into RAM)
    pos = mm.find(b"error")
    if pos != -1:
        mm.seek(pos)
        line = mm.readline()
        print(f"Found at offset {pos}: {line}")

    mm.close()
```

If the log contains the word `error`, this prints something like (the offset and line text depend on your file's contents):

```text
Found at offset 48213: b'Jun  4 09:12:01 host app[1234]: error: connection refused\n'
```

**How to read this output:** `mm.find` scans the file's bytes as if they were one giant in-memory buffer, but the OS only faults in the 4KB pages it actually touches during the scan — so you can search a multi-gigabyte log without the RSS of your process ballooning to the file size. The returned offset is a byte position into the file, and `readline()` reads from there to the next newline. In production this is how tools grep huge files cheaply; the trade-off is that random access across a file larger than RAM still costs page faults (disk reads), so it shines for scanning, not for repeated random lookups.

> **Common pitfall:** Opening the file in text mode (`"r"`) instead of binary (`"r+b"`). `mmap` operates on bytes, so your search needles must be `bytes` literals (`b"error"`, not `"error"`) and the file must be opened in binary mode, or you will get a type error.

**Real-world use:** Database page caches (SQLite, MongoDB), shared memory IPC, large file processing without loading into RAM, efficient log scanning.

#### OOM Killer and Memory Monitoring

When Linux runs out of memory, the **OOM killer** selects and kills a process to free RAM. It chooses based on an OOM score (higher = more likely to be killed) influenced by memory usage and `oom_score_adj`. In containerized environments, **cgroups** set hard memory limits per container — exceeding the limit kills the container, not a random process.

Key memory metrics:

- **RSS (Resident Set Size):** actual physical memory currently used
- **VSZ (Virtual Size):** total virtual address space mapped (includes shared libraries, mmap'd files)
- **USS (Unique Set Size):** memory unique to this process (not shared)

```bash
# Monitor process memory
ps aux --sort=-%mem | head -10
cat /proc/$(pidof python3)/status | grep -E 'VmRSS|VmSize|VmPeak'

# Per-container memory limits (Docker)
# docker run --memory=512m --memory-swap=512m myapp
```

The `grep` on `/proc/.../status` prints something like (values are in kB):

```console
$ cat /proc/$(pidof python3)/status | grep -E 'VmRSS|VmSize|VmPeak'
VmPeak:    412880 kB
VmSize:    398220 kB
VmRSS:     156432 kB
```

**How to read this output:** `VmRSS` (~156 MB here) is the physical RAM actually resident — this is the number the OOM killer and your container's memory cgroup care about. `VmSize` (~398 MB) is the total virtual address space mapped, which is almost always larger than RSS because it counts shared libraries and lazily-allocated/`mmap`'d regions that aren't resident. `VmPeak` is the high-water mark of `VmSize`. In an interview the key point is: a high VSZ alone is not a leak — watch RSS climbing steadily over time, because that is what triggers OOM kills in a 512 MB container.

> **Key Takeaway:** Memory management is where many production performance issues live. Understanding virtual memory, the TLB, stack vs heap, and Python's GC helps you diagnose memory leaks, reduce GC pauses, and configure memory limits. Use `tracemalloc` in Python to profile memory allocations, and always set memory limits on containers to prevent OOM cascades.

---

### Concurrency & Synchronization Primitives

The moment two threads (or processes) touch shared mutable state, you need synchronization. These primitives are the vocabulary of every concurrent system, and getting them wrong produces the hardest bugs in backend engineering — ones that appear only under load and vanish when you attach a debugger.

#### Race Conditions and Critical Sections

A **race condition** is a bug where the result depends on the unpredictable *interleaving* of operations on shared state. The classic example is `counter += 1`, which is not atomic — it is read, add, write, and two threads can interleave to lose an update.

```python
import threading

counter = 0
def increment():
    global counter
    for _ in range(100_000):
        counter += 1          # NOT atomic: read, +1, write-back

threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(counter)                # expected 400000 — but often less
```

```text
312847
```

**How to read this output:** Four threads each adding 100,000 *should* yield 400,000, but the result is lower and varies run-to-run because increments interleave and overwrite each other. (In CPython the GIL makes a *single* bytecode atomic, but `+=` compiles to several bytecodes, so the race survives even under the GIL — a common misconception in interviews.) The region of code that must not run concurrently — here, the read-modify-write — is the **critical section**, and it must be protected by a lock.

#### Mutex, Semaphore, Condition Variable

- **Mutex (mutual exclusion lock):** only one holder at a time. Wrap the critical section in `lock.acquire()`/`release()` — in Python always via a `with` block so it is released on every path, including exceptions.
- **Semaphore:** a counter permitting up to **N** concurrent holders. A binary semaphore (N=1) behaves like a mutex; larger N **bounds concurrency** — e.g., "at most 10 simultaneous outbound DB connections."
- **Condition variable:** lets a thread *wait until a predicate becomes true*, woken by another thread's `notify()`. The producer-consumer pattern is built on this.

```python
import threading

lock = threading.Lock()
counter = 0
def safe_increment():
    global counter
    for _ in range(100_000):
        with lock:            # critical section — exactly one thread at a time
            counter += 1

# Semaphore: cap concurrency at 10
db_slots = threading.Semaphore(10)
def query_db():
    with db_slots:            # blocks if 10 are already inside
        ...                   # at most 10 threads run this concurrently

# Condition variable — ALWAYS re-check the predicate in a while loop:
cond = threading.Condition()
queue = []
def consumer():
    with cond:
        while not queue:                  # NOT `if` — guards against spurious wakeups
            cond.wait()                   # releases lock, sleeps, re-acquires on wake
        item = queue.pop(0)
```

> **Common pitfall:** Waiting on a condition variable with `if` instead of `while`. A thread can wake up **without** the predicate being true — a **spurious wakeup** (and even without true spuriousness, another thread may have grabbed the item first). Always loop: `while not predicate: cond.wait()`. This single mistake causes "impossible" empty-queue pops under load.

#### Spinlocks, Futexes, and Read-Write Locks

- **Spinlock:** instead of sleeping, the thread **busy-waits** in a tight loop until the lock frees. Cheap for *very short* critical sections on multicore (no context-switch cost); wasteful otherwise (burns a CPU). Used inside kernels and lock-free libraries.
- **Futex (fast userspace mutex, Linux):** the building block of `pthread` mutexes. The uncontended case is resolved entirely in user space with an atomic compare-and-swap (no syscall); only when there is contention does it fall into the kernel to sleep/wake. This is why an uncontended lock is nearly free.
- **Read-write lock:** allows **many concurrent readers OR one exclusive writer**. Ideal for read-heavy shared state (a config cache read constantly, written rarely). The risk is **writer starvation** — a steady stream of readers can keep a writer waiting forever unless the lock is writer-preferring.

#### Atomic Operations and CAS

**Compare-and-swap (CAS)** is a hardware instruction that atomically does "if this memory still equals the value I read, replace it; otherwise tell me it changed." It is the foundation of **lock-free** programming: reference counts, lock-free queues, and **optimistic concurrency control** (read a version, compute, then CAS — retry if someone else won). Lock-free code avoids the deadlock/priority-inversion failures of locks, at the cost of subtle correctness reasoning (the "ABA problem", memory ordering).

#### Deadlock, Livelock, Starvation

A **deadlock** is a cycle of threads each holding a resource the next one needs. It requires **all four Coffman conditions** simultaneously — break any one and deadlock is impossible:

```
Coffman conditions (ALL four must hold for deadlock):
  1. Mutual exclusion   - resources can't be shared
  2. Hold and wait      - a thread holds one resource while waiting for another
  3. No preemption      - resources can't be forcibly taken away
  4. Circular wait      - a cycle: T1 waits on T2 waits on ... waits on T1

Classic deadlock — inconsistent lock ordering:
  Thread A: lock(X) ... lock(Y)        Thread B: lock(Y) ... lock(X)
  -> A holds X waiting for Y; B holds Y waiting for X. Forever.

Fix: GLOBAL LOCK ORDERING. Every thread acquires locks in the same order
     (e.g., always X before Y). This breaks "circular wait".
```

The most practical defense is a **global lock-ordering discipline**: define a total order over locks and always acquire them in that order. Related failures:

- **Livelock:** threads keep changing state in response to each other but make no progress (two people stepping aside in a corridor, repeatedly, in the same direction). They are not blocked — they are busy doing nothing useful.
- **Starvation:** a thread *never* gets the resource because others keep jumping ahead (e.g., writer starvation under a reader-preferring RW lock).

#### Priority Inversion

A **low**-priority thread holds a lock that a **high**-priority thread needs; meanwhile a **medium**-priority thread preempts the low one, so the low thread can't run to release the lock — and the high-priority thread is stuck waiting on the medium one indirectly. The fix is **priority inheritance**: the lock-holder temporarily inherits the priority of the highest-priority waiter so it can finish and release. This famously caused the **Mars Pathfinder** to repeatedly reset on the surface of Mars in 1997, fixed by enabling priority inheritance remotely.

> **Key Takeaway:** Protect every critical section, prefer `with lock:` so locks are always released, re-check condition predicates in a `while` loop, and bound concurrency with semaphores rather than unbounded thread spawning. To avoid deadlock, impose a consistent global lock order. And remember: in CPython the GIL serializes bytecode but does **not** make multi-step operations like `+=` atomic — you still need real locks for shared mutable state.

---

### Scheduling

The OS scheduler decides which runnable thread gets the CPU next. How it does this — and how you size your own thread/worker pools on top of it — directly determines a service's throughput and tail latency.

#### Preemptive vs Cooperative

- **Preemptive scheduling:** the OS forcibly interrupts a running thread on a timer (the **time slice** / quantum) and switches to another. No thread can monopolize the CPU. This is how OS threads and processes are scheduled. The cost is **context-switch overhead** and cache pollution on every switch.
- **Cooperative scheduling:** a task runs until it **voluntarily yields** (asyncio coroutines at `await`, generators at `yield`). Simpler to reason about — no preemption means no surprise interleavings between yield points, so you need far fewer locks. The danger is that **one CPU-bound task that never yields stalls everything** (a synchronous `time.sleep` or a heavy computation inside an async event loop freezes the whole loop).

#### The Linux CFS (and EEVDF)

Linux's longtime default was the **Completely Fair Scheduler (CFS)**, which allocates CPU *proportionally* rather than via fixed time slices. Each task accumulates **virtual runtime (vruntime)** — roughly, how much CPU it has consumed, weighted by priority. The scheduler always runs the task with the **smallest vruntime**, so threads that have run less get the CPU next, approximating "everyone gets a fair share." (Recent kernels, 6.6+, replaced CFS with **EEVDF**, which adds latency-sensitivity but keeps the same fair-share spirit.)

- **`nice` value** (-20 to +19): biases a task's share. Lower nice = higher priority = larger CPU slice; a "nicer" (higher) value yields more to others. It weights vruntime accumulation, not a hard guarantee.
- **Real-time classes** (`SCHED_FIFO`, `SCHED_RR`): for latency-critical work that must run ahead of all normal tasks. A runaway `SCHED_FIFO` thread can lock up a core, so these are used sparingly (audio, control loops, some trading systems).

#### Pool Sizing

The most common practical scheduling decision a backend engineer makes is **how many workers/threads to run**. Oversubscribing — far more busy threads than cores — degrades throughput via context-switch thrash and cache pollution, while undersubscribing leaves cores idle. The rule of thumb depends on what the work *does*:

```
CPU-bound work  (parsing, hashing, image resize, math):
    pool size  ~=  number of cores
    More threads than cores just thrash; they can't run in parallel anyway.

I/O-bound work  (DB queries, HTTP calls, disk):
    pool size  >>  number of cores
    Threads spend most of their time blocked/waiting, so many can overlap
    on few cores. Size to the concurrency you need, bounded by the
    downstream's capacity (e.g., the DB connection-pool limit).

Little's Law sanity check:  concurrency = throughput x latency
    e.g., 1000 req/s x 0.05 s each  ->  ~50 in-flight  ->  ~50 workers.
```

**How to read this guidance:** For CPU-bound work, going past core count buys nothing (the GIL makes this *especially* true in Python — use processes, sized to cores). For I/O-bound work, the threads are mostly asleep waiting on the network or disk, so dozens or hundreds can share a few cores productively — but the real ceiling is usually the **downstream resource** (a 20-connection DB pool means 200 worker threads will just queue on the pool). Use Little's Law (`concurrency = throughput × latency`) to derive a starting pool size, then measure: watch for rising context-switch counts (`vmstat`) and tail latency as the signal that you have oversubscribed.

> **Key Takeaway:** Match concurrency to the work. CPU-bound pools ≈ cores (processes in Python); I/O-bound pools can be much larger but are capped by the slowest downstream dependency. Understand that the OS scheduler is already multiplexing fairly via CFS/vruntime — your job is to avoid fighting it by oversubscribing CPUs, and to keep cooperative event loops free of blocking calls so one task never starves the rest.

---

> [!NOTE]
> **Beginner's Mental Model — System Calls:**
> Think of your application as a customer in a restaurant (user space) and the operating system kernel as the kitchen (kernel space). You cannot walk into the kitchen and cook or grab food yourself because it's restricted for safety and order. Instead, you look at the menu and place an order through a waiter. The waiter taking your order and bringing back the food is a **System Call**—a controlled way to ask the kitchen to do something for you (like reading a file or sending a network packet).

### I/O Models

#### Blocking I/O

The simplest model: a thread calls `read()` or `write()` and **blocks** (sleeps) until the operation completes. While waiting, the thread cannot do anything else.

```
Blocking I/O:

  Thread          Kernel
    |               |
    |-- read() ---->|
    |   (blocked)   |--- wait for data ---|
    |   (blocked)   |<--- data arrives ---|
    |<-- data ------|
    |               |
```

This works fine when each connection gets its own thread (**thread-per-connection** model), but threads are expensive (~8MB stack each). Supporting 10,000 concurrent connections would require 10,000 threads = ~80GB of stack memory alone, plus the overhead of context switching.

#### Non-Blocking I/O

With non-blocking I/O, `read()` returns immediately with either data or an `EAGAIN`/`EWOULDBLOCK` error indicating no data is available yet. The application must poll repeatedly — this is **busy-waiting** and wastes CPU cycles.

> [!NOTE]
> **Beginner's Mental Model — epoll and io_uring:**
> Imagine a waiter (single thread) managing 100 tables (connections).
> - With basic I/O, the waiter stands at one table waiting for them to decide what to order, ignoring all other tables.
> - With **epoll**, the waiter gives every table a buzzer. When a table is ready to order, they press the buzzer, and the waiter goes directly to that specific table.
> - With **io_uring**, tables write their orders on a shared notepad (submission queue). The waiter processes the notepad in the background and writes the ready food details on another notepad (completion queue), allowing the table to pick it up without ever interrupting the waiter.

#### I/O Multiplexing

I/O multiplexing lets a single thread monitor multiple file descriptors and react when any of them becomes ready. This is the foundation of event-driven servers.

```
I/O Multiplexing (epoll):

  Single Thread              Kernel
      |                        |
      |-- epoll_wait() ------->|
      |   (blocked, but        |  Monitors 10,000 sockets simultaneously
      |    all sockets at once) |
      |<-- [fd3, fd7 ready] ---|
      |                        |
      |-- read(fd3) ---------->|  Now read only the ready ones
      |<-- data --------------|
      |-- read(fd7) ---------->|
      |<-- data --------------|
      |                        |
      |-- epoll_wait() ------->|  Go back to waiting
```

| Mechanism | Time Complexity | FD Limit | Notes |
|---|---|---|---|
| `select` | O(n) per call | 1024 (FD_SETSIZE) | Portable, but does not scale |
| `poll` | O(n) per call | No limit | Better than select, still O(n) |
| `epoll` | O(1) per event | No practical limit | Linux-specific, edge/level triggered |
| `kqueue` | O(1) per event | No practical limit | BSD/macOS, similar to epoll |

**epoll** is the workhorse of Linux high-performance servers. It has two trigger modes:

- **Level-triggered** (default): keeps notifying as long as the fd is ready (like poll). Simpler but generates more events.
- **Edge-triggered**: notifies only when the fd state changes (not ready -> ready). More efficient but you must drain all available data on each notification or you will miss events.

```python
# Python's asyncio uses epoll (on Linux) internally
# Here's what it looks like at the low level with selectors:
import selectors
import socket

sel = selectors.DefaultSelector()  # Uses epoll on Linux, kqueue on macOS

def accept(sock, mask):
    conn, addr = sock.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read)

def read(conn, mask):
    data = conn.recv(1024)
    if data:
        conn.send(data)  # Echo server
    else:
        sel.unregister(conn)
        conn.close()

# Setup
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 8080))
server.listen(100)
server.setblocking(False)
sel.register(server, selectors.EVENT_READ, accept)

# Event loop — single thread handles thousands of connections
# while True:
#     events = sel.select()  # Blocks until something is ready
#     for key, mask in events:
#         callback = key.data
#         callback(key.fileobj, mask)
```

#### io_uring

`io_uring` (Linux 5.1+) is the latest evolution in async I/O. It uses two ring buffers in shared memory — a **submission queue** (SQ) and a **completion queue** (CQ) — between the application and the kernel. After initial setup, submissions and completions require **no system calls**, dramatically reducing overhead.

```
io_uring Architecture:

  User Space                    Kernel Space
  +-------------------+        +-------------------+
  | Submission Queue   |------->| Process requests  |
  | (app writes here)  |        | (file I/O, net,   |
  +-------------------+        |  etc.)             |
                                |                   |
  +-------------------+<-------| Completion Queue  |
  | (app reads here)   |        | (results appear   |
  +-------------------+        |  here)            |
                                +-------------------+

  No syscalls needed for submit/complete after setup!
  Used by modern high-performance servers and databases.
```

#### Zero-Copy I/O

**`sendfile()`** sends file data directly from the kernel's page cache to a socket without ever copying it to user space. Traditional file serving requires: disk -> kernel buffer -> user buffer -> kernel socket buffer -> NIC. With sendfile: disk -> kernel buffer -> NIC (two fewer copies).

**`splice()`** achieves similar zero-copy for pipe-based transfers.

**Real-world use:** Nginx uses sendfile for static file serving. Kafka uses sendfile to send log segments to consumers.

#### Buffered I/O and Page Cache

The Linux kernel maintains a **page cache** that caches file data in RAM. Reads first check the page cache; writes go to the page cache and are flushed to disk later (write-back caching).

- **`fsync()`**: flushes file data and metadata to disk (guarantees durability)
- **`fdatasync()`**: flushes only file data, not metadata (faster)
- **`O_DIRECT`**: bypasses the page cache entirely — used by databases (PostgreSQL, MySQL) that manage their own buffer pool

> **Key Takeaway:** Understanding I/O models is crucial for building scalable servers. Modern Python web frameworks (Django with ASGI, FastAPI, Starlette) use asyncio under the hood, which uses epoll/kqueue for I/O multiplexing. This is why a single ASGI worker can handle thousands of concurrent WebSocket connections while a WSGI worker can handle only one request at a time per thread.

---

### File Systems

#### Inodes and File Descriptors

An **inode** stores metadata about a file: permissions, ownership, timestamps, size, and pointers to data blocks. The filename is stored in the directory (which maps names to inode numbers). This is why hard links work — multiple names can point to the same inode.

**File descriptors** are per-process integer handles that reference kernel file objects. Every process starts with three: 0 (stdin), 1 (stdout), 2 (stderr). The per-process limit defaults to 1024 on many systems but can be raised.

```bash
# Check and raise file descriptor limits
ulimit -n            # Current per-process limit (e.g., 1024)
ulimit -n 65536      # Raise for current shell session

# System-wide limit
cat /proc/sys/fs/file-max    # e.g., 9223372036854775807

# For a running process
ls /proc/$(pidof nginx)/fd | wc -l   # Count open file descriptors
```

A typical session looks like:

```console
$ ulimit -n
1024
$ ls /proc/$(pidof nginx)/fd | wc -l
312
```

**How to read this output:** The soft limit (1024) is the per-process ceiling on open file descriptors, and every socket, pipe, and open file counts against it. A busy server with 312 descriptors is fine, but a connection leak — sockets never closed — marches that count toward 1024, at which point `accept()`/`open()` start failing with `EMFILE: Too many open files` and the service stops accepting connections while still appearing "up." This is why production deployments raise `LimitNOFILE` (see the systemd unit below) and why "Too many open files" is a classic incident signature pointing at a descriptor leak, not a memory problem.

#### Page Cache

The kernel's page cache is a transparent read/write cache for file data. It is responsible for the phenomenon where the second read of a file is dramatically faster than the first.

Read-ahead: the kernel detects sequential access patterns and pre-reads upcoming pages. This is why sequential reads (e.g., streaming a video file) are much faster than random reads.

Dirty pages: pages modified in the cache but not yet written to disk. The kernel flushes them asynchronously via `pdflush`/`writeback` threads. Use `sync`, `fsync`, or `fdatasync` when you need durability guarantees.

#### Journaling

**Journaling** protects against corruption from crashes (power loss, kernel panic). Before modifying the filesystem's main data structures, the changes are first written to a journal (write-ahead log). If a crash occurs, the filesystem replays the journal on mount to reach a consistent state.

**ext4** supports three journaling modes:

- **journal**: logs both data and metadata (safest but slowest)
- **ordered** (default): writes data to its final location first, then journals metadata
- **writeback**: journals only metadata, data may be written after metadata (fastest but data may be stale after crash)

#### Common Filesystems

| Filesystem | Best For | Key Features |
|---|---|---|
| ext4 | General Linux use | Journaling, extents, up to 1EB, mature |
| XFS | Large files, parallel I/O | Excellent scaling, used by many databases |
| ZFS | Data integrity, servers | Checksums, snapshots, compression, RAID |
| tmpfs | Temporary data | RAM-backed, contents lost on reboot |
| overlayfs | Container layers | Union mount, Docker image layers |

#### Disk I/O Patterns

Sequential I/O is **much** faster than random I/O, especially on HDDs (100x difference). SSDs narrow the gap but sequential is still faster (3-5x).

```
HDD Sequential vs Random:

  Sequential: 150-200 MB/s    Read head moves smoothly
  ============================================================>

  Random: 0.5-2 MB/s          Read head jumps everywhere
  ===>  <=  ===>     <===  =>   <=====  ===>

SSD (NVMe):
  Sequential: 3,000-7,000 MB/s
  Random (4K):  500-1,000 MB/s (still 3-7x slower!)

  IOPS (I/O Operations Per Second):
    HDD: ~100-200 random IOPS
    SSD: 100,000-1,000,000 random IOPS
```

This is why B-Trees (with their high branching factor and sequential leaf scanning) are the dominant database index structure — they minimize random disk reads.

> **Key Takeaway:** Understanding file systems helps you make informed decisions about storage configuration, database tuning, and debugging I/O performance issues. Key principles: use journaling for crash safety, leverage the page cache for read performance, use fsync when you need durability, and prefer sequential access patterns when possible.

---

### Linux Fundamentals

#### Signals

Signals are asynchronous notifications sent to processes. The most important ones for backend developers:

| Signal | Number | Default | Notes |
|---|---|---|---|
| SIGTERM | 15 | Terminate | Graceful shutdown. Can be caught. Docker sends this first. |
| SIGKILL | 9 | Kill | Immediate, cannot be caught or ignored. Docker sends after timeout. |
| SIGHUP | 1 | Terminate | Traditionally: reload config. Nginx, Gunicorn use this. |
| SIGINT | 2 | Terminate | Ctrl+C from terminal |
| SIGUSR1/2 | 10/12 | Terminate | Application-defined. Often used for log rotation, debug dumps. |
| SIGCHLD | 17 | Ignore | Child process terminated. Important for process managers. |

```python
import signal
import sys

def graceful_shutdown(signum, frame):
    """Handle SIGTERM for clean shutdown."""
    print(f"Received signal {signum}, shutting down gracefully...")
    # Close database connections
    # Finish processing current request
    # Flush logs
    sys.exit(0)

def reload_config(signum, frame):
    """Handle SIGHUP to reload configuration."""
    print("Reloading configuration...")
    # Re-read config file
    # Update runtime settings

signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGHUP, reload_config)

# In Django, you can use this pattern for custom management commands
# that need graceful shutdown (e.g., a background worker)
```

#### Cgroups and Namespaces (Containers)

**Cgroups** (Control Groups) limit and account for resource usage per process group:

- **CPU**: limit CPU time (e.g., 0.5 CPUs), set CPU shares for relative weighting
- **Memory**: hard limit (OOM kill on exceed), soft limit (reclaim under pressure)
- **I/O**: throttle read/write bandwidth, IOPS limits
- **PIDs**: limit number of processes (fork bomb protection)

**Namespaces** provide isolation of system resources — each namespace gives a process group its own view:

| Namespace | Isolates |
|---|---|
| PID | Process IDs (PID 1 inside container != PID 1 on host) |
| NET | Network stack (interfaces, routing tables, ports) |
| MNT | Mount points (filesystem tree) |
| UTS | Hostname and domain name |
| IPC | System V IPC, POSIX message queues |
| USER | User and group IDs |

```
Container = Cgroups + Namespaces:

  Host Kernel
  +----------------------------------------------------------+
  |  Container A                    Container B               |
  |  +------------------------+    +------------------------+ |
  |  | PID Namespace          |    | PID Namespace          | |
  |  |   PID 1: nginx         |    |   PID 1: gunicorn      | |
  |  |   PID 2: worker        |    |   PID 2: celery        | |
  |  | NET Namespace          |    | NET Namespace          | |
  |  |   eth0: 172.17.0.2     |    |   eth0: 172.17.0.3     | |
  |  | MNT Namespace          |    | MNT Namespace          | |
  |  |   /app/... (overlay)   |    |   /app/... (overlay)   | |
  |  +------------------------+    +------------------------+ |
  |  | Cgroup: 512MB RAM, 1 CPU   | Cgroup: 1GB RAM, 2 CPU | |
  +----------------------------------------------------------+
```

#### systemd

systemd is the default init system on most modern Linux distributions. It manages services through **unit files**:

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Django Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/venv/bin/gunicorn myapp.wsgi:application --bind 0.0.0.0:8000
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
MemoryMax=512M
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

```bash
# Common systemctl commands
systemctl start myapp      # Start the service
systemctl stop myapp       # Stop the service
systemctl restart myapp    # Restart
systemctl reload myapp     # Reload (sends SIGHUP)
systemctl status myapp     # Check status
systemctl enable myapp     # Start on boot

# View logs
journalctl -u myapp -f           # Follow logs for the service
journalctl -u myapp --since "1 hour ago"  # Recent logs
```

#### Debugging Tools

| Tool | Purpose | Example |
|---|---|---|
| `strace` | Trace system calls | `strace -p 1234 -e trace=network` |
| `ltrace` | Trace library calls | `ltrace -p 1234 -e malloc` |
| `perf` | CPU profiling | `perf top`, `perf record -g ./myapp` |
| `bpftrace` | Dynamic tracing (eBPF) | `bpftrace -e 'tracepoint:syscalls:sys_enter_open { printf("%s\n", str(args->filename)); }'` |

#### Network Stack

Linux's **netfilter** framework provides packet filtering and manipulation. **iptables** (legacy) and **nftables** (modern replacement) define rules organized into chains:

```
Packet Flow through Netfilter:

  Incoming Packet
       |
  [PREROUTING] --> Routing Decision --> [INPUT] --> Local Process
       |                    |
       |               [FORWARD] --> [POSTROUTING] --> Outgoing
       |                                    ^
  Local Process --> [OUTPUT] ---------------+

  NAT (Network Address Translation): modifies source/destination addresses
  Masquerading: SNAT for dynamic outbound IP (used by Docker, VMs)
  Connection Tracking: remembers established connections for stateful filtering
```

> **Key Takeaway:** Linux fundamentals are essential for production backend work. Signals for graceful shutdown, cgroups/namespaces for containerization, systemd for service management, and debugging tools for production troubleshooting. These are not just "ops" skills — every backend developer needs them for debugging production issues, writing Dockerfiles, configuring deployment, and understanding why their application behaves differently in production than in development.

*Last reviewed: 2026-06-08*
