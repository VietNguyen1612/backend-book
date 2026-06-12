[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 3.2 Design Patterns

Design patterns are reusable solutions to commonly occurring problems in software design. They are not code templates to copy-paste but rather conceptual blueprints that you adapt to your specific situation. The following sections cover the most important patterns, organized by their intent.

### Creational Patterns

Creational patterns abstract the instantiation process, making a system independent of how its objects are created, composed, and represented.

---

#### Factory Method

The Factory Method pattern defines an interface for creating an object but lets subclasses (or, in Python, factory functions) decide which class to instantiate. Use it when the exact type of object to create is determined at runtime or when object creation involves complex logic.

In Python, factory functions are often simpler and more idiomatic than a full class hierarchy.

```python
from dataclasses import dataclass
from typing import Protocol


class Notification(Protocol):
    def send(self, recipient: str, message: str) -> None: ...


@dataclass
class EmailNotification:
    smtp_server: str = "smtp.example.com"

    def send(self, recipient: str, message: str) -> None:
        print(f"Sending email to {recipient} via {self.smtp_server}: {message}")


@dataclass
class SMSNotification:
    api_key: str = "sms-api-key"

    def send(self, recipient: str, message: str) -> None:
        print(f"Sending SMS to {recipient}: {message}")


@dataclass
class PushNotification:
    app_id: str = "my-app"

    def send(self, recipient: str, message: str) -> None:
        print(f"Sending push to {recipient} in {self.app_id}: {message}")


# Factory function -- decides which class to instantiate
def create_notification(channel: str) -> Notification:
    factories: dict[str, type] = {
        "email": EmailNotification,
        "sms": SMSNotification,
        "push": PushNotification,
    }
    notification_class = factories.get(channel)
    if notification_class is None:
        raise ValueError(f"Unknown notification channel: {channel}")
    return notification_class()


# Usage
notifier = create_notification("sms")
notifier.send("+1234567890", "Your order has shipped!")
```

Running this prints:

```text
Sending SMS to +1234567890: Your order has shipped!
```

**How to read this output:** The caller never wrote `SMSNotification()` directly -- it passed the string `"sms"` and got back the right concrete class. That indirection is the whole point: in production, the channel usually comes from config, a database column, or the request body, so the calling code stays the same whether the system adds Slack, webhook, or in-app channels later. Swapping the `factories` dict (or loading it from an entry-point registry) extends behavior without touching `notifier.send(...)`.

> **Common pitfall:** A factory that grows a long `if/elif channel == ...` ladder instead of a lookup table is a classic code smell -- every new type forces an edit to the same function, violating open/closed. The dict-dispatch form above sidesteps that, and raising `ValueError` on an unknown key surfaces typos loudly instead of silently returning `None`.

In a Django project, the Factory Method appears when creating serializers based on request type, instantiating different storage backends based on settings, or building different queryset filters dynamically.

---

#### Abstract Factory

The Abstract Factory pattern provides an interface for creating **families of related objects** without specifying their concrete classes. Use it when your system must work with multiple families of products that are designed to be used together.

```python
from abc import ABC, abstractmethod


# Abstract products
class Button(ABC):
    @abstractmethod
    def render(self) -> str: ...

class TextInput(ABC):
    @abstractmethod
    def render(self) -> str: ...


# Concrete family: Web
class WebButton(Button):
    def render(self) -> str:
        return "<button>Click me</button>"

class WebTextInput(TextInput):
    def render(self) -> str:
        return '<input type="text" />'


# Concrete family: Mobile
class MobileButton(Button):
    def render(self) -> str:
        return "[ Click me ]"

class MobileTextInput(TextInput):
    def render(self) -> str:
        return "[________]"


# Abstract factory
class UIFactory(ABC):
    @abstractmethod
    def create_button(self) -> Button: ...

    @abstractmethod
    def create_text_input(self) -> TextInput: ...


class WebUIFactory(UIFactory):
    def create_button(self) -> Button:
        return WebButton()

    def create_text_input(self) -> TextInput:
        return WebTextInput()


class MobileUIFactory(UIFactory):
    def create_button(self) -> Button:
        return MobileButton()

    def create_text_input(self) -> TextInput:
        return MobileTextInput()


# Client code works with any factory
def build_form(factory: UIFactory) -> str:
    button = factory.create_button()
    text_input = factory.create_text_input()
    return f"Form: {text_input.render()} {button.render()}"


print(build_form(WebUIFactory()))
# Form: <input type="text" /> <button>Click me</button>

print(build_form(MobileUIFactory()))
# Form: [________] [ Click me ]
```

In backend development, this pattern appears when supporting multiple database backends, multiple cloud providers (AWS vs. GCP), or multiple API versions where the components of each version must be consistent.

---

#### Builder

The Builder pattern constructs complex objects step by step, separating the construction process from the representation. This is useful when an object has many optional parameters or when the construction involves multiple steps.

Python offers idiomatic alternatives: dataclasses with defaults, Pydantic models, and method chaining.

```python
from dataclasses import dataclass, field


@dataclass
class QueryBuilder:
    """Builds SQL-like queries step by step."""
    _table: str = ""
    _conditions: list[str] = field(default_factory=list)
    _order_by: str | None = None
    _limit: int | None = None
    _columns: list[str] = field(default_factory=lambda: ["*"])

    def table(self, name: str) -> "QueryBuilder":
        self._table = name
        return self

    def select(self, *columns: str) -> "QueryBuilder":
        self._columns = list(columns)
        return self

    def where(self, condition: str) -> "QueryBuilder":
        self._conditions.append(condition)
        return self

    def order(self, column: str) -> "QueryBuilder":
        self._order_by = column
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit = n
        return self

    def build(self) -> str:
        cols = ", ".join(self._columns)
        query = f"SELECT {cols} FROM {self._table}"
        if self._conditions:
            query += " WHERE " + " AND ".join(self._conditions)
        if self._order_by:
            query += f" ORDER BY {self._order_by}"
        if self._limit:
            query += f" LIMIT {self._limit}"
        return query


# Method chaining makes construction readable
query = (
    QueryBuilder()
    .table("users")
    .select("id", "name", "email")
    .where("active = true")
    .where("created_at > '2025-01-01'")
    .order("name")
    .limit(50)
    .build()
)
print(query)
# SELECT id, name, email FROM users WHERE active = true
#   AND created_at > '2025-01-01' ORDER BY name LIMIT 50
```

In a Django project, you see the Builder pattern in Django's `QuerySet` API itself: `User.objects.filter(...).exclude(...).order_by(...).values(...)` is a fluent builder. You might also use this pattern for constructing complex email messages, report configurations, or API request payloads.

---

> [!NOTE]
> **Beginner's Mental Model — Singleton:**
> Think of a Singleton as a single physical printer in a small office. Instead of giving every employee their own personal printer (which would be expensive and waste resources), everyone sends their documents to the exact same shared machine. No matter who clicks "Print," the request goes to that one specific device.

#### Singleton

Imagine a small office with dozens of employees. Instead of buying every single employee their own personal heavy-duty printer—which would be expensive, waste space, and require massive maintenance—the office has one single, shared printer. Every computer in the office is wired to send print jobs to this exact same machine. In software, a Singleton works the same way. It is a design pattern that guarantees a specific class will only ever have one single instance active in your running application. Any part of your code that needs to print a log, read a configuration file, or talk to a database connection pool will share that exact same single object, preventing your application from wasting resources by spinning up duplicate connections or config readers.

The Singleton pattern ensures a class has only one instance and provides a global access point to it. Common uses include database connection pools, configuration managers, and logging instances.

In Python, the simplest Singleton is a **module-level instance**. Python modules are only loaded once, so a module-level variable is naturally a singleton.

```python
# ---- Approach 1: Module-level instance (preferred in Python) ----

# config.py
class _AppConfig:
    def __init__(self):
        self.debug = False
        self.database_url = "sqlite:///db.sqlite3"

    def load_from_env(self):
        import os
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.database_url = os.getenv("DATABASE_URL", self.database_url)

# The singleton instance -- import this, not the class
app_config = _AppConfig()
app_config.load_from_env()

# Usage in other modules:
# from config import app_config


# ---- Approach 2: __new__ override (when you need class-based singleton) ----

class DatabasePool:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_connections: int = 10):
        if self._initialized:
            return
        self.max_connections = max_connections
        self.connections: list = []
        self._initialized = True
        print(f"Pool created with {max_connections} max connections")

# Both variables point to the same instance
pool1 = DatabasePool(max_connections=5)
pool2 = DatabasePool(max_connections=20)  # max_connections=20 is ignored
print(pool1 is pool2)  # True
```

**Warning:** Singleton is often considered an anti-pattern because it introduces global state and makes testing difficult. Prefer **dependency injection** -- pass the shared instance explicitly rather than accessing it globally. Django's `settings` module is an example of a module-level singleton that works well because it is read-only after startup.

---

#### Prototype

The Prototype pattern creates new objects by cloning existing ones. This is useful when object creation is expensive (e.g., involves database queries or complex computation) or when you want to create variations of a template object.

Python provides built-in support via the `copy` module.

```python
import copy
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    hostname: str
    port: int
    ssl_enabled: bool
    environment_vars: dict[str, str] = field(default_factory=dict)
    allowed_hosts: list[str] = field(default_factory=list)


# Create a template configuration
template = ServerConfig(
    hostname="app.example.com",
    port=443,
    ssl_enabled=True,
    environment_vars={"LOG_LEVEL": "INFO", "WORKERS": "4"},
    allowed_hosts=["example.com", "*.example.com"],
)

# Clone and customize for different environments
staging = copy.deepcopy(template)
staging.hostname = "staging.example.com"
staging.environment_vars["LOG_LEVEL"] = "DEBUG"

production = copy.deepcopy(template)
production.environment_vars["WORKERS"] = "16"

print(staging.hostname)               # staging.example.com
print(staging.environment_vars)        # {'LOG_LEVEL': 'DEBUG', 'WORKERS': '4'}
print(production.environment_vars)     # {'LOG_LEVEL': 'INFO', 'WORKERS': '16'}
print(template.environment_vars)       # {'LOG_LEVEL': 'INFO', 'WORKERS': '4'} (unchanged)
```

Use `copy.copy()` for shallow copies (nested objects are shared) and `copy.deepcopy()` for deep copies (everything is independent). In a Django context, this is useful for cloning complex queryset filters or duplicating model instances with modifications.

---

#### Object Pool

The Object Pool pattern keeps a set of pre-created, reusable objects ready for use, handing one out on request and taking it back when the caller is done -- instead of constructing and destroying expensive objects repeatedly. It is the pattern behind database connection pools, thread pools, and HTTP client pools: creating a TCP connection or spawning a thread costs milliseconds and OS resources, so you amortize that cost by reusing a bounded set.

```python
import queue
import threading


class Connection:
    """Stand-in for an expensive-to-create resource."""
    _counter = 0

    def __init__(self):
        Connection._counter += 1
        self.id = Connection._counter
        print(f"Opening expensive connection #{self.id}")

    def execute(self, sql: str) -> str:
        return f"conn#{self.id} ran: {sql}"


class ConnectionPool:
    def __init__(self, size: int = 2):
        self._pool: queue.Queue[Connection] = queue.Queue(maxsize=size)
        for _ in range(size):
            self._pool.put(Connection())  # pre-create up front

    def acquire(self, timeout: float = 5.0) -> Connection:
        # Blocks if all connections are checked out -- this is backpressure.
        return self._pool.get(timeout=timeout)

    def release(self, conn: Connection) -> None:
        self._pool.put(conn)


pool = ConnectionPool(size=2)
print("--- pool ready ---")
conn = pool.acquire()
print(conn.execute("SELECT 1"))
pool.release(conn)
conn2 = pool.acquire()       # reuses an existing connection, no new "Opening..."
print(conn2.execute("SELECT 2"))
```

```text
Opening expensive connection #1
Opening expensive connection #2
--- pool ready ---
conn#1 ran: SELECT 1
conn#2 ran: SELECT 2
```

**How to read this output:** Both "Opening expensive connection" lines appear *before* `--- pool ready ---` -- the cost is paid once at startup, not per query. Crucially, the second `acquire()` prints no new "Opening..." line: it handed back a connection already in the pool. That is the entire value proposition under load -- a web app serving thousands of requests reuses a handful of connections instead of opening one per request (which would exhaust the database's connection limit). The `queue.Queue.get(timeout=...)` also gives you free backpressure: if every connection is checked out, the caller blocks (or times out) rather than overwhelming the backend, which is why SQLAlchemy's `pool_size` + `max_overflow` and PgBouncer exist. The `Queue` is thread-safe, so this pool is safe to share across worker threads without extra locking.

> **Common pitfall:** A pooled object must be *reset* before reuse -- a database connection mid-transaction or an HTTP client with stale headers will leak state into the next caller. Real pools validate/recycle connections (SQLAlchemy's `pool_pre_ping`) and cap object lifetime, because a connection silently dropped by the server will otherwise be handed to an unsuspecting caller as a broken resource.

> **Key Takeaway:** Creational patterns solve the problem of "how do I create objects flexibly?" In Python, many of these patterns are simpler than their Java equivalents because of first-class functions, duck typing, and the `copy` module. Use Factory functions for runtime type selection, Builder for complex construction, and prefer module-level instances or dependency injection over Singleton.

---

### Structural Patterns

Structural patterns deal with object composition -- how classes and objects are assembled to form larger structures while keeping the structure flexible and efficient.

---

> [!NOTE]
> **Beginner's Mental Model — Adapter:**
> Think of an Adapter like a physical travel plug adapter. If you travel from the US to Europe, your laptop plug (with flat pins) won't fit into the European wall outlet (with round holes). An adapter doesn't change how your laptop works, nor does it change the electricity in the wall; it simply sits in the middle and translates the connection so they can work together.

#### Adapter

If you have ever traveled to another country with your laptop, you have likely run into a socket compatibility issue. Your plug might have flat pins, but the wall outlet has round holes. You cannot change the wiring of the building, and you cannot redesign your laptop charger. Instead, you use a travel adapter. The adapter sits in the middle: it accepts your flat-pin plug on one side and fits into the round-hole outlet on the other, translating the physical connection without altering the electrical current. In software engineering, the Adapter pattern does exactly the same job. When you have two parts of a system that need to talk to each other but speak different languages—such as your code expecting a standard payment format but a third-party service like Stripe or PayPal requiring its own custom function arguments—you write an adapter class. This adapter translates the inputs and outputs, allowing incompatible interfaces to work together seamlessly without modifying either side.

The Adapter pattern converts the interface of a class into another interface that clients expect. It lets classes work together that otherwise could not because of incompatible interfaces. This is especially common when integrating third-party libraries or legacy systems.

```python
from typing import Protocol


# Your application expects this interface
class PaymentProcessor(Protocol):
    def charge(self, amount: float, currency: str) -> dict: ...


# Third-party library has a different interface
class StripeSDK:
    def create_charge(self, amount_cents: int, currency_code: str, idempotency_key: str) -> dict:
        print(f"Stripe: charging {amount_cents} {currency_code}")
        return {"id": "ch_123", "status": "succeeded"}


class PayPalSDK:
    def execute_payment(self, value: str, currency: str) -> dict:
        print(f"PayPal: paying {value} {currency}")
        return {"payment_id": "PAY-456", "state": "approved"}


# Adapters translate between your interface and the third-party interface
import uuid

class StripeAdapter:
    def __init__(self, stripe: StripeSDK):
        self.stripe = stripe

    def charge(self, amount: float, currency: str) -> dict:
        result = self.stripe.create_charge(
            amount_cents=int(amount * 100),
            currency_code=currency.lower(),
            idempotency_key=str(uuid.uuid4()),
        )
        return {"provider": "stripe", "transaction_id": result["id"], "status": result["status"]}


class PayPalAdapter:
    def __init__(self, paypal: PayPalSDK):
        self.paypal = paypal

    def charge(self, amount: float, currency: str) -> dict:
        result = self.paypal.execute_payment(
            value=f"{amount:.2f}",
            currency=currency.upper(),
        )
        return {"provider": "paypal", "transaction_id": result["payment_id"], "status": result["state"]}


# Client code works with the uniform interface
def process_order(processor: PaymentProcessor, total: float) -> dict:
    return processor.charge(total, "USD")


# Swap implementations freely
stripe_processor = StripeAdapter(StripeSDK())
paypal_processor = PayPalAdapter(PayPalSDK())

process_order(stripe_processor, 99.99)
process_order(paypal_processor, 99.99)
```

Running this prints:

```text
Stripe: charging 9999 usd
PayPal: paying 99.99 USD
```

**How to read this output:** Notice the two SDKs disagree on everything -- Stripe wants integer cents (`9999`) and a lowercase currency, PayPal wants a formatted string (`99.99`) and uppercase. The adapter absorbs those differences so `process_order` only ever calls `charge(total, "USD")`. This is exactly why adapters matter in production: when you switch payment providers, add a fallback processor, or run an A/B split between gateways, the business logic that calls `charge(...)` never changes -- only which adapter you inject does. The normalized return shape (`{"provider", "transaction_id", "status"}`) is what lets downstream code log and reconcile transactions uniformly.

In a Django project, adapters are used when integrating multiple email providers (SendGrid, Mailgun, SES), storage backends (S3, GCS, local filesystem), or authentication providers (OAuth2, SAML, LDAP).

---

#### Decorator (Structural Pattern)

The structural Decorator pattern dynamically adds responsibilities to objects by wrapping them. This is distinct from Python's `@decorator` syntax, though Python decorators are inspired by the same concept. The structural Decorator wraps an object with an enhanced version that implements the same interface.

```python
from typing import Protocol
import time
import logging

logger = logging.getLogger(__name__)


class DataFetcher(Protocol):
    def fetch(self, key: str) -> str | None: ...


class DatabaseFetcher:
    """Base implementation -- fetches from database."""
    def fetch(self, key: str) -> str | None:
        time.sleep(0.1)  # Simulate database query
        return f"data_for_{key}"


class CachingDecorator:
    """Wraps a DataFetcher with an in-memory cache."""
    def __init__(self, wrapped: DataFetcher):
        self._wrapped = wrapped
        self._cache: dict[str, str] = {}

    def fetch(self, key: str) -> str | None:
        if key in self._cache:
            logger.info(f"Cache hit for {key}")
            return self._cache[key]
        result = self._wrapped.fetch(key)
        if result is not None:
            self._cache[key] = result
        return result


class LoggingDecorator:
    """Wraps a DataFetcher with logging."""
    def __init__(self, wrapped: DataFetcher):
        self._wrapped = wrapped

    def fetch(self, key: str) -> str | None:
        logger.info(f"Fetching key={key}")
        start = time.time()
        result = self._wrapped.fetch(key)
        elapsed = time.time() - start
        logger.info(f"Fetched key={key} in {elapsed:.3f}s")
        return result


class RetryDecorator:
    """Wraps a DataFetcher with retry logic."""
    def __init__(self, wrapped: DataFetcher, max_retries: int = 3):
        self._wrapped = wrapped
        self._max_retries = max_retries

    def fetch(self, key: str) -> str | None:
        for attempt in range(self._max_retries):
            try:
                return self._wrapped.fetch(key)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == self._max_retries - 1:
                    raise
        return None


# Stack decorators -- each layer adds a responsibility
fetcher: DataFetcher = DatabaseFetcher()
fetcher = RetryDecorator(fetcher, max_retries=3)
fetcher = CachingDecorator(fetcher)
fetcher = LoggingDecorator(fetcher)

# Caller does not know about caching, logging, or retries
result = fetcher.fetch("user:42")
```

The decorators use the `logging` module, so you only see output if logging is configured (e.g. `logging.basicConfig(level=logging.INFO)`). With logging enabled, the first call to `fetch("user:42")` prints something like:

```text
INFO:__main__:Fetching key=user:42
INFO:__main__:Fetched key=user:42 in 0.103s
```

**How to read this output:** The log lines come from the outermost wrapper (`LoggingDecorator`) -- the request enters at the top of the stack and falls through `Retry -> Caching -> Database`, then unwinds back up. The `0.103s` reflects the real `time.sleep(0.1)` in `DatabaseFetcher`. Call `fetch("user:42")` a second time and the timing drops to near zero because `CachingDecorator` short-circuits before the database layer ever runs (and emits `Cache hit for user:42`). The order in which you wrap matters: putting caching *inside* logging means cache hits are still logged; flipping them would log only genuine misses.

> **Common pitfall:** Decorator order is a real source of production bugs. If you wrap retry *outside* logging, each retry attempt gets logged separately; if you wrap caching *outside* retry, a cached failure can mask a now-recovered backend. Always reason about which responsibility should run first.

This is a powerful technique because you can add, remove, or reorder behaviors without modifying the base class.

---

#### Facade

The Facade pattern provides a simplified interface to a complex subsystem. It does not add new functionality but rather presents a more convenient, higher-level API. Use it to reduce the number of objects a client must interact with.

```python
class InventoryService:
    def check_stock(self, product_id: str) -> bool:
        print(f"Checking stock for {product_id}")
        return True

    def reserve_stock(self, product_id: str, qty: int) -> None:
        print(f"Reserved {qty} of {product_id}")


class PaymentService:
    def authorize(self, amount: float, card_token: str) -> str:
        print(f"Authorized ${amount}")
        return "auth_123"

    def capture(self, auth_id: str) -> None:
        print(f"Captured {auth_id}")


class ShippingService:
    def create_shipment(self, address: str, product_id: str) -> str:
        print(f"Shipment created for {product_id} to {address}")
        return "SHIP_456"


class NotificationService:
    def send_confirmation(self, email: str, order_id: str) -> None:
        print(f"Confirmation sent to {email} for {order_id}")


class OrderFacade:
    """
    Simplified interface for placing an order.
    Coordinates four subsystems behind one method call.
    """
    def __init__(self):
        self.inventory = InventoryService()
        self.payment = PaymentService()
        self.shipping = ShippingService()
        self.notifications = NotificationService()

    def place_order(
        self,
        product_id: str,
        qty: int,
        amount: float,
        card_token: str,
        address: str,
        email: str,
    ) -> str:
        # Step 1: Check and reserve inventory
        if not self.inventory.check_stock(product_id):
            raise ValueError("Out of stock")
        self.inventory.reserve_stock(product_id, qty)

        # Step 2: Process payment
        auth_id = self.payment.authorize(amount, card_token)
        self.payment.capture(auth_id)

        # Step 3: Create shipment
        tracking = self.shipping.create_shipment(address, product_id)

        # Step 4: Notify customer
        self.notifications.send_confirmation(email, tracking)

        return tracking


# Client uses one simple call instead of coordinating four services
facade = OrderFacade()
tracking = facade.place_order("PROD-1", 2, 59.99, "tok_abc", "123 Main St", "a@b.com")
```

Running this prints:

```text
Checking stock for PROD-1
Reserved 2 of PROD-1
Authorized $59.99
Captured auth_123
Shipment created for PROD-1 to 123 Main St
Confirmation sent to a@b.com for SHIP_456
```

**How to read this output:** Each line comes from a different subsystem, but the client issued exactly one call. That is the facade's value -- it collapses a six-step orchestration (inventory, payment, shipping, notification) into `place_order(...)`, so a view or API handler never has to know the correct ordering or which services to wire together. The sequence also encodes the business rule: stock is reserved *before* payment, and the customer is notified only after a tracking number exists. In real systems this is where service-layer classes live; keeping orchestration here (not in the view) is what keeps controllers thin and the workflow testable in isolation.

In a Django project, service classes often act as facades that coordinate models, external APIs, and notifications behind a single method that views can call.

---

#### Proxy

The Proxy pattern provides a surrogate or placeholder for another object to control access to it. There are several types of proxies:

- **Virtual Proxy** -- delays expensive object creation until it is actually needed (lazy loading)
- **Protection Proxy** -- controls access based on permissions
- **Caching Proxy** -- caches results to avoid repeated computation
- **Remote Proxy** -- represents an object in a different address space (network call)

```python
from typing import Protocol
import time


class ExpensiveResource(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class RealDatabase:
    """Expensive to create -- establishes actual connection."""
    def __init__(self, connection_string: str):
        print(f"Connecting to {connection_string}...")
        time.sleep(1)  # Simulate slow connection
        self.connection_string = connection_string

    def query(self, sql: str) -> list[dict]:
        print(f"Executing: {sql}")
        return [{"id": 1, "name": "example"}]


class LazyDatabaseProxy:
    """Virtual proxy -- delays connection until first query."""
    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self._real_db: RealDatabase | None = None

    def _get_db(self) -> RealDatabase:
        if self._real_db is None:
            self._real_db = RealDatabase(self._connection_string)
        return self._real_db

    def query(self, sql: str) -> list[dict]:
        return self._get_db().query(sql)


class AccessControlProxy:
    """Protection proxy -- checks permissions before allowing queries."""
    def __init__(self, real_db: ExpensiveResource, allowed_users: set[str]):
        self._real_db = real_db
        self._allowed_users = allowed_users

    def query(self, sql: str, user: str = "anonymous") -> list[dict]:
        if user not in self._allowed_users:
            raise PermissionError(f"User '{user}' is not allowed to query the database")
        return self._real_db.query(sql)


# Usage
db = LazyDatabaseProxy("postgresql://localhost/mydb")  # No connection yet
print("Proxy created, no connection established yet")
result = db.query("SELECT * FROM users")  # NOW it connects
```

Running this prints:

```text
Proxy created, no connection established yet
Connecting to postgresql://localhost/mydb...
Executing: SELECT * FROM users
```

**How to read this output:** The key signal is *ordering*. Constructing the proxy prints nothing about connecting -- the `Connecting to...` line (and its one-second delay from `time.sleep(1)`) appears only when `query()` runs and triggers `_get_db()`. That deferral is the whole purpose of a virtual proxy: in a web request that may short-circuit early (a cache hit, a 403, a validation error), you never pay the expensive connection cost unless you actually need the resource. Query the proxy a second time and `Connecting to...` does *not* reprint, because `_real_db` is now cached. This is precisely how Django's `SimpleLazyObject` defers loading `request.user` until a view actually touches it.

In Python, `__getattr__` provides a concise way to implement proxies by delegating attribute access to the wrapped object. Django's `SimpleLazyObject` is a real-world example of a virtual proxy.

---

#### Composite

The Composite pattern composes objects into tree structures to represent part-whole hierarchies. It lets clients treat individual objects and compositions of objects uniformly. Classic examples include file systems (files and directories), organizational charts, and UI component trees.

```python
from abc import ABC, abstractmethod


class Component(ABC):
    """Common interface for both leaves and composites."""
    @abstractmethod
    def get_size(self) -> int: ...

    @abstractmethod
    def display(self, indent: int = 0) -> str: ...


class File(Component):
    """Leaf node."""
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size

    def get_size(self) -> int:
        return self.size

    def display(self, indent: int = 0) -> str:
        return " " * indent + f"{self.name} ({self.size} bytes)"


class Directory(Component):
    """Composite node -- contains other Components (files or directories)."""
    def __init__(self, name: str):
        self.name = name
        self.children: list[Component] = []

    def add(self, component: Component) -> None:
        self.children.append(component)

    def get_size(self) -> int:
        return sum(child.get_size() for child in self.children)

    def display(self, indent: int = 0) -> str:
        lines = [" " * indent + f"{self.name}/ ({self.get_size()} bytes)"]
        for child in self.children:
            lines.append(child.display(indent + 2))
        return "\n".join(lines)


# Build a tree structure
root = Directory("project")
src = Directory("src")
src.add(File("main.py", 1200))
src.add(File("utils.py", 800))

tests = Directory("tests")
tests.add(File("test_main.py", 600))

root.add(src)
root.add(tests)
root.add(File("README.md", 300))

print(root.display())
# project/ (2900 bytes)
#   src/ (2000 bytes)
#     main.py (1200 bytes)
#     utils.py (800 bytes)
#   tests/ (600 bytes)
#     test_main.py (600 bytes)
#   README.md (300 bytes)

print(f"Total size: {root.get_size()} bytes")
# Total size: 2900 bytes
```

In backend development, the Composite pattern is useful for modeling permission hierarchies (roles contain permissions, permission groups contain roles), menu systems, or organizational structures.

---

#### Bridge

The Bridge pattern decouples an **abstraction** from its **implementation** so the two can vary independently. It is the answer to a combinatorial explosion: when you have *M* kinds of "what" and *N* kinds of "how", inheritance forces you to write `M x N` subclasses, while Bridge splits them into two hierarchies you compose at runtime (`M + N` classes). The classic example: notification *types* (alert, report, reminder) crossed with delivery *channels* (email, SMS, Slack). Rather than `EmailAlert`, `SmsAlert`, `SlackAlert`, `EmailReport`... you have a `Notification` abstraction holding a reference to a `Channel` implementor.

```python
from abc import ABC, abstractmethod


# ---- Implementor hierarchy: the "how" (delivery channel) ----
class Channel(ABC):
    @abstractmethod
    def deliver(self, text: str) -> None: ...


class EmailChannel(Channel):
    def deliver(self, text: str) -> None:
        print(f"[email] {text}")


class SmsChannel(Channel):
    def deliver(self, text: str) -> None:
        print(f"[sms] {text}")


# ---- Abstraction hierarchy: the "what" (message type) ----
class Notification(ABC):
    def __init__(self, channel: Channel):
        self.channel = channel  # the bridge: holds an implementor, not a subclass

    @abstractmethod
    def send(self, payload: dict) -> None: ...


class Alert(Notification):
    def send(self, payload: dict) -> None:
        self.channel.deliver(f"ALERT: {payload['message']}")


class Reminder(Notification):
    def send(self, payload: dict) -> None:
        self.channel.deliver(f"Reminder: {payload['message']} (due {payload['due']})")


# Mix and match any abstraction with any implementor at runtime
Alert(EmailChannel()).send({"message": "CPU at 95%"})
Alert(SmsChannel()).send({"message": "CPU at 95%"})
Reminder(SmsChannel()).send({"message": "renew cert", "due": "Friday"})
```

```text
[email] ALERT: CPU at 95%
[sms] ALERT: CPU at 95%
[sms] Reminder: renew cert (due Friday)
```

**How to read this output:** The same `Alert` class produced both an email and an SMS line -- the message *type* and the *channel* were chosen independently and composed at the call site. That is the structural win: adding a new channel (say Slack) is one new `Channel` subclass that *every* notification type can immediately use, with zero edits to `Alert` or `Reminder`; adding a new message type is one new `Notification` subclass that works over every existing channel. Without Bridge, each new channel would force you to add one subclass per message type. Bridge and Strategy look similar in Python (both inject a collaborator), but the intent differs: Strategy swaps one *algorithm*, Bridge separates two whole *dimensions of variation* that each have their own hierarchy.

> **Key Takeaway:** Structural patterns help you compose objects into larger structures while keeping things flexible. Adapter bridges incompatible interfaces, Decorator adds behavior without modifying classes, Facade simplifies complex subsystems, Proxy controls access, and Composite handles tree structures. In Python, duck typing and Protocols make these patterns lighter than in statically-typed languages.

---

### Behavioral Patterns

Behavioral patterns deal with algorithms and the assignment of responsibilities between objects. They describe not just patterns of objects but also patterns of communication between them.

---

> [!NOTE]
> **Beginner's Mental Model — Observer:**
> Think of the Observer pattern like subscribing to a YouTube channel or a newsletter. Instead of you (the viewer) constantly refreshing the channel's page to check for new videos (polling), you hit the "Subscribe" button. When a new video is uploaded, the channel automatically sends a notification to all subscribers at once.

#### Observer

Imagine you are waiting for a popular sneaker release at a local store. You could walk to the store every single hour, peek through the window, and ask the cashier if the shoes have arrived. This is called "polling," and it is a massive waste of your time and energy. Alternatively, the store could place a sign-up sheet on the counter. You write down your email address, subscribing to updates. When the sneakers finally arrive, the store manager walks down the list and blasts an email to everyone who signed up. This is the Observer pattern. Instead of having various parts of your system constantly check ("poll") whether an object has changed state, the object itself maintains a list of interested dependents (observers) and automatically broadcasts a message to all of them the moment something happens. This keeps the parts of your application decoupled, as the main object doesn't need to know the details of *who* is listening or *why*, only that it needs to notify them.

The Observer pattern defines a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically. This decouples the subject (publisher) from its observers (subscribers).

```python
from typing import Protocol, Any
from dataclasses import dataclass, field


class EventHandler(Protocol):
    def handle(self, event: str, data: Any) -> None: ...


class EventBus:
    """Simple publish-subscribe event bus."""
    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(event, []).append(handler)

    def publish(self, event: str, data: Any = None) -> None:
        for handler in self._subscribers.get(event, []):
            handler.handle(event, data)


class InventoryUpdater:
    def handle(self, event: str, data: Any) -> None:
        print(f"[Inventory] Reducing stock for order {data['order_id']}")


class EmailSender:
    def handle(self, event: str, data: Any) -> None:
        print(f"[Email] Sending confirmation for order {data['order_id']}")


class AnalyticsTracker:
    def handle(self, event: str, data: Any) -> None:
        print(f"[Analytics] Tracking order {data['order_id']}, total: ${data['total']}")


# Wire up observers
bus = EventBus()
bus.subscribe("order.placed", InventoryUpdater())
bus.subscribe("order.placed", EmailSender())
bus.subscribe("order.placed", AnalyticsTracker())

# Publishing an event notifies all subscribers
bus.publish("order.placed", {"order_id": "ORD-123", "total": 59.99})
# [Inventory] Reducing stock for order ORD-123
# [Email] Sending confirmation for order ORD-123
# [Analytics] Tracking order ORD-123, total: $59.99
```

In a Django project, the Observer pattern is built into the framework as **Django signals** (`post_save`, `pre_delete`, etc.). While signals provide decoupling, they also create hidden dependencies that are hard to trace during debugging. For complex workflows, consider explicit event buses or domain events over Django signals.

---

#### Strategy

The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. The client delegates to a strategy object, allowing the algorithm to vary independently from the clients that use it.

In Python, first-class functions can serve as lightweight strategies, but classes are better when strategies need state or configuration.

```python
from typing import Protocol
from dataclasses import dataclass


class PricingStrategy(Protocol):
    def calculate_price(self, base_price: float, quantity: int) -> float: ...


class RegularPricing:
    def calculate_price(self, base_price: float, quantity: int) -> float:
        return base_price * quantity


class BulkPricing:
    """10% discount for orders over 100 units."""
    def calculate_price(self, base_price: float, quantity: int) -> float:
        total = base_price * quantity
        if quantity > 100:
            total *= 0.90
        return total


class SeasonalPricing:
    """Applies a seasonal multiplier."""
    def __init__(self, multiplier: float = 1.2):
        self.multiplier = multiplier

    def calculate_price(self, base_price: float, quantity: int) -> float:
        return base_price * quantity * self.multiplier


class TieredPricing:
    """Different rates at different volume tiers."""
    def calculate_price(self, base_price: float, quantity: int) -> float:
        if quantity <= 10:
            return base_price * quantity
        elif quantity <= 50:
            return base_price * quantity * 0.95
        else:
            return base_price * quantity * 0.85


@dataclass
class ShoppingCart:
    pricing: PricingStrategy

    def checkout(self, items: list[tuple[str, float, int]]) -> float:
        total = 0.0
        for name, price, qty in items:
            item_total = self.pricing.calculate_price(price, qty)
            print(f"  {name}: ${item_total:.2f}")
            total += item_total
        return total


# Swap strategies at runtime
items = [("Widget", 9.99, 200), ("Gadget", 24.99, 5)]

print("Regular pricing:")
cart = ShoppingCart(RegularPricing())
print(f"  Total: ${cart.checkout(items):.2f}\n")

print("Bulk pricing:")
cart = ShoppingCart(BulkPricing())
print(f"  Total: ${cart.checkout(items):.2f}\n")

print("Holiday pricing (1.5x):")
cart = ShoppingCart(SeasonalPricing(multiplier=1.5))
print(f"  Total: ${cart.checkout(items):.2f}")
```

Running this prints:

```text
Regular pricing:
  Widget: $1998.00
  Gadget: $124.95
  Total: $2122.95

Bulk pricing:
  Widget: $1798.20
  Gadget: $124.95
  Total: $1923.15

Holiday pricing (1.5x):
  Widget: $2997.00
  Gadget: $187.42
  Total: $3184.42
```

**How to read this output:** Same cart, same items, three totals -- only the injected strategy changed. The `Widget` line tells the story: 200 units at $9.99 is $1998.00 under regular pricing, but $1798.20 under bulk (the 10% discount kicks in because quantity > 100), and $2997.00 under the 1.5x seasonal multiplier. `Gadget` (5 units) gets no bulk discount because it is under the 100-unit threshold, which is why its price only changes under seasonal pricing. This is the production payoff of Strategy: pricing rules, A/B experiments, and promotional campaigns become a runtime choice rather than branching logic baked into `checkout()` -- you can pull the active strategy from a feature flag or a customer's plan tier without rewriting the cart.

Strategy is one of the most commonly used patterns in backend development. In a Django project, you might use it for: different serialization formats (JSON, CSV, XML), different authentication methods, different search backends, or different caching strategies.

---

#### Command

The Command pattern encapsulates a request as an object, allowing you to parameterize clients with different requests, queue requests, log them, and support undo/redo operations.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


@dataclass
class Document:
    content: str = ""

    def insert_text(self, position: int, text: str) -> None:
        self.content = self.content[:position] + text + self.content[position:]

    def delete_text(self, position: int, length: int) -> str:
        deleted = self.content[position:position + length]
        self.content = self.content[:position] + self.content[position + length:]
        return deleted


@dataclass
class InsertCommand(Command):
    document: Document
    position: int
    text: str

    def execute(self) -> None:
        self.document.insert_text(self.position, self.text)

    def undo(self) -> None:
        self.document.delete_text(self.position, len(self.text))


@dataclass
class DeleteCommand(Command):
    document: Document
    position: int
    length: int
    _deleted_text: str = ""

    def execute(self) -> None:
        self._deleted_text = self.document.delete_text(self.position, self.length)

    def undo(self) -> None:
        self.document.insert_text(self.position, self._deleted_text)


@dataclass
class CommandHistory:
    _history: list[Command] = field(default_factory=list)
    _redo_stack: list[Command] = field(default_factory=list)

    def execute(self, command: Command) -> None:
        command.execute()
        self._history.append(command)
        self._redo_stack.clear()

    def undo(self) -> None:
        if not self._history:
            return
        command = self._history.pop()
        command.undo()
        self._redo_stack.append(command)

    def redo(self) -> None:
        if not self._redo_stack:
            return
        command = self._redo_stack.pop()
        command.execute()
        self._history.append(command)


# Usage
doc = Document()
history = CommandHistory()

history.execute(InsertCommand(doc, 0, "Hello"))
print(doc.content)  # "Hello"

history.execute(InsertCommand(doc, 5, " World"))
print(doc.content)  # "Hello World"

history.undo()
print(doc.content)  # "Hello"

history.redo()
print(doc.content)  # "Hello World"

history.execute(DeleteCommand(doc, 5, 6))
print(doc.content)  # "Hello"

history.undo()
print(doc.content)  # "Hello World"
```

In backend systems, the Command pattern appears in task queues (Celery tasks are essentially command objects), database migrations (each migration is a command with `forward()` and `backward()` methods), and transaction logging.

---

#### Chain of Responsibility

The Chain of Responsibility pattern passes a request along a chain of handlers. Each handler decides either to process the request or to pass it to the next handler in the chain. This decouples senders from receivers and allows you to compose processing pipelines dynamically.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Request:
    path: str
    method: str
    headers: dict[str, str]
    body: str
    user: str | None = None
    response_code: int = 200
    response_body: str = ""


class Middleware(ABC):
    def __init__(self):
        self._next: Middleware | None = None

    def set_next(self, handler: "Middleware") -> "Middleware":
        self._next = handler
        return handler

    @abstractmethod
    def handle(self, request: Request) -> Request: ...

    def pass_to_next(self, request: Request) -> Request:
        if self._next:
            return self._next.handle(request)
        return request


class AuthenticationMiddleware(Middleware):
    def handle(self, request: Request) -> Request:
        token = request.headers.get("Authorization", "")
        if not token:
            request.response_code = 401
            request.response_body = "Unauthorized: no token provided"
            return request  # Stop the chain
        request.user = f"user_for_{token}"
        print(f"[Auth] Authenticated as {request.user}")
        return self.pass_to_next(request)


class RateLimitMiddleware(Middleware):
    def __init__(self, max_requests: int = 100):
        super().__init__()
        self.max_requests = max_requests
        self._request_counts: dict[str, int] = {}

    def handle(self, request: Request) -> Request:
        user = request.user or "anonymous"
        self._request_counts[user] = self._request_counts.get(user, 0) + 1
        if self._request_counts[user] > self.max_requests:
            request.response_code = 429
            request.response_body = "Too many requests"
            return request
        print(f"[RateLimit] {user}: {self._request_counts[user]}/{self.max_requests}")
        return self.pass_to_next(request)


class LoggingMiddleware(Middleware):
    def handle(self, request: Request) -> Request:
        print(f"[Log] {request.method} {request.path} by {request.user}")
        result = self.pass_to_next(request)
        print(f"[Log] Response: {result.response_code}")
        return result


# Build the chain
auth = AuthenticationMiddleware()
rate_limit = RateLimitMiddleware(max_requests=10)
logging_mw = LoggingMiddleware()

auth.set_next(rate_limit).set_next(logging_mw)

# Process a request through the chain
req = Request(
    path="/api/orders",
    method="GET",
    headers={"Authorization": "Bearer abc123"},
    body="",
)
result = auth.handle(req)
```

Running this prints:

```text
[Auth] Authenticated as user_for_Bearer abc123
[RateLimit] user_for_Bearer abc123: 1/10
[Log] GET /api/orders by user_for_Bearer abc123
[Log] Response: 200
```

**How to read this output:** Read the lines top to bottom as the request travelling *into* the chain (`Auth -> RateLimit -> Log`) and then the last `[Log] Response: 200` as it unwinds back *out*. Each handler did its one job and called `pass_to_next(request)` to continue. The decisive feature is short-circuiting: if the `Authorization` header had been missing, `AuthenticationMiddleware` would have set `response_code = 401` and returned immediately -- you would see only the auth line, and rate-limiting and logging would never run. That early-exit-on-failure is exactly what you want in a real request pipeline, and it is how Django's `settings.MIDDLEWARE` list behaves: order determines which checks gate the others.

> **Common pitfall:** Middleware ordering is load-bearing. Put rate limiting *before* authentication and you let unauthenticated traffic consume your rate-limit budget; put logging at the very end and a handler that short-circuits earlier produces no log line at all. The chain's order is a design decision, not an implementation detail.

This is exactly how Django middleware and ASGI/WSGI middleware stacks work. Each middleware in `settings.MIDDLEWARE` forms a link in the chain, processing the request on the way in and the response on the way out.

---

#### State

The State pattern allows an object to alter its behavior when its internal state changes. The object appears to change its class. State transitions are modeled as objects, making the transition logic explicit and each state's behavior self-contained.

```python
from abc import ABC, abstractmethod


class OrderState(ABC):
    @abstractmethod
    def confirm(self, order: "Order") -> None: ...

    @abstractmethod
    def ship(self, order: "Order") -> None: ...

    @abstractmethod
    def deliver(self, order: "Order") -> None: ...

    @abstractmethod
    def cancel(self, order: "Order") -> None: ...


class PendingState(OrderState):
    def confirm(self, order: "Order") -> None:
        print("Order confirmed. Processing payment...")
        order.state = ConfirmedState()

    def ship(self, order: "Order") -> None:
        print("Cannot ship: order not confirmed yet.")

    def deliver(self, order: "Order") -> None:
        print("Cannot deliver: order not shipped yet.")

    def cancel(self, order: "Order") -> None:
        print("Order cancelled.")
        order.state = CancelledState()


class ConfirmedState(OrderState):
    def confirm(self, order: "Order") -> None:
        print("Order already confirmed.")

    def ship(self, order: "Order") -> None:
        print("Order shipped!")
        order.state = ShippedState()

    def deliver(self, order: "Order") -> None:
        print("Cannot deliver: order not shipped yet.")

    def cancel(self, order: "Order") -> None:
        print("Order cancelled. Refund initiated.")
        order.state = CancelledState()


class ShippedState(OrderState):
    def confirm(self, order: "Order") -> None:
        print("Order already confirmed and shipped.")

    def ship(self, order: "Order") -> None:
        print("Order already shipped.")

    def deliver(self, order: "Order") -> None:
        print("Order delivered!")
        order.state = DeliveredState()

    def cancel(self, order: "Order") -> None:
        print("Cannot cancel: order already shipped. Initiate return instead.")


class DeliveredState(OrderState):
    def confirm(self, order: "Order") -> None:
        print("Order already delivered.")

    def ship(self, order: "Order") -> None:
        print("Order already delivered.")

    def deliver(self, order: "Order") -> None:
        print("Order already delivered.")

    def cancel(self, order: "Order") -> None:
        print("Cannot cancel: order already delivered. Initiate return instead.")


class CancelledState(OrderState):
    def confirm(self, order: "Order") -> None:
        print("Cannot confirm: order is cancelled.")

    def ship(self, order: "Order") -> None:
        print("Cannot ship: order is cancelled.")

    def deliver(self, order: "Order") -> None:
        print("Cannot deliver: order is cancelled.")

    def cancel(self, order: "Order") -> None:
        print("Order already cancelled.")


class Order:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.state: OrderState = PendingState()

    def confirm(self) -> None:
        self.state.confirm(self)

    def ship(self) -> None:
        self.state.ship(self)

    def deliver(self) -> None:
        self.state.deliver(self)

    def cancel(self) -> None:
        self.state.cancel(self)


order = Order("ORD-001")
order.ship()       # Cannot ship: order not confirmed yet.
order.confirm()    # Order confirmed. Processing payment...
order.confirm()    # Order already confirmed.
order.ship()       # Order shipped!
order.cancel()     # Cannot cancel: order already shipped.
order.deliver()    # Order delivered!
```

This is much cleaner than a series of `if/elif` checks on a status string scattered throughout the codebase. Each state encapsulates its own rules. In a Django project, you might use this for workflow engines, document approval flows, or subscription lifecycle management.

---

#### Template Method

The Template Method pattern defines the **skeleton of an algorithm** in a base class, deferring specific steps to subclasses. The overall sequence is fixed; only the variable steps are overridden. This is the inheritance-based cousin of Strategy (which uses composition): use Template Method when the steps are tightly bound to a fixed workflow, and Strategy when you want to swap a whole step at runtime.

```python
from abc import ABC, abstractmethod


class ReportGenerator(ABC):
    """Defines the fixed algorithm; subclasses fill in the variable steps."""

    def generate(self, source: str) -> str:
        # --- the template method: the invariant skeleton ---
        raw = self.fetch(source)
        rows = self.parse(raw)
        cleaned = self.transform(rows)   # hook with a default
        return self.format(cleaned)

    @abstractmethod
    def fetch(self, source: str) -> str: ...

    @abstractmethod
    def parse(self, raw: str) -> list[dict]: ...

    @abstractmethod
    def format(self, rows: list[dict]) -> str: ...

    def transform(self, rows: list[dict]) -> list[dict]:
        """Hook method: optional override, sensible default."""
        return rows


class CsvSalesReport(ReportGenerator):
    def fetch(self, source: str) -> str:
        return "name,amount\nAlice,100\nBob,200"

    def parse(self, raw: str) -> list[dict]:
        header, *lines = raw.splitlines()
        keys = header.split(",")
        return [dict(zip(keys, line.split(","))) for line in lines]

    def transform(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if int(r["amount"]) >= 150]  # override the hook

    def format(self, rows: list[dict]) -> str:
        return "; ".join(f"{r['name']}={r['amount']}" for r in rows)


print(CsvSalesReport().generate("sales.csv"))
```

```text
Bob=200
```

**How to read this output:** Only `Bob=200` survived because `CsvSalesReport` overrode the `transform` hook to drop rows under 150, while inheriting the fixed `fetch -> parse -> transform -> format` order from the base class. That fixed order is the point: the base class owns the *workflow*, so every report variant is guaranteed to fetch before parsing and parse before formatting -- a subclass cannot accidentally reorder or skip a step. Django's class-based generic views are this pattern in production: `ListView` defines the request-handling skeleton (`get_queryset -> paginate -> get_context_data -> render`), and you override just `get_queryset()`. The risk is the inverse of its strength: deep template hierarchies create the fragile-base-class problem, which is why composition-based Strategy is often preferred when steps need to vary freely.

---

#### Mediator

The Mediator pattern centralizes communication between a set of objects so they no longer refer to each other directly. Instead of *N* objects each holding references to the others (an `O(N^2)` web of dependencies), every object talks only to the mediator, which routes the interactions. This reduces coupling at the cost of a mediator that can itself grow complex.

```python
from typing import Protocol


class Mediator(Protocol):
    def notify(self, sender: str, event: str) -> None: ...


class AuthDialog:
    """A 'colleague' -- knows the mediator, not its siblings."""
    def __init__(self, mediator: Mediator):
        self._mediator = mediator
        self.username = ""
        self.login_enabled = False

    def type_username(self, text: str) -> None:
        self.username = text
        self._mediator.notify("username_field", "changed")


class DialogMediator:
    """Owns the interaction rules between widgets."""
    def __init__(self):
        self.username_field = AuthDialog(self)

    def notify(self, sender: str, event: str) -> None:
        if sender == "username_field" and event == "changed":
            # Coordination logic lives HERE, not smeared across the widgets
            self.username_field.login_enabled = bool(self.username_field.username.strip())
            print(f"login button enabled: {self.username_field.login_enabled}")


dialog = DialogMediator()
dialog.username_field.type_username("")
dialog.username_field.type_username("alice")
```

```text
login button enabled: False
login button enabled: True
```

**How to read this output:** Typing into the username field never directly touched the login button -- the field only told the mediator "I changed," and the mediator decided to enable the button. That indirection is why the field knows nothing about the button's existence: you can add a password field, a "forgot password" link, or a captcha and only the mediator changes, not the existing widgets. The same pattern scales up in backend systems as the in-process event bus / coordinator: the Observer's `EventBus` shown earlier is essentially a mediator for domain events, and a Saga orchestrator (see Architectural Styles) is a mediator coordinating services. The trade-off is real -- a mediator can decay into a god object if you push *all* logic into it rather than just the cross-object coordination.

---

#### Iterator

The Iterator pattern provides sequential access to the elements of a collection without exposing its underlying representation. In Python this pattern is built into the language: any object implementing `__iter__` (and `__next__`) works in a `for` loop, and **generators** are the idiomatic, lazy way to produce iterators without writing a class. Laziness is the production payoff -- you can iterate a billion-row table or an infinite stream without materializing it in memory.

```python
from collections.abc import Iterator


def paginate(total: int, page_size: int) -> Iterator[list[int]]:
    """Lazy iterator over pages -- yields one page at a time, never the whole set."""
    page: list[int] = []
    for item in range(1, total + 1):
        page.append(item)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page  # final partial page


for batch in paginate(total=7, page_size=3):
    print(batch)
```

```text
[1, 2, 3]
[4, 5, 6]
[7]
```

**How to read this output:** The three batches were produced one at a time, on demand -- at no point did `paginate` build a list of all seven items, let alone all seven pages. Swap `total=7` for `total=10_000_000` and the memory footprint is unchanged: only one page exists at a time. This is exactly how you stream large query results (`queryset.iterator()` in Django, server-side cursors in psycopg), process a multi-gigabyte file line by line, or page through an external API without loading every record. The `yield` keyword turns the function into a generator whose execution suspends at each `yield` and resumes on the next iteration, which is what makes the laziness possible. Contrast with returning a fully-built list, which would force every page into memory before the first one could be processed.

---

#### Visitor

The Visitor pattern lets you add new operations to a set of object types **without modifying those types**. You separate the operation (the "visitor") from the structure it operates on, using double dispatch to pick the right behavior for each element type. It shines when the set of types is stable but you keep adding new operations (export, validate, price, render) over them. In Python, `functools.singledispatch` provides type-based dispatch that captures the essence of Visitor without the boilerplate `accept(visitor)` methods of the classic Java form.

```python
from dataclasses import dataclass
from functools import singledispatch


# Stable data types (e.g. an AST or a shape hierarchy) -- never modified to add ops
@dataclass
class Circle:
    radius: float


@dataclass
class Rectangle:
    width: float
    height: float


@dataclass
class Group:
    children: list


# A new operation = a new singledispatch function, no edits to the types above
@singledispatch
def area(shape) -> float:
    raise NotImplementedError(f"No area() for {type(shape).__name__}")


@area.register
def _(shape: Circle) -> float:
    return 3.14159 * shape.radius ** 2


@area.register
def _(shape: Rectangle) -> float:
    return shape.width * shape.height


@area.register
def _(shape: Group) -> float:
    return sum(area(child) for child in shape.children)  # recurses, like a visitor


drawing = Group([Circle(1.0), Rectangle(2.0, 3.0), Group([Circle(2.0)])])
print(round(area(drawing), 2))
```

```text
21.71
```

**How to read this output:** `area` dispatched to a different implementation for each element type -- circle, rectangle, and (recursively) nested group -- summing to `3.14 + 6.0 + 12.57 = 21.71`. The key property is that adding a *new operation* over these shapes (say `perimeter` or `to_svg`) means writing one new `singledispatch` function and zero changes to `Circle`, `Rectangle`, or `Group`. This is the classic use for AST processing -- a compiler keeps a fixed node hierarchy but constantly adds passes (type-check, optimize, emit code) as separate visitors. The trade-off is the dual of the open/closed tension: Visitor makes adding *operations* easy but adding a new *type* hard (you must update every visitor). Reach for it only when types are stable and operations proliferate; if the reverse is true, ordinary polymorphism (a method per type) is the better fit.

---

#### Repository

The Repository pattern mediates between the domain and data mapping layers, providing a collection-like interface for accessing domain objects. It encapsulates the logic needed to access data sources and centralizes query logic so that it is not scattered across the application.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class User:
    id: str | None
    email: str
    name: str
    is_active: bool = True


class UserRepository(ABC):
    """Port -- collection-like interface for User persistence."""
    @abstractmethod
    def find_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def find_active(self) -> list[User]: ...

    @abstractmethod
    def save(self, user: User) -> User: ...

    @abstractmethod
    def delete(self, user_id: str) -> None: ...


class DjangoUserRepository(UserRepository):
    """Adapter -- implements repository using Django ORM."""
    def find_by_id(self, user_id: str) -> User | None:
        from myapp.models import UserModel
        try:
            obj = UserModel.objects.get(pk=user_id)
            return User(id=str(obj.pk), email=obj.email, name=obj.name, is_active=obj.is_active)
        except UserModel.DoesNotExist:
            return None

    def find_by_email(self, email: str) -> User | None:
        from myapp.models import UserModel
        obj = UserModel.objects.filter(email=email).first()
        if obj is None:
            return None
        return User(id=str(obj.pk), email=obj.email, name=obj.name, is_active=obj.is_active)

    def find_active(self) -> list[User]:
        from myapp.models import UserModel
        return [
            User(id=str(obj.pk), email=obj.email, name=obj.name, is_active=obj.is_active)
            for obj in UserModel.objects.filter(is_active=True)
        ]

    def save(self, user: User) -> User:
        from myapp.models import UserModel
        obj, _ = UserModel.objects.update_or_create(
            pk=user.id,
            defaults={"email": user.email, "name": user.name, "is_active": user.is_active},
        )
        user.id = str(obj.pk)
        return user

    def delete(self, user_id: str) -> None:
        from myapp.models import UserModel
        UserModel.objects.filter(pk=user_id).delete()


class InMemoryUserRepository(UserRepository):
    """For testing -- no database needed."""
    def __init__(self):
        self._store: dict[str, User] = {}
        self._counter = 0

    def find_by_id(self, user_id: str) -> User | None:
        return self._store.get(user_id)

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    def find_active(self) -> list[User]:
        return [u for u in self._store.values() if u.is_active]

    def save(self, user: User) -> User:
        if user.id is None:
            self._counter += 1
            user.id = str(self._counter)
        self._store[user.id] = user
        return user

    def delete(self, user_id: str) -> None:
        self._store.pop(user_id, None)
```

The `InMemoryUserRepository` makes testing trivial -- no database setup, no migrations, fast test execution. The domain logic that depends on `UserRepository` does not know or care which implementation is behind it.

---

#### Unit of Work

The Unit of Work pattern tracks all changes made to objects during a business transaction and coordinates writing those changes to the database as a single atomic operation. Either all changes are committed, or all are rolled back.

```python
from abc import ABC, abstractmethod
from contextlib import contextmanager


class UnitOfWork(ABC):
    @abstractmethod
    def __enter__(self): ...

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb): ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...


class DjangoUnitOfWork(UnitOfWork):
    """Wraps Django's transaction.atomic()."""
    def __enter__(self):
        from django.db import transaction
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._atomic.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        pass  # Django auto-commits when exiting atomic() without exception

    def rollback(self) -> None:
        from django.db import transaction
        transaction.set_rollback(True)


# Usage in a service
class TransferService:
    def __init__(self, uow: UnitOfWork, account_repo):
        self.uow = uow
        self.account_repo = account_repo

    def transfer(self, from_id: str, to_id: str, amount: float) -> None:
        with self.uow:
            from_account = self.account_repo.find_by_id(from_id)
            to_account = self.account_repo.find_by_id(to_id)

            if from_account.balance < amount:
                raise ValueError("Insufficient funds")

            from_account.balance -= amount
            to_account.balance += amount

            self.account_repo.save(from_account)
            self.account_repo.save(to_account)
            # If anything fails, both saves are rolled back
```

Django's `transaction.atomic()` is the most common Unit of Work implementation in the Django ecosystem. SQLAlchemy provides a more explicit Unit of Work through its `Session` object.

---

#### CQRS (Command Query Responsibility Segregation)

CQRS separates the **read model** (optimized for queries) from the **write model** (optimized for business rules and data integrity). The write side uses a normalized domain model with validation and business rules. The read side uses denormalized projections optimized for specific queries.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


# ---- Write Side (Commands) ----

@dataclass
class CreateOrderCommand:
    customer_id: str
    items: list[dict]


@dataclass
class Order:
    """Write model -- enforces business rules."""
    id: str
    customer_id: str
    items: list[dict]
    status: str = "pending"
    total: float = 0.0
    created_at: datetime = None

    def calculate_total(self) -> None:
        self.total = sum(i["price"] * i["qty"] for i in self.items)

    def validate(self) -> None:
        if not self.items:
            raise ValueError("Order must have at least one item")
        if self.total <= 0:
            raise ValueError("Order total must be positive")


class CommandHandler:
    def __init__(self, write_repo, event_publisher):
        self.write_repo = write_repo
        self.event_publisher = event_publisher

    def handle_create_order(self, cmd: CreateOrderCommand) -> str:
        import uuid
        order = Order(
            id=str(uuid.uuid4()),
            customer_id=cmd.customer_id,
            items=cmd.items,
            created_at=datetime.now(),
        )
        order.calculate_total()
        order.validate()
        self.write_repo.save(order)
        self.event_publisher.publish("order.created", {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "total": order.total,
            "item_count": len(order.items),
        })
        return order.id


# ---- Read Side (Queries) ----

@dataclass
class OrderSummary:
    """Read model -- denormalized for fast display."""
    order_id: str
    customer_name: str  # Denormalized: no join needed
    item_count: int
    total: float
    status: str
    created_at: str


class OrderQueryService:
    """Read service -- optimized for query patterns."""
    def __init__(self, read_repo):
        self.read_repo = read_repo

    def get_recent_orders(self, limit: int = 20) -> list[OrderSummary]:
        return self.read_repo.find_recent(limit)

    def get_orders_by_customer(self, customer_id: str) -> list[OrderSummary]:
        return self.read_repo.find_by_customer(customer_id)

    def get_order_detail(self, order_id: str) -> OrderSummary | None:
        return self.read_repo.find_by_id(order_id)


# ---- Event Handler updates read model ----

class OrderProjection:
    """Listens for write-side events and updates the read model."""
    def __init__(self, read_repo, customer_repo):
        self.read_repo = read_repo
        self.customer_repo = customer_repo

    def on_order_created(self, event_data: dict) -> None:
        customer = self.customer_repo.find_by_id(event_data["customer_id"])
        summary = OrderSummary(
            order_id=event_data["order_id"],
            customer_name=customer.name,  # Denormalize at write time
            item_count=event_data["item_count"],
            total=event_data["total"],
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        self.read_repo.save(summary)
```

CQRS adds significant complexity. Use it when read and write patterns differ dramatically (e.g., writes go to a normalized relational database, reads come from Elasticsearch or Redis), when read and write loads need to scale independently, or when paired with Event Sourcing. For most CRUD applications, a single model serves both reads and writes just fine.

> **Key Takeaway:** Behavioral patterns manage complex interactions between objects. Observer decouples event producers from consumers. Strategy makes algorithms interchangeable. Command enables undo/redo and task queuing. Chain of Responsibility builds processing pipelines. State makes state machines explicit. Repository and Unit of Work abstract persistence. CQRS separates read and write concerns. Choose patterns based on the problem you are solving, not for their own sake.

---

### Enterprise Application Patterns

Beyond the GoF catalog, a set of patterns (largely from Martin Fowler's *Patterns of Enterprise Application Architecture*) address the recurring concerns of data-backed business applications: moving data across boundaries, expressing business rules reusably, and choosing how domain objects relate to the database. Repository, Unit of Work, and Service Layer were covered with the behavioral patterns above; the remaining ones round out the toolkit.

---

#### DTO (Data Transfer Object)

A DTO is a flat, serializable object whose only job is to **carry data across a boundary** -- an API request/response, a queue payload, a cache entry. It is deliberately behavior-free and is kept *separate from your domain entities*. The point is decoupling: your wire format (the contract clients depend on) should not be your database schema or your rich domain model, because then any internal refactor becomes a breaking API change, and any internal field accidentally leaks to clients.

```python
from dataclasses import dataclass


# ---- Rich domain entity: behavior + invariants + internal fields ----
class User:
    def __init__(self, id: int, email: str, password_hash: str, is_admin: bool):
        self.id = id
        self.email = email
        self.password_hash = password_hash   # MUST NOT leak to clients
        self.is_admin = is_admin

    def can_moderate(self) -> bool:
        return self.is_admin


# ---- DTO: only the fields the API contract promises ----
@dataclass(frozen=True)
class UserResponseDTO:
    id: int
    email: str
    role: str

    @classmethod
    def from_entity(cls, user: User) -> "UserResponseDTO":
        return cls(
            id=user.id,
            email=user.email,
            role="admin" if user.is_admin else "member",
        )


user = User(1, "a@b.com", password_hash="$2b$...secret", is_admin=True)
print(UserResponseDTO.from_entity(user))
```

```text
UserResponseDTO(id=1, email='a@b.com', role='admin')
```

**How to read this output:** The DTO carried `id`, `email`, and a derived `role` -- and crucially, `password_hash` is *absent*. The boundary translation in `from_entity` is what guarantees that an internal field can never be serialized to a client by accident, no matter how the `User` entity grows later. The `is_admin` boolean was also reshaped into a `role` string, so the public contract is expressed in client-facing terms rather than mirroring the internal flag. In a Django/FastAPI app this role is played by DRF serializers and Pydantic models; the discipline they enforce -- explicitly listing output fields rather than dumping the model -- is precisely why "just return the ORM object" is a security and compatibility footgun.

---

#### Specification

The Specification pattern encapsulates a business rule or query predicate as a **composable object**, so the rule can be named, reused, and combined with boolean logic (`and`, `or`, `not`) rather than being duplicated as ad-hoc `if` conditions and `WHERE` clauses scattered across the codebase. The same specification can drive both in-memory validation ("does this object satisfy the rule?") and querying ("fetch all objects satisfying the rule").

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Customer:
    name: str
    orders_count: int
    is_active: bool


class Specification(ABC):
    @abstractmethod
    def is_satisfied_by(self, candidate) -> bool: ...

    def __and__(self, other: "Specification") -> "Specification":
        return AndSpec(self, other)

    def __invert__(self) -> "Specification":
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, a: Specification, b: Specification):
        self.a, self.b = a, b

    def is_satisfied_by(self, candidate) -> bool:
        return self.a.is_satisfied_by(candidate) and self.b.is_satisfied_by(candidate)


class NotSpec(Specification):
    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, candidate) -> bool:
        return not self.spec.is_satisfied_by(candidate)


class IsActive(Specification):
    def is_satisfied_by(self, c: Customer) -> bool:
        return c.is_active


class IsVip(Specification):
    def is_satisfied_by(self, c: Customer) -> bool:
        return c.orders_count >= 10


# Compose rules with boolean operators -- each rule has one definition
active_vip = IsActive() & IsVip()
churn_risk = ~IsActive() & IsVip()   # was a VIP, now inactive

customers = [
    Customer("Alice", orders_count=12, is_active=True),
    Customer("Bob", orders_count=15, is_active=False),
    Customer("Carol", orders_count=2, is_active=True),
]
print([c.name for c in customers if active_vip.is_satisfied_by(c)])
print([c.name for c in customers if churn_risk.is_satisfied_by(c)])
```

```text
['Alice']
['Bob']
```

**How to read this output:** The two queries reused the *same* `IsActive` and `IsVip` building blocks, combined differently -- `active_vip` matched only Alice, while `churn_risk` (`~IsActive() & IsVip()`) surfaced Bob, the lapsed high-value customer. The win is single-definition rules: "what makes a VIP" lives in exactly one class, so a marketing query, a validation check, and a report all agree, and changing the threshold from 10 to 20 is a one-line edit instead of a hunt through the codebase. The trade-off is that an in-memory `is_satisfied_by` cannot run in the database; production implementations usually add a second method that translates the specification into a SQLAlchemy/Django `Q` expression so the same rule object can also build an efficient query.

---

#### Data Mapper vs. Active Record

These are the two dominant patterns for connecting domain objects to relational tables, and the choice shapes your whole persistence strategy.

**Active Record** -- the object *is* the table row and knows how to persist itself. The model carries both data and CRUD behavior (`user.save()`, `User.objects.filter(...)`). This is Django's ORM and Rails. It is fast to build, intuitive, and ideal for CRUD-heavy applications. The cost: the domain model is fused to the database, so business logic and persistence concerns mix in the same class, pure unit testing requires a database (or heavy mocking), and the model's shape is dictated by the table's shape.

**Data Mapper** -- a *separate* layer moves data between objects and the database, and the domain object has **no knowledge** that a database exists. SQLAlchemy's classic/imperative mapping and the Repository pattern embody this. The cost is more moving parts; the benefit is a domain model that is pure Python (testable with zero I/O), free to differ from the table structure, and the natural fit for Clean/Hexagonal architecture where the domain must not depend on infrastructure.

```python
# ---- Active Record (Django) ----
# The model knows how to persist itself; data + behavior + persistence fused.
class Order(models.Model):
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="draft")

    def place(self):
        self.status = "placed"
        self.save()           # the object persists ITSELF


