[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 7.3 Observability

### Logging

#### Structured Logging

Traditional log messages are unstructured strings: `"User 42 logged in from 10.0.0.1"`. They are easy for humans to read but painful for machines to parse. Structured logging outputs each log entry as a JSON object with explicit, typed fields. This makes logs machine-parseable, searchable, filterable, and aggregatable.

Every structured log entry should include at minimum: `timestamp`, `level`, `message`, `service`, `logger`. For request-scoped logs, add `trace_id`, `request_id`, `user_id`, `method`, `path`, `status_code`, and `duration_ms`. This metadata is what makes debugging distributed systems possible.

In Python, the `structlog` library is the gold standard for structured logging. It provides context-aware logging (bind fields once, include them in all subsequent log entries), a processor pipeline (for filtering, formatting, adding fields), and seamless integration with the standard library.

```python
# app/logging_config.py
"""
Structured logging configuration using structlog.
"""

import logging
import sys
import structlog


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output JSON. If False, output colored console text
                     (useful for local development).
    """

    # Shared processors used by both structlog and stdlib logging.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,    # Merge context from contextvars
        structlog.stdlib.add_logger_name,           # Add logger name field
        structlog.stdlib.add_log_level,             # Add log level field
        structlog.stdlib.ExtraAdder(),               # Add extra kwargs as fields
        structlog.processors.TimeStamper(fmt="iso"), # ISO 8601 timestamp
        structlog.processors.StackInfoRenderer(),    # Render stack_info if present
        structlog.processors.UnicodeDecoder(),       # Decode bytes to str
    ]

    if json_output:
        # Production: JSON output
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored, human-readable output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

```python
# app/middleware.py
"""
Request logging middleware that binds context for every log within a request.
"""

import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.stdlib.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates a unique request_id for each request.
    2. Binds request context (method, path, user, trace) to structlog contextvars.
    3. Logs request start and completion with timing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

        # Clear and bind context for this request. All log calls within this
        # request (in any module) will include these fields automatically.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        logger.info("request_started")
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Propagate request_id in response headers for client-side correlation.
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,     # Include full traceback
            )
            raise
```

```python
# app/services/order_service.py
"""
Example service demonstrating structured logging in business logic.
"""

import structlog

logger = structlog.stdlib.get_logger()


async def create_order(user_id: int, items: list[dict]) -> dict:
    """
    Business logic for creating an order.
    Note: we do NOT need to pass request_id or trace_id here.
    They are automatically included from the contextvars bound by middleware.
    """

    # Bind user context -- all subsequent logs in this function include user_id.
    structlog.contextvars.bind_contextvars(user_id=user_id)

    logger.info("order_creation_started", item_count=len(items))

    total = sum(item["price"] * item["quantity"] for item in items)

    if total > 10000:
        logger.warning("high_value_order_detected", total=total)

    # ... database operations ...

    order_id = 12345  # placeholder

    logger.info(
        "order_created",
        order_id=order_id,
        total=total,
        item_count=len(items),
    )

    return {"order_id": order_id, "total": total}
