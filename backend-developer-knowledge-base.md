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
- Cache locality matters more than asymptotics at small n: a linear scan over a contiguous array often beats an O(log n) pointer-chasing structure because of prefetching and fewer cache misses. "Big-O isn't everything" — constant factors and memory layout dominate for small-to-medium n.

**Hash Tables**
- Hash function properties: deterministic, uniform distribution, fast computation. Collision resolution: separate chaining (linked list per bucket), open addressing (linear probing, quadratic probing, double hashing).
- Load factor = n/k. Rehashing when load factor exceeds threshold (~0.75). Amortized O(1) for insert/lookup/delete.
- Python `dict` internals: compact dict (since 3.6, insertion order preserved). Open addressing with perturbation. Key sharing for instance dicts (__dict__).
- `collections.OrderedDict` (doubly-linked list + dict), `defaultdict`, `Counter`.
- Consistent hashing for distributed systems (virtual nodes, minimal key redistribution on node add/remove). Used in load balancers, distributed caches, database sharding.
- Cuckoo hashing: two hash functions, each key lives in one of two possible buckets. Worst-case O(1) lookup (check two locations). Inserts may "kick out" existing keys (cuckoo behavior); high load factors can trigger rehash cycles. Used where predictable lookup latency matters.
- Hash flooding (algorithmic complexity attack): adversary crafts keys that all collide, degrading O(1) to O(n). Mitigation: randomized hash seeds (Python enables `PYTHONHASHSEED` randomization for str/bytes by default). Relevant for any service that hashes untrusted input.

**Trees**
- Binary Search Tree: O(log n) average for search/insert/delete, O(n) worst case (degenerate/skewed).
- Self-balancing BSTs: AVL (strict balance, faster lookups), Red-Black (relaxed balance, faster inserts/deletes). Used in language standard libraries (C++ std::map, Java TreeMap).
- B-Trees & B+ Trees: designed for disk-based storage. High branching factor minimizes disk reads. B+ trees store data only in leaves with linked leaf nodes for range scans. Foundation of database indexes (PostgreSQL, MySQL InnoDB).
- Heap: complete binary tree, O(1) min/max access, O(log n) insert/extract. Used for priority queues, task schedulers, Dijkstra's algorithm. Python `heapq` (min-heap; negate values or use tuples `(priority, item)` for max-heap or custom ordering).
- Trie (prefix tree): O(m) lookup where m = key length. Used for autocomplete, IP routing tables, spell checkers. Compressed trie (radix tree) for memory efficiency.
- Segment trees for range queries (sum, min, max over intervals). Fenwick tree (Binary Indexed Tree) for prefix sums with updates. Both useful in analytics and time-series.

**LSM-Trees & Write-Optimized Structures**
- Log-Structured Merge tree: optimized for write-heavy workloads. Writes go to an in-memory `memtable` (sorted, e.g., skip list or red-black tree) plus a write-ahead log for durability. When the memtable fills, it's flushed to disk as an immutable, sorted SSTable (Sorted String Table).
- Reads check the memtable, then SSTables newest-to-oldest; Bloom filters per SSTable skip files that definitely don't contain the key. Compaction merges SSTables in the background to reclaim space and bound read amplification.
- Write amplification (data rewritten during compaction), read amplification (files checked per read), space amplification (extra disk used). LSM tuning is about balancing these three.
- LSM (Cassandra, RocksDB, LevelDB, ScyllaDB) favors sequential writes and high write throughput; B-trees (PostgreSQL, InnoDB) favor read-heavy and in-place update workloads. Knowing which engine your database uses explains its performance profile.

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
- Bloom filter: probabilistic set membership. O(k) lookup with k hash functions. False positives possible, false negatives impossible. Used in databases (avoid unnecessary disk reads), web caching, spam filtering. Counting Bloom filter for deletion support. Cuckoo filter as a modern alternative (supports deletion, better locality).
- HyperLogLog: cardinality estimation with O(1) space. Count distinct elements in a stream with <2% error using ~12KB. Used in Redis, analytics systems (unique visitors).
- LRU cache: hash map + doubly-linked list. O(1) get/put. `functools.lru_cache` in Python. LFU cache: frequency-based eviction (more complex, heap + hash maps).
- Disjoint Set / Union-Find: near O(1) amortized with path compression + union by rank. Applications: Kruskal's MST, network connectivity, image segmentation.
- Rope: balanced binary tree of strings for efficient text editing (insert, delete, concatenate on large strings).
- Count-Min Sketch: probabilistic frequency estimation for streaming data. Used in network monitoring, NLP.
- Merkle tree (hash tree): tree of hashes where each leaf is the hash of a data block and each internal node hashes its children. The root hash certifies the whole dataset. Enables efficient verification of which blocks changed (O(log n) proof). Used in Git (commit/tree objects), Bitcoin/blockchains, anti-entropy repair in Cassandra/DynamoDB, IPFS, and content-addressable storage.

### 1.2 Algorithms & Complexity

**Big-O Analysis**
- Time and space complexity. Learn to identify: O(1) constant, O(log n) binary search/balanced tree ops, O(n) linear scan, O(n log n) efficient sorts, O(n²) nested loops, O(2ⁿ) brute-force subsets, O(n!) permutations.
- Amortized analysis: average cost per operation over a sequence (e.g., dynamic array resizing is amortized O(1) for append despite occasional O(n) copy).
- Best/average/worst case distinction. Quicksort: O(n log n) average, O(n²) worst. Hash table: O(1) average, O(n) worst.
- Space-time tradeoffs: caching (trade space for time), streaming algorithms (trade accuracy for space), precomputation (trade startup time for query time).
- Master theorem for divide-and-conquer recurrences: T(n) = aT(n/b) + O(nᵈ). Compare d against log_b(a): smaller → O(n^log_b a), equal → O(nᵈ log n), larger → O(nᵈ).

**Algorithmic Techniques (Problem-Solving Patterns)**
- Two pointers: process a sequence with two indices moving toward/with each other. Pair-sum in sorted arrays, removing duplicates, partitioning, palindrome checks. O(n) instead of O(n²).
- Sliding window: maintain a moving range over a sequence, expanding/contracting to satisfy a constraint. Longest substring without repeats, max sum subarray of size k, rate-limiting windows. Fixed vs variable window.
- Binary search on the answer: when the answer is monotonic ("can we do it with budget X?"), binary-search over X rather than the array. Used in capacity planning, "minimum max load" problems, allocation.
- Backtracking: build candidates incrementally, abandon ("prune") partial solutions that can't succeed. Permutations, combinations, N-queens, sudoku, constraint satisfaction.
- Greedy: make the locally optimal choice at each step. Works only when the problem has the greedy-choice property + optimal substructure (interval scheduling, Huffman coding, Dijkstra). Easy to apply incorrectly — prove it or test against brute force.
- Divide and conquer: split, solve subproblems, combine (merge sort, quickselect, FFT, Karatsuba multiplication).
- Bit manipulation: masks, `x & (x-1)` (clear lowest set bit), `x & -x` (isolate lowest set bit), XOR tricks (find the single non-duplicated element), bitsets for compact boolean arrays, permission flags.

**Sorting**
- Comparison-based sorts (lower bound Ω(n log n)): Quicksort (in-place, cache-friendly, O(n log n) average), Mergesort (stable, O(n log n) guaranteed, needs O(n) extra space), Heapsort (in-place, O(n log n) guaranteed, poor cache locality).
- Non-comparison sorts: Counting sort (O(n+k), integer keys), Radix sort (O(d(n+k)), fixed-length keys), Bucket sort (O(n) average for uniform distribution).
- When stability matters: preserving relative order of equal elements. Important for multi-key sorts, database ordering.
- External sorting: merge sort variant for data larger than RAM. Used in database query processing, large file sorting.
- Python: Timsort (hybrid merge+insertion sort, stable, adaptive). `sorted()` returns new list, `.sort()` in-place. Key functions for custom ordering. `functools.cmp_to_key` to adapt old-style comparators.

**Selection & Order Statistics**
- Quickselect: find the k-th smallest element in O(n) average (partition like quicksort but recurse into one side only). Median, top-k, percentiles.
- Heap-based top-k: maintain a size-k heap while streaming, O(n log k). `heapq.nlargest`/`nsmallest`. Better than full sort when k ≪ n.

**Dynamic Programming**
- Two properties: overlapping subproblems (same subproblems solved repeatedly) and optimal substructure (optimal solution contains optimal sub-solutions).
- Top-down (memoization): recursive with cache. Bottom-up (tabulation): iterative, fill table.
- Classic patterns: 0/1 knapsack (resource allocation), longest common subsequence (diff algorithms), edit distance (spell check, DNA alignment), coin change, matrix chain multiplication.
- State machine DP: model problem as state transitions (e.g., stock trading with cooldown).
- Bitmask DP: represent subset states as bitmasks for small n (traveling salesman, set cover).
- Practical uses: rate limiting sliding windows, resource allocation, route optimization, text wrapping algorithms (the Knuth-Plass line-breaking algorithm).

**Graph Algorithms (Extended)**
- Floyd-Warshall: all-pairs shortest path, O(V³). Good for small dense graphs, detects negative cycles.
- Network flow: Ford-Fulkerson, Edmonds-Karp. Applications: maximum bipartite matching, project selection, image segmentation. Min-cut/max-flow duality.
- Eulerian path/circuit: visiting every edge exactly once. Applications: DNA assembly, circuit design.
- Union-Find for connectivity: dynamic connectivity, detecting cycles in undirected graphs incrementally.

**String Algorithms**
- KMP (Knuth-Morris-Pratt): pattern matching in O(n+m). Failure function for prefix matching.
- Rabin-Karp: rolling hash for multi-pattern matching. Used in plagiarism detection.
- Aho-Corasick: multiple pattern matching simultaneously. Used in intrusion detection, content filtering.
- Suffix array / suffix tree: O(n) construction, powerful for substring queries. Used in bioinformatics, full-text search.
- Levenshtein / edit distance: fuzzy matching, spell correction, diff tools.

**Randomized & Streaming Algorithms**
- Reservoir sampling: select k random items from a stream of unknown length in O(n) time, O(k) space, each item equally likely. Used for log sampling, A/B bucketing, telemetry.
- Misra-Gries / heavy hitters: find elements occurring more than n/k times in a stream with bounded memory. Network "top talkers", trending detection.
- Randomized algorithms trade determinism for simplicity/speed: randomized quicksort pivot (avoids worst case on sorted input), Monte Carlo (fixed time, probabilistic correctness) vs Las Vegas (always correct, probabilistic time).

### 1.3 Operating Systems

**Processes & Threads**
- Process: independent memory space, isolation, heavier context switch (~1-10μs). Thread: shared memory within process, lighter context switch. Coroutine: cooperative multitasking, user-space scheduling, cheapest (~100ns switch).
- Process states: new → ready → running → waiting → terminated. Context switch saves/restores registers, program counter, stack pointer.
- IPC mechanisms: pipes (unidirectional byte stream), named pipes (FIFO), message queues (structured messages), shared memory (fastest, needs synchronization), Unix domain sockets (bidirectional, same host), signals (async notifications).
- Copy-on-write (COW) fork: parent and child share pages until write. Efficient for fork-exec pattern. Used by Redis for background saves.
- Green threads / user-space threads: managed by runtime, not OS. Python's asyncio coroutines, Go's goroutines. M:N threading model.
- Zombie & orphan processes: a zombie has exited but its parent hasn't `wait()`ed to reap the exit status (occupies a PID table entry); an orphan's parent died and it's re-parented to init/PID 1. Matters for long-running daemons and PID-1 behavior in containers (use `tini`/`--init` so signals and reaping work).

**CPU Architecture & Caches**
- Memory hierarchy (approximate latencies): register (<1ns) → L1 cache (~1ns) → L2 (~4ns) → L3 (~10-20ns) → main memory (~100ns) → SSD (~100μs) → spinning disk (~10ms). Each level is larger and slower. Performance work is largely about keeping hot data in fast levels.
- Cache lines: memory is fetched in fixed blocks (typically 64 bytes). Accessing one byte loads the whole line. Sequential access is cheap (prefetching); random access thrashes the cache.
- False sharing: two threads modifying different variables that happen to live on the same cache line invalidate each other's caches, killing performance. Pad/align hot per-thread data to separate cache lines.
- NUMA (Non-Uniform Memory Access): on multi-socket servers, each CPU has faster access to its local memory bank. Cross-socket access is slower. Pin threads/memory (`numactl`, thread affinity) for latency-sensitive workloads.
- Branch prediction & speculative execution: the CPU guesses branch outcomes to keep the pipeline full; mispredictions cost ~10-20 cycles. Predictable, sorted data branches faster (a famous reason sorted input can speed up a loop). Side-channel attacks (Spectre/Meltdown) exploit speculation.

**Memory Management**
- Virtual memory: each process sees contiguous address space. Page table maps virtual → physical addresses. Page size typically 4KB, huge pages (2MB/1GB) reduce TLB misses.
- TLB (Translation Lookaside Buffer): cache for page table entries. TLB miss triggers page table walk. Huge pages improve TLB hit rate for large working sets.
- Stack: automatic allocation, LIFO, function call frames (local variables, return address). Default stack size ~8MB on Linux. Stack overflow on deep recursion.
- Heap: dynamic allocation (malloc/free, Python object allocation). Fragmentation over time. Memory allocators: glibc malloc, jemalloc (used by Redis, Rust), tcmalloc.
- Python memory: reference counting (immediate cleanup) + generational garbage collector (handles cycles). Three generations: gen0 (new objects, collected frequently), gen1, gen2 (long-lived, collected rarely). `gc.collect()` to force. `gc.disable()` for latency-sensitive code.
- Memory-mapped files (mmap): map file into virtual address space. Lazy loading, shared between processes. Used for large file processing, shared memory IPC, database page caches.
- OOM killer: Linux kernel kills process with highest OOM score when memory exhausted. `oom_score_adj` to influence selection. Cgroups for memory limits per container.
- Monitoring: `RSS` (Resident Set Size, actual physical memory), `VSZ` (Virtual Size, total mapped). `top`, `htop`, `smem`, `/proc/[pid]/status`.
- Page faults: minor (page in memory, just not mapped to this process — cheap) vs major (page must be read from disk — expensive). High major-fault rates indicate memory pressure / swapping. Thrashing: system spends more time swapping than working.

**Concurrency & Synchronization Primitives**
- Race condition: outcome depends on unpredictable interleaving of operations on shared state. Critical section: code that must not run concurrently.
- Mutex (mutual exclusion lock): only one thread holds it at a time. Lock/unlock around the critical section. Must be released on every path (use context managers / RAII).
- Semaphore: counter allowing up to N concurrent holders. Binary semaphore ≈ mutex. Used to bound concurrency (connection limits, worker pools).
- Condition variable: lets a thread wait until some predicate becomes true, woken by another thread's `notify()`. Always re-check the predicate in a `while` loop (spurious wakeups).
- Spinlock: busy-waits instead of sleeping. Cheap for very short critical sections on multicore; wasteful otherwise. Futex (Linux): fast user-space path, falls back to kernel only on contention — the building block of pthread mutexes.
- Read-write lock: many concurrent readers OR one writer. Good for read-heavy shared state; risk of writer starvation.
- Atomic operations / CAS (compare-and-swap): lock-free updates using hardware instructions. Foundation of lock-free queues, reference counts, optimistic concurrency.
- Deadlock — the four Coffman conditions (all required): mutual exclusion, hold-and-wait, no preemption, circular wait. Break any one to prevent deadlock; the common fix is a global lock-ordering discipline. Livelock: threads keep changing state in response to each other but make no progress. Starvation: a thread never gets the resource.
- Priority inversion: a low-priority thread holds a lock a high-priority thread needs, while a medium-priority thread preempts the low one. Fix: priority inheritance. (Famously hit the Mars Pathfinder.)