# ---- Data Mapper (pure domain + repository) ----
# The domain object has no idea a database exists.
@dataclass
class Order:                  # plain Python, no ORM base class
    total: float
    status: str = "draft"

    def place(self) -> None:
        self.status = "placed"   # pure state change, no I/O


class OrderRepository:        # the mapper/repository owns persistence
    def save(self, order: Order) -> None:
        ...  # translate the domain object into rows and write them
```

**How to choose:** reach for Active Record when the app is mostly CRUD, the domain logic is thin, and developer velocity matters most -- which describes the majority of Django projects, and fighting the ORM there is usually a mistake. Reach for Data Mapper when the domain is rich and rules-heavy, when you need the domain model decoupled from the schema, or when fast, database-free unit tests of business logic are a priority. A common pragmatic middle path in Django is to keep thin Active Record models for persistence but push real business logic into service classes and plain domain objects, getting most of the testability benefit without abandoning the ORM.

---

#### Dependency Injection

Dependency Injection (DI) means an object receives its collaborators from the outside -- as constructor arguments or function parameters -- rather than constructing them internally. This is the practical mechanism behind the Dependency Inversion Principle: it is what lets you pass a real adapter in production and a fake in tests through the same code path, and it is visible throughout this chapter (every `__init__(self, repo: Repository)` above is DI). In Python, explicit constructor injection is usually all you need; for larger apps, frameworks help -- FastAPI's `Depends`, or containers like `dependency-injector` that wire object graphs from a central configuration. The anti-pattern to avoid is the Service Locator, where objects reach into a global registry to *fetch* their dependencies, which hides the dependency graph and reintroduces the global-state problems DI was meant to solve.

> **Key Takeaway:** Enterprise patterns deal with the realities of data-backed applications. DTOs keep your API contract decoupled from your schema. Specifications make business rules reusable and composable. The Data Mapper vs. Active Record choice trades developer velocity (Active Record) against domain purity and testability (Data Mapper) -- pick by domain complexity. Dependency Injection ties it all together by making collaborators swappable.

---

### Concurrency & Reliability Patterns

Distributed and concurrent systems fail in ways single-threaded programs do not: dependencies time out, queues fill up, the same message arrives twice, one slow service drags down everything that calls it. The following patterns are the standard toolkit for building systems that degrade gracefully instead of collapsing. (Several appear again in the Architectural Styles chapter in a distributed-systems context; here the focus is the in-process and client-side mechanics.)

---

#### Producer-Consumer

The Producer-Consumer pattern decouples the rate of *producing* work from the rate of *consuming* it by placing a buffer (queue) between them. Producers enqueue items and move on; consumers dequeue and process at their own pace. This smooths bursts, lets you scale producers and consumers independently, and is the foundation of every task queue.

```python
import queue
import threading
import time

