[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 3.3 Architectural Styles

Architectural styles are high-level strategies for organizing a system. The choice of architectural style has far-reaching consequences for development workflow, deployment, scaling, and team organization.

### Monolith

A monolith is a single deployment unit where all components run in the same process. Despite its reputation, a monolith is the correct starting point for most projects. The key is to build a **modular monolith**: a single deployment unit that is internally organized into modules with clear boundaries.

#### Modular Monolith Structure

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

#### Benefits of the Monolith

- **Simple deployment**: one artifact, one process, one server (or a few behind a load balancer)
- **Easier debugging**: a single stack trace tells the whole story, no distributed tracing needed
- **No network overhead**: function calls within the same process are orders of magnitude faster than HTTP/gRPC
- **ACID transactions**: a single database means real transactions across domains (e.g., create order AND deduct inventory in one transaction)
- **Simpler development workflow**: one repository, one CI pipeline, one set of dependencies

#### When to Move Away

Move away from a monolith when:

- **Team size** makes coordination costly -- multiple teams stepping on each other's code
- **Independent scaling** is needed -- one module needs 10x the resources of another
- **Technology requirements** differ per component -- one module needs Python, another needs Go
- **Deployment frequency** conflicts -- one team needs to deploy hourly, another is on a weekly cycle
- **Module boundaries** are well-understood and stable (if they are not, you will draw the wrong service boundaries)

> **Key Takeaway:** Start with a modular monolith. Enforce module boundaries through interfaces and discipline. A well-structured monolith is easier to work with than a poorly-structured set of microservices. You can always extract services later when the need is clear and the boundaries are proven.

---

### Microservices

Microservices architecture decomposes a system into small, independently deployable services, each owning its own data and organized around a business capability. It is a powerful approach for large organizations but comes with significant operational complexity.

#### Characteristics

- **Independently deployable**: each service can be deployed without coordinating with other teams
- **Own their data**: each service has its own database; no shared database across services
- **Organized around business capabilities**: a "Payments" service, not a "Database Access" service
- **Decentralized governance**: each team picks its own technology stack, deployment strategy, and data store
- **Design for failure**: networks are unreliable; every external call can fail; circuit breakers, retries, and timeouts are mandatory

#### Data Ownership

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

#### Communication Patterns

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

#### Challenges

Microservices introduce a class of problems that do not exist in monoliths:

- **Distributed transactions**: no single database transaction spans services (solved by the Saga pattern)
- **Data consistency**: eventual consistency requires careful design and monitoring
- **Operational complexity**: logging, tracing, monitoring, deployment pipelines -- all multiplied by the number of services
- **Debugging**: a request touches five services; you need distributed tracing (Jaeger, Zipkin)
- **Testing**: unit tests are easy, but integration tests across services require contract testing (Pact)
- **Service discovery**: services need to find each other (Consul, Kubernetes DNS)

#### Saga Pattern

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

#### Strangler Fig Pattern

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

> **Key Takeaway:** Microservices are a tool for organizational scaling, not a default architecture. They trade development simplicity for deployment independence. Each service owns its data, communicates through well-defined APIs and events, and is designed for failure. Use the Saga pattern for distributed transactions and the Strangler Fig pattern for migration. Do not adopt microservices until you have the team size, operational maturity, and clear bounded contexts to justify the complexity.

---

### Event-Driven Architecture

Event-Driven Architecture (EDA) is an architectural style where the flow of the program is determined by events -- significant changes in state. Components produce and consume events, leading to loosely coupled systems that can react to changes in real time.

#### Event Sourcing

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

#### Event Types

- **Domain events**: record something that happened within a bounded context (e.g., `OrderPlaced`, `PaymentReceived`). Named in past tense.
- **Integration events**: cross-service communication events. These are published on the message bus for other services to consume.

Event schema evolution is critical for long-lived systems:

- **Adding fields** is backward compatible -- old consumers ignore new fields
- **Removing or renaming fields** is a breaking change -- use versioning (`OrderPlacedV2`)
- **Schema registry** (Confluent Schema Registry) enforces compatibility rules

#### Event Bus Options

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

#### Idempotency

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

> **Key Takeaway:** Event-Driven Architecture enables loose coupling, scalability, and real-time reactivity. Event Sourcing provides a complete audit trail and time-travel capabilities but adds complexity. Always design consumers for idempotency. Choose your event bus based on your needs: Kafka for event sourcing and stream processing, RabbitMQ for traditional task queues, or managed services for low-ops environments.

---

### Domain-Driven Design (DDD)

Domain-Driven Design is an approach to software development that focuses on modeling the software after the real-world domain it serves. It was introduced by Eric Evans and is most valuable for **complex domains** where the business rules are the competitive advantage.

#### Bounded Context

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

#### Aggregate

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

#### Value Objects

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

#### Domain Events

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

#### Anti-Corruption Layer

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

#### Strategic DDD: Context Mapping

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
