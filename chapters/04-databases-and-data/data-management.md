[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 4.3 Data Management

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

### ETL & Data Pipelines

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
            SELECT CASE
                WHEN COUNT(*) = 0 THEN RAISE EXCEPTION 'No rows loaded'
                ELSE 1
            END
            FROM dim_users
            WHERE load_date = CURRENT_DATE;
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

> **Key Takeaway:** Modern data pipelines favor ELT over ETL when the warehouse has sufficient compute power. Use Airflow or similar orchestrators for complex dependencies and retries. CDC with Debezium enables real-time data integration without modifying application code. Data quality validation is essential -- build it into every pipeline, not as an afterthought.