work: queue.Queue[int | None] = queue.Queue(maxsize=5)  # bounded buffer


def producer() -> None:
    for i in range(3):
        work.put(i)               # blocks if the queue is full -> backpressure
        print(f"produced {i}")
    work.put(None)                # sentinel signals "no more work"


def consumer() -> None:
    while True:
        item = work.get()
        if item is None:
            break
        time.sleep(0.05)          # consumer is slower than producer
        print(f"consumed {item}")


t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start(); t2.start()
t1.join(); t2.join()
```

```text
produced 0
produced 1
produced 2
consumed 0
consumed 1
consumed 2
```

**How to read this output:** All three items were *produced* before the first was *consumed* -- the queue absorbed the burst because the consumer is slower (`time.sleep`). That buffering is the entire value: a traffic spike fills the queue instead of overwhelming the slow downstream worker, and the producer is not blocked waiting for each item to finish processing. The `maxsize=5` is the safety valve -- once the buffer fills, `work.put()` blocks, applying *backpressure* to the producer rather than letting the queue grow unbounded and exhaust memory. This is exactly how Celery (broker between web workers and task workers), Kafka, and `asyncio.Queue`-based pipelines decouple request handling from background processing.

---

#### Thread Pool / Worker Pool

A worker pool maintains a fixed set of threads (or processes) that pull tasks from a queue, bounding concurrency so you never spawn an unlimited number of workers and exhaust CPU, memory, or downstream connection limits. Python's `concurrent.futures.ThreadPoolExecutor` is the standard implementation.

```python
from concurrent.futures import ThreadPoolExecutor
import time


