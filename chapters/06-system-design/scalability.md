[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 6.1 Scalability

### Horizontal vs Vertical Scaling

When an application grows and traffic increases, its existing servers can become overwhelmed. To keep up with demand, engineers must choose how to scale the system. Imagine you run a bakery and need to bake more bread to serve an increasing number of customers.

One approach is **Vertical Scaling (Scaling Up)**, which is like buying a single, much larger and more expensive oven. This doesn't change your daily workflow—you still put all the dough into one oven—but eventually, you hit a physical limit because manufacturers do not build ovens beyond a certain size. Furthermore, the cost of specialized, giant ovens grows exponentially.

The alternative is **Horizontal Scaling (Scaling Out)**, which is like buying ten more regular-sized ovens and placing them side-by-side. You can bake an almost infinite amount of bread by simply adding more ovens as demand grows. However, this introduces coordination challenges: you now need a team of bakers to manage all the ovens, and you must design a system to ensure they do not fight over the same mixing bowls or ingredients (a concept in software called statelessness).

**Vertical Scaling (Scale Up)** means upgrading the hardware of a single machine -- more CPU cores, more RAM, faster SSDs, better network cards. This approach is attractive because it requires zero changes to your application code. A single-threaded application that runs on 1 CPU and 4 GB of RAM will run just as well on a machine with 64 CPUs and 512 GB of RAM (it will just have more headroom). Databases, in particular, benefit from vertical scaling because coordinating writes across multiple machines is inherently difficult. The downsides are clear: there is a hard ceiling on how large a single machine can get (you cannot buy a server with 1 million CPUs), and cost increases non-linearly. Going from 16 GB to 32 GB of RAM might cost 2x, but going from 512 GB to 1 TB can cost 5-10x due to specialized hardware.

**Horizontal Scaling (Scale Out)** means adding more machines to your fleet instead of making one machine bigger. This approach has near-unlimited theoretical capacity -- you can always add another server. However, it demands that your application is designed to be stateless: no machine should hold data that another machine cannot access. If server A stores a user's session in local memory and the next request is routed to server B, that session is lost. Horizontal scaling requires externalizing all shared state to purpose-built stores (Redis for sessions, S3 for file uploads, a database for persistent data, environment variables or a configuration service for settings).

Auto-scaling is the automated version of horizontal scaling. Cloud providers let you define scaling policies based on metrics such as CPU utilization, memory usage, message queue depth, or custom application metrics (like requests per second). When the metric crosses a threshold, new instances are launched; when load drops, instances are terminated.

**Stateless Services** are the foundation of horizontal scaling. The rule is simple: any instance should be able to handle any request from any user at any time. To achieve this:

- Store session data in Redis or a database, not in local memory.
- Send file uploads directly to object storage (S3, GCS), not to the local filesystem.
- Read configuration from environment variables or a configuration service (Consul, AWS Parameter Store), not from local config files that might differ per machine.
- Avoid in-memory caches that cannot tolerate loss -- use them only as a performance optimization layer where a cache miss is handled gracefully.

### Load Balancing

Once you have horizontally scaled your application by running multiple servers, you need a way to distribute incoming traffic among them. Think of a load balancer as a host standing at the entrance of a busy restaurant. Instead of allowing customers to crowd the kitchen door and overwhelm a single chef, the host greets guests at the door and assigns them to an open table or routes them to a specific chef who is currently free. If a chef goes home sick (similar to a server failing a health check), the host immediately notices and stops sending guests to that station until the chef recovers and returns to work. In this way, the load balancer keeps the workload balanced and ensures that no single server is crushed by traffic while others sit idle.

A load balancer sits between clients and a pool of backend servers, distributing incoming requests across the pool. Load balancers are essential for horizontal scaling, high availability, and graceful maintenance.

**Layer 4 (Transport Layer) Load Balancing** operates at the TCP/UDP level. It makes routing decisions based on source/destination IP addresses and port numbers without inspecting the actual packet contents. Because it does not parse HTTP headers or payloads, L4 balancing is significantly faster and uses less CPU. It works by performing Network Address Translation (NAT) -- rewriting the destination IP of incoming packets to point to a selected backend server. L4 balancing can handle any protocol (HTTP, WebSocket, gRPC, database connections, custom TCP protocols) because it is protocol-agnostic.

**Layer 7 (Application Layer) Load Balancing** operates at the HTTP/HTTPS level. It fully parses the request and can make routing decisions based on URL paths (e.g., `/api/v2/*` goes to the new service), HTTP headers (e.g., route based on `Accept-Language`), cookies (e.g., session affinity), or even request body content. L7 balancers can terminate SSL/TLS connections, handle WebSocket upgrade requests, inject headers (like `X-Forwarded-For`), and perform content-based transformations. The trade-off is higher CPU usage and latency compared to L4.

**Algorithms** determine how the load balancer selects a backend server:

- **Round-Robin**: Requests are distributed sequentially across servers. Server 1, then Server 2, then Server 3, then back to Server 1. Simple and fair when all servers have equal capacity.
- **Weighted Round-Robin**: Like round-robin, but each server has a weight proportional to its capacity. A server with weight 3 receives three times as many requests as a server with weight 1. Useful when your fleet has mixed hardware generations.
- **Least Connections**: Routes each new request to the server currently handling the fewest active connections. Excellent for workloads where request durations vary widely (e.g., some API calls take 10ms, others take 5 seconds).
- **IP Hash**: A hash of the client's IP address determines which server handles the request. The same client always goes to the same server, providing session affinity without cookies. However, if a server goes down, all its clients are redistributed.
- **Consistent Hashing**: A hash ring distributes keys (client IPs or request attributes) across servers. When a server is added or removed, only a small fraction of keys are remapped. This is the best choice for cache-layer load balancing where you want to maximize cache hit rates.

**Health Checks** ensure the load balancer only sends traffic to healthy servers:

- **Active health checks**: The load balancer periodically sends probe requests (e.g., HTTP GET to `/health` expecting a 200 response, or a TCP connect on port 8080). If a server fails N consecutive checks, it is removed from the pool.
- **Passive health checks**: The load balancer monitors real traffic responses. If a server returns too many 5xx errors or connection timeouts, it is marked unhealthy.
- A **grace period** allows newly started servers time to warm up (load caches, establish database connections) before receiving full traffic.

**SSL Termination** is the practice of decrypting TLS/SSL at the load balancer rather than at each backend server. The load balancer handles the CPU-intensive TLS handshake and decryption, then forwards plaintext HTTP to backend servers over the trusted internal network. This offloads significant CPU from backends and centralizes certificate management. For environments requiring end-to-end encryption (e.g., PCI compliance), the load balancer can re-encrypt traffic to backends using internal certificates.

Here is an example nginx load balancer configuration demonstrating several of these concepts:

```nginx
# /etc/nginx/nginx.conf -- Layer 7 Load Balancer Configuration

upstream backend_api {
    # Least connections algorithm -- route to the server with fewest active connections
    least_conn;

    # Backend servers with weights (server2 has double capacity)
    server 10.0.1.10:8080 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8080 weight=2 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8080 weight=1 max_fails=3 fail_timeout=30s;

    # Backup server -- only receives traffic when all primary servers are down
    server 10.0.1.99:8080 backup;

    # Keep persistent connections to backends (connection pooling)
    keepalive 64;
}

upstream static_assets {
    server 10.0.2.10:80;
    server 10.0.2.11:80;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    # --- SSL Termination ---
    ssl_certificate     /etc/nginx/ssl/api.example.com.crt;
    ssl_certificate_key /etc/nginx/ssl/api.example.com.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # --- Content-Based Routing (L7) ---

    # API requests go to the backend_api upstream
    location /api/ {
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout settings
        proxy_connect_timeout 5s;
        proxy_read_timeout    60s;
        proxy_send_timeout    10s;

        # Use keepalive connections to backends
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Static assets go to a separate upstream
    location /static/ {
        proxy_pass http://static_assets;
        proxy_cache_valid 200 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # WebSocket upgrade support
    location /ws/ {
        proxy_pass http://backend_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;  # Keep WebSocket connections alive for 1 hour
    }

    # Health check endpoint (used by upstream load balancers / cloud health checks)
    location /health {
        access_log off;
        return 200 "ok";
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

Before nginx loads a config, validate it with `nginx -t`. On a healthy config you will see:

```console
$ sudo nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**How to read this output:** `nginx -t` parses the file and checks that referenced certificates and upstreams are well-formed without actually reloading the running process -- always run it before `nginx -s reload` in production, because reloading a broken config can drop the listener and take the site down. The two-line "syntax is ok" / "test is successful" pair is what your deploy pipeline should grep for; any other output (a `[emerg]` line pointing at a file and line number) means the reload must be aborted.

> **Common pitfall:** A `backup` server (line 59) only receives traffic when *every* primary is down, so it stays cold and its caches/connection pools never warm up -- when the primaries fail and traffic suddenly lands on it, the first requests are slow. Treat backup servers as a last resort, not as capacity.

> **Key Takeaway:** Layer 4 is fast and protocol-agnostic but blind to content; Layer 7 can route on paths, headers, and cookies and terminate TLS at the cost of CPU. Pick the algorithm to match the workload -- round-robin for uniform requests, least-connections for highly variable request durations, and consistent hashing when you are load-balancing a cache tier and want to preserve hit rates as nodes come and go.

### Caching

Caching stores frequently accessed data in a faster storage layer (usually memory) to reduce latency and load on the primary data store. The choice of caching pattern has profound implications for consistency, latency, and failure modes.

**Cache-Aside (Lazy Loading)** is the most common pattern. The application is responsible for all cache interactions: on a read, it checks the cache first; on a cache miss, it loads from the database, writes the result to the cache, and returns it. The cache only contains data that has actually been requested, which means cold starts are slow (empty cache, everything is a miss). The main risk is staleness: if the database is updated without invalidating the cache, the cache serves outdated data.

**Write-Through** means the application writes to both the cache and the database on every write operation. The cache is always consistent with the database, eliminating staleness. The cost is higher write latency because every write must succeed in both stores before returning to the caller. This pattern is a good fit when reads vastly outnumber writes and you need strong consistency.

**Write-Behind (Write-Back)** means the application writes to the cache, and the cache asynchronously flushes changes to the database in the background (often in batches). This gives the fastest write latency because the application only waits for the in-memory cache write. The danger is data loss: if the cache node crashes before flushing to the database, those writes are lost. CPU caches and many database engines (e.g., InnoDB buffer pool) use this pattern internally.

**Read-Through** moves the cache-miss logic into the cache layer itself. The application only ever talks to the cache. When the cache does not have the requested key, the cache itself loads from the database, stores the result, and returns it. This simplifies application code because there is no "check cache, if miss load from DB" logic scattered across your codebase. The cache library or proxy handles it transparently.

Here is a Python implementation demonstrating cache-aside and write-through patterns with Redis:

```python
import json
import time
import hashlib
import redis
import logging

logger = logging.getLogger(__name__)

# --- Redis connection ---
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


# =============================================================================
# Pattern 1: Cache-Aside (Lazy Loading)
# =============================================================================
class CacheAsideRepository:
    """
    The application manages the cache explicitly.
    Read: check cache -> miss -> load from DB -> populate cache.
    Write: update DB -> invalidate cache.
    """

    def __init__(self, db_connection, default_ttl=300):
        self.db = db_connection
        self.ttl = default_ttl

    def _cache_key(self, entity: str, entity_id: str) -> str:
        return f"cache:{entity}:{entity_id}"

    def get_user(self, user_id: str) -> dict:
        cache_key = self._cache_key("user", user_id)

        # Step 1: Check cache
        cached = redis_client.get(cache_key)
        if cached is not None:
            logger.info(f"Cache HIT for {cache_key}")
            return json.loads(cached)

        # Step 2: Cache miss -- load from database
        logger.info(f"Cache MISS for {cache_key}")
        user = self.db.execute(
            "SELECT id, name, email FROM users WHERE id = %s", (user_id,)
        )
        if user is None:
            return None

        # Step 3: Populate cache with TTL
        redis_client.setex(cache_key, self.ttl, json.dumps(user))
        return user

    def update_user(self, user_id: str, data: dict) -> None:
        # Step 1: Update the database (source of truth)
        self.db.execute(
            "UPDATE users SET name=%s, email=%s WHERE id=%s",
            (data["name"], data["email"], user_id),
        )

        # Step 2: Invalidate cache (delete, not update -- next read will repopulate)
        cache_key = self._cache_key("user", user_id)
        redis_client.delete(cache_key)
        logger.info(f"Cache INVALIDATED for {cache_key}")


# =============================================================================
# Pattern 2: Write-Through
# =============================================================================
class WriteThroughRepository:
    """
    Every write updates both the database AND the cache atomically.
    The cache is always consistent with the database.
    """

    def __init__(self, db_connection, default_ttl=600):
        self.db = db_connection
        self.ttl = default_ttl

    def _cache_key(self, entity: str, entity_id: str) -> str:
        return f"cache:{entity}:{entity_id}"

    def get_user(self, user_id: str) -> dict:
        cache_key = self._cache_key("user", user_id)
        cached = redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        # On miss, load from DB and populate cache (same as cache-aside for reads)
        user = self.db.execute(
            "SELECT id, name, email FROM users WHERE id = %s", (user_id,)
        )
        if user:
            redis_client.setex(cache_key, self.ttl, json.dumps(user))
        return user

    def update_user(self, user_id: str, data: dict) -> None:
        # Step 1: Update the database
        self.db.execute(
            "UPDATE users SET name=%s, email=%s WHERE id=%s",
            (data["name"], data["email"], user_id),
        )

        # Step 2: Write the NEW value to cache (not delete -- write-through)
        user = {"id": user_id, "name": data["name"], "email": data["email"]}
        cache_key = self._cache_key("user", user_id)
        redis_client.setex(cache_key, self.ttl, json.dumps(user))
        logger.info(f"Cache UPDATED (write-through) for {cache_key}")


# =============================================================================
# Cache Stampede Prevention with Locking
# =============================================================================
class StampedeProtectedCache:
    """
    When a popular key expires, hundreds of concurrent requests may all
    experience a cache miss simultaneously and all hit the database.
    This "stampede" can overwhelm the DB.

    Solution: use a Redis lock so that only ONE request loads from DB.
    Other requests wait briefly, then retry the cache.
    """

    def __init__(self, db_connection, default_ttl=300, lock_timeout=5):
        self.db = db_connection
        self.ttl = default_ttl
        self.lock_timeout = lock_timeout

    def get_with_lock(self, cache_key: str, db_loader, *args) -> dict:
        # Try the cache first
        cached = redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        # Acquire a lock so only one request loads from DB
        lock_key = f"lock:{cache_key}"
        lock = redis_client.set(lock_key, "1", nx=True, ex=self.lock_timeout)

        if lock:
            # We got the lock -- load from DB
            try:
                data = db_loader(*args)
                if data is not None:
                    redis_client.setex(cache_key, self.ttl, json.dumps(data))
                return data
            finally:
                redis_client.delete(lock_key)
        else:
            # Another request is loading -- wait and retry the cache
            time.sleep(0.1)
            cached = redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
            # If still not in cache, fall through to DB (lock holder may have failed)
            return db_loader(*args)
```

These are class definitions, so importing the module prints nothing. The behavior becomes visible once you drive a repository through a read/write/read sequence with logging enabled:

```python
logging.basicConfig(level=logging.INFO, format="%(message)s")
repo = CacheAsideRepository(db_connection)

repo.get_user("42")              # first read -- cache is empty
repo.get_user("42")              # second read -- now cached
repo.update_user("42", {"name": "Ann", "email": "ann@x.io"})
repo.get_user("42")              # read after write
```

Running that prints (timestamps omitted via the format string):

```text
Cache MISS for cache:user:42
Cache HIT for cache:user:42
Cache INVALIDATED for cache:user:42
Cache MISS for cache:user:42
```

**How to read this output:** The first `get_user` is a MISS -- the cache is cold, so the code falls through to `db.execute` and then `setex` populates Redis; this is the latency cost every key pays exactly once per TTL window. The second call is a HIT served entirely from memory, which is the whole point of the cache. The `update_user` logs INVALIDATED because cache-aside *deletes* rather than rewrites the key -- so the very next read is again a MISS that repopulates from the database. In an interview, the key insight to articulate is the deliberate delete-don't-update choice: deleting guarantees the next reader sees fresh data straight from the source of truth, whereas writing a computed value into the cache risks caching a value that never matched the row (e.g. if the UPDATE and the cache write race). Swap in `WriteThroughRepository` and that third line would instead read `Cache UPDATED (write-through)` with no following MISS, because the new value is written into Redis inline -- trading a slightly slower write for a guaranteed-warm cache.

> **Common pitfall:** In `CacheAsideRepository.get_user`, a database row that genuinely does not exist returns `None` and is *not* cached, so every request for a missing key becomes a database query -- a classic cache-penetration vector an attacker can exploit by requesting random non-existent IDs. The fix is to cache a short-TTL negative sentinel (e.g. an empty marker) for misses.

**Cache Invalidation Strategies** are notoriously difficult. As Phil Karlton famously said, "There are only two hard things in computer science: cache invalidation and naming things."

- **TTL (Time-To-Live)**: Set an expiry on every cached key. After the TTL elapses, the key is automatically deleted. This is the simplest approach and provides a guaranteed upper bound on staleness. A TTL of 5 minutes means data is at most 5 minutes stale.
- **Event-Based Invalidation**: When data changes in the database, publish an event (via Kafka, Redis Pub/Sub, or a database trigger) that tells the cache layer to delete or update the relevant key. This provides near-real-time consistency but adds architectural complexity.
- **Version-Based**: Include a version number in the cache key (e.g., `user:42:v7`). When data changes, increment the version. Old keys naturally expire via TTL. This avoids the explicit deletion step but wastes some memory on stale keys.

**Cache Stampede** (also called "thundering herd") occurs when a popular cache key expires and many concurrent requests simultaneously discover the cache miss, all rushing to the database to reload the data. Solutions include locking (shown in the code above), probabilistic early expiry (XFetch algorithm, where each request has a small probability of refreshing the cache before the actual TTL expires), and stale-while-revalidate (serve the stale value while one background request refreshes it).

**Hot Key / Celebrity Problem** is the cache-tier equivalent of a write hotspot. Most caching math assumes traffic spreads roughly evenly across keys, so adding cache nodes adds capacity. But occasionally a *single* key becomes wildly disproportionate -- a celebrity's profile with 100 million followers, a viral post, a flash-sale product, the configuration object every request reads. Because a given key lives on exactly one cache node (consistent hashing puts it there), all of that traffic lands on one node, saturating its CPU and network while the rest of the fleet sits idle. Adding nodes does nothing, because the hot key still hashes to the same single node. Three mitigations, often combined:

- **Local replication of the hot key**: detect hot keys (sample request counts) and copy them into each application server's in-process L1 cache for a short TTL. Reads then never leave the box, so the load fans out across all app servers instead of converging on one Redis node. The cost is staleness bounded by the L1 TTL -- fine for a follower count, not for a balance.
- **Request coalescing (single-flight)**: when many requests for the same key miss simultaneously, let only one of them perform the expensive load and have the rest wait for and share its result. This is the same single-flight lock used for stampede prevention, applied per-process; it collapses a burst of N identical loads into one.
- **Key splitting (sharding the hot key)**: replicate the value under several physical keys (`post:123#0` ... `post:123#9`) spread across different cache nodes, and have each reader pick a random replica. This deliberately fans a single logical key across N nodes, trading N-fold write amplification on update for N-fold read capacity. Used for counters and other read-heavy hot values.

The first step in production is always *detection*: instrument the cache client to track per-key request rates so you can identify a celebrity key before it melts a node, rather than after.

To speed up access for users scattered across different countries, web architectures use a Content Delivery Network. Imagine you publish a popular magazine in New York, and readers all over the world want to read it. If every single subscriber in Tokyo or London has to wait for a cargo ship to transport their individual copy from New York, delivery will take weeks. Instead, you send digital templates of the magazine to local print shops (known as CDN edge servers) in Tokyo and London. When a reader in Tokyo wants a copy, they pick it up instantly from the shop down the street. This drastically reduces transit time for the user and cuts down on the mailing bottleneck at your main office in New York.

**CDN (Content Delivery Network)** caches content at edge locations geographically close to users. Services like CloudFront, Cloudflare, and Fastly cache static assets (images, CSS, JavaScript) and can also cache API responses. Control caching behavior with HTTP headers (`Cache-Control: public, max-age=86400`), configure cache keys (what makes two requests "the same" from the CDN's perspective), and use purge/invalidation APIs when content changes.

**Multi-Tier Caching** layers multiple caches for optimal performance:

- **L1 (In-Process)**: The fastest cache, stored directly in the application's memory (e.g., a Python dictionary or `lru_cache`). Extremely fast (nanoseconds) but limited in size and not shared across instances.
- **L2 (Shared/Distributed)**: A centralized cache like Redis or Memcached. Shared across all application instances. Access time is sub-millisecond over the network. Can hold much more data.
- **L3 (CDN/Edge)**: Closest to the user geographically. Best for static or slowly-changing content.

A request flows through these layers: check L1, if miss check L2, if miss check L3 (for applicable content), if miss query the database.

> **Key Takeaway:** Every caching pattern trades consistency against latency and durability -- cache-aside is simple but can serve stale data, write-through stays consistent at the cost of write latency, write-behind is fastest but can lose data on a crash. The hardest part is never the lookup; it is invalidation and the failure modes (stampede on expiry, penetration on missing keys). Choose TTLs and patterns by asking how much staleness the business can tolerate, not by defaulting to "cache everything."

### CAP Theorem & Consistency

**The CAP Theorem** states that a distributed data store can provide at most two of three guarantees simultaneously: **Consistency** (every read receives the most recent write or an error), **Availability** (every request receives a non-error response, though it may not contain the most recent write), and **Partition Tolerance** (the system continues operating despite network partitions between nodes). Since network partitions are inevitable in distributed systems, the real choice is between CP and AP during a partition event.

- **CP systems** (e.g., PostgreSQL with synchronous replication, HBase, ZooKeeper) refuse to respond or return an error if they cannot guarantee that the response is up-to-date. They sacrifice availability for correctness. Use CP for financial transactions, inventory management, and any scenario where stale data causes real-world harm.
- **AP systems** (e.g., Cassandra, DynamoDB, CouchDB) continue responding even during partitions, but may return stale data. They sacrifice consistency for availability. Use AP for social media feeds, analytics dashboards, product catalogs, and any scenario where showing slightly stale data is acceptable.

**PACELC** extends CAP by addressing behavior during normal operation (when there is no partition). The full statement is: "If there is a Partition, choose between Availability and Consistency; Else (during normal operation), choose between Latency and Consistency." Most real-world systems sacrifice consistency for latency even during normal operation. For example, DynamoDB defaults to eventually consistent reads (faster) but offers strongly consistent reads as an option (slower).

**Eventual Consistency** means that if no new updates are made to a piece of data, all replicas will eventually converge to the same value. The "eventually" could be milliseconds or seconds depending on the system. This is acceptable for social media feeds (a post appearing 2 seconds late is fine), analytics counters (approximate counts are useful), and search indices (a few seconds of lag is acceptable). It is not acceptable for bank account balances, inventory counts for the last item in stock, or any scenario where two users acting on stale data creates a conflict.

**Conflict Resolution** becomes necessary when concurrent writes happen to different replicas during a partition:

- **Last-Write-Wins (LWW)**: The write with the latest timestamp wins. Simple to implement but can silently lose data. If two users update the same record at nearly the same time, one update is discarded without notification. Clock synchronization issues (clock skew between servers) make this even more unreliable.
- **Vector Clocks**: Each node maintains a vector of logical clocks (one per node). By comparing vectors, the system can detect concurrent writes (neither happened-before the other) versus sequential writes (a clear ordering exists). When concurrency is detected, the system can present both versions to the application for resolution. Amazon's Dynamo paper popularized this approach.
- **CRDTs (Conflict-free Replicated Data Types)**: Specially designed data structures that can be merged automatically without conflicts. Examples include G-Counters (grow-only counters), PN-Counters (increment and decrement), G-Sets (grow-only sets), OR-Sets (observed-remove sets), and LWW-Registers. CRDTs guarantee convergence by mathematical construction. Used by Redis (CRDTs in Redis Enterprise), Riak, and collaborative editing tools.

**Linearizability** is the strongest consistency model. Every operation appears to take effect atomically at some point between its invocation and its response. The system behaves as if there is only a single copy of the data. This requires a consensus protocol (like Raft or Paxos) and is expensive in terms of latency because writes must be acknowledged by a majority of nodes before they are considered committed.

**Causal Consistency** respects the happens-before relationship. If operation A causally precedes operation B (e.g., A is a write and B is a read that sees A's value), then every node will see A before B. However, operations that are not causally related may be seen in different orders on different nodes. Causal consistency is weaker (and therefore cheaper) than linearizability but stronger than eventual consistency. It is sufficient for most applications.

**Session (Client-Centric) Guarantees** are pragmatic, cheap consistency promises scoped to a single client's session rather than to the whole system. They are the guarantees users actually notice, and they are achievable on top of an eventually consistent store without paying for linearizability:

- **Read-Your-Writes**: a client that performs a write is guaranteed to see (at least) that write in its subsequent reads. The classic violation: a user edits their profile, the write goes to the primary, then the next read is served by a replica that has not yet replicated the change -- so the user sees their *old* profile and assumes the save failed (and saves again). Common implementations: route a user's reads to the primary for a short window after they write (sticky/"read-after-write" routing); track the write's log position (LSN/version) in the user's session and only serve the read from a replica that has caught up to that position; or simply route all of a session's traffic to one replica.
- **Monotonic Reads**: a client never sees time go backward -- once it has read a value, later reads return that value or a newer one, never an older one. The violation happens when successive reads hit different replicas at different replication lag: read 1 hits an up-to-date replica and shows 10 comments, read 2 hits a lagging replica and shows 8, and the UI appears to lose data. Pinning a session to one replica (session affinity) gives monotonic reads for free.
- **Monotonic Writes** (a client's writes are applied in the order it issued them) and **Writes-Follow-Reads** (a write is ordered after any write the client previously read) round out the four session guarantees.

These are the everyday consistency wins: most "the database is eventually consistent" complaints are really read-your-writes or monotonic-read violations, and both are fixable with routing/session affinity rather than a global consensus protocol.

> **Key Takeaway**: The CAP theorem is not about choosing two of three properties as a permanent system-wide decision. It is about understanding the trade-off that is forced during network partitions. Most systems are not purely CP or AP -- they make different trade-offs for different operations. A system might use CP for payment processing and AP for recommendation feeds, all within the same architecture.

*Last reviewed: 2026-06-08*