```

The resulting log output in production looks like this (one JSON object per line):

```json
{"timestamp": "2026-03-25T10:15:30.123456Z", "level": "info", "event": "request_started", "logger": "app.middleware", "request_id": "a1b2c3d4", "trace_id": "e5f6g7h8", "method": "POST", "path": "/api/v1/orders", "client_ip": "10.0.0.42"}
{"timestamp": "2026-03-25T10:15:30.125000Z", "level": "info", "event": "order_creation_started", "logger": "app.services.order_service", "request_id": "a1b2c3d4", "trace_id": "e5f6g7h8", "method": "POST", "path": "/api/v1/orders", "client_ip": "10.0.0.42", "user_id": 42, "item_count": 3}
{"timestamp": "2026-03-25T10:15:30.140000Z", "level": "info", "event": "order_created", "logger": "app.services.order_service", "request_id": "a1b2c3d4", "trace_id": "e5f6g7h8", "method": "POST", "path": "/api/v1/orders", "client_ip": "10.0.0.42", "user_id": 42, "order_id": 12345, "total": 299.97, "item_count": 3}
{"timestamp": "2026-03-25T10:15:30.142000Z", "level": "info", "event": "request_completed", "logger": "app.middleware", "request_id": "a1b2c3d4", "trace_id": "e5f6g7h8", "method": "POST", "path": "/api/v1/orders", "client_ip": "10.0.0.42", "user_id": 42, "status_code": 201, "duration_ms": 18.55}
```

Every log line carries the full context. You can search for all logs from request `a1b2c3d4`, or all orders by user `42`, or all requests slower than 100ms, without relying on regex or manual parsing.

#### Log Levels

Log levels control the verbosity of your logging output. Choosing the right level for each log statement is important for keeping production logs useful without drowning in noise.

**DEBUG:** Fine-grained diagnostic information useful only during development. Variable values, SQL queries, cache hit/miss details. Never enable in production by default (too much volume and potential for sensitive data exposure).

**INFO:** Business-significant events and normal operations. Request received, order created, user logged in, payment processed, cache refreshed. This is your primary level in production.

**WARNING:** Unexpected situations that the application handled gracefully. Deprecated API usage, retry after a transient failure, approaching rate limit, disk usage above 80%. Something a developer should look at, but it is not an emergency.

**ERROR:** Failures that need attention. An unhandled exception, a failed external API call that could not be retried, a database query timeout. These warrant investigation. Error logs should include full stack traces.

**CRITICAL:** System-level failures that may require immediate intervention. Database connection pool exhausted, out of memory, configuration missing on startup. The application may not be able to continue functioning.

Never log sensitive data: passwords, access tokens, credit card numbers, personally identifiable information (PII). Implement redaction processors in your logging pipeline that strip or mask sensitive fields before they reach your log aggregator.

#### Correlation IDs

In a microservice architecture, a single user request often flows through multiple services. Without a correlation mechanism, it is impossible to trace which logs belong to the same user interaction across services.

A **request ID** (or correlation ID) is a unique identifier generated at the entry point (API gateway, first service) and propagated in HTTP headers through every downstream service call. Every log entry includes this ID, so you can search for it in your log aggregator and see the complete journey of a request across all services.

A **trace ID** (from distributed tracing systems like OpenTelemetry, Jaeger, or Zipkin) extends this concept with span hierarchies that show timing and parent-child relationships between operations.

Propagation is straightforward: when service A calls service B, it includes the trace/request ID in an HTTP header (commonly `X-Request-ID` or W3C `traceparent`). Service B reads it and binds it to its logging context.

#### Log Aggregation

In a distributed system with dozens of services running across many containers, you cannot SSH into individual machines to read logs. A log aggregation system collects logs from all sources, stores them centrally, indexes them, and provides a search and visualization interface.

**ELK Stack (Elasticsearch + Logstash + Kibana):** The original log aggregation stack. Elasticsearch stores and indexes logs. Logstash ingests, transforms, and forwards logs. Kibana provides search and dashboards. Powerful but resource-intensive and expensive at scale.

**EFK Stack (Elasticsearch + Fluentd + Kibana):** Replaces Logstash with Fluentd (or Fluent Bit for lower resource usage). Fluentd is a CNCF project widely used in Kubernetes environments. Fluent Bit runs as a DaemonSet, tailing container logs and forwarding them to Elasticsearch.

**Loki + Grafana:** Grafana Loki is a log aggregation system that indexes only labels (metadata), not the full log text. This makes it dramatically cheaper to run than Elasticsearch. Logs are stored in object storage (S3). You query using LogQL. Because it integrates natively with Grafana, you can have metrics and logs in the same dashboard.

**Cloud-native:** AWS CloudWatch Logs, Google Cloud Logging, Azure Monitor Logs. Lowest operational overhead if you are already on that cloud.

#### Sampling

For high-traffic services (thousands of requests per second), logging every single request in full detail creates enormous volume and cost. Sampling strategies reduce volume while preserving visibility into problems.

**Head-based sampling** decides at the start of a request whether to log it in full. For example, log 10% of requests in detail and only log summary metrics for the rest. This is simple but means you might miss the one request that fails.

**Tail-based sampling** buffers data during the request and makes the sampling decision after the request completes. This lets you always log errors, slow requests, and unusual patterns in full while sampling routine successes. Tail-based sampling is more complex to implement but produces much more useful data.

A common practical approach: always log errors and slow requests (> P99 latency) in full detail. Sample normal successful requests at a configurable rate (e.g., 10%).

> **Key Takeaway:** Structured logging (JSON with explicit fields) is non-negotiable for production systems. Use structlog in Python with context-bound fields. Assign every request a unique ID and propagate it across services. Aggregate logs centrally with ELK, Loki, or a cloud service. Choose appropriate log levels and never log sensitive data. For high-traffic systems, implement sampling to control volume and cost.

---

### Metrics & Monitoring

#### Prometheus

Prometheus is the de facto standard for metrics collection in cloud-native environments. It uses a **pull-based** model: Prometheus scrapes HTTP endpoints (usually `/metrics`) on your services at configured intervals. Each service exposes metrics in Prometheus's text-based exposition format.

Prometheus supports four metric types:

**Counter:** A monotonically increasing value that only goes up (or resets to zero on restart). Use for: total requests served, total errors, total bytes sent. To get the rate of change, use `rate()` or `irate()` in PromQL.

**Gauge:** A value that can go up and down. Use for: current temperature, number of active connections, memory usage, queue depth.

**Histogram:** Samples observations (e.g., request durations) and counts them in configurable buckets. Allows computing quantiles (P50, P95, P99) server-side. Use for: request latency, response body size.

**Summary:** Similar to histogram but computes quantiles client-side. Less flexible for aggregation across instances. Generally, prefer histograms.

Each service exposes these metrics over the `/metrics` endpoint in Prometheus's text-based exposition format. Hitting it with `curl localhost:8000/metrics` returns something like:

```text
# HELP http_requests_total Total HTTP requests.
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/api/v1/orders",status_code="201"} 1482
http_requests_total{method="GET",path="/api/v1/orders",status_code="200"} 90413
http_requests_total{method="POST",path="/api/v1/orders",status_code="500"} 37
# HELP http_request_duration_seconds Request latency in seconds.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{path="/api/v1/orders",le="0.1"} 88201
http_request_duration_seconds_bucket{path="/api/v1/orders",le="0.5"} 91802
http_request_duration_seconds_bucket{path="/api/v1/orders",le="1.0"} 91930
http_request_duration_seconds_bucket{path="/api/v1/orders",le="+Inf"} 91932
http_request_duration_seconds_sum{path="/api/v1/orders"} 7184.3
http_request_duration_seconds_count{path="/api/v1/orders"} 91932
# HELP db_pool_active_connections Active DB connections.
# TYPE db_pool_active_connections gauge
db_pool_active_connections 14
```

**How to read this output:** Each `# HELP`/`# TYPE` pair documents a metric so Prometheus knows how to treat it. The label sets in `{...}` create separate time series — `http_requests_total` is split per method, path, and status so you can compute per-endpoint error rates later. The histogram is the subtle one: each `_bucket{le="..."}` is a *cumulative* counter of observations at or below that boundary (`le` = "less than or equal"), plus a `_sum` and `_count`. Prometheus stores only these raw counters; the P95/P99 percentiles are reconstructed at query time with `histogram_quantile()`. This is why a single scrape is just an instantaneous snapshot of counters — the interesting signal comes from `rate()` over time, not the absolute numbers.