def fetch(url: str) -> str:
    time.sleep(0.1)           # simulate I/O-bound work
    return f"200 OK {url}"


urls = [f"/api/item/{i}" for i in range(6)]

with ThreadPoolExecutor(max_workers=3) as pool:   # at most 3 concurrent fetches
    results = list(pool.map(fetch, urls))

for r in results:
    print(r)
```

```text
200 OK /api/item/0
200 OK /api/item/1
200 OK /api/item/2
200 OK /api/item/3
200 OK /api/item/4
200 OK /api/item/5
```

**How to read this output:** Six tasks completed but only three ran at any instant -- `max_workers=3` caps concurrency. With six `0.1s` I/O-bound tasks across three workers, total wall time is roughly `2 x 0.1s = 0.2s` (two waves of three) instead of `6 x 0.1s = 0.6s` serial, yet you never opened six simultaneous connections. That bound is the production point: an unbounded "thread per task" approach will, under load, open thousands of connections and take down the very database or API you are calling. Note the GIL caveat -- a thread pool only speeds up *I/O-bound* work (network, disk) because the GIL is released during I/O; for CPU-bound work you need `ProcessPoolExecutor` instead.

---

#### Future / Promise

A Future is a placeholder for a result that does not exist yet -- you receive it immediately when you submit async work, and later read its value (or exception) once the work completes. It lets you launch work, keep doing other things, and collect results when convenient. Python exposes this as `concurrent.futures.Future` (thread/process pools) and `asyncio.Future`/awaitables (async I/O).

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def slow_square(n: int) -> int:
    time.sleep(0.1)
    return n * n


with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(slow_square, n): n for n in range(4)}
    # as_completed yields each Future the moment IT finishes, not in submit order
    for fut in as_completed(futures):
        print(f"{futures[fut]}^2 = {fut.result()}")
```

