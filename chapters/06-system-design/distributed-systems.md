[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 6.2 Distributed Systems

### Consensus & Coordination

**Raft** is a consensus algorithm designed to be understandable (in contrast to Paxos, which is notoriously difficult to implement correctly). Raft ensures that a cluster of nodes agrees on a sequence of operations (a replicated log), even if some nodes fail. It is used by etcd (which powers Kubernetes), Consul, CockroachDB, and TiKV.

Raft operates in three phases: **leader election**, **log replication**, and **safety**. At any time, each node is in one of three states: Leader, Follower, or Candidate.

**Step-by-step Raft Consensus -- Leader Election:**

```
INITIAL STATE: All nodes start as Followers. Each has a randomized election timeout.

  Node A (Follower)      Node B (Follower)      Node C (Follower)
  timeout: 150ms         timeout: 300ms         timeout: 200ms
  +----------------+     +----------------+     +----------------+
  | Term: 0        |     | Term: 0        |     | Term: 0        |
  | State: Follower|     | State: Follower|     | State: Follower|
  +----------------+     +----------------+     +----------------+

STEP 1: Node A's election timeout fires first (150ms). It becomes a Candidate,
         increments its term, and votes for itself.

  Node A (Candidate)     Node B (Follower)      Node C (Follower)
  +----------------+     +----------------+     +----------------+
  | Term: 1        |     | Term: 0        |     | Term: 0        |
  | State:Candidate|     | State: Follower|     | State: Follower|
  | Votes: {A}     |     |                |     |                |
  +----------------+     +----------------+     +----------------+
         |                                              |
         |---------- RequestVote(term=1) -------------->|
         |---------- RequestVote(term=1) ----->|        |

STEP 2: Nodes B and C receive RequestVote. They have not voted in term 1,
         so they grant their votes to A and update their term.

  Node A (Candidate)     Node B (Follower)      Node C (Follower)
  +----------------+     +----------------+     +----------------+
  | Term: 1        |     | Term: 1        |     | Term: 1        |
  | Votes: {A,B,C} |     | Voted for: A   |     | Voted for: A   |
  +----------------+     +----------------+     +----------------+
         |<--------- VoteGranted --------------|        |
         |<--------- VoteGranted -----------------------|

STEP 3: Node A receives majority (3/3). It becomes Leader.
         It immediately sends heartbeat AppendEntries to prevent new elections.

  Node A (LEADER)        Node B (Follower)      Node C (Follower)
  +----------------+     +----------------+     +----------------+
  | Term: 1        |     | Term: 1        |     | Term: 1        |
  | State: LEADER  |     | Leader: A      |     | Leader: A      |
  +----------------+     +----------------+     +----------------+
         |--- Heartbeat (empty AppendEntries) ->|      |
         |--- Heartbeat (empty AppendEntries) -------->|
```

**Step-by-step Raft Consensus -- Log Replication:**

```
CLIENT sends a write request: SET x = 42

STEP 1: Leader (A) appends entry to its log (uncommitted).

  Node A (LEADER)        Node B (Follower)      Node C (Follower)
  Log: [(1, SET x=42)]   Log: []                Log: []
       ^ uncommitted

STEP 2: Leader sends AppendEntries RPC to all followers.

  Node A ---- AppendEntries(term=1, entry="SET x=42") ----> Node B
  Node A ---- AppendEntries(term=1, entry="SET x=42") ----> Node C

STEP 3: Followers append to their logs and respond with success.

  Node A (LEADER)        Node B (Follower)      Node C (Follower)
  Log: [(1, SET x=42)]   Log: [(1, SET x=42)]  Log: [(1, SET x=42)]
       ^ uncommitted           ^ uncommitted         ^ uncommitted

  Node B ---- ACK -----> Node A
  Node C ---- ACK -----> Node A

STEP 4: Leader receives ACK from majority (A + B = 2/3 or A + C = 2/3).
         Entry is now COMMITTED. Leader applies to state machine and
         responds to client.

  Node A (LEADER)        Node B (Follower)      Node C (Follower)
  Log: [(1, SET x=42)]   Log: [(1, SET x=42)]  Log: [(1, SET x=42)]
       ^ COMMITTED             ^ committed on        ^ committed on
                                 next heartbeat        next heartbeat

  Leader ----> Client: "OK, x = 42 is committed"

STEP 5: On next heartbeat, leader notifies followers of the new commit index.
         Followers apply committed entries to their state machines.
```

**Split-Brain** is the most dangerous failure mode in a distributed cluster. It occurs when a network partition divides the cluster into two or more groups, each of which believes it is the authoritative group. If both sides accept writes, the data diverges and reconciliation becomes extremely difficult (or impossible without data loss).

Prevention mechanisms include:

- **Quorum**: Require a majority of nodes (N/2 + 1) to agree before any decision is made. In a 5-node cluster, you need at least 3 nodes to form a quorum. A network partition cannot create two groups that both have a majority, so at most one side can make progress.
- **Fencing (STONITH)**: "Shoot The Other Node In The Head" -- when a node is suspected of being partitioned, physically shut it down (via IPMI, cloud API, or power management) before allowing another node to take over. This prevents the old leader from continuing to accept writes.

**etcd / ZooKeeper / Consul** are distributed coordination services that provide strongly consistent key-value storage, service discovery, leader election, and distributed locking. They are the "kernel" of many distributed systems:

- **etcd**: Uses Raft consensus. Powers Kubernetes (stores all cluster state). Simple key-value API with watch capabilities.
- **ZooKeeper**: Uses ZAB (ZooKeeper Atomic Broadcast). Powers Kafka (older versions), Hadoop, and HBase. Hierarchical namespace (like a filesystem). Being gradually replaced by Raft-based alternatives.
- **Consul**: Uses Raft. Provides service mesh capabilities alongside key-value storage. Includes health checking and DNS-based service discovery out of the box.

> **Key Takeaway**: Consensus is fundamentally about turning a quorum of fallible machines into a single source of truth. The recurring theme -- in Raft's "majority of votes," in quorum writes, and in split-brain prevention -- is that **a majority can never exist on both sides of a partition**, so at most one side ever makes progress. When you reach for etcd, ZooKeeper, or Consul, you are renting that hard-won guarantee instead of building it yourself; the cardinal sin is putting consensus-critical state behind a system that has no quorum and can silently split-brain.

### Service Communication Patterns

**Synchronous Communication** (HTTP REST, gRPC) follows the request-response pattern. The caller sends a request and blocks until it receives a response. This is simple to reason about and ideal for user-facing requests that need an immediate response (e.g., "show me my profile"). The downsides are temporal coupling (if the downstream service is down, the caller fails), latency accumulation (each hop adds latency), and cascading failure risk (one slow dependency can exhaust the caller's thread pool, causing it to fail, which cascades to its callers).

**Asynchronous Communication** (message brokers like Kafka, RabbitMQ, SQS) decouples services in time. The producer publishes a message and immediately continues. The consumer processes it whenever it is ready. This provides natural retry semantics (failed messages can be redelivered), load leveling (bursts of messages are buffered), and fault isolation (a consumer being down does not affect the producer). The trade-off is increased complexity: you need to reason about eventual consistency, message ordering, idempotency, and dead letter queues.

**Service Discovery** is how services find each other in a dynamic environment where instances come and go:

- **Client-Side Discovery**: The client queries a service registry (Consul, Eureka) to get a list of available instances, then selects one using its own load-balancing logic. More flexible but puts complexity in the client.
- **Server-Side Discovery**: The client sends requests to a load balancer or DNS name, which queries the registry and routes the request. Kubernetes DNS is the canonical example: a Service named `user-service` is reachable at `user-service.default.svc.cluster.local`. Simpler for clients but adds a hop.

**Circuit Breaker** is a stability pattern that prevents a service from repeatedly calling a failing dependency. It has three states:

1. **Closed** (normal): Requests pass through. Failures are counted. If the failure count exceeds a threshold within a time window, the circuit trips to Open.
2. **Open**: All requests fail immediately without calling the dependency. This gives the dependency time to recover. After a configurable timeout, the circuit transitions to Half-Open.
3. **Half-Open**: A limited number of test requests are allowed through. If they succeed, the circuit closes (back to normal). If they fail, the circuit re-opens.

Here is a complete circuit breaker implementation in Python:

```python
import time
import threading
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation, requests flow through
    OPEN = "open"           # Failing fast, no requests to dependency
    HALF_OPEN = "half_open" # Testing if dependency has recovered


class CircuitBreakerError(Exception):
    """Raised when the circuit is open and the request is rejected."""
    pass


class CircuitBreaker:
    """
    A circuit breaker that wraps calls to an external dependency.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

        @breaker
        def call_payment_service(order_id):
            response = requests.post(f"https://payments.internal/charge/{order_id}")
            response.raise_for_status()
            return response.json()

        try:
            result = call_payment_service("order_123")
        except CircuitBreakerError:
            # Circuit is open -- return a fallback or cached response
            result = {"status": "pending", "message": "Payment processing delayed"}
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        expected_exceptions: tuple = (Exception,),
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    logger.info("Circuit transitioning from OPEN to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
            return self._state

    def _handle_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    logger.info("Circuit transitioning from HALF_OPEN to CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset failure count on success

    def _handle_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning("Circuit transitioning from HALF_OPEN to OPEN (test request failed)")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit transitioning from CLOSED to OPEN "
                    f"(failures: {self._failure_count}/{self.failure_threshold})"
                )
                self._state = CircuitState.OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit is OPEN. Calls blocked for {self.recovery_timeout}s."
            )

        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerError("Circuit is HALF_OPEN, max test calls reached.")
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._handle_success()
            return result
        except self.expected_exceptions as e:
            self._handle_failure()
            raise

    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

payment_breaker = CircuitBreaker(
    failure_threshold=5,       # Open after 5 consecutive failures
    recovery_timeout=30.0,     # Wait 30 seconds before testing again
    half_open_max_calls=3,     # Allow 3 test requests in half-open state
    expected_exceptions=(ConnectionError, TimeoutError),
)


@payment_breaker
def charge_customer(customer_id: str, amount: float) -> dict:
    """Calls the external payment service."""
    import requests
    response = requests.post(
        "https://payments.internal/charge",
        json={"customer_id": customer_id, "amount": amount},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()


def process_order(order_id: str, customer_id: str, amount: float):
    """Business logic that uses the circuit breaker."""
    try:
        result = charge_customer(customer_id, amount)
        return {"status": "charged", "transaction_id": result["id"]}
    except CircuitBreakerError:
        # Fallback: queue for later processing
        logger.warning(f"Payment service unavailable, queuing order {order_id}")
        # queue_for_retry(order_id, customer_id, amount)
        return {"status": "pending", "message": "Payment will be processed shortly"}
    except Exception as e:
        logger.error(f"Payment failed for order {order_id}: {e}")
        return {"status": "failed", "error": str(e)}
```

The classes and example functions above are pure definitions, so they produce nothing on import. The behavior worth seeing is the state machine *tripping*. Here is a small driver that forces five failures and then one more call, with logging turned on:

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0,
                         expected_exceptions=(ConnectionError,))

@breaker
def flaky():
    raise ConnectionError("dependency down")

for i in range(7):
    try:
        flaky()
    except CircuitBreakerError as e:
        print(f"call {i}: BLOCKED -- {e}")
    except ConnectionError:
        print(f"call {i}: reached dependency, failed")
```

Running this prints something like:

```text
call 0: reached dependency, failed
call 1: reached dependency, failed
call 2: reached dependency, failed
call 3: reached dependency, failed
WARNING Circuit transitioning from CLOSED to OPEN (failures: 5/5)
call 4: reached dependency, failed
call 5: BLOCKED -- Circuit is OPEN. Calls blocked for 30.0s.
call 6: BLOCKED -- Circuit is OPEN. Calls blocked for 30.0s.
```

**How to read this output:** Calls 0-4 actually reach the (failing) dependency and increment `_failure_count`. The fifth failure hits the threshold, so `_handle_failure` flips the state to OPEN and logs the transition. From that moment, calls 5 and 6 never touch the dependency at all -- `call()` sees `CircuitState.OPEN` and raises `CircuitBreakerError` immediately. That instantaneous rejection is the entire point: instead of 1000 callers each waiting 5 seconds on a `timeout=5.0` that will fail anyway, they fail in microseconds and run their fallback. This is what stops one sick dependency from exhausting every caller's thread pool and cascading the outage upstream -- the exact scenario interviewers probe when they ask "what happens when your payment provider goes down?"

**Common pitfall:** A circuit breaker with no fallback path just converts slow failures into fast failures -- users still see errors. The value comes from pairing OPEN with a degraded response (cached data, "queued for later," a default), as `process_order` does. Also note this breaker counts *consecutive* failures and resets on any success; a high-traffic service usually wants a rolling failure-*rate* window instead, so a steady trickle of errors among mostly-good traffic still trips the circuit.

**Retry with Exponential Backoff + Jitter** prevents overwhelming a recovering service with a flood of retries. The formula is:

```
retry_delay = min(base_delay * 2^attempt + random(0, jitter), max_delay)
```

The exponential backoff spaces out retries (1s, 2s, 4s, 8s, ...) while the random jitter prevents the "thundering herd" problem where many clients retry at exactly the same time. Always set a maximum delay cap and a maximum retry count. Only retry idempotent operations (operations that produce the same result when executed multiple times).

A quick simulation makes the cap and the jitter visible:

```python
import random
base_delay, jitter, max_delay = 1.0, 0.5, 10.0
for attempt in range(7):
    delay = min(base_delay * 2 ** attempt + random.uniform(0, jitter), max_delay)
    print(f"attempt {attempt}: {delay:.2f}s")
```

Running this prints something like (the jitter is random, so the fractional parts differ on every run):

```text
attempt 0: 1.31s
attempt 1: 2.07s
attempt 2: 4.42s
attempt 3: 8.19s
attempt 4: 10.00s
attempt 5: 10.00s
attempt 6: 10.00s
```

**How to read this output:** The integer part doubles each attempt (1, 2, 4, 8) while the random fraction added on top means two clients that failed at the same instant will *not* retry at the same instant -- that desynchronization is what breaks the thundering herd. From attempt 4 onward the raw value (16s, 32s, ...) exceeds `max_delay`, so `min()` clamps it to 10s; without that cap a few unlucky retries would back off for minutes and look like a hang. In production this loop also needs a retry *count* limit and should only wrap idempotent calls -- retrying a non-idempotent `POST /charge` after a timeout can double-charge a customer.

**Timeout Budgets** propagate a remaining time budget through a chain of service calls. If an upstream API gateway sets a 5-second timeout for a request, and the first internal service call takes 2 seconds, the next service call should be given at most 3 seconds. This prevents wasted work: there is no point in a downstream service spending 10 seconds computing a result if the upstream caller has already timed out after 5 seconds. Timeout budgets are typically propagated via HTTP headers (e.g., `grpc-timeout` in gRPC).

> **Key Takeaway**: Synchronous calls are simple but couple services in time; asynchronous messaging buys decoupling at the cost of eventual-consistency complexity. Whichever you choose, every remote call needs the resilience trio -- a **timeout** (never wait forever), **bounded retries with jittered backoff** (recover from blips without a thundering herd), and a **circuit breaker** (stop hammering a dependency that is already down). Together they convert slow, cascading failures into fast, contained ones, which is the difference between one degraded service and a full site outage.

### Observability (Three Pillars)

Observability is the ability to understand the internal state of a system by examining its external outputs. In a distributed system with dozens of services, observability is not optional -- it is the only way to debug production issues. The three pillars are logs, metrics, and traces.

**Logs** answer "what happened." Each log entry records a discrete event: a request received, a query executed, an error encountered. Modern systems use structured logging (JSON format) rather than free-text logs, because structured logs can be parsed, searched, and aggregated programmatically. Every log entry should include a **correlation ID** (also called a request ID or trace ID) that ties together all log entries across all services for a single user request. Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) allow filtering by severity. Logs are aggregated in centralized systems like the ELK stack (Elasticsearch for storage and search, Logstash for ingestion and transformation, Kibana for visualization) or Grafana Loki (lightweight, integrates with Grafana).

**Metrics** answer "how much" and "how often." They are numeric measurements collected over time. There are three fundamental metric types:

- **Counters**: Monotonically increasing values (total requests served, total errors). You derive rates from counters (requests per second = counter delta / time delta).
- **Gauges**: Point-in-time values that can go up or down (current number of active connections, memory usage, queue depth).
- **Histograms**: Record the distribution of values (request latency). They let you compute percentiles (p50, p95, p99) which are far more useful than averages for understanding user experience.

Prometheus + Grafana is the standard open-source metrics stack. Two frameworks guide what to measure:

- **RED Method** (for request-driven services): Rate (requests/sec), Errors (errors/sec), Duration (latency distribution).
- **USE Method** (for resources like CPU, memory, disk): Utilization (% time busy), Saturation (queue depth), Errors (error count).

**Traces** answer "what was the request's journey across services." Distributed tracing (using OpenTelemetry, the industry standard) assigns a unique **Trace ID** to each incoming request. As the request flows through services, each service creates a **Span** recording its operation name, start/end time, status, and metadata. The spans form a tree that shows the entire request flow, including parallel calls, retries, and which service introduced the most latency. Traces are visualized in tools like Jaeger, Zipkin, Datadog, or Honeycomb.

**SLI/SLO/SLA** formalize reliability commitments:

- **SLI (Service Level Indicator)**: A concrete metric that measures service quality. Example: "the proportion of requests that complete in under 200ms" or "the proportion of requests that return a non-5xx status code."
- **SLO (Service Level Objective)**: A target value for an SLI. Example: "99.9% of requests should complete in under 200ms." SLOs are internal goals that guide engineering priorities.
- **SLA (Service Level Agreement)**: A contractual commitment with consequences (typically financial) for failing to meet it. Example: "If uptime drops below 99.95% in a calendar month, the customer receives a 10% service credit." SLAs are typically less aggressive than SLOs (your SLO might be 99.99% while your SLA promises 99.9%).
- **Error Budgets**: If your SLO is 99.9% availability, your error budget is 0.1% -- roughly 43 minutes of downtime per month. As long as you have error budget remaining, you can take risks (deploy new features, run experiments). When the budget is exhausted, the team focuses exclusively on reliability improvements. This creates a healthy tension between velocity and reliability.

> **Key Takeaway**: Observability is not about installing tools -- it is about building a culture where every service emits structured logs with correlation IDs, exposes standard metrics (RED/USE), and participates in distributed tracing. Without all three pillars working together, debugging a production incident across 50 microservices is like finding a needle in a haystack while blindfolded.