**Scheduling**
- Preemptive (OS forcibly switches threads on a timer) vs cooperative (a task runs until it yields — asyncio, generators). Cooperative is simpler to reason about but one blocking task stalls everything.
- Linux CFS (Completely Fair Scheduler): allocates CPU proportionally via "virtual runtime"; threads that have run less get scheduled next. `nice` value (-20 to 19) biases the share. Real-time scheduling classes (SCHED_FIFO, SCHED_RR) for latency-critical work.
- Time slice / quantum, context-switch overhead, and why oversubscribing CPUs (too many busy threads) degrades throughput via context-switch thrash and cache pollution. Rule of thumb: CPU-bound pools ≈ number of cores; I/O-bound pools can be much larger.

**I/O Models**
- Blocking I/O: thread waits until operation completes. Simple but wastes threads. Thread-per-connection model.
- Non-blocking I/O: returns immediately (EAGAIN/EWOULDBLOCK). Application polls for readiness. Busy-waiting waste.
- I/O multiplexing: monitor multiple file descriptors. `select` (O(n), 1024 fd limit), `poll` (O(n), no fd limit), `epoll` (O(1) for events, Linux-specific, edge/level triggered), `kqueue` (BSD/macOS).
- epoll in detail: `epoll_create`, `epoll_ctl` (add/modify/remove), `epoll_wait`. Level-triggered (like poll) vs edge-triggered (notify only on state change, must drain completely). Edge-triggered is more efficient but harder to use correctly.
- Async I/O: `io_uring` (Linux 5.1+): submission queue + completion queue in shared memory, no syscalls needed after setup. Significantly reduces syscall overhead. Used by modern high-performance servers.
- Zero-copy: `sendfile()` sends file directly from kernel buffer to socket without copying to userspace. `splice()` for pipe-based zero-copy. Used for static file serving.
- Buffered I/O: kernel page cache. Write-back caching (write to cache, flush later). `fsync`/`fdatasync` for durability guarantees. Direct I/O (`O_DIRECT`) bypasses page cache for database engines that manage their own buffer pool.
- The C10K → C10M problem: handling tens of thousands to millions of concurrent connections is why event-driven (epoll/kqueue) and async architectures exist — thread-per-connection doesn't scale to that level.

**File Systems**
- Inodes: metadata (permissions, timestamps, data block pointers). File descriptors: per-process integer handles to kernel file objects. fd limits (`ulimit -n`, `/proc/sys/fs/file-max`).
- Page cache: kernel caches file data in memory. Read-ahead for sequential access. Dirty pages written back asynchronously. `sync`, `fsync` to flush.
- Journaling: ext4 journal records metadata changes before applying. Prevents corruption on crash. Full journaling (data+metadata) vs ordered mode (metadata only, data written first).
- Common filesystems: ext4 (Linux default, journaling, extents), XFS (large files, parallel I/O), ZFS (checksums, snapshots, compression), tmpfs (RAM-backed, /tmp), overlayfs (Docker layers).
- Disk I/O patterns: sequential reads/writes much faster than random (especially HDDs). SSDs reduce random I/O penalty but sequential still faster. IOPS vs throughput. I/O scheduler: noop/none for SSDs, deadline/mq-deadline for HDDs.
- Hard links (multiple directory entries → same inode) vs symlinks (a file pointing at a path). Atomic file replacement: write to temp file + `rename()` (atomic on the same filesystem) — the safe way to update a config/data file without a partial-write window.

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
- Load average: the 1/5/15-minute exponentially-weighted count of runnable + uninterruptible (D-state) processes. On Linux, high load with low CPU often means I/O wait, not CPU saturation. Always interpret against core count.
- Permissions model: user/group/other rwx, setuid/setgid/sticky bits, `umask`. Capabilities (`CAP_NET_BIND_SERVICE`, etc.) for fine-grained privilege instead of full root.

### 1.4 Networking

**The Layered Model & Lower Layers**
- OSI vs TCP/IP model: link (Ethernet/MAC) → internet (IP) → transport (TCP/UDP) → application (HTTP/DNS/etc.). Encapsulation: each layer wraps the layer above with its own header.
- IP addressing: IPv4 (32-bit, dotted quad) vs IPv6 (128-bit, hex). Private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) vs public. Loopback (127.0.0.1/::1). Link-local.
- CIDR & subnetting: `/24` = 256 addresses (254 usable), `/16` = 65,536. The prefix length is how many leading bits are the network portion. Essential for VPC/subnet design and security-group/firewall rules.
- ARP (Address Resolution Protocol): maps IP → MAC address on a local network. ICMP: control/diagnostic messages (ping, traceroute, "destination unreachable", "fragmentation needed").
- NAT (Network Address Translation): maps many private addresses to one public address (port translation). Why most devices aren't directly reachable from the internet; relevant to outbound-only patterns, hole-punching, and why inbound webhooks need a public endpoint.
- Routing & BGP: the internet is autonomous systems exchanging routes via BGP. Anycast: one IP announced from many locations; routing sends clients to the nearest — the backbone of CDNs, public DNS (8.8.8.8), and DDoS absorption.

**TCP/IP Deep Dive**
- 3-way handshake: SYN → SYN-ACK → ACK. Connection establishment adds 1 RTT latency. SYN flood attack and SYN cookies defense.
- Flow control: sliding window. Receiver advertises window size (rwnd). Sender cannot send more than min(cwnd, rwnd).
- Congestion control: slow start (exponential growth), congestion avoidance (linear growth, AIMD). ssthresh. Modern: CUBIC (Linux default), BBR (Google, bandwidth-based).
- TCP_NODELAY: disables Nagle's algorithm (buffers small packets). Important for low-latency applications (real-time, interactive). Usually combine with TCP_QUICKACK.
- TIME_WAIT: 2MSL (typically 60s) after connection close. Prevents delayed packets from previous connection affecting new one. Can exhaust ports on high-traffic servers. `SO_REUSEADDR`, `SO_REUSEPORT`, `net.ipv4.tcp_tw_reuse`.
- Keep-alive: periodic probes to detect dead connections. `SO_KEEPALIVE`, configure with `tcp_keepalive_time`, `tcp_keepalive_intvl`, `tcp_keepalive_probes`. Application-level heartbeats are more reliable.
- Socket buffer tuning: `SO_SNDBUF`, `SO_RCVBUF`. Auto-tuning (`net.ipv4.tcp_rmem`, `tcp_wmem`). BDP (bandwidth-delay product) determines optimal buffer size.
- TCP vs UDP: TCP for reliability (HTTP, database connections). UDP for low latency, multicast, or when application handles reliability (video streaming, DNS, game networking, QUIC).
- Head-of-line blocking: in TCP, one lost segment stalls everything behind it (in-order delivery). This motivates HTTP/3 over QUIC, which gives independent streams.

**Socket Programming Basics**
- The Berkeley sockets lifecycle — server: `socket()` → `bind()` → `listen()` → `accept()` (returns a new connected socket per client) → `recv()`/`send()` → `close()`. Client: `socket()` → `connect()` → `send()`/`recv()` → `close()`.
- A socket is identified by the 4-tuple (src IP, src port, dst IP, dst port); this is why one server port can hold many simultaneous connections.
- TCP is a byte stream, not a message protocol: a single `recv()` may return part of a message or several messages glued together. You must frame messages yourself (length prefix, delimiter, or a higher protocol). This "message framing" bug bites everyone once.
- Backlog queue (`listen(backlog)`), the accept loop, and why blocking accept loops led to thread-per-connection, then to epoll/async designs.

**HTTP Protocol**
- HTTP/1.1: persistent connections (Connection: keep-alive), pipelining (rarely used due to head-of-line blocking), chunked transfer encoding.
- HTTP/2: binary framing layer. Multiplexing (multiple streams over single connection, no HOL blocking at HTTP level). HPACK header compression. Server push. Stream priorities. Still has TCP HOL blocking.
- HTTP/3: QUIC protocol (UDP-based). Independent streams (no TCP HOL blocking). 0-RTT connection resumption. Connection migration (IP changes). Built-in TLS 1.3. Better for lossy networks.
- Methods & semantics: safe methods (GET, HEAD — no side effects), idempotent methods (GET, PUT, DELETE, HEAD), and non-idempotent (POST, PATCH). Conditional requests (`If-Match`, `If-None-Match`) for optimistic concurrency and cache validation.
- Caching headers: `Cache-Control` (max-age, no-cache, no-store, public, private, s-maxage), `ETag` (content hash for conditional requests), `Last-Modified`/`If-Modified-Since`, `Vary` (cache key includes specified headers).
- Content negotiation: `Accept` (media type), `Accept-Encoding` (compression: gzip, br, zstd), `Accept-Language`.
- Important headers: `X-Request-Id` (tracing), `X-Forwarded-For` (real client IP behind proxy), `Strict-Transport-Security` (HSTS), `Content-Security-Policy`.
- Cookies: `Set-Cookie` attributes — `HttpOnly` (no JS access), `Secure` (HTTPS only), `SameSite` (Lax/Strict/None — CSRF defense), `Domain`/`Path`, `Max-Age`/`Expires`.

**Proxies, Gateways & Load Balancers**
- Forward proxy: sits in front of clients, makes requests on their behalf (corporate egress, caching, anonymity). Reverse proxy: sits in front of servers, terminates client connections and forwards to backends (nginx, Envoy, HAProxy) — handles TLS termination, caching, compression, load balancing.
- API gateway: an application-aware reverse proxy that also does auth, rate limiting, request routing/aggregation, and protocol translation. Single entry point for many backend services.
- Tunneling and `CONNECT`: how proxies pass through TLS; why `X-Forwarded-For`/`Forwarded` headers and PROXY protocol exist (to preserve the real client IP through layers). Trusting these headers blindly is a spoofing risk — only honor them from known proxies.