```text
2^2 = 4
0^2 = 0
3^2 = 9
1^2 = 1
```

**How to read this output:** The results arrive in *completion* order, not submission order (your exact ordering will vary run to run) -- `submit()` returned a Future instantly and `as_completed` surfaced each one the moment its thread finished. This is the production payoff: you fan out independent calls (query three services, hit several shards) concurrently and process whichever responds first, instead of blocking on them in a fixed sequence. `fut.result()` returns the value or *re-raises* any exception the worker hit, so error handling stays at the collection point rather than being swallowed in the worker thread.

---

#### Circuit Breaker

A Circuit Breaker stops calling a failing dependency so you fail *fast* instead of piling up doomed requests that hold threads and connections while waiting to time out. It models a circuit with three states: **closed** (calls flow normally, failures are counted), **open** (the failure threshold was crossed -- calls are rejected immediately without even trying), and **half-open** (after a cooldown, a trial call is allowed; success closes the circuit, failure re-opens it).

```python
import time


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 5.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "closed"
        self.opened_at = 0.0

    def call(self, func, *args):
        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.reset_timeout:
                self.state = "half-open"          # time to test recovery
            else:
                raise RuntimeError("Circuit OPEN -- failing fast")
        try:
            result = func(*args)
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    def _on_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = time.monotonic()
            print(f"-> circuit OPEN after {self.failures} failures")

    def _on_success(self) -> None:
        if self.state == "half-open":
            print("-> circuit CLOSED (recovered)")
        self.failures = 0
        self.state = "closed"


def flaky() -> str:
    raise ConnectionError("downstream down")


cb = CircuitBreaker(failure_threshold=3)
for attempt in range(5):
    try:
        cb.call(flaky)
    except Exception as e:
        print(f"attempt {attempt}: {type(e).__name__}: {e}")
```

