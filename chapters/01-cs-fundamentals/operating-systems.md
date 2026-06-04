[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.3 Operating Systems

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

> **Key Takeaway:** Understanding processes, threads, and coroutines is fundamental to building performant backend systems. In Python/Django: use multiprocessing for CPU-bound parallelism, threading for blocking I/O concurrency (database calls, HTTP requests), and asyncio for high-concurrency I/O (WebSockets, many simultaneous API calls). The GIL makes this choice more important in Python than in most other languages.

---

### Memory Management

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
