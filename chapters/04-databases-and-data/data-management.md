[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 4.3 Data Management

> [!NOTE]
> **Beginner's Mental Model — Database Migrations:**
> Think of database migrations like version control (like Git) for your database structure. Just as Git commits track changes to your source code over time, migrations are a series of step-by-step instructions (scripts) that track changes to your database schema (adding tables, renaming columns, setting constraints). They ensure that every environment—your local machine, staging, and production—runs on the exact same database structure.

### Migration Strategies

Database migrations are one of the highest-risk operations in production systems. A bad migration can lock tables, corrupt data, or cause downtime. Understanding which changes are safe and which require careful planning is essential.

#### Additive Changes

Additive changes are always safe because they do not modify existing structures or data. They include adding new tables, adding nullable columns, and adding indexes concurrently.

```sql
-- Safe: adding a new table
CREATE TABLE notifications (
    id          bigserial PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users(id),
    message     text NOT NULL,
    read_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Safe: adding a nullable column (no table rewrite in PostgreSQL)
ALTER TABLE users ADD COLUMN phone_number text;

-- Safe: adding a column with a non-volatile default (PostgreSQL 11+)
-- This does NOT rewrite the table; PG stores the default in the catalog
ALTER TABLE users ADD COLUMN is_active boolean NOT NULL DEFAULT true;

-- Safe: creating an index without locking writes
-- CONCURRENTLY avoids holding an exclusive lock on the table
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);
```

In Django, the equivalent migration:

```python
# migrations/0042_add_phone_number.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('myapp', '0041_previous')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
    ]
```

To create indexes concurrently in Django, use `AddIndex` with `SeparateDatabaseAndState` or a `RunSQL` operation:

```python
from django.db import migrations

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    dependencies = [('myapp', '0042_add_phone_number')]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_orders_user_id;",
        ),
    ]
```

> [!NOTE]
> **Beginner's Mental Model — Expand-Contract Pattern:**
> Imagine you want to replace a narrow old bridge on a busy highway with a wide new bridge. You can't just blow up the old bridge (downtime); instead, you build the new bridge alongside the old one first (**Expand**). You route a small amount of traffic onto the new bridge, keep both running in parallel, and eventually shift all traffic over (**Migrate**). Finally, once the new bridge is proven stable, you tear down the old one (**Contract**). This allows you to make major, breaking database changes with zero downtime.

#### Breaking Changes and the Expand-Contract Pattern

Breaking changes -- renaming columns, changing column types, adding NOT NULL constraints without defaults, or dropping columns -- require careful multi-phase deployment to avoid downtime. The expand-contract pattern (also known as parallel change) handles this safely.

**Example: Renaming a column from `name` to `full_name`**

```
  Expand-Contract Pattern Timeline
  =================================

  Phase 1: Expand                Phase 2: Migrate           Phase 3: Contract
  (add new, write both)          (switch reads, backfill)   (remove old)

  +--------+  +------------+    +--------+  +------------+  +--------+  +------------+
  | Code   |  | Database   |    | Code   |  | Database   |  | Code   |  | Database   |
  +--------+  +------------+    +--------+  +------------+  +--------+  +------------+
  | writes |  | name       |    | writes |  | name       |  | reads  |  |            |
  | to     |->| full_name  |    | to     |->| full_name  |  | from   |->| full_name  |
  | BOTH   |  | (trigger   |    | full_  |  | (backfill  |  | full_  |  |            |
  | cols   |  |  syncs)    |    | name   |  |  done)     |  | name   |  | (name col  |
  |        |  |            |    | only   |  |            |  | only   |  |  dropped)  |
  +--------+  +------------+    +--------+  +------------+  +--------+  +------------+

  Deploy 1                       Deploy 2                    Deploy 3
```

**Phase 1: Expand** -- Add the new column and a trigger to keep them in sync.

```sql
-- Step 1: Add the new column
ALTER TABLE users ADD COLUMN full_name text;

-- Step 2: Create a trigger to keep both columns in sync
CREATE OR REPLACE FUNCTION sync_user_name() RETURNS trigger AS $$
BEGIN
    IF NEW.full_name IS NULL AND NEW.name IS NOT NULL THEN
        NEW.full_name := NEW.name;
    END IF;
    IF NEW.name IS NULL AND NEW.full_name IS NOT NULL THEN
        NEW.name := NEW.full_name;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_user_name
BEFORE INSERT OR UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION sync_user_name();

-- Step 3: Backfill existing data (in batches to avoid long locks)
UPDATE users SET full_name = name WHERE full_name IS NULL AND id BETWEEN 1 AND 10000;
UPDATE users SET full_name = name WHERE full_name IS NULL AND id BETWEEN 10001 AND 20000;
-- ... continue until all rows are updated

-- Deploy application code that writes to BOTH columns
```

**Phase 2: Migrate** -- Once backfill is complete and all application code writes to both columns, switch reads to the new column.

```python
# Application code reads from full_name instead of name
# Both columns are still written to for rollback safety
```

**Phase 3: Contract** -- After the new column is proven in production, remove the old column, trigger, and any references.

```sql
-- Remove the sync trigger
DROP TRIGGER trg_sync_user_name ON users;
DROP FUNCTION sync_user_name();

-- Remove the old column
ALTER TABLE users DROP COLUMN name;
```

**Example: Adding NOT NULL to an existing column safely**

```sql
-- Wrong (locks the table and scans all rows in old PostgreSQL):
ALTER TABLE users ALTER COLUMN email SET NOT NULL;

-- Safe approach:
-- Step 1: Add a CHECK constraint as NOT VALID (no full table scan)
ALTER TABLE users ADD CONSTRAINT users_email_not_null
    CHECK (email IS NOT NULL) NOT VALID;

-- Step 2: Validate the constraint (scans table but does not block writes)
ALTER TABLE users VALIDATE CONSTRAINT users_email_not_null;

-- Step 3 (optional): Convert to a proper NOT NULL constraint
-- In PostgreSQL 12+, if a valid CHECK (col IS NOT NULL) exists,
-- ALTER COLUMN SET NOT NULL is instant.
ALTER TABLE users ALTER COLUMN email SET NOT NULL;
ALTER TABLE users DROP CONSTRAINT users_email_not_null;
```

#### Schema Versioning

Always version-control your migrations and never modify a migration that has already been applied to a shared database. Each migration framework tracks which migrations have been applied:

- **Django Migrations**: Stored in `django_migrations` table. Generate with `python manage.py makemigrations`, apply with `python manage.py migrate`.
- **Alembic** (SQLAlchemy): Uses a `alembic_version` table. Generate with `alembic revision --autogenerate`, apply with `alembic upgrade head`.
- **Flyway** (Java): Uses a `flyway_schema_history` table. Migrations are numbered SQL files.
- **Liquibase**: Uses a `databasechangelog` table. Migrations in XML, YAML, JSON, or SQL.

> **Key Takeaway:** Treat every migration as a production deployment risk. Additive changes (new columns with defaults, new tables, concurrent indexes) are safe. For breaking changes, use the expand-contract pattern: add the new structure, migrate data, switch traffic, then remove the old structure. Never rename or drop a column in a single step. Always use `CONCURRENTLY` for index creation on live tables.

---

### Data Patterns

#### Soft Delete

Soft delete replaces physical deletion with a logical flag -- typically a `deleted_at` timestamp column. Instead of `DELETE FROM users WHERE id = 42`, you execute `UPDATE users SET deleted_at = NOW() WHERE id = 42`. The row remains in the database and can be recovered.

```sql
-- Table setup
ALTER TABLE users ADD COLUMN deleted_at timestamptz;

-- Soft delete
UPDATE users SET deleted_at = NOW() WHERE id = 42;

-- All queries must filter out deleted records:
SELECT * FROM users WHERE deleted_at IS NULL;

-- Unique constraints need a partial index to work correctly:
-- (Otherwise, a deleted user's email blocks new registrations)
CREATE UNIQUE INDEX idx_users_email_unique
ON users (email) WHERE deleted_at IS NULL;

-- Create a view for convenience:
CREATE VIEW active_users AS
SELECT * FROM users WHERE deleted_at IS NULL;
```

```python
# Django: soft delete with a custom manager
from django.db import models
from django.utils import timezone

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()       # Default: only active records
    all_objects = models.Manager()      # Includes soft-deleted records

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])

    class Meta:
        abstract = True

class User(SoftDeleteModel):
    email = models.EmailField()
    name = models.CharField(max_length=255)

# Usage:
User.objects.all()       # Only active users
User.all_objects.all()   # All users including deleted
```

Soft delete considerations: remember that every query must include the filter (use a default manager or view), foreign key cascades do not trigger soft deletes (handle in application code), and you should establish a data retention policy to periodically hard-delete old soft-deleted records.

#### Audit Trail

An audit trail records who changed what, and when. This is essential for compliance (GDPR, SOX, HIPAA), debugging, and accountability. The two main approaches are trigger-based (database level) and application-level.

```sql
-- Trigger-based audit trail
CREATE TABLE audit_log (
    id              bigserial PRIMARY KEY,
    table_name      text NOT NULL,
    record_id       bigint NOT NULL,
    action          text NOT NULL,  -- INSERT, UPDATE, DELETE
    old_values      jsonb,
    new_values      jsonb,
    changed_by      text,
    changed_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_table_record ON audit_log (table_name, record_id);
CREATE INDEX idx_audit_log_changed_at ON audit_log (changed_at);

CREATE OR REPLACE FUNCTION audit_trigger_func() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, action, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', to_jsonb(NEW),
                current_setting('app.current_user', true));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW),
                current_setting('app.current_user', true));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values, changed_by)
        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', to_jsonb(OLD),
                current_setting('app.current_user', true));
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Attach to tables
CREATE TRIGGER audit_users
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

-- Set the current user in the application before queries:
SET LOCAL app.current_user = 'alice@example.com';
```

```python
# Django: using django-simple-history for automatic audit trails
# pip install django-simple-history

from simple_history.models import HistoricalRecords

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    history = HistoricalRecords()

# Query history:
product = Product.objects.get(id=1)
for record in product.history.all():
    print(f"{record.history_date}: {record.history_type} by {record.history_user}")
    # history_type: '+' (create), '~' (update), '-' (delete)

# Get the version as of a specific date:
from datetime import datetime
old_product = product.history.as_of(datetime(2025, 1, 1))
print(old_product.price)  # Price as of Jan 1, 2025
```

For a product that was created and then re-priced twice, the history loop prints something like (newest first, since `history.all()` orders by `-history_date`):

```text
2025-05-20 14:03:11+00:00: ~ by carol@example.com
2025-03-02 09:47:55+00:00: ~ by bob@example.com
2025-01-01 08:00:00+00:00: + by alice@example.com
19.99
```

**How to read this output:** each historical record is a full snapshot of the row at that moment, not a diff -- `simple-history` writes a new row to `historicalproduct` on every save, tagged with `history_type` (`+` create, `~` update, `-` delete) and `history_user`. The two `~` rows are the price changes; the `+` row is the original create. The final `19.99` is what `as_of(Jan 1)` returned: it walked back through history to the version that was live on that date, which is the production-grade way to answer "what price did this customer actually see at checkout?" during a billing dispute. The cost to be aware of: this doubles your write volume and grows the history table unboundedly, so a retention/archival policy is required for hot tables.

#### Multi-Tenancy

Multi-tenancy is the pattern of serving multiple customers (tenants) from a single application deployment. There are three common strategies, each with different trade-offs:

**Row-level isolation** uses a `tenant_id` column on every table. All tenants share the same tables and schema. PostgreSQL's Row-Level Security (RLS) can enforce isolation at the database level:

```sql
-- Add tenant_id to every table
ALTER TABLE orders ADD COLUMN tenant_id bigint NOT NULL;
CREATE INDEX idx_orders_tenant ON orders (tenant_id);

-- Enable Row-Level Security
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Create a policy that restricts access based on a session variable
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::bigint);

-- In application code, set the tenant before queries:
SET LOCAL app.current_tenant = '42';
SELECT * FROM orders;  -- Only sees tenant 42's orders
```

**Schema-level isolation** creates a separate PostgreSQL schema for each tenant. Tables have the same structure but live in different schemas:

```sql
CREATE SCHEMA tenant_42;
CREATE TABLE tenant_42.orders (LIKE public.orders_template INCLUDING ALL);

-- Switch schema in application code:
SET search_path TO tenant_42, public;
SELECT * FROM orders;  -- Queries tenant_42.orders
```

**Database-level isolation** gives each tenant their own database. This provides the strongest isolation but is the most operationally complex (separate backups, migrations, connection pools).

The trade-off spectrum: Row-level is cheapest and simplest to operate but has the weakest isolation. Database-level provides the strongest isolation but is expensive and complex. Schema-level is a middle ground. Most SaaS applications start with row-level and only move to schema or database-level for enterprise customers with strict compliance requirements.

#### Event Sourcing

Event sourcing stores every change to application state as an immutable event, rather than overwriting the current state. The current state is derived by replaying all events from the beginning (or from a snapshot).

```sql
-- Event store table
CREATE TABLE events (
    id              bigserial PRIMARY KEY,
    aggregate_type  text NOT NULL,          -- e.g., 'Order'
    aggregate_id    uuid NOT NULL,          -- e.g., the order ID
    event_type      text NOT NULL,          -- e.g., 'OrderCreated', 'ItemAdded'
    event_data      jsonb NOT NULL,
    metadata        jsonb DEFAULT '{}',
    version         integer NOT NULL,       -- for optimistic concurrency
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_events_aggregate_version
ON events (aggregate_type, aggregate_id, version);

-- Insert events
INSERT INTO events (aggregate_type, aggregate_id, event_type, event_data, version) VALUES
('Order', 'a1b2c3', 'OrderCreated',  '{"customer_id": 42}', 1),
('Order', 'a1b2c3', 'ItemAdded',     '{"product": "Laptop", "price": 999.99}', 2),
('Order', 'a1b2c3', 'ItemAdded',     '{"product": "Mouse", "price": 29.99}', 3),
('Order', 'a1b2c3', 'OrderShipped',  '{"tracking": "1Z999AA10123456784"}', 4);

-- Rebuild current state by replaying events
SELECT event_type, event_data, created_at
FROM events
WHERE aggregate_type = 'Order' AND aggregate_id = 'a1b2c3'
ORDER BY version;
```

The replay query returns the events in the exact order they happened:

```text
 event_type  |                  event_data                  |          created_at
-------------+----------------------------------------------+-------------------------------
 OrderCreated| {"customer_id": 42}                          | 2025-06-04 10:15:02.331+00
 ItemAdded   | {"price": 999.99, "product": "Laptop"}       | 2025-06-04 10:15:04.882+00
 ItemAdded   | {"price": 29.99, "product": "Mouse"}         | 2025-06-04 10:16:11.204+00
 OrderShipped| {"tracking": "1Z999AA10123456784"}           | 2025-06-04 10:42:55.017+00
(4 rows)
```

**How to read this output:** the rows ARE the order's history -- there is no `orders` table holding a current row, only this append-only log. To get the order's current state you fold these events left-to-right: create the order, add a laptop, add a mouse, mark it shipped. Note `ORDER BY version` (not `created_at`) is what guarantees correctness -- wall-clock timestamps can tie or skew under concurrency, but the monotonic `version` (backed by the unique index on `(aggregate_type, aggregate_id, version)`) gives a deterministic replay order. This is exactly why event sourcing shines in audit-heavy domains (finance, healthcare): you can answer "what did this order look like at 10:20?" by replaying only events up to that point, something a mutable `orders` row throws away on every UPDATE.

> **Common pitfall:** rebuilding state by replaying the full log on every read does not scale -- an aggregate with 50,000 events becomes unusably slow. That is the entire reason for the snapshot table below: periodically persist the folded state at a known version, then replay only the events newer than the snapshot. include a complete audit trail, the ability to reconstruct state at any point in time, and decoupled systems (other services can subscribe to events). The costs are significant complexity (every read requires replaying or maintaining a projection), eventual consistency between the event store and read models, and increased storage usage. Use snapshots to avoid replaying thousands of events:

```sql
-- Snapshot table for performance
CREATE TABLE snapshots (
    aggregate_type  text NOT NULL,
    aggregate_id    uuid NOT NULL,
    version         integer NOT NULL,
    state           jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aggregate_type, aggregate_id)
);
```

> **Key Takeaway:** Choose data patterns based on your actual requirements. Soft delete is simple but pollutes queries -- use a default manager or view. Audit trails are often a compliance requirement -- trigger-based approaches are transparent to application code. Multi-tenancy strategy should match your isolation and operational requirements. Event sourcing is powerful but complex -- use it when you genuinely need a complete history of state changes, not as a default architecture.

---

### Storing Money & Time Correctly

Two data types are wrong in a surprising number of production systems, and both failures are expensive: money stored as floating point, and timestamps stored without time-zone awareness. Getting these right is a hallmark of an experienced engineer and a frequent interview probe.

#### Money

**Never store money as `float` or `double`.** Binary floating point cannot represent most decimal fractions exactly, so `0.1 + 0.2` is not `0.3`, and these tiny errors compound across millions of rows until your ledger no longer balances. There are two correct approaches:

- **`NUMERIC`/`DECIMAL`** -- an exact, arbitrary-precision decimal type. Store the amount with an explicit precision and scale, e.g. `NUMERIC(19, 4)`, and always store the **currency** alongside it (an amount without a currency is meaningless).
- **Integer minor units** -- store the value as an integer count of the smallest unit (cents, satoshis), e.g. `2599` for $25.99, plus a currency column. This is common in payment systems (Stripe's API uses it) because integer arithmetic has no rounding ambiguity at all.

```sql
CREATE TABLE invoices (
    id            bigserial PRIMARY KEY,
    -- exact decimal: 4 fractional digits leaves room for sub-cent tax math
    amount        numeric(19, 4) NOT NULL,
    currency      char(3) NOT NULL,                 -- ISO 4217: 'USD', 'EUR'
    CONSTRAINT amount_non_negative CHECK (amount >= 0)
);

-- Aggregate with exact types; the sum stays exact, no float drift
SELECT currency, SUM(amount) AS total
FROM invoices
GROUP BY currency;
```

```text
 currency |   total
----------+------------
 USD      | 184230.5500
 EUR      |  92011.0000
```

**How to read this output:** The totals carry their full declared scale (`.5500`, `.0000`) because `NUMERIC` preserves precision through aggregation -- summing a million rows yields a value that still balances to the cent, which a `double` column would not guarantee. Notice the `GROUP BY currency`: you must never sum amounts across currencies, and storing the currency per row is what makes that mistake structurally impossible. The remaining decision the schema cannot make for you is the **rounding policy** -- when you must collapse those 4 fractional digits to 2 for a customer-facing charge, decide and document whether you use banker's rounding (round-half-to-even) or round-half-up, because tax and billing regulations often mandate a specific rule and inconsistency between services causes off-by-a-cent reconciliation failures.

#### Time

Store timestamps as **`timestamptz`** (timestamp with time zone), not naive `timestamp`. Despite the name, `timestamptz` does not store a time zone -- it stores an absolute instant in UTC and converts to the session's time zone on the way out. Naive `timestamp` stores wall-clock digits with no anchor, so the same value means different instants depending on who reads it, which silently breaks ordering, intervals, and DST transitions.

The rules that keep time correct:

- **Persist everything in UTC** (`timestamptz` does this for you). Convert to local time only at the display edge.
- If you need "9am local, *forever*" semantics (a recurring alarm, a store's opening hour that must survive DST and even legislative time-zone changes), store the user's **intended time zone separately** as an IANA name (`'America/New_York'`), not a fixed offset. An offset like `-05:00` is wrong half the year.
- Be explicit about the server/session `timezone` setting so conversions are predictable across environments.

```sql
CREATE TABLE events (
    id          bigserial PRIMARY KEY,
    starts_at   timestamptz NOT NULL,        -- absolute instant, stored UTC
    -- store the zone separately when "local time" semantics must be preserved
    local_tz    text NOT NULL DEFAULT 'UTC'  -- IANA name, e.g. 'Europe/Berlin'
);

-- Render an event in its own local zone regardless of server settings
SELECT id,
       starts_at,
       starts_at AT TIME ZONE local_tz AS local_wall_clock
FROM events;
```

```text
 id |        starts_at         |   local_wall_clock
----+--------------------------+---------------------
  1 | 2025-06-04 18:00:00+00   | 2025-06-04 20:00:00
  2 | 2025-12-04 18:00:00+00   | 2025-12-04 19:00:00
```

**How to read this output:** Both rows are stored as the same UTC hour (`18:00:00+00`), yet `AT TIME ZONE 'Europe/Berlin'` renders them two different wall-clock times -- `20:00` in June (CEST, UTC+2) and `19:00` in December (CET, UTC+1). That is DST handled correctly *for free*, precisely because the zone is an IANA name rather than a frozen offset. Had you stored a naive `timestamp` plus a `-01:00`-style offset, the winter event would have displayed an hour wrong. This single example is why "always store UTC, convert at the edges, keep the IANA zone separately" is the standard answer to the time-handling interview question.

#### Constrained State Types

A status or state column should never be free text. A typo (`'shiped'`) or an invented value silently corrupts your data and breaks every query that filters on it. Constrain the allowed values at the database level using a `CHECK` constraint, a native enum type, or a reference table with a foreign key:

```sql
-- Option A: CHECK constraint (simple, easy to evolve)
ALTER TABLE orders ADD CONSTRAINT orders_status_valid
    CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled'));

-- Option B: native enum type (compact, but adding values requires ALTER TYPE)
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'shipped', 'delivered', 'cancelled');

-- Option C: reference table + FK (most flexible; values are data, not schema)
CREATE TABLE order_statuses (code text PRIMARY KEY);
ALTER TABLE orders ADD CONSTRAINT orders_status_fk
    FOREIGN KEY (status) REFERENCES order_statuses (code);
```

> **Key Takeaway:** Money is exact decimals (`NUMERIC`) or integer minor units, always with a currency and a documented rounding policy -- never floats. Time is `timestamptz` stored in UTC, with the user's IANA time zone kept separately when local-clock semantics matter. State columns are constrained by `CHECK`, enum, or FK so bad values can never enter. These are cheap to get right up front and brutally expensive to fix after the bad data has spread.

---

### Connection & Resource Management

A database has a hard, finite ceiling on concurrent connections, and every connection consumes real server resources. In PostgreSQL each connection is a separate OS process using several megabytes of RAM, so the default `max_connections` of 100 is a genuine limit, not a suggestion. Mismanaging connections turns a healthy database into an outage faster than almost any query problem.

#### Pool to the Database's Limit, Not Your App's Ambition

Always use a connection pool -- PgBouncer in front of the database, plus your framework's pool (SQLAlchemy's `QueuePool`, Django's `CONN_MAX_AGE`). The critical sizing rule is counter-intuitive: **size the total pool to what the database can handle, not to your application's concurrency.** Ten app servers each opening a pool of 50 connections is 500 connections demanded against a `max_connections` of 100 -- the database will reject connections and effectively go down. More connections than the DB can serve does not increase throughput; past the point where active connections roughly match CPU cores plus effective spindles, added connections only increase context-switching and lock contention, *reducing* throughput.

```python
# SQLAlchemy: a pool sized deliberately, with a bounded checkout wait
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg://user:pass@host/db",
    pool_size=10,          # steady-state connections this process keeps
    max_overflow=5,        # extra connections allowed under burst (hard cap 15)
    pool_timeout=3,        # seconds to wait for a free connection before erroring
    pool_recycle=300,      # recycle connections older than 5 min (avoid stale TCP)
    pool_pre_ping=True,    # validate a connection before handing it out
)
```

**How to read this configuration:** `pool_size + max_overflow` (here 15) is this *one process's* hard ceiling -- multiply by the number of processes/replicas and that total must stay comfortably under the database's `max_connections` (with headroom for migrations, monitoring, and superuser sessions). `pool_timeout=3` is the safety valve that matters most under load: when every connection is busy, a request waits at most 3 seconds and then fails fast, rather than piling up an unbounded queue of stalled requests that exhausts the web server's worker threads -- the mechanism by which one slow query cascades into a total outage.

#### Timeouts at Every Layer

An unbounded wait anywhere in the stack is a latent outage. Set explicit timeouts at each layer so a single stuck operation cannot hold resources indefinitely:

```sql
-- Set per-role or per-session; can also go in postgresql.conf
SET statement_timeout = '5s';                      -- kill any query running > 5s
SET lock_timeout = '2s';                           -- give up waiting for a lock after 2s
SET idle_in_transaction_session_timeout = '10s';   -- abort transactions left open & idle
```

- **`statement_timeout`** caps how long any single query may run -- the backstop against a missing index or a runaway report dragging the server down.
- **`lock_timeout`** caps how long a statement waits to *acquire* a lock; without it, a migration needing a brief `ACCESS EXCLUSIVE` lock can queue behind a long query and then block every transaction behind it.
- **`idle_in_transaction_session_timeout`** aborts transactions that were opened and then abandoned (a common bug where application code starts a transaction, makes a slow external API call, and holds locks + prevents VACUUM the whole time).
- Above the database, set **connection/socket timeouts** in the driver and **pool checkout timeouts** (the `pool_timeout` above) so the app never blocks forever waiting on the network or on a free connection.

> **Common pitfall:** Setting a generous `statement_timeout` but forgetting `idle_in_transaction_session_timeout`. A query that finishes quickly but leaves its transaction open (because the app then does slow work before COMMIT) still holds row locks and pins dead tuples from VACUUM -- the timeout that catches this is the idle-in-transaction one, not the statement one.

#### Serverless and the Connection-Exhaustion Trap

Serverless functions (AWS Lambda, Cloud Functions) break the pooling model: the platform may spin up hundreds or thousands of concurrent function instances, and each one that opens its own database connection multiplies straight onto the database. A traffic spike that launches 1,000 Lambda instances against a `max_connections` of 100 exhausts the database instantly, even though each function is only doing trivial work. The fixes:

- Put a **connection proxy** between the functions and the database -- **Amazon RDS Proxy** or a PgBouncer instance -- that maintains a small warm pool and multiplexes the flood of short-lived function connections onto it.
- Or use a **serverless/HTTP-based database driver** (e.g. Neon's or Supabase's HTTP driver, Aurora Data API) that does not hold a persistent TCP connection per invocation at all.

> **Key Takeaway:** Connections are a scarce, server-side resource. Always pool, and size the *aggregate* pool across all app instances to the database's `max_connections`, never to your desired concurrency. Set timeouts at every layer -- `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`, and pool checkout timeouts -- so no single stuck operation can cascade into an outage. In serverless environments, front the database with RDS Proxy/PgBouncer or use a connection-less driver, or you will exhaust connections on the first real traffic spike.

---

### ETL & Data Pipelines

> [!NOTE]
> **Beginner's Mental Model — ETL vs. ELT:**
> Imagine you run a juice company importing oranges from different farms:
>
> - **ETL (Extract, Transform, Load)** is like squeezing the oranges into juice at a factory *before* shipping the cartons to your retail stores. The stores receive ready-to-sell juice, saving space and weight, but if they later decide they wanted orange marmalade instead, they are out of luck because the raw oranges were already processed.
> - **ELT (Extract, Load, Transform)** is like shipping the whole, raw oranges directly to a massive warehouse store first. Once inside the warehouse, you can squeeze them into juice, make marmalade, or slice them up on demand using the warehouse's advanced kitchen. This keeps the raw data available for any future use, but requires a powerful, modern warehouse to handle the processing.

#### ETL vs ELT

**ETL (Extract, Transform, Load)** is the traditional pattern: extract data from source systems, transform it (clean, enrich, aggregate, reshape) in a processing layer, and then load the transformed data into the destination (data warehouse). This approach makes sense when the destination has limited compute resources or when you want to minimize the data stored.

**ELT (Extract, Load, Transform)** is the modern approach enabled by powerful cloud data warehouses (BigQuery, Snowflake, Redshift). Raw data is extracted and loaded directly into the warehouse, then transformed in-place using SQL. ELT is simpler because it eliminates a separate processing layer and leverages the warehouse's massive compute for transformations.

```python
# Simple ETL pipeline example using Python

import pandas as pd
from sqlalchemy import create_engine

# EXTRACT: read from source
source_engine = create_engine('postgresql://user:pass@source-db/mydb')
df = pd.read_sql("""
    SELECT id, email, created_at, last_login_at, order_count
    FROM users
    WHERE created_at >= %(start_date)s
""", source_engine, params={'start_date': '2025-01-01'})

# TRANSFORM: clean and enrich
df['email_domain'] = df['email'].str.split('@').str[1]
df['days_since_login'] = (pd.Timestamp.now() - pd.to_datetime(df['last_login_at'])).dt.days
df['user_segment'] = pd.cut(
    df['order_count'],
    bins=[0, 1, 5, 20, float('inf')],
    labels=['new', 'casual', 'regular', 'power']
)
df = df.drop(columns=['email'])  # Remove PII

# LOAD: write to warehouse
warehouse_engine = create_engine('postgresql://user:pass@warehouse-db/analytics')
df.to_sql('dim_users', warehouse_engine, if_exists='append', index=False, method='multi')
```

After the TRANSFORM step, inspecting `df.head()` shows the reshaped frame that gets loaded (PII column dropped, derived columns added):

```text
   id           created_at           last_login_at  order_count email_domain  days_since_login user_segment
0   1  2025-01-03 09:12:00     2025-05-30 11:02:00            3    gmail.com                  5      casual
1   2  2025-01-07 14:55:00     2025-02-01 08:30:00           41  outlook.com                123       power
2   3  2025-01-09 22:01:00                     NaT            0  company.com                NaN         new
```

**How to read this output:** the `email` column is gone (intentionally dropped for PII compliance before anything touches the warehouse), replaced by the non-identifying `email_domain`. `user_segment` comes from `pd.cut`, which buckets `order_count` into labeled bins -- 41 orders lands in `power`, 0 lands in `new`. Watch the row with no `last_login_at`: pandas propagates the missing value as `NaT`, and the arithmetic yields `NaN` for `days_since_login` rather than raising. That silent null is the classic ETL trap -- it loads cleanly but skews every downstream "average days since login" metric, which is exactly the kind of defect the Great Expectations checks later in this section are meant to catch before the data reaches a dashboard.

#### Orchestration with Apache Airflow

Apache Airflow is the standard tool for orchestrating data pipelines as DAGs (Directed Acyclic Graphs). Each node in the DAG is a task, and edges define dependencies.

```python
# airflow_dags/daily_etl.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'daily_user_etl',
    default_args=default_args,
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
) as dag:

    extract = PythonOperator(
        task_id='extract_users',
        python_callable=extract_users_from_source,
    )

    transform = PythonOperator(
        task_id='transform_users',
        python_callable=transform_user_data,
    )

    load = PythonOperator(
        task_id='load_to_warehouse',
        python_callable=load_to_warehouse,
    )

    validate = PostgresOperator(
        task_id='validate_data',
        postgres_conn_id='warehouse',
        sql="""
            DO $$
            BEGIN
                IF (SELECT COUNT(*) FROM dim_users
                    WHERE load_date = CURRENT_DATE) = 0 THEN
                    RAISE EXCEPTION 'No rows loaded';
                END IF;
            END $$;
        """,
    )

    extract >> transform >> load >> validate
```

#### CDC (Change Data Capture)

Change Data Capture captures row-level changes (INSERT, UPDATE, DELETE) from the database's transaction log and streams them as events. This is the foundation of real-time data integration.

**Debezium** is the leading open-source CDC platform. It reads PostgreSQL's WAL (or MySQL's binlog) and publishes change events to Apache Kafka:

```
  CDC Architecture with Debezium
  ===============================

  +-------------+       WAL        +-----------+     Kafka Topics     +------------------+
  | PostgreSQL  | ----------------> | Debezium  | ------------------> | Kafka            |
  | (source DB) |   logical         | Connector |   dbserver.schema.  | +--> Consumer A  |
  +-------------+   replication     +-----------+   table_name        | |   (cache sync)  |
                                                                      | +--> Consumer B  |
                                                                      |     (warehouse)  |
                                                                      | +--> Consumer C  |
                                                                      |     (search idx) |
                                                                      +------------------+
```

A Debezium change event looks like this:

```json
{
    "before": { "id": 42, "name": "Alice", "email": "alice@old.com" },
    "after":  { "id": 42, "name": "Alice", "email": "alice@new.com" },
    "source": {
        "version": "2.5.0",
        "connector": "postgresql",
        "ts_ms": 1718450000000,
        "db": "mydb",
        "schema": "public",
        "table": "users"
    },
    "op": "u",
    "ts_ms": 1718450000123
}
```

CDC enables several powerful patterns: keeping a search index (Elasticsearch) in sync with the primary database, invalidating caches when data changes, replicating data to a warehouse in near-real-time, and driving event-driven architectures without modifying application code.

#### Data Quality

Data quality is not an afterthought -- bad data leads to bad decisions. Implement validation at multiple layers:

```python
# Using Great Expectations for data validation
import great_expectations as gx

context = gx.get_context()

# Define expectations for a dataset
validator = context.sources.pandas_default.read_dataframe(df)
validator.expect_column_values_to_not_be_null("user_id")
validator.expect_column_values_to_be_unique("user_id")
validator.expect_column_values_to_be_between("order_count", min_value=0)
validator.expect_column_values_to_match_regex("email_domain", r"^[a-z0-9.-]+\.[a-z]{2,}$")
validator.expect_table_row_count_to_be_between(min_value=1000, max_value=1000000)

results = validator.validate()
if not results.success:
    raise DataQualityError(f"Validation failed: {results}")
```

When one expectation fails -- say a handful of `user_id` values are null -- `results` summarizes which checks passed and which did not:

```text
{
  "success": false,
  "statistics": {
    "evaluated_expectations": 5,
    "successful_expectations": 4,
    "unsuccessful_expectations": 1,
    "success_percent": 80.0
  },
  "results": [
    {
      "expectation_config": {"expectation_type": "expect_column_values_to_not_be_null",
                             "kwargs": {"column": "user_id"}},
      "success": false,
      "result": {"element_count": 12450, "unexpected_count": 18,
                 "unexpected_percent": 0.1445, "partial_unexpected_list": [null, null, null]}
    }
  ]
}
```

**How to read this output:** `success: false` at the top is the single boolean the pipeline branches on -- here it flips the `if` and raises `DataQualityError`, which in an Airflow DAG fails the task and stops bad data from propagating downstream. The detail block tells you *why*: 18 of 12,450 rows (0.14%) had a null `user_id` despite the not-null expectation. That `unexpected_percent` is what you alert on -- a row count that's slightly off may be tolerable, but a primary-key column going null almost always means a broken upstream join. The other four expectations passed, so the failure is narrowly scoped, which is the whole point of declaring expectations per-column rather than one monolithic check: you learn exactly which assumption the data violated.

> **Common pitfall:** Treating any failed expectation as a hard stop. Some checks (an unusual row count, a slightly stale timestamp) warrant a warning, not a pipeline halt -- wiring every expectation to `raise` causes alert fatigue and tempts on-call engineers to disable validation entirely. Separate blocking expectations (null primary keys, broken foreign keys) from advisory ones.

Data quality dimensions to monitor include:

- **Completeness**: Are required fields populated? What percentage of rows have null values?
- **Freshness**: Is the data current? When was the last update?
- **Volume**: Is the row count within expected bounds? A sudden drop may indicate a broken pipeline.
- **Schema**: Do column types and names match expectations? Did an upstream schema change break the pipeline?
- **Accuracy**: Do values fall within expected ranges? Are foreign key references valid?

#### Batch vs Streaming (Lambda and Kappa)

Pipelines process data in one of two paradigms. **Batch** processing runs periodically over a bounded chunk of accumulated data -- nightly aggregations, hourly rollups -- using tools like Airflow-scheduled jobs or Spark. It is simple, easy to reason about and reprocess, but introduces latency (results are as fresh as the last run). **Streaming** processes events one at a time (or in micro-batches) as they arrive, using engines like Kafka Streams or Apache Flink, giving near-real-time results at the cost of more operational complexity and harder semantics around ordering and late-arriving data.

Two reference architectures combine or choose between them:

- **Lambda architecture** runs a **batch layer** (accurate, complete, recomputed periodically) *and* a **speed layer** (fast, approximate, streaming) in parallel, merging their outputs at query time. It gives both correctness and low latency but forces you to maintain the same logic twice, in two codebases.
- **Kappa architecture** drops the batch layer entirely: everything is a stream, and "reprocessing" means replaying the event log from the beginning through the same streaming code. One codebase, simpler to maintain, but it demands a durable, replayable log (Kafka) and streaming logic robust enough to also serve as your batch backfill.

#### Apache Kafka

Kafka is a distributed, durable, append-only **commit log** that sits at the heart of most streaming and CDC pipelines. The core concepts:

- **Topics** are named categories of events. A topic is split into **partitions**, which are the unit of parallelism and the *only* scope in which ordering is guaranteed -- events are ordered within a partition, never across partitions. The partition is chosen by the event key (e.g. all events for `user_id=42` hash to the same partition, preserving per-user order).
- **Consumer groups** provide load balancing: each partition is consumed by exactly one consumer within a group, so adding consumers (up to the partition count) scales throughput. Multiple independent groups can each read the whole topic for different purposes.
- **Offsets** are each consumer's bookmark -- the position it has read up to in a partition. Committing the offset *after* successfully processing a message gives **at-least-once** delivery (a crash before commit re-delivers the message); committing before gives at-most-once.
- **Retention** keeps messages for a configured time or size regardless of consumption, which is what makes replay (and Kappa-style reprocessing) possible.
- **Exactly-once semantics** are achievable with the **idempotent producer** (dedupes retried writes) plus **transactions** spanning the consume-process-produce cycle, so a message is processed and its result published atomically.

```python
# Consumer committing offsets only after processing -> at-least-once
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "orders",
    group_id="invoice-service",
    enable_auto_commit=False,          # commit manually, after work succeeds
    auto_offset_reset="earliest",
)

for message in consumer:
    process(message.value)             # if this throws, offset is NOT committed
    consumer.commit()                  # bookmark advances only on success
```

**How to read this code:** `enable_auto_commit=False` plus a manual `commit()` *after* `process()` is the standard at-least-once pattern -- if the worker crashes between processing and committing, the message is re-delivered and processed again on restart. That is why downstream processing must be **idempotent** (e.g. UPSERT on a natural key): at-least-once guarantees no message is lost but explicitly allows duplicates. Choosing `enable_auto_commit=True` would silently commit on a timer and risk losing in-flight messages on a crash -- the classic "we lost events but the offsets said we processed them" incident.

#### Warehouse, Lake, and Lakehouse

The destination for analytical data has evolved through three models:

- **Data warehouse** -- structured, query-optimized storage with a schema enforced on write (Snowflake, BigQuery, Redshift). Excellent for BI and SQL analytics; you pay to load and structure data up front (schema-on-write).
- **Data lake** -- cheap object storage (S3, GCS) holding raw files in open formats like Parquet, with schema applied only when read (schema-on-read). Flexible and inexpensive at massive scale, but without governance it degrades into a "data swamp" of undocumented files.
- **Lakehouse** -- open **table formats** (Delta Lake, Apache Iceberg, Apache Hudi) layered over lake storage that add ACID transactions, schema evolution, time travel, and efficient updates/deletes. It aims to give warehouse-grade reliability on lake-grade economics, so one copy of the data serves both BI and ML.

The dominant organizing principle within these is the **medallion architecture**, which refines data through quality tiers:

```text
  Bronze  -->  Silver  -->  Gold
  (raw)        (cleaned)     (curated)

  Bronze: raw ingested data, exactly as received (immutable landing zone,
          full history, replayable source of truth)
  Silver: cleaned, deduplicated, conformed, joined (validated, typed,
          business keys resolved)
  Gold:   aggregated, business-level marts / dimensional models ready for
          BI dashboards and ML features
```

**How to read this:** Each arrow is a transformation step with its own dbt models and data-quality tests, and the tiers are intentionally separate physical tables, not views. **Bronze** stays raw and immutable so you can always reprocess from a faithful copy if downstream logic has a bug -- it is the lake's replayable source of truth. **Silver** is where cleaning, deduplication, and conforming happen (the work the Great Expectations checks above guard). **Gold** is what analysts and dashboards actually query -- the star-schema marts described in the next section. The discipline of materializing each tier is what keeps a lake from rotting into a swamp: every table has a known quality contract and a clear lineage back to bronze.

> **Key Takeaway:** Modern data pipelines favor ELT over ETL when the warehouse has sufficient compute power. Use Airflow or similar orchestrators for complex dependencies and retries. CDC with Debezium enables real-time data integration without modifying application code. Choose batch for simplicity, streaming (Kafka + Flink) for freshness, and Kappa over Lambda when a replayable log lets you avoid maintaining two codebases. Land data through medallion tiers (bronze/silver/gold) so every table has a known quality contract. Data quality validation is essential -- build it into every pipeline, not as an afterthought.

---

### Dimensional Modeling (Analytics Schemas)

Transactional (OLTP) databases are normalized to make writes safe and non-redundant. Analytical (OLAP) databases are modeled the opposite way -- **dimensionally** -- to make large aggregate reads fast and intuitive for BI tools. Dimensional modeling, popularized by Ralph Kimball, is the standard way to structure the **gold** tier of a warehouse.

#### Star Schema

A **star schema** has a central **fact table** surrounded by **dimension tables**. The fact table records measurable business *events* -- one row per event -- holding numeric **measures** (quantities, amounts) plus foreign keys to the dimensions. Dimension tables hold the descriptive *context* you slice and filter by (who, what, when, where): customer, product, date, store. The shape -- one fact in the middle, dimensions radiating out -- is the "star."

```sql
-- Fact table: one row per order line item (the grain), numeric measures + FKs
CREATE TABLE fact_sales (
    sale_id       bigserial PRIMARY KEY,
    date_key      int    NOT NULL REFERENCES dim_date(date_key),
    product_key   int    NOT NULL REFERENCES dim_product(product_key),
    customer_key  int    NOT NULL REFERENCES dim_customer(customer_key),
    store_key     int    NOT NULL REFERENCES dim_store(store_key),
    quantity      int    NOT NULL,         -- measure
    revenue       numeric(19,4) NOT NULL,  -- measure
    discount      numeric(19,4) NOT NULL   -- measure
);

-- Dimension table: descriptive attributes, denormalized for query simplicity
CREATE TABLE dim_product (
    product_key   serial PRIMARY KEY,      -- surrogate key (not the source PK)
    product_id    text NOT NULL,           -- natural/business key from source
    name          text NOT NULL,
    category      text NOT NULL,
    brand         text NOT NULL
);

-- A typical BI query: revenue by category by month
SELECT d.year, d.month, p.category, SUM(f.revenue) AS revenue
FROM fact_sales f
JOIN dim_date    d ON d.date_key = f.date_key
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY d.year, d.month, p.category
ORDER BY d.year, d.month, revenue DESC;
```

The star schema joins are simple (fact-to-dimension, one hop each) and BI tools generate them automatically, which is exactly why this layout dominates analytics.

#### Snowflake Schema

A **snowflake schema** normalizes the dimensions further -- e.g. `dim_product` splits into `dim_product -> dim_category -> dim_department`. It saves some storage and avoids update anomalies in dimensions, but adds more joins and complexity to every query. In practice the star schema is usually preferred: storage is cheap, dimension tables are small, and query simplicity and speed matter more for analytics. Snowflake only when a dimension is genuinely large and volatile.

#### Grain

Before writing a single column, define the **grain**: exactly what one row in the fact table represents. "One row per order"? "One row per order *line item*"? "One row per product per day (a daily snapshot)"? The grain determines what you can and cannot measure -- you can always roll a fine grain up, but you can never recover detail a coarse grain threw away. Getting the grain wrong (mixing order-level and line-item-level rows in one fact table, for instance) poisons every aggregate built on top, double-counting or under-counting silently. Declaring the grain first is the most important step in the whole exercise.

#### Slowly Changing Dimensions (SCD)

Dimension attributes change over time -- a customer relocates, a product is recategorized. **Slowly Changing Dimensions** are the standard strategies for handling that change, and the choice hinges on whether you need history:

- **Type 1 (overwrite)**: just update the attribute in place. Simple, but you *lose history* -- past facts now appear under the new value (a customer who moved looks like they always lived in the new city).
- **Type 2 (new row + validity range)**: insert a *new* dimension row with a new surrogate key and `valid_from`/`valid_to` dates (and often an `is_current` flag), keeping the old row intact. Facts point to whichever version was current when the event occurred, so history is preserved exactly. This is the common choice when history matters.
- **Type 3 (previous-value column)**: keep a `previous_value` column alongside the current one. Captures only the last change, useful when you need limited before/after comparison without full history.

```sql
-- Type 2 dimension: each version of a customer is its own row
CREATE TABLE dim_customer (
    customer_key  serial PRIMARY KEY,    -- surrogate key, unique per version
    customer_id   text NOT NULL,         -- natural key, stable across versions
    name          text NOT NULL,
    city          text NOT NULL,
    valid_from    date NOT NULL,
    valid_to      date,                  -- NULL = current version
    is_current    boolean NOT NULL DEFAULT true
);
```

```text
 customer_key | customer_id | name  | city     | valid_from | valid_to   | is_current
--------------+-------------+-------+----------+------------+------------+-----------
          501 | C-1007      | Alice | Berlin   | 2023-01-01 | 2025-03-31 | f
          892 | C-1007      | Alice | Munich   | 2025-04-01 | (null)     | t
```

**How to read this output:** Both rows are the *same* customer (`customer_id = C-1007`) but two **versions**, each with its own surrogate `customer_key`. A sale recorded in February 2025 references key `501` (Berlin); a sale in May references key `892` (Munich) -- so when you aggregate revenue by city, each sale is correctly attributed to where Alice lived *at the time*, which a Type 1 overwrite would have falsified by moving all her history to Munich. The `valid_to IS NULL` / `is_current = true` row is the live version new facts attach to. This versioned-row pattern is the canonical interview answer to "how do you preserve history when a dimension attribute changes?"

> **Key Takeaway:** Model analytics dimensionally: a central fact table of measurable events at a clearly-defined grain, surrounded by descriptive dimension tables (star schema). Prefer star over snowflake unless a dimension is large and volatile. Declare the grain before anything else -- it is the decision everything else depends on. And choose your SCD type by whether history matters: Type 1 overwrites and forgets, Type 2 versions rows to preserve full history (the usual choice), Type 3 keeps just the previous value.

*Last reviewed: 2026-06-08*