```text
attempt 0: ConnectionError: downstream down
attempt 1: ConnectionError: downstream down
-> circuit OPEN after 3 failures
attempt 2: ConnectionError: downstream down
attempt 3: RuntimeError: Circuit OPEN -- failing fast
attempt 4: RuntimeError: Circuit OPEN -- failing fast
```

**How to read this output:** The first three attempts actually *called* the failing dependency (`ConnectionError`), but once the third failure tripped the threshold the circuit opened, and attempts 3 and 4 were rejected *instantly* with `Circuit OPEN -- failing fast` -- they never touched the dead backend. That instant rejection is the whole purpose: when a downstream is down, continuing to call it just ties up your threads and connection pool waiting for timeouts, which is how one failing dependency cascades into a full outage of the caller. After `reset_timeout`, the breaker would move to half-open and let one trial call probe whether the dependency recovered. Libraries like `pybreaker` and the retry library `tenacity` provide production-grade versions; pair a breaker with retries so retries stop hammering a dependency the breaker has already declared dead.

---

#### Bulkhead

Named after the watertight compartments that stop a breached ship from flooding entirely, the Bulkhead pattern isolates resources so a failure in one area cannot consume *all* of them. You give each dependency (or tenant, or request class) its own bounded resource pool -- separate thread pools, separate connection pools, separate rate limits -- so that one slow or failing dependency exhausts only its own compartment.

