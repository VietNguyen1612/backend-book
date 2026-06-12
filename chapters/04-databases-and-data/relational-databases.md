[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 4.1 Relational Databases (PostgreSQL Focus)

The previous chapter dealt with the shape of systems — how to draw boundaries between services and layers. This chapter descends into the layer those boundaries ultimately protect: the data. For most backend systems, the relational database is the single stateful component everything else depends on, and it is where the most expensive production incidents originate. A query that was fast at ten thousand rows grinds to a halt at ten million; a deploy stalls because an `ALTER TABLE` took a lock nobody anticipated; two concurrent requests both read a balance of 100 and both write 50; a table that should be 2 GB occupies 40 GB because VACUUM fell behind. None of these are exotic — they are the ordinary failure modes of teams that treat the database as a black box behind an ORM.

This section opens that box, using PostgreSQL as the concrete engine. By the end you should be able to answer questions like: why is this query slow, and what does its execution plan actually say? Which index type fits this access pattern, and what does each additional index cost on writes? What anomalies can occur at Read Committed that Serializable would prevent, and when is the stricter level worth its retry cost? When should a row be locked pessimistically with `SELECT FOR UPDATE` rather than guarded by an optimistic version column? And which problems — time-series retention, analytics, JSON documents, full-text search — can PostgreSQL itself solve before you reach for another system?

We build from the ground up. *Storage Internals & Durability* establishes the physical foundation — pages, the buffer pool, the write-ahead log, MVCC version storage, and B-tree versus LSM engines. *Query Optimization* shows how to read execution plans and fix the slow queries that foundation explains. *Indexing Strategies* surveys the index types PostgreSQL offers and the decision rules for choosing among them. *Transactions & Concurrency* turns from performance to correctness: ACID, isolation levels, locking, and MVCC's operational consequences. Finally, *Advanced Features* covers the capabilities — partitioning, window functions, JSONB, full-text search, replication, connection pooling — that often make PostgreSQL the only database you need.

## Storage Internals & Durability

Before tuning queries, it helps to understand how PostgreSQL physically stores and protects data. Almost every performance and durability trade-off in a relational database traces back to these mechanics.

### Pages and the Buffer Pool

PostgreSQL reads and writes data in fixed-size **pages** (blocks), 8 KB by default. A table or index is just a sequence of such pages on disk. Crucially, the engine never operates on a row directly from disk -- it first loads the whole page into a shared in-memory cache called the **buffer pool**, sized by the `shared_buffers` setting. On top of that, the operating system's page cache provides a second tier of caching. The practical consequence is that almost all query tuning is really about keeping your *working set* (the hot pages a query touches) resident in these caches so that reads are served from RAM instead of disk.

```sql
-- See how much of each table is currently cached in shared_buffers
-- (requires the pg_buffercache extension)
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

SELECT c.relname,
       count(*) AS buffers,
       pg_size_pretty(count(*) * 8192) AS cached,
       pg_size_pretty(pg_relation_size(c.oid)) AS total
FROM pg_buffercache b
JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
GROUP BY c.relname, c.oid
ORDER BY buffers DESC
LIMIT 5;
```

```text
   relname   | buffers |  cached  |  total
-------------+---------+----------+---------
 orders      |   31204 | 244 MB   | 612 MB
 order_items |   18550 | 145 MB   | 1208 MB
 users       |    4096 | 32 MB    | 32 MB
 sessions    |     980 | 7664 kB  | 410 MB
```

**How to read this output:** Compare `cached` against `total` per table. `users` is 100% cached (32 MB of 32 MB) -- every query against it is served from RAM. `order_items` has only 145 MB of 1.2 GB resident, so range scans over it will trigger disk reads and run inconsistently depending on what got evicted. This view is the concrete way to answer "is `shared_buffers` big enough for my working set?" -- if your hot tables are chronically under-cached and the box has spare RAM, that is your signal to raise `shared_buffers` (a common starting point is ~25% of system memory, leaving the rest for the OS page cache). Sizing it to fit the working set, not the whole database, is the real goal.

### Write-Ahead Log (WAL)

Durability -- the "D" in ACID -- comes from the **Write-Ahead Log**. The rule is simple and absolute: the WAL record describing a change must be flushed (`fsync`'d) to durable storage *before* the modified ("dirty") data page is allowed to be written back to disk. Note the ordering carefully -- the in-memory page in the buffer pool is updated *first*; what the WAL protocol guarantees is that the corresponding WAL record is durable before that dirty page is *flushed to disk* (and, separately, that the WAL up to the commit record is durable before COMMIT is acknowledged). WAL writes are sequential appends, which are far faster than the random I/O of updating scattered heap pages, so the commit path stays fast. On a crash, PostgreSQL replays the WAL from the last **checkpoint** to bring the data files back to a consistent state. This same WAL stream is what feeds streaming replication and Point-in-Time Recovery.

A **checkpoint** periodically flushes all dirty buffer-pool pages to the data files and records a marker in the WAL; recovery only needs to replay WAL written after the most recent checkpoint. Tuning checkpoint frequency is a balance: frequent checkpoints mean fast recovery but more constant I/O; infrequent checkpoints mean less steady-state I/O but longer recovery and larger WAL.

```sql
-- Inspect WAL and checkpoint activity
SELECT pg_current_wal_lsn() AS current_wal_position;

-- NOTE: this view shape is for PostgreSQL <= 16. In PG 17+ these columns were split out:
-- checkpoints_* / buffers_checkpoint moved to pg_stat_checkpointer, and buffers_backend
-- moved to pg_stat_io. (buffers_clean stays in pg_stat_bgwriter.)
SELECT checkpoints_timed, checkpoints_req,
       buffers_checkpoint, buffers_clean, buffers_backend
FROM pg_stat_bgwriter;
```

```text
 checkpoints_timed | checkpoints_req | buffers_checkpoint | buffers_clean | buffers_backend
-------------------+-----------------+--------------------+---------------+-----------------
            14820  |            3120 |           48201334 |       2104998 |        18044510
```

**How to read this output:** `checkpoints_timed` (triggered by `checkpoint_timeout`) versus `checkpoints_req` (forced because `max_wal_size` filled up first) is the headline. Here ~17% of checkpoints are *requested* rather than timed, which means write bursts are filling the WAL faster than the timeout fires -- raising `max_wal_size` would smooth the I/O into fewer, scheduled checkpoints. The `buffers_backend` number being high (dirty pages flushed by ordinary backends rather than the background writer or checkpointer) is a classic sign that foreground queries are doing flush work they should not, hurting latency. `fsync = off` would make all of this faster and is a guaranteed way to corrupt your database on a crash -- never do it on real data.

### Heap, TIDs, and the Clustered-Index Contrast

PostgreSQL stores table rows in an unordered **heap** -- rows live wherever there is free space, in no particular order. Every index (including the primary key) is a separate structure whose leaf entries point back to heap rows via a **TID** (tuple identifier: a `(page number, item offset)` pair). So an index lookup in PostgreSQL is two steps: walk the index to get TIDs, then fetch those rows from the heap.

This is fundamentally different from MySQL's InnoDB, which uses a **clustered index**: the table *is* the primary-key B-tree, with full rows stored in the leaf nodes. Secondary indexes in InnoDB store the primary-key value (not a physical pointer), so a secondary-index lookup costs two B-tree traversals. The trade-offs fall out directly from this layout:

- InnoDB primary-key lookups and range scans are very fast (rows are physically ordered by PK and stored in the leaf). PostgreSQL needs the extra heap fetch, which is why **index-only scans** and the visibility map matter so much there.
- A fat or randomly-distributed primary key is more expensive in InnoDB because its value is duplicated into every secondary index. This is one reason monotonic (time-sorted) keys like a `BIGINT` or UUIDv7 are preferred over random UUIDv4 for InnoDB primary keys.
- PostgreSQL can `CLUSTER` a table to physically reorder it by an index, but unlike InnoDB the ordering is not maintained automatically after writes.

### MVCC Storage: Heap Bloat vs Undo Log

Both PostgreSQL and InnoDB use MVCC so readers never block writers, but they store old row versions differently -- and this single design choice drives very different operational behavior:

- **PostgreSQL** keeps old versions *in the heap itself*. An UPDATE writes a brand-new tuple and marks the old one dead (via `xmax`). Dead tuples accumulate and must be reclaimed by **VACUUM**; left unchecked they cause table and index **bloat**. The upside is that ROLLBACK is essentially free (the new tuple is simply never made visible).
- **InnoDB** keeps old versions in a separate **undo log** (rollback segments). The main B-tree holds only the current row; readers reconstruct older versions by walking undo records. There is no equivalent of heap bloat from dead tuples, but ROLLBACK must actively undo changes, and a long-running read transaction forces the undo log to grow to preserve the versions that transaction can still see (the analog of PostgreSQL's "long transactions block VACUUM" problem).

The lesson for both engines is the same: long-running transactions are the enemy. In PostgreSQL they pin dead tuples and prevent VACUUM from reclaiming them; in InnoDB they balloon the undo log. Keep transactions short.

### B-tree vs LSM Storage Engines

The B-tree is the dominant on-disk index structure for relational databases (PostgreSQL, InnoDB): it supports reads, range scans, and in-place updates well, with O(log n) lookups. But it is not the only choice, and picking a database is partly picking a storage engine.

A **Log-Structured Merge-tree (LSM)** -- used by Cassandra, RocksDB, ScyllaDB, and as an option in some engines -- optimizes for write throughput. Writes go to an in-memory **memtable** plus a sequential commit log, then are flushed to immutable on-disk files (**SSTables**); background **compaction** merges and rewrites these files to keep reads efficient and discard deleted/overwritten data. The trade-offs:

- LSM excels at high-volume, append-heavy write workloads because every write is a fast sequential append rather than a random in-place page update.
- Reads can be slower (a key may live in the memtable or any of several SSTable levels, mitigated by bloom filters and caching), and compaction consumes background I/O and CPU.
- Deletes are not in-place either; they write a **tombstone** marker that is only physically removed during compaction -- which is why tombstone buildup is a real operational concern in LSM systems (revisited under Cassandra in the NoSQL chapter).

> **Key Takeaway:** The shape of a relational database's performance and durability comes from its storage layer: pages cached in the buffer pool, durability guaranteed by WAL-before-data, heap-plus-TID vs clustered layout determining lookup cost, MVCC version storage dictating whether you fight bloat or undo growth, and B-tree vs LSM choosing whether you optimize for balanced reads/writes or raw write throughput. Knowing these internals is what turns "add an index" into informed tuning.

---

## Query Optimization

The storage internals we just covered explain *where* query time goes — pages fetched from disk, heap lookups behind index scans, caches hit or missed. This section turns that understanding into practice: how to see what the planner actually decided to do with your query, and how to fix it when the answer is unflattering.

### EXPLAIN ANALYZE: Reading Execution Plans

The single most important tool for understanding query performance in PostgreSQL is `EXPLAIN ANALYZE`. While `EXPLAIN` alone shows the planner's estimated plan, adding `ANALYZE` actually executes the query and reports real timing and row counts. This distinction matters because the planner's estimates can be wildly inaccurate when table statistics are stale.

```sql
EXPLAIN ANALYZE
SELECT u.id, u.email, COUNT(o.id) AS order_count
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2025-01-01'
GROUP BY u.id, u.email
ORDER BY order_count DESC
LIMIT 10;
```

A typical output looks like this:

```
                                                          QUERY PLAN
------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=1523.45..1523.47 rows=10 width=48) (actual time=12.431..12.435 rows=10 loops=1)
   ->  Sort  (cost=1523.45..1530.12 rows=2670 width=48) (actual time=12.429..12.432 rows=10 loops=1)
         Sort Key: (count(o.id)) DESC
         Sort Method: top-N heapsort  Memory: 26kB
         ->  HashAggregate  (cost=1450.20..1476.90 rows=2670 width=48) (actual time=11.895..12.148 rows=2670 loops=1)
               Group Key: u.id
               Batches: 1  Memory Usage: 369kB
               ->  Hash Join  (cost=120.55..1403.85 rows=9270 width=44) (actual time=1.234..9.567 rows=9270 loops=1)
                     Hash Cond: (o.user_id = u.id)
                     ->  Seq Scan on orders o  (cost=0.00..983.00 rows=50000 width=8) (actual time=0.012..3.456 rows=50000 loops=1)
                     ->  Hash  (cost=87.20..87.20 rows=2668 width=40) (actual time=1.198..1.199 rows=2670 loops=1)
                           Buckets: 4096  Batches: 1  Memory Usage: 195kB
                           ->  Index Scan using idx_users_created_at on users u  (cost=0.29..87.20 rows=2668 width=40)
                                                                                 (actual time=0.025..0.789 rows=2670 loops=1)
                                 Index Cond: (created_at > '2025-01-01 00:00:00'::timestamp)
 Planning Time: 0.452 ms
 Execution Time: 12.521 ms
```

Read the plan bottom-up, inside-out. The innermost nodes execute first. Key metrics to watch:

- **actual time**: The first number is time to return the first row; the second is time to return all rows (in milliseconds). Multiply by `loops` for the real wall-clock cost.
- **rows**: Compare `rows=2668` (estimated) against `actual ... rows=2670`. When these diverge significantly (by 10x or more), the planner is making bad decisions. Run `ANALYZE` on the table to update statistics.
- **loops**: If a node executes multiple times (common in nested loop joins), the reported times are per-loop. Total cost = time * loops.
- **Sort Method / Memory**: Shows whether sorts spill to disk. "external merge" means insufficient `work_mem`.

The equivalent Django ORM query that produces the SQL above:

```python
from django.db.models import Count

top_users = (
    User.objects
    .filter(created_at__gt='2025-01-01')
    .annotate(order_count=Count('orders'))
    .order_by('-order_count')[:10]
)

# To see the generated SQL:
print(top_users.query)
```

Printing `.query` shows the SQL Django will send (note: this is Django's internal representation, with parameters inlined rather than the exact parameterized form the driver executes):

```text
SELECT "users"."id", "users"."email", COUNT("orders"."id") AS "order_count"
FROM "users" LEFT OUTER JOIN "orders" ON ("users"."id" = "orders"."user_id")
WHERE "users"."created_at" > 2025-01-01 GROUP BY "users"."id", "users"."email"
ORDER BY "order_count" DESC LIMIT 10
```

**How to read this output:** `top_users.query` is the single most useful debugging trick when an ORM query is mysteriously slow -- it lets you paste the generated SQL straight into `EXPLAIN ANALYZE`. Notice Django emits a `LEFT OUTER JOIN` (not an inner join) because `annotate(Count(...))` must still count users who have zero orders; if you intended an inner join you would need an explicit `.filter()`. The datetime appears unquoted here because `.query` is a developer-facing approximation -- never copy it into application code as a string, since that would expose you to SQL injection; let the ORM parameterize it.

### Seq Scan vs Index Scan

A sequential scan reads every row in a table from disk, page by page. This is not inherently bad. For small tables (under a few thousand rows), a sequential scan is often faster than an index scan because it avoids the overhead of traversing the index tree and performing random I/O to fetch heap tuples. The planner also favors sequential scans when the query's selectivity is low -- for example, if a WHERE clause matches more than roughly 5-15% of the table, the planner often decides that reading the entire table sequentially is cheaper than performing thousands of random index lookups.

An index scan traverses the B-tree (or other index type) to find matching entries, then fetches the corresponding rows from the heap (the actual table data). This involves random I/O, which is slower per page than sequential I/O but dramatically faster overall when only a small fraction of the table is needed.

An index-only scan is even better: if all columns required by the query are present in the index itself (a "covering index"), PostgreSQL can answer the query entirely from the index without touching the heap at all, provided the visibility map confirms the pages are all-visible.

```sql
-- Covering index: includes all columns the query needs
CREATE INDEX idx_orders_covering
ON orders (user_id)
INCLUDE (total_amount, created_at);

-- This query can use an index-only scan:
EXPLAIN ANALYZE
SELECT user_id, total_amount, created_at
FROM orders
WHERE user_id = 42;
```

With the covering index in place, the plan reports an index-only scan:

```text
                                                          QUERY PLAN
-----------------------------------------------------------------------------------------------------------------------------
 Index Only Scan using idx_orders_covering on orders  (cost=0.42..8.61 rows=12 width=20) (actual time=0.018..0.024 rows=12 loops=1)
   Index Cond: (user_id = 42)
   Heap Fetches: 0
 Planning Time: 0.094 ms
 Execution Time: 0.041 ms
```

**How to read this output:** The node type `Index Only Scan` (not the usual `Index Scan`) is the proof that PostgreSQL answered the query entirely from the index without touching the table heap. The line to watch is `Heap Fetches: 0` -- it means every matching page was marked all-visible in the visibility map, so zero random heap reads were needed. In a hot read path (think a dashboard hitting this query thousands of times a second) eliminating heap fetches is what turns a "fast" query into a "free" one. If you instead see a high `Heap Fetches` count, the table needs a `VACUUM` to refresh its visibility map, otherwise the covering index buys you nothing.

### Query Planner and Statistics

PostgreSQL's query planner is cost-based: it estimates the cost of various execution strategies and picks the cheapest one. These cost estimates depend heavily on table statistics -- histograms of column value distributions, most-common-values lists, and correlation data. When statistics are stale, the planner makes poor choices.

The `ANALYZE` command (not to be confused with `EXPLAIN ANALYZE`) scans a sample of the table and updates these statistics in the `pg_statistic` catalog:

```sql
-- Update statistics for a specific table
ANALYZE orders;

-- Update statistics for all tables in the database
ANALYZE;

-- Check when a table was last analyzed
SELECT relname, last_analyze, last_autoanalyze, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
WHERE relname = 'orders';
```

This returns one row summarizing the table's maintenance history:

```text
 relname | last_analyze        | last_autoanalyze    | n_live_tup | n_dead_tup
---------+---------------------+---------------------+------------+-----------
 orders  | 2025-06-04 09:12:33 | 2025-06-03 22:41:07 |      48213 |       1502
```

**How to read this output:** `last_analyze` is the last *manual* `ANALYZE`; `last_autoanalyze` is the last one autovacuum ran on its own -- if both are `NULL`, the planner has never seen real statistics for this table and is guessing, which is a classic root cause of a sudden bad plan after a bulk load. `n_dead_tup` relative to `n_live_tup` tells you how much bloat has built up; here ~3% dead is healthy. In an interview, knowing to check this view first (rather than blaming the query) signals real operational experience.

Autovacuum runs `ANALYZE` automatically, but after bulk loads or major data changes, you should run it manually. You can also increase the statistics target for columns with unusual distributions:

```sql
-- Increase statistics granularity for a specific column (default is 100)
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;
```

### Common Anti-Patterns

**SELECT * fetches unnecessary columns.** This wastes I/O bandwidth, memory, and network transfer. It also prevents index-only scans. Always specify only the columns you need. In Django, use `values()` or `only()` to limit selected fields:

```python
# Bad: fetches all columns
users = User.objects.all()

# Good: fetches only what is needed
users = User.objects.values('id', 'email', 'created_at')

# Or with model instances that defer unused fields:
users = User.objects.only('id', 'email', 'created_at')
```

**Missing indexes on WHERE and JOIN columns.** Any column that regularly appears in a WHERE clause, JOIN condition, or ORDER BY clause is a candidate for indexing. Without an index, PostgreSQL must perform a sequential scan. Monitor slow queries using `pg_stat_statements` and look for sequential scans on large tables in `pg_stat_user_tables`:

```sql
-- Find tables with a high ratio of sequential scans
SELECT relname,
       seq_scan,
       idx_scan,
       seq_scan - idx_scan AS too_many_seq_scans,
       pg_size_pretty(pg_relation_size(relid)) AS table_size
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
  AND pg_relation_size(relid) > 10485760  -- tables over 10MB
ORDER BY seq_scan - idx_scan DESC;
```

A result on a real database might look like:

```text
   relname    | seq_scan | idx_scan | too_many_seq_scans | table_size
--------------+----------+----------+--------------------+-----------
 audit_log    |   182304 |     1120 |             181184 | 1240 MB
 order_items  |    45120 |    33890 |              11230 | 612 MB
```

**How to read this output:** Each row is a large table the planner keeps reading end-to-end. `audit_log` with 182k sequential scans against a 1.2 GB table is an alarm bell -- some hot query is missing an index, and every execution drags the whole table through memory. This view is your triage list: start at the top, find the offending query (via `pg_stat_statements`), and add the index. Note the caveat -- a high `seq_scan` count is fine for a tiny lookup table the planner reads in full on purpose; that is why the query filters to tables over 10 MB.

**N+1 queries** occur when code fetches a list of objects and then issues a separate query for each related object. This is extremely common in ORM-based code. In Django, use `select_related` (for ForeignKey / OneToOne, performs a JOIN) and `prefetch_related` (for ManyToMany / reverse ForeignKey, performs a separate IN query):

```python
# Bad: N+1 -- one query for orders, then one query per order for the user
orders = Order.objects.all()
for order in orders:
    print(order.user.email)  # Each access triggers a separate query

# Good: single JOIN query
orders = Order.objects.select_related('user').all()
for order in orders:
    print(order.user.email)  # No additional query

# Good for reverse/many-to-many relations:
users = User.objects.prefetch_related('orders').all()
for user in users:
    print(user.orders.count())  # Uses prefetched data
```

**LIKE '%prefix' (leading wildcard) cannot use a standard B-tree index** because B-trees are ordered left-to-right. For substring search, use a trigram index (`pg_trgm` extension) or PostgreSQL's built-in full-text search:

```sql
-- Enable the trigram extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create a GIN trigram index for substring matching
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- Now this query can use the index:
SELECT * FROM products WHERE name LIKE '%widget%';
SELECT * FROM products WHERE name ILIKE '%Widget%';  -- Case-insensitive too
```

> **Key Takeaway:** Query optimization is an empirical discipline. Always use `EXPLAIN ANALYZE` to verify your assumptions. Keep statistics current with `ANALYZE`. The biggest wins usually come from adding the right index and eliminating N+1 queries, not from rewriting SQL.

---

## Indexing Strategies

`EXPLAIN ANALYZE` tells you *that* a query needs an index; it does not tell you *which kind*. PostgreSQL offers several index types with very different shapes, and the right choice depends on the data and the access pattern — a point we will keep returning to. We start with the default that covers most cases, then work through the specialized types and the techniques for keeping indexes small and targeted.

### B-tree (Default Index)

B-tree is the default and most versatile index type in PostgreSQL. It supports equality (`=`) and range queries (`<`, `>`, `<=`, `>=`, `BETWEEN`), as well as `IS NULL`, `ORDER BY`, and pattern matching with anchored `LIKE 'prefix%'`.

A B-tree is a balanced tree structure where internal nodes contain keys and pointers to child nodes, and leaf nodes contain keys and pointers to heap tuples. The tree is always balanced -- every leaf is the same distance from the root, ensuring O(log n) lookup time.

```
                        B-tree Index Structure
                        ======================

                          [  50  |  100  ]              <-- Root node
                         /       |        \
                        /        |         \
              [10|20|30|40]  [60|70|80|90]  [110|120|130|140]   <-- Internal nodes
              / | | | \      / | | | \       / |  |  |  \
             /  | | |  \    /  | | |  \     /  |  |  |   \
            v   v v v   v  v   v v v   v   v   v  v  v    v    <-- Leaf nodes
           [1] ... [45] [51]  ... [95] [101] ... [145]          (contain TIDs
            |        |    |        |     |         |              pointing to
            v        v    v        v     v         v              heap tuples)
          heap     heap  heap    heap  heap      heap
```

**Multi-column indexes** follow the leftmost prefix rule. An index on `(a, b, c)` can be used for queries filtering on `(a)`, `(a, b)`, or `(a, b, c)`, but not for queries filtering only on `(b)` or `(c)`. Think of it like a phone book sorted by last name, then first name: you can look up by last name alone, but not by first name alone.

```sql
-- Multi-column index
CREATE INDEX idx_orders_user_status_date
ON orders (user_id, status, created_at);

-- These queries CAN use the index:
SELECT * FROM orders WHERE user_id = 42;
SELECT * FROM orders WHERE user_id = 42 AND status = 'shipped';
SELECT * FROM orders WHERE user_id = 42 AND status = 'shipped' AND created_at > '2025-06-01';

-- These queries CANNOT efficiently use the index:
SELECT * FROM orders WHERE status = 'shipped';                    -- skips leading column
SELECT * FROM orders WHERE created_at > '2025-06-01';             -- skips leading columns
```

**Covering indexes** use the `INCLUDE` clause (PostgreSQL 11+) to store additional columns in the leaf nodes of the index without making them part of the search key. This enables index-only scans for queries that need those extra columns:

```sql
-- Covering index: user_id is the search key; total_amount is just along for the ride
CREATE INDEX idx_orders_user_covering
ON orders (user_id)
INCLUDE (total_amount, status);

-- This query can be satisfied with an index-only scan:
SELECT user_id, total_amount, status
FROM orders
WHERE user_id = 42;
```

### Hash Index

Hash indexes support only equality comparisons (`=`). They are faster than B-tree for exact-match lookups because the key is hashed to a bucket directly, avoiding tree traversal. Since PostgreSQL 10, hash indexes are crash-safe and WAL-logged.

```sql
CREATE INDEX idx_sessions_token_hash ON sessions USING hash (token);

-- Fast for exact match:
SELECT * FROM sessions WHERE token = 'abc123def456';

-- Cannot use hash index for:
SELECT * FROM sessions WHERE token > 'abc';  -- range query
SELECT * FROM sessions ORDER BY token;        -- sorting
```

In practice, B-tree indexes are almost always preferred because they are more versatile and the performance difference for equality is small. Consider hash indexes only for very large tables with purely equality-based lookups and no range or sort requirements.

### GIN (Generalized Inverted Index)

GIN indexes are designed for values that contain multiple elements -- arrays, JSONB documents, full-text search vectors, and other composite types. A GIN index maps each element (array member, JSON key, lexeme) to the set of rows containing that element.

```sql
-- GIN index for JSONB containment queries
CREATE INDEX idx_products_attrs_gin ON products USING gin (attributes);

-- Find products where attributes contain {"color": "red"}
SELECT * FROM products WHERE attributes @> '{"color": "red"}';

-- GIN index for array operations
CREATE INDEX idx_posts_tags_gin ON posts USING gin (tags);

-- Find posts tagged with 'python'
SELECT * FROM posts WHERE tags @> ARRAY['python'];

-- GIN index for full-text search
CREATE INDEX idx_articles_fts ON articles USING gin (to_tsvector('english', title || ' ' || body));
```

GIN indexes are slower to build and update than B-tree (because inserting one row may require updating many index entries), but they are very fast for lookups. PostgreSQL supports "fastupdate" for GIN which batches pending entries for better write throughput at the cost of slightly slower reads.

### GiST (Generalized Search Tree)

GiST indexes support geometric data, range types, full-text search, and nearest-neighbor queries. Unlike GIN which stores exact element-to-row mappings, GiST uses a lossy structure that may require recheck of results.

```sql
-- GiST index for range queries
CREATE INDEX idx_reservations_during ON reservations USING gist (during);

-- Find overlapping reservations
SELECT * FROM reservations
WHERE during && tsrange('2025-06-01', '2025-06-15');

-- GiST index for nearest-neighbor search on geometric data
CREATE INDEX idx_locations_point ON locations USING gist (coordinates);

-- Find 5 nearest locations to a point
SELECT *, coordinates <-> point(40.7128, -74.0060) AS distance
FROM locations
ORDER BY coordinates <-> point(40.7128, -74.0060)
LIMIT 5;
```

### BRIN (Block Range Index)

BRIN indexes are extremely compact. Instead of indexing individual rows, they store summary information (min/max values) for each block range (a group of consecutive physical pages). This makes BRIN indexes tiny -- often 1000x smaller than equivalent B-tree indexes -- but only effective when data is physically ordered on disk in the same order as the indexed column.

```sql
-- Perfect for a time-series table where rows are inserted in timestamp order
CREATE INDEX idx_events_created_brin ON events USING brin (created_at)
  WITH (pages_per_range = 32);

-- The index is tiny but effective for range scans:
EXPLAIN ANALYZE
SELECT * FROM events
WHERE created_at BETWEEN '2025-06-01' AND '2025-06-02';
```

On a well-ordered events table the plan looks like:

```text
                                                  QUERY PLAN
---------------------------------------------------------------------------------------------------------------
 Bitmap Heap Scan on events  (cost=12.40..4821.00 rows=2880 width=120) (actual time=0.211..6.430 rows=2873 loops=1)
   Recheck Cond: ((created_at >= '2025-06-01') AND (created_at <= '2025-06-02'))
   Rows Removed by Index Recheck: 1287
   Heap Blocks: lossy=64
   ->  Bitmap Index Scan on idx_events_created_brin  (cost=0.00..11.68 rows=2880 width=0) (actual time=0.041..0.041 rows=640 loops=1)
         Index Cond: ((created_at >= '2025-06-01') AND (created_at <= '2025-06-02'))
 Planning Time: 0.120 ms
 Execution Time: 6.610 ms
```

**How to read this output:** BRIN always drives a `Bitmap Heap Scan` with a `Recheck Cond`, because the index only knows the min/max of each block range -- it can rule blocks out but cannot confirm individual rows, so PostgreSQL must re-test every row in the surviving blocks. `Heap Blocks: lossy=64` and `Rows Removed by Index Recheck: 1287` quantify that overhead: 64 block ranges were scanned and 1,287 rows were read only to be discarded. That waste is acceptable here because the index itself is a few kilobytes instead of hundreds of megabytes. The whole bet pays off only while the data stays physically ordered by `created_at` -- if you see `Rows Removed by Index Recheck` explode into the millions, the table has been updated out of order and the BRIN index has degraded into a near-full scan.

BRIN indexes shine for append-only tables (logs, events, metrics) where the physical order matches the column order. If rows are inserted out of order or frequently updated, BRIN becomes ineffective because each block range will have wide min/max boundaries, causing many false positives.

### Partial Indexes

A partial index indexes only a subset of rows, defined by a WHERE predicate. This keeps the index small and focused. It is particularly useful when you frequently query a small, well-defined subset of a large table.

```sql
-- Only index pending orders (assume 5% of total orders)
CREATE INDEX idx_orders_pending ON orders (created_at)
WHERE status = 'pending';

-- This query uses the partial index:
SELECT * FROM orders WHERE status = 'pending' AND created_at > '2025-06-01';

-- Partial unique index: enforce uniqueness only for active records
CREATE UNIQUE INDEX idx_users_email_active ON users (email)
WHERE deleted_at IS NULL;
-- This allows multiple "deleted" rows with the same email
```

### Expression Indexes

An expression index indexes the result of a function or expression rather than a raw column value. The query must use the exact same expression to benefit from the index.

```sql
-- Index on lowercase email for case-insensitive lookups
CREATE INDEX idx_users_email_lower ON users (lower(email));

-- This query uses the expression index:
SELECT * FROM users WHERE lower(email) = 'john@example.com';

-- Index on extracted year from a timestamp
CREATE INDEX idx_orders_year ON orders ((EXTRACT(YEAR FROM created_at)));

-- This query uses it:
SELECT * FROM orders WHERE EXTRACT(YEAR FROM created_at) = 2025;
```

In Django, you can define indexes in the model's Meta class:

```python
from django.db import models
from django.db.models import Index
from django.db.models.functions import Lower

class User(models.Model):
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            # Expression index (passing an expression like Lower('email') to Index
            # requires Django 4.0+)
            Index(Lower('email'), name='idx_user_email_lower'),
            # Partial index (the condition= argument has been supported since Django 2.2)
            Index(
                fields=['email'],
                name='idx_user_email_active',
                condition=models.Q(deleted_at__isnull=True),
            ),
            # Multi-column index
            Index(fields=['created_at', 'email'], name='idx_user_created_email'),
        ]
```

> **Key Takeaway:** There is no single "best" index type. B-tree covers most needs. Use GIN for composite values (JSONB, arrays, full-text), BRIN for naturally ordered large tables, and partial/expression indexes to keep things targeted and small. Every index speeds up reads but slows down writes -- index deliberately, not indiscriminately.

---

## Transactions & Concurrency

So far we have been concerned with making individual queries fast. But a production database is never running one query at a time — it is interleaving hundreds, and the harder question is whether they remain *correct* while doing so. This section covers the guarantees the database makes about concurrent work, the anomalies each isolation level does and does not prevent, and the locking strategies you reach for when the defaults are not enough.

### ACID Properties

ACID is the set of guarantees that relational databases provide for transactions:

**Atomicity** means a transaction is all-or-nothing. If any statement in a transaction fails, the entire transaction is rolled back, leaving the database unchanged. There is no such thing as a "half-applied" transaction.

**Consistency** means a transaction takes the database from one valid state to another. All constraints (CHECK, UNIQUE, FOREIGN KEY, NOT NULL) are enforced. If a transaction would violate a constraint, it is aborted.

**Isolation** means concurrent transactions do not see each other's uncommitted changes (the degree of isolation depends on the isolation level). Without isolation, concurrent transactions could read partially-updated data and produce incorrect results.

**Durability** means once a transaction is committed, its changes survive any subsequent crash, power failure, or system error. PostgreSQL achieves this by writing changes to the Write-Ahead Log (WAL) before acknowledging the commit.

```sql
BEGIN;
  UPDATE accounts SET balance = balance - 500 WHERE id = 1;
  UPDATE accounts SET balance = balance + 500 WHERE id = 2;

  -- If either UPDATE fails, or the application calls ROLLBACK,
  -- neither account is modified.
COMMIT;
```

In Django:

```python
from django.db import transaction

# Using the decorator
@transaction.atomic
def transfer_funds(from_id, to_id, amount):
    sender = Account.objects.select_for_update().get(id=from_id)
    receiver = Account.objects.select_for_update().get(id=to_id)

    if sender.balance < amount:
        raise ValueError("Insufficient funds")

    sender.balance -= amount
    sender.save()
    receiver.balance += amount
    receiver.save()

# Using the context manager
def transfer_funds_v2(from_id, to_id, amount):
    with transaction.atomic():
        sender = Account.objects.select_for_update().get(id=from_id)
        receiver = Account.objects.select_for_update().get(id=to_id)
        sender.balance -= amount
        sender.save()
        receiver.balance += amount
        receiver.save()
```

### Isolation Levels

PostgreSQL supports four isolation levels, each providing a different trade-off between correctness and performance:

**Read Uncommitted** is the weakest level. In theory, it allows "dirty reads" (seeing uncommitted changes from other transactions). However, PostgreSQL treats this the same as Read Committed -- dirty reads are never actually possible in PostgreSQL.

**Read Committed** is the PostgreSQL default. Each statement within a transaction sees a snapshot of data as of the start of that statement. If another transaction commits between two statements in your transaction, the second statement sees the new data. This prevents dirty reads but allows non-repeatable reads and phantom rows.

**Repeatable Read** provides a snapshot as of the start of the transaction (not each statement). All queries in the transaction see the same consistent data. If another transaction modifies rows that your transaction has read, your transaction gets a serialization error if it tries to update those rows, and must retry.

**Serializable** is the strongest level. It uses Serializable Snapshot Isolation (SSI) to detect and prevent all anomalies, ensuring that the result is equivalent to running transactions one at a time. Transactions that would cause anomalies receive a serialization failure and must retry.

```sql
-- Set isolation level for a transaction
BEGIN ISOLATION LEVEL SERIALIZABLE;
  SELECT * FROM inventory WHERE product_id = 1;
  -- If another transaction modifies inventory for product_id=1
  -- and commits before us, our COMMIT will fail with a serialization error.
  UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 1;
COMMIT;
```

```python
# Django: set isolation level per-transaction (PostgreSQL)
from django.db import connection

# Using raw SQL for isolation level
with connection.cursor() as cursor:
    cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    # ... perform queries ...
```

### Concurrency Anomalies: Lost Update and Write Skew

The isolation levels above are defined by *which anomalies they prevent*. Two of these anomalies cause subtle, expensive bugs in production and come up constantly in interviews, so they deserve a closer look.

**Lost update** happens when two transactions read the same row, each computes a new value from what it read, and then both write back -- the second write silently clobbers the first. The classic case is a read-modify-write in application code:

```sql
-- Transaction A                          -- Transaction B
BEGIN;                                     BEGIN;
SELECT balance FROM accounts              SELECT balance FROM accounts
  WHERE id = 1;  -- reads 100               WHERE id = 1;  -- also reads 100
-- app computes 100 - 30 = 70             -- app computes 100 - 50 = 50
UPDATE accounts SET balance = 70          UPDATE accounts SET balance = 50
  WHERE id = 1;                             WHERE id = 1;
COMMIT;                                    COMMIT;  -- final balance = 50, the 30 withdrawal vanished
```

Read Committed does *not* prevent this; both transactions read 100 and the second commit wins. There are three standard fixes:

- **Atomic update** -- let the database do the arithmetic so there is no read-then-write gap: `UPDATE accounts SET balance = balance - 30 WHERE id = 1;`. In Django, this is `F('balance') - 30`.
- **Pessimistic lock** -- `SELECT ... FOR UPDATE` so the second transaction blocks until the first commits, then reads the updated value.
- **Optimistic concurrency** -- a version column checked in the WHERE clause (covered under Optimistic vs Pessimistic Locking below).

**Write skew** is more insidious. Two transactions read an *overlapping* set of rows, each makes a decision that is valid given what it read, and each writes a *different* row -- so no lost update occurs, yet a global invariant is violated. The textbook example is an on-call rule that requires at least one doctor on shift:

```sql
-- Invariant: at least one doctor must remain on call.
-- Currently Alice and Bob are both on call.

-- Transaction A (Alice going off)            -- Transaction B (Bob going off)
BEGIN;                                          BEGIN;
SELECT count(*) FROM doctors                    SELECT count(*) FROM doctors
  WHERE on_call = true;  -- sees 2, OK            WHERE on_call = true;  -- sees 2, OK
UPDATE doctors SET on_call = false              UPDATE doctors SET on_call = false
  WHERE name = 'Alice';                           WHERE name = 'Bob';
COMMIT;                                          COMMIT;
-- Result: ZERO doctors on call -- invariant violated
```

Each transaction's logic was correct in isolation, and they updated different rows, so locking the row each one writes would not have helped. **Snapshot isolation (PostgreSQL's Repeatable Read) does NOT prevent write skew** -- each transaction reads its own consistent snapshot showing two doctors. Only **Serializable** isolation catches it: PostgreSQL's Serializable Snapshot Isolation tracks the read/write dependencies between the transactions, detects the dangerous cycle, and aborts one with a serialization failure for the application to retry.

```text
ERROR:  could not serialize access due to read/write dependencies among transactions
DETAIL:  Reason code: Canceled on identification as a pivot, during commit attempt.
HINT:  The transaction might succeed if retried.
```

**How to read this output:** This is the error your application must be prepared to catch under `SERIALIZABLE`. The HINT is the key operational instruction -- a serialization failure is *not* a bug, it is the database telling you it prevented an anomaly and you should simply retry the transaction. Any code path running at Serializable must wrap its transaction in a retry loop (with a small bounded number of attempts); forgetting that retry loop is the most common mistake when teams reach for Serializable to fix write skew. The alternative, if you want to stay at a weaker isolation level, is to *materialize the conflict* -- e.g. `SELECT ... FOR UPDATE` the rows you counted, so the two transactions actually contend on the same locks.

### MVCC (Multi-Version Concurrency Control)

PostgreSQL uses MVCC to handle concurrency without read locks. The fundamental idea is that every row has hidden system columns (`xmin` and `xmax`) recording which transactions created and deleted that row version. When a row is updated, PostgreSQL does not overwrite it in place. Instead, it creates a new version of the row and marks the old version as "dead" (by setting its `xmax`).

```
  MVCC: Row Versioning During an UPDATE
  ======================================

  Transaction 100 inserts a row:
  +-------------------------------------------+
  | xmin=100 | xmax=0 | id=1 | name='Alice'  |   <-- live tuple
  +-------------------------------------------+

  Transaction 200 updates the row (UPDATE users SET name='Bob' WHERE id=1):
  +-------------------------------------------+
  | xmin=100 | xmax=200 | id=1 | name='Alice' |   <-- dead tuple (invisible to new txns)
  +-------------------------------------------+
  +-------------------------------------------+
  | xmin=200 | xmax=0   | id=1 | name='Bob'   |   <-- new live tuple
  +-------------------------------------------+

  Transaction 150 (started before 200) still sees:
      name='Alice'   (because xmax=200 is not visible to snapshot 150)

  Transaction 250 (started after 200 committed) sees:
      name='Bob'     (because xmin=200 is committed and visible)
```

This design means writers never block readers and readers never block writers. The downside is that dead tuples accumulate and must be cleaned up by VACUUM. Autovacuum handles this automatically, but heavily-updated tables may need tuned autovacuum settings:

```sql
-- Check dead tuple count
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / GREATEST(n_live_tup, 1) * 100, 2) AS dead_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

The output ranks your most bloated tables:

```text
   relname    | n_live_tup | n_dead_tup | dead_pct
--------------+------------+------------+---------
 sessions     |      82000 |     410500 |   500.61
 orders       |    1500000 |     180000 |    12.00
```

**How to read this output:** `dead_pct` over 100 (like `sessions` at 500%) means dead tuples vastly outnumber live ones -- the table is mostly garbage and every scan wastes I/O reading tombstones autovacuum has not reclaimed yet. This is the signature of a high-churn table (a session store hammered by UPDATEs) whose autovacuum settings are too lax, which is exactly why the next snippet tunes them. A bloated table also bloats its indexes and degrades the planner's row estimates, so chronic high `dead_pct` quietly poisons performance across the board.

```sql
-- Tune autovacuum for a specific high-churn table
ALTER TABLE orders SET (
    autovacuum_vacuum_threshold = 100,
    autovacuum_vacuum_scale_factor = 0.05,   -- vacuum when 5% of rows are dead (default 20%)
    autovacuum_analyze_threshold = 50,
    autovacuum_analyze_scale_factor = 0.02
);
```

**HOT (Heap-Only Tuple) updates** are a PostgreSQL optimization. When a row is updated and (a) no indexed column changes, and (b) the new version fits on the same heap page, PostgreSQL can avoid creating a new index entry. The old index entry simply follows a chain of HOT pointers on the heap page to reach the current version. This dramatically reduces index bloat for frequently-updated non-indexed columns.

### Locking

**Row-level locks** are the most common explicit locks. `SELECT FOR UPDATE` acquires an exclusive lock on selected rows, blocking other transactions from modifying or locking those rows until the lock-holding transaction commits or rolls back. `SELECT FOR SHARE` acquires a shared lock, allowing other readers but blocking writers.

```sql
BEGIN;
  -- Lock the row so no other transaction can modify it until we commit
  SELECT * FROM accounts WHERE id = 1 FOR UPDATE;
  -- ... compute new balance ...
  UPDATE accounts SET balance = 750 WHERE id = 1;
COMMIT;

-- FOR UPDATE NOWAIT: fail immediately instead of waiting if the row is locked
SELECT * FROM accounts WHERE id = 1 FOR UPDATE NOWAIT;

-- FOR UPDATE SKIP LOCKED: skip already-locked rows (great for job queues)
SELECT * FROM jobs WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

**Advisory locks** are application-defined locks that PostgreSQL tracks but does not associate with any table or row. They are useful for coordinating application-level processes:

```sql
-- Session-level advisory lock (held until session ends or explicitly released)
SELECT pg_advisory_lock(12345);
-- ... do exclusive work keyed by 12345 ...
SELECT pg_advisory_unlock(12345);

-- Transaction-level advisory lock (released at end of transaction)
SELECT pg_advisory_xact_lock(12345);
```

```python
# Django: advisory lock pattern
import contextlib
from django.db import connection

@contextlib.contextmanager
def with_advisory_lock(lock_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
        try:
            yield
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])

# Usage:
# with with_advisory_lock(12345):
#     ...  # exclusive work keyed by 12345
```

**Deadlock detection** is automatic in PostgreSQL. When two transactions each wait for a lock held by the other, PostgreSQL detects the cycle (typically within 1 second, controlled by `deadlock_timeout`) and aborts one of the transactions. To prevent deadlocks, always acquire locks in a consistent order (e.g., by ascending ID).

### Optimistic vs Pessimistic Locking

**Pessimistic locking** uses `SELECT FOR UPDATE` to lock rows before modifying them. It guarantees that no one else can change the row while you work on it. This is appropriate when contention is high and conflicts are expected.

**Optimistic locking** uses a version column or timestamp. The application reads the row (noting the version), computes a new value, and then updates only if the version has not changed. If it has, the application detects the conflict and retries. This avoids holding locks during computation and is better for low-contention scenarios.

```sql
-- Optimistic locking with a version column
UPDATE products
SET price = 29.99, version = version + 1
WHERE id = 42 AND version = 7;
-- If 0 rows affected, someone else updated the row -> retry
```

```python
# Django: optimistic locking pattern
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    version = models.IntegerField(default=0)

def update_price(product_id, new_price, max_retries=3):
    for attempt in range(max_retries):
        product = Product.objects.get(id=product_id)
        old_version = product.version

        updated = Product.objects.filter(
            id=product_id,
            version=old_version
        ).update(
            price=new_price,
            version=old_version + 1
        )

        if updated == 1:
            return  # Success
        # else: conflict detected, retry

    raise Exception("Max retries exceeded -- too much contention")
```

> **Key Takeaway:** MVCC allows PostgreSQL to provide high concurrency without read-write blocking. Choose the right isolation level for your use case (Read Committed is fine for most applications). Use pessimistic locking (`SELECT FOR UPDATE`) when conflicts are common and data integrity is critical; use optimistic locking (version columns) when conflicts are rare and you want to avoid holding database locks.

---

## Advanced Features

Storage, queries, indexes, and transactions are the fundamentals every relational engine shares. What follows is the set of capabilities that frequently makes PostgreSQL sufficient where teams might otherwise bolt on a second system — a document store, a search engine, an analytics warehouse. Knowing what the database can already do is often the cheapest architectural decision available.

### Partitioning

Partitioning splits a large table into smaller physical pieces (partitions) while presenting a single logical table to queries. This improves query performance (partition pruning skips irrelevant partitions), maintenance operations (VACUUM, reindex per partition), and data lifecycle management (drop old partitions instead of deleting rows).

PostgreSQL supports three partitioning strategies:

**Range partitioning** divides data by value ranges. This is the most common strategy, especially for time-series data:

```sql
-- Create a range-partitioned table by month
CREATE TABLE events (
    id          bigserial,
    event_type  text NOT NULL,
    payload     jsonb,
    created_at  timestamptz NOT NULL
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE events_2025_01 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE events_2025_02 PARTITION OF events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE events_2025_03 PARTITION OF events
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
-- ... create future partitions as needed

-- Create a default partition for data that does not match any partition
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Indexes are created per-partition
CREATE INDEX idx_events_type ON events (event_type);
-- This creates one index per partition automatically

-- Queries automatically prune irrelevant partitions:
EXPLAIN ANALYZE
SELECT * FROM events
WHERE created_at >= '2025-02-01' AND created_at < '2025-03-01';
-- Only scans events_2025_02

-- Drop old data instantly (no row-by-row DELETE, no dead tuples):
DROP TABLE events_2025_01;
```

**List partitioning** divides data by explicit value lists:

```sql
CREATE TABLE orders (
    id          bigserial,
    region      text NOT NULL,
    total       numeric(10,2),
    created_at  timestamptz NOT NULL
) PARTITION BY LIST (region);

CREATE TABLE orders_americas PARTITION OF orders
    FOR VALUES IN ('us', 'ca', 'br', 'mx');
CREATE TABLE orders_europe PARTITION OF orders
    FOR VALUES IN ('gb', 'de', 'fr', 'es');
CREATE TABLE orders_asia PARTITION OF orders
    FOR VALUES IN ('jp', 'cn', 'kr', 'in');
```

**Hash partitioning** distributes data evenly across partitions using a hash function. This is useful when there is no natural range or list boundary but you want to spread data for parallel processing:

```sql
CREATE TABLE sessions (
    id         uuid PRIMARY KEY,
    user_id    bigint NOT NULL,
    data       jsonb
) PARTITION BY HASH (id);

CREATE TABLE sessions_p0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_p1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_p2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_p3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

### Window Functions

Window functions perform calculations across a set of rows related to the current row, without collapsing them into a single output row (unlike GROUP BY). They are indispensable for analytics, ranking, running totals, and comparing rows with their neighbors.

```sql
-- ROW_NUMBER, RANK, DENSE_RANK: ranking within groups
SELECT
    department,
    employee_name,
    salary,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS row_num,
    RANK()       OVER (PARTITION BY department ORDER BY salary DESC) AS rank,
    DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dense_rank
FROM employees;

-- Result:
-- department | employee_name | salary | row_num | rank | dense_rank
-- -----------+---------------+--------+---------+------+-----------
-- Engineering| Alice         | 150000 |       1 |    1 |         1
-- Engineering| Bob           | 140000 |       2 |    2 |         2
-- Engineering| Carol         | 140000 |       3 |    2 |         2
-- Engineering| Dave          | 130000 |       4 |    4 |         3   <-- RANK skips 3, DENSE_RANK does not
-- Sales      | Eve           | 120000 |       1 |    1 |         1
-- Sales      | Frank         | 110000 |       2 |    2 |         2


-- LAG and LEAD: access previous/next rows
SELECT
    date,
    revenue,
    LAG(revenue, 1)  OVER (ORDER BY date) AS prev_day_revenue,
    LEAD(revenue, 1) OVER (ORDER BY date) AS next_day_revenue,
    revenue - LAG(revenue, 1) OVER (ORDER BY date) AS day_over_day_change
FROM daily_revenue
ORDER BY date;

-- Result:
--    date    | revenue | prev_day_revenue | next_day_revenue | day_over_day_change
-- -----------+---------+------------------+------------------+--------------------
-- 2025-06-01 |    1000 |           (null) |             1200 |             (null)
-- 2025-06-02 |    1200 |             1000 |              900 |                200
-- 2025-06-03 |     900 |             1200 |             1500 |               -300
-- 2025-06-04 |    1500 |              900 |           (null) |                600


-- Running total with SUM OVER
SELECT
    date,
    amount,
    SUM(amount) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
    AVG(amount) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS seven_day_avg
FROM daily_sales
ORDER BY date;


-- Practical: find top 3 products per category by revenue
SELECT category, product_name, total_revenue
FROM (
    SELECT
        p.category,
        p.name AS product_name,
        SUM(oi.quantity * oi.unit_price) AS total_revenue,
        ROW_NUMBER() OVER (
            PARTITION BY p.category
            ORDER BY SUM(oi.quantity * oi.unit_price) DESC
        ) AS rn
    FROM products p
    JOIN order_items oi ON oi.product_id = p.id
    GROUP BY p.category, p.name
) ranked
WHERE rn <= 3;
```

**How to read these examples:** In the LAG/LEAD result, the first row's `prev_day_revenue` is `(null)` because there is no earlier row to look back to, and the last row's `next_day_revenue` is `(null)` for the same reason at the other end -- this boundary behavior is the classic gotcha when computing day-over-day deltas, since any arithmetic against that NULL silently yields NULL. The "top 3 per category" pattern at the bottom is the canonical answer to a very common interview question ("get the top N rows within each group"): you cannot do it with `GROUP BY` plus `LIMIT`, so you number the rows with `ROW_NUMBER() OVER (PARTITION BY ...)` in a subquery and filter `rn <= 3` in the outer query.

> **Common pitfall:** A window function cannot appear in a `WHERE` clause of the same query level (e.g. `WHERE ROW_NUMBER() OVER (...) <= 3` is a syntax error), because `WHERE` is evaluated before window functions are computed. That is precisely why the top-N pattern wraps the ranking in a subquery and filters in the outer `SELECT`.

### CTEs (Common Table Expressions)

CTEs, written with the `WITH` clause, allow you to define named temporary result sets within a query. They make complex queries readable and maintainable by breaking them into logical steps. Since PostgreSQL 12, non-recursive CTEs can be "inlined" by the optimizer (treated as subqueries), so there is usually no performance penalty.

```sql
-- Readable multi-step query using CTEs
WITH monthly_revenue AS (
    SELECT
        date_trunc('month', created_at) AS month,
        SUM(total_amount) AS revenue
    FROM orders
    WHERE created_at >= '2024-01-01'
    GROUP BY date_trunc('month', created_at)
),
revenue_with_growth AS (
    SELECT
        month,
        revenue,
        LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
        ROUND(
            (revenue - LAG(revenue) OVER (ORDER BY month))
            / LAG(revenue) OVER (ORDER BY month) * 100, 2
        ) AS growth_pct
    FROM monthly_revenue
)
SELECT * FROM revenue_with_growth ORDER BY month;
```

**Recursive CTEs** are powerful for querying hierarchical data such as organizational charts, category trees, and graph traversals:

```sql
-- Recursive CTE: find all reports (direct and indirect) of a manager
WITH RECURSIVE org_tree AS (
    -- Base case: the manager themselves
    SELECT id, name, manager_id, 0 AS depth
    FROM employees
    WHERE id = 1  -- CEO

    UNION ALL

    -- Recursive case: find employees who report to someone in the tree
    SELECT e.id, e.name, e.manager_id, ot.depth + 1
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT id, name, manager_id, depth
FROM org_tree
ORDER BY depth, name;

-- Recursive CTE: generate a series of dates (useful for filling gaps)
WITH RECURSIVE date_series AS (
    SELECT DATE '2025-01-01' AS dt
    UNION ALL
    SELECT dt + INTERVAL '1 day'
    FROM date_series
    WHERE dt < DATE '2025-01-31'
)
SELECT dt FROM date_series;
```

The org-tree query returns each employee with their depth in the hierarchy, and the date-series query generates one row per day:

```text
-- org_tree:
 id |  name   | manager_id | depth
----+---------+------------+------
  1 | Asha    |     (null) |     0
  2 | Bilal   |          1 |     1
  5 | Chen    |          1 |     1
  9 | Dmitri  |          2 |     2
 14 | Elena   |          5 |     2

-- date_series:
     dt
------------
 2025-01-01
 2025-01-02
 ...
 2025-01-31
(31 rows)
```

**How to read this output:** The `depth` column is computed by the recursion itself -- the base case seeds `depth = 0` (the CEO), and each recursive step adds 1, so `depth` literally counts how many management levels separate a person from the root. The `UNION ALL` (not `UNION`) is essential: it skips the duplicate-elimination pass, which is both faster and required for the recursion to terminate naturally. The date-series trick is the standard way to "fill gaps" -- LEFT JOIN your sparse data onto this generated calendar so days with zero activity still appear as rows instead of vanishing.

> **Common pitfall:** A recursive CTE with no terminating condition (here, the `WHERE dt < ...` guard) loops forever. PostgreSQL will run until it exhausts memory or `temp_file_limit`, so always make sure the recursive arm shrinks toward a stopping point.

```python
# Django: raw SQL for recursive CTE (Django ORM does not natively support recursive CTEs)
from django.db import connection

def get_org_tree(manager_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH RECURSIVE org_tree AS (
                SELECT id, name, manager_id, 0 AS depth
                FROM employees WHERE id = %s
                UNION ALL
                SELECT e.id, e.name, e.manager_id, ot.depth + 1
                FROM employees e
                JOIN org_tree ot ON e.manager_id = ot.id
            )
            SELECT id, name, manager_id, depth
            FROM org_tree
            ORDER BY depth, name
        """, [manager_id])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### JSONB

JSONB (Binary JSON) stores JSON data in a decomposed binary format, allowing efficient querying and indexing. It is the preferred JSON type in PostgreSQL (over `json`, which stores raw text).

```sql
-- Create a table with a JSONB column
CREATE TABLE products (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    attributes  jsonb NOT NULL DEFAULT '{}'
);

-- Insert data
INSERT INTO products (name, attributes) VALUES
    ('Laptop', '{"brand": "Dell", "specs": {"ram": 16, "storage": 512}, "tags": ["electronics", "portable"]}'),
    ('Phone',  '{"brand": "Apple", "specs": {"ram": 8, "storage": 256}, "tags": ["electronics", "mobile"]}'),
    ('Desk',   '{"brand": "IKEA", "material": "wood", "tags": ["furniture"]}');

-- JSONB operators:
-- ->   get JSON object field by key (returns jsonb)
-- ->>  get JSON object field by key (returns text)
-- #>   get JSON value at path (returns jsonb)
-- #>>  get JSON value at path (returns text)
-- @>   contains (left contains right)
-- <@   is contained by
-- ?    key exists
-- ?|   any key exists
-- ?&   all keys exist

-- Query examples:
SELECT name, attributes->>'brand' AS brand
FROM products
WHERE attributes->>'brand' = 'Dell';

-- Nested access:
SELECT name, attributes#>>'{specs,ram}' AS ram_gb
FROM products
WHERE (attributes#>>'{specs,ram}')::int >= 16;

-- Containment query (uses GIN index):
SELECT name FROM products
WHERE attributes @> '{"brand": "Apple"}';

-- Key existence:
SELECT name FROM products
WHERE attributes ? 'material';

-- Array containment within JSONB:
SELECT name FROM products
WHERE attributes->'tags' ? 'mobile';

-- Update JSONB fields:
UPDATE products
SET attributes = jsonb_set(attributes, '{specs,ram}', '32')
WHERE name = 'Laptop';

-- Remove a key:
UPDATE products
SET attributes = attributes - 'material'
WHERE name = 'Desk';

-- JSONPath (PostgreSQL 12+):
SELECT name, jsonb_path_query_first(attributes, '$.specs.ram') AS ram
FROM products
WHERE jsonb_path_exists(attributes, '$.specs ? (@.ram > 8)');

-- GIN index for efficient JSONB queries:
CREATE INDEX idx_products_attrs ON products USING gin (attributes);

-- For queries on specific keys, use jsonb_path_ops (smaller, faster for @> queries):
CREATE INDEX idx_products_attrs_pathops ON products USING gin (attributes jsonb_path_ops);
```

```python
# Django: JSONB queries using JSONField
from django.db.models import Q
from django.contrib.postgres.fields import JSONField  # or models.JSONField in Django 3.1+

class Product(models.Model):
    name = models.CharField(max_length=255)
    attributes = models.JSONField(default=dict)

# Query by nested key
laptops = Product.objects.filter(attributes__brand='Dell')

# Query nested paths
high_ram = Product.objects.filter(attributes__specs__ram__gte=16)

# Check key existence
has_material = Product.objects.filter(attributes__has_key='material')

# Containment
apple_products = Product.objects.filter(attributes__contains={'brand': 'Apple'})
```

### Full-Text Search

PostgreSQL provides built-in full-text search with support for stemming, ranking, and language-specific processing. It transforms documents into `tsvector` (a sorted list of lexemes) and queries into `tsquery` (a boolean expression of lexemes).

```sql
-- Basic full-text search
SELECT title, ts_rank(
    to_tsvector('english', title || ' ' || body),
    plainto_tsquery('english', 'database optimization')
) AS rank
FROM articles
WHERE to_tsvector('english', title || ' ' || body) @@ plainto_tsquery('english', 'database optimization')
ORDER BY rank DESC;

-- Stored tsvector column for better performance
ALTER TABLE articles ADD COLUMN search_vector tsvector;

UPDATE articles
SET search_vector = to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''));

CREATE INDEX idx_articles_search ON articles USING gin (search_vector);

-- Trigger to keep search_vector updated
CREATE OR REPLACE FUNCTION articles_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', coalesce(NEW.title, '') || ' ' || coalesce(NEW.body, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_articles_search
BEFORE INSERT OR UPDATE ON articles
FOR EACH ROW EXECUTE FUNCTION articles_search_trigger();

-- Phrase search, negation, and boolean operators
SELECT * FROM articles
WHERE search_vector @@ to_tsquery('english', 'postgres & !mysql');

SELECT * FROM articles
WHERE search_vector @@ phraseto_tsquery('english', 'query optimization');
```

### Logical Replication and Streaming Replication

PostgreSQL supports two forms of replication for different use cases:

**Streaming replication** copies the entire database cluster at the WAL (Write-Ahead Log) level. The replica is a byte-for-byte copy of the primary. It is used for high availability (HA) and read scaling.

**Logical replication** works at the logical level -- it replicates changes (INSERT, UPDATE, DELETE) for specific tables using a publisher-subscriber model. It is used for selective replication, cross-version upgrades, and data distribution.

```
  Replication Topology
  ====================

  Streaming Replication (HA):

  +-------------+       WAL stream       +-------------+
  |   Primary   | ---------------------> |   Replica   |  (hot standby,
  | (read/write)|                        | (read-only) |   can serve reads)
  +-------------+                        +-------------+
        |                WAL stream       +-------------+
        +-------------------------------> |   Replica   |
                                          | (read-only) |
                                          +-------------+

  Logical Replication (selective):

  +-------------+    Pub: orders,users    +------------------+
  |  Publisher   | ---------------------> |   Subscriber A   |  (analytics DB,
  | (production) |                        | (different schema)|   may be different
  +-------------+                         +------------------+   PG version)
        |              Pub: orders
        +-------------------------------> +------------------+
                                          |   Subscriber B   |  (microservice DB)
                                          +------------------+
```

```sql
-- Setting up logical replication:

-- On the publisher (source database):
ALTER SYSTEM SET wal_level = 'logical';
-- Restart PostgreSQL after changing wal_level

CREATE PUBLICATION my_pub FOR TABLE orders, users;

-- On the subscriber (target database):
CREATE SUBSCRIPTION my_sub
    CONNECTION 'host=publisher-host dbname=mydb user=replication_user password=secret'
    PUBLICATION my_pub;
```

### Connection Pooling

Each PostgreSQL connection consumes approximately 5-10 MB of RAM (due to per-process memory allocations for sort buffers, hash tables, and other state). The default `max_connections` is 100. For applications with hundreds or thousands of concurrent users, opening a direct connection for each is unsustainable.

PgBouncer is an external connection pooler that sits between your application and PostgreSQL. It maintains a small pool of actual PostgreSQL connections and multiplexes many client connections onto them.

```
  Connection Pooling with PgBouncer
  ==================================

  Without PgBouncer:                 With PgBouncer:

  App Server 1 --[50 conns]--+      App Server 1 --[50 conns]--+
  App Server 2 --[50 conns]--+--> PostgreSQL   App Server 2 --[50 conns]--+--> PgBouncer --[20 conns]--> PostgreSQL
  App Server 3 --[50 conns]--+   (150 conns!)  App Server 3 --[50 conns]--+   (150->20)               (20 conns)
```

PgBouncer supports three pooling modes:

- **Session pooling**: a server connection is assigned for the entire client session. Safest but least efficient.
- **Transaction pooling**: a server connection is assigned only for the duration of a transaction. Most common mode. Prepared statements and session-level features (SET, LISTEN/NOTIFY) do not work across transactions.
- **Statement pooling**: a server connection is assigned for each individual statement. Only works for simple, autocommit queries.

> **Key Takeaway:** PostgreSQL's advanced features -- partitioning, window functions, CTEs, JSONB, full-text search, and logical replication -- can eliminate the need for many external tools. Master these features before reaching for additional infrastructure. Use connection pooling (PgBouncer) in production to manage connection overhead.

## Summary

A relational database's observable behavior — its speed, its durability, its failure modes — is determined by mechanics you can learn and inspect. At the storage layer, everything moves in 8 KB pages through the buffer pool; durability rests on the write-ahead rule that the WAL record reaches disk before the dirty page does; and MVCC's choice to keep old row versions in the heap is why PostgreSQL administration revolves around VACUUM and bloat, while InnoDB's undo log and clustered index produce a different set of trade-offs. B-trees balance reads and writes; LSM engines trade read cost for write throughput.

On top of that foundation, query work is empirical: `EXPLAIN ANALYZE` shows what the planner actually did, and the largest wins come from the right index and from eliminating N+1 patterns, not from clever SQL. Indexing is a matter of matching structure to access pattern — B-tree for the common case, GIN for composite values like JSONB and full-text, BRIN for huge naturally-ordered tables, partial and expression indexes to stay small — always remembering that every index taxes writes.

Correctness under concurrency has its own decision rules. Read Committed serves most applications; Repeatable Read and Serializable buy stronger guarantees at the price of retry handling. Lock pessimistically with `SELECT FOR UPDATE` when conflicts are common and integrity is critical; version optimistically when conflicts are rare. And before adding infrastructure, check whether partitioning, window functions, JSONB, full-text search, logical replication, or PgBouncer already solve the problem inside PostgreSQL.

Sometimes, though, the relational model genuinely is the wrong fit — and knowing when is the subject of 4.2 NoSQL & Specialized Databases.

*Last reviewed: 2026-06-08*

**Next:** [4.2 NoSQL & Specialized Databases](nosql-and-specialized.md)
