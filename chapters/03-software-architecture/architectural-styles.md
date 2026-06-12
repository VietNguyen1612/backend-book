[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 3.3 Architectural Styles

The design patterns of the previous section organize code within a process; architectural styles organize the system itself. An architectural style is a high-level strategy for deciding what gets deployed together, what communicates over a network, and where the data lives -- and that choice has far-reaching consequences for development workflow, deployment, scaling, and team organization. It is also where the most expensive mistakes in backend engineering are made. The team that splits a young product into twelve services inherits distributed-systems failure modes -- partial failures, lost messages, data that is consistent in one service and stale in another -- before it has the operational maturity to handle them. The team that lets a monolith grow without internal boundaries ends up with a system nobody can change safely. Most production incidents that look like bugs are, at root, consequences of an architectural style applied without understanding its trade-offs.

By the end of this section you should be able to answer the questions that recur in every architecture review: When should a monolith be split, and how do you keep one healthy until then? What does it actually cost to own microservices, and how do services share data without sharing a database? How do you keep a business operation consistent when it spans services that cannot share a transaction? Where does Domain-Driven Design pay for itself, and where is it ceremony? And which workloads genuinely fit serverless?

We proceed roughly in the order a system evolves. We start with the **Monolith** -- the right default -- and the discipline that keeps it modular. We then examine **Microservices**: their characteristics, data ownership rules, communication styles, and migration patterns. **Event-Driven Architecture** covers the asynchronous backbone that loosely couples services, including event sourcing and CQRS. **Domain-Driven Design** supplies the vocabulary -- bounded contexts, aggregates, value objects -- for drawing the boundaries all of these styles depend on. **Integration & Deployment Patterns** then addresses how clients reach a fleet of services and how services find each other; **Distributed Transactions & Consistency** confronts the hardest consequence of splitting data across services; and **Serverless & FaaS** closes with the style that pushes operational outsourcing to its limit.

## Monolith

We begin with the style every system starts as, because how well you structure a monolith determines both how long it stays pleasant to work in and how cleanly it can be split later if the need ever arises.

A monolith is a single deployment unit where all components run in the same process. Despite its reputation, a monolith is the correct starting point for most projects. The key is to build a **modular monolith**: a single deployment unit that is internally organized into modules with clear boundaries.

### Modular Monolith Structure

```
my_project/
|-- orders/              <-- Module: Orders
|   |-- models.py
|   |-- services.py
|   |-- api.py
|   |-- events.py        <-- Publishes domain events
|   |-- interfaces.py    <-- Public contracts for other modules
|
|-- inventory/           <-- Module: Inventory
|   |-- models.py
|   |-- services.py
|   |-- api.py
|   |-- listeners.py     <-- Subscribes to events from other modules
|   |-- interfaces.py
|
|-- payments/            <-- Module: Payments
|   |-- models.py
|   |-- services.py
|   |-- api.py
|   |-- listeners.py
|   |-- interfaces.py
|
|-- shared/              <-- Shared kernel (minimal!)
|   |-- events.py
|   |-- value_objects.py
```

Module communication should go through **well-defined interfaces**, not by importing each other's models directly. This discipline means that if you later need to extract a module into a microservice, the boundary is already clear.

```python
# orders/interfaces.py -- public contract
from typing import Protocol


class InventoryChecker(Protocol):
    def is_available(self, product_id: str, quantity: int) -> bool: ...


# orders/services.py -- depends on interface, not on inventory module directly
class OrderService:
    def __init__(self, inventory: InventoryChecker):
        self.inventory = inventory

    def place_order(self, product_id: str, quantity: int) -> str:
        if not self.inventory.is_available(product_id, quantity):
            raise ValueError("Product not available")
        # ... create order
        return "ORD-123"


# inventory/services.py -- implements the interface
class InventoryService:
    def is_available(self, product_id: str, quantity: int) -> bool:
        # ... check database
        return True


# Wiring (at application startup)
inventory_service = InventoryService()
order_service = OrderService(inventory=inventory_service)
```

### Benefits of the Monolith

- **Simple deployment**: one artifact, one process, one server (or a few behind a load balancer)
- **Easier debugging**: a single stack trace tells the whole story, no distributed tracing needed
- **No network overhead**: function calls within the same process are orders of magnitude faster than HTTP/gRPC
- **ACID transactions**: a single database means real transactions across domains (e.g., create order AND deduct inventory in one transaction)
- **Simpler development workflow**: one repository, one CI pipeline, one set of dependencies

### When to Move Away

Move away from a monolith when:

- **Team size** makes coordination costly -- multiple teams stepping on each other's code
- **Independent scaling** is needed -- one module needs 10x the resources of another
- **Technology requirements** differ per component -- one module needs Python, another needs Go
- **Deployment frequency** conflicts -- one team needs to deploy hourly, another is on a weekly cycle
- **Module boundaries** are well-understood and stable (if they are not, you will draw the wrong service boundaries)

### Layered (N-Tier) Architecture

The layered (or n-tier) architecture is the most common way to organize a monolith internally: stack the code into horizontal layers where each layer may only call the one directly beneath it. The canonical stack is **presentation -> business logic -> data access -> database**.

```
+--------------------------------------+
| Presentation  (views, controllers,   |  HTTP request/response, serialization
|                serializers)          |
+------------------+-------------------+
                   | calls down only
+------------------v-------------------+
| Business Logic (services, domain)    |  use cases, rules, orchestration
+------------------+-------------------+
                   |
+------------------v-------------------+
| Data Access   (repositories, ORM)    |  queries, persistence mapping
+------------------+-------------------+
                   |
+------------------v-------------------+
| Database                             |
+--------------------------------------+
```

It is simple, universally understood, and maps directly onto a default Django project (views -> services -> models). Two failure modes recur. First, **layer bypassing** -- a view reaching straight into the ORM and skipping the business-logic layer -- erodes the structure until the layers exist in name only. Second, **anemic pass-through layers** that add ceremony without value (the "lasagna code" anti-pattern). Note the key contrast with Clean/Hexagonal architecture covered in 3.1: in plain layered architecture dependencies point *downward* toward the database, so the business logic depends on the data-access layer; in hexagonal architecture dependencies point *inward* toward the domain, so the domain depends on nothing and infrastructure depends on it. Layered is the simpler default; invert the dependencies when the domain complexity justifies protecting it from infrastructure.

> **Key Takeaway:** Start with a modular monolith. Enforce module boundaries through interfaces and discipline. A well-structured monolith is easier to work with than a poorly-structured set of microservices. You can always extract services later when the need is clear and the boundaries are proven.

---

## Microservices

When the limits described above are real -- teams blocking each other, deploys serialized, components with incompatible scaling needs -- the next step is to make the module boundaries physical. This is a far bigger commitment than it first appears, so we look closely at what microservices demand before they pay off.

Microservices architecture decomposes a system into small, independently deployable services, each owning its own data and organized around a business capability. It is a powerful approach for large organizations but comes with significant operational complexity.

### Characteristics

- **Independently deployable**: each service can be deployed without coordinating with other teams
- **Own their data**: each service has its own database; no shared database across services
- **Organized around business capabilities**: a "Payments" service, not a "Database Access" service
- **Decentralized governance**: each team picks its own technology stack, deployment strategy, and data store
- **Design for failure**: networks are unreliable; every external call can fail; circuit breakers, retries, and timeouts are mandatory

### Data Ownership

Each microservice owns its database. This is a non-negotiable rule. Sharing a database between services creates hidden coupling -- a schema change in one service breaks another.

```
+-------------------+     +-------------------+     +-------------------+
|  Order Service    |     |  Payment Service  |     |  Inventory Svc    |
|                   |     |                   |     |                   |
|  +-------------+  |     |  +-------------+  |     |  +-------------+  |
|  | Orders DB   |  |     |  | Payments DB |  |     |  | Inventory DB|  |
|  | (PostgreSQL)|  |     |  | (PostgreSQL)|  |     |  | (MongoDB)   |  |
|  +-------------+  |     |  +-------------+  |     |  +-------------+  |
+-------------------+     +-------------------+     +-------------------+
         |                         |                         |
         +------------+------------+-------------------------+
                      |
               +------+------+
               | Message Bus |
               | (Kafka)     |
               +-------------+
```

Data duplication across services is **expected and intentional**. The Order Service may store a denormalized copy of the customer name. Consistency between services is **eventual**, not immediate.

### Communication Patterns

- **Synchronous** (HTTP/gRPC): for queries where the caller needs an immediate response. Use for reads and simple lookups. API gateway sits in front for external access.
- **Asynchronous** (events/messages): for commands and notifications where the caller does not need an immediate result. Use for writes that trigger downstream processing.

```python
# Synchronous: Order Service calls Payment Service via HTTP
import httpx


class PaymentClient:
    def __init__(self, base_url: str = "http://payment-service:8000"):
        self.base_url = base_url

    def charge(self, order_id: str, amount: float) -> dict:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{self.base_url}/api/charges",
                json={"order_id": order_id, "amount": amount},
            )
            response.raise_for_status()
            return response.json()


# Asynchronous: Order Service publishes event, Inventory Service subscribes
import json


class EventPublisher:
    def __init__(self, kafka_producer):
        self.producer = kafka_producer

    def publish(self, topic: str, event: dict) -> None:
        self.producer.send(topic, json.dumps(event).encode())


# In Order Service:
def place_order(order_data: dict, publisher: EventPublisher) -> str:
    order_id = save_order(order_data)
    publisher.publish("order-events", {
        "type": "OrderPlaced",
        "order_id": order_id,
        "items": order_data["items"],
    })
    return order_id


# In Inventory Service (consumer):
def handle_order_event(event: dict) -> None:
    if event["type"] == "OrderPlaced":
        for item in event["items"]:
            reserve_stock(item["product_id"], item["quantity"])
```

### Challenges

Microservices introduce a class of problems that do not exist in monoliths:

- **Distributed transactions**: no single database transaction spans services (solved by the Saga pattern)
- **Data consistency**: eventual consistency requires careful design and monitoring
- **Operational complexity**: logging, tracing, monitoring, deployment pipelines -- all multiplied by the number of services
- **Debugging**: a request touches five services; you need distributed tracing (Jaeger, Zipkin)
- **Testing**: unit tests are easy, but integration tests across services require contract testing (Pact)
- **Service discovery**: services need to find each other (Consul, Kubernetes DNS)

### Saga Pattern

When a business operation spans multiple services, you cannot use a single database transaction. The Saga pattern replaces one distributed transaction with a sequence of local transactions, each with a compensating action (undo) in case of failure.

```
Saga: Place Order

Step 1: Order Service     -- Create order (status: pending)
Step 2: Payment Service   -- Charge customer
Step 3: Inventory Service -- Reserve stock
Step 4: Order Service     -- Confirm order (status: confirmed)

If Step 3 fails:
  Compensate Step 2: Payment Service -- Refund customer
  Compensate Step 1: Order Service   -- Cancel order
```

Two coordination styles:

- **Orchestration**: a central coordinator (saga orchestrator) tells each service what to do. Easier to understand, single point of control, but the orchestrator can become a bottleneck.
- **Choreography**: each service listens for events and knows what to do next. More decoupled, but harder to trace and understand the full workflow.

```python
# Orchestration-based saga
from dataclasses import dataclass
from enum import Enum


class SagaStep(Enum):
    CREATE_ORDER = "create_order"
    CHARGE_PAYMENT = "charge_payment"
    RESERVE_STOCK = "reserve_stock"
    CONFIRM_ORDER = "confirm_order"


@dataclass
class SagaState:
    order_id: str
    current_step: SagaStep
    completed_steps: list[SagaStep]
    failed: bool = False


class PlaceOrderSaga:
    """Orchestrator that coordinates the saga."""

    def __init__(self, order_svc, payment_svc, inventory_svc):
        self.order_svc = order_svc
        self.payment_svc = payment_svc
        self.inventory_svc = inventory_svc

    def execute(self, order_data: dict) -> str:
        state = SagaState(
            order_id="",
            current_step=SagaStep.CREATE_ORDER,
            completed_steps=[],
        )

        try:
            # Step 1
            state.order_id = self.order_svc.create(order_data)
            state.completed_steps.append(SagaStep.CREATE_ORDER)

            # Step 2
            self.payment_svc.charge(state.order_id, order_data["total"])
            state.completed_steps.append(SagaStep.CHARGE_PAYMENT)

            # Step 3
            self.inventory_svc.reserve(order_data["items"])
            state.completed_steps.append(SagaStep.RESERVE_STOCK)

            # Step 4
            self.order_svc.confirm(state.order_id)
            state.completed_steps.append(SagaStep.CONFIRM_ORDER)

            return state.order_id

        except Exception as e:
            self._compensate(state)
            raise

    def _compensate(self, state: SagaState) -> None:
        """Undo completed steps in reverse order."""
        for step in reversed(state.completed_steps):
            match step:
                case SagaStep.CONFIRM_ORDER:
                    self.order_svc.cancel(state.order_id)
                case SagaStep.RESERVE_STOCK:
                    self.inventory_svc.release(state.order_id)
                case SagaStep.CHARGE_PAYMENT:
                    self.payment_svc.refund(state.order_id)
                case SagaStep.CREATE_ORDER:
                    self.order_svc.cancel(state.order_id)
```

### Strangler Fig Pattern

When migrating from a monolith to microservices, never do a big-bang rewrite. The Strangler Fig pattern incrementally replaces monolith functionality with new services:

```
Phase 1: All traffic goes to monolith
+--------+     +-----------+
| Client | --> | Monolith  |
+--------+     +-----------+

Phase 2: Proxy routes some traffic to new service
+--------+     +-------+     +-----------+
| Client | --> | Proxy | --> | Monolith  |  (most routes)
+--------+     +-------+ --> +-----------+
                    |
                    +------> +-----------+
                             | Orders    |  (/api/orders only)
                             | Service   |
                             +-----------+

Phase 3: Gradually move all functionality
+--------+     +-------+     +-----------+
| Client | --> | Proxy | --> | Orders    |
+--------+     +-------+ --> +-----------+
                    | -----> | Payments  |
                    | -----> | Inventory |
                    |        +-----------+
                    +------> +-----------+
                             | Monolith  |  (legacy routes only)
                             +-----------+

Phase 4: Monolith is empty and can be decommissioned
```

Route requests at the proxy/API gateway level. Both the old and new systems run simultaneously. Gradually move functionality, one bounded context at a time. This reduces risk because you can always fall back to the monolith for any given route.

### Conway's Law

> "Any organization that designs a system will produce a design whose structure is a copy of the organization's communication structure." -- Melvin Conway, 1968

Conway's Law observes that software architecture inevitably mirrors the communication structure of the teams that build it. Three teams will, left to their own devices, produce three components with the seams falling exactly where the team boundaries are -- because the cross-team interfaces are expensive to change while the within-team code is cheap. This is why microservice boundaries that cut across team boundaries produce a distributed monolith: every feature requires coordinating multiple teams, and the chatty coupling between services reflects the constant cross-team negotiation.

The practical corollary is the **Inverse Conway Maneuver**: instead of fighting the law, *deliberately structure your teams* to produce the architecture you want. If you want three independently-deployable services owned by three autonomous teams, organize three small, long-lived teams each owning one bounded context end-to-end (the "two-pizza team" / stream-aligned team idea). Align team boundaries with service boundaries with bounded-context boundaries, and the architecture, the org chart, and the domain model all reinforce each other. Misalign them and you will spend your time on integration meetings.

### When NOT to Use Microservices

Microservices are an answer to *organizational* scaling problems, and adopting them without that problem is one of the most expensive mistakes in backend engineering. Treat the following as a checklist of reasons to stay with a (modular) monolith:

- **Small team** -- with fewer than roughly 10-15 engineers, the operational overhead (separate pipelines, observability, on-call per service) costs more than the coordination it saves.
- **Unclear or unstable domain boundaries** -- if you do not yet understand the bounded contexts, you *will* draw the service boundaries in the wrong place, and moving a boundary across services is vastly harder than moving it inside a monolith.
- **Strong consistency requirements** -- if your core flows need ACID transactions across what would become multiple services, you are signing up for the full complexity of sagas and eventual consistency for a guarantee a single database gives you for free.
- **Limited DevOps / platform maturity** -- microservices demand containerization, CI/CD per service, centralized logging, distributed tracing, and service discovery *before* they pay off. Without that platform, you get the distribution tax and none of the benefits.
- **Early-stage product** -- when the product is still finding fit, the requirement is to change direction cheaply; a monolith refactors far more easily than a fleet of services with versioned contracts between them.

If several of these apply, the right move is a modular monolith with clean internal boundaries -- which keeps the option to extract services later, once the boundaries are proven and the team has grown.

### Service Mesh

As the number of services grows, every service ends up re-implementing the same cross-cutting network concerns: mutual TLS, retries, timeouts, circuit breaking, load balancing, and telemetry. A **service mesh** extracts these into a **sidecar proxy** (typically Envoy) deployed alongside each service instance, so the application code makes a plain localhost call and the proxy handles the reliability and security mechanics. The proxies form the *data plane*; a central *control plane* (Istio, Linkerd) configures them with policy.

```
+-------------------+                 +-------------------+
|  Order Service    |                 | Payment Service   |
|  +-------------+  |   mTLS, retry   |  +-------------+  |
|  | app code    |  |   timeout, LB   |  | app code    |  |
|  +------+------+  |                 |  +------+------+  |
|         |         |                 |         |         |
|  +------v------+  |  <===========>  |  +------v------+  |
|  | sidecar     |  |   data plane    |  | sidecar     |  |
|  | proxy(Envoy)|  |                 |  | proxy(Envoy)|  |
|  +-------------+  |                 |  +-------------+  |
+-------------------+                 +-------------------+
          ^                                     ^
          |          control plane              |
          +----------(Istio / Linkerd)----------+
              policy, mTLS certs, telemetry
```

The mesh is the network-level enforcement of bulkheads, circuit breakers, and retries from the reliability patterns -- but applied uniformly without touching application code, and consistently across services written in different languages. The cost is real operational complexity (the mesh itself must be run and debugged) plus a small per-hop latency from the extra proxy, so it earns its place only once you have enough services that consistent, language-agnostic networking policy is worth the overhead.

### Distributed Tracing

In a monolith, a single stack trace explains a request. Once a request fans out across five services, you need **distributed tracing** to see the whole path. A unique **trace ID** is generated at the edge and propagated through every downstream call (via headers like W3C `traceparent`); each service records **spans** -- timed segments with parent/child relationships -- tagged with that trace ID. A tracing backend (Jaeger, Zipkin, or an OpenTelemetry-compatible vendor) stitches the spans into a single timeline showing exactly where the latency went and which hop failed.

```
trace_id = abc123   (one request across three services)

API Gateway  |==================================== 240ms ====|
  Order Svc    |======================= 180ms =====|
    DB query     |==== 40ms ====|
    Payment Svc      |========= 90ms =========|
      Stripe call      |===== 70ms =====|
```

OpenTelemetry (OTel) is now the vendor-neutral standard for generating and exporting traces (as well as metrics and logs), which is why most new systems instrument with OTel SDKs and export to whichever backend they prefer. Tracing is non-negotiable for microservices: without it, debugging a slow or failing request that touches several services is guesswork. The two practical requirements are *context propagation* (every service must forward the trace headers, including across async message boundaries) and *sampling* (tracing 100% of high-volume traffic is expensive, so you sample a representative fraction while keeping all error traces).

> **Key Takeaway:** Microservices are a tool for organizational scaling, not a default architecture. They trade development simplicity for deployment independence. Each service owns its data, communicates through well-defined APIs and events, and is designed for failure. Use the Saga pattern for distributed transactions and the Strangler Fig pattern for migration. Do not adopt microservices until you have the team size, operational maturity, and clear bounded contexts to justify the complexity.

---

## Event-Driven Architecture

The previous section showed that asynchronous, event-based communication is what keeps microservices loosely coupled. Taken seriously, that idea becomes an architectural style in its own right -- one that applies just as well inside a modular monolith as across a service fleet.

Event-Driven Architecture (EDA) is an architectural style where the flow of the program is determined by events -- significant changes in state. Components produce and consume events, leading to loosely coupled systems that can react to changes in real time.

### Event Sourcing

Instead of storing only the current state of an entity, Event Sourcing stores the complete sequence of state-changing events. The current state is derived by replaying all events from the beginning (or from a snapshot).

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    data: dict
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 0


class EventStore:
    """Append-only store for domain events."""
    def __init__(self):
        self._events: list[DomainEvent] = []

    def append(self, event: DomainEvent) -> None:
        self._events.append(event)

    def get_events(self, aggregate_id: str) -> list[DomainEvent]:
        return [e for e in self._events if e.aggregate_id == aggregate_id]


class BankAccount:
    """Aggregate that rebuilds state from events."""
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.balance: float = 0.0
        self.is_open: bool = False
        self._pending_events: list[DomainEvent] = []
        self._version: int = 0

    # ---- Commands produce events ----

    def open(self, initial_deposit: float) -> None:
        if self.is_open:
            raise ValueError("Account already open")
        self._apply(DomainEvent(
            event_type="AccountOpened",
            aggregate_id=self.account_id,
            data={"initial_deposit": initial_deposit},
        ))

    def deposit(self, amount: float) -> None:
        if not self.is_open:
            raise ValueError("Account not open")
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self._apply(DomainEvent(
            event_type="MoneyDeposited",
            aggregate_id=self.account_id,
            data={"amount": amount},
        ))

    def withdraw(self, amount: float) -> None:
        if not self.is_open:
            raise ValueError("Account not open")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self._apply(DomainEvent(
            event_type="MoneyWithdrawn",
            aggregate_id=self.account_id,
            data={"amount": amount},
        ))

    # ---- Event handlers update state ----

    def _apply(self, event: DomainEvent) -> None:
        self._handle_event(event)
        self._pending_events.append(event)

    def _handle_event(self, event: DomainEvent) -> None:
        match event.event_type:
            case "AccountOpened":
                self.is_open = True
                self.balance = event.data["initial_deposit"]
            case "MoneyDeposited":
                self.balance += event.data["amount"]
            case "MoneyWithdrawn":
                self.balance -= event.data["amount"]
        self._version += 1

    # ---- Rebuild from event history ----

    @classmethod
    def from_events(cls, account_id: str, events: list[DomainEvent]) -> "BankAccount":
        account = cls(account_id)
        for event in events:
            account._handle_event(event)
        return account


# Usage
store = EventStore()

account = BankAccount("ACC-001")
account.open(initial_deposit=100.0)
account.deposit(50.0)
account.withdraw(30.0)

# Save events
for event in account._pending_events:
    store.append(event)

print(f"Balance: ${account.balance}")  # $120.0

# Rebuild from history (e.g., after restart)
events = store.get_events("ACC-001")
rebuilt = BankAccount.from_events("ACC-001", events)
print(f"Rebuilt balance: ${rebuilt.balance}")  # $120.0

# Complete audit trail
for e in events:
    print(f"  {e.event_type}: {e.data}")
# AccountOpened: {'initial_deposit': 100.0}
# MoneyDeposited: {'amount': 50.0}
# MoneyWithdrawn: {'amount': 30.0}
```

Benefits of Event Sourcing: complete audit trail, ability to reconstruct state at any point in time ("time travel"), natural fit with CQRS (build read models by projecting events). Costs: increased storage, complexity of rebuilding state, event schema evolution.

### Event Types

- **Domain events**: record something that happened within a bounded context (e.g., `OrderPlaced`, `PaymentReceived`). Named in past tense.
- **Integration events**: cross-service communication events. These are published on the message bus for other services to consume.

Event schema evolution is critical for long-lived systems:

- **Adding fields** is backward compatible -- old consumers ignore new fields
- **Removing or renaming fields** is a breaking change -- use versioning (`OrderPlacedV2`)
- **Schema registry** (Confluent Schema Registry) enforces compatibility rules

### Event Bus Options

```
+------------------+-------------------+--------------------+------------------+
| Feature          | Kafka             | RabbitMQ           | AWS EventBridge  |
+------------------+-------------------+--------------------+------------------+
| Model            | Distributed log   | Message queue      | Serverless bus   |
| Ordering         | Per-partition     | Per-queue          | Best-effort      |
| Persistence      | Yes (configurable)| Until consumed     | Limited          |
| Replay           | Yes               | No                 | Via archive      |
| Throughput       | Very high         | High               | Medium           |
| Best for         | Event sourcing,   | Task queues,       | AWS-native,      |
|                  | stream processing | RPC, pub/sub       | low-ops          |
+------------------+-------------------+--------------------+------------------+
```

Dead letter queues (DLQs) are essential: when a consumer fails to process a message after several retries, the message is moved to a DLQ for manual inspection and replay.

### Idempotency

In an event-driven system, events may be delivered **more than once** (at-least-once delivery). Consumers must handle duplicates gracefully.

```python
class IdempotentOrderHandler:
    """Processes each event exactly once using an idempotency key."""

    def __init__(self, processed_events_store: set):
        self._processed = processed_events_store

    def handle(self, event: dict) -> None:
        event_id = event["event_id"]

        # Check if already processed
        if event_id in self._processed:
            print(f"Skipping duplicate event {event_id}")
            return

        # Process the event
        self._do_process(event)

        # Mark as processed
        self._processed.add(event_id)

    def _do_process(self, event: dict) -> None:
        print(f"Processing order {event['order_id']}")


# In production, _processed would be a database table or Redis set
processed = set()
handler = IdempotentOrderHandler(processed)

event = {"event_id": "evt-001", "order_id": "ORD-123", "type": "OrderPlaced"}
handler.handle(event)  # Processing order ORD-123
handler.handle(event)  # Skipping duplicate event evt-001
```

Design every consumer to be idempotent: use idempotency keys, check if the operation has already been performed, and make operations naturally idempotent where possible (e.g., `SET balance = 100` is idempotent; `SET balance = balance + 50` is not).

### Three Flavors of "Event"

"Event-driven" hides three genuinely different patterns, and confusing them causes real design problems. Knowing which one you are using tells you how much data to put in the event and how coupled producer and consumer become.

- **Event notification** -- a thin "something happened" message with little more than an ID (`{"type": "OrderPlaced", "order_id": "123"}`). Consumers that need details *call back* to the source. This gives the loosest coupling (the event reveals almost nothing about the producer's data model) but the most chatter -- every interested consumer makes a follow-up request, and you depend on the source still being reachable.
- **Event-carried state transfer** -- the event carries all the data a consumer needs (`{"type": "OrderPlaced", "order_id": "123", "customer": {...}, "items": [...], "total": 149}`), so consumers never call back. This trades looser runtime coupling (consumers keep working even if the producer is down, and can build their own local read copies) for tighter *schema* coupling (consumers now depend on the event's shape) and larger messages.
- **Event sourcing** -- events are the *source of truth*, not just notifications; current state is derived by replaying them (covered in detail above). This is the most powerful and the most complex of the three.

The common mistake is reaching for event sourcing when all you needed was event notification or state transfer. Most "event-driven microservices" use event-carried state transfer for cross-service integration -- it is the sweet spot that lets a service maintain a local replica of data it does not own.

### Delivery Semantics

A broker can promise one of three delivery guarantees, and the choice dictates how defensive your consumers must be:

- **At-most-once** -- a message is delivered zero or one times; it may be *lost* but never duplicated. Cheap, acceptable only for data where loss is tolerable (metrics samples, low-value telemetry).
- **At-least-once** -- a message is delivered one or more times; it is never lost but may be *duplicated* (a consumer crashes after processing but before acknowledging, so the broker redelivers). This is the practical default for most systems, and it is *why idempotent consumers are mandatory*.
- **Exactly-once** -- delivered and processed precisely once. True exactly-once across a network is generally impossible; what systems actually provide is **effectively-once**: at-least-once delivery plus consumer-side idempotency/deduplication (or transactional features like Kafka's transactions that bundle consume-process-produce atomically). When someone claims "exactly-once," they almost always mean "at-least-once delivery made idempotent."

The takeaway: assume at-least-once, and make every consumer idempotent. Do not design for a free exactly-once guarantee the network cannot give you.

### Eventual Consistency

In a distributed event-driven system, when one service changes data and publishes an event, other services update *some time later* -- there is a window during which different services hold different views of the world. This is **eventual consistency**: given no new updates, all replicas converge to the same value eventually, but not instantly. It is acceptable and even desirable for much of a system -- a search index, an analytics dashboard, a recommendation cache, or a notification can all lag by seconds without harm. It is *not* acceptable where a stale read causes incorrect business outcomes: selling the last unit of inventory twice, or showing a paid invoice as unpaid. For those flows you either keep them inside a single consistency boundary (one aggregate, one transaction) or use a compensation-based workflow (saga/TCC) that explicitly handles the in-between states. The design skill is deciding, per use case, where eventual consistency is fine and where you must pay for stronger guarantees.

### The Outbox Pattern

The hardest reliability problem in event-driven systems is the **dual-write problem**: a handler must both write to its database *and* publish an event, but those are two separate systems with no shared transaction. If the DB commit succeeds and the broker publish then fails (or the process crashes between them), the state changed but no event was emitted -- downstream services never find out, and the data drifts. Publishing first has the opposite failure. The **Outbox pattern** solves this by making the event part of the *same database transaction* as the state change:

```python
def place_order(order_data: dict, conn) -> str:
    with conn.transaction():                       # ONE atomic transaction
        order_id = insert_order(conn, order_data)
        # Write the event to an outbox TABLE in the same transaction
        insert_outbox(conn, {
            "type": "OrderPlaced",
            "order_id": order_id,
            "payload": order_data,
            "published": False,
        })
    return order_id
    # A separate relay process polls the outbox table (or tails the DB's
    # change log via CDC) and publishes unpublished rows to the broker,
    # marking them published only after the broker acknowledges.
```

Because the order row and the outbox row commit atomically, you can never have one without the other. A separate **relay** (a polling worker, or a Change-Data-Capture tool like Debezium tailing the transaction log) reads unpublished outbox rows and pushes them to the broker, marking each published only after the broker acks. The relay publishes at-least-once (it may re-send a row whose ack was lost), which is exactly why consumers must be idempotent. The Outbox is the standard, correct fix whenever you need "change data AND emit an event" reliably.

### Inbox / Deduplication Pattern

The Outbox guarantees an event is published; the **Inbox pattern** is its consumer-side mirror that guarantees an event is *processed* once despite at-least-once redelivery. The consumer records the IDs of messages it has already handled in an inbox/dedup table, and writes that record in the *same transaction* as the side effects of processing. On redelivery, it sees the ID is already present and skips the work.

```python
def handle_event(event: dict, conn) -> None:
    event_id = event["event_id"]
    with conn.transaction():
        if already_processed(conn, event_id):      # check dedup table
            return                                  # idempotent skip
        apply_side_effects(conn, event)            # the actual work
        mark_processed(conn, event_id)             # record in SAME transaction
```

Recording the processed ID atomically with the work is what makes it bulletproof: if the process crashes after the side effects but before committing, the whole transaction rolls back and redelivery reprocesses cleanly; once committed, the ID blocks any duplicate. This is the durable, database-backed version of the in-memory idempotency check shown earlier.

### Dead Letter Queues (in depth)

A consumer cannot retry forever -- a message that fails because of a poison payload (malformed data, a schema it cannot parse, a referenced record that no longer exists) will fail on every redelivery and, without a backstop, blocks the queue (head-of-line blocking) or loops infinitely consuming resources. A **Dead Letter Queue** is where such messages go after exhausting their retry budget: the broker (or consumer) moves the message to a separate DLQ instead of redelivering it endlessly.

The DLQ is not a dumping ground to ignore -- it is an operational signal. A healthy system treats DLQ depth as an alerting metric, because messages landing there mean something is genuinely broken: a deploy that changed a schema, a bug in a consumer, or upstream data corruption. The DLQ workflow is: alert on non-zero depth, inspect the failed messages to find the root cause, fix it, then *replay* the messages back onto the main queue (which is safe precisely because consumers are idempotent). Always capture the failure reason and original metadata when dead-lettering, or you will be debugging blind.

### Ordering and Partitioning

A common false assumption is that a broker delivers messages in the order they were sent. In general it does not -- ordering is only guaranteed **within a single partition or queue**, never globally across a topic that is parallelized for throughput. Kafka, for instance, guarantees order only within one partition, and it routes a message to a partition by hashing a **partition key**. The design lever is choosing that key so that messages which *must* be ordered relative to each other share a partition: keying order events by `order_id` (or per-customer events by `customer_id`) guarantees that all events for one order land on one partition and are therefore processed in order, while different orders spread across partitions for parallelism.

The tension is **ordering vs. throughput vs. hot partitions**. Fewer partitions (or a coarse key) gives stronger ordering but less parallelism; a key with skewed distribution (e.g., one whale customer generating 90% of events) creates a *hot partition* that bottlenecks while others sit idle. Pick the finest-grained key that still keeps causally-related events together -- per-entity (`order_id`) is usually right, per-tenant only if a single tenant's volume cannot overwhelm one partition. And accept that some events simply do not need ordering, in which case you can key them randomly for maximum spread.

> **Key Takeaway:** Event-Driven Architecture enables loose coupling, scalability, and real-time reactivity. Event Sourcing provides a complete audit trail and time-travel capabilities but adds complexity. Always design consumers for idempotency. Choose your event bus based on your needs: Kafka for event sourcing and stream processing, RabbitMQ for traditional task queues, or managed services for low-ops environments.

---

## Domain-Driven Design (DDD)

Every style so far has assumed we know where the boundaries lie -- between modules, between services, between event producers and consumers. Domain-Driven Design is the discipline for finding those boundaries, which is why its vocabulary keeps surfacing in the sections above.

Domain-Driven Design is an approach to software development that focuses on modeling the software after the real-world domain it serves. It was introduced by Eric Evans and is most valuable for **complex domains** where the business rules are the competitive advantage.

### Bounded Context

A Bounded Context is an explicit boundary within which a particular domain model applies. The same real-world concept can have completely different meanings in different bounded contexts. For example, "Customer" in a Billing context has payment methods and invoices, while "Customer" in a Shipping context has addresses and delivery preferences.

```
+-------------------------------------------------------------------+
|                     E-COMMERCE SYSTEM                              |
|                                                                   |
|  +-----------------+  +-----------------+  +-------------------+  |
|  | ORDERING        |  | BILLING         |  | SHIPPING          |  |
|  | Context         |  | Context         |  | Context           |  |
|  |                 |  |                 |  |                   |  |
|  | Customer:       |  | Customer:       |  | Customer:         |  |
|  |   - name        |  |   - billing     |  |   - shipping      |  |
|  |   - cart        |  |     address     |  |     address       |  |
|  |   - preferences |  |   - payment     |  |   - delivery      |  |
|  |                 |  |     methods     |  |     preferences   |  |
|  | Order:          |  |   - credit      |  |   - contact       |  |
|  |   - items       |  |     limit       |  |     phone         |  |
|  |   - status      |  |                 |  |                   |  |
|  |   - total       |  | Invoice:        |  | Shipment:         |  |
|  |                 |  |   - line items  |  |   - tracking #    |  |
|  | Product:        |  |   - due date    |  |   - carrier       |  |
|  |   - name        |  |   - payment     |  |   - weight        |  |
|  |   - description |  |     status      |  |   - dimensions    |  |
|  |   - price       |  |                 |  |                   |  |
|  +-----------------+  +-----------------+  +-------------------+  |
|          |                    |                     |              |
|          +----Integration Events / Anti-Corruption Layer-----+    |
+-------------------------------------------------------------------+
```

Each bounded context has its own models, its own database schema, its own ubiquitous language. The Ordering context does not need to know about invoices. The Shipping context does not need to know about shopping carts.

```python
# ---- Ordering Context ----

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OrderItem:
    product_id: str
    product_name: str
    unit_price: float
    quantity: int

    @property
    def subtotal(self) -> float:
        return self.unit_price * self.quantity


@dataclass
class Order:
    """Order as understood in the Ordering context."""
    id: str
    customer_id: str
    items: list[OrderItem] = field(default_factory=list)
    status: str = "draft"
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total(self) -> float:
        return sum(item.subtotal for item in self.items)

    def place(self) -> None:
        if not self.items:
            raise ValueError("Cannot place empty order")
        self.status = "placed"

    def cancel(self) -> None:
        if self.status not in ("draft", "placed"):
            raise ValueError(f"Cannot cancel order in '{self.status}' status")
        self.status = "cancelled"


# ---- Billing Context ----

@dataclass
class Invoice:
    """Invoice as understood in the Billing context.
    'Customer' here means billing address + payment method."""
    id: str
    order_reference: str  # References ordering context by ID only
    billing_address: str
    line_items: list[dict] = field(default_factory=list)
    total_due: float = 0.0
    payment_status: str = "unpaid"

    def mark_paid(self, payment_reference: str) -> None:
        self.payment_status = "paid"


# ---- Shipping Context ----

@dataclass
class Shipment:
    """Shipment as understood in the Shipping context.
    'Customer' here means shipping address + contact phone."""
    id: str
    order_reference: str  # References ordering context by ID only
    shipping_address: str
    contact_phone: str
    carrier: str = ""
    tracking_number: str = ""
    weight_kg: float = 0.0
    status: str = "pending"

    def dispatch(self, carrier: str, tracking_number: str) -> None:
        self.carrier = carrier
        self.tracking_number = tracking_number
        self.status = "dispatched"
```

Notice that each context has its own `Customer` representation (embedded in the data it needs) and references other contexts by **ID only**, not by importing their models.

---

### Aggregate

An Aggregate is a cluster of domain objects treated as a single unit for data changes. The Aggregate Root is the only entry point -- external objects cannot hold references to internal entities. Consistency is guaranteed within the aggregate boundary. Across aggregates, consistency is eventual.

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass(frozen=True)
class Money:
    """Value object: compared by value, immutable."""
    amount: float
    currency: str

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {self.currency} and {other.currency}")
        return Money(amount=self.amount - other.amount, currency=self.currency)


@dataclass
class OrderLine:
    """Entity within the Order aggregate. Cannot be accessed directly from outside."""
    id: str
    product_id: str
    quantity: int
    unit_price: Money

    @property
    def line_total(self) -> Money:
        return Money(
            amount=self.unit_price.amount * self.quantity,
            currency=self.unit_price.currency,
        )


@dataclass
class Order:
    """
    Aggregate root. All modifications go through this object.
    External code never directly modifies OrderLine.
    """
    id: str
    customer_id: str  # Reference to Customer aggregate by ID only
    _lines: list[OrderLine] = field(default_factory=list)
    status: str = "draft"
    _events: list[dict] = field(default_factory=list)

    def add_item(self, product_id: str, quantity: int, unit_price: Money) -> None:
        """Business rule: max 20 unique items per order."""
        if self.status != "draft":
            raise ValueError("Can only add items to draft orders")
        if len(self._lines) >= 20:
            raise ValueError("Maximum 20 items per order")

        # Check if product already exists
        for line in self._lines:
            if line.product_id == product_id:
                line.quantity += quantity
                return

        self._lines.append(OrderLine(
            id=str(uuid.uuid4()),
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
        ))

    def remove_item(self, product_id: str) -> None:
        if self.status != "draft":
            raise ValueError("Can only remove items from draft orders")
        self._lines = [l for l in self._lines if l.product_id != product_id]

    @property
    def total(self) -> Money:
        if not self._lines:
            return Money(0.0, "USD")
        result = Money(0.0, self._lines[0].unit_price.currency)
        for line in self._lines:
            result = result.add(line.line_total)
        return result

    @property
    def item_count(self) -> int:
        return len(self._lines)

    def place(self) -> None:
        """Transition to placed status. Emits a domain event."""
        if not self._lines:
            raise ValueError("Cannot place empty order")
        if self.status != "draft":
            raise ValueError(f"Cannot place order in '{self.status}' status")

        self.status = "placed"
        self._events.append({
            "type": "OrderPlaced",
            "order_id": self.id,
            "customer_id": self.customer_id,
            "total": self.total.amount,
            "currency": self.total.currency,
            "item_count": self.item_count,
            "timestamp": datetime.now().isoformat(),
        })

    def collect_events(self) -> list[dict]:
        events = self._events.copy()
        self._events.clear()
        return events
```

Key rules for aggregates:

- The Aggregate Root (`Order`) is the only entry point for modifications
- Internal entities (`OrderLine`) are never accessed directly from outside
- Reference other aggregates by **ID only** (`customer_id: str`, not `customer: Customer`)
- Transactional consistency within the aggregate; eventual consistency across aggregates
- Keep aggregates small -- large aggregates cause contention and performance problems

---

### Value Objects

Value Objects are defined by their attributes, not by a unique identity. Two `Money(100, "USD")` objects are equal regardless of where they were created. Value Objects should be immutable.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if len(self.currency) != 3:
            raise ValueError("Currency must be 3-letter ISO code")


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    state: str
    zip_code: str
    country: str

    def format_single_line(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}, {self.country}"


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("Start must be before end")

    def contains(self, date: datetime) -> bool:
        return self.start <= date <= self.end

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days


# Value objects are compared by value
m1 = Money(100.0, "USD")
m2 = Money(100.0, "USD")
print(m1 == m2)  # True -- same value, same object semantically

a1 = Address("123 Main St", "Springfield", "IL", "62704", "US")
a2 = Address("123 Main St", "Springfield", "IL", "62704", "US")
print(a1 == a2)  # True
```

Value Objects are a powerful modeling tool. Use them instead of primitive types whenever a concept has validation rules or is composed of multiple related fields. `Money` instead of `float`, `EmailAddress` instead of `str`, `DateRange` instead of two separate `datetime` fields.

---

### Domain Events

Domain Events record that something meaningful happened in the domain. They are named in the **past tense** (`OrderPlaced`, not `PlaceOrder`) because they describe facts that have already occurred. Domain events are used for communication across aggregates and across bounded contexts.

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    order_id: str = ""
    customer_id: str = ""
    total_amount: float = 0.0
    currency: str = "USD"


@dataclass(frozen=True)
class PaymentReceived(DomainEvent):
    payment_id: str = ""
    order_id: str = ""
    amount: float = 0.0
    method: str = ""


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    order_id: str = ""
    tracking_number: str = ""
    carrier: str = ""


# Domain event handlers in other bounded contexts
class BillingEventHandler:
    def on_order_placed(self, event: OrderPlaced) -> None:
        print(f"[Billing] Creating invoice for order {event.order_id}")
        print(f"  Amount: {event.total_amount} {event.currency}")
        # Create invoice in billing context...


class ShippingEventHandler:
    def on_payment_received(self, event: PaymentReceived) -> None:
        print(f"[Shipping] Preparing shipment for order {event.order_id}")
        # Create shipment in shipping context...


class NotificationEventHandler:
    def on_order_shipped(self, event: OrderShipped) -> None:
        print(f"[Notifications] Sending tracking info for {event.tracking_number}")
        # Send email/SMS...


# A simple in-process dispatcher wires events to their handlers
billing = BillingEventHandler()
shipping = ShippingEventHandler()
notifications = NotificationEventHandler()

billing.on_order_placed(OrderPlaced(order_id="ORD-123", customer_id="CUST-9",
                                    total_amount=149.0, currency="USD"))
shipping.on_payment_received(PaymentReceived(payment_id="PAY-1", order_id="ORD-123",
                                             amount=149.0, method="card"))
notifications.on_order_shipped(OrderShipped(order_id="ORD-123",
                                            tracking_number="1Z999", carrier="UPS"))
```

Running this prints:

```text
[Billing] Creating invoice for order ORD-123
  Amount: 149.0 USD
[Shipping] Preparing shipment for order ORD-123
[Notifications] Sending tracking info for 1Z999
```

**How to read this output:** Each line comes from a *different* bounded context reacting to a fact that already happened, without the publisher knowing or caring who is listening. The Ordering context never imports `BillingEventHandler` or `ShippingEventHandler`; it just emits `OrderPlaced` and moves on. That is the whole point of domain events -- adding a new reaction (say, a `FraudCheckHandler` on `OrderPlaced`) means writing one new handler, with zero edits to the order-placing code. The past-tense names (`OrderPlaced`, not `PlaceOrder`) reinforce that handlers receive *facts*, not commands they could refuse. In a real system this dispatcher is replaced by a message bus, but the decoupling guarantee is identical.

> **Common pitfall:** In-process handlers like these run synchronously inside the same transaction, so a slow or failing handler can stall or roll back the original operation. Once you have more than a couple of consumers, publish to a real bus and let each context process the event in its own transaction.

---

### Anti-Corruption Layer

The Anti-Corruption Layer (ACL) translates between your domain model and external systems. It prevents external models (third-party APIs, legacy systems, partner services) from leaking into your clean domain model. This is the Adapter pattern applied at the bounded context boundary.

```python
from dataclasses import dataclass
from typing import Protocol


# ---- Your clean domain model ----

@dataclass
class Product:
    id: str
    name: str
    price_usd: float
    in_stock: bool


class ProductCatalog(Protocol):
    def get_product(self, product_id: str) -> Product | None: ...


# ---- External legacy system has a completely different model ----

class LegacyInventoryAPI:
    """Third-party API with ugly interface and different terminology."""
    def fetch_item_record(self, sku: str) -> dict:
        return {
            "SKU": sku,
            "ITEM_DESC": "  Widget Type-A  ",
            "UNIT_PRC": "19.99",
            "QTY_ON_HAND": "42",
            "STATUS_CD": "A",  # A=Active, D=Discontinued
        }


# ---- Anti-Corruption Layer translates between the two ----

class LegacyProductAdapter:
    """ACL: translates legacy API responses into clean domain objects."""

    STATUS_MAP = {"A": True, "D": False}

    def __init__(self, legacy_api: LegacyInventoryAPI):
        self._api = legacy_api

    def get_product(self, product_id: str) -> Product | None:
        try:
            raw = self._api.fetch_item_record(product_id)
        except Exception:
            return None

        return Product(
            id=raw["SKU"],
            name=raw["ITEM_DESC"].strip(),
            price_usd=float(raw["UNIT_PRC"]),
            in_stock=self.STATUS_MAP.get(raw["STATUS_CD"], False)
                     and int(raw["QTY_ON_HAND"]) > 0,
        )


# Your domain code works with clean Product objects
# and never sees the legacy API's format:
adapter = LegacyProductAdapter(LegacyInventoryAPI())
product = adapter.get_product("WIDGET-001")
print(product)
# Product(id='WIDGET-001', name='Widget Type-A', price_usd=19.99, in_stock=True)
```

The ACL is especially important during migrations: as you move from a legacy system to a new one, the ACL shields your new domain model from the legacy system's quirks.

---

### Strategic DDD: Context Mapping

Context Mapping describes the relationships between bounded contexts. These relationships determine how teams interact and how data flows between contexts.

```
+-------------------+          +-------------------+
|   ORDERING        | Partner  |   BILLING         |
|   Context         |<-------->|   Context         |
|                   |  ship    |                   |
+-------------------+          +-------------------+
        |                              |
        | Customer-                    | Conformist
        | Supplier                     | (uses payment
        | (ordering                    |  gateway's model
        |  dictates)                   |  as-is)
        v                              v
+-------------------+          +-------------------+
|   INVENTORY       |          |   PAYMENT         |
|   Context         |          |   GATEWAY         |
|                   |          |   (External)      |
+-------------------+          +-------------------+
        |
        | Anti-Corruption
        | Layer
        v
+-------------------+
|   LEGACY          |
|   WAREHOUSE       |
|   (External)      |
+-------------------+
```

Key relationship types:

- **Partnership**: two contexts cooperate, teams coordinate closely, shared timeline
- **Shared Kernel**: two contexts share a subset of the model (use sparingly -- it creates coupling)
- **Customer-Supplier**: upstream (supplier) context provides what downstream (customer) context needs; downstream has influence over upstream's priorities
- **Conformist**: downstream context conforms to upstream's model with no ability to influence it (common with external APIs)
- **Anti-Corruption Layer**: downstream context translates upstream's model to protect its own domain
- **Open Host Service**: upstream context provides a well-defined, stable API (e.g., a published REST API or event schema) for multiple downstream consumers

```python
# Example: Shared Kernel -- minimal shared types between contexts
# shared/value_objects.py

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """Shared across Ordering and Billing contexts.
    Changes here affect both contexts -- keep this small!"""
    amount: float
    currency: str


@dataclass(frozen=True)
class CustomerId:
    """Shared identifier -- both contexts agree on what identifies a customer."""
    value: str


# Example: Customer-Supplier -- Ordering publishes events, Inventory consumes
# ordering/events.py (Supplier / Upstream)

@dataclass(frozen=True)
class OrderPlacedEvent:
    """Public event contract. Inventory team can request changes to this schema."""
    order_id: str
    items: list[dict]  # [{"product_id": "...", "quantity": N}]


# inventory/handlers.py (Customer / Downstream)

class OrderPlacedHandler:
    """Inventory context consumes events from Ordering context.
    If the schema does not meet our needs, we request changes from the Ordering team."""
    def handle(self, event: OrderPlacedEvent) -> None:
        for item in event.items:
            self.reserve_stock(item["product_id"], item["quantity"])
```

> **Key Takeaway:** Domain-Driven Design is about modeling software to match the real-world domain. Bounded Contexts define where a model applies. Aggregates enforce consistency boundaries. Value Objects eliminate primitive obsession. Domain Events enable decoupled communication. Anti-Corruption Layers protect your model from external pollution. Context Mapping describes how teams and systems relate. DDD is most valuable for complex domains -- for simple CRUD, it is overkill.

---

## Integration & Deployment Patterns

Once a system is composed of multiple services, a recurring set of structural patterns governs how clients reach those services and how the services find and talk to each other. These patterns keep cross-cutting concerns out of the individual services and out of the clients.

### API Gateway

An API Gateway is a single entry point that sits in front of a fleet of services and handles the concerns that would otherwise be re-implemented by every client and every service: request routing, authentication and authorization, rate limiting, TLS termination, request/response transformation, and sometimes response aggregation. Clients talk to one stable endpoint; the gateway fans out to the right backend services.

```
                +------------------+
                |   API Gateway    |   auth, rate-limit, TLS, routing
   client  ---> |  api.example.com |
                +--------+---------+
                  |      |        |
         +--------+      |        +---------+
         v               v                  v
   +-----------+   +-----------+      +-----------+
   | Order Svc |   | User Svc  |      | Search Svc|
   +-----------+   +-----------+      +-----------+
```

The gateway centralizes cross-cutting policy so individual services stay focused on business logic and never reimplement auth or rate limiting. The danger is the **god gateway**: as it is tempting to add "just a little" routing logic, the gateway accretes business rules and becomes a deployment bottleneck that every team must coordinate through. Keep it thin -- routing and cross-cutting concerns only, never domain logic.

### Backend-for-Frontend (BFF)

A single general-purpose API rarely serves every client well: a mobile app wants small, battery-friendly payloads and few round trips, while a web SPA wants richer data, and a partner integration wants something else again. A **Backend-for-Frontend** is a dedicated gateway/aggregation layer *per client type*, each shaping the underlying services' data to exactly what that client needs.

```
  mobile app --> Mobile BFF  --+
                               |
  web SPA    --> Web BFF    ---+--> [ Order Svc | User Svc | Catalog Svc ]
                               |
  partner    --> Partner BFF --+
```

Each BFF owns the aggregation and trimming for its consumer -- the Mobile BFF might stitch three service calls into one compact response, while the Web BFF returns the full objects. This avoids the "one-size-fits-none" API that bloats mobile payloads to satisfy the web (or vice versa), and lets each frontend team evolve its own BFF without coordinating a shared API. The cost is more components to run; the pattern earns its place when client needs genuinely diverge.

### Sidecar and Ambassador

A **sidecar** is a helper process deployed in the same unit (the same Kubernetes pod) as the main application, sharing its lifecycle and network namespace, to provide a capability the app should not implement itself -- log shipping, configuration sync, secrets rotation, or the service-mesh data-plane proxy. The app stays focused on business logic; the sidecar handles the platform concern alongside it.

An **Ambassador** is a specialized sidecar that proxies the app's *outbound* connections. The application simply talks to `localhost`, and the ambassador handles the messy realities of reaching remote services -- retries, timeouts, TLS, service discovery, circuit breaking. This is especially useful for giving a legacy app modern networking behavior without modifying it, and it is essentially what a mesh sidecar does for egress traffic.

```
+-----------------------------------+
|  Pod                              |
|   +-----------+   +-----------+   |
|   |  App      |-->| Ambassador|---+--> remote DB / external API
|   | (localhost)|  | (egress   |   |    (handles retry, TLS, discovery)
|   +-----------+   |  proxy)   |   |
|                   +-----------+   |
+-----------------------------------+
```

### Anti-Corruption Layer at the Edge

The Anti-Corruption Layer (introduced in DDD for protecting a domain model) appears again as an *integration* pattern at the system edge: a translation layer that normalizes disparate external systems -- a flaky partner API, a legacy mainframe, a third-party with ugly data formats -- into a single consistent internal contract. Each external system gets an adapter that maps its quirks (different field names, encodings, error conventions) onto your clean internal model, so the rest of the system depends only on the normalized contract and never on the foreign system's shape. This is the same idea as the `LegacyProductAdapter` shown in the DDD section, applied at the boundary of the whole system rather than a single bounded context.

### Service Discovery

In a dynamic environment where service instances come and go (autoscaling, deploys, failures), callers cannot rely on hardcoded addresses -- they need a way to find healthy instances at call time. Two models:

- **Client-side discovery** -- the client queries a service registry (Consul, Eureka) to get the current list of healthy instances and picks one itself (doing its own load balancing). More control, but every client needs registry-aware logic.
- **Server-side discovery** -- the client calls a stable virtual address (a load balancer or a Kubernetes `Service` DNS name) and the infrastructure resolves it to a healthy instance. Simpler for the client; the platform owns the routing.

DNS-based server-side discovery (as in Kubernetes Services) is the simplest and most common today -- the client just calls `http://payment-service` and the platform handles the rest. Dedicated registries like Consul add richer health checking, metadata, and cross-datacenter awareness when you need it.

### Aggregator / Scatter-Gather

The Aggregator (scatter-gather) pattern fans a single request out to several services in parallel, then combines their responses into one result -- a product page that needs pricing, inventory, reviews, and recommendations from four services, returned as one payload. The key engineering concerns are *parallelism* (issue the calls concurrently, not sequentially, so total latency is the slowest call rather than the sum), *timeouts* (cap how long you wait for stragglers), and *partial-result handling* (decide whether a missing recommendations response degrades gracefully or fails the whole request). An API Gateway or BFF is often where scatter-gather lives.

```
                 +--> Pricing Svc ----+
   request --> Aggregator --> Inventory Svc --+--> combined response
                 +--> Reviews Svc ----+        (with timeout + partial results)
```

> **Key Takeaway:** Integration patterns keep cross-cutting concerns out of services and clients. An API Gateway centralizes routing and policy (keep it thin); a BFF tailors APIs per client; sidecars and ambassadors offload platform concerns alongside the app; service discovery lets callers find healthy instances; and aggregator/scatter-gather composes responses from many services with timeouts and partial-result handling.

---

## Distributed Transactions & Consistency

When a single business operation must change data owned by multiple services, you cannot wrap it in one database transaction. This section covers the spectrum of options for keeping distributed data consistent. (The Saga pattern, the workhorse here, is covered in detail in the Microservices section above; this section places it alongside its alternatives.)

### Why Not Two-Phase Commit (2PC) Everywhere

Two-Phase Commit is the classic protocol for atomic commits across multiple resources. A **coordinator** runs two phases: a *prepare* phase where it asks every participant "can you commit?" and each votes yes (and locks the relevant data) or no, followed by a *commit* phase where, if all voted yes, the coordinator tells everyone to commit. It does give true atomicity across services -- so why is it avoided?

- **It blocks on coordinator failure.** If the coordinator crashes after participants have voted yes but before sending the commit decision, participants are stuck holding locks, unable to commit or abort until the coordinator recovers -- a fragile single point of failure.
- **It holds locks across the network.** Resources stay locked for the entire duration of the protocol, including network round trips, which destroys throughput under contention.
- **It does not scale and couples availability.** Every participant must be up and responsive for any transaction to complete; the transaction is only as available as the *least* available participant.

2PC is fine *within* a single database or a tightly-coupled environment (it underpins distributed databases internally), but across independently-deployed services it trades away exactly the availability and decoupling that motivated the split. The industry answer is to give up cross-service atomicity and embrace eventual consistency via sagas.

### Saga (Recap in Context)

A saga replaces one distributed ACID transaction with a sequence of *local* transactions, each with a **compensating action** that semantically undoes it if a later step fails -- refund the charge, release the reserved stock, cancel the order. It comes in two coordination styles, **orchestration** (a central coordinator drives the steps -- easier to reason about and trace, single point of logic) and **choreography** (each service reacts to the previous step's event -- more decoupled, harder to follow end to end). The trade-off versus 2PC is explicit: sagas give up atomic isolation (other actors *can* observe the intermediate states) in exchange for availability and decoupling, and the developer must design compensations and tolerate the in-between states. Full code for an orchestration saga appears in the Microservices section.

### TCC (Try-Confirm-Cancel)

TCC is a more structured alternative to the saga for operations that fit a *reservation* model. Each participant exposes three operations:

- **Try** -- reserve the resources tentatively without committing (hold the seat, earmark the inventory, place a hold on the funds).
- **Confirm** -- commit the previously reserved resources (only called if every participant's Try succeeded).
- **Cancel** -- release the reservation (called if any Try failed).

```
Book a trip = flight + hotel + car

Try:     flight.hold()    hotel.hold()    car.hold()
            |                |               |
         all succeeded? --------> yes --> Confirm: flight/hotel/car commit holds
                          |
                          +-----> any failed --> Cancel: release all holds
```

The difference from a plain saga is that TCC resources are *reserved* during Try rather than fully committed, so confirmation is cheap and cancellation just releases a hold rather than reversing a completed action. This fits inventory, seat booking, and fund holds well -- anywhere you can express "tentatively reserve, then either commit or release." The cost is that every participant must implement the three-phase contract and the reservations need timeouts so a crashed orchestrator does not leave resources held forever.

### The Workhorse Primitives

In practice, reliable eventually-consistent workflows are built from three primitives that recur throughout this chapter: **idempotency** (so retries and redeliveries are safe), the **outbox pattern** (so a state change and its event commit atomically), and **retries with backoff** (so transient failures self-heal). A saga or TCC defines the *business* choreography; idempotency + outbox + retries are the *mechanical* guarantees that make each step reliable. Get the mechanics right and the higher-level pattern becomes tractable; skip them and even a correct saga corrupts data under the first duplicate message or partial failure.

> **Key Takeaway:** Avoid 2PC across services -- it blocks on coordinator failure and couples availability. Model cross-service operations as sagas (sequences of local transactions with compensations) or, for reservation-style flows, TCC. Underpin every step with the workhorse primitives -- idempotency, outbox, and bounded retries -- because eventual consistency is only reliable when each local step is itself crash- and duplicate-safe.

---

## Serverless & FaaS

We close with the style that takes the decomposition trend to its endpoint: instead of services you operate, individual functions the platform operates for you. Its economics are attractive, but its constraints are sharp enough that fit matters more here than anywhere else in this section.

Function-as-a-Service (FaaS) -- AWS Lambda, Google Cloud Functions, Azure Functions -- runs your code as short-lived, stateless functions triggered by events (an HTTP request, a queue message, a schedule, a database change), with the platform handling all provisioning and scaling, including scaling **to zero** when idle. You pay per invocation and per millisecond of execution rather than for always-on servers.

### Cold Starts

When a function has been idle (or needs to scale up), the platform must spin up a fresh execution environment -- download the code, start the runtime, run initialization -- before it can serve the request. This **cold start** adds latency to that first invocation, ranging from ~100ms to several seconds depending on runtime and package size (a slim Python function may cold-start in a couple hundred milliseconds; a large JVM function can take seconds). Subsequent requests hitting the warm environment skip this cost. Mitigations include **provisioned concurrency** (keep a pool of environments pre-warmed), minimizing deployment package size and dependencies, and choosing a faster-starting runtime. Cold starts are the headline reason FaaS struggles with latency-sensitive, user-facing paths that see bursty or infrequent traffic.

### Stateless Design

A FaaS function must be **stateless**: any environment can vanish between invocations, the local filesystem is ephemeral, and you have no control over which (if any) warm instance handles the next request. All durable state lives in external backing services -- DynamoDB/a database, S3 for files, Redis for caching/sessions. Handlers should be idempotent, since the platform may retry a failed invocation. This is the Twelve-Factor "stateless processes" rule taken to its extreme, and it is liberating when honored and a constant source of bugs when violated (e.g., caching in a module-level dict that only sometimes persists across the unpredictable warm-instance reuse).

### Limitations

FaaS is not a universal replacement for servers; its constraints are real and shape what fits:

- **Execution time limits** -- functions are capped (AWS Lambda at 15 minutes); long-running jobs do not fit.
- **Payload and resource limits** -- bounded request/response sizes and memory/CPU per invocation.
- **No long-lived connections** -- WebSockets and other persistent connections do not map onto the request-scoped model (they require separate managed services).
- **Database connection exhaustion** -- because the platform may spin up thousands of concurrent function instances, each opening its own database connection, you can blow past a relational database's connection limit almost instantly. The fix is a connection proxy/pooler (RDS Proxy, PgBouncer) or a serverless-native data store.
- **Vendor lock-in** -- triggers, IAM, and the surrounding ecosystem are provider-specific, making migration costly.
- **Debugging and observability complexity** -- no long-running process to attach to; you rely on the platform's logs and distributed tracing.

### When It Fits (and When It Does Not)

FaaS shines for **event processing** (react to a queue/storage/database event), **scheduled tasks** (cron), **webhooks**, **light or spiky APIs**, and **glue code** between managed services -- workloads that are bursty, short, stateless, and benefit from scale-to-zero economics. It is a poor fit for **sustained high-traffic** services (always-on containers are cheaper once utilization is high), **long-running or complex workflows**, **latency-critical** user paths (cold starts), and anything needing persistent connections. The honest framing: FaaS trades operational simplicity and per-use pricing for execution constraints and less control. Use it where those constraints are irrelevant; reach for containers/servers where they bite.

> **Key Takeaway:** Serverless/FaaS runs stateless, event-triggered functions that scale to zero, billing per invocation. Its defining constraints -- cold-start latency, execution-time and payload limits, no persistent connections, and database connection exhaustion under high concurrency -- make it ideal for bursty event processing, scheduled jobs, webhooks, and glue code, and ill-suited to sustained high-traffic, long-running, or latency-critical workloads. Design handlers stateless and idempotent, and protect databases with a connection proxy.

---

## Summary

An architectural style is a bet about where your system's complexity should live, and the styles in this section form a progression rather than a menu. Start with a **modular monolith**: one deployment unit, internally divided into modules that communicate through explicit interfaces and events. Split into **microservices** only when the organizational pressure is real -- teams blocking each other, conflicting deploy cadences, genuinely different scaling needs -- and only when the module boundaries are already proven, because every service split converts in-process calls into network calls and one database transaction into a distributed-consistency problem. **Event-Driven Architecture** is the loose-coupling backbone for either world; its price is designing every consumer for idempotency and accepting eventual consistency, with event sourcing and CQRS as powerful but heavyweight extensions. **Domain-Driven Design** supplies the boundary-finding discipline underneath all of this -- bounded contexts tell you where models (and services) should end, aggregates define consistency boundaries, and anti-corruption layers keep external models from leaking in; reserve the full toolkit for genuinely complex domains. Once services exist, the **integration patterns** (a thin API gateway, BFFs, sidecars, service discovery) keep cross-cutting concerns out of business code, and **distributed transactions** are handled not with 2PC but with sagas or TCC built on idempotency, the outbox pattern, and retries. **Serverless** fits bursty, short, stateless work and little else.

This closes Chapter 3. We have moved from architecture principles, through design patterns, to the system-level styles above -- and every one of those styles ultimately rests on how data is stored, queried, and kept consistent. That is the subject of Chapter 4, which begins with 4.1 Relational Databases (PostgreSQL Focus).

---

*Last reviewed: 2026-06-08*

**Next:** [4.1 Relational Databases (PostgreSQL Focus)](../04-databases-and-data/relational-databases.md)