```python
from concurrent.futures import ThreadPoolExecutor

# Each downstream gets its own bounded pool -- one cannot starve the others.
pools = {
    "payments": ThreadPoolExecutor(max_workers=5),
    "recommendations": ThreadPoolExecutor(max_workers=2),  # non-critical, small
}


def call_dependency(name: str, func, *args):
    return pools[name].submit(func, *args)
```

The payoff is failure isolation: if the recommendations service hangs, it can tie up at most its 2 dedicated workers -- the 5 payment workers keep flowing, so checkout still works while recommendations degrade. Without bulkheads, a single hung dependency called from a shared global thread pool will, under load, consume every worker, and *every* feature stalls because one non-critical service is slow. This is why production systems give critical and non-critical dependencies separate pools (and is what a service mesh enforces at the network level).

---

#### Backpressure

Backpressure is the mechanism by which an overwhelmed consumer signals upstream producers to *slow down*, rather than silently dropping work or growing an unbounded buffer until it runs out of memory. The simplest form is a bounded queue: when it fills, `put()` blocks, which naturally throttles the producer (as in the Producer-Consumer example above). At the network level it appears as HTTP `429 Too Many Requests`, TCP flow control, or a queue depth limit that rejects new work. The anti-pattern it prevents is the unbounded queue: an in-memory queue with no size limit will happily accept work faster than it can be processed until the process is OOM-killed -- turning a transient slowdown into a crash. The rule: every buffer between a fast producer and a slow consumer must be bounded, and the system must have a defined behavior (block, shed load, or reject) for when it is full.

