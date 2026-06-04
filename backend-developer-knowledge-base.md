# Backend Developer Knowledge Base

**Mid → Senior → Architect Level · Python/Django Flavored · Framework-Agnostic Principles**

---

## 1. Computer Science Fundamentals

### 1.1 Data Structures

**Arrays & Linked Lists**
- Contiguous vs node-based memory layout. Arrays give O(1) random access, O(n) insertion/deletion. Linked lists give O(1) insert/delete at known position, O(n) access.
- Python `list` is a dynamic array (over-allocates with amortized doubling). `collections.deque` is a doubly-linked list optimized for append/pop on both ends.
- Know when to use each: arrays for indexed access and cache locality, linked lists for frequent insertions/removals at arbitrary positions.
- Circular buffers (ring buffers) for fixed-size queues, producer-consumer patterns, log buffers.

**Hash Tables**
- Hash function properties: deterministic, uniform distribution, fast computation. Collision resolution: separate chaining (linked list per bucket), open addressing (linear probing, quadratic probing, double hashing).
- Load factor = n/k. Rehashing when load factor exceeds threshold (~0.75). Amortized O(1) for insert/lookup/delete.
- Python `dict` internals: compact dict (since 3.6, insertion order preserved). Open addressing with perturbation. Key sharing for instance dicts (__dict__).
- `collections.OrderedDict` (doubly-linked list + dict), `defaultdict`, `Counter`.
- Consistent hashing for distributed systems (virtual nodes, minimal key redistribution on node add/remove). Used in load balancers, distributed caches, database sharding.

**Trees**
- Binary Search Tree: O(log n) average for search/insert/delete, O(n) worst case (degenerate/skewed).
- Self-balancing BSTs: AVL (strict balance, faster lookups), Red-Black (relaxed balance, faster inserts/deletes). Used in language standard libraries (C++ std::map, Java TreeMap).
- B-Trees & B+ Trees: designed for disk-based storage. High branching factor minimizes disk reads. B+ trees store data only in leaves with linked leaf nodes for range scans. Foundation of database indexes (PostgreSQL, MySQL InnoDB).
- Heap: complete binary tree, O(1) min/max access, O(log n) insert/extract. Used for priority queues, task schedulers, Dijkstra's algorithm. Python `heapq` (min-heap).
- Trie (prefix tree): O(m) lookup where m = key length. Used for autocomplete, IP routing tables, spell checkers. Compressed trie (radix tree) for memory efficiency.
- Segment trees for range queries (sum, min, max over intervals). Fenwick tree (Binary Indexed Tree) for prefix sums with updates. Both useful in analytics and time-series.

**Graphs**
- Representations: adjacency list (sparse graphs, O(V+E) space), adjacency matrix (dense graphs, O(V²) space, O(1) edge lookup).
- BFS: level-order traversal, shortest path in unweighted graphs, O(V+E). Use queue. Applications: social network distance, web crawling, shortest path.
- DFS: preorder/postorder traversal, cycle detection, topological sort, connected components. Use stack/recursion. Applications: dependency resolution, maze solving.
- Dijkstra: shortest path with non-negative weights, O((V+E) log V) with binary heap. Bellman-Ford: handles negative weights, O(VE), detects negative cycles.
- A* search: Dijkstra + heuristic. Used in pathfinding, game AI, route planning.
- Topological sort: linear ordering of DAG vertices. Kahn's algorithm (BFS-based) or DFS-based. Applications: build systems, task scheduling, migration ordering.
- Minimum spanning tree: Kruskal's (edge-sorted, union-find) and Prim's (vertex-based, priority queue). Applications: network design, clustering.
- Strongly connected components: Tarjan's or Kosaraju's algorithm. Applications: compiler optimization, social network analysis.
- DAGs in practice: workflow engines (Airflow), data pipelines, dependency graphs.

**Advanced Data Structures**
- Skip list: probabilistic alternative to balanced BSTs. O(log n) average for search/insert/delete. Used in Redis sorted sets, LevelDB. Simpler to implement than red-black trees.
- Bloom filter: probabilistic set membership. O(k) lookup with k hash functions. False positives possible, false negatives impossible. Used in databases (avoid unnecessary disk reads), web caching, spam filtering. Counting Bloom filter for deletion support.
- HyperLogLog: cardinality estimation with O(1) space. Count distinct elements in a stream with <2% error using ~12KB. Used in Redis, analytics systems (unique visitors).
- LRU cache: hash map + doubly-linked list. O(1) get/put. `functools.lru_cache` in Python. LFU cache: frequency-based eviction (more complex, heap + hash maps).
- Disjoint Set / Union-Find: near O(1) amortized with path compression + union by rank. Applications: Kruskal's MST, network connectivity, image segmentation.
- Rope: balanced binary tree of strings for efficient text editing (insert, delete, concatenate on large strings).
- Count-Min Sketch: probabilistic frequency estimation for streaming data. Used in network monitoring, NLP.

### 1.2 Algorithms & Complexity

**Big-O Analysis**
- Time and space complexity. Learn to identify: O(1) constant, O(log n) binary search/balanced tree ops, O(n) linear scan, O(n log n) efficient sorts, O(n²) nested loops, O(2ⁿ) brute-force subsets, O(n!) permutations.
- Amortized analysis: average cost per operation over a sequence (e.g., dynamic array resizing is amortized O(1) for append despite occasional O(n) copy).
- Best/average/worst case distinction. Quicksort: O(n log n) average, O(n²) worst. Hash table: O(1) average, O(n) worst.
- Space-time tradeoffs: caching (trade space for time), streaming algorithms (trade accuracy for space), precomputation (trade startup time for query time).
- Master theorem for divide-and-conquer recurrences: T(n) = aT(n/b) + O(nᵈ).

**Sorting**
- Comparison-based sorts (lower bound Ω(n log n)): Quicksort (in-place, cache-friendly, O(n log n) average), Mergesort (stable, O(n log n) guaranteed, needs O(n) extra space), Heapsort (in-place, O(n log n) guaranteed, poor cache locality).
- Non-comparison sorts: Counting sort (O(n+k), integer keys), Radix sort (O(d(n+k)), fixed-length keys), Bucket sort (O(n) average for uniform distribution).
- When stability matters: preserving relative order of equal elements. Important for multi-key sorts, database ordering.
- External sorting: merge sort variant for data larger than RAM. Used in database query processing, large file sorting.
- Python: Timsort (hybrid merge+insertion sort, stable, adaptive). `sorted()` returns new list, `.sort()` in-place. Key functions for custom ordering.

**Dynamic Programming**
- Two properties: overlapping subproblems (same subproblems solved repeatedly) and optimal substructure (optimal solution contains optimal sub-solutions).
- Top-down (memoization): recursive with cache. Bottom-up (tabulation): iterative, fill table.
- Classic patterns: 0/1 knapsack (resource allocation), longest common subsequence (diff algorithms), edit distance (spell check, DNA alignment), coin change, matrix chain multiplication.
- State machine DP: model problem as state transitions (e.g., stock trading with cooldown).
- Bitmask DP: represent subset states as bitmasks for small n (traveling salesman, set cover).
- Practical uses: rate limiting sliding windows, resource allocation, route optimization, text wrapping algorithms.

**Graph Algorithms (Extended)**
- Floyd-Warshall: all-pairs shortest path, O(V³). Good for small dense graphs, detects negative cycles.
- Network flow: Ford-Fulkerson, Edmonds-Karp. Applications: maximum bipartite matching, project selection, image segmentation.
- Eulerian path/circuit: visiting every edge exactly once. Applications: DNA assembly, circuit design.

**String Algorithms**
- KMP (Knuth-Morris-Pratt): pattern matching in O(n+m). Failure function for prefix matching.
- Rabin-Karp: rolling hash for multi-pattern matching. Used in plagiarism detection.
- Aho-Corasick: multiple pattern matching simultaneously. Used in intrusion detection, content filtering.
- Suffix array / suffix tree: O(n) construction, powerful for substring queries. Used in bioinformatics, full-text search.

### 1.3 Operating Systems

**Processes & Threads**
- Process: independent memory space, isolation, heavier context switch (~1-10μs). Thread: shared memory within process, lighter context switch. Coroutine: cooperative multitasking, user-space scheduling, cheapest (~100ns switch).
- Process states: new → ready → running → waiting → terminated. Context switch saves/restores registers, program counter, stack pointer.
- IPC mechanisms: pipes (unidirectional byte stream), named pipes (FIFO), message queues (structured messages), shared memory (fastest, needs synchronization), Unix domain sockets (bidirectional, same host), signals (async notifications).
- Copy-on-write (COW) fork: parent and child share pages until write. Efficient for fork-exec pattern. Used by Redis for background saves.
- Green threads / user-space threads: managed by runtime, not OS. Python's asyncio coroutines, Go's goroutines. M:N threading model.

**Memory Management**
- Virtual memory: each process sees contiguous address space. Page table maps virtual → physical addresses. Page size typically 4KB, huge pages (2MB/1GB) reduce TLB misses.
- TLB (Translation Lookaside Buffer): cache for page table entries. TLB miss triggers page table walk. Huge pages improve TLB hit rate for large working sets.
- Stack: automatic allocation, LIFO, function call frames (local variables, return address). Default stack size ~8MB on Linux. Stack overflow on deep recursion.
- Heap: dynamic allocation (malloc/free, Python object allocation). Fragmentation over time. Memory allocators: glibc malloc, jemalloc (used by Redis, Rust), tcmalloc.
- Python memory: reference counting (immediate cleanup) + generational garbage collector (handles cycles). Three generations: gen0 (new objects, collected frequently), gen1, gen2 (long-lived, collected rarely). `gc.collect()` to force. `gc.disable()` for latency-sensitive code.
- Memory-mapped files (mmap): map file into virtual address space. Lazy loading, shared between processes. Used for large file processing, shared memory IPC, database page caches.
- OOM killer: Linux kernel kills process with highest OOM score when memory exhausted. `oom_score_adj` to influence selection. Cgroups for memory limits per container.
- Monitoring: `RSS` (Resident Set Size, actual physical memory), `VSZ` (Virtual Size, total mapped). `top`, `htop`, `smem`, `/proc/[pid]/status`.

**I/O Models**
- Blocking I/O: thread waits until operation completes. Simple but wastes threads. Thread-per-connection model.
- Non-blocking I/O: returns immediately (EAGAIN/EWOULDBLOCK). Application polls for readiness. Busy-waiting waste.
- I/O multiplexing: monitor multiple file descriptors. `select` (O(n), 1024 fd limit), `poll` (O(n), no fd limit), `epoll` (O(1) for events, Linux-specific, edge/level triggered), `kqueue` (BSD/macOS).
- epoll in detail: `epoll_create`, `epoll_ctl` (add/modify/remove), `epoll_wait`. Level-triggered (like poll) vs edge-triggered (notify only on state change, must drain completely). Edge-triggered is more efficient but harder to use correctly.
- Async I/O: `io_uring` (Linux 5.1+): submission queue + completion queue in shared memory, no syscalls needed after setup. Significantly reduces syscall overhead. Used by modern high-performance servers.
- Zero-copy: `sendfile()` sends file directly from kernel buffer to socket without copying to userspace. `splice()` for pipe-based zero-copy. Used for static file serving.
- Buffered I/O: kernel page cache. Write-back caching (write to cache, flush later). `fsync`/`fdatasync` for durability guarantees. Direct I/O (`O_DIRECT`) bypasses page cache for database engines that manage their own buffer pool.

**File Systems**
- Inodes: metadata (permissions, timestamps, data block pointers). File descriptors: per-process integer handles to kernel file objects. fd limits (`ulimit -n`, `/proc/sys/fs/file-max`).
- Page cache: kernel caches file data in memory. Read-ahead for sequential access. Dirty pages written back asynchronously. `sync`, `fsync` to flush.
- Journaling: ext4 journal records metadata changes before applying. Prevents corruption on crash. Full journaling (data+metadata) vs ordered mode (metadata only, data written first).
- Common filesystems: ext4 (Linux default, journaling, extents), XFS (large files, parallel I/O), ZFS (checksums, snapshots, compression), tmpfs (RAM-backed, /tmp), overlayfs (Docker layers).
- Disk I/O patterns: sequential reads/writes much faster than random (especially HDDs). SSDs reduce random I/O penalty but sequential still faster. IOPS vs throughput. I/O scheduler: noop/none for SSDs, deadline/mq-deadline for HDDs.

**Linux Fundamentals**
- Signals: SIGTERM (graceful shutdown), SIGKILL (immediate, uncatchable), SIGHUP (reload config), SIGUSR1/SIGUSR2 (application-defined). Signal handlers must be async-signal-safe.
- Cgroups (control groups): resource limits (CPU, memory, I/O, network) per process group. v1 vs v2 (unified hierarchy). Foundation of container resource isolation.
- Namespaces: isolation of system resources. PID (process IDs), NET (network stack), MNT (mount points), UTS (hostname), IPC (IPC resources), USER (user/group IDs). Foundation of container isolation.
- Together, cgroups + namespaces = containers (Docker, Podman).
- systemd: init system and service manager. Unit files (.service, .timer, .socket). `systemctl` commands. Journal logging (`journalctl`). Socket activation. Dependency management.
- ulimits: per-user resource limits. `nofile` (open files), `nproc` (processes), `memlock` (locked memory). Set in `/etc/security/limits.conf` or systemd unit.
- `/proc` filesystem: process information (/proc/[pid]/status, maps, fd, cmdline). System info (/proc/cpuinfo, meminfo, loadavg). `/sys`: kernel/device configuration.
- Debugging tools: `strace` (syscall tracing), `ltrace` (library call tracing), `perf` (performance counters, profiling), `bpftrace` (dynamic tracing with eBPF).
- Network stack: netfilter framework (packet filtering/manipulation). iptables (legacy) / nftables (modern). Chains: INPUT, OUTPUT, FORWARD. NAT, masquerading. Connection tracking.

