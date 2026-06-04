# Chapter 6: System Design

[Back to Book Index](../../README.md)

---

This chapter covers the core principles and practical patterns of system design for backend engineers. Starting with scalability fundamentals and distributed systems theory, it progresses through real-world design examples and concludes with the quantitative estimation skills needed to reason about scale.

## Table of Contents

### [6.1 Scalability](scalability.md)
Foundations of building systems that grow with demand.
- Horizontal vs Vertical Scaling, Stateless Services, Auto-Scaling
- Load Balancing (L4/L7, algorithms, health checks, SSL termination)
- Caching Patterns (cache-aside, write-through, write-behind, read-through)
- Cache Invalidation Strategies (TTL, event-based, version-based)
- CDN and Multi-Tier Caching
- CAP Theorem, PACELC, Eventual Consistency, Conflict Resolution (LWW, Vector Clocks, CRDTs)

### [6.2 Distributed Systems](distributed-systems.md)
Coordination, communication, and observability in multi-service architectures.
- Consensus & Coordination (Raft leader election and log replication, split-brain prevention)
- etcd, ZooKeeper, Consul
- Service Communication (synchronous vs asynchronous, service discovery)
- Resilience Patterns (circuit breaker, retry with exponential backoff, timeout budgets)
- Observability (logs, metrics, traces), RED/USE methods, SLI/SLO/SLA, error budgets

### [6.3 Real-World System Design Examples](real-world-examples.md)
End-to-end architecture walkthroughs for common interview and production systems.
- URL Shortener (key generation, storage, caching, analytics pipeline)
- Distributed Rate Limiter (token bucket, sliding window log, fixed window counter)
- Chat System (WebSocket connections, message routing, presence tracking)
- Notification System (multi-channel delivery, user preferences, deduplication, reliability)

### [6.4 Back-of-Envelope Calculations](back-of-envelope.md)
Quantitative reasoning to guide architecture decisions before writing code.
- Reference latency, throughput, and storage numbers
- Walkthrough: URL Shortener scale estimation
- Walkthrough: Chat System scale estimation
- Walkthrough: Notification System scale estimation
