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

#### Singleton

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

> **Key Takeaway:** Creational patterns solve the problem of "how do I create objects flexibly?" In Python, many of these patterns are simpler than their Java equivalents because of first-class functions, duck typing, and the `copy` module. Use Factory functions for runtime type selection, Builder for complex construction, and prefer module-level instances or dependency injection over Singleton.

---

### Structural Patterns

Structural patterns deal with object composition -- how classes and objects are assembled to form larger structures while keeping the structure flexible and efficient.

---

#### Adapter

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

> **Key Takeaway:** Structural patterns help you compose objects into larger structures while keeping things flexible. Adapter bridges incompatible interfaces, Decorator adds behavior without modifying classes, Facade simplifies complex subsystems, Proxy controls access, and Composite handles tree structures. In Python, duck typing and Protocols make these patterns lighter than in statically-typed languages.

---

### Behavioral Patterns

Behavioral patterns deal with algorithms and the assignment of responsibilities between objects. They describe not just patterns of objects but also patterns of communication between them.

---

#### Observer

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