**DNS**
- Recursive resolution: client → recursive resolver → root → TLD → authoritative nameserver. Caching at every level.
- Record types: A (IPv4), AAAA (IPv6), CNAME (alias, can't coexist with other records at zone apex), MX (mail), TXT (verification, SPF, DKIM), SRV (service discovery with port+priority), NS (nameserver delegation), PTR (reverse DNS), CAA (certificate authority authorization).
- TTL strategies: low TTL (30-300s) for services that need fast failover, high TTL (3600-86400s) for stable records to reduce DNS load. Pre-warm DNS before TTL changes for migrations.
- DNS-based load balancing: round-robin A records (simple but uneven), weighted records (Route53), GeoDNS (latency-based routing), health-checked failover.
- Split-horizon DNS: different responses for internal vs external queries. Used for accessing services via internal IPs within a network.
- DNSSEC: cryptographic signing of DNS records. Chain of trust from root. Prevents DNS spoofing/poisoning. DS, DNSKEY, RRSIG records.
- Common production gotcha: client-side DNS caching (and JVM/connection-pool caching) means low TTLs don't always take effect quickly during failover; some clients cache forever unless configured.

**TLS/SSL**
- TLS 1.3 handshake: 1-RTT (down from 2-RTT in TLS 1.2). Removed insecure ciphers. 0-RTT resumption (with replay risk). Only supports AEAD ciphers (AES-GCM, ChaCha20-Poly1305).
- Certificate chain: leaf cert → intermediate cert(s) → root CA. Servers must send full chain (minus root). Certificate pinning for mobile apps.
- mTLS (mutual TLS): both client and server present certificates. Used for service-to-service authentication in microservices. SPIFFE/SPIRE for workload identity.
- OCSP stapling: server fetches and caches certificate revocation status, sends to client. Eliminates client-side OCSP lookup latency and privacy concerns.
- Let's Encrypt automation: ACME protocol. HTTP-01 challenge (prove domain control via HTTP), DNS-01 challenge (prove via DNS TXT record, supports wildcards). Auto-renewal with certbot or similar.
- SNI (Server Name Indication): client sends requested hostname in TLS handshake. Allows multiple TLS sites on single IP. Encrypted Client Hello (ECH) hides the SNI from observers.

**Network Debugging**
- `tcpdump`: packet capture. `tcpdump -i any port 443 -w capture.pcap`. Filters: host, port, protocol. Essential for debugging connection issues.
- `Wireshark`: GUI packet analysis. Follow TCP streams, decode protocols, statistics.
- `curl`: HTTP client. `-v` verbose, `-I` headers only, `--resolve` DNS override, `-w` timing stats (%{time_connect}, %{time_starttransfer}), `--http2`.
- `traceroute`/`mtr`: path analysis. MTR combines ping + traceroute for continuous monitoring. Identify network hops with high latency or packet loss.
- `ss` (modern) / `netstat` (legacy): socket statistics. `ss -tlnp` (listening TCP), `ss -s` (summary). Diagnose connection states, TIME_WAIT buildup.
- `dig` / `nslookup`: DNS queries. `dig +trace` for full resolution path. `dig @8.8.8.8` for specific resolver.
- MTU/fragmentation: Maximum Transmission Unit (typically 1500 bytes). Path MTU Discovery. Fragmentation performance impact. `ping -s 1472 -M do` to test. MTU mismatches (e.g., VPN/overlay networks) cause mysterious hangs on large payloads while small requests work.

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
- Mutability & hashability: only immutable objects should be hashable; `__hash__` and `__eq__` must agree (equal objects → equal hashes). The classic footgun: mutable default arguments (`def f(x=[])`) share one list across calls — use `None` + create inside.

**Bytecode & the Interpreter**
- CPython compiles source to bytecode (`.pyc` in `__pycache__`), executed by a stack-based virtual machine. `dis.dis(func)` shows the bytecode — useful for understanding performance and surprising behavior.
- The interpreter loop, frame objects (`f_locals`, `f_globals`, `f_back`), and why local variable access is faster than global (locals are array slots, globals are dict lookups).
- `compile()`, `exec()`, `eval()` exist but are rarely the right tool; `code` objects underlie them. CPython is reference implementation; alternatives: PyPy (JIT), GraalPy, MicroPython.

**Memory & Garbage Collection**
- Reference counting: every object has a refcount. Decremented when reference removed. Object deallocated when refcount reaches 0. Immediate cleanup, no pauses. `sys.getrefcount()`.
- Generational GC: handles circular references that refcounting can't. Three generations (gen0, gen1, gen2). Objects promoted to next generation if they survive a collection cycle. Gen0 collected most frequently.
- Weak references (`weakref`): reference that doesn't prevent GC. `weakref.ref()`, `WeakValueDictionary`, `WeakSet`. Used for caches, observer patterns, avoiding circular reference issues.
- Memory profiling: `tracemalloc` (stdlib, track allocations), `objgraph` (visualize object reference graphs), `memory_profiler` (line-by-line memory usage), `pympler` (object sizing).
- `sys.getsizeof()`: size of object itself (not referenced objects). For deep size, use `pympler.asizeof` or recursive calculation.
- Interning: Python interns small integers (-5 to 256) and some strings (identifiers). `sys.intern()` for explicit string interning. Reduces memory for repeated strings. This is why `is` sometimes "works" on small ints/short strings — never rely on it for value comparison; use `==`.
- `__del__` pitfalls: not guaranteed to run (especially during interpreter shutdown). Circular references with `__del__` prevent GC in older Python. Prefer `__enter__`/`__exit__` or `atexit`.
- Memory optimization: `__slots__`, `array.array` (typed arrays), `numpy` for numerical data, generators for streaming, `struct` for packed binary data.

**GIL (Global Interpreter Lock)**
- GIL prevents multiple threads from executing Python bytecode simultaneously. Only one thread holds the GIL at a time. GIL is released during I/O operations (file, network, sleep) and some C extensions (numpy).
- CPU-bound work: GIL is the bottleneck. Solutions: `multiprocessing` (separate processes, separate GILs), C extensions that release GIL, Cython with `nogil`, or use PyPy.
- I/O-bound work: GIL is NOT a bottleneck (released during I/O). `threading` works fine. `asyncio` even better (single thread, no GIL contention overhead).
- `multiprocessing`: process pools (`Pool`, `ProcessPoolExecutor`). IPC via `Queue`, `Pipe`, `Value`/`Array` (shared memory). `multiprocessing.shared_memory` (Python 3.8+) for zero-copy sharing. Watch out for fork vs spawn start methods (spawn re-imports the module; fork can deadlock with threads).
- `concurrent.futures`: unified interface. `ThreadPoolExecutor` for I/O, `ProcessPoolExecutor` for CPU. `submit()` returns `Future`, `map()` for bulk. `as_completed()` for results in completion order.
- Free-threaded Python (PEP 703, experimental in 3.13+): opt-in GIL removal. `python3.13t`. Still experimental, library compatibility varies. Subinterpreters (PEP 684/734) are another route to parallelism.

**Iterators & Generators**
- Iterator protocol: `__iter__()` returns self, `__next__()` returns next value or raises `StopIteration`. Any object implementing both is an iterator.
- Generators: functions with `yield`. Lazy evaluation — compute values on demand. Memory-efficient for large datasets. Generator state is preserved between yields.
- Generator expressions: `(x*2 for x in range(10))`. More memory-efficient than list comprehensions for large sequences.
- `yield from`: delegate to sub-generator. Flattens nested generators. Passes `send()`, `throw()`, `close()` through. Essential for coroutine composition.
- `send()`: send a value into a generator (received as return value of `yield`). `throw()`: raise exception inside generator. `close()`: trigger `GeneratorExit`.
- `itertools` mastery: `chain` (concatenate iterables), `islice` (slice iterators), `groupby` (group consecutive elements), `product`/`combinations`/`permutations` (combinatorics), `accumulate` (running totals), `starmap`, `tee` (fork iterator), `zip_longest`, `pairwise` (3.10+).
- `more-itertools`: community extension with `chunked`, `peekable`, `unique_everseen`, `flatten`, `windowed`.

**Import System**
- Module search order: `sys.modules` cache → built-in modules → `sys.path` (current dir, PYTHONPATH, installed packages).
- `__init__.py`: marks directory as package. Can be empty or contain initialization code. Implicit namespace packages (PEP 420, no `__init__.py`) for split-across-directories packages.
- Circular imports: A imports B, B imports A. Solutions: import inside function, restructure code, use `importlib.import_module()` lazily, or extract shared code to third module.
- `importlib`: dynamic imports (`import_module`), reload modules (`reload`), custom importers/finders. Plugin systems.
- `sys.modules`: dict of all loaded modules. Can be manipulated (mock modules, module aliases). Module is executed only once; subsequent imports use cache.
- Relative imports: `from . import sibling`, `from .. import parent_module`. Only work inside packages. Use absolute imports for clarity in most cases.
- `if __name__ == "__main__":` guard — required for `multiprocessing` spawn safety and to make a module both importable and runnable. `python -m package.module` runs a module as a script with correct package context.

### 2.2 Async Programming

**asyncio Core**
- Event loop: single-threaded, runs coroutines cooperatively. `asyncio.run()` creates loop, runs coroutine, closes loop. `loop.run_until_complete()` for more control.
- Coroutines: `async def` functions. Must be awaited. Execution suspends at `await`, resumes when awaited thing completes. Calling without `await` returns coroutine object (common bug).
- Tasks: wrap coroutines for concurrent execution. `asyncio.create_task()` schedules coroutine. Task starts executing at next `await` point in current coroutine.
- `asyncio.gather(*coros)`: run coroutines concurrently, wait for all. `return_exceptions=True` to collect exceptions instead of raising.
- `asyncio.wait(tasks, return_when=FIRST_COMPLETED|ALL_COMPLETED|FIRST_EXCEPTION)`: more control over completion.
- `asyncio.shield(coro)`: protect from cancellation (outer cancel doesn't propagate).
- `asyncio.Queue`: async producer-consumer queue. `put()`, `get()`, `join()`. Bounded queue with `maxsize` for backpressure.
- Exception handling: unhandled exceptions in tasks are logged but don't crash. Use `task.add_done_callback()` or gather with `return_exceptions`. Always await or check task results — orphaned tasks that are garbage-collected before completion warn and may silently drop work; keep a reference.
- Cancellation: `task.cancel()` raises `CancelledError` at next await point. Handle with `try/except asyncio.CancelledError`. Cleanup in `finally` block. Don't swallow `CancelledError` — re-raise after cleanup.
- `contextvars`: the async-safe replacement for thread-locals. Carries per-task context (request ID, current user) across `await` points without leaking between concurrent tasks. Used by structured logging and tracing.

**Async Patterns**
- Semaphores: `asyncio.Semaphore(n)` limits concurrency. Use as context manager: `async with sem:`. Critical for rate-limiting API calls, database connections.
- Async context managers: `async with`. Implement `__aenter__` and `__aexit__`. Or use `@asynccontextmanager` from `contextlib`.
- Async iterators: `__aiter__` and `__anext__`. Async generators: `async def` with `yield`. `async for item in aiter:`.
- Debouncing: delay execution until input settles. Use `asyncio.sleep()` with cancellation. Throttling: limit execution rate. Token bucket pattern.
- Fan-out/fan-in: dispatch work to multiple coroutines (fan-out), collect results (fan-in). Use `gather`, `as_completed`, or `TaskGroup` (Python 3.11+).
- Graceful shutdown: handle SIGTERM/SIGINT. Cancel running tasks. Wait for cleanup. `asyncio.get_running_loop().add_signal_handler()`.
- `asyncio.timeout()` (Python 3.11+) or `async_timeout` library. Wrap operations that might hang. Essential for network calls.
- The cardinal rule: never call blocking code (CPU-heavy loops, `time.sleep`, sync DB drivers, `requests`) directly in a coroutine — it stalls the entire event loop and every other task. Offload to `asyncio.to_thread()` / an executor.

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
- Generics: `TypeVar('T')` for generic functions/classes. `TypeVar('T', bound=Base)` for upper-bound. `ParamSpec` for decorator typing (preserve function signature). PEP 695 (3.12+) adds `class Box[T]:` / `def f[T](...)` syntax.
- Protocol (PEP 544): structural subtyping (duck typing with type checking). Define interface without inheritance. `@runtime_checkable` for `isinstance` checks.
- `TypedDict`: typed dictionaries with specific keys. `total=True` (all keys required) or `total=False` (all optional). Useful for JSON/API response typing.
- `Literal['a', 'b']`: restrict to specific values. `Final`: prevent reassignment. `ClassVar`: class-level variable hint. `Annotated[int, "metadata"]` attaches metadata (used by Pydantic/FastAPI).
- Runtime validation: Pydantic (data validation, serialization, settings management), `beartype` (runtime type checking decorator), `attrs` (class definition with validation).
- Type checkers: `mypy` (mature, configurable), `pyright` (fast, VSCode integration). Strict mode for maximum safety. Gradual typing: add types incrementally. Type hints are erased at runtime (no enforcement) unless a library inspects them.

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
- `functools` toolbox: `lru_cache`/`cache` (memoization), `partial` (pre-bind arguments), `reduce`, `singledispatch` (type-based function overloading), `cached_property`, `total_ordering`.

**Dataclasses, Enums & Modeling**
- `@dataclass`: auto-generates `__init__`, `__repr__`, `__eq__`. Options: `frozen=True` (immutable, hashable — great for value objects), `slots=True` (3.10+, memory savings), `order=True` (comparison methods), `kw_only=True`. `field(default_factory=list)` for mutable defaults.
- `__post_init__` for validation/derived fields. Dataclasses are the idiomatic lightweight value/DTO container; `attrs` is the more powerful third-party predecessor with validators and converters.
- `NamedTuple` (typed, immutable, tuple-compatible) vs `dataclass` vs plain dict — choose based on mutability and whether you need methods.
- `enum.Enum`: named constants with identity. `IntEnum`/`StrEnum` (3.11+) for interop with ints/strings. `Flag`/`IntFlag` for bitwise combinable flags (permissions). `auto()` for values. Prefer enums over magic strings/ints for states and choices.
- Pydantic models for parse-don't-validate: convert untrusted input into a typed, validated object at the boundary so the rest of the code can trust it.

**Dates, Times & Time Zones**
- Store and compute in UTC; convert to local only for display. This single rule prevents most date bugs.
- Aware vs naive `datetime`: a naive datetime has no `tzinfo` and is ambiguous. Always use timezone-aware datetimes for anything real. `datetime.now(timezone.utc)` — not the deprecated `utcnow()` (which returns a naive value, a classic trap).
- `zoneinfo` (stdlib, 3.9+) is the modern IANA time-zone source (`ZoneInfo("Europe/Paris")`); `pytz` is the older library with a different, error-prone `localize()` API.
- DST transitions cause real bugs: some local times don't exist (spring-forward gap) or happen twice (fall-back fold — handled via the `fold` attribute). Never do arithmetic in local time across a DST boundary; convert to UTC, do math, convert back.
- ISO 8601 / RFC 3339 for serialization (`2026-06-05T12:00:00+00:00`). `datetime.fromisoformat()` / `.isoformat()`. Unix timestamps are unambiguous (always UTC seconds since epoch) but lose the original zone.
- Monotonic vs wall-clock time: use `time.monotonic()` for measuring durations/timeouts (immune to clock adjustments, NTP steps, DST); use wall-clock only for "what time is it". Wall clocks can jump backward.
- Storing dates: persist UTC; if the user's intended zone matters (e.g., "9am in their city, forever"), store the zone name separately. Beware year-2038 (32-bit time_t) and leap seconds (usually smeared by infra).

**Numbers, Precision & Money**
- `float` is IEEE 754 double — binary floating point. `0.1 + 0.2 != 0.3`. Never use floats for money or exact decimal arithmetic. Comparisons need tolerances (`math.isclose`).
- `decimal.Decimal`: exact base-10 arithmetic with configurable precision and rounding (`ROUND_HALF_EVEN` / banker's rounding is the default and reduces bias). Use for currency, tax, financial calculations.
- The common production pattern for money: store as integer minor units (cents) in the database, or as `NUMERIC`/`DECIMAL`; never `float`/`double`. Track the currency alongside the amount (a `Money` value object). Define rounding policy explicitly.
- `fractions.Fraction` for exact rational arithmetic. Python `int` is arbitrary precision (no overflow) — but other systems/languages and DB columns are not, so validate ranges at boundaries.
- `numpy` numeric types DO overflow silently (fixed-width). Be careful mixing Python ints and numpy ints.

**Strings, Bytes & Encoding**
- `str` is a sequence of Unicode code points; `bytes` is a sequence of raw octets. They are different types — mixing them raises `TypeError`. Encode `str → bytes` with `.encode("utf-8")`; decode `bytes → str` with `.decode("utf-8")`. "Encode to bytes, decode to text."
- Always specify the encoding explicitly (`open(path, encoding="utf-8")`); relying on the platform default causes mojibake across OSes. UTF-8 everywhere is the safe default.
- `len()` counts code points, not user-perceived characters: emoji and combining sequences (e.g., flag emoji, accented letters) can be multiple code points. Slicing/length on user-facing text can surprise you.
- Unicode normalization (`unicodedata.normalize`): NFC vs NFD — the same visual string can have different byte representations (precomposed "é" vs "e" + combining accent). Normalize before comparing, hashing, or storing usernames/identifiers to avoid duplicate-but-different bugs and homograph attacks.
- Encoding pitfalls: `latin-1`/`cp1252` legacy data, BOM markers, `errors="replace"`/`"ignore"` to control decode failures. Base64 (`base64`) is binary-to-text, not encryption. URL/percent encoding (`urllib.parse.quote`) for query strings.

**Serialization**
- JSON (`json`): the interchange default. Watch out — it has no native datetime/Decimal/set/bytes types; provide custom encoders. Keys become strings; large ints may lose precision in JS consumers.
- `pickle`: Python-specific binary serialization that preserves arbitrary objects — but it executes arbitrary code on load. NEVER unpickle untrusted data (remote code execution). Not a stable cross-version format.
- `struct`: pack/unpack C-style binary records (network protocols, file formats); explicit byte order and field widths.
- Cross-language schema formats: Protocol Buffers / Avro / MessagePack (compact, schema-driven, versionable). Prefer these over pickle for anything crossing a process or network boundary.

### 2.4 Standard Library & Tooling Essentials

**Logging**
- Use the `logging` module, never `print`, for anything beyond throwaway scripts. Hierarchy of named loggers, handlers (where logs go), formatters (how they look), levels (DEBUG/INFO/WARNING/ERROR/CRITICAL).
- Configure once at app startup (`logging.config.dictConfig`). Get a module-level logger with `logging.getLogger(__name__)` so the logger name reflects the module path.
- Use lazy formatting (`logger.info("user %s did %s", uid, action)`) not f-strings, so the string is only built if the level is enabled. `logger.exception()` inside an `except` block logs the traceback.
- Structured logging (`structlog`, or JSON formatter) for production: machine-parseable, attach context (request_id, user_id) via `contextvars`. Never log secrets/PII.

**Filesystem, Processes & OS Interaction**
- `pathlib.Path`: object-oriented paths (`p / "sub" / "file.txt"`, `.exists()`, `.read_text()`, `.glob()`). Prefer it over `os.path` string juggling.
- `subprocess.run([...], check=True, capture_output=True, text=True)`: the right way to call external programs. Pass args as a list (avoid `shell=True` with untrusted input — shell injection). Set timeouts.
- `os`/`shutil` for env vars, file ops, temp files (`tempfile`). `tempfile.NamedTemporaryFile` + atomic `os.replace` for safe file writes.
- `argparse` for CLIs (or `click`/`typer` for richer ones). `configparser`/`tomllib` (3.11+, read TOML) for config.

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
- Structural patterns: avoid global variable lookups (local faster), cache attribute lookups in loops, use `operator.itemgetter`/`attrgetter` for key functions. `memoryview` for zero-copy slicing of buffers.

**Pattern Matching (3.10+)**
- `match`/`case` structural pattern matching: not just a switch — it destructures. Match against literals, sequences (`[x, *rest]`), mappings (`{"type": t}`), classes (`Point(x=0, y=y)`), and capture variables. Guards with `if`. `case _` is the wildcard.
- Great for parsing ASTs, command dispatch, handling tagged/variant data, and state machines. Beware: bare names in patterns are *capture* patterns (always match + bind), not equality checks — use dotted names or `Enum.MEMBER` for constants.

### 2.5 Packaging & Tooling

**Project Setup**
- `pyproject.toml` (PEP 621): single config file for project metadata, build system, tool configuration. Replaces `setup.py`, `setup.cfg`, `MANIFEST.in`.
- Package managers: Poetry (dependency resolution, lock file, virtual env), PDM (PEP 582 support), uv (extremely fast, Rust-based, drop-in pip/venv replacement), Hatch (build backend, environment management).
- Virtual environments: `python -m venv .venv`. Isolate project dependencies. `pip freeze > requirements.txt`. Lock files (Poetry.lock, uv.lock) for reproducible builds.
- Dependency resolution: version specifiers (`>=1.0,<2.0`, `~=1.4`), extras (`package[extra]`), platform markers. Dependency conflicts (diamond dependencies). Lock files resolve to exact versions. Distinguish abstract deps (loose ranges, for libraries) from pinned/locked deps (exact, for applications).
- Monorepo: shared utilities, consistent tooling. Tools: `pants`, `bazel`, `nx`. Or simpler: workspace packages (Poetry, uv).
- Distribution: wheels (`.whl`, pre-built) vs sdists (source). Semantic versioning (MAJOR.MINOR.PATCH). Publishing to PyPI (or a private index).

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
- **Law of Demeter (principle of least knowledge)**: a method should only talk to its immediate collaborators — avoid `a.b().c().d()` train wrecks that couple you to deep internal structure.
- **Fail fast**: validate inputs and invariants at boundaries and crash loudly on programmer errors rather than limping on with corrupt state. Make illegal states unrepresentable (types, enums, value objects).

**The Twelve-Factor App**
- A checklist for cloud-native, deployable services: (1) codebase in version control, one repo per app; (2) explicitly declared dependencies; (3) config in the environment, not code; (4) backing services (DB, cache, queue) as attached resources via URLs/credentials; (5) strict separate build/release/run stages; (6) stateless processes (no sticky local state); (7) export services via port binding; (8) scale out via the process model; (9) fast startup and graceful shutdown (disposability); (10) dev/prod parity; (11) logs as event streams to stdout; (12) admin tasks as one-off processes.
- The practical payoff: statelessness + config-from-env are what make horizontal scaling, containers, and zero-downtime deploys possible. Most "why won't this scale?" problems trace back to violating factors 3, 6, or 11.

**Coupling & Cohesion**
- **Tight coupling**: classes depend on each other's internals. Changes ripple. Hard to test in isolation. Signs: direct instantiation of dependencies, accessing private attributes, many import dependencies.
- **Loose coupling**: interact through well-defined interfaces. Dependency injection. Event-driven communication. Message passing. Easy to swap implementations.
- **Afferent coupling (Ca)**: number of classes that depend on this class. High Ca = high responsibility, change is risky.
- **Efferent coupling (Ce)**: number of classes this class depends on. High Ce = fragile, breaks when dependencies change.
- **Instability = Ce / (Ca + Ce)**: 0 = maximally stable, 1 = maximally unstable. Stable classes should be abstract.
- **High cohesion**: elements within a module are strongly related. Single purpose. Low cohesion = "utility" classes, god objects.
- **Package by feature** (users/, orders/, products/) vs **package by layer** (models/, views/, services/). Feature packaging promotes cohesion, reduces coupling between features.
- **Connascence** (a finer-grained coupling vocabulary): name, type, meaning, position, algorithm, execution order, timing, value, identity. Lower-grade (static, local) connascence is fine; high-grade (dynamic, distant) connascence is the dangerous kind to eliminate or localize.

**Common Anti-Patterns**
- **God object / blob**: one class that knows/does everything. Split by responsibility.
- **Anemic domain model**: domain objects are bags of getters/setters with all logic in "service" procedures — object-oriented in name only. Push behavior onto the entities/value objects that own the data.
- **Spaghetti vs lasagna**: tangled control flow vs too many pass-through layers that add ceremony without value. Both hurt; aim for the right number of meaningful boundaries.
- **Big ball of mud**: no discernible architecture; everything depends on everything. The most common architecture in practice — fight entropy deliberately.
- **Premature optimization / premature abstraction**: complexity added before it's justified. Pairs with YAGNI.
- **Magic / hidden coupling**: behavior that "just happens" via signals, monkeypatching, or global state, making code hard to trace. Prefer explicit.
- **Distributed monolith**: microservices so chatty and tightly coupled they must be deployed together — worst of both worlds (covered more in 3.3).

**Domain-Driven Design (DDD)**
- **Bounded Context**: explicit boundary around a domain model. Different contexts can have different models for same real-world concept (e.g., "User" means different things in auth vs billing).
- **Ubiquitous Language**: shared language between developers and domain experts within a bounded context. Code uses same terms as business. Reduces translation errors.
- **Entities**: identified by ID, mutable, lifecycle. Equality by identity, not attributes. (e.g., User, Order).
- **Value Objects**: identified by attributes, immutable. Equality by value. No separate ID. (e.g., Money, Address, DateRange). Use `@dataclass(frozen=True)` or `NamedTuple`.
- **Aggregates**: cluster of entities/value objects treated as a unit. One entity is the aggregate root (entry point). All modifications go through root. Consistency boundary. Keep aggregates small; reference other aggregates by ID, not by object.
- **Domain Events**: something meaningful that happened in the domain. Immutable, past-tense naming (OrderPlaced, PaymentReceived). Enable loose coupling between bounded contexts. Event sourcing stores events as source of truth.
- **Repository**: abstraction for data access. Hides storage details from domain. In-memory collection-like interface. One repository per aggregate root.
- **Anti-Corruption Layer (ACL)**: translation layer between bounded contexts or legacy systems. Prevents foreign models from leaking into your domain.
- **Context Mapping**: how bounded contexts relate. Patterns: shared kernel, customer-supplier, conformist, ACL, published language.
- **Strategic DDD**: identifying bounded contexts, their relationships, team ownership. Tactical DDD: implementation patterns within a context.
- **Domain vs application vs infrastructure services**: domain services hold logic that doesn't belong to a single entity; application services orchestrate use cases (no business rules); infrastructure services talk to the outside world.

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

**Enterprise Application Patterns**
- **Repository**: mediates between the domain and data mapping, exposing a collection-like interface (`add`, `get`, `list`) and hiding the ORM/SQL. Lets you swap storage and unit-test domain logic against an in-memory fake repository.
- **Unit of Work**: tracks objects changed during a business transaction and commits them atomically (one DB transaction), coordinating one or more repositories. Maps naturally to a DB transaction / SQLAlchemy session. Gives you "all-or-nothing" at the use-case level.
- **Service Layer (application services)**: thin orchestration layer defining the use cases of the application (`place_order`, `register_user`). Coordinates domain objects, repositories, and the unit of work; holds no business rules itself. The natural entry point your web/CLI/queue adapters call.
- **Data Mapper vs Active Record**: Active Record (Django ORM) — the model knows how to persist itself (`user.save()`); simple, couples domain to persistence. Data Mapper (SQLAlchemy classic, repositories) — a separate layer maps objects to rows; better for rich domain models and clean architecture. Choose based on domain complexity.
- **DTO (Data Transfer Object)**: a flat, serializable object for crossing boundaries (API request/response, queue payload), distinct from your domain entities. Prevents leaking internal models and decouples your API contract from your schema (Pydantic models, serializers).
- **Specification**: encapsulate a business rule / query predicate as a composable object (`overdue_and_unpaid = Overdue() & Unpaid()`). Reusable in validation and querying.
- **Dependency Injection**: pass collaborators in (constructor args, function params) rather than constructing them internally. Enables testing and swapping. In Python, explicit DI is usually enough; containers (`dependency-injector`, FastAPI's `Depends`) help for larger apps.

**Concurrency & Reliability Patterns**
- **Producer-Consumer**: decouple data production from consumption via buffer/queue. In Python: `queue.Queue`, `asyncio.Queue`, Celery, Redis streams.
- **Thread Pool / Worker Pool**: fixed set of threads processing tasks from queue. `concurrent.futures.ThreadPoolExecutor`. Bound resource usage.
- **Future/Promise**: placeholder for result of async operation. `concurrent.futures.Future`, `asyncio.Future`. Chain computations.
- **Circuit Breaker**: prevent cascade failures. States: closed (normal), open (failing fast), half-open (testing recovery). Libraries: `pybreaker`, `tenacity`. Configurable thresholds, timeout, fallback.
- **Bulkhead**: isolate failures to compartments. Separate thread pools, connection pools, rate limits per dependency. Prevents one failing dependency from consuming all resources.
- **Saga**: manage distributed transactions. Choreography (event-driven, each service reacts) vs orchestration (central coordinator). Compensating transactions for rollback.
- **Backpressure**: signal upstream to slow down when downstream is overwhelmed. Bounded queues, flow control, reactive streams.
- **Retry with backoff + jitter** and **timeout budgets**: never retry without a cap, backoff, and jitter; only retry idempotent operations. Combine with circuit breakers so retries don't hammer a dying dependency.
- **Idempotency / dedup**: design operations so re-execution is safe (idempotency keys, natural-key upserts, dedup tables) — essential under at-least-once delivery and client retries.
- **Leader election / leases**: ensure exactly one worker performs a singleton task (cron, compaction) using a distributed lock or lease (etcd, Redis, advisory locks).

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

**Integration & Deployment Patterns**
- **API Gateway**: single entry point for clients. Handles routing, auth, rate limiting, request aggregation, protocol translation, and TLS termination so individual services don't reimplement cross-cutting concerns. Risk: becoming a bottleneck or a "god gateway" with business logic — keep it thin.
- **Backend for Frontend (BFF)**: a dedicated gateway/aggregation layer per client type (web, mobile, partner) tailoring payloads and calls to that client's needs. Avoids one-size-fits-none APIs.
- **Sidecar**: deploy a helper process alongside the main service in the same pod (logging, proxy, config sync). The mesh data-plane proxy is a sidecar.
- **Ambassador**: a sidecar that proxies *outbound* connections (handles retries, TLS, service discovery to remote services), so the app talks to localhost.
- **Adapter/anti-corruption at the edge**: normalize disparate external systems into a consistent internal contract.
- **Service discovery**: how services find each other — client-side (query a registry: Consul, Eureka) vs server-side (a load balancer / DNS resolves: Kubernetes Services). DNS-based is simplest; dedicated registries handle health and metadata.
- **Aggregator / scatter-gather**: fan a request out to several services and combine responses (with timeouts and partial-result handling).

**Event-Driven Architecture**
- **Three flavors of "event"** (know which you're using): *event notification* (thin "something happened, go look" — low coupling, more callbacks), *event-carried state transfer* (the event contains the data consumers need, so they don't call back — more coupling to schema, less chatter), and *event sourcing* (events are the source of truth).
- **Event Sourcing**: store every state change as an immutable event. Derive current state by replaying events. Full audit trail. Temporal queries. Can rebuild state from any point. Trade-off: complexity, eventual consistency, event schema evolution, snapshotting for performance.
- **CQRS (Command Query Responsibility Segregation)**: separate models for reads and writes. Write model optimized for consistency/business rules. Read model optimized for queries (denormalized, different storage). Can use different databases. Often (not always) paired with event sourcing; introduce only when read/write needs genuinely diverge.
- **Event Bus / Message Broker**: Kafka (high throughput, log-based, replay), RabbitMQ (flexible routing, AMQP, traditional messaging), Redis Streams (lightweight, in-memory). AWS SNS/SQS, Google Pub/Sub.
- **Delivery semantics**: at-most-once (may lose), at-least-once (may duplicate — the common default, requires idempotent consumers), exactly-once (expensive; usually "effectively once" via idempotency + dedup, e.g., Kafka transactions). There is no free exactly-once across a network.
- **Eventual consistency**: data will become consistent eventually (not immediately). Acceptable for many use cases (analytics, notifications, search index). Unacceptable for financial transactions, inventory without compensation.
- **Idempotency**: processing same event multiple times produces same result. Critical for at-least-once delivery. Techniques: idempotency key, check-and-set, deduplication table.
- **Outbox pattern**: write event to outbox table in same transaction as data change. Separate process publishes events from outbox. Guarantees data and event consistency. The standard fix for the "dual-write" problem (you can't atomically write to a DB and a broker).
- **Inbox / dedup pattern**: consumer records processed message IDs to make handling idempotent.
- **Dead letter queue (DLQ)**: messages that fail processing after max retries go to DLQ. Monitor, investigate, reprocess. Essential for reliability.
- **Ordering & partitioning**: ordering is only guaranteed within a partition/queue keyed by something (e.g., per-aggregate). Choose partition keys so related events stay ordered without creating hot partitions.

**Distributed Transactions & Consistency**
- **Why not 2PC everywhere**: two-phase commit (prepare → commit, coordinated by a transaction manager) gives atomicity across services but blocks on coordinator failure, holds locks, and doesn't scale — generally avoided across service/network boundaries.
- **Saga**: model a long-lived business transaction as a sequence of local transactions, each with a compensating action to undo it on failure. Orchestration (central state machine drives steps — easier to reason about, single point of logic) vs choreography (services react to each other's events — more decoupled, harder to trace).
- **TCC (Try-Confirm-Cancel)**: reserve resources in a Try phase, then Confirm or Cancel. A more structured alternative to sagas for reservations (inventory, seats).
- **Idempotency + outbox + retries** are the workhorse primitives that make eventually-consistent workflows reliable in practice.

**Serverless & FaaS**
- Lambda/Cloud Functions: stateless functions triggered by events (HTTP, queue, schedule, database change). Pay per invocation. Auto-scales to zero.
- Cold starts: first invocation after idle period is slow (100ms-10s depending on runtime/size). Mitigations: provisioned concurrency, keep-warm pings, smaller deployments, language choice (Python ~200ms, Java ~1-3s).
- Stateless design: no local file system persistence. External state (DynamoDB, S3, Redis). Idempotent handlers.
- Limitations: execution time limits (15min AWS Lambda), payload size limits, no long-running connections (WebSocket), vendor lock-in, debugging complexity, and connection-pool exhaustion against databases (use a proxy like RDS Proxy or a serverless DB).
- When it fits: event processing, scheduled tasks, webhooks, light APIs, glue code between services, prototyping. When it doesn't: sustained high traffic (cost), complex workflows, low-latency requirements.

---
## 4. Databases & Data

### 4.1 Relational Databases (PostgreSQL Focus)

**Storage Internals & Durability**
- Pages and the buffer pool: databases read/write in fixed-size pages (PostgreSQL: 8KB). A shared in-memory buffer pool (`shared_buffers`) caches hot pages; the OS page cache adds a second tier. Most query work is about keeping the working set in these caches.
- Write-Ahead Log (WAL): every change is written to the WAL (sequential, fast) and `fsync`'d before the data pages are updated in place. On crash, the WAL is replayed to recover. This is the "D" in ACID and the foundation of replication and PITR. `wal_level`, checkpoints flush dirty pages and bound recovery time.
- Heap + indexes: PostgreSQL stores rows in an unordered heap; indexes point to heap tuples via TIDs. Contrast with InnoDB's clustered index (the table *is* the primary-key B-tree, secondary indexes store the PK). Clustered vs heap layout explains a lot of performance differences.
- MVCC storage: PostgreSQL keeps old row versions in the heap (hence VACUUM); MySQL/InnoDB keeps old versions in a separate undo log. Both let readers avoid blocking writers.
- B-tree vs LSM storage engines: PostgreSQL/InnoDB use B-trees (good for reads and updates in place); Cassandra/RocksDB use LSM-trees (good for high write throughput, append-only with background compaction). Choosing a database is partly choosing a storage engine.

**Query Optimization**
- `EXPLAIN ANALYZE`: actual execution plan with timing. Read bottom-up. Key metrics: actual rows vs estimated rows (bad estimate = bad plan), loops, shared hit/read (buffer cache). `BUFFERS` option shows cache hits vs disk reads.
- Index types: B-tree (default, equality + range), Hash (equality only, rarely better), GIN (full-text search, JSONB, arrays), GiST (geometric, range types, full-text), BRIN (block range index, for naturally ordered data like timestamps — very compact).
- Partial indexes: `CREATE INDEX idx ON orders (status) WHERE status = 'pending'`. Index only relevant rows. Smaller, faster.
- Expression indexes: `CREATE INDEX idx ON users (lower(email))`. Index computed values. Must match query expression exactly.
- Composite index column order: leftmost prefix matters. Index on (a, b, c) supports queries on (a), (a, b), (a, b, c), but NOT (b) or (c) alone. Put equality columns first, range columns last.
- Index-only scans: query answered entirely from index (no table access). Requires all selected columns in index. `INCLUDE` clause for additional columns without affecting index ordering.
- Covering indexes and selectivity: an index helps most on high-selectivity predicates (few matching rows). The planner may correctly choose a sequential scan when a query returns a large fraction of the table.
- `pg_stat_statements`: track query execution statistics (calls, mean/total time, rows). Essential for finding slow queries. Reset periodically.
- Statistics & `ANALYZE`: the planner relies on table statistics (histograms, n_distinct). Stale stats cause bad plans; `ANALYZE` refreshes them (autovacuum does this). Extended statistics for correlated columns.
- Query planner decisions: sequential scan vs index scan (depends on selectivity, table size). Nested loop vs hash join vs merge join. `SET enable_seqscan = off` for testing (never in production).
- Common mistakes: missing indexes on foreign keys, `SELECT *` preventing index-only scans, functions in WHERE preventing index use, implicit type casting, `OR` conditions preventing index use (use `UNION` instead), leading wildcard `LIKE '%x'` can't use a normal B-tree index (use trigram/GIN).

**Transactions & Concurrency**
- ACID: Atomicity (all or nothing), Consistency (valid state), Isolation (concurrent transactions don't interfere), Durability (committed data survives crashes).
- Isolation levels: Read Committed (default in PostgreSQL, sees committed data at statement start), Repeatable Read (snapshot at transaction start, serialization failures possible), Serializable (appears serial execution, most serialization failures).
- The isolation anomalies (what each level prevents):
  - *Dirty read*: reading another transaction's uncommitted data. Prevented at Read Committed and above.
  - *Non-repeatable read*: re-reading a row returns different committed data within one transaction. Prevented at Repeatable Read.
  - *Phantom read*: a range query returns new rows on re-execution because another transaction inserted matching rows. Prevented at Serializable (and largely at PostgreSQL's Repeatable Read via snapshot isolation).
  - *Lost update*: two transactions read-modify-write the same row; one overwrites the other. Prevent with `SELECT ... FOR UPDATE`, atomic updates (`SET balance = balance - 10`), or optimistic concurrency (version column).
  - *Write skew*: two transactions read an overlapping set, each makes a decision valid alone but invalid together (e.g., both doctors go off-call). Only Serializable prevents it; snapshot isolation does NOT.
- MVCC (Multi-Version Concurrency Control): each transaction sees a snapshot. Writers don't block readers, readers don't block writers. Dead tuples (old versions) cleaned by VACUUM.
- Optimistic vs pessimistic concurrency: pessimistic locks rows up front (`FOR UPDATE`); optimistic checks a version/timestamp at write time and retries on conflict. Optimistic wins under low contention; pessimistic under high contention.
- Row-level locking: `SELECT FOR UPDATE` (exclusive lock), `SELECT FOR SHARE` (shared lock), `SELECT FOR UPDATE SKIP LOCKED` (skip locked rows — great for job queues), `SELECT FOR UPDATE NOWAIT` (fail immediately if locked).
- Advisory locks: application-level locks managed by PostgreSQL. `pg_advisory_lock(key)`, `pg_try_advisory_lock(key)`. Great for distributed locking, ensuring single worker for a task.
- Deadlock detection: PostgreSQL detects deadlocks and aborts one transaction. Consistent lock ordering prevents deadlocks. Keep transactions short.
- VACUUM: reclaim dead tuple space. Autovacuum runs automatically (tune `autovacuum_vacuum_scale_factor`). `VACUUM FULL` rewrites table (locks table, use sparingly). Dead tuple bloat monitoring. Transaction ID wraparound is a real operational hazard — autovacuum also prevents it.
- Transaction anti-patterns: long-running transactions (hold locks, prevent vacuum, bloat the system), implicit transactions (autocommit off by default in psycopg2), savepoints for partial rollback, doing slow external I/O (API calls) while holding a DB transaction open.

**Schema Design**
- Normalization: 1NF (atomic values, no repeating groups), 2NF (no partial dependencies on composite key), 3NF (no transitive dependencies), BCNF (every determinant is a candidate key). Normalize first, denormalize for performance later.
- Denormalization trade-offs: faster reads, slower writes, data consistency risk. Materialized views, computed columns, summary tables are controlled denormalization.
- Constraints are documentation the database enforces: `NOT NULL`, `UNIQUE`, `CHECK`, foreign keys with appropriate `ON DELETE` (CASCADE/RESTRICT/SET NULL), exclusion constraints. Push invariants into the schema where you can — the DB is the last line of defense against bad data.
- JSONB columns: when to use — dynamic attributes, user preferences, API response storage, schema-less extensions. When not to use — data you query/join/filter frequently (use proper columns). Can index with GIN. Don't let JSONB become a schema-avoidance dumping ground.
- Partitioning: divide large tables. Range partitioning (by date — most common), list partitioning (by category), hash partitioning (even distribution). Partition pruning eliminates irrelevant partitions. Essential for time-series data retention (drop old partitions instead of `DELETE`).
- UUID vs serial PKs: UUIDs avoid hotspots in distributed systems, prevent ID enumeration, no coordination needed. Serial/BIGSERIAL is smaller (8 vs 16 bytes), better index performance, naturally ordered. Random UUIDv4 hurts B-tree locality (random inserts); UUIDv7/ULID (time-sorted) combines uniqueness with insert locality.
- Soft deletes: `deleted_at` timestamp instead of actual DELETE. Pros: easy undo, audit trail, referential integrity. Cons: query complexity (add `WHERE deleted_at IS NULL` everywhere), index bloat, GDPR compliance issues. Alternative: archive table.
- Multi-tenancy: separate database (strongest isolation, operational overhead), separate schema (good isolation, migration complexity), row-level (simplest, use `tenant_id` everywhere + row-level security).

**Advanced PostgreSQL**
- CTEs (Common Table Expressions): `WITH name AS (query)`. Readable subqueries. Recursive CTEs for hierarchical data: `WITH RECURSIVE tree AS (base UNION ALL recursive)`. Org charts, category trees, graph traversal. Note: CTEs can be optimization fences in older versions; PostgreSQL 12+ inlines non-recursive CTEs by default.
- Window functions: `ROW_NUMBER()` (numbering), `RANK()`/`DENSE_RANK()` (ranking with ties), `LAG()`/`LEAD()` (access previous/next rows), `SUM() OVER (ORDER BY date)` (running totals), `NTILE()` (percentiles). `PARTITION BY` for grouping, `ORDER BY` for ordering within partition. `ROWS BETWEEN` for frame specification.
- `UPSERT`: `INSERT ... ON CONFLICT (key) DO UPDATE/DO NOTHING`. The idiomatic idempotent write; great for dedup and "create or update" semantics.
- Materialized views: pre-computed query results. `CREATE MATERIALIZED VIEW`. `REFRESH MATERIALIZED VIEW CONCURRENTLY` (no lock, requires unique index). Use for expensive aggregations, dashboards. Refresh on schedule or trigger.
- `LISTEN/NOTIFY`: PostgreSQL pub/sub. `NOTIFY channel, 'payload'`. `LISTEN channel`. Low-latency event notification. Use for cache invalidation, real-time updates. Limited payload size (8000 bytes).
- Full-text search: `tsvector` (document), `tsquery` (query). `to_tsvector('english', text)`. GIN index. Ranking with `ts_rank`. Phrase search. Headline with highlighted matches. Custom dictionaries.
- `pg_trgm`: trigram-based similarity search. `LIKE`/`ILIKE` with GIN index. `similarity()` function. Fuzzy matching, typo tolerance. `CREATE INDEX idx ON table USING gin (column gin_trgm_ops)`.
- Extensions: PostGIS (geospatial), TimescaleDB (time-series), pg_partman (partition management), pgvector (vector similarity search for ML/embeddings), pg_stat_statements (query stats), pg_cron (scheduled jobs).

**Replication & High Availability**
- Streaming replication: physical replication of WAL (Write-Ahead Log). Synchronous (guaranteed consistency, added latency) vs asynchronous (lower latency, potential data loss on failover).
- Logical replication: replicate specific tables/operations. Can replicate between different PostgreSQL versions. Selective replication. Can have different indexes/schemas on replica. Basis for zero-downtime major-version upgrades and CDC.
- Read replicas: route read queries to replicas, writes to primary. Replication lag (ms to seconds). Application must handle stale reads. Session-based routing for read-your-writes consistency (route a user to the primary right after they write).
- Connection pooling: PgBouncer (lightweight, supports transaction/session/statement pooling), pgpool-II (more features: load balancing, query routing). Essential for reducing connection overhead (each PostgreSQL connection = a backend process, ~10MB). Transaction-mode pooling breaks session features (prepared statements, advisory locks, `SET`) — know the trade-offs.
- Failover: Patroni (industry standard, etcd/ZooKeeper/Consul for consensus, automatic failover), repmgr. VIP/DNS switchover. Application retry logic. Beware split-brain — fencing required.
- PITR (Point-in-Time Recovery): continuous WAL archiving. Recover to any point in time. Base backup + WAL replay. Essential for disaster recovery. Define RPO (how much data you can lose) and RTO (how fast you must recover) and test restores regularly — an untested backup is not a backup.
- Backup strategies: `pg_dump` (logical, single database, portable), `pg_dumpall` (all databases), `pg_basebackup` (physical, full cluster), WAL-G / pgBackRest (continuous WAL archiving to cloud storage, PITR support).

### 4.2 NoSQL & Specialized Databases

**Choosing a Data Model**
- Relational (row store): strong consistency, joins, ad-hoc queries, transactions — the default until you have a reason not to.
- Key-value (Redis, DynamoDB): O(1) access by key, caching, sessions, simple high-scale lookups.
- Document (MongoDB): flexible/nested schema, aggregate stored together, content/catalogs.
- Wide-column (Cassandra, ScyllaDB, HBase, Bigtable): massive write throughput, time-series/event data, query-driven schema.
- Graph (Neo4j): relationship-heavy traversals (social, fraud, recommendations).
- Search (Elasticsearch): full-text, relevance ranking, faceted analytics.
- Vector (pgvector, Pinecone, Milvus): semantic similarity for embeddings/ML.
- Polyglot persistence: use the right store per workload, accept the operational cost. But every new datastore is a new thing to operate, back up, and keep consistent — don't add one casually.

**Redis**
- Data types: Strings (counters, simple cache), Hashes (object fields), Lists (queues, timelines), Sets (unique collections, tags), Sorted Sets (leaderboards, priority queues, rate limiting), Streams (event log, consumer groups), HyperLogLog (cardinality estimation), Bitmaps (feature flags, user activity tracking), Geospatial (location-based queries).
- Pub/Sub: `PUBLISH`, `SUBSCRIBE`, `PSUBSCRIBE` (pattern). Fire-and-forget (no persistence). Use Streams for persistent messaging.
- Lua scripting: `EVAL`. Atomic execution of multiple commands. No race conditions. Used for complex operations (rate limiting, distributed locking). EVALSHA for cached scripts.
- Pipelining: batch multiple commands in single round-trip. 5-10x throughput improvement. `MULTI`/`EXEC` for transactions (all-or-nothing, but no rollback — use Lua for conditional logic).
- Redis Cluster: automatic sharding (16384 hash slots). Multi-master with replicas. Cluster-aware clients. No cross-slot transactions. vs Sentinel: master-slave with automatic failover, no sharding.
- Persistence: RDB (periodic snapshots, compact, faster recovery, data loss between snapshots), AOF (append-only file, every write logged, fsync configurable, larger but more durable). Use both for best durability. Remember: Redis is primarily a cache — treat its data as losable unless explicitly configured otherwise.
- Use cases: session storage, caching (with TTL), rate limiting (INCR + EXPIRE or sorted sets), distributed locking (the Redlock debate — single-instance lock with a lease/token is fine for most; Redlock is contested for correctness), leaderboards (sorted sets), job queues (lists or streams), real-time analytics.
- Memory management: `maxmemory` policy (allkeys-lru, volatile-lru, allkeys-random, noeviction). Monitor memory with `INFO memory`. Key expiration. `SCAN` for iteration (not KEYS in production — KEYS blocks the single-threaded server).

**MongoDB**
- Document model: BSON (binary JSON). Flexible schema within collection. Nested documents and arrays. Denormalization is common (embed vs reference decision: embed for data read together and bounded in size; reference for unbounded or shared-across-documents data).
- Aggregation pipeline: `$match` (filter), `$group` (aggregate), `$project` (reshape), `$lookup` (join), `$unwind` (flatten arrays), `$sort`, `$limit`, `$facet` (parallel pipelines). Powerful but complex. Put `$match`/`$limit` early to reduce work.
- Indexing: B-tree indexes, compound indexes, multi-key (array fields), text indexes, geospatial (2dsphere), TTL indexes (auto-expire documents), partial indexes, wildcard indexes.
- Sharding: horizontal scaling. Shard key selection is critical and irreversible(-ish). Range sharding vs hashed sharding. Choose high-cardinality, write-distributed key. Avoid monotonically increasing keys (hotspot). Jumbo chunks.
- Replica sets: automatic failover, read preferences (primary, primaryPreferred, secondary, nearest). Write concern (w:1, w:"majority"). Read concern (local, majority, linearizable). The write-concern/read-concern combo is your consistency dial.
- Change streams: real-time notification of data changes. Resume token for fault tolerance. Trigger-like functionality without polling. Use for: CDC, cache invalidation, event-driven architecture.
- When documents fit: variable schema, hierarchical data, content management, catalogs, user profiles. When they don't: heavy relationships/joins, multi-document transactions (supported but expensive), strict schema requirements.

**Cassandra & Wide-Column Stores**
- Query-first / denormalized modeling: you design tables around your read queries, not normalized entities. One table per query pattern; duplicate data freely (writes are cheap). There are no joins.
- Partition key + clustering columns: the partition key decides which node holds the data (and must distribute evenly — avoid hot partitions); clustering columns order rows within a partition (enabling efficient range scans). The primary key = (partition key, clustering columns).
- Tunable consistency: per-query consistency level (ONE, QUORUM, ALL). With replication factor N, `R + W > N` gives strong consistency for that operation; lower for availability/latency. Classic AP system (favor availability under partition).
- Anti-entropy & repair: hinted handoff, read repair, and Merkle-tree-based repair reconcile replicas. LSM storage means tombstones for deletes (and tombstone buildup is a real operational footgun).
- DynamoDB parallels: partition key/sort key, single-table design, provisioned vs on-demand capacity, hot-partition throttling, global secondary indexes, streams for CDC.

**Graph Databases**
- Model: nodes (entities), edges (relationships, themselves first-class with properties), properties on both. Relationships are stored as direct pointers, so multi-hop traversals are fast (no repeated join cost) — the key advantage over relational for deep relationship queries.
- Cypher (Neo4j): pattern-matching query language — `MATCH (a:User)-[:FOLLOWS]->(b:User) WHERE a.name = 'x' RETURN b`. Gremlin is the alternative traversal language (Apache TinkerPop).
- When to use: social graphs, recommendations ("friends who bought"), fraud rings, network/dependency analysis, knowledge graphs, identity resolution. When not: simple tabular data, heavy aggregation/analytics (use columnar), or when relationships are shallow (relational joins are fine).

**Vector Databases & Embeddings**
- Embeddings: ML models map text/images/audio to high-dimensional vectors where semantic similarity ≈ geometric closeness (cosine similarity / dot product / Euclidean distance). The backbone of semantic search and RAG.
- ANN (Approximate Nearest Neighbor) search: exact nearest-neighbor is too slow at scale, so indexes like HNSW (graph-based, great recall/latency), IVF (inverted file/clustering), and product quantization (compression) trade a little accuracy for big speed/memory wins.
- Options: `pgvector` (vectors inside PostgreSQL — keep them next to your relational data, simplest operationally), dedicated stores (Pinecone, Milvus, Weaviate, Qdrant), and search engines adding vector support (Elasticsearch/OpenSearch).
- Hybrid search: combine vector similarity with keyword/filter (BM25) for better relevance; pre-filter by metadata (tenant, date) then rank by vector distance. Watch dimensionality, index build cost, and recall vs latency tuning.

**Elasticsearch / OpenSearch**
- Inverted index: maps terms to documents containing them. Foundation of full-text search. Each field can have different analyzers.
- Analyzers: tokenizer + token filters. Standard (split on whitespace/punctuation), keyword (no splitting), custom (language-specific stemming, synonyms, ngrams). Character filters for preprocessing.
- Mappings: define field types and analysis. Static (explicit) vs dynamic (auto-detected). `keyword` (exact match, sorting, aggregations) vs `text` (full-text search, analyzed). Multi-field mappings.
- Query DSL: `match` (full-text), `term` (exact), `range`, `bool` (must/should/must_not/filter). Full-text queries are scored, filter queries are cached. Combine for relevance + filtering.
- Relevance scoring: BM25 (default). Boosting, function scores, and the difference between query context (scored) and filter context (yes/no, cacheable).
- Aggregations: metrics (avg, sum, min, max, stats), bucket (terms, histogram, date_histogram, range), pipeline (derivative, moving_avg). Basis for analytics dashboards.
- Sharding & replication: primary shards (set at index creation, hard to change), replica shards (scalable read throughput, fault tolerance). Shard sizing: 10-50GB each. Over-sharding wastes resources.
- Operational reality: Elasticsearch is a search/analytics index, not a source of truth — feed it from your primary store (often via CDC) and be able to rebuild it. Refresh interval controls near-real-time visibility vs indexing throughput.
- Performance tuning: bulk indexing, refresh interval, doc_values for aggregations, fielddata circuit breaker, query caching, index lifecycle management (hot-warm-cold).

**Time-Series & Analytics**
- TimescaleDB: PostgreSQL extension. Hypertables (auto-partitioned by time). Compression (90%+ for older data). Continuous aggregates (auto-updated materialized views). Compatible with all PostgreSQL tooling.
- ClickHouse: columnar OLAP database. Extremely fast analytical queries. MergeTree engine family. Parallel processing. 100-1000x faster than PostgreSQL for analytical queries. Limited update/delete support.
- Columnar storage: Parquet (Hadoop/lake ecosystem), ORC. Efficient compression (similar values together). Column pruning (read only needed columns). Predicate pushdown. 10-100x compression vs row-based.
- OLTP vs OLAP: OLTP (transactional — many small reads/writes, normalized, row-based) vs OLAP (analytical — few complex queries over large data, denormalized, columnar). Don't mix workloads; ship OLTP data to an analytics store rather than running heavy analytics on the transactional primary.

### 4.3 Data Management

**Migrations**
- Tools: Alembic (SQLAlchemy), Django migrations (auto-generated from models), Flyway (Java, version-based SQL scripts), Liquibase. Forward-only vs reversible migrations.
- Zero-downtime migrations (expand-contract): Phase 1: add new column (nullable), deploy code that writes to both. Phase 2: backfill data in batches. Phase 3: deploy code that reads from new column. Phase 4: remove old column. Each step is backward-compatible with the currently-running code.
- Dangerous operations: adding NOT NULL column without default (table rewrite — though modern PostgreSQL optimizes constant defaults), dropping column (coordinate with code), renaming column/table (breaks running code — use expand-contract instead), changing a column type (rewrite + lock), adding index without CONCURRENTLY (locks table), adding a foreign key (validates existing rows under lock — use `NOT VALID` then `VALIDATE`).
- `CREATE INDEX CONCURRENTLY`: non-blocking index creation. Takes longer but no table lock. Can fail (leaves invalid index — drop and retry). Always use for production.
- Lock-awareness: a migration that needs a brief `ACCESS EXCLUSIVE` lock can queue behind a long-running query and then block everything behind *it*. Use short `lock_timeout`/`statement_timeout` and retry.
- Data migrations: separate from schema migrations. Batch processing for large tables (avoid one giant transaction). Idempotent (re-runnable). Test with production-size data.
- Migration testing: run on copy of production data. Measure execution time. Test rollback. CI runs migrations against empty and seeded database.

**ORM Mastery**
- Django ORM: `QuerySet` is lazy (not evaluated until iterated). Chaining: `.filter()`, `.exclude()`, `.annotate()`, `.aggregate()`, `.values()`, `.order_by()`, `.distinct()`.
- `select_related`: SQL JOIN, one query. Use for ForeignKey, OneToOne. `prefetch_related`: separate query per relation, Python-side join. Use for ManyToMany, reverse FK.
- `Q` objects: complex queries with `|` (OR), `&` (AND), `~` (NOT). `F` expressions: reference model field values in queries (e.g., `filter(views__gt=F('likes') * 2)`) and do atomic updates (`F('balance') - 10`) to avoid lost updates.
- Annotations & aggregations: `annotate(total=Sum('amount'))` adds computed fields. `aggregate(avg=Avg('price'))` returns single result. Subquery, OuterRef for correlated subqueries.
- N+1 query detection: `django-debug-toolbar`, `nplusone` library. N+1: loop over queryset, each iteration triggers related query. Fix with `select_related`/`prefetch_related`. The single most common ORM performance bug.
- Bulk operations: `bulk_create`, `bulk_update`, `update()`/`delete()` on querysets (single SQL statement, but skip signals and `save()`). Use them for large data changes instead of per-row saves.
- SQLAlchemy: Core (SQL expression language, explicit) vs ORM (objects, Unit of Work pattern). Session scoping (one session per request/unit of work). `joinedload` (eager join), `selectinload` (eager separate query — usually best for collections), `lazyload` (on-access). 2.0 style: async support, type hints.
- Raw SQL escape hatches: Django `raw()`, `connection.cursor()`. SQLAlchemy `text()`. Use for complex queries ORM can't express. Always parameterize (never string format — SQL injection).
- The leaky abstraction: ORMs hide SQL but you still pay for it. Read the generated SQL (`.query`, echo) for hot paths; an ORM doesn't free you from understanding the database.

**Storing Money & Time Correctly**
- Money: never `float`/`double`. Use `NUMERIC`/`DECIMAL` (exact) or integer minor units (cents) with the currency stored alongside. Decide and document rounding rules. Sum/aggregate in the database with exact types.
- Timestamps: store `timestamptz` (PostgreSQL stores UTC internally and converts on the way out) rather than naive `timestamp`. Keep everything UTC; store the user's intended time zone separately if "9am local forever" semantics matter. Be explicit about server `timezone` setting.
- Enumerations/state: prefer constrained types (`CHECK`, enum types, or a reference table with FK) over free-text status columns.

**Connection & Resource Management**
- Connections are expensive and finite. Always pool (PgBouncer, SQLAlchemy pool, framework pool). Size the pool to the database's `max_connections`, not to your app's concurrency dreams — too many connections degrades the DB.
- Set timeouts at every layer: `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`, connection/socket timeouts, and pool checkout timeouts. Unbounded waits turn a slow query into a full outage.
- Serverless + traditional DBs = connection-pool exhaustion (each function instance opens connections). Use a proxy (RDS Proxy, PgBouncer) or a connection-less/serverless DB.

**Data Pipelines**
- ETL (Extract, Transform, Load) vs ELT (Extract, Load, Transform): ETL transforms before loading (traditional, limited by ETL tool). ELT loads raw then transforms in-place (modern, leverages destination power — dbt, BigQuery, Snowflake).
- Batch vs streaming: Batch (Airflow, Spark — process accumulated data periodically). Streaming (Kafka, Flink — process events as they arrive). Lambda architecture (both batch + speed layers). Kappa architecture (streaming only).
- Apache Kafka: distributed log. Topics (categories), partitions (parallelism, ordering within partition), consumer groups (load balancing). Retention policy (time or size based). Exactly-once semantics (idempotent producer + transactional consumer). Kafka Connect for data integration. Consumer offset management (commit after processing for at-least-once).
- CDC (Change Data Capture): capture database changes as events. Debezium (log-based CDC for PostgreSQL, MySQL, MongoDB → Kafka). Enables real-time replication, cache invalidation, search-index sync, event sourcing from existing databases without dual writes.
- Orchestration: Airflow (Python DAGs, scheduling, monitoring — mature but complex), Dagster (software-defined assets, better testing/typing), Prefect (Python-native, dynamic workflows).
- Data quality: Great Expectations / dbt tests (data validation framework, expectation suites, data docs). Schema validation. Null checks, uniqueness constraints, referential integrity. Alerting on quality failures.
- Data warehouse / lake / lakehouse: warehouse (structured, query-optimized — Snowflake, BigQuery, Redshift); data lake (raw files, cheap, schema-on-read — S3 + Parquet); lakehouse (table formats like Delta Lake/Iceberg/Hudi bringing ACID + schema to the lake). Medallion architecture: bronze (raw) → silver (cleaned) → gold (curated/marts).

**Dimensional Modeling (Analytics Schemas)**
- Star schema: a central fact table (measurable events — orders, clicks, with foreign keys + numeric measures) surrounded by dimension tables (descriptive context — date, customer, product). Optimized for analytical queries and BI tools.
- Snowflake schema: dimensions further normalized into sub-dimensions. More normalized, more joins; usually star is preferred for query simplicity/speed.
- Grain: define exactly what one fact row represents (one order line? one daily summary?) before anything else — getting the grain wrong poisons the whole model.
- Slowly Changing Dimensions (SCD): how to handle dimension attributes that change over time — Type 1 (overwrite, lose history), Type 2 (new row + validity dates, preserve history), Type 3 (keep previous value in a column). Type 2 is the common choice when history matters.

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
- Scaling reads vs writes: reads scale out easily (replicas, caches); writes are the hard part (single primary, coordination). Most "scaling" work is really about removing the single write bottleneck (sharding, async writes, batching).

**Data Partitioning & Sharding**
- Why shard: when a single database can't hold the data or serve the write throughput, split data across nodes. This is the big lever — and the one with the most operational pain, so delay it until vertical scaling + read replicas + caching are exhausted.
- Partitioning strategies: *range* (by key range — simple, supports range scans, but risks hotspots if data is skewed), *hash* (hash the key for even distribution — no range scans), *directory/lookup* (a lookup table maps keys → shards, flexible but adds a dependency), *geographic* (by region, for locality/compliance).
- Choosing a shard key: high cardinality, even access distribution, and aligned with your most common query (so a query hits one shard). Monotonic keys (auto-increment, timestamp) create write hotspots — the newest shard takes all traffic.
- Cross-shard pain: joins, transactions, and aggregations across shards are hard/expensive. Denormalize, do scatter-gather, or keep related data on the same shard (co-location by tenant/user).
- Resharding: splitting/rebalancing shards as you grow. Consistent hashing with virtual nodes minimizes data movement when adding/removing nodes. Pre-split / use logical shards mapped to physical nodes so you can move shards without rehashing everything.

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
- Cache stampede / thundering herd: many concurrent requests for same expired key. All hit DB simultaneously. Solutions: locking/single-flight (only one request loads, others wait), probabilistic early expiry (XFetch), stale-while-revalidate (serve stale while one request refreshes).
- Hot key / celebrity problem: one key (a viral post, a huge tenant) gets disproportionate traffic and overloads its single cache node/shard. Mitigate with local replication of the hot key, request coalescing, or splitting the key.
- CDN: cache static assets and API responses at edge locations. CloudFront, Cloudflare, Fastly. Cache-Control headers, cache key configuration, purge/invalidation API.
- Multi-tier: L1 (in-process, fastest, limited size), L2 (shared like Redis, larger), L3 (CDN, closest to users). Cache aside at each level.

**CAP Theorem & Consistency**
- CAP: during network partition, system must choose between Consistency (all nodes see same data) and Availability (all nodes respond). Can't have both. CP: refuse requests if can't guarantee consistency (PostgreSQL, HBase). AP: respond with potentially stale data (Cassandra, DynamoDB).
- PACELC: extension. If Partition: choose A or C. Else (normal operation): choose Latency or Consistency. Most systems sacrifice consistency for latency in normal operation.
- Eventual consistency: all replicas will converge to same state given enough time without updates. Acceptable for: social feeds, analytics, search. Not for: financial transactions, inventory.
- Read-your-writes / monotonic reads: useful intermediate guarantees — a user should at least see their own writes and never see time go backward. Often achieved by sticky routing to the primary briefly after a write.
- Quorums (N/R/W): with N replicas, require R nodes to agree on a read and W on a write. `W + R > N` guarantees read sees latest write (strong-ish consistency); tuning R/W trades latency vs consistency (Dynamo-style systems). `W = N` favors read availability; `R = N` favors write availability.
- Conflict resolution: Last-Write-Wins (simple but lossy), vector clocks (detect conflicts), CRDTs (Conflict-free Replicated Data Types — automatic conflict resolution for specific data structures: counters, sets, registers).
- Linearizability: strongest consistency. Operations appear atomic and ordered. As if single copy. Expensive (consensus protocol needed).
- Causal consistency: respects happens-before relationship. If A causes B, everyone sees A before B. Weaker than linearizable but cheaper.

### 6.2 Distributed Systems

**Consensus & Coordination**
- Raft: leader-based consensus. Leader election via randomized timeouts. Log replication to followers. Committed when majority acknowledges. Used by: etcd, Consul, CockroachDB. Easier to understand than Paxos.
- Split-brain: network partition separates cluster into groups that each think they're the leader. Prevention: quorum (majority needed for decisions), fencing (STONITH — Shoot The Other Node In The Head), fencing tokens (monotonic token rejected by stale holders).
- etcd / ZooKeeper / Consul: distributed key-value stores for configuration, service discovery, leader election, distributed locking. etcd (Kubernetes uses it), Consul (service mesh), ZooKeeper (Kafka, Hadoop).

**Time, Clocks & Ordering**
- Physical clocks drift and are not synchronized perfectly across nodes (NTP error is milliseconds, sometimes worse). Never assume two machines' wall clocks agree, and never order distributed events by comparing their timestamps.
- Logical clocks: Lamport timestamps give a total order consistent with causality (if A → B then L(A) < L(B), but not vice versa). Vector clocks capture true causality and can detect concurrent (conflicting) events — used for conflict detection in Dynamo-style stores.
- Hybrid Logical Clocks (HLC) / Google TrueTime: combine physical and logical time to get useful ordering with bounded uncertainty (Spanner waits out the uncertainty to provide external consistency).

**Distributed Unique IDs**
- Why not auto-increment: a single sequence is a coordination bottleneck and reveals volume; you can't generate IDs independently per shard/service.
- UUIDv4: random, no coordination, but poor index locality (random B-tree inserts) and 128 bits. UUIDv7 / ULID: time-prefixed so they sort roughly by creation time → much better insert locality while staying decentralized. Often the best default now.
- Snowflake IDs: 64-bit = timestamp + machine/worker ID + per-ms sequence. Roughly time-sortable, compact, no central coordinator (just unique worker IDs + synced-enough clocks). Used by Twitter/Discord/Instagram-style systems.
- Ticket servers / pre-allocated ranges: a central service hands out blocks of IDs that each node consumes locally — amortizes coordination.

**Distributed Locking & Coordination Primitives**
- Use cases: ensure a single worker runs a cron/compaction, prevent double-processing, serialize access to a resource.
- Implementations: PostgreSQL advisory locks, a Redis lock with a random token + expiry (lease) released only by the owner, or a lease in etcd/ZooKeeper. Always set an expiry so a crashed holder doesn't deadlock the system.
- Correctness caveat: locks with timeouts can't guarantee mutual exclusion if the holder pauses (GC, VM stall) past the lease — pair with fencing tokens that downstream resources can reject. Often the better design is to make the operation idempotent and avoid needing a strict lock at all.

**Service Communication Patterns**
- Synchronous: HTTP/gRPC. Simple request-response. Creates temporal coupling (caller waits). Cascading failures risk. Use for: user-facing requests needing immediate response.
- Asynchronous: message broker (Kafka, RabbitMQ). Decoupled in time. Retry built-in. Higher complexity. Use for: cross-service data propagation, background processing.
- Service discovery: client-side (client queries registry, Consul, eureka) vs server-side (load balancer queries registry, Kubernetes DNS). DNS-based (simple, caching issues) vs dedicated registry.
- Circuit breaker: states: Closed (requests pass through, failures counted), Open (requests fail fast, no calls to dependency), Half-Open (allow test requests, transition to closed or open). `tenacity` library in Python. Hystrix-style.
- Retry with exponential backoff + jitter: `retry_delay = base_delay * 2^attempt + random_jitter`. Jitter prevents thundering herd. Cap maximum delay. Set max retries. Idempotent operations only.
- Timeout budgets: propagate remaining time budget through call chain. If upstream has 5s budget and first call took 2s, downstream gets 3s. Prevents wasted work when budget is exhausted.
- Cascading-failure prevention: timeouts + circuit breakers + bulkheads + load shedding (reject early when overloaded) + backpressure together stop one slow dependency from taking down the whole system. A retry storm without these makes outages worse.

**Observability (Three Pillars)**
- Logs: what happened. Structured logging (JSON). Correlation IDs across services. Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL. Aggregate: ELK (Elasticsearch, Logstash, Kibana) or Loki.
- Metrics: how much/how often. Counters (total requests), Gauges (current connections), Histograms (response time distribution). Prometheus + Grafana. RED method: Rate, Errors, Duration. USE method: Utilization, Saturation, Errors.
- Traces: request flow across services. Distributed tracing with OpenTelemetry. Trace ID → Spans (one per service/operation). Visualize: Jaeger, Zipkin, Datadog, Honeycomb.
- SLI/SLO/SLA: SLI (indicator: latency p99 < 200ms), SLO (objective: 99.9% of requests meet SLI), SLA (agreement: contractual commitment with consequences). Error budgets: if SLO is 99.9%, error budget is 0.1%. Spend on feature velocity; when exhausted, focus on reliability.
- Always reason in percentiles, not averages: p50/p95/p99/p99.9. Averages hide tail latency, and tail latency is what users feel — especially with fan-out (a request touching 100 services hits the p99 of at least one).

### 6.3 Real-World System Design Examples

**A Reusable Framework**
- Clarify requirements & scope (functional + non-functional: consistency, latency, availability targets). Estimate scale (QPS, data size, read:write ratio). Define the API. Sketch the high-level data flow. Choose data storage & schema. Address bottlenecks (caching, sharding, async). Discuss trade-offs and failure modes. State assumptions out loud.

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

**News Feed / Timeline**
- The core tension: *fan-out on write* (push) — when a user posts, write the post into every follower's precomputed feed (fast reads, expensive writes, terrible for celebrities with millions of followers). vs *fan-out on read* (pull) — assemble the feed at read time by querying followees (cheap writes, expensive reads).
- Hybrid (the real-world answer): push for normal users; for celebrity accounts, pull their posts at read time and merge with the precomputed feed. Avoids the "celebrity fan-out" blowup.
- Storage: feed as a list of post IDs per user in Redis (capped); posts and media stored separately and hydrated on read. Rank by recency or a relevance score.
- Scale: feed generation workers consume a post-created stream; cache hot feeds; paginate with cursors. Accept eventual consistency (a new post appearing a few seconds late is fine).

**Typeahead / Search Autocomplete**
- Data structure: a trie (prefix tree) of popular queries with frequency/weights at nodes; return top-k completions for a prefix. Precompute and cache the top-k per prefix node so reads are O(prefix length).
- Pipeline: aggregate query logs offline → build/refresh the trie (or a prefix→suggestions map in Redis) periodically → serve from an in-memory/edge cache. Debounce client requests; cap latency hard (suggestions must feel instant).
- Ranking: blend frequency, recency, personalization. Handle typos (edit distance / fuzzy) and filter inappropriate suggestions. For full search, this sits in front of an inverted index (Elasticsearch).

**Proximity / Geo Service (ride-share, "nearby")**
- Problem: efficiently answer "what's near (lat, lng) within R?" over millions of moving points without scanning everything.
- Spatial indexing: geohash (encode lat/lng into a string prefix where shared prefix ≈ nearby — easy to shard and query by prefix), quadtrees, S2 cells (Google), or H3 hexagons (Uber). PostGIS / Redis GEO commands implement this for you.
- Live location: drivers publish location updates to a stream; an in-memory geo-index (e.g., Redis GEO per cell) holds current positions with TTL. Matching service queries nearby cells. Shard by region; handle cell boundaries by querying neighbors.

**Object Storage / File Upload Service**
- Don't proxy large files through your app servers. Use pre-signed URLs: the client requests permission, your backend returns a time-limited signed URL, and the client uploads/downloads directly to/from object storage (S3/GCS). Saves bandwidth and scales effortlessly.
- Large files: multipart upload (parallel chunks, resumable). Store only metadata + the object key in your database. Serve via CDN with signed URLs for access control.
- Integrity & dedup: content hashes (ETags) for deduplication and verification. Lifecycle policies for tiering (hot → cold → archive) and expiry. Virus scanning / validation on upload (out of band).

**Payment / Wallet System (consistency-critical)**
- Correctness over availability here: use a relational DB with ACID transactions for the ledger; money must never be created or destroyed.
- Double-entry ledger: record immutable debit/credit entries that always balance, rather than mutating a single balance field. Balance is derived (or a maintained materialized total reconciled against entries). Gives a full audit trail.
- Idempotency is mandatory: every charge/transfer carries a client-generated idempotency key; the server stores the result and returns the same outcome on retry — networks and clients *will* retry. Prevents double charges.
- Distributed flows: coordinating payment + inventory + shipping across services uses a saga with compensating transactions (refund/cancel), not a distributed 2PC. Handle webhook callbacks from payment providers idempotently and verify their signatures.
- Exactly-once effects: achieved via idempotency keys + dedup + the outbox pattern, never by assuming the network delivers exactly once.

**Distributed Cache / Key-Value Store**
- Partition keys across nodes with consistent hashing (virtual nodes for balance); replicate each key to N nodes for fault tolerance.
- Tunable consistency via quorum reads/writes (`R + W > N`). Eviction policy (LRU/LFU) per node; TTLs for freshness.
- Failure handling: replica failover, hinted handoff for temporarily-down nodes, anti-entropy/read-repair to reconcile divergent replicas. This is essentially the Dynamo design and underlies Redis Cluster / Memcached fleets / DynamoDB.

### 6.4 Capacity & Estimation

**Back-of-Envelope Numbers**
- Time: 1 day ≈ 86,400 s ≈ 100K s. So 1M requests/day ≈ 12 req/s; 1B/day ≈ 12K req/s. Always convert "per day" to "per second" to reason about load.
- Latency ladder (orders of magnitude): L1 cache ~1ns, main memory ~100ns, SSD random read ~100μs, intra-datacenter round trip ~0.5ms, disk seek ~10ms, cross-continent round trip ~100-150ms. These dictate where you can afford to put data.
- Storage: 1B records × 1KB = 1TB. Plan 3-5 years of growth × replication factor. Account for indexes and overhead (often 2-3×).
- Powers of 2: 2^10 ≈ 1K, 2^20 ≈ 1M, 2^30 ≈ 1B, 2^40 ≈ 1T. Bandwidth, QPS, and storage estimates all lean on these.
- Read:write ratio and peak:average ratio drive the design — size for peak (often 2-5× average), and let the dominant operation (usually reads) decide your caching/replication strategy.

---
## 7. Infrastructure & DevOps

### 7.1 Containers

**Docker Fundamentals**
- Image vs container: an image is an immutable, layered filesystem + metadata; a container is a running (or stopped) instance of an image with a writable top layer. Images are built once and run anywhere the runtime exists.
- Layers & caching: each Dockerfile instruction creates a layer. Layers are cached and shared between images. Order instructions from least- to most-frequently-changing (copy dependency manifests and install deps before copying source) so a code change doesn't bust the dependency-install cache.
- Dockerfile best practices: use specific base image tags (not `latest`), minimize layers, combine `RUN` commands with `&&`, clean up package caches in the same layer, use `.dockerignore`, run as a non-root user, set a `HEALTHCHECK`, and prefer `COPY` over `ADD`.
- Multi-stage builds: build artifacts in a heavy builder stage, copy only the result into a minimal runtime stage. Dramatically smaller, more secure final images (no compilers/build tools shipped).
- Base image choice: `distroless` or `alpine` for small/secure images (alpine uses musl libc — watch for compatibility issues with some Python wheels); slim Debian images for broad compatibility.
- Image size: smaller images pull faster, have a smaller attack surface, and cost less to store. Audit with `docker history` / `dive`.
- Security: scan images (Trivy, Grype, Snyk), pin digests, drop capabilities, read-only root filesystem, no secrets baked into layers (they persist even if deleted in a later layer — use build secrets/mounts).
- Registries: Docker Hub, GitHub Container Registry, AWS ECR, GCR. Tag with immutable identifiers (git SHA) in addition to semantic tags. Sign images (cosign) for supply-chain integrity.

**Container Runtime**
- The OCI (Open Container Initiative) standard separates image format and runtime. `containerd` and CRI-O are common runtimes; Docker now uses containerd under the hood.
- Resource isolation comes from cgroups (limits) + namespaces (isolation), as covered in the OS section. A container is just a process with restricted visibility and resources — not a VM.
- Containers should be ephemeral and stateless: persist data in volumes or external services, log to stdout/stderr, and handle SIGTERM for graceful shutdown.

### 7.2 Orchestration (Kubernetes)

**Core Objects**
- Pod: the smallest deployable unit — one or more co-located containers sharing network and storage. Usually one main container per pod (+ sidecars).
- Deployment: declarative management of stateless pods via ReplicaSets. Handles rolling updates and rollbacks. Desired state reconciliation.
- StatefulSet: for stateful workloads needing stable network identity and persistent storage (databases, queues). Ordered, stable pod names.
- DaemonSet: one pod per node (log collectors, monitoring agents). Job/CronJob: run-to-completion and scheduled tasks.
- Service: stable virtual IP + DNS name load-balancing across a set of pods (ClusterIP internal, NodePort, LoadBalancer external). Decouples clients from ephemeral pod IPs.
- Ingress / Gateway API: L7 HTTP routing into the cluster (host/path rules, TLS termination) via an ingress controller (nginx, Traefik, Envoy).
- ConfigMap & Secret: externalized configuration and sensitive data, mounted as env vars or files. Secrets are base64-encoded (not encrypted) by default — enable encryption at rest and use external secret managers for real security.
- Namespace: virtual cluster partition for multi-tenancy, quotas, and access control.

**Operations**
- Resource requests & limits: requests drive scheduling; limits cap usage. CPU limits throttle; memory limits OOM-kill. Setting requests well is essential for bin-packing and stability.
- Health probes: liveness (restart if unhealthy), readiness (remove from service endpoints until ready), startup (protect slow-starting apps). Misconfigured probes cause restart loops or routing traffic to not-ready pods.
- Autoscaling: Horizontal Pod Autoscaler (scale replicas on CPU/memory/custom metrics), Vertical Pod Autoscaler (adjust requests), Cluster Autoscaler (add/remove nodes). KEDA for event-driven scaling (queue depth).
- Scheduling: node selectors, affinity/anti-affinity, taints and tolerations, topology spread constraints, pod disruption budgets (limit voluntary disruptions during maintenance).
- Storage: PersistentVolume / PersistentVolumeClaim / StorageClass for dynamic provisioning.
- Helm: package manager for Kubernetes (templated, versioned charts). Kustomize: template-free overlay-based config. Operators: encode operational knowledge for stateful apps via custom resources + controllers.
- GitOps: declarative cluster state in Git, reconciled automatically by Argo CD or Flux. Git is the single source of truth; the cluster converges to match.

### 7.3 CI/CD

**Pipelines**
- Continuous Integration: every push triggers build + automated tests + linting + type checks + security scans, catching issues early. Keep the main branch always releasable.
- Continuous Delivery vs Deployment: delivery keeps every change deployable with a manual promotion gate; deployment pushes every passing change to production automatically.
- Pipeline stages: checkout → build → unit tests → integration tests → static analysis/security scan → build artifact/image → deploy to staging → smoke tests → promote to production. Fail fast; cache dependencies; run independent stages in parallel.
- Tools: GitHub Actions, GitLab CI, CircleCI, Jenkins, Buildkite. Keep pipeline config in the repo (pipeline-as-code).
- Artifacts: build once, promote the same immutable artifact/image through environments. Never rebuild per environment (config comes from the environment, per 12-factor).

**Deployment Strategies**
- Rolling update: gradually replace old instances with new. Default in Kubernetes. Zero downtime if readiness probes and backward-compatible changes are in place.
- Blue-green: run two identical environments; switch traffic from blue (old) to green (new) instantly; roll back by switching back. Doubles infrastructure briefly.
- Canary: release to a small percentage of traffic/users, watch metrics, then ramp up. Catches problems with limited blast radius. Automated canary analysis compares error/latency against baseline.
- Feature flags: decouple deploy from release. Ship code dark, enable per user/segment, kill instantly without redeploy. Enables trunk-based development, A/B testing, and gradual rollouts. Manage flag debt (remove stale flags).
- Database changes must be backward-compatible (expand-contract) so old and new code can run simultaneously during a rollout.

### 7.4 Infrastructure as Code

- Declarative provisioning: describe desired infrastructure; the tool computes and applies the diff. Reproducible, reviewable, version-controlled environments.
- Terraform / OpenTofu: cloud-agnostic, declarative. State file tracks managed resources (store remotely + locked — never commit it). Modules for reuse. `plan` before `apply`. Beware state drift.
- Pulumi: IaC in general-purpose languages (Python, TypeScript). CloudFormation/CDK: AWS-native.
- Ansible: agentless configuration management over SSH (idempotent playbooks) — good for provisioning and config, less for full lifecycle state.
- Immutable infrastructure: replace servers rather than patching them in place (bake images with Packer, redeploy). Eliminates configuration drift and "works on that one server" mysteries.
- Environment parity & secrets: keep dev/staging/prod as similar as practical; inject secrets from a manager (not in state files or repos).

### 7.5 Operating in Production

- Observability recap (see 6.2): structured logs, metrics (RED/USE), distributed traces, correlated by request/trace IDs. Dashboards for the golden signals: latency, traffic, errors, saturation.
- Alerting: alert on symptoms users feel (SLO burn, elevated error rate) not every cause; make alerts actionable; avoid alert fatigue. Page only on things that need a human now.
- Error tracking & APM: Sentry-style aggregation (group, dedupe, track release health), and APM (Datadog, New Relic, Honeycomb) for latency breakdowns and span-level traces.
- On-call & runbooks: clear ownership, escalation policy, runbooks for common incidents, and dashboards linked from alerts.
- Capacity & cost: monitor utilization and saturation; right-size resources; understand the cost of your architecture (FinOps) — over-provisioning is common waste.

---

## 8. Security

### 8.1 OWASP Top 10 & Common Vulnerabilities

- Injection (SQL, NoSQL, command, LDAP): untrusted input interpreted as code/query. Defense: parameterized queries/prepared statements, ORM query builders, never string-concatenate input into queries or shell commands, allow-list validation.
- Broken authentication: weak password policies, no MFA, session fixation, predictable tokens. Defense: strong hashing (argon2/bcrypt), MFA, secure session management, account lockout/rate limiting on login.
- Broken access control: missing authorization checks, IDOR (insecure direct object references — accessing `/orders/123` you don't own). Defense: enforce authorization on every request server-side, default deny, scope every query by the current user/tenant.
- Cross-Site Scripting (XSS): injecting scripts into pages. Stored, reflected, DOM-based. Defense: context-aware output encoding, Content-Security-Policy, framework auto-escaping, sanitize HTML input.
- Cross-Site Request Forgery (CSRF): tricking a logged-in user's browser into making unwanted requests. Defense: CSRF tokens, `SameSite` cookies, check Origin/Referer for state-changing requests.
- SSRF (Server-Side Request Forgery): tricking the server into making requests to internal resources (e.g., cloud metadata endpoint). Defense: allow-list outbound destinations, block link-local/internal ranges, no user-controlled URLs to internal services.
- Insecure deserialization: untrusted data deserialized into objects (Python `pickle` RCE). Defense: never deserialize untrusted data with unsafe formats; use JSON/schema-based formats.
- Security misconfiguration: default credentials, verbose errors, unnecessary services, missing hardening. Defense: secure defaults, least privilege, automated configuration scanning.
- Vulnerable dependencies: known CVEs in libraries. Defense: dependency scanning (Dependabot, Snyk, `pip-audit`), keep dependencies updated, SBOMs.
- Insufficient logging & monitoring: attacks go undetected. Defense: log security-relevant events (authn/authz failures, privilege changes), alert on anomalies, protect logs from tampering.

### 8.2 Input Validation & Hardening

- Validate at the boundary: parse untrusted input into typed, validated objects (Pydantic/serializers) before it reaches business logic ("parse, don't validate"). Allow-list over deny-list.
- Output encoding: encode for the destination context (HTML, attribute, JS, URL, SQL). Let the framework/template engine auto-escape.
- Security headers: `Content-Security-Policy` (mitigate XSS), `Strict-Transport-Security` (HSTS, force TLS), `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors` (clickjacking), `Referrer-Policy`, `Permissions-Policy`.
- Rate limiting & abuse prevention: throttle by IP/user/key, CAPTCHA where appropriate, bot detection, account-takeover protections.
- File uploads: validate type/size, store outside the web root or in object storage, never trust the filename, scan content, serve with correct content-type and `Content-Disposition`.

### 8.3 Secrets Management

- Never commit secrets to source control. Scan for leaked secrets (gitleaks, detect-secrets, pre-commit hooks). Rotate anything that leaks.
- Secret stores: HashiCorp Vault, AWS Secrets Manager / Parameter Store, GCP Secret Manager, Kubernetes external-secrets. Inject at runtime via env or mounted files.
- Rotation: rotate credentials regularly and on compromise; prefer short-lived, dynamically-issued credentials (Vault dynamic secrets, cloud IAM roles / workload identity) over long-lived static keys.
- Least privilege for machine identities: scope IAM roles tightly; prefer role assumption / workload identity over distributing static keys.
- Separate config from secrets (12-factor): both come from the environment, but secrets need stricter handling (encryption, access audit, rotation).

### 8.4 Cryptography Fundamentals

- Password hashing: use a slow, salted, memory-hard KDF — argon2id (preferred), bcrypt, or scrypt. Never use fast general-purpose hashes (MD5/SHA) for passwords. Per-user salt is built in; tune work factors.
- Symmetric vs asymmetric: symmetric (AES-GCM) is fast, one shared key — for bulk encryption. Asymmetric (RSA, ECC) uses key pairs — for key exchange, signatures, and identity. Hybrid systems use asymmetric to exchange a symmetric key.
- Hashing vs encryption vs encoding: hashing is one-way (integrity, fingerprints), encryption is reversible with a key (confidentiality), encoding (base64) is neither — not security.
- HMAC: keyed hash for message authentication/integrity (webhook signatures, token signing). Verify with constant-time comparison to avoid timing attacks.
- Digital signatures: prove authenticity + integrity using a private key, verified with the public key (JWT RS256/ES256, package signing).
- Nonces / IVs: never reuse a nonce/IV with the same key (catastrophic for many ciphers). Use AEAD modes (AES-GCM, ChaCha20-Poly1305) that combine encryption + authentication.
- Randomness: use a cryptographically secure RNG (`secrets` module in Python, not `random`) for tokens, keys, salts.
- Key management: store keys in a KMS/HSM, rotate them, separate key-encryption keys from data-encryption keys (envelope encryption), and limit access.
- TLS (see networking): encrypt data in transit everywhere, including internal service-to-service (mTLS).

### 8.5 Compliance & Privacy

- Data classification: know what personal/sensitive data you hold, where it lives, and who can access it. Minimize collection and retention.
- GDPR / CCPA: lawful basis, consent, data subject rights (access, deletion/"right to be forgotten", portability), breach notification, data residency. "Soft delete everywhere" can conflict with deletion requirements — plan for hard erasure.
- PCI-DSS: handling card data — prefer tokenization and never store raw PANs/CVVs; scope reduction by using a payment provider.
- SOC 2 / ISO 27001: control frameworks (access control, change management, monitoring, incident response) demonstrated via audits.
- Auditability: immutable audit logs of sensitive actions; encryption at rest and in transit; documented data flows.
- Privacy by design: bake privacy into architecture (data minimization, purpose limitation, encryption, access controls) rather than bolting it on.

---

## 9. Testing Strategy

### 9.1 The Test Pyramid

- Unit tests: many, fast, isolated — test a single function/class with dependencies stubbed. The base of the pyramid. Should run in milliseconds and give precise failure localization.
- Integration tests: fewer, slower — test components working together (code + real database, code + queue). Catch wiring/contract issues unit tests miss. Use containers (Testcontainers) or a real test DB.
- End-to-end tests: fewest, slowest, most brittle — exercise the whole system through its external interface. Reserve for critical user journeys.
- Anti-pattern — the "ice cream cone" / inverted pyramid: too many slow E2E tests and too few unit tests → slow, flaky suites. Push coverage down the pyramid.
- The "testing trophy" view emphasizes integration tests for confidence-per-cost in modern apps; the right shape depends on your architecture.

### 9.2 Test Design

- Arrange-Act-Assert (AAA): set up state, perform the action, assert the outcome. One logical assertion/behavior per test. Clear, descriptive test names (what + condition + expected result).
- Fixtures & factories: build test data with factories (factory_boy) rather than brittle hand-built dicts; use fixtures for shared setup/teardown with appropriate scope.
- Test doubles: dummy, stub (canned responses), spy (records calls), mock (pre-programmed with expectations), fake (working lightweight implementation, e.g., in-memory repository). Mock at architectural boundaries (I/O, external services), not your own internals.
- Don't over-mock: mocking everything tests your mocks, not your code, and couples tests to implementation. Prefer real objects/fakes where cheap.
- Coverage: branch coverage is more meaningful than line coverage, but coverage is a guide, not a goal — 100% coverage of trivial code with no edge-case tests is false confidence. Test behavior and edge cases, not lines.
- Determinism: no dependence on real time (freeze it), network, randomness (seed it), or test ordering. Flaky tests erode trust — quarantine and fix them.
- Property-based testing (Hypothesis): assert invariants over generated inputs to find edge cases you wouldn't think of; it shrinks failures to minimal cases.

### 9.3 Integration & Contract Testing

- Database tests: run against a real engine (same as production) in a transaction rolled back per test, or a disposable container. SQLite-as-stand-in hides engine-specific behavior.
- External services: use fakes/sandboxes or record-replay (VCR-style) rather than hitting real third parties in CI.
- Contract testing: verify that a service and its consumers agree on the API contract (Pact, schema validation against OpenAPI/AsyncAPI). Prevents integration breakage in microservices without full E2E. Consumer-driven contracts let consumers specify expectations the provider verifies.

### 9.4 Performance & Load Testing

- Load testing: simulate expected traffic to validate capacity (Locust, k6, Gatling, JMeter). Measure throughput and latency percentiles (p50/p95/p99), not just averages.
- Stress testing: push beyond expected load to find the breaking point and observe failure behavior (graceful degradation vs collapse).
- Soak/endurance testing: sustained load over hours/days to reveal leaks, resource exhaustion, and degradation.
- Spike testing: sudden surges to validate autoscaling and backpressure.
- Profiling under load: find the actual bottleneck (CPU, DB, locks, GC) before optimizing. Establish baselines and watch for regressions in CI.

### 9.5 Testing in Production (Safely)

- Some things can only be validated in production: real traffic patterns, data scale, and third-party behavior.
- Techniques: canary releases + automated analysis, feature flags for gradual rollout and instant kill, shadow/dark traffic (mirror real requests to a new version without affecting users), synthetic monitoring (scripted probes of critical paths).
- Strong observability + fast rollback is the safety net that makes this responsible. Define and watch SLOs; spend the error budget deliberately.
- Chaos engineering: deliberately inject failures (kill nodes, add latency, drop dependencies) in controlled experiments to verify resilience. Run game days. Define RTO/RPO and test disaster recovery for real.

---
## 10. Senior / Architect Mindset

### 10.1 Decision-Making & Trade-offs

- Engineering is the art of trade-offs under constraints: there is rarely a "best" choice, only the right choice for this context (scale, team, timeline, cost, risk). Make the trade-offs explicit.
- Architecture Decision Records (ADRs): short, versioned documents capturing a significant decision — context, options considered, decision, and consequences. They preserve the "why" for future engineers and prevent re-litigating settled questions.
- RFC / design-doc process: write the design before building anything non-trivial; circulate for feedback. Surfaces objections and alternatives cheaply (before code).
- Reversible vs irreversible decisions ("one-way vs two-way doors"): move fast on reversible choices, deliberate carefully on hard-to-undo ones (data model, public API, vendor lock-in).
- Prefer boring technology: the cost of operating, hiring for, and debugging exotic tech is usually underestimated. Spend your "innovation tokens" where they create real differentiation.
- Constraints first: clarify functional and non-functional requirements (consistency, latency, availability, cost, compliance) before choosing a solution.

### 10.2 Technical Debt

- Technical debt is the implied cost of choosing an expedient solution now over a better one. Some debt is deliberate and prudent (ship to learn); some is reckless or accidental. Name which kind you're taking on.
- Make debt visible: track it, attach it to its cost (what it slows down or risks), and pay it down continuously rather than in mythical "rewrite" projects.
- Refactor under test coverage and in small, safe steps. Boy-scout rule: leave code a little better than you found it. Avoid big-bang rewrites — they're high-risk and frequently fail.
- Distinguish debt from poor quality: not all old code is debt; debt is specifically what's costing you now or will predictably cost you soon.

### 10.3 Code Review

- Purpose: catch defects, share context, maintain consistency, and teach — not to demonstrate cleverness or enforce personal style.
- Review for correctness, design, readability, tests, security, and edge cases. Automate style/formatting/linting so humans focus on substance.
- Be kind and specific: critique the code, not the person; ask questions; explain the "why"; distinguish blocking issues from suggestions ("nit:"). Approve when it's better than the status quo, not when it's perfect.
- Keep PRs small and focused — they get better reviews and merge faster. Large PRs get rubber-stamped.

### 10.4 Estimation & Back-of-the-Envelope

- Estimate to support decisions, not to predict the future precisely. Communicate ranges and assumptions, not false-precision single numbers.
- Back-of-the-envelope math (see 6.4): convert per-day to per-second, use the latency ladder and powers of two, size storage with growth + replication. A quick estimate often rules out a design before you build it.
- Break work down; estimate the pieces; account for the unknowns (integration, testing, review, deployment, the "long tail"). Track estimate vs actual to calibrate over time.

### 10.5 Incident Management

- Incident response roles: incident commander (coordinates), communications lead, and responders. Mitigate first (stop the bleeding), diagnose root cause after.
- Blameless postmortems: focus on systemic causes and contributing factors, not individuals. People act reasonably given the information and tools they had; fix the system, not the human.
- Write up timeline, impact, root cause, what went well/poorly, and concrete action items with owners. Track action items to completion — a postmortem with no follow-through is theater.
- Reduce MTTR (mean time to recovery): good observability, runbooks, fast rollback, and practiced response matter more than trying to prevent every possible failure.

### 10.6 Technology Evaluation

- Evaluate against your actual requirements and constraints, not hype or résumé-driven development. Build a small spike/proof-of-concept for risky choices.
- Consider total cost of ownership: operational burden, observability, hiring/learning curve, community/maturity, licensing, lock-in, and exit cost — not just the happy-path feature set.
- "Build vs buy vs adopt": prefer managed services and proven open source for undifferentiated heavy lifting; build what is core to your value.
- Beware adding new datastores/languages/frameworks: each is a permanent operational commitment. Consolidate where you can.

---

## 11. Django & Web Framework Knowledge

### 11.1 Request/Response Lifecycle

- WSGI/ASGI server (gunicorn/uvicorn) receives the request → middleware stack (top-down on request) → URL resolver → view → response → middleware (bottom-up on response). Understanding the order is key to debugging auth, sessions, and CORS.
- Middleware: cross-cutting concerns (authentication, sessions, CSRF, security headers, GZip, common). Order matters. Write custom middleware for request-scoped context (request IDs, timing).
- Views: function-based (explicit, simple) vs class-based (reusable via mixins, generic views for CRUD). Keep views thin — push business logic into a service layer.

### 11.2 ORM (Django)

- See chapter 4 for ORM depth. Django uses the Active Record pattern (models persist themselves). QuerySets are lazy and chainable.
- Avoid the N+1 problem with `select_related` (FK/OneToOne via JOIN) and `prefetch_related` (M2M/reverse FK via a second query). Use `only()`/`defer()`/`values()` to limit columns.
- Use `F()` expressions for atomic updates (avoid lost updates), `Q()` for complex lookups, and `annotate()`/`aggregate()` to push computation into SQL.
- Bulk operations (`bulk_create`, `bulk_update`, queryset `update()`/`delete()`) for large changes — but they skip `save()` and signals.
- Migrations: review generated SQL, apply expand-contract for zero-downtime, and create indexes concurrently in production (via custom migration operations / `AddIndexConcurrently`).
- Transactions: `transaction.atomic()` (as decorator or context manager). Avoid slow external calls inside atomic blocks; use `select_for_update()` for pessimistic locking; use `on_commit()` hooks to fire side effects only after commit (e.g., enqueueing tasks).

### 11.3 Django REST Framework (DRF)

- Serializers: validate and transform between models and JSON; act as DTOs and your API contract. `ModelSerializer` for convenience; explicit serializers for control. Validate at this boundary.
- ViewSets + routers: concise CRUD endpoints; `APIView`/generic views when you need more control.
- Authentication classes (session, token, JWT) and permission classes (per-view and object-level). Enforce object-level permissions to prevent IDOR.
- Throttling, pagination (cursor pagination for large/changing datasets), filtering, and versioning (URL or header-based).
- Schema generation: produce OpenAPI (drf-spectacular) for docs and generated clients — contract-first benefits.

### 11.4 Async & Real-Time Django

- Django supports async views and an async ORM interface; mixing sync and async requires care (`sync_to_async`/`async_to_sync`). Don't call blocking code in async views.
- Django Channels: WebSockets and background consumers over ASGI, with a channel layer (Redis) for cross-process messaging — for chat, notifications, live updates.
- For most background work, offload to a task queue (Celery) rather than doing it in the request path.

### 11.5 Performance

- Caching: per-view and template-fragment caching, the low-level cache API, and `cached_property`. Cache expensive queries/aggregations; invalidate carefully. Use Redis as the cache backend.
- Database: connection pooling (`CONN_MAX_AGE`, PgBouncer), read replicas via a database router, and query optimization (see chapter 4). Profile with django-debug-toolbar / Silk.
- Pagination and `iterator()`/chunking for large result sets to avoid loading everything into memory.
- Static/media: serve via CDN and object storage (WhiteNoise for simple static, S3 for media); never serve large files through Django itself.

### 11.6 Security (Built-in Protections)

- Django provides strong defaults: ORM parameterization (SQL injection), template auto-escaping (XSS), CSRF middleware, clickjacking protection, and security middleware for HSTS/secure cookies/SSL redirect.
- Keep `DEBUG = False` in production, set `ALLOWED_HOSTS`, configure `SECRET_KEY` from the environment, and enable secure cookie flags (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SameSite`).
- Use the auth framework's password hashers (argon2 available), permissions, and `login_required`/permission decorators/mixins. Don't reinvent auth.

### 11.7 Background Tasks (Celery)

- Celery for asynchronous/scheduled work (emails, report generation, integrations). Broker (Redis/RabbitMQ) + result backend. Beat for periodic tasks.
- Design tasks to be idempotent (they can be retried/redelivered), keep payloads small (pass IDs, not objects), set time limits, and configure retries with backoff.
- Fire tasks from `transaction.on_commit()` so you never enqueue work referencing data that later rolls back. Monitor with Flower; route long/heavy tasks to dedicated queues/workers.

---

## 12. Soft Skills & Career Growth

### 12.1 Communication

- Writing is the highest-leverage skill for senior engineers: design docs, ADRs, postmortems, and clear PR descriptions scale your thinking across people and time.
- Tailor to the audience: lead with the conclusion and the "so what" for stakeholders; provide depth for engineers. Make the ask explicit.
- Asynchronous, written-first communication scales better than meetings for distributed teams — and creates a durable record.
- Communicate status honestly and early, especially bad news. Surface risks and blockers before they become crises.

### 12.2 Collaboration & Mentorship

- Strong teams beat strong individuals. Share context generously, document decisions, and reduce bus-factor risk.
- Mentorship multiplies your impact: pair, review thoughtfully, and create space for others to grow (delegate meaningful work, not just scraps).
- Give feedback that is specific, timely, and kind; receive it without defensiveness. Assume good intent.
- Psychological safety — the ability to ask questions, admit mistakes, and disagree — is what makes teams learn and ship reliably.

### 12.3 Career Ladders & Scope

- The IC track continues past senior: staff, principal, distinguished — defined by scope of impact and ambiguity handled, not lines of code. The management track is a different job, not a promotion.
- Levels broadly map to scope: execute a task → own a project → own a system/team's area → influence org-wide direction. Impact, not effort, is what's rewarded at senior levels.
- Seniority means multiplying others' effectiveness, owning outcomes (not just tasks), navigating ambiguity, and making good decisions with incomplete information.

### 12.4 Influence & Ownership

- Influence without authority: build trust through reliable delivery, persuade with data and clear writing, and align proposals with others' goals. You rarely get to mandate; you get to convince.
- Ownership: take responsibility for outcomes end-to-end, including operations and failure. "Not my code" is not a senior attitude.
- Manage up and sideways: make your manager's and peers' jobs easier; bring solutions and trade-offs, not just problems.
- Pick your battles: disagree-and-commit when a decision goes against you but isn't catastrophic; reserve strong pushback for genuinely high-stakes calls.

### 12.5 Continuous Learning

- The field changes constantly; durable fundamentals (the contents of this document) matter more than any specific framework. Invest in fundamentals; learn tools as needed.
- Learn by building, reading code, writing, and teaching. Depth in something plus broad working knowledge ("T-shaped") is a strong profile.
- Avoid both résumé-driven development (chasing shiny tech) and stagnation. Be deliberate: learn what serves your goals and your systems.
- Protect against burnout: sustainable pace, boundaries, and rest are part of a long career, not the opposite of productivity.

---

*This is a living document. Treat it as a map, not the territory — every principle here bends to context, and the senior skill is knowing when. Revisit and revise it as you learn.*
