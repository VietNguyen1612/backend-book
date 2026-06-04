# Chapter 4: Databases & Data

This chapter covers the database technologies and data management practices essential for backend engineering -- from deep PostgreSQL internals and query optimization, through NoSQL and specialized databases, to migration strategies, data patterns, and ETL pipelines.

## Table of Contents

### [4.1 Relational Databases (PostgreSQL Focus)](relational-databases.md)
Deep dive into PostgreSQL as the backbone of most backend systems.
- **Query Optimization** -- EXPLAIN ANALYZE, sequential vs index scans, query planner statistics, common anti-patterns (N+1, SELECT *, missing indexes)
- **Indexing Strategies** -- B-tree, Hash, GIN, GiST, BRIN, partial indexes, expression indexes, covering indexes
- **Transactions & Concurrency** -- ACID properties, isolation levels, MVCC internals, row-level locking, advisory locks, optimistic vs pessimistic locking
- **Advanced Features** -- Partitioning (range, list, hash), window functions, CTEs (including recursive), JSONB, full-text search, replication, connection pooling (PgBouncer)

### [4.2 NoSQL & Specialized Databases](nosql-and-specialized.md)
When and how to use non-relational databases alongside PostgreSQL.
- **Redis** -- Data structures (strings, hashes, lists, sets, sorted sets, streams, HyperLogLog), caching, rate limiting, distributed locking, Pub/Sub, persistence (RDB/AOF), clustering, Lua scripting, eviction policies
- **MongoDB** -- Document model, schema design for queries, indexing, aggregation pipeline, replication and sharding
- **Elasticsearch** -- Inverted indexes, mappings (keyword vs text), bool queries, aggregations, index lifecycle management
- **Time-Series Databases** -- TimescaleDB (hypertables, continuous aggregates, retention/compression), InfluxDB, Prometheus, ClickHouse

### [4.3 Data Management](data-management.md)
Strategies for evolving schemas, managing data lifecycle, and building pipelines.
- **Migration Strategies** -- Additive changes, breaking changes with expand-contract pattern, safe NOT NULL additions, schema versioning (Django, Alembic, Flyway, Liquibase)
- **Data Patterns** -- Soft delete, audit trails (trigger-based and application-level), multi-tenancy (row-level, schema-level, database-level), event sourcing with snapshots
- **ETL & Data Pipelines** -- ETL vs ELT, orchestration with Apache Airflow, CDC with Debezium, data quality validation with Great Expectations

---

[Back to Book Index](../../README.md)
