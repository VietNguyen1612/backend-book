[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 4.1 Relational Databases (PostgreSQL Focus)

### Query Optimization

#### EXPLAIN ANALYZE: Reading Execution Plans

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

#### Seq Scan vs Index Scan

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

#### Query Planner and Statistics

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

Autovacuum runs `ANALYZE` automatically, but after bulk loads or major data changes, you should run it manually. You can also increase the statistics target for columns with unusual distributions:

```sql
-- Increase statistics granularity for a specific column (default is 100)
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;
```

#### Common Anti-Patterns

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

### Indexing Strategies

#### B-tree (Default Index)

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

#### Hash Index

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

#### GIN (Generalized Inverted Index)

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

#### GiST (Generalized Search Tree)

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

#### BRIN (Block Range Index)

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

BRIN indexes shine for append-only tables (logs, events, metrics) where the physical order matches the column order. If rows are inserted out of order or frequently updated, BRIN becomes ineffective because each block range will have wide min/max boundaries, causing many false positives.

#### Partial Indexes

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

#### Expression Indexes

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
            # Expression index
            Index(Lower('email'), name='idx_user_email_lower'),
            # Partial index (Django 5.0+)
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

### Transactions & Concurrency

#### ACID Properties

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

#### Isolation Levels

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

#### MVCC (Multi-Version Concurrency Control)

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

-- Tune autovacuum for a specific high-churn table
ALTER TABLE orders SET (
    autovacuum_vacuum_threshold = 100,
    autovacuum_vacuum_scale_factor = 0.05,   -- vacuum when 5% of rows are dead (default 20%)
    autovacuum_analyze_threshold = 50,
    autovacuum_analyze_scale_factor = 0.02
);
```

**HOT (Heap-Only Tuple) updates** are a PostgreSQL optimization. When a row is updated and (a) no indexed column changes, and (b) the new version fits on the same heap page, PostgreSQL can avoid creating a new index entry. The old index entry simply follows a chain of HOT pointers on the heap page to reach the current version. This dramatically reduces index bloat for frequently-updated non-indexed columns.

#### Locking

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
from django.db import connection

def with_advisory_lock(lock_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
        try:
            yield
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
```

**Deadlock detection** is automatic in PostgreSQL. When two transactions each wait for a lock held by the other, PostgreSQL detects the cycle (typically within 1 second, controlled by `deadlock_timeout`) and aborts one of the transactions. To prevent deadlocks, always acquire locks in a consistent order (e.g., by ascending ID).

#### Optimistic vs Pessimistic Locking

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

### Advanced Features

#### Partitioning

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

#### Window Functions

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

#### CTEs (Common Table Expressions)

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

#### JSONB

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

#### Full-Text Search

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

#### Logical Replication and Streaming Replication

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

#### Connection Pooling

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