> **Common pitfall:** Every distinct label value creates a new time series. Putting high-cardinality values (user IDs, request IDs, raw URLs with query strings) into labels causes a "cardinality explosion" that can OOM Prometheus. Keep labels bounded — normalize `/orders/12345` to a templated `/orders/{id}` before it becomes a label.

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s        # How often to scrape targets
  evaluation_interval: 15s    # How often to evaluate alerting rules
  scrape_timeout: 10s

# Alerting configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load alerting rules
rule_files:
  - /etc/prometheus/rules/*.yml

# Scrape configurations
scrape_configs:
  # Prometheus scrapes itself
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]

  # Application service
  - job_name: myapp
    metrics_path: /metrics
    scrape_interval: 10s
    dns_sd_configs:
      - names:
          - myapp.production.svc.cluster.local
        type: A
        port: 8000
    # OR use Kubernetes service discovery
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - production
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: myapp
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # Node Exporter (system metrics from every node)
  - job_name: node-exporter
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - action: replace
        source_labels: [__address__]
        regex: (.+):(.+)
        replacement: $1:9100
        target_label: __address__

  # PostgreSQL Exporter
  - job_name: postgres-exporter
    static_configs:
      - targets: ["postgres-exporter:9187"]

  # Redis Exporter
  - job_name: redis-exporter
    static_configs:
      - targets: ["redis-exporter:9121"]
```

{% raw %}
```yaml
# prometheus/rules/alerts.yml
groups:
  - name: application-alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }} (>5%) for the last 5 minutes."

      # High latency
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
          > 2.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency above 2s on {{ $labels.service }}"
          description: "P99 latency is {{ $value | humanizeDuration }}."

      # Pod restarts
      - alert: PodRestarting
        expr: |
          increase(kube_pod_container_status_restarts_total[1h]) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} restarting frequently"
          description: "{{ $value }} restarts in the last hour."

      # Disk usage
      - alert: DiskUsageHigh
        expr: |
          (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) < 0.15
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Disk usage above 85% on {{ $labels.instance }}"
```
{% endraw %}

#### Grafana and PromQL

Grafana is the standard visualization tool for Prometheus metrics. You build dashboards composed of panels, each panel displaying one or more PromQL queries as graphs, gauges, tables, or heatmaps.

Below are practical PromQL queries organized by the type of insight they provide. These can be directly used as Grafana panel queries.

**Request Rate (throughput):**
```promql
# Total requests per second across all instances
sum(rate(http_requests_total[5m]))

# Requests per second broken down by endpoint
sum(rate(http_requests_total[5m])) by (method, path)

# Requests per second broken down by status code class
sum(rate(http_requests_total[5m])) by (status_code)
```

**Error Rate:**
```promql
# Error rate as a percentage (5xx responses / total responses)
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Error rate per endpoint
sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (path)
/
sum(rate(http_requests_total[5m])) by (path)
```

**Latency Distribution:**
```promql
# P50 (median) latency
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# P95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Average request duration
sum(rate(http_request_duration_seconds_sum[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))

# P99 latency per endpoint
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))
```

Run in Grafana's Explore view (or `curl` against Prometheus's `/api/v1/query`), the per-endpoint P99 query returns one value per series, something like:

```text
{path="/api/v1/orders"}    0.412
{path="/api/v1/search"}    1.870
{path="/api/v1/health"}    0.003
```

**How to read this output:** Values are in seconds, so `/api/v1/search` has a P99 of ~1.87s — one in a hundred search requests takes that long, even though the median is likely far lower. This is exactly the tail that an average would hide, and it is the number you compare against your SLO. In an interview, the key point is that `histogram_quantile` interpolates *within* the bucket that crosses the target quantile, so your percentile is only as precise as your bucket boundaries: if your largest finite bucket is `le="1.0"` but real latency reaches 5s, everything piles into `+Inf` and P99 is reported as effectively unbounded. Choose buckets that bracket your expected latency range.

**Resource Utilization:**
```promql
# CPU usage per pod (percentage of requested CPU)
sum(rate(container_cpu_usage_seconds_total{namespace="production"}[5m])) by (pod)
/
sum(kube_pod_container_resource_requests{resource="cpu", namespace="production"}) by (pod)

# Memory usage per pod (percentage of limit)
sum(container_memory_working_set_bytes{namespace="production"}) by (pod)
/
sum(kube_pod_container_resource_limits{resource="memory", namespace="production"}) by (pod)

# Node CPU utilization
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)
```

**Application-Specific Metrics:**
```promql
# Database connection pool utilization
db_pool_active_connections / db_pool_max_connections

# Cache hit rate
sum(rate(cache_hits_total[5m]))
/
(sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Queue depth (for background job systems)
job_queue_depth{queue="emails"}

# Active WebSocket connections
websocket_active_connections
```

#### RED Method

The RED method provides a simple framework for monitoring request-driven services (APIs, web servers, microservices). For every service, track three metrics:

**Rate:** The number of requests per second your service is handling. This tells you about traffic volume and helps you plan capacity. A sudden drop in rate might indicate an upstream issue; a sudden spike might be a traffic surge or an attack.

**Errors:** The number (or percentage) of requests that fail. Track both explicit errors (5xx status codes, exception counts) and implicit errors (successful responses with wrong content). Set alerts when the error rate exceeds your SLO.

**Duration:** How long requests take to process, as a distribution. Always look at percentiles (P50, P95, P99), not just averages. An average of 200ms can hide the fact that 1% of users wait 10 seconds. Duration degradation often precedes errors -- it is an early warning signal.

#### USE Method

The USE method is for monitoring infrastructure resources (CPU, memory, disk, network, database connections, thread pools). For every resource, track:

**Utilization:** The percentage of time the resource is busy, or the fraction of capacity in use. CPU at 80% utilization, disk at 60% full, connection pool 90% consumed.

**Saturation:** The degree to which the resource has extra work queued that it cannot serve. CPU run queue length, disk I/O queue depth, network socket backlog. High saturation means requests are waiting, which manifests as increased latency.

**Errors:** Resource-level error events. Disk read errors, network packet drops, OOM kills, connection timeouts.

#### Four Golden Signals (Google SRE)

Google's SRE book defines four signals that every service should monitor:

**Latency:** The time it takes to serve a request. Importantly, distinguish between the latency of successful requests and the latency of errors. A fast 500 error should not bring down your average latency -- it is still a problem.

**Traffic:** A measure of demand on your service. For web services, this is typically HTTP requests per second. For a streaming service, it might be concurrent sessions. For a data pipeline, it might be records processed per second.

**Errors:** The rate of requests that fail. This includes explicit errors (HTTP 5xx), implicit errors (HTTP 200 with wrong content or slow response violating your SLO), and policy errors (responses that succeed technically but violate business rules).

**Saturation:** How "full" your service is. This is typically the most constrained resource (CPU, memory, I/O, database connections). Saturation is predictive: it tells you when you are approaching capacity limits, before errors start occurring.

#### Alerting

Effective alerting is critical, but excessive or poorly designed alerting is counterproductive -- it leads to alert fatigue where on-call engineers start ignoring alerts.

**Alert on symptoms, not causes.** Do not alert on "CPU above 80%." Alert on "error rate above 1%" or "P99 latency above 2 seconds." Users do not care about CPU usage; they care about whether the service is working. If high CPU is not causing user impact, it does not warrant waking someone up.

**Every alert must be actionable.** If there is nothing an on-call engineer can do about an alert, it should not page anyone. It might belong in a dashboard or a daily report instead.

**Use severity levels.** Critical alerts (service is down, data loss risk) page immediately. Warning alerts (degraded performance, approaching limits) can wait for business hours. Info-level alerts go to a dashboard, not a pager.

**Implement on-call rotation.** No one should be on-call 24/7 indefinitely. Use tools like PagerDuty, OpsGenie, or Grafana OnCall to manage rotations, escalation policies, and incident tracking.

**Include context in alerts.** Alert messages should contain enough information for the responder to start investigating immediately: which service, which environment, the current metric value versus the threshold, a link to the relevant Grafana dashboard, and a link to the runbook.

> **Key Takeaway:** Observability is the combination of logs, metrics, and traces that lets you understand your system's behavior. Use Prometheus for metrics collection, Grafana for visualization, and structured logging for operational insight. Apply the RED method for services and the USE method for resources. Alert on user-facing symptoms, not internal causes. Make every alert actionable and include enough context for rapid diagnosis.