---

#### Retry with Backoff and Jitter

Retrying a failed operation is essential for surviving transient faults (a brief network blip, a momentary timeout), but a naive retry loop is dangerous. Three rules make retries safe:

1. **Only retry idempotent operations** -- retrying a non-idempotent write can double-charge a card or create duplicate records. (See Idempotency below.)
2. **Use exponential backoff with jitter** -- wait progressively longer between attempts (`1s, 2s, 4s...`) so you do not hammer a struggling service, and add randomness so that many clients retrying after a shared outage do not all reconnect in lockstep (the "thundering herd" that re-kills the recovering service).
3. **Cap retries and enforce a timeout budget** -- a total deadline across all attempts, so a request does not retry forever while the caller (and the user) waits.

```python
import random
import time


def retry_with_backoff(func, max_attempts: int = 5, base: float = 0.5, cap: float = 8.0):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            # exponential backoff with full jitter
            delay = min(cap, base * (2 ** attempt))
            sleep = random.uniform(0, delay)
            print(f"attempt {attempt} failed ({e}); retrying in {sleep:.2f}s")
            time.sleep(sleep)
```

```text
attempt 0 failed (timeout); retrying in 0.31s
attempt 1 failed (timeout); retrying in 0.74s
attempt 2 failed (timeout); retrying in 2.18s
```

**How to read this output:** Each retry waited longer than the last (the `base * 2**attempt` growth) and each delay was *randomized* within that window (full jitter) -- your exact numbers will differ every run. The growing delay protects a struggling dependency from being pounded while it tries to recover; the jitter is the subtle but critical part, because if a thousand clients all failed at the same instant and retried on the same fixed schedule, they would synchronize into repeated traffic spikes that re-overwhelm the service. AWS's published guidance and libraries like `tenacity` implement exactly this. Combine retries with a circuit breaker (stop retrying a dependency that is comprehensively down) and a timeout budget (so the total retry time stays bounded).

---

#### Idempotency and Deduplication

An operation is idempotent if performing it multiple times has the same effect as performing it once. This is the property that makes retries and at-least-once message delivery *safe* -- if a client retries a payment because the response was lost (but the charge actually succeeded), an idempotent endpoint recognizes the duplicate and returns the original result instead of charging again. The standard mechanism is an **idempotency key**: the client sends a unique key with the request, and the server records it; a second request with the same key returns the stored result rather than re-executing.

```python
class PaymentService:
    def __init__(self):
        self._processed: dict[str, dict] = {}   # idempotency_key -> result

    def charge(self, idempotency_key: str, amount: float) -> dict:
        if idempotency_key in self._processed:
            print(f"duplicate {idempotency_key}: returning stored result")
            return self._processed[idempotency_key]      # no second charge
        result = {"status": "charged", "amount": amount, "txn": "txn_001"}
        self._processed[idempotency_key] = result
        print(f"charged {amount}")
        return result


svc = PaymentService()
print(svc.charge("key-abc", 50.0))
print(svc.charge("key-abc", 50.0))   # client retried with the SAME key
```

```text
charged 50.0
{'status': 'charged', 'amount': 50.0, 'txn': 'txn_001'}
duplicate key-abc: returning stored result
{'status': 'charged', 'amount': 50.0, 'txn': 'txn_001'}
```

**How to read this output:** The amount was charged exactly once even though `charge` was called twice with the same key -- the second call short-circuited and returned the *stored* result (same `txn_001`). This is the production-critical guarantee: networks drop responses, so clients *will* retry, and at-least-once message brokers *will* redeliver; without an idempotency check those duplicates become double charges and duplicate orders. Other techniques achieve the same property: natural-key `INSERT ... ON CONFLICT DO NOTHING` upserts, a dedup table of processed message IDs (the inbox pattern in the Architectural Styles chapter), or designing the operation to be naturally idempotent (`SET status = 'shipped'` is idempotent; `balance = balance + 10` is not). In production the `_processed` map is a database table or Redis with a TTL, not an in-memory dict.

---

#### Leader Election / Leases

When you run multiple identical instances of a service for availability, some tasks must be performed by **exactly one** instance -- a scheduled cron job, a log compaction, a queue cleanup. Running them on every replica causes duplicate work or corruption. Leader election ensures one instance is designated the leader and only it performs the singleton task. The common implementation is a **lease** (a time-bounded distributed lock): an instance acquires a lock with a TTL, periodically renews it while it holds leadership, and if it crashes the lease expires and another instance takes over -- avoiding the deadlock of a permanent lock held by a dead node.

```python
import time


class Lease:
    """Sketch of a lease-based leader election (real version uses Redis/etcd)."""
    def __init__(self, store: dict, key: str, ttl: float):
        self.store, self.key, self.ttl = store, key, ttl

    def try_acquire(self, node_id: str) -> bool:
        now = time.monotonic()
        holder = self.store.get(self.key)
        if holder is None or holder["expires"] < now:      # free or expired
            self.store[self.key] = {"node": node_id, "expires": now + self.ttl}
            return True
        if holder["node"] == node_id:                      # already mine -> renew the lease
            holder["expires"] = now + self.ttl
            return True
        return False


store: dict = {}
lease = Lease(store, "cron-leader", ttl=10.0)
print("node-A acquires:", lease.try_acquire("node-A"))
print("node-B acquires:", lease.try_acquire("node-B"))   # A still holds it
```

```text
node-A acquires: True
node-B acquires: False
```

**How to read this output:** Only `node-A` won the lease; `node-B` was refused because the lock is held and unexpired -- so a cron job guarded by this lease runs on exactly one node even though both are alive. The TTL is the safety mechanism that distinguishes a lease from a plain lock: if node-A crashes without releasing it, the `expires` timestamp lapses and node-B's next `try_acquire` succeeds, so leadership fails over automatically instead of being stuck forever on a dead node. Production systems use the atomic primitives that make this race-free -- Redis `SET NX PX`, etcd/ZooKeeper leases, Kubernetes `Lease` objects, or PostgreSQL advisory locks -- because the naive read-then-write shown here has a check-then-act race that a real distributed lock must close.

> **Key Takeaway:** Reliability patterns assume failure is normal. Bound everything -- worker pools, queues (backpressure), retries (caps + timeout budgets). Fail fast on dead dependencies (circuit breaker) and isolate them (bulkhead) so one failure does not cascade. Make operations idempotent so retries and redeliveries are safe, and use leases when exactly one instance must act. These patterns are what separate a system that degrades gracefully from one that collapses under its first dependency failure.

*Last reviewed: 2026-06-08*
