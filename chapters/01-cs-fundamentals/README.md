# Chapter 1: Computer Science Fundamentals

This chapter covers the foundational computer science concepts that every backend engineer needs to master. From data structures and algorithms that underpin efficient software, to operating system internals that govern how your code actually runs, to networking protocols that connect your services to the world -- these fundamentals form the bedrock upon which all backend systems are built.

## Table of Contents

### [1.1 Data Structures](data-structures.md)
The building blocks of efficient software. Covers arrays, linked lists, circular buffers, hash tables (including Python dict internals and consistent hashing), trees (BST, B-Trees, heaps, tries, segment trees), graphs (representations, BFS, DFS, Dijkstra, topological sort, MST), and advanced structures (skip lists, Bloom filters, HyperLogLog, LRU caches, Union-Find).

**Key topics:** Arrays vs linked lists, hash collisions and load factors, B-Tree database indexes, priority queues, graph traversal and shortest paths, probabilistic data structures, cache eviction strategies.

### [1.2 Algorithms & Complexity](algorithms-and-complexity.md)
The analytical tools for reasoning about performance and scalability. Covers Big-O analysis (complexity classes, amortized analysis, space-time tradeoffs, Master Theorem), sorting (comparison-based sorts, non-comparison sorts, stability, Timsort, external sorting), dynamic programming (memoization, tabulation, classic patterns like knapsack and edit distance, state machine DP, bitmask DP), extended graph algorithms (Floyd-Warshall, network flow, Eulerian paths), and string algorithms (KMP, Rabin-Karp, Aho-Corasick, suffix arrays).

**Key topics:** Complexity class intuition, quicksort vs merge sort tradeoffs, Python's Timsort, DP problem-solving patterns, all-pairs shortest paths, pattern matching algorithms.

### [1.3 Operating Systems](operating-systems.md)
How your code runs on real hardware. Covers processes and threads (GIL, multiprocessing, asyncio, coroutines, IPC, copy-on-write, green threads), memory management (virtual memory, TLB, stack vs heap, Python's garbage collector, mmap, OOM killer), I/O models (blocking, non-blocking, epoll/kqueue, io_uring, zero-copy I/O, page cache), file systems (inodes, journaling, filesystems comparison, disk I/O patterns), and Linux fundamentals (signals, cgroups, namespaces, systemd, debugging tools, netfilter).

**Key topics:** When to use threads vs processes vs asyncio in Python, Python memory management and GC tuning, epoll-based event loops, container isolation with cgroups and namespaces, systemd service management, production debugging with strace and perf.

### [1.4 Networking](networking.md)
The protocols and tools that connect distributed systems. Covers TCP/IP (three-way handshake, flow and congestion control, TCP tuning, socket buffers, TCP vs UDP), HTTP (HTTP/1.1, HTTP/2 multiplexing, HTTP/3 and QUIC, caching headers, important headers), DNS (recursive resolution, record types, TTL strategies, DNS-based load balancing, split-horizon DNS, DNSSEC), TLS/SSL (TLS 1.3 handshake, certificate chains, mTLS, OCSP stapling, Let's Encrypt, SNI), and network debugging (tcpdump, curl, traceroute/mtr, ss, dig, MTU and fragmentation).

**Key topics:** TCP performance tuning (NODELAY, TIME_WAIT, keep-alive), HTTP/2 and HTTP/3 advantages, cache-control headers, DNS migration strategies, TLS 1.3 and mTLS for microservices, essential network debugging tools.

---

## Homework

Hands-on exercises for this chapter -- see [homework/questions.md](homework/questions.md). Skeleton files (`hw_*.py`) live alongside the questions in the [`homework/`](homework/) folder.

[Back to Book Index](../../README.md)