### 1.4 Networking

**TCP/IP Deep Dive**
- 3-way handshake: SYN → SYN-ACK → ACK. Connection establishment adds 1 RTT latency. SYN flood attack and SYN cookies defense.
- Flow control: sliding window. Receiver advertises window size (rwnd). Sender cannot send more than min(cwnd, rwnd).
- Congestion control: slow start (exponential growth), congestion avoidance (linear growth, AIMD). ssthresh. Modern: CUBIC (Linux default), BBR (Google, bandwidth-based).
- TCP_NODELAY: disables Nagle's algorithm (buffers small packets). Important for low-latency applications (real-time, interactive). Usually combine with TCP_QUICKACK.
- TIME_WAIT: 2MSL (typically 60s) after connection close. Prevents delayed packets from previous connection affecting new one. Can exhaust ports on high-traffic servers. `SO_REUSEADDR`, `SO_REUSEPORT`, `net.ipv4.tcp_tw_reuse`.
- Keep-alive: periodic probes to detect dead connections. `SO_KEEPALIVE`, configure with `tcp_keepalive_time`, `tcp_keepalive_intvl`, `tcp_keepalive_probes`. Application-level heartbeats are more reliable.
- Socket buffer tuning: `SO_SNDBUF`, `SO_RCVBUF`. Auto-tuning (`net.ipv4.tcp_rmem`, `tcp_wmem`). BDP (bandwidth-delay product) determines optimal buffer size.
- TCP vs UDP: TCP for reliability (HTTP, database connections). UDP for low latency, multicast, or when application handles reliability (video streaming, DNS, game networking, QUIC).

**HTTP Protocol**
- HTTP/1.1: persistent connections (Connection: keep-alive), pipelining (rarely used due to head-of-line blocking), chunked transfer encoding.
- HTTP/2: binary framing layer. Multiplexing (multiple streams over single connection, no HOL blocking at HTTP level). HPACK header compression. Server push. Stream priorities. Still has TCP HOL blocking.
- HTTP/3: QUIC protocol (UDP-based). Independent streams (no TCP HOL blocking). 0-RTT connection resumption. Connection migration (IP changes). Built-in TLS 1.3. Better for lossy networks.
- Caching headers: `Cache-Control` (max-age, no-cache, no-store, public, private, s-maxage), `ETag` (content hash for conditional requests), `Last-Modified`/`If-Modified-Since`, `Vary` (cache key includes specified headers).
- Content negotiation: `Accept` (media type), `Accept-Encoding` (compression: gzip, br, zstd), `Accept-Language`.
- Important headers: `X-Request-Id` (tracing), `X-Forwarded-For` (real client IP behind proxy), `Strict-Transport-Security` (HSTS), `Content-Security-Policy`.

