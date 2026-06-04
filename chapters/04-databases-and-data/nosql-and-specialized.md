[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 4.2 NoSQL & Specialized Databases

### Redis

Redis is an in-memory data structure store used as a cache, message broker, and general-purpose database. Its power comes from its rich set of data structures, atomic operations, and sub-millisecond latency.

#### Data Structures

**Strings** are the simplest Redis type. A string can hold any binary data up to 512 MB -- text, serialized JSON, integers, or raw bytes. Strings support atomic increment/decrement, making them useful for counters.

```
> SET user:1:name "Alice"
OK
> GET user:1:name
"Alice"

> SET page:views 0
OK
> INCR page:views
(integer) 1
> INCRBY page:views 100
(integer) 101

> SET session:abc123 '{"user_id": 1, "role": "admin"}' EX 3600
OK
-- EX 3600 sets a 1-hour TTL

> TTL session:abc123
(integer) 3597

> MSET user:1:name "Alice" user:1:email "alice@example.com" user:1:role "admin"
OK
> MGET user:1:name user:1:email user:1:role
1) "Alice"
2) "alice@example.com"
3) "admin"
```

**Hashes** store field-value pairs, like a dictionary. They are memory-efficient for representing objects because Redis optimizes small hashes using a ziplist encoding.

```
> HSET user:1 name "Alice" email "alice@example.com" age 30
(integer) 3
> HGET user:1 name
"Alice"
> HGETALL user:1
1) "name"
2) "Alice"
3) "email"
4) "alice@example.com"
5) "age"
6) "30"
> HINCRBY user:1 age 1
(integer) 31
```

**Lists** are doubly-linked lists of strings. They support push/pop from both ends in O(1), making them suitable for queues, stacks, and recent-items lists.

```
> LPUSH queue:emails "email1" "email2" "email3"
(integer) 3
> RPOP queue:emails
"email1"
> LRANGE queue:emails 0 -1
1) "email3"
2) "email2"

-- Blocking pop: wait up to 30 seconds for an item (great for worker queues)
> BRPOP queue:emails 30
1) "queue:emails"
2) "email2"
```

**Sets** are unordered collections of unique strings. They support set operations (union, intersection, difference) in addition to membership testing.

```
> SADD user:1:tags "python" "django" "postgresql"
(integer) 3
> SADD user:2:tags "python" "flask" "mongodb"
(integer) 3
> SISMEMBER user:1:tags "python"
(integer) 1
> SINTER user:1:tags user:2:tags
1) "python"
> SUNION user:1:tags user:2:tags
1) "python"
2) "django"
3) "postgresql"
4) "flask"
5) "mongodb"
```

**Sorted sets** associate a score (floating-point number) with each member, keeping the set ordered by score. This is the go-to structure for leaderboards, priority queues, rate limiters, and time-based indexes.

```
> ZADD leaderboard 1500 "alice" 1200 "bob" 1800 "carol" 900 "dave"
(integer) 4

-- Top 3 players (highest score first)
> ZREVRANGE leaderboard 0 2 WITHSCORES
1) "carol"
2) "1800"
3) "alice"
4) "1500"
5) "bob"
6) "1200"

-- Get rank (0-based, highest first)
> ZREVRANK leaderboard "alice"
(integer) 1

-- Increment a score
> ZINCRBY leaderboard 400 "bob"
"1600"

-- Range by score
> ZRANGEBYSCORE leaderboard 1000 1600 WITHSCORES
1) "bob"
2) "1600"
3) "alice"
4) "1500"

-- Count members in score range
> ZCOUNT leaderboard 1000 1600
(integer) 2

-- Remove members with scores below 1000
> ZREMRANGEBYSCORE leaderboard -inf 999
(integer) 1
```

**Streams** (Redis 5.0+) are append-only log structures designed for event streaming, similar to Apache Kafka. They support consumer groups for distributing work among multiple consumers.

**HyperLogLog** provides probabilistic cardinality estimation (counting unique elements) using only ~12 KB of memory regardless of the number of elements. The standard error is 0.81%.

```
> PFADD daily:visitors:2025-06-15 "user:1" "user:2" "user:3" "user:1"
(integer) 1
> PFCOUNT daily:visitors:2025-06-15
(integer) 3
-- Only 3 unique visitors, even though "user:1" was added twice
```

#### Use Cases with Code Examples

**Caching with TTL:**

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def get_user_profile(user_id):
    cache_key = f"user:{user_id}:profile"

    # Try cache first
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss: fetch from database
    profile = fetch_from_database(user_id)

    # Store in cache with 15-minute TTL
    r.set(cache_key, json.dumps(profile), ex=900)
    return profile

def invalidate_user_profile(user_id):
    r.delete(f"user:{user_id}:profile")
```

**Rate limiting with sorted sets (sliding window):**

```python
import time

def is_rate_limited(user_id, max_requests=100, window_seconds=60):
    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    # Remove entries outside the window
    pipe.zremrangebyscore(key, '-inf', window_start)
    # Add the current request
    pipe.zadd(key, {f"{now}:{id(now)}": now})
    # Count requests in the window
    pipe.zcard(key)
    # Set TTL on the key so it auto-expires
    pipe.expire(key, window_seconds)
    results = pipe.execute()

    request_count = results[2]
    return request_count > max_requests
```

**Distributed locking (simplified Redlock):**

```python
import uuid

def acquire_lock(lock_name, timeout=10):
    lock_id = str(uuid.uuid4())
    acquired = r.set(f"lock:{lock_name}", lock_id, nx=True, ex=timeout)
    return lock_id if acquired else None

def release_lock(lock_name, lock_id):
    # Use Lua script for atomic check-and-delete
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    return r.eval(script, 1, f"lock:{lock_name}", lock_id)

# Usage:
lock_id = acquire_lock("process-payments")
if lock_id:
    try:
        process_payments()
    finally:
        release_lock("process-payments", lock_id)
```

**Pub/Sub for real-time notifications:**

```python
# Publisher
r.publish('notifications:user:42', json.dumps({
    'type': 'new_message',
    'from': 'alice',
    'preview': 'Hey, are you available?'
}))

# Subscriber (blocking, typically in a separate process)
pubsub = r.pubsub()
pubsub.subscribe('notifications:user:42')
for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        print(f"Notification: {data}")
```

When the publisher fires, the subscriber's loop wakes and prints something like:

```text
Notification: {'type': 'new_message', 'from': 'alice', 'preview': 'Hey, are you available?'}
```

**How to read this output:** `pubsub.listen()` is a blocking generator that yields control-frame messages too (the `subscribe` confirmation arrives first with `type == 'subscribe'`), which is why the `if message['type'] == 'message'` guard matters -- without it you would try to `json.loads` the subscription acknowledgement and crash. The key production caveat: Redis Pub/Sub is fire-and-forget. If no subscriber is connected at publish time, the message is dropped -- there is no replay. When you need durable delivery and consumer groups, reach for Streams instead. This distinction is a common interview probe.

> **Common pitfall:** A connection sitting in `pubsub.listen()` cannot issue other commands on that same connection. Run subscribers on a dedicated connection (or thread/process), not the one your application uses for normal reads and writes.

#### Persistence

**RDB (Redis Database)** snapshots save the entire dataset to a binary file at configured intervals. The snapshot is a compact, point-in-time representation. It is fast to load on startup but you can lose data since the last snapshot.

**AOF (Append-Only File)** logs every write operation. It is more durable (you can configure `appendfsync` to `always`, `everysec`, or `no`), but the file is larger and recovery is slower because it replays all operations.

The recommended production configuration uses both: RDB for fast restarts and backups, AOF for durability. Redis 7 introduced multi-part AOF which simplifies management by splitting the AOF into a base file and incremental files.

```
# redis.conf excerpt
save 900 1         # RDB: save after 900 seconds if at least 1 key changed
save 300 10        # RDB: save after 300 seconds if at least 10 keys changed
save 60 10000      # RDB: save after 60 seconds if at least 10000 keys changed

appendonly yes
appendfsync everysec    # AOF: fsync once per second (good balance)
```

#### Clustering and High Availability

**Redis Sentinel** provides high availability without sharding. It monitors primary and replica instances, automatically promotes a replica to primary upon failure, and notifies clients of the topology change. Use Sentinel when your dataset fits on a single machine.

**Redis Cluster** provides horizontal scaling by partitioning data across multiple nodes using 16384 hash slots. Each key is mapped to a slot via `CRC16(key) mod 16384`, and each node is responsible for a subset of slots. Redis Cluster also provides automatic failover within each shard.

```
  Redis Cluster Topology (3 primaries, 3 replicas)
  =================================================

  +-------------------+    +-------------------+    +-------------------+
  | Primary A         |    | Primary B         |    | Primary C         |
  | Slots: 0-5460     |    | Slots: 5461-10922 |    | Slots: 10923-16383|
  +-------------------+    +-------------------+    +-------------------+
         |                        |                        |
         | replication             | replication             | replication
         v                        v                        v
  +-------------------+    +-------------------+    +-------------------+
  | Replica A1        |    | Replica B1        |    | Replica C1        |
  +-------------------+    +-------------------+    +-------------------+
```

#### Lua Scripting

Lua scripts execute atomically on the Redis server, meaning no other command can run between the start and end of the script. This eliminates race conditions without requiring external locking. Scripts also reduce round-trips by performing multiple operations in a single call.

```
-- Lua script: atomic rate limiter
-- KEYS[1] = rate limit key
-- ARGV[1] = max requests
-- ARGV[2] = window in seconds

local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
if current > tonumber(ARGV[1]) then
    return 0  -- rate limited
end
return 1  -- allowed
```

```python
# Using Lua scripts from Python
rate_limit_script = r.register_script("""
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
if current > tonumber(ARGV[1]) then
    return 0
end
return 1
""")

# Call the script
allowed = rate_limit_script(keys=['ratelimit:user:42'], args=[100, 60])
if not allowed:
    raise RateLimitExceeded()
```

#### Eviction Policies

When Redis reaches its configured `maxmemory` limit, it needs a strategy for what to do with new writes. The `maxmemory-policy` setting controls this behavior:

- `noeviction`: Return an error on write commands. Reads still work. Use when data loss is unacceptable.
- `allkeys-lru`: Evict the least recently used key across all keys. Best general-purpose cache policy.
- `volatile-lru`: Evict the least recently used key among those with a TTL set. Keeps permanent keys safe.
- `allkeys-lfu` (Redis 4.0+): Evict the least frequently used key. Better than LRU for workloads with popular items.
- `volatile-ttl`: Evict the key with the shortest remaining TTL.

```
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

> **Key Takeaway:** Redis is far more than a simple key-value cache. Its data structures (sorted sets, streams, HyperLogLog) enable elegant solutions for leaderboards, rate limiting, real-time analytics, and distributed coordination. Use Lua scripting for atomic multi-step operations. Always configure persistence and eviction policies for production.

---

### MongoDB

MongoDB is a document database that stores data as BSON (Binary JSON) documents. Each document is a self-contained unit that can have a different structure from other documents in the same collection, providing schema flexibility.

#### Document Model

The document model encourages denormalization: instead of normalizing data into multiple tables with foreign keys (as in relational databases), you embed related data directly in the document. Design your schema around your query patterns, not around eliminating data duplication.

```javascript
// A denormalized order document
{
    "_id": ObjectId("64a1b2c3d4e5f6a7b8c9d0e1"),
    "order_number": "ORD-2025-001",
    "customer": {
        "id": 42,
        "name": "Alice Johnson",
        "email": "alice@example.com"
    },
    "items": [
        { "product": "Laptop", "sku": "LAP-001", "quantity": 1, "price": 999.99 },
        { "product": "Mouse",  "sku": "MOU-003", "quantity": 2, "price": 29.99 }
    ],
    "shipping_address": {
        "street": "123 Main St",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701"
    },
    "total": 1059.97,
    "status": "shipped",
    "created_at": ISODate("2025-06-15T10:30:00Z")
}
```

#### When to Use MongoDB

MongoDB is appropriate when your data has varied or evolving schemas (e.g., product catalogs where each category has different attributes), when your data is naturally document-oriented (CMS content, user profiles, IoT device data), or when you need rapid prototyping with flexible schemas.

MongoDB is not the best fit when you have heavily relational data that requires multi-table JOINs, when you need strict ACID transactions across multiple documents (though MongoDB 4.0+ supports multi-document transactions, they are slower than single-document operations), or when your queries require complex aggregations that relational databases handle naturally.

#### Indexing

MongoDB uses B-tree indexes similar to relational databases. The `explain()` method is equivalent to PostgreSQL's `EXPLAIN ANALYZE`:

```javascript
// Create indexes
db.orders.createIndex({ "customer.id": 1 })
db.orders.createIndex({ status: 1, created_at: -1 })
db.orders.createIndex({ "items.sku": 1 })  // Multikey index on array field
db.orders.createIndex({ order_number: 1 }, { unique: true })

// Text index for search
db.articles.createIndex({ title: "text", body: "text" })
db.articles.find({ $text: { $search: "database optimization" } })

// Analyze query performance
db.orders.find({ status: "pending" }).sort({ created_at: -1 }).explain("executionStats")
```

The `explain("executionStats")` call returns a large JSON document; the fields that matter are buried in `executionStats` and `winningPlan`:

```text
"winningPlan": { "stage": "IXSCAN", "indexName": "status_1_created_at_-1" }
"executionStats": {
    "nReturned": 37,
    "totalKeysExamined": 37,
    "totalDocsExamined": 37,
    "executionTimeMillis": 2
}
```

**How to read this output:** The goal is `totalKeysExamined` and `totalDocsExamined` being close to `nReturned` -- here all three are 37, meaning the compound index `{ status: 1, created_at: -1 }` satisfied both the filter and the sort, so MongoDB walked exactly the rows it returned. If you saw `"stage": "COLLSCAN"` or `totalDocsExamined` in the thousands while `nReturned` was 37, the query is scanning the whole collection and the index is not being used (often because the sort direction does not match the index). A second red flag is a `SORT` stage in the plan: it means MongoDB had to sort in memory rather than reading rows in index order, which fails outright once the result exceeds the 100 MB sort limit. This is the MongoDB equivalent of reading a PostgreSQL `EXPLAIN ANALYZE`, and interviewers expect you to name the keys-examined-vs-returned ratio as the headline metric.

#### Aggregation Pipeline

The aggregation pipeline is MongoDB's framework for data transformation and analysis. Each stage transforms the documents as they pass through:

```javascript
// Monthly revenue by category with year-over-year comparison
db.orders.aggregate([
    { $match: { status: { $in: ["shipped", "delivered"] } } },
    { $unwind: "$items" },
    { $group: {
        _id: {
            year: { $year: "$created_at" },
            month: { $month: "$created_at" },
            category: "$items.category"
        },
        revenue: { $sum: { $multiply: ["$items.price", "$items.quantity"] } },
        order_count: { $sum: 1 }
    }},
    { $sort: { "_id.year": 1, "_id.month": 1 } },
    { $project: {
        year: "$_id.year",
        month: "$_id.month",
        category: "$_id.category",
        revenue: { $round: ["$revenue", 2] },
        order_count: 1,
        _id: 0
    }}
])
```

A typical result set looks like this (one document per year/month/category group):

```text
{ "year": 2025, "month": 5, "category": "Electronics", "revenue": 184230.5, "order_count": 412 }
{ "year": 2025, "month": 5, "category": "Accessories", "revenue": 21899.4,  "order_count": 880 }
{ "year": 2025, "month": 6, "category": "Electronics", "revenue": 203117.0, "order_count": 451 }
```

**How to read this output:** Each stage reshaped the stream that flowed into it. `$unwind: "$items"` was the pivotal step -- it exploded each order into one document per line item, so an order with three items became three documents before the `$group`. That is why `order_count` counts line items in a category, not distinct orders; a frequent bug is reading this number as "orders placed." `$round` exists because `$multiply` on floating-point prices accumulates noise (1059.9700000000001), so you round at the projection stage rather than trusting raw float sums. In an interview, the expected insight is that ordering `$match` before `$unwind` lets MongoDB use an index to discard non-shipped orders early, keeping the expensive unwind off the full collection.

#### Replication and Sharding

Replica sets provide high availability through automatic failover. A replica set consists of a primary (receives all writes) and one or more secondaries (replicate from the primary). If the primary goes down, secondaries hold an election and one is promoted.

Sharding distributes data across multiple replica sets (shards) using a shard key. Choosing the right shard key is critical: it should have high cardinality, distribute writes evenly, and support your most common queries (query locality). A poor shard key leads to hot spots and scatter-gather queries.

> **Key Takeaway:** MongoDB excels when your data is document-oriented and your access patterns are known up front. Design your schema for your queries, not for normalization. Use the aggregation pipeline for analytics. Choose shard keys very carefully -- they are effectively immutable and determine the performance characteristics of your entire cluster.

---

### Elasticsearch

Elasticsearch is a distributed search and analytics engine built on Apache Lucene. It stores data as JSON documents and builds an inverted index that maps every term to the documents containing that term.

#### Inverted Index

An inverted index is the core data structure that makes full-text search fast. When a document is indexed, Elasticsearch tokenizes the text (splits it into terms), applies analyzers (lowercasing, stemming, stop-word removal), and records which documents contain each term.

```
Document 1: "PostgreSQL is a powerful database"
Document 2: "Redis is a fast in-memory database"
Document 3: "PostgreSQL supports full-text search"

Inverted Index (after analysis):
  Term          -> Documents
  --------------------------------
  postgresql    -> [1, 3]
  powerful      -> [1]
  database      -> [1, 2]
  redis         -> [2]
  fast          -> [2]
  in-memory     -> [2]
  supports      -> [3]
  full-text     -> [3]
  search        -> [3]
```

#### Queries and Mappings

```json
// Define an explicit mapping
PUT /articles
{
    "mappings": {
        "properties": {
            "title":      { "type": "text", "analyzer": "english" },
            "title_raw":  { "type": "keyword" },
            "body":       { "type": "text", "analyzer": "english" },
            "author":     { "type": "keyword" },
            "published":  { "type": "date" },
            "tags":       { "type": "keyword" },
            "view_count": { "type": "integer" }
        }
    }
}

// Bool query with full-text search, filtering, and aggregation
POST /articles/_search
{
    "query": {
        "bool": {
            "must": [
                { "match": { "body": "database performance" } }
            ],
            "filter": [
                { "term": { "author": "alice" } },
                { "range": { "published": { "gte": "2025-01-01" } } }
            ],
            "should": [
                { "match": { "title": { "query": "database performance", "boost": 2 } } }
            ]
        }
    },
    "aggs": {
        "by_tag": {
            "terms": { "field": "tags", "size": 10 }
        }
    },
    "highlight": {
        "fields": { "body": {} }
    }
}
```

#### Scaling

Elasticsearch scales by distributing index data across shards (horizontal scaling) and replicating shards for fault tolerance and read throughput. For time-based data (logs, events), the standard pattern is to create one index per time period and use aliases for transparent rollover:

```json
// Index lifecycle management for log data
PUT /_ilm/policy/logs_policy
{
    "policy": {
        "phases": {
            "hot":    { "actions": { "rollover": { "max_size": "50gb", "max_age": "1d" } } },
            "warm":   { "min_age": "7d",  "actions": { "shrink": { "number_of_shards": 1 } } },
            "cold":   { "min_age": "30d", "actions": { "freeze": {} } },
            "delete": { "min_age": "90d", "actions": { "delete": {} } }
        }
    }
}
```

> **Key Takeaway:** Use Elasticsearch when you need full-text search with relevance scoring, complex aggregations, or log analytics. It complements a relational database -- do not use it as your primary data store. Be deliberate about mappings (keyword vs text) and plan your index lifecycle strategy for time-based data.

---

### Time-Series Databases

Time-series databases are optimized for the specific workload pattern of time-stamped data: high-throughput appends, time-range queries, and downsampling/aggregation. While general-purpose databases can handle time-series data, specialized databases provide better compression, faster queries, and built-in retention policies.

**TimescaleDB** is a PostgreSQL extension that adds time-series capabilities without giving up SQL or the PostgreSQL ecosystem. It automatically partitions data into "chunks" by time and provides specialized functions for time-series analysis:

```sql
-- Convert a regular table to a hypertable
SELECT create_hypertable('metrics', 'time');

-- Insert data normally
INSERT INTO metrics (time, device_id, temperature, humidity)
VALUES (NOW(), 'sensor-01', 22.5, 45.0);

-- Time-bucketed aggregation (TimescaleDB function)
SELECT
    time_bucket('1 hour', time) AS hour,
    device_id,
    AVG(temperature) AS avg_temp,
    MAX(temperature) AS max_temp,
    MIN(temperature) AS min_temp
FROM metrics
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour, device_id
ORDER BY hour DESC;

-- Continuous aggregates (materialized views that auto-update)
CREATE MATERIALIZED VIEW hourly_metrics
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    device_id,
    AVG(temperature) AS avg_temp,
    COUNT(*) AS num_readings
FROM metrics
GROUP BY hour, device_id;

-- Retention policy: automatically drop data older than 90 days
SELECT add_retention_policy('metrics', INTERVAL '90 days');

-- Compression policy: compress chunks older than 7 days
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id'
);
SELECT add_compression_policy('metrics', INTERVAL '7 days');
```

The `time_bucket` aggregation query in the middle of that block returns rows grouped into fixed one-hour windows:

```text
         hour          | device_id | avg_temp | max_temp | min_temp
-----------------------+-----------+----------+----------+----------
 2025-06-04 14:00:00+00 | sensor-01 |    22.48 |     23.1 |     21.9
 2025-06-04 14:00:00+00 | sensor-02 |    19.73 |     20.4 |     19.0
 2025-06-04 13:00:00+00 | sensor-01 |    22.51 |     23.0 |     22.0
(3 rows)
```

**How to read this output:** `time_bucket('1 hour', time)` is the time-series analog of `GROUP BY` on a rounded timestamp -- it snaps every raw reading to the start of its hour, so thousands of per-second samples collapse into one row per sensor per hour. Note the timestamps land exactly on the hour (`14:00:00`, `13:00:00`), which is what makes the buckets comparable across devices and joinable to other hourly series. In production this query is cheap because TimescaleDB only touches the chunks covering the last 24 hours rather than the whole table; the `CREATE MATERIALIZED VIEW ... timescaledb.continuous` defined just below pre-computes exactly this rollup so dashboards read from `hourly_metrics` instead of recomputing the average on every page load.

Other notable time-series databases include **InfluxDB** (purpose-built for metrics with its own query language, Flux), **Prometheus** (pull-based monitoring system with PromQL), and **ClickHouse** (column-oriented analytics database with exceptional query speed on large datasets).

> **Key Takeaway:** For time-series workloads, consider TimescaleDB if you want to stay in the PostgreSQL ecosystem. It provides automatic partitioning, compression, continuous aggregates, and retention policies with familiar SQL. For pure metrics monitoring, Prometheus is the standard. For large-scale analytics, ClickHouse offers unmatched query performance.