**DNS**
- Recursive resolution: client → recursive resolver → root → TLD → authoritative nameserver. Caching at every level.
- Record types: A (IPv4), AAAA (IPv6), CNAME (alias, can't coexist with other records at zone apex), MX (mail), TXT (verification, SPF, DKIM), SRV (service discovery with port+priority), NS (nameserver delegation), PTR (reverse DNS), CAA (certificate authority authorization).
- TTL strategies: low TTL (30-300s) for services that need fast failover, high TTL (3600-86400s) for stable records to reduce DNS load. Pre-warm DNS before TTL changes for migrations.
- DNS-based load balancing: round-robin A records (simple but uneven), weighted records (Route53), GeoDNS (latency-based routing), health-checked failover.
- Split-horizon DNS: different responses for internal vs external queries. Used for accessing services via internal IPs within a network.
- DNSSEC: cryptographic signing of DNS records. Chain of trust from root. Prevents DNS spoofing/poisoning. DS, DNSKEY, RRSIG records.

**TLS/SSL**
- TLS 1.3 handshake: 1-RTT (down from 2-RTT in TLS 1.2). Removed insecure ciphers. 0-RTT resumption (with replay risk). Only supports AEAD ciphers (AES-GCM, ChaCha20-Poly1305).
- Certificate chain: leaf cert → intermediate cert(s) → root CA. Servers must send full chain (minus root). Certificate pinning for mobile apps.
- mTLS (mutual TLS): both client and server present certificates. Used for service-to-service authentication in microservices. SPIFFE/SPIRE for workload identity.
- OCSP stapling: server fetches and caches certificate revocation status, sends to client. Eliminates client-side OCSP lookup latency and privacy concerns.
- Let's Encrypt automation: ACME protocol. HTTP-01 challenge (prove domain control via HTTP), DNS-01 challenge (prove via DNS TXT record, supports wildcards). Auto-renewal with certbot or similar.
- SNI (Server Name Indication): client sends requested hostname in TLS handshake. Allows multiple TLS sites on single IP.

**Network Debugging**
- `tcpdump`: packet capture. `tcpdump -i any port 443 -w capture.pcap`. Filters: host, port, protocol. Essential for debugging connection issues.
- `Wireshark`: GUI packet analysis. Follow TCP streams, decode protocols, statistics.
- `curl`: HTTP client. `-v` verbose, `-I` headers only, `--resolve` DNS override, `-w` timing stats (%{time_connect}, %{time_starttransfer}), `--http2`.
- `traceroute`/`mtr`: path analysis. MTR combines ping + traceroute for continuous monitoring. Identify network hops with high latency or packet loss.
- `ss` (modern) / `netstat` (legacy): socket statistics. `ss -tlnp` (listening TCP), `ss -s` (summary). Diagnose connection states, TIME_WAIT buildup.
- `dig` / `nslookup`: DNS queries. `dig +trace` for full resolution path. `dig @8.8.8.8` for specific resolver.
- MTU/fragmentation: Maximum Transmission Unit (typically 1500 bytes). Path MTU Discovery. Fragmentation performance impact. `ping -s 1472 -M do` to test.

---

## 2. Python Deep Knowledge

### 2.1 Language Internals

**Data Model**
- Everything is an object with identity (`id()`), type (`type()`), and value. Even functions, classes, and modules are objects.
- `__slots__`: declare fixed set of attributes, skip per-instance `__dict__`. Saves ~40-50% memory per instance. Can't add arbitrary attributes. Subclasses must also declare `__slots__` or they get `__dict__` back.
- Descriptors: objects defining `__get__`, `__set__`, `__delete__`. Foundation of `property`, `classmethod`, `staticmethod`, ORMs. Data descriptors (both get+set) take priority over instance dict. Non-data descriptors (only get) don't.
- Metaclasses: class of a class. `type` is the default metaclass. `__new__` creates class, `__init__` initializes it. Use `__init_subclass__` (simpler) when possible. Practical uses: ORMs (Django model metaclass), validation frameworks, registries.
- `__new__` vs `__init__`: `__new__` creates the instance (classmethod), `__init__` initializes it. Override `__new__` for immutable types (str, int, tuple), singletons, caching.
- MRO (Method Resolution Order): C3 linearization. `ClassName.mro()` or `__mro__`. Ensures consistent method lookup in diamond inheritance. `super()` follows MRO, not parent class.
- Dunder methods: `__repr__` (unambiguous, for developers), `__str__` (readable, for users), `__hash__` (must be consistent with `__eq__`), `__bool__`, `__len__`, `__contains__`, `__getitem__`/`__setitem__`/`__delitem__`, `__call__`, `__enter__`/`__exit__`.
- `__init_subclass__`: called when a class is subclassed. Simpler alternative to metaclasses for class registration, validation, plugin systems.

**Memory & Garbage Collection**
- Reference counting: every object has a refcount. Decremented when reference removed. Object deallocated when refcount reaches 0. Immediate cleanup, no pauses. `sys.getrefcount()`.
- Generational GC: handles circular references that refcounting can't. Three generations (gen0, gen1, gen2). Objects promoted to next generation if they survive a collection cycle. Gen0 collected most frequently.
- Weak references (`weakref`): reference that doesn't prevent GC. `weakref.ref()`, `WeakValueDictionary`, `WeakSet`. Used for caches, observer patterns, avoiding circular reference issues.
- Memory profiling: `tracemalloc` (stdlib, track allocations), `objgraph` (visualize object reference graphs), `memory_profiler` (line-by-line memory usage), `pympler` (object sizing).
- `sys.getsizeof()`: size of object itself (not referenced objects). For deep size, use `pympler.asizeof` or recursive calculation.
- Interning: Python interns small integers (-5 to 256) and some strings (identifiers). `sys.intern()` for explicit string interning. Reduces memory for repeated strings.
- `__del__` pitfalls: not guaranteed to run (especially during interpreter shutdown). Circular references with `__del__` prevent GC in older Python. Prefer `__enter__`/`__exit__` or `atexit`.
- Memory optimization: `__slots__`, `array.array` (typed arrays), `numpy` for numerical data, generators for streaming, `struct` for packed binary data.

**GIL (Global Interpreter Lock)**
- GIL prevents multiple threads from executing Python bytecode simultaneously. Only one thread holds the GIL at a time. GIL is released during I/O operations (file, network, sleep) and some C extensions (numpy).
- CPU-bound work: GIL is the bottleneck. Solutions: `multiprocessing` (separate processes, separate GILs), C extensions that release GIL, Cython with `nogil`, or use PyPy.
- I/O-bound work: GIL is NOT a bottleneck (released during I/O). `threading` works fine. `asyncio` even better (single thread, no GIL contention overhead).
- `multiprocessing`: process pools (`Pool`, `ProcessPoolExecutor`). IPC via `Queue`, `Pipe`, `Value`/`Array` (shared memory). `multiprocessing.shared_memory` (Python 3.8+) for zero-copy sharing.
- `concurrent.futures`: unified interface. `ThreadPoolExecutor` for I/O, `ProcessPoolExecutor` for CPU. `submit()` returns `Future`, `map()` for bulk. `as_completed()` for results in completion order.
- Free-threaded Python (PEP 703, experimental in 3.13+): opt-in GIL removal. `python3.13t`. Still experimental, library compatibility varies.

**Iterators & Generators**
- Iterator protocol: `__iter__()` returns self, `__next__()` returns next value or raises `StopIteration`. Any object implementing both is an iterator.
- Generators: functions with `yield`. Lazy evaluation — compute values on demand. Memory-efficient for large datasets. Generator state is preserved between yields.
- Generator expressions: `(x*2 for x in range(10))`. More memory-efficient than list comprehensions for large sequences.
- `yield from`: delegate to sub-generator. Flattens nested generators. Passes `send()`, `throw()`, `close()` through. Essential for coroutine composition.
- `send()`: send a value into a generator (received as return value of `yield`). `throw()`: raise exception inside generator. `close()`: trigger `GeneratorExit`.
- `itertools` mastery: `chain` (concatenate iterables), `islice` (slice iterators), `groupby` (group consecutive elements), `product`/`combinations`/`permutations` (combinatorics), `accumulate` (running totals), `starmap`, `tee` (fork iterator), `zip_longest`.
- `more-itertools`: community extension with `chunked`, `peekable`, `unique_everseen`, `flatten`, `windowed`.

**Import System**
- Module search order: `sys.modules` cache → built-in modules → `sys.path` (current dir, PYTHONPATH, installed packages).
- `__init__.py`: marks directory as package. Can be empty or contain initialization code. Implicit namespace packages (PEP 420, no `__init__.py`) for split-across-directories packages.
- Circular imports: A imports B, B imports A. Solutions: import inside function, restructure code, use `importlib.import_module()` lazily, or extract shared code to third module.
- `importlib`: dynamic imports (`import_module`), reload modules (`reload`), custom importers/finders. Plugin systems.
- `sys.modules`: dict of all loaded modules. Can be manipulated (mock modules, module aliases). Module is executed only once; subsequent imports use cache.
- Relative imports: `from . import sibling`, `from .. import parent_module`. Only work inside packages. Use absolute imports for clarity in most cases.

### 2.2 Async Programming

**asyncio Core**
- Event loop: single-threaded, runs coroutines cooperatively. `asyncio.run()` creates loop, runs coroutine, closes loop. `loop.run_until_complete()` for more control.
- Coroutines: `async def` functions. Must be awaited. Execution suspends at `await`, resumes when awaited thing completes. Calling without `await` returns coroutine object (common bug).
- Tasks: wrap coroutines for concurrent execution. `asyncio.create_task()` schedules coroutine. Task starts executing at next `await` point in current coroutine.
- `asyncio.gather(*coros)`: run coroutines concurrently, wait for all. `return_exceptions=True` to collect exceptions instead of raising.
- `asyncio.wait(tasks, return_when=FIRST_COMPLETED|ALL_COMPLETED|FIRST_EXCEPTION)`: more control over completion.
- `asyncio.shield(coro)`: protect from cancellation (outer cancel doesn't propagate).
- `asyncio.Queue`: async producer-consumer queue. `put()`, `get()`, `join()`. Bounded queue with `maxsize` for backpressure.
- Exception handling: unhandled exceptions in tasks are logged but don't crash. Use `task.add_done_callback()` or gather with `return_exceptions`. Always await or check task results.
- Cancellation: `task.cancel()` raises `CancelledError` at next await point. Handle with `try/except asyncio.CancelledError`. Cleanup in `finally` block.

**Async Patterns**
- Semaphores: `asyncio.Semaphore(n)` limits concurrency. Use as context manager: `async with sem:`. Critical for rate-limiting API calls, database connections.
- Async context managers: `async with`. Implement `__aenter__` and `__aexit__`. Or use `@asynccontextmanager` from `contextlib`.
- Async iterators: `__aiter__` and `__anext__`. Async generators: `async def` with `yield`. `async for item in aiter:`.
- Debouncing: delay execution until input settles. Use `asyncio.sleep()` with cancellation. Throttling: limit execution rate. Token bucket pattern.
- Fan-out/fan-in: dispatch work to multiple coroutines (fan-out), collect results (fan-in). Use `gather`, `as_completed`, or `TaskGroup` (Python 3.11+).
- Graceful shutdown: handle SIGTERM/SIGINT. Cancel running tasks. Wait for cleanup. `asyncio.get_running_loop().add_signal_handler()`.
- `asyncio.timeout()` (Python 3.11+) or `async_timeout` library. Wrap operations that might hang. Essential for network calls.

**Async Ecosystem**
- ASGI vs WSGI: WSGI is synchronous (one request per thread). ASGI is async (handles multiple concurrent requests per worker). ASGI servers: Uvicorn (uvloop-based), Hypercorn, Daphne.
- uvloop: drop-in asyncio event loop replacement. 2-4x faster. Based on libuv (Node.js). `uvloop.install()` before `asyncio.run()`.
- HTTP clients: `httpx` (async + sync, HTTP/2 support), `aiohttp` (async only, WebSocket support). Always use connection pooling. Set timeouts.
- Database: `asyncpg` (PostgreSQL, fastest), `aiomysql`, `aiosqlite`. `databases` library for async ORM-like interface. SQLAlchemy 2.0 async support.
- Redis: `redis.asyncio` (official async client, formerly aioredis). Connection pooling. Pipeline support.
- Structured concurrency: `asyncio.TaskGroup` (Python 3.11+). All tasks in group must complete. If one fails, others are cancelled. `anyio` for library-agnostic async. `trio` for strict structured concurrency.
- Mixing sync/async: `loop.run_in_executor()` runs sync code in thread pool from async context. `asyncio.to_thread()` (Python 3.9+). Never call blocking code directly in async context.

### 2.3 Advanced Patterns

**Type System**
- Type hints: PEP 484+. `int`, `str`, `list[int]`, `dict[str, Any]`, `Optional[X]` (= `X | None`), `Union[X, Y]` (= `X | Y` in 3.10+).
- Generics: `TypeVar('T')` for generic functions/classes. `TypeVar('T', bound=Base)` for upper-bound. `ParamSpec` for decorator typing (preserve function signature).
- Protocol (PEP 544): structural subtyping (duck typing with type checking). Define interface without inheritance. `@runtime_checkable` for `isinstance` checks.
- `TypedDict`: typed dictionaries with specific keys. `total=True` (all keys required) or `total=False` (all optional). Useful for JSON/API response typing.
- `Literal['a', 'b']`: restrict to specific values. `Final`: prevent reassignment. `ClassVar`: class-level variable hint.
- Runtime validation: Pydantic (data validation, serialization, settings management), `beartype` (runtime type checking decorator), `attrs` (class definition with validation).
- Type checkers: `mypy` (mature, configurable), `pyright` (fast, VSCode integration). Strict mode for maximum safety. Gradual typing: add types incrementally.

**Decorators & Context Managers**
- Decorator: function that takes a function and returns a modified function. `@decorator` is sugar for `func = decorator(func)`.
- Decorator factories: decorator that takes arguments. Three levels of nesting: outer (takes args) → middle (takes func) → inner (wraps func). `functools.wraps` preserves `__name__`, `__doc__`, `__module__`.
- Class-based decorators: implement `__call__`. Maintain state across calls. Useful for caching, retry logic, rate limiting.
- Stacking: `@a @b @c def f` = `f = a(b(c(f)))`. Outer decorator wraps result of inner. Order matters.
- Context managers: `__enter__` (setup, return resource) and `__exit__` (cleanup, handle exceptions). `__exit__` receives exception info; return `True` to suppress.
- `contextlib.contextmanager`: decorator that turns generator function into context manager. `yield` separates setup from cleanup. Simpler than class-based.
- `contextlib.ExitStack`: manage dynamic number of context managers. Stack cleanup callbacks. Useful when number of resources is determined at runtime.
- `contextlib.suppress(*exceptions)`: ignore specified exceptions. `contextlib.nullcontext()`: no-op context manager for optional contexts.
- Async variants: `@asynccontextmanager`, `AsyncExitStack`, `async with`.

**Metaprogramming**
- Metaclass: class whose instances are classes. `class Meta(type):` then `class MyClass(metaclass=Meta):`. `__new__` creates class, `__init__` initializes, `__call__` called when class is instantiated.
- Practical metaclass uses: Django model metaclass (collects field definitions, creates database mapping), validation frameworks (enforce method signatures), abstract class enforcement, automatic registration.
- `__init_subclass__`: simpler alternative introduced in Python 3.6. Class method called when subclassed. Good for plugin registration, validation, adding methods.
- Class decorators: modify class after creation. Can add methods, wrap methods, register class. Simpler than metaclasses for many use cases.
- ABC (Abstract Base Classes): `abc.ABC`, `@abstractmethod`. Can't instantiate ABC directly. Enforce interface contracts. Virtual subclasses with `register()`.
- Dynamic creation: `type('ClassName', (bases,), {'attr': value})`. `types.FunctionType` for dynamic functions. `exec`/`eval` (avoid in production).
- `inspect` module: introspect live objects. `inspect.signature()`, `inspect.getsource()`, `inspect.getmembers()`. Useful for documentation generators, debugging tools, framework internals.

**Performance Optimization**
- Profiling: `cProfile` (function-level timing), `line_profiler` (`@profile` decorator, line-by-line), `py-spy` (sampling profiler, attach to running process without modification), `scalene` (CPU + memory + GPU).
- `timeit` module: microbenchmarks. `python -m timeit "expression"`. Use `timeit.timeit()` in code. Avoid premature optimization — profile first.
- String performance: `''.join(list)` instead of `+=` concatenation. f-strings fastest for formatting. `str.translate()` for character replacement.
- Data structure choices: `set` for membership testing (O(1) vs O(n) for list), `deque` for queue operations, `bisect` for sorted list operations, `array.array` for typed numeric arrays.
- Comprehensions: list/dict/set comprehensions are faster than equivalent `for` loops (optimized bytecode). But generators for memory efficiency on large data.
- `__slots__`: 30-50% memory reduction for many instances. Faster attribute access.
- Cython: write Python-like code, compile to C. 10-100x speedup for CPU-bound code. `cdef` for C variables, `cpdef` for dual Python/C callable.
- C extensions: `ctypes` (call C shared libraries), `cffi` (C Foreign Function Interface, cleaner than ctypes), `pybind11` (C++ bindings).
- PyPy: alternative Python implementation with JIT compiler. 5-10x faster for long-running pure Python. Not all C extensions compatible.
- Structural patterns: avoid global variable lookups (local faster), cache attribute lookups in loops, use `operator.itemgetter`/`attrgetter` for key functions.

### 2.4 Packaging & Tooling

**Project Setup**
- `pyproject.toml` (PEP 621): single config file for project metadata, build system, tool configuration. Replaces `setup.py`, `setup.cfg`, `MANIFEST.in`.
- Package managers: Poetry (dependency resolution, lock file, virtual env), PDM (PEP 582 support), uv (extremely fast, Rust-based, drop-in pip/venv replacement), Hatch (build backend, environment management).
- Virtual environments: `python -m venv .venv`. Isolate project dependencies. `pip freeze > requirements.txt`. Lock files (Poetry.lock, uv.lock) for reproducible builds.
- Dependency resolution: version specifiers (`>=1.0,<2.0`, `~=1.4`), extras (`package[extra]`), platform markers. Dependency conflicts (diamond dependencies). Lock files resolve to exact versions.
- Monorepo: shared utilities, consistent tooling. Tools: `pants`, `bazel`, `nx`. Or simpler: workspace packages (Poetry, uv).

**Code Quality**
- Ruff: extremely fast linter + formatter (Rust-based). Replaces flake8, isort, pyupgrade, pydocstyle, and many plugins. `ruff check` and `ruff format`.
- Type checking: mypy (strict mode, incremental, daemon mode), pyright (faster, better inference, VSCode/Pylance integration). Configure in `pyproject.toml`.
- Pre-commit hooks: `.pre-commit-config.yaml`. Run checks before commit. Hooks: ruff, mypy, detect-secrets, conventional commits, file size limits.
- EditorConfig: `.editorconfig` for consistent editor settings (indent style, line endings, charset). Language-agnostic.

**Testing Ecosystem**
- pytest: de facto standard. Auto-discovery. Fixtures (`@pytest.fixture`, scopes: function/class/module/session). `conftest.py` for shared fixtures. Parametrize (`@pytest.mark.parametrize`). Markers (`@pytest.mark.slow`).
- Fixtures: dependency injection for tests. `yield` fixtures for setup/teardown. `autouse=True` for automatic application. Fixture factories for parameterized fixture creation.
- Coverage: `pytest-cov`. Branch coverage (more meaningful than line coverage). `# pragma: no cover` for intentional exclusions. Coverage thresholds in CI.
- Hypothesis: property-based testing. Generate random inputs from strategies. Shrinks failing examples to minimal reproduction. Find edge cases you'd never think of.
- factory_boy: test data factories. `Factory`, `SubFactory`, `LazyAttribute`, `Sequence`. Integrates with Django, SQLAlchemy. Better than manual fixture data.
- Time mocking: `freezegun` or `time-machine` (faster). Freeze/travel time for tests involving datetime, expiry, scheduling.
- pytest-asyncio: async test support. `@pytest.mark.asyncio`. Async fixtures. Event loop fixtures.
- tox / nox: test automation across multiple Python versions. Matrix testing. nox uses Python for config (vs tox's ini format).

---

## 3. Software Architecture

### 3.1 Design Principles

**SOLID Principles**
- **Single Responsibility (SRP)**: a class/module should have one reason to change. Not "one thing" but "one actor/stakeholder." Separate concerns: data access, business logic, presentation. Signs of violation: class changes for unrelated reasons, large classes with mixed responsibilities.
- **Open/Closed (OCP)**: open for extension, closed for modification. Use polymorphism, strategy pattern, plugin architecture. Add new behavior by adding new code, not changing existing code. Not always achievable — pragmatism matters.
- **Liskov Substitution (LSP)**: subtypes must be usable wherever base type is expected. No surprising behavior. If Square extends Rectangle, setting width shouldn't change height. Design by contract: preconditions can't be strengthened, postconditions can't be weakened.
- **Interface Segregation (ISP)**: prefer small, focused interfaces over fat ones. Clients shouldn't depend on methods they don't use. In Python: use Protocols, ABCs with minimal methods. Multiple small mixins over one large base class.
- **Dependency Inversion (DIP)**: high-level modules shouldn't depend on low-level modules; both depend on abstractions. Don't import concrete implementations directly. Dependency injection. In Python: pass dependencies as constructor arguments, use Protocols for typing.

**Other Key Principles**
- **DRY (Don't Repeat Yourself)**: extract when you see 3+ repetitions (Rule of Three), not 2. Premature DRY creates wrong abstractions. "Duplication is far cheaper than the wrong abstraction" — Sandi Metz.
- **KISS (Keep It Simple)**: simplest solution that meets requirements. Complexity is the enemy. Simple code is easier to debug, test, extend. Beware "astronaut architecture."
- **YAGNI (You Aren't Gonna Need It)**: don't build for hypothetical future requirements. Build for today, refactor when needed. Speculative generality is an anti-pattern.
- **Composition over inheritance**: prefer "has-a" over "is-a." Mixins cautiously. Inheritance creates tight coupling. Python's dynamic nature makes composition easy (duck typing, Protocols).
- **Separation of Concerns**: each module/layer handles one concern. UI, business logic, data access, infrastructure. Reduces cognitive load, improves testability.
- **Principle of Least Surprise**: code should behave as other developers expect. Follow language conventions. Consistent naming. Predictable APIs.
- **Tell, Don't Ask**: tell objects what to do, don't ask for their state and make decisions externally. Encapsulation. Move behavior to where the data is.

**Coupling & Cohesion**
- **Tight coupling**: classes depend on each other's internals. Changes ripple. Hard to test in isolation. Signs: direct instantiation of dependencies, accessing private attributes, many import dependencies.
- **Loose coupling**: interact through well-defined interfaces. Dependency injection. Event-driven communication. Message passing. Easy to swap implementations.
- **Afferent coupling (Ca)**: number of classes that depend on this class. High Ca = high responsibility, change is risky.
- **Efferent coupling (Ce)**: number of classes this class depends on. High Ce = fragile, breaks when dependencies change.
- **Instability = Ce / (Ca + Ce)**: 0 = maximally stable, 1 = maximally unstable. Stable classes should be abstract.
- **High cohesion**: elements within a module are strongly related. Single purpose. Low cohesion = "utility" classes, god objects.
- **Package by feature** (users/, orders/, products/) vs **package by layer** (models/, views/, services/). Feature packaging promotes cohesion, reduces coupling between features.

**Domain-Driven Design (DDD)**
- **Bounded Context**: explicit boundary around a domain model. Different contexts can have different models for same real-world concept (e.g., "User" means different things in auth vs billing).
- **Ubiquitous Language**: shared language between developers and domain experts within a bounded context. Code uses same terms as business. Reduces translation errors.
- **Entities**: identified by ID, mutable, lifecycle. Equality by identity, not attributes. (e.g., User, Order).
- **Value Objects**: identified by attributes, immutable. Equality by value. No separate ID. (e.g., Money, Address, DateRange). Use `@dataclass(frozen=True)` or `NamedTuple`.
- **Aggregates**: cluster of entities/value objects treated as a unit. One entity is the aggregate root (entry point). All modifications go through root. Consistency boundary.
- **Domain Events**: something meaningful that happened in the domain. Immutable, past-tense naming (OrderPlaced, PaymentReceived). Enable loose coupling between bounded contexts. Event sourcing stores events as source of truth.
- **Repository**: abstraction for data access. Hides storage details from domain. In-memory collection-like interface. One repository per aggregate root.
- **Anti-Corruption Layer (ACL)**: translation layer between bounded contexts or legacy systems. Prevents foreign models from leaking into your domain.
- **Context Mapping**: how bounded contexts relate. Patterns: shared kernel, customer-supplier, conformist, ACL, published language.
- **Strategic DDD**: identifying bounded contexts, their relationships, team ownership. Tactical DDD: implementation patterns within a context.

**Clean / Hexagonal Architecture**
- **Ports & Adapters (Hexagonal)**: application core defines ports (interfaces). Adapters implement ports for external systems (database, HTTP, messaging). Core has zero knowledge of infrastructure.
- **Dependency Rule**: dependencies point inward. Outer layers depend on inner layers, never the reverse. Domain → Use Cases → Interface Adapters → Frameworks.
- **Layers**: Domain (entities, value objects), Application (use cases, orchestration), Infrastructure (database, HTTP, messaging), Interface (API controllers, CLI).
- **Benefits**: testability (mock adapters), framework independence (swap Django for FastAPI), clear boundaries.
- **Onion Architecture**: similar to hexagonal. Concentric layers: Domain Model → Domain Services → Application Services → Infrastructure.
- **Trade-off**: adds complexity. Not worth it for small CRUD apps. Shines in complex business logic with multiple I/O dependencies. Start simple, extract layers when complexity warrants.

### 3.2 Design Patterns

**Creational Patterns**
- **Factory Method**: define interface for creating objects, let subclasses decide the class. In Python: classmethod factories (`User.create_from_dict()`), module-level factory functions.
- **Abstract Factory**: create families of related objects. Plugin systems (database backends, storage backends). In Python: dict mapping + dynamic import.
- **Builder**: construct complex objects step by step. Fluent API. In Python: `dataclasses` with defaults, method chaining, or dedicated builder class. Useful for complex configuration objects.
- **Singleton**: ensure single instance. Controversial — global state, testing difficulty. In Python: module-level instance is the idiomatic singleton. Or `__new__` override. Prefer dependency injection.
- **Prototype**: clone existing objects. In Python: `copy.copy()` (shallow) and `copy.deepcopy()` (deep). Useful when object creation is expensive.
- **Object Pool**: reuse expensive objects (database connections, threads). `queue.Queue` of pre-created objects. Connection pools (PgBouncer, SQLAlchemy pool).

**Structural Patterns**
- **Adapter**: convert interface of one class to another. Wrap legacy code. In Python: class wrapper or function wrapper. Common for integrating third-party libraries.
- **Decorator (pattern, not Python decorator)**: add behavior dynamically. Wrap object with same interface. In Python: `functools.wraps`, class wrappers. Logging, caching, retry decorators.
- **Facade**: simplified interface to complex subsystem. Hide internal complexity. In Python: module or class that wraps multiple components. Service layer as facade over domain logic.
- **Proxy**: control access to object. Types: virtual proxy (lazy loading), protection proxy (access control), caching proxy, remote proxy (RPC). In Python: `__getattr__` delegation.
- **Composite**: tree structure, uniform interface. In Python: recursive data structures, file system trees, UI component trees, organization hierarchies.
- **Bridge**: decouple abstraction from implementation. Separate "what" from "how." In Python: strategy pattern achieves similar goals.

**Behavioral Patterns**
- **Strategy**: define family of interchangeable algorithms. In Python: pass functions/callables as arguments. Or Protocol-based strategy classes. Used for: payment processing, notification channels, serialization formats.
- **Observer**: notify dependents of state changes. In Python: Django signals, custom event bus, `blinker` library, callbacks/hooks. Decouples publisher from subscribers.
- **Command**: encapsulate request as object. Supports undo, queue, logging. In Python: callable objects or functions with metadata. Task queues (Celery tasks are commands).
- **Chain of Responsibility**: pass request along chain of handlers. Each handler can process or pass to next. In Python: middleware stacks (Django/ASGI middleware), validation chains, logging handlers.
- **State Machine**: object behavior changes based on internal state. Transitions between states. In Python: `transitions` library, enum-based state machines, match/case (3.10+). Used for: order processing, workflow engines, protocol parsing.
- **Template Method**: define skeleton in base class, let subclasses override steps. In Python: abstract base classes with concrete and abstract methods. Django class-based views.
- **Mediator**: centralize complex communication between objects. Reduce direct dependencies. In Python: event bus, message broker, coordinator services.
- **Iterator**: sequential access without exposing underlying structure. In Python: built-in via `__iter__`/`__next__`. Generators are the Pythonic way.
- **Visitor**: add operations to objects without modifying them. Double dispatch. In Python: `functools.singledispatch` for type-based dispatch. AST processing.

**Concurrency Patterns**
- **Producer-Consumer**: decouple data production from consumption via buffer/queue. In Python: `queue.Queue`, `asyncio.Queue`, Celery, Redis streams.
- **Thread Pool / Worker Pool**: fixed set of threads processing tasks from queue. `concurrent.futures.ThreadPoolExecutor`. Bound resource usage.
- **Future/Promise**: placeholder for result of async operation. `concurrent.futures.Future`, `asyncio.Future`. Chain computations.
- **Circuit Breaker**: prevent cascade failures. States: closed (normal), open (failing fast), half-open (testing recovery). Libraries: `pybreaker`, `tenacity`. Configurable thresholds, timeout, fallback.
- **Bulkhead**: isolate failures to compartments. Separate thread pools, connection pools, rate limits per dependency. Prevents one failing dependency from consuming all resources.
- **Saga**: manage distributed transactions. Choreography (event-driven, each service reacts) vs orchestration (central coordinator). Compensating transactions for rollback.
- **Backpressure**: signal upstream to slow down when downstream is overwhelmed. Bounded queues, flow control, reactive streams.

### 3.3 Architectural Styles

**Monolith**
- **Modular monolith**: best starting point for most projects. Clear module boundaries, internal APIs. Each module owns its data. Can be extracted to services later if needed.
- **Layered architecture**: presentation → business logic → data access → database. Simple, well-understood. Risk: layers become too coupled, bypass layering.
- **Package by feature**: organize code by business feature (users/, orders/, payments/) rather than technical layer (models/, views/, services/). Better cohesion, easier to understand business logic.
- **When monolith is RIGHT**: small team (<10 devs), early-stage product, simple deployment needs, strong consistency requirements. Microservices are NOT an upgrade from monolith — they're a different tradeoff.
- **Strangler fig pattern**: incrementally replace monolith functionality with new services. Route traffic gradually. Both systems run in parallel during migration.

**Microservices**
- **Service boundaries**: align with bounded contexts (DDD). One team owns one or few services. Service owns its data (no shared database). Size: small enough to rewrite in ~2 weeks.
- **Data ownership**: each service has its own database. No direct database access between services. Data replication via events or API calls. Accept eventual consistency.
- **Communication**: synchronous (HTTP/gRPC, simpler but creates coupling) vs asynchronous (message broker, more complex but decoupled). Prefer async for cross-service communication.
- **Service mesh**: sidecar proxy (Envoy) for service-to-service communication. Handles: mTLS, load balancing, circuit breaking, retries, observability. Istio, Linkerd.
- **Distributed tracing**: follow request across services. Trace ID propagation. Spans for each service call. Jaeger, Zipkin, OpenTelemetry.
- **Conway's Law**: system design mirrors organizational structure. Align team boundaries with service boundaries. Inverse Conway maneuver: structure teams to get desired architecture.
- **When NOT to use microservices**: small team, unclear domain boundaries, need strong consistency, limited DevOps maturity, early-stage product.
- **Common failures**: distributed monolith (services too coupled), data consistency nightmares, network reliability assumptions, increased operational complexity.

**Event-Driven Architecture**
- **Event Sourcing**: store every state change as an immutable event. Derive current state by replaying events. Full audit trail. Temporal queries. Can rebuild state from any point. Trade-off: complexity, eventual consistency, event schema evolution.
- **CQRS (Command Query Responsibility Segregation)**: separate models for reads and writes. Write model optimized for consistency/business rules. Read model optimized for queries (denormalized, different storage). Can use different databases.
- **Event Bus / Message Broker**: Kafka (high throughput, log-based, replay), RabbitMQ (flexible routing, AMQP, traditional messaging), Redis Streams (lightweight, in-memory). AWS SNS/SQS.
- **Eventual consistency**: data will become consistent eventually (not immediately). Acceptable for many use cases (analytics, notifications, search index). Unacceptable for financial transactions, inventory.
- **Idempotency**: processing same event multiple times produces same result. Critical for at-least-once delivery. Techniques: idempotency key, check-and-set, deduplication table.
- **Outbox pattern**: write event to outbox table in same transaction as data change. Separate process publishes events from outbox. Guarantees data and event consistency.
- **Dead letter queue (DLQ)**: messages that fail processing after max retries go to DLQ. Monitor, investigate, reprocess. Essential for reliability.

**Serverless & FaaS**
- Lambda/Cloud Functions: stateless functions triggered by events (HTTP, queue, schedule, database change). Pay per invocation. Auto-scales to zero.
- Cold starts: first invocation after idle period is slow (100ms-10s depending on runtime/size). Mitigations: provisioned concurrency, keep-warm pings, smaller deployments, language choice (Python ~200ms, Java ~1-3s).
- Stateless design: no local file system persistence. External state (DynamoDB, S3, Redis). Idempotent handlers.
- Limitations: execution time limits (15min AWS Lambda), payload size limits, no long-running connections (WebSocket), vendor lock-in, debugging complexity.
- When it fits: event processing, scheduled tasks, webhooks, light APIs, glue code between services, prototyping. When it doesn't: sustained high traffic (cost), complex workflows, low-latency requirements.

---

## 4. Databases & Data

### 4.1 Relational Databases (PostgreSQL Focus)

**Query Optimization**
- `EXPLAIN ANALYZE`: actual execution plan with timing. Read bottom-up. Key metrics: actual rows vs estimated rows (bad estimate = bad plan), loops, shared hit/read (buffer cache).
- Index types: B-tree (default, equality + range), Hash (equality only, rarely better), GIN (full-text search, JSONB, arrays), GiST (geometric, range types, full-text), BRIN (block range index, for naturally ordered data like timestamps — very compact).
- Partial indexes: `CREATE INDEX idx ON orders (status) WHERE status = 'pending'`. Index only relevant rows. Smaller, faster.
- Expression indexes: `CREATE INDEX idx ON users (lower(email))`. Index computed values. Must match query expression exactly.
- Composite index column order: leftmost prefix matters. Index on (a, b, c) supports queries on (a), (a, b), (a, b, c), but NOT (b) or (c) alone. Put equality columns first, range columns last.
- Index-only scans: query answered entirely from index (no table access). Requires all selected columns in index. `INCLUDE` clause for additional columns without affecting index ordering.
- `pg_stat_statements`: track query execution statistics (calls, mean/total time, rows). Essential for finding slow queries. Reset periodically.
- Query planner decisions: sequential scan vs index scan (depends on selectivity, table size). Nested loop vs hash join vs merge join. `SET enable_seqscan = off` for testing (never in production).
- Common mistakes: missing indexes on foreign keys, `SELECT *` preventing index-only scans, functions in WHERE preventing index use, implicit type casting, `OR` conditions preventing index use (use `UNION` instead).

**Transactions & Concurrency**
- ACID: Atomicity (all or nothing), Consistency (valid state), Isolation (concurrent transactions don't interfere), Durability (committed data survives crashes).
- Isolation levels: Read Committed (default in PostgreSQL, sees committed data at statement start), Repeatable Read (snapshot at transaction start, serialization failures possible), Serializable (appears serial execution, most serialization failures).
- MVCC (Multi-Version Concurrency Control): each transaction sees a snapshot. Writers don't block readers, readers don't block writers. Dead tuples (old versions) cleaned by VACUUM.
- Row-level locking: `SELECT FOR UPDATE` (exclusive lock), `SELECT FOR SHARE` (shared lock), `SELECT FOR UPDATE SKIP LOCKED` (skip locked rows — great for job queues), `SELECT FOR UPDATE NOWAIT` (fail immediately if locked).
- Advisory locks: application-level locks managed by PostgreSQL. `pg_advisory_lock(key)`, `pg_try_advisory_lock(key)`. Great for distributed locking, ensuring single worker for a task.
- Deadlock detection: PostgreSQL detects deadlocks and aborts one transaction. Consistent lock ordering prevents deadlocks. Keep transactions short.
- VACUUM: reclaim dead tuple space. Autovacuum runs automatically (tune `autovacuum_vacuum_scale_factor`). `VACUUM FULL` rewrites table (locks table, use sparingly). Dead tuple bloat monitoring.
- Transaction anti-patterns: long-running transactions (hold locks, prevent vacuum), implicit transactions (autocommit off by default in psycopg2), savepoints for partial rollback.

**Schema Design**
- Normalization: 1NF (atomic values, no repeating groups), 2NF (no partial dependencies on composite key), 3NF (no transitive dependencies), BCNF (every determinant is a candidate key). Normalize first, denormalize for performance later.
- Denormalization trade-offs: faster reads, slower writes, data consistency risk. Materialized views, computed columns, summary tables are controlled denormalization.
- JSONB columns: when to use — dynamic attributes, user preferences, API response storage, schema-less extensions. When not to use — data you query/join/filter frequently (use proper columns). Can index with GIN.
- Partitioning: divide large tables. Range partitioning (by date — most common), list partitioning (by category), hash partitioning (even distribution). Partition pruning eliminates irrelevant partitions. Essential for time-series data retention.
- UUID vs serial PKs: UUIDs avoid hotspots in distributed systems, prevent ID enumeration, no coordination needed. Serial/BIGSERIAL is smaller (8 vs 16 bytes), better index performance, naturally ordered. UUIDv7 (time-sorted) combines benefits.
- Soft deletes: `deleted_at` timestamp instead of actual DELETE. Pros: easy undo, audit trail, referential integrity. Cons: query complexity (add `WHERE deleted_at IS NULL` everywhere), index bloat, GDPR compliance issues. Alternative: archive table.
- Multi-tenancy: separate database (strongest isolation, operational overhead), separate schema (good isolation, migration complexity), row-level (simplest, use `tenant_id` everywhere + row-level security).

**Advanced PostgreSQL**
- CTEs (Common Table Expressions): `WITH name AS (query)`. Readable subqueries. Recursive CTEs for hierarchical data: `WITH RECURSIVE tree AS (base UNION ALL recursive)`. Org charts, category trees, graph traversal.
- Window functions: `ROW_NUMBER()` (numbering), `RANK()`/`DENSE_RANK()` (ranking with ties), `LAG()`/`LEAD()` (access previous/next rows), `SUM() OVER (ORDER BY date)` (running totals), `NTILE()` (percentiles). `PARTITION BY` for grouping, `ORDER BY` for ordering within partition. `ROWS BETWEEN` for frame specification.
- Materialized views: pre-computed query results. `CREATE MATERIALIZED VIEW`. `REFRESH MATERIALIZED VIEW CONCURRENTLY` (no lock, requires unique index). Use for expensive aggregations, dashboards. Refresh on schedule or trigger.
- `LISTEN/NOTIFY`: PostgreSQL pub/sub. `NOTIFY channel, 'payload'`. `LISTEN channel`. Low-latency event notification. Use for cache invalidation, real-time updates. Limited payload size (8000 bytes).
- Full-text search: `tsvector` (document), `tsquery` (query). `to_tsvector('english', text)`. GIN index. Ranking with `ts_rank`. Phrase search. Headline with highlighted matches. Custom dictionaries.
- `pg_trgm`: trigram-based similarity search. `LIKE`/`ILIKE` with GIN index. `similarity()` function. Fuzzy matching, typo tolerance. `CREATE INDEX idx ON table USING gin (column gin_trgm_ops)`.
- Extensions: PostGIS (geospatial), TimescaleDB (time-series), pg_partman (partition management), pgvector (vector similarity search for ML/embeddings), pg_stat_statements (query stats), pg_cron (scheduled jobs).

**Replication & High Availability**
- Streaming replication: physical replication of WAL (Write-Ahead Log). Synchronous (guaranteed consistency, added latency) vs asynchronous (lower latency, potential data loss on failover).
- Logical replication: replicate specific tables/operations. Can replicate between different PostgreSQL versions. Selective replication. Can have different indexes/schemas on replica.
- Read replicas: route read queries to replicas, writes to primary. Replication lag (ms to seconds). Application must handle stale reads. Session-based routing for read-your-writes consistency.
- Connection pooling: PgBouncer (lightweight, supports transaction/session/statement pooling), pgpool-II (more features: load balancing, query routing). Essential for reducing connection overhead (each PostgreSQL connection = ~10MB).
- Failover: Patroni (industry standard, etcd/ZooKeeper/Consul for consensus, automatic failover), repmgr. VIP/DNS switchover. Application retry logic.
- PITR (Point-in-Time Recovery): continuous WAL archiving. Recover to any point in time. Base backup + WAL replay. Essential for disaster recovery.
- Backup strategies: `pg_dump` (logical, single database, portable), `pg_dumpall` (all databases), `pg_basebackup` (physical, full cluster), WAL-G (continuous WAL archiving to cloud storage, PITR support).

### 4.2 NoSQL & Specialized Databases

**Redis**
- Data types: Strings (counters, simple cache), Hashes (object fields), Lists (queues, timelines), Sets (unique collections, tags), Sorted Sets (leaderboards, priority queues, rate limiting), Streams (event log, consumer groups), HyperLogLog (cardinality estimation), Bitmaps (feature flags, user activity tracking), Geospatial (location-based queries).
- Pub/Sub: `PUBLISH`, `SUBSCRIBE`, `PSUBSCRIBE` (pattern). Fire-and-forget (no persistence). Use Streams for persistent messaging.
- Lua scripting: `EVAL`. Atomic execution of multiple commands. No race conditions. Used for complex operations (rate limiting, distributed locking). EVALSHA for cached scripts.
- Pipelining: batch multiple commands in single round-trip. 5-10x throughput improvement. `MULTI`/`EXEC` for transactions (all-or-nothing, but no rollback — use Lua for conditional logic).
- Redis Cluster: automatic sharding (16384 hash slots). Multi-master with replicas. Cluster-aware clients. No cross-slot transactions. vs Sentinel: master-slave with automatic failover, no sharding.
- Persistence: RDB (periodic snapshots, compact, faster recovery, data loss between snapshots), AOF (append-only file, every write logged, fsync configurable, larger but more durable). Use both for best durability.
- Use cases: session storage, caching (with TTL), rate limiting (INCR + EXPIRE or sorted sets), distributed locking (RedLock), leaderboards (sorted sets), job queues (lists or streams), real-time analytics.
- Memory management: `maxmemory` policy (allkeys-lru, volatile-lru, allkeys-random, noeviction). Monitor memory with `INFO memory`. Key expiration. `SCAN` for iteration (not KEYS in production).

**MongoDB**
- Document model: BSON (binary JSON). Flexible schema within collection. Nested documents and arrays. Denormalization is common (embed vs reference decision).
- Aggregation pipeline: `$match` (filter), `$group` (aggregate), `$project` (reshape), `$lookup` (join), `$unwind` (flatten arrays), `$sort`, `$limit`, `$facet` (parallel pipelines). Powerful but complex.
- Indexing: B-tree indexes, compound indexes, multi-key (array fields), text indexes, geospatial (2dsphere), TTL indexes (auto-expire documents), partial indexes, wildcard indexes.
- Sharding: horizontal scaling. Shard key selection is critical and irreversible. Range sharding vs hashed sharding. Choose high-cardinality, write-distributed key. Avoid monotonically increasing keys (hotspot). Jumbo chunks.
- Replica sets: automatic failover, read preferences (primary, primaryPreferred, secondary, nearest). Write concern (w:1, w:"majority"). Read concern (local, majority, linearizable).
- Change streams: real-time notification of data changes. Resume token for fault tolerance. Trigger-like functionality without polling. Use for: CDC, cache invalidation, event-driven architecture.
- When documents fit: variable schema, hierarchical data, content management, catalogs, user profiles. When they don't: heavy relationships/joins, multi-document transactions (supported but expensive), strict schema requirements.

**Elasticsearch / OpenSearch**
- Inverted index: maps terms to documents containing them. Foundation of full-text search. Each field can have different analyzers.
- Analyzers: tokenizer + token filters. Standard (split on whitespace/punctuation), keyword (no splitting), custom (language-specific stemming, synonyms, ngrams). Character filters for preprocessing.
- Mappings: define field types and analysis. Static (explicit) vs dynamic (auto-detected). `keyword` (exact match, sorting, aggregations) vs `text` (full-text search, analyzed). Multi-field mappings.
- Query DSL: `match` (full-text), `term` (exact), `range`, `bool` (must/should/must_not/filter). Full-text queries are scored, filter queries are cached. Combine for relevance + filtering.
- Aggregations: metrics (avg, sum, min, max, stats), bucket (terms, histogram, date_histogram, range), pipeline (derivative, moving_avg). Basis for analytics dashboards.
- Sharding & replication: primary shards (set at index creation, hard to change), replica shards (scalable read throughput, fault tolerance). Shard sizing: 10-50GB each.
- Performance tuning: bulk indexing, refresh interval, doc_values for aggregations, fielddata circuit breaker, query caching, index lifecycle management (hot-warm-cold).

**Time-Series & Analytics**
- TimescaleDB: PostgreSQL extension. Hypertables (auto-partitioned by time). Compression (90%+ for older data). Continuous aggregates (auto-updated materialized views). Compatible with all PostgreSQL tooling.
- ClickHouse: columnar OLAP database. Extremely fast analytical queries. MergeTree engine family. Parallel processing. 100-1000x faster than PostgreSQL for analytical queries. Limited update/delete support.
- Columnar storage: Parquet (Hadoop ecosystem), ORC. Efficient compression (similar values together). Column pruning (read only needed columns). Predicate pushdown. 10-100x compression vs row-based.
- OLTP vs OLAP: OLTP (transactional — many small reads/writes, normalized, row-based) vs OLAP (analytical — few complex queries over large data, denormalized, columnar). Don't mix workloads.

### 4.3 Data Management

**Migrations**
- Tools: Alembic (SQLAlchemy), Django migrations (auto-generated from models), Flyway (Java, version-based SQL scripts). Forward-only vs reversible migrations.
- Zero-downtime migrations (expand-contract): Phase 1: add new column (nullable), deploy code that writes to both. Phase 2: backfill data. Phase 3: deploy code that reads from new column. Phase 4: remove old column.
- Dangerous operations: adding NOT NULL column without default (table rewrite), dropping column (can't be undone), renaming column (breaks running code), adding index without CONCURRENTLY (locks table).
- `CREATE INDEX CONCURRENTLY`: non-blocking index creation. Takes longer but no table lock. Can fail (leaves invalid index — drop and retry). Always use for production.
- Data migrations: separate from schema migrations. Batch processing for large tables. Idempotent (re-runnable). Test with production-size data.
- Migration testing: run on copy of production data. Measure execution time. Test rollback. CI runs migrations against empty and seeded database.

**ORM Mastery**
- Django ORM: `QuerySet` is lazy (not evaluated until iterated). Chaining: `.filter()`, `.exclude()`, `.annotate()`, `.aggregate()`, `.values()`, `.order_by()`, `.distinct()`.
- `select_related`: SQL JOIN, one query. Use for ForeignKey, OneToOne. `prefetch_related`: separate query per relation, Python-side join. Use for ManyToMany, reverse FK.
- `Q` objects: complex queries with `|` (OR), `&` (AND), `~` (NOT). `F` expressions: reference model field values in queries (e.g., `filter(views__gt=F('likes') * 2)`).
- Annotations & aggregations: `annotate(total=Sum('amount'))` adds computed fields. `aggregate(avg=Avg('price'))` returns single result. Subquery, OuterRef for correlated subqueries.
- N+1 query detection: `django-debug-toolbar`, `nplusone` library. N+1: loop over queryset, each iteration triggers related query. Fix with `select_related`/`prefetch_related`.
- SQLAlchemy: Core (SQL expression language, explicit) vs ORM (objects, Unit of Work pattern). Session scoping. `joinedload` (eager join), `selectinload` (eager separate query), `lazyload` (on-access). 2.0 style: async support, type hints.
- Raw SQL escape hatches: Django `raw()`, `connection.cursor()`. SQLAlchemy `text()`. Use for complex queries ORM can't express. Always parameterize (never string format).

**Data Pipelines**
- ETL (Extract, Transform, Load) vs ELT (Extract, Load, Transform): ETL transforms before loading (traditional, limited by ETL tool). ELT loads raw then transforms in-place (modern, leverages destination power — dbt, BigQuery).
- Batch vs streaming: Batch (Airflow, Spark — process accumulated data periodically). Streaming (Kafka, Flink — process events as they arrive). Lambda architecture (both). Kappa architecture (streaming only).
- Apache Kafka: distributed log. Topics (categories), partitions (parallelism, ordering within partition), consumer groups (load balancing). Retention policy (time or size based). Exactly-once semantics (idempotent producer + transactional consumer). Kafka Connect for data integration.
- CDC (Change Data Capture): capture database changes as events. Debezium (log-based CDC for PostgreSQL, MySQL, MongoDB → Kafka). Enables real-time replication, cache invalidation, event sourcing from existing databases.
- Orchestration: Airflow (Python DAGs, scheduling, monitoring — mature but complex), Dagster (software-defined assets, better testing/typing), Prefect (Python-native, dynamic workflows).
- Data quality: Great Expectations (data validation framework, expectation suites, data docs). Schema validation. Null checks, uniqueness constraints, referential integrity. Alerting on quality failures.

---

## 5. API Design & Integration

### 5.1 RESTful APIs

**REST Principles**
- Resource-oriented: URLs represent resources (nouns, not verbs). `/users`, `/orders/{id}`, `/users/{id}/orders`. Use plural nouns. Hierarchical for relationships.
- HTTP methods: GET (read, idempotent, cacheable), POST (create, not idempotent), PUT (full replace, idempotent), PATCH (partial update, idempotent), DELETE (remove, idempotent).
- Status codes: 200 OK, 201 Created (with Location header), 204 No Content (successful DELETE/PUT), 301/302/307 redirects, 400 Bad Request, 401 Unauthorized (not authenticated), 403 Forbidden (not authorized), 404 Not Found, 409 Conflict, 422 Unprocessable Entity (validation), 429 Too Many Requests, 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout.
- HATEOAS: include links to related resources and available actions. Discoverability. Rarely implemented fully — pragmatic approach: include `self`, `next`, `prev` links.
- Idempotency: same request multiple times = same result. GET, PUT, DELETE are idempotent. POST is not. Use idempotency keys for POST (client generates unique key, server deduplicates).
- Content negotiation: `Accept: application/json`, `Content-Type: application/json`. Support `Accept: application/json, application/xml`. Version via Accept header: `Accept: application/vnd.api.v2+json`.
- Richardson Maturity Model: Level 0 (single URI, single verb), Level 1 (resources), Level 2 (HTTP verbs), Level 3 (HATEOAS).

**Pagination & Filtering**
- Offset-based: `?page=3&per_page=20`. Simple, familiar. Problem: inconsistent results with concurrent inserts/deletes, poor performance for deep pages (OFFSET scans and discards rows).
- Cursor-based: `?cursor=eyJpZCI6MTAwfQ`. Encode position (typically last item's sort key). Consistent results, good performance. Can't jump to arbitrary page. Used by most APIs (Twitter, Slack, Stripe).
- Keyset pagination: `WHERE (created_at, id) > ($last_created_at, $last_id) ORDER BY created_at, id LIMIT 20`. Uses index efficiently. Requires unique sort key (add `id` as tiebreaker).
- Filtering: query params `?status=active&created_after=2024-01-01`. Operators: `?price[gte]=100&price[lte]=500` or `?price__gte=100` (Django-style). Complex filtering: consider search parameter with mini-language.
- Sorting: `?sort=created_at` (ascending), `?sort=-created_at` (descending). Multiple: `?sort=-priority,created_at`.
- Sparse fieldsets: `?fields=id,name,email`. Reduce payload size. GraphQL advantage but achievable in REST.

**Error Handling**
- Consistent format (RFC 7807 Problem Details): `{ "type": "uri", "title": "Validation Error", "status": 422, "detail": "Email is required", "instance": "/users" }`.
- Machine-readable error codes: `"code": "INVALID_EMAIL_FORMAT"`. Clients can handle programmatically. Document all error codes.
- Validation errors: per-field details. `{ "errors": [{"field": "email", "code": "REQUIRED", "message": "Email is required"}, {"field": "age", "code": "MIN_VALUE", "message": "Must be at least 18"}] }`.
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix timestamp). `Retry-After` header on 429 responses.
- Idempotency keys: `Idempotency-Key: <uuid>` header. Server stores result, returns cached response on retry. TTL for key storage (typically 24-48h). Essential for payment APIs.

### 5.2 Beyond REST

**GraphQL**
- Schema-first design: define types, queries, mutations. Strong typing. Self-documenting (introspection). Schema is the contract.
- Resolvers: function per field. Resolve data from any source (database, API, cache). Resolver chain for nested types.
- N+1 problem: naively resolving nested fields triggers N+1 queries. DataLoader: batch and cache within a request. Collect all IDs, single query, distribute results.
- Pagination: Relay-style connections. `{ edges { node { ... } cursor } pageInfo { hasNextPage endCursor } }`. Cursor-based, consistent.
- Authorization: field-level (check permissions per field/type). Directive-based (`@auth(requires: ADMIN)`) or resolver-based. Depth limiting to prevent abuse.
- When GraphQL > REST: multiple clients needing different data shapes, deeply nested data, rapid iteration on frontend without backend changes. When REST is better: simple CRUD, caching (HTTP caching works out of the box), file uploads, server-to-server.

**gRPC**
- Protocol Buffers (protobuf): binary serialization format. Schema defined in `.proto` files. Code generation for multiple languages. Strongly typed. 5-10x smaller than JSON, 5-10x faster serialization.
- Communication patterns: Unary (request-response, like REST), Server streaming (server sends stream), Client streaming (client sends stream), Bidirectional streaming (both stream).
- HTTP/2: multiplexing, header compression, binary framing. Lower latency than HTTP/1.1 REST.
- Interceptors: middleware equivalent. Authentication, logging, metrics, retry. Client-side and server-side.
- When to choose gRPC: inter-service communication (especially polyglot), performance-critical paths, streaming data, well-defined service contracts. When REST: public APIs (browser compatibility), simpler tooling/debugging, human-readable payloads.

**WebSocket & Server-Sent Events**
- WebSocket: full-duplex, persistent connection. Upgrade from HTTP. Binary and text frames. Use for: real-time chat, gaming, live collaboration, trading platforms.
- SSE (Server-Sent Events): server → client only. Built on HTTP (simpler than WebSocket). Auto-reconnect. Event types. Use for: live feeds, notifications, progress updates, streaming LLM responses.
- WebSocket scaling: sticky sessions (route to same server) or external pub/sub (Redis). Connection limits per server. Heartbeats for connection health. Graceful reconnection with exponential backoff.
- When to use each: SSE for server→client (dashboards, feeds), WebSocket for bidirectional (chat, gaming), HTTP polling as simplest option (infrequent updates, low concurrency).

**Message Queues & Async APIs**
- RabbitMQ: AMQP protocol. Exchanges (direct, topic, fanout, headers) route to queues. Dead letter exchanges/queues for failed messages. Acknowledgements (manual for reliability). Prefetch count for flow control. Clustering for HA.
- Kafka: distributed log, not traditional queue. Topics with partitions. Consumer groups for parallel processing. Retention (replay events). Exactly-once with idempotent producers + transactions. Higher throughput than RabbitMQ but higher operational complexity.
- Celery: Python distributed task queue. Backends: Redis, RabbitMQ. Task routing. Retry with backoff. Rate limiting. Task chaining, groups, chords. Canvas for complex workflows. Monitoring: Flower.
- Webhooks: HTTP callbacks for event notification. Design considerations: HMAC signature verification (prevent spoofing), retry with exponential backoff, idempotency (receiver handles duplicates), timeout handling, event payload versioning.
- AsyncAPI: specification for async APIs (like OpenAPI for REST). Document message channels, schemas, operations. Code generation.

### 5.3 Authentication & Authorization

**Authentication**
- OAuth 2.0 flows: Authorization Code (server-side apps, most secure), Authorization Code + PKCE (SPAs, mobile), Client Credentials (machine-to-machine), Device Code (TV, CLI). Implicit flow deprecated.
- JWT (JSON Web Token): Header.Payload.Signature (base64url encoded). Stateless — server doesn't store session. Signing: HS256 (symmetric), RS256/ES256 (asymmetric, preferred). Include: sub (user), exp (expiry), iat (issued at), iss (issuer), aud (audience).
- Refresh tokens: short-lived access token (15-60 min) + long-lived refresh token (days-weeks). Rotation: new refresh token on each use, detect reuse (compromise indicator). Store refresh tokens in HttpOnly cookies or secure server-side.
- API keys: simple authentication for server-to-server. Not for user authentication. Hash before storing. Prefix for identification (e.g., `sk_live_`). Rate limit per key. Key rotation support.
- Session-based auth: server stores session data (Redis, database). Session ID in HttpOnly, Secure, SameSite cookie. CSRF protection required. Better for traditional web apps. Easier revocation than JWT.
- SSO: SAML (XML-based, enterprise), OIDC (OpenID Connect, OAuth 2.0 extension, modern). OIDC: ID token (JWT with user info) + access token. Provider handles authentication.

**Authorization**
- RBAC (Role-Based Access Control): users → roles → permissions. Simple, widely understood. Limitation: role explosion for fine-grained control. Example: admin, editor, viewer roles.
- ABAC (Attribute-Based Access Control): policies based on user attributes, resource attributes, action, context. More flexible than RBAC. Example: "user.department == resource.department AND time < 18:00."
- Policy engines: OPA (Open Policy Agent) with Rego language. Externalize authorization decisions. Test policies independently. Consistent across services. Cedar (AWS).
- Row-level security (RLS): PostgreSQL feature. Policies restrict which rows a user can see/modify. `CREATE POLICY`. Enable with `ALTER TABLE ENABLE ROW LEVEL SECURITY`. Great for multi-tenancy.
- Principle of least privilege: grant minimum permissions necessary. Default deny. Explicit allow. Regular audit. Time-bound access for elevated permissions.

---

## 6. System Design

### 6.1 Scalability

**Horizontal vs Vertical Scaling**
- Vertical: bigger machine (more CPU, RAM, SSD). Simple but has ceiling. Good for databases (scaling reads horizontally is easier than writes). Cost increases non-linearly.
- Horizontal: more machines. Requires stateless design (externalize sessions, caches). Auto-scaling based on CPU, memory, queue depth, custom metrics. Nearly unlimited scale.
- Stateless services: no local state between requests. Session in Redis/database. File uploads to S3. Configuration from environment. Any instance can handle any request.

**Load Balancing**
- L4 (transport layer): TCP/UDP. Based on IP + port. Faster (no packet inspection). NAT-based. Handles any protocol.
- L7 (application layer): HTTP/HTTPS. Content-based routing (URL path, headers, cookies). SSL termination. WebSocket upgrade. More flexible.
- Algorithms: Round-robin (simple, equal distribution), Weighted round-robin (capacity-aware), Least connections (route to least busy), IP hash (session affinity), Consistent hashing (minimal redistribution on server changes).
- Health checks: active (periodic probe: HTTP 200, TCP connect) vs passive (monitor response codes). Unhealthy servers removed from pool. Grace period for startup.
- SSL termination: decrypt at load balancer, backend communication in plaintext (within trusted network) or re-encrypt (end-to-end encryption). Offloads CPU-intensive TLS from backends.

**Caching**
- Cache-aside (lazy loading): application checks cache, on miss loads from DB and writes to cache. Most common. Cache can become stale.
- Write-through: application writes to cache and DB simultaneously. Cache always consistent. Higher write latency.
- Write-behind (write-back): application writes to cache, cache asynchronously writes to DB. Faster writes. Risk of data loss. Used in CPU caches, some database engines.
- Read-through: cache itself loads from DB on miss. Application only talks to cache. Simpler application code.
- Cache invalidation strategies: TTL (time-based expiry, simplest), event-based (invalidate on data change), version-based (cache key includes version). "There are only two hard things in CS: cache invalidation and naming things."
- Cache stampede: many concurrent requests for same expired key. All hit DB simultaneously. Solutions: locking (only one request loads), probabilistic early expiry (XFetch), stale-while-revalidate.
- CDN: cache static assets and API responses at edge locations. CloudFront, Cloudflare, Fastly. Cache-Control headers, cache key configuration, purge/invalidation API.
- Multi-tier: L1 (in-process, fastest, limited size), L2 (shared like Redis, larger), L3 (CDN, closest to users). Cache aside at each level.

**CAP Theorem & Consistency**
- CAP: during network partition, system must choose between Consistency (all nodes see same data) and Availability (all nodes respond). Can't have both. CP: refuse requests if can't guarantee consistency (PostgreSQL, HBase). AP: respond with potentially stale data (Cassandra, DynamoDB).
- PACELC: extension. If Partition: choose A or C. Else (normal operation): choose Latency or Consistency. Most systems sacrifice consistency for latency in normal operation.
- Eventual consistency: all replicas will converge to same state given enough time without updates. Acceptable for: social feeds, analytics, search. Not for: financial transactions, inventory.
- Conflict resolution: Last-Write-Wins (simple but lossy), vector clocks (detect conflicts), CRDTs (Conflict-free Replicated Data Types — automatic conflict resolution for specific data structures: counters, sets, registers).
- Linearizability: strongest consistency. Operations appear atomic and ordered. As if single copy. Expensive (consensus protocol needed).
- Causal consistency: respects happens-before relationship. If A causes B, everyone sees A before B. Weaker than linearizable but cheaper.

### 6.2 Distributed Systems

**Consensus & Coordination**
- Raft: leader-based consensus. Leader election via randomized timeouts. Log replication to followers. Committed when majority acknowledges. Used by: etcd, Consul, CockroachDB. Easier to understand than Paxos.
- Split-brain: network partition separates cluster into groups that each think they're the leader. Prevention: quorum (majority needed for decisions), fencing (STONITH — Shoot The Other Node In The Head).
- etcd / ZooKeeper / Consul: distributed key-value stores for configuration, service discovery, leader election, distributed locking. etcd (Kubernetes uses it), Consul (service mesh), ZooKeeper (Kafka, Hadoop).

**Service Communication Patterns**
- Synchronous: HTTP/gRPC. Simple request-response. Creates temporal coupling (caller waits). Cascading failures risk. Use for: user-facing requests needing immediate response.
- Asynchronous: message broker (Kafka, RabbitMQ). Decoupled in time. Retry built-in. Higher complexity. Use for: cross-service data propagation, background processing.
- Service discovery: client-side (client queries registry, Consul, eureka) vs server-side (load balancer queries registry, Kubernetes DNS). DNS-based (simple, caching issues) vs dedicated registry.
- Circuit breaker: states: Closed (requests pass through, failures counted), Open (requests fail fast, no calls to dependency), Half-Open (allow test requests, transition to closed or open). `tenacity` library in Python. Hystrix-style.
- Retry with exponential backoff + jitter: `retry_delay = base_delay * 2^attempt + random_jitter`. Jitter prevents thundering herd. Cap maximum delay. Set max retries. Idempotent operations only.
- Timeout budgets: propagate remaining time budget through call chain. If upstream has 5s budget and first call took 2s, downstream gets 3s. Prevents wasted work when budget is exhausted.

**Observability (Three Pillars)**
- Logs: what happened. Structured logging (JSON). Correlation IDs across services. Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL. Aggregate: ELK (Elasticsearch, Logstash, Kibana) or Loki.
- Metrics: how much/how often. Counters (total requests), Gauges (current connections), Histograms (response time distribution). Prometheus + Grafana. RED method: Rate, Errors, Duration. USE method: Utilization, Saturation, Errors.
- Traces: request flow across services. Distributed tracing with OpenTelemetry. Trace ID → Spans (one per service/operation). Visualize: Jaeger, Zipkin, Datadog, Honeycomb.
- SLI/SLO/SLA: SLI (indicator: latency p99 < 200ms), SLO (objective: 99.9% of requests meet SLI), SLA (agreement: contractual commitment with consequences). Error budgets: if SLO is 99.9%, error budget is 0.1%. Spend on feature velocity; when exhausted, focus on reliability.

### 6.3 Real-World System Design Examples

**URL Shortener**
- Generate short code: counter-based (sequential, predictable), hash-based (MD5/SHA256 truncated, collision risk), Base62 encoding of auto-increment ID, nanoid/UUID truncated. 6-7 chars = billions of unique URLs.
- Storage: key-value store (Redis for hot data, DynamoDB/Cassandra for persistence). Read-heavy workload (100:1 read:write).
- Caching: cache popular URLs in Redis. 80/20 rule (20% of URLs get 80% of traffic). Cache aside with TTL.
- Analytics: click tracking (write to Kafka, process async). Geo, device, referrer. Time-series storage.
- Features: custom aliases, expiration, rate limiting (per user/IP), abuse prevention (spam URL detection).

**Distributed Rate Limiter**
- Token bucket: bucket refills at fixed rate, each request consumes a token. Allows bursts up to bucket capacity. Redis: MULTI + GET + SET with TTL.
- Sliding window: count requests in rolling time window. More accurate than fixed window. Redis sorted set with timestamp scores. ZRANGEBYSCORE + ZADD + ZREMRANGEBYSCORE.
- Fixed window counter: count per time window (e.g., per minute). Simple, Redis INCR + EXPIRE. Edge case: burst at window boundary (double rate). Hybrid: sliding window counter combines fixed windows.
- Distributed: Redis as shared state. Lua scripts for atomicity (read + increment + check in one operation). Race condition prevention.
- Multi-tier: local in-memory rate limiter for first line (approximate), shared Redis for global accuracy.

**Chat System**
- Connection: WebSocket for real-time, SSE as fallback. Connection manager tracks user → server mapping (Redis hash).
- Message flow: client → WebSocket server → message service → storage + delivery. Kafka for message bus between services.
- Storage: messages in database (partitioned by conversation + time). Last N messages cached in Redis. Media in object storage (S3).
- Features: online presence (heartbeat to Redis with TTL), read receipts (last-read pointer per user per conversation), typing indicators (ephemeral, no persistence).
- Scaling: partition conversations across servers. Message delivery: look up recipient's server, forward via internal messaging.

**Notification System**
- Channels: email (SES, SendGrid), push (FCM, APNS), SMS (Twilio), in-app (WebSocket/SSE), Slack/Teams webhooks.
- Architecture: notification service receives events → template engine renders message → channel-specific workers deliver. Priority queue (urgent vs batch).
- User preferences: opt-in/out per channel per notification type. Quiet hours. Frequency caps (max N notifications per hour).
- Reliability: at-least-once delivery. Deduplication (idempotency key per notification). Dead letter queue for failures. Delivery status tracking.

---

## 7. Infrastructure & DevOps

### 7.1 Containerization

**Docker**
- Multi-stage builds: separate build and runtime stages. Build stage has compilers/build tools, runtime stage has only dependencies and artifacts. Reduces image size dramatically.
- Layer caching: each Dockerfile instruction creates a layer. Order instructions from least to most frequently changing. Copy requirements.txt before source code (pip install cached if requirements unchanged).
- Security: run as non-root user (`USER appuser`). Distroless or Alpine base images (smaller attack surface). Scan for vulnerabilities (Trivy, Snyk). Don't store secrets in images. Read-only filesystem where possible.
- .dockerignore: exclude unnecessary files (`.git`, `node_modules`, `__pycache__`, `.env`). Reduces build context size and improves security.
- Health checks: `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`. Docker restarts unhealthy containers. Kubernetes uses readiness/liveness probes instead.
- Networking: bridge (default, isolated), host (share host network), overlay (multi-host), none. Docker Compose networking: service names as DNS.
- Volumes: named volumes (Docker-managed), bind mounts (host path), tmpfs (in-memory). Data persistence across container restarts. Volume drivers for remote storage.

**Kubernetes**
- Pod: smallest deployable unit. One or more containers sharing network/storage. Sidecar pattern (logging, proxy). Init containers (setup before main).
- Deployment: declares desired state (replicas, image, resources). Rolling updates. Rollback (`kubectl rollout undo`). Strategy: RollingUpdate (default), Recreate.
- Service: stable network endpoint for pods. Types: ClusterIP (internal), NodePort (external port), LoadBalancer (cloud LB). Selects pods by label.
- Ingress: HTTP(S) routing. Host-based and path-based routing. TLS termination. Ingress controller (nginx-ingress, traefik, AWS ALB).
- ConfigMaps & Secrets: externalize configuration. Mount as files or environment variables. Secrets base64-encoded (not encrypted by default — use external secret management).
- Resource management: `requests` (guaranteed resources, used for scheduling) and `limits` (maximum, throttled/killed if exceeded). CPU (millicores), memory (Mi/Gi). QoS classes: Guaranteed, Burstable, BestEffort.
- HPA (Horizontal Pod Autoscaler): auto-scale pods based on CPU, memory, or custom metrics. `minReplicas`, `maxReplicas`, `targetCPUUtilizationPercentage`. KEDA for event-driven scaling.
- Probes: `livenessProbe` (container alive? restart if fails), `readinessProbe` (ready to accept traffic? remove from service if fails), `startupProbe` (started successfully? gives slow-starting apps time).
- StatefulSets: for stateful workloads (databases, message brokers). Stable network identity, ordered deployment/scaling, persistent volume per pod.
- DaemonSets: one pod per node. Use for: log collectors, monitoring agents, network plugins.
- RBAC: Role/ClusterRole (define permissions), RoleBinding/ClusterRoleBinding (assign to users/service accounts). Principle of least privilege.
- Network Policies: firewall rules between pods. Default deny, explicit allow. Namespace isolation.

### 7.2 CI/CD & Deployment

**CI/CD Pipelines**
- Stages: lint → type check → unit tests → build → integration tests → security scan → deploy staging → deploy production.
- Parallel jobs: run independent stages concurrently. Matrix builds (test across Python 3.10, 3.11, 3.12).
- Caching: cache pip/npm dependencies between runs. Cache Docker layers. Significant speed improvement.
- Secret management: GitHub Actions secrets, GitLab CI variables. Never echo secrets. Mask in logs. Rotate regularly.
- Artifact management: build artifacts stored for deployment. Container registry (ECR, GCR, Docker Hub). Artifact versioning.

**Deployment Strategies**
- Blue-green: two identical environments. Switch traffic atomically. Instant rollback. Double infrastructure cost during deployment.
- Canary: route small percentage of traffic to new version. Monitor metrics. Gradually increase. Automatic rollback on error spike.
- Rolling update: replace instances one at a time. No extra infrastructure. Brief period of mixed versions. Kubernetes default.
- Feature flags: deploy code but control activation. Gradual rollout (1%, 10%, 50%, 100%). Kill switch for problems. A/B testing. LaunchDarkly, Unleash, Flagsmith.
- Database migration coordination: run migration before deploying new code (additive changes only). Or use expand-contract for breaking changes.

**Infrastructure as Code**
- Terraform: declarative. HCL language. Providers for AWS/GCP/Azure/etc. State management (remote backend: S3 + DynamoDB lock). Plan → Apply workflow. Modules for reusability. Workspaces for environments.
- Pulumi: IaC in real programming languages (Python, TypeScript). Same concepts as Terraform. Better for complex logic.
- Ansible: configuration management. Agentless (SSH). Playbooks (YAML). Idempotent tasks. Good for server configuration, not infrastructure provisioning.
- Drift detection: compare actual state with declared state. Terraform plan shows drift. Automated drift detection in CI.

### 7.3 Observability

**Logging**
- Structured logging: JSON format. Machine-parseable. Fields: timestamp, level, message, service, trace_id, user_id, request_id, duration_ms. `structlog` in Python (context-aware, processors).
- Log levels: DEBUG (development detail), INFO (business events), WARNING (unexpected but handled), ERROR (failures needing attention), CRITICAL (system-level failures). Don't log sensitive data (PII, passwords, tokens). Redact.
- Correlation IDs: unique ID per request. Propagate through all services. Include in all log entries. Track request across microservices.
- Log aggregation: ELK stack (Elasticsearch + Logstash + Kibana), EFK (Fluentd replaces Logstash), Loki + Grafana (label-based, cheaper). Cloud: CloudWatch, Cloud Logging.
- Sampling: for high-volume services, log a percentage of requests in detail. Always log errors fully. Head-based (decide at request start) vs tail-based (decide after request completes).

**Metrics & Monitoring**
- Prometheus: pull-based metrics collection. Counter (total requests), Gauge (current temperature), Histogram (request duration distribution), Summary (similar to histogram, calculated client-side).
- Grafana: visualization. Dashboards for service health, business metrics, infrastructure. Alerting rules.
- RED method: Rate (requests per second), Errors (error rate), Duration (latency distribution). For request-driven services.
- USE method: Utilization (% busy), Saturation (queue depth), Errors. For resources (CPU, memory, disk, network).
- Four Golden Signals (Google SRE): Latency, Traffic, Errors, Saturation.
- Alerting: avoid fatigue. Alert on symptoms (users affected), not causes. Actionable alerts only. Severity levels. PagerDuty, OpsGenie. On-call rotation.

---

## 8. Security

### 8.1 Application Security

**OWASP Top 10 Essentials**
- **Injection**: SQL, NoSQL, command, LDAP. Prevention: parameterized queries (ALWAYS), input validation, ORM (mostly safe), principle of least privilege for DB user.
- **Broken Authentication**: weak passwords, credential stuffing, session fixation. Prevention: bcrypt/argon2 (NEVER MD5/SHA for passwords), MFA, account lockout with progressive delay, secure session management.
- **XSS (Cross-Site Scripting)**: inject malicious scripts. Stored (database), reflected (URL), DOM-based (client-side). Prevention: output encoding (context-aware: HTML, JS, URL, CSS), Content Security Policy headers, `HttpOnly` cookies.
- **CSRF (Cross-Site Request Forgery)**: trick authenticated user into making unwanted request. Prevention: CSRF tokens (Django has built-in), SameSite cookies, check Origin/Referer headers.
- **Broken Access Control**: accessing resources without authorization, privilege escalation. Prevention: deny by default, server-side validation, don't rely on client-side checks, test authorization for every endpoint.
- **Security Misconfiguration**: default credentials, unnecessary features enabled, verbose error messages in production, missing security headers. Prevention: hardening checklist, automated scanning, security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP).
- **Insecure Deserialization**: manipulated serialized objects execute code. Prevention: don't deserialize untrusted data, use safe formats (JSON over pickle), integrity checks, input validation.

**Input Validation & Security Headers**
- Whitelist validation: define what's allowed, reject everything else. More secure than blacklist.
- Parameterized queries: `cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))`. NEVER: `f"SELECT * FROM users WHERE id = {user_id}"`.
- Security headers: `Strict-Transport-Security` (HSTS, force HTTPS), `Content-Security-Policy` (restrict resource loading), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 0` (use CSP instead).
- CORS: `Access-Control-Allow-Origin` (specific origins, not `*` for credentialed requests), `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`. Preflight requests (OPTIONS).
- File upload: validate type (magic bytes, not just extension), limit size, store outside webroot, generate random filenames, scan for malware, serve from separate domain/CDN.
- Rate limiting for security: login attempts, password reset, API endpoints. IP-based + account-based.

### 8.2 Infrastructure Security

**Secrets Management**
- HashiCorp Vault: dynamic secrets (short-lived, auto-rotated), encryption as a service, PKI, secret engines. Policies for access control. Audit logging.
- AWS Secrets Manager / Parameter Store: managed secret storage. Auto-rotation for RDS passwords. IAM-based access control.
- Environment variables: 12-factor app config. Never commit to git. `.env` files for local development only (in `.gitignore`).
- Secret detection: `detect-secrets` (pre-commit hook), `trufflehog` (git history scanning), `gitleaks`. Prevent accidental commits.
- Encryption: at rest (AES-256, KMS-managed keys), in transit (TLS 1.2+). Application-level encryption for sensitive fields. Key rotation.

**Compliance & Best Practices**
- GDPR: data minimization, consent management, right to erasure, data portability, breach notification (72h), DPO requirement. Technical: encryption, pseudonymization, audit trails, data retention policies.
- Dependency scanning: Dependabot (GitHub), Snyk, Safety (Python). Automated PRs for vulnerable dependencies. Pin versions. Audit regularly.
- Penetration testing: regular testing (annual minimum). OWASP testing guide. Automated SAST (static analysis) and DAST (dynamic analysis) in CI.
- Zero-trust: never trust, always verify. Identity-based access. Microsegmentation. Continuous authentication. Principle of least privilege everywhere.

---

## 9. Testing Strategy

### 9.1 Testing Pyramid

**Unit Tests**
- Test single unit in isolation. Mock external dependencies (database, APIs, filesystem). Fast execution (<1s per test). High coverage of business logic.
- Arrange-Act-Assert (AAA) pattern: setup, execute, verify. One assertion concept per test. Descriptive names: `test_expired_coupon_raises_validation_error`.
- Edge cases: empty inputs, null/None, boundary values, very large inputs, special characters, Unicode, concurrent access.
- Property-based testing (Hypothesis): define properties that must hold for all inputs. Framework generates random inputs. Finds edge cases you'd never think of. Shrinks to minimal failing example.

**Integration Tests**
- Test component interactions with real dependencies. Real database (testcontainers for Docker-based test databases), real Redis, real message queue.
- API tests: real HTTP requests to test endpoint. Test request validation, serialization, authentication, authorization.
- Database tests: test migrations, queries, constraints, triggers. Transaction rollback for test isolation (`pytest-django` TransactionTestCase).
- Test doubles: stubs (return canned data), mocks (verify interactions), fakes (working lightweight implementation), spies (record calls).

**Performance Testing**
- Load testing: simulate expected traffic. Locust (Python, distributed), k6 (JavaScript, modern), JMeter (Java, GUI).
- Types: load (expected traffic), stress (beyond capacity, find breaking point), soak/endurance (sustained load, detect memory leaks), spike (sudden burst).
- Metrics: response time (p50, p95, p99), throughput (req/s), error rate, resource usage (CPU, memory, connections).
- Benchmarking: establish baseline. Test after changes. Automated performance regression detection in CI.

### 9.2 Testing Practices

**Test Design Principles**
- F.I.R.S.T.: Fast, Independent (no test depends on another), Repeatable (same result every time), Self-validating (pass/fail, no manual inspection), Timely (written alongside code).
- Test coverage: branch coverage > line coverage (catches more logic paths). 80% is a good target. 100% is often waste (diminishing returns). Coverage measures tested, not correctness.
- Test data: factory_boy (declarative test data factories), Faker (realistic fake data). Avoid fixtures/JSON dumps (brittle, hard to maintain).
- Mutation testing: modify code and verify tests catch it. mutmut (Python). Measures test quality, not just coverage.
- Contract testing: Pact. Verify service APIs meet consumer expectations without running all services. Consumer-driven contract testing.

---

## 10. Senior / Architect Mindset

### 10.1 Technical Leadership

**Architecture Decision Records (ADR)**
- Document WHY, not just WHAT. Context (problem, constraints), Decision (what was chosen), Consequences (trade-offs, risks). Short, versioned, reviewable.
- Prevents re-litigation of old decisions. New team members understand historical context. Lightweight format (~1 page per decision).
- Template: Title, Date, Status (proposed/accepted/deprecated), Context, Decision, Consequences.

**Technical Debt Management**
- Classify: reckless/deliberate ("we don't have time for design"), reckless/inadvertent ("what's layering?"), prudent/deliberate ("ship now, refactor later"), prudent/inadvertent ("now we know how we should have done it").
- Quantify impact: developer velocity, incident frequency, onboarding time, feature delivery time. Communicate in business terms.
- Strategies: Boy Scout Rule (leave code better than you found it), dedicated debt sprints, debt tax (20% of sprint capacity), tech debt backlog.
- When to rewrite vs refactor: rewrite only when current architecture fundamentally can't support requirements AND team understands domain well AND there's business justification. Refactoring is almost always safer.

**Code Review Excellence**
- Review for: correctness (does it work?), design (is it well-structured?), readability (can others understand it?), testability, security, performance. Automate style checks (don't nitpick in review).
- Constructive feedback: explain why, suggest alternatives, ask questions rather than dictate. "Have you considered X?" vs "Do X." Praise good code.
- Size: small PRs reviewed better. <400 lines of meaningful changes. Break large changes into stacked PRs.

### 10.2 System Thinking

**Trade-off Analysis Framework**
- Every decision has trade-offs. Document: What are we optimizing for? What are we sacrificing? What's the reversibility?
- Common trade-offs: consistency vs availability, latency vs throughput, simplicity vs flexibility, speed of delivery vs code quality, build vs buy, monolith vs microservices.
- Evaluation matrix: score options on criteria (performance, maintainability, team familiarity, cost, time to implement). Weight by importance. Not scientific, but structured.
- Reversibility: prefer reversible decisions (two-way doors). Invest more time in irreversible ones (one-way doors). Database schema, public API contracts, architectural style are hard to reverse.

**Back-of-Envelope Estimation**
- Know your numbers: QPS, data volume, storage, bandwidth. 1 day = 86,400 seconds ≈ 100K seconds. 1 million requests/day ≈ 12 req/s.
- Storage: 1 billion records × 1KB = 1TB. Plan for 3-5 years growth. Replication factor.
- Latency: memory access ~100ns, SSD read ~100μs, network round-trip ~1ms, disk seek ~10ms. These dominate system design decisions.
- Powers of 2: 2^10 ≈ 1K, 2^20 ≈ 1M, 2^30 ≈ 1B, 2^40 ≈ 1T.

**Incident Management**
- Process: detect → triage → mitigate → resolve → postmortem. Clear roles: incident commander, communication lead, technical lead.
- On-call: rotation schedule (weekly or bi-weekly). Escalation paths. Runbooks for common issues. Alert → runbook → resolution.
- Blameless postmortem: what happened (timeline), why (root cause analysis, 5 Whys), how to prevent (action items with owners and deadlines). Share widely. Focus on systems, not individuals.
- Incident classification: SEV1 (critical, customer-facing, all hands), SEV2 (major degradation), SEV3 (minor issue), SEV4 (cosmetic). SLA for response time per severity.

**Technology Evaluation**
- ThoughtWorks Technology Radar model: Adopt (proven, use on appropriate projects), Trial (worth pursuing, use on pilot project), Assess (worth exploring, understand impact), Hold (proceed with caution).
- Evaluation criteria: maturity, community size, documentation quality, maintenance activity, license, security track record, migration path, team skill gap.
- Proof of concept: time-boxed (1-2 weeks). Test specific hypotheses. Realistic workload. Document findings and decision. PoC is not MVP — it tests feasibility, not business value.

---

## 11. Django & Web Framework Knowledge (Framework-Aware, Principle-Focused)

### 11.1 Django Specifics (Transferable Concepts)

**Request/Response Lifecycle**
- Middleware chain: request → middleware stack → URL routing → view → response → middleware stack (reverse). Concepts: interceptor pattern, filter chain. Same in Flask (before/after request), FastAPI (middleware), Express (middleware). Understanding this helps you debug any web framework.
- URL routing: mapping URLs to handlers. Django: URL patterns → views. REST frameworks add resource-based routing. Concepts: route matching, path parameters, query parameters, reverse URL resolution.

**ORM & Database Layer**
- Django ORM: Active Record pattern (model instances know how to save themselves). SQLAlchemy: Data Mapper pattern (separate mapper layer). Know the difference and when each fits.
- Migration system: declarative schema changes, dependency tracking, auto-generation from model changes. Concepts apply to: Alembic (SQLAlchemy), Flyway (Java), Knex (Node.js). Key principle: migrations are versioned database schema changes.
- QuerySet evaluation: lazy evaluation (build query, execute on iteration). `.select_related()` and `.prefetch_related()` solve N+1. Manager pattern for custom querysets.

**Signals & Events**
- Django signals: observer pattern. `pre_save`, `post_save`, `pre_delete`, `post_delete`, `request_started`, `request_finished`. Decoupling, but can create hidden dependencies. Use sparingly. Prefer explicit service calls for important logic.
- Transferable: event hooks in Flask, FastAPI events, middleware hooks. Event-driven patterns in any framework.

**Admin & Rapid Development**
- Django admin: auto-generated CRUD interface. Custom admin classes, filters, actions. Quick internal tools. Concept: scaffolding / auto-generated interfaces (Rails scaffold, Laravel Nova).

### 11.2 Web Framework-Agnostic Patterns

**Middleware / Interceptors**
- Cross-cutting concerns: logging, authentication, CORS, compression, rate limiting, request ID injection. Same concept across all frameworks. Implement as decorators, middleware, or interceptors.
- Order matters: authentication before authorization before business logic. Logging/tracing at outermost layer.

**Request Validation**
- Input validation at the boundary. Pydantic (FastAPI native), Django REST Framework serializers, marshmallow, cerberus. Validate early, fail fast. Structured error responses.
- Serialization/deserialization: converting between wire format (JSON) and internal representation. Schema definitions. Versioning.

**Background Task Processing**
- Celery: de facto Python task queue. But concepts are universal: task definition, serialization, routing, retry, dead letter, monitoring. Alternatives: Dramatiq, Huey, rq, Arq (async).
- Task design: idempotent, small, quick (break large work into subtasks), include all needed data in task payload (not just IDs that might be deleted).

**Caching Layer**
- Django cache framework: cache backends (Redis, Memcached, file, database). Per-view caching, template fragment caching, low-level cache API. Concepts: cache keys, TTL, invalidation, cache stampede prevention.
- Cache patterns are framework-agnostic. Same strategies in any web framework.

**Template / Rendering Layer**
- Server-side rendering: Django templates, Jinja2. MVC/MVT pattern. Template inheritance, context processors.
- API-only backends: JSON serialization, content negotiation, HATEOAS. Most modern backends are API-only.

---

## 12. Soft Skills & Career Growth

### 12.1 Communication

**Technical Writing**
- RFC / Design Document: problem statement, proposed solution, alternatives considered, trade-offs, rollout plan, metrics for success. Get feedback before implementation.
- README: what it does, how to run it, how to contribute. Keep updated. First impression of your project.
- Runbooks: step-by-step operational procedures. Include: symptoms, diagnosis steps, remediation, escalation. Tested and updated after incidents.
- ADRs: lightweight, version-controlled, searchable. Living documentation of architectural decisions.

**Stakeholder Communication**
- Translate technical concepts to business impact. "Database migration" → "30 minutes of read-only mode for users."
- Estimate honestly. Include uncertainty ranges. "2-4 weeks" is better than "3 weeks."
- Say no constructively. Explain trade-offs. Offer alternatives. "We can do X quickly, but Y would be more sustainable."

### 12.2 Career Progression

**Mid → Senior**
- Own features end-to-end (design → implement → deploy → monitor). Anticipate edge cases. Consider operational impact. Write tests. Document decisions.
- Debug systematically (hypothesize → test → narrow down). Read source code of libraries/frameworks you use. Understand abstraction layers.
- Mentor juniors. Share knowledge. Code review as teaching tool.

**Senior → Architect**
- Think in systems, not features. Understand how components interact. Non-functional requirements (scalability, reliability, security, cost).
- Make technology choices with full context (team skills, timeline, maintenance burden, migration path).
- Influence without authority. Build consensus. Navigate organizational dynamics.
- Balance ideal architecture with pragmatic delivery. Perfect is the enemy of good. Iterate.
- Define technical vision and roadmap. Communicate clearly to technical and non-technical stakeholders.

---

*This is a living document. Depth in any single topic could fill a book — use this as a map of what to learn, not a substitute for deep study. Focus on principles over specific tools; frameworks change, fundamentals don't.*
