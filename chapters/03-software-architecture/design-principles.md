[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 3.1 Design Principles

> [!NOTE]
> **Beginner's Mental Model — SOLID Principles:**
> Think of SOLID as the blueprint for a professional restaurant kitchen. Instead of one chaotic chef doing everything, tasks are divided: a pastry chef only bakes (Single Responsibility); you customize dishes by adding toppings, not by rebuilding the recipe (Open/Closed); you can swap whole milk for oat milk without rewriting the baking instructions (Liskov Substitution); a waiter only needs the ordering menu, not the dishwasher's manual (Interface Segregation); and the kitchen orders ingredients through a general "supplier contract" rather than depending on one specific farm (Dependency Inversion).

### SOLID Principles

When you build a house, you do not glue the light bulbs directly to the electrical wires, nor do you cement the refrigerator into the kitchen floor. If you did, replacing a burnt-out bulb would require calling an electrician to splice wires, and upgrading your fridge would mean tearing down a wall. Instead, we use standardized sockets, plugs, and modular spaces. The SOLID principles are a set of five design guidelines that bring this same modularity to software. They ensure that our codebase is built from independent, swappable parts rather than a single, tangled web of code. By following these rules, we can change or expand one part of our application—like switching how we calculate discounts or saving data to a different database—without triggering a chain reaction of bugs throughout the rest of the system.

#### S -- Single Responsibility Principle (SRP)

A class or module should have **one and only one reason to change**. This does not mean "does one thing" in a narrow sense. Rather, it means that exactly one actor or stakeholder should be the source of requirements changes for that module. When a module serves two different stakeholders, a change requested by one stakeholder risks breaking functionality for the other.

**Violation -- one class serving two stakeholders:**

```python
class Employee:
    def __init__(self, name: str, hours_worked: float, hourly_rate: float):
        self.name = name
        self.hours_worked = hours_worked
        self.hourly_rate = hourly_rate

    def calculate_pay(self) -> float:
        """Used by the Accounting department."""
        return self.hours_worked * self.hourly_rate

    def generate_performance_report(self) -> str:
        """Used by the HR department."""
        return f"Report for {self.name}: {self.hours_worked} hours worked"

    def save_to_database(self) -> None:
        """Used by the DBA / infrastructure team."""
        print(f"INSERT INTO employees VALUES ('{self.name}', ...)")
```

Here, the `Employee` class has three reasons to change: Accounting might change the pay formula, HR might change the report format, and the DBA might change the database schema. A change for one stakeholder could introduce bugs for another.

**Fix -- separate responsibilities into distinct classes:**

```python
class Employee:
    """Pure domain object -- holds data only."""
    def __init__(self, name: str, hours_worked: float, hourly_rate: float):
        self.name = name
        self.hours_worked = hours_worked
        self.hourly_rate = hourly_rate


class PayCalculator:
    """Owned by Accounting."""
    def calculate_pay(self, employee: Employee) -> float:
        return employee.hours_worked * employee.hourly_rate


class PerformanceReporter:
    """Owned by HR."""
    def generate_report(self, employee: Employee) -> str:
        return f"Report for {employee.name}: {employee.hours_worked} hours worked"


class EmployeeRepository:
    """Owned by Infrastructure / DBA."""
    def save(self, employee: Employee) -> None:
        print(f"INSERT INTO employees VALUES ('{employee.name}', ...)")
```

Now each class has exactly one reason to change. In a Django project, this maps naturally: a model for the domain object, a service class for business logic, a serializer or view for presentation, and the ORM layer for persistence.

---

#### O -- Open/Closed Principle (OCP)

Software entities should be **open for extension** but **closed for modification**. When new behavior is needed, you should be able to add it by writing new code rather than modifying existing, tested code. This minimizes the risk of introducing regressions. The classic mechanism is the Strategy pattern: define an interface, then plug in new implementations.

**Violation -- adding a new discount type requires editing existing code:**

```python
class DiscountCalculator:
    def calculate(self, order_total: float, discount_type: str) -> float:
        if discount_type == "percentage":
            return order_total * 0.10
        elif discount_type == "flat":
            return 5.00
        elif discount_type == "bogo":
            return order_total * 0.50
        # Every new discount type means editing THIS function
        else:
            return 0.0
```

Every new discount type requires modifying `calculate()`. This violates OCP because existing tested code must be changed.

**Fix -- use a strategy pattern so new discount types are added without modifying existing code:**

```python
from abc import ABC, abstractmethod


class DiscountStrategy(ABC):
    @abstractmethod
    def calculate(self, order_total: float) -> float:
        ...


class PercentageDiscount(DiscountStrategy):
    def __init__(self, rate: float = 0.10):
        self.rate = rate

    def calculate(self, order_total: float) -> float:
        return order_total * self.rate


class FlatDiscount(DiscountStrategy):
    def __init__(self, amount: float = 5.00):
        self.amount = amount

    def calculate(self, order_total: float) -> float:
        return self.amount


class BogoDiscount(DiscountStrategy):
    def calculate(self, order_total: float) -> float:
        return order_total * 0.50


class DiscountCalculator:
    def __init__(self, strategy: DiscountStrategy):
        self.strategy = strategy

    def calculate(self, order_total: float) -> float:
        return self.strategy.calculate(order_total)


# Adding a new discount is a new class -- no modification to existing code:
class LoyaltyDiscount(DiscountStrategy):
    def calculate(self, order_total: float) -> float:
        return order_total * 0.15
```

In a Django project, this often appears when handling different payment providers, notification channels, or export formats. Define an abstract base, then register new implementations via settings or a registry dict.

---

#### L -- Liskov Substitution Principle (LSP)

Subtypes must be **substitutable for their base types** without altering the correctness of the program. If a function works with a base class, it should work with any subclass without surprises. Violations arise when a subclass changes behavior in ways the caller does not expect -- throwing unexpected exceptions, ignoring inputs, or breaking contracts.

**Violation -- the classic Rectangle/Square problem:**

```python
class Rectangle:
    def __init__(self, width: float, height: float):
        self._width = width
        self._height = height

    @property
    def width(self) -> float:
        return self._width

    @width.setter
    def width(self, value: float) -> None:
        self._width = value

    @property
    def height(self) -> float:
        return self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = value

    def area(self) -> float:
        return self._width * self._height


class Square(Rectangle):
    """A square IS-A rectangle... or is it?"""
    @Rectangle.width.setter
    def width(self, value: float) -> None:
        self._width = value
        self._height = value  # Surprise! Setting width also changes height

    @Rectangle.height.setter
    def height(self, value: float) -> None:
        self._width = value
        self._height = value


def double_width(rect: Rectangle) -> None:
    """Caller assumes width and height are independent."""
    rect.width = rect.width * 2


r = Rectangle(4, 5)
double_width(r)
print(r.area())  # 40 -- correct

s = Square(4, 4)
double_width(s)
print(s.area())  # Expected 32 (8*4), got 64 (8*8) -- LSP violation!
```

**Fix -- use composition or separate hierarchies:**

```python
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        ...


class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height


class Square(Shape):
    def __init__(self, side: float):
        self.side = side

    def area(self) -> float:
        return self.side ** 2
```

Now `Square` is not a subtype of `Rectangle`. Both implement `Shape`, and neither violates the caller's expectations. Design by contract: if the base class promises independent width/height, every subclass must honor that promise.

---

#### I -- Interface Segregation Principle (ISP)

Clients should not be forced to depend on interfaces they do not use. A single large interface forces implementors to provide stub methods for operations they do not support. Many small, focused interfaces are preferable to one monolithic one.

**Violation -- one fat interface for all workers:**

```python
from abc import ABC, abstractmethod


class Worker(ABC):
    @abstractmethod
    def write_code(self) -> None: ...

    @abstractmethod
    def review_code(self) -> None: ...

    @abstractmethod
    def manage_team(self) -> None: ...

    @abstractmethod
    def do_accounting(self) -> None: ...


class Developer(Worker):
    def write_code(self) -> None:
        print("Writing code")

    def review_code(self) -> None:
        print("Reviewing code")

    def manage_team(self) -> None:
        pass  # Not my job, but forced to implement

    def do_accounting(self) -> None:
        pass  # Not my job either
```

**Fix -- split into focused interfaces (Python Protocols work great here):**

```python
from typing import Protocol


class Coder(Protocol):
    def write_code(self) -> None: ...


class Reviewer(Protocol):
    def review_code(self) -> None: ...


class Manager(Protocol):
    def manage_team(self) -> None: ...


class Accountant(Protocol):
    def do_accounting(self) -> None: ...


class Developer:
    """Implements only the interfaces it actually supports."""
    def write_code(self) -> None:
        print("Writing code")

    def review_code(self) -> None:
        print("Reviewing code")


class TeamLead:
    """Implements Coder, Reviewer, and Manager -- but not Accountant."""
    def write_code(self) -> None:
        print("Writing code")

    def review_code(self) -> None:
        print("Reviewing code")

    def manage_team(self) -> None:
        print("Managing team")


def assign_coding_task(coder: Coder) -> None:
    """Accepts anything that can code -- does not care about other abilities."""
    coder.write_code()


assign_coding_task(Developer())
assign_coding_task(TeamLead())
```

Running the two calls at the bottom prints:

```text
Writing code
Writing code
```

**What's happening:** Both `Developer` and `TeamLead` satisfy the `Coder` protocol because each has a `write_code()` method -- and crucially, neither inherits from `Coder`. With `typing.Protocol`, conformance is *structural* (duck typing checked by the type checker), so `assign_coding_task` accepts any object shaped like a `Coder` without a declared base class. In production this is why you can pass a real adapter in deployment and a hand-rolled fake in tests through the same function signature, with `mypy` still catching a missing `write_code` at lint time rather than at 3 a.m. The `Manager`/`Accountant` capabilities a `TeamLead` may or may not have are simply irrelevant to this call site -- which is the entire point of segregating interfaces.

In a Django project, ISP shows up when you define serializers. Rather than one giant serializer with every field, create purpose-specific serializers: `UserListSerializer` (few fields), `UserDetailSerializer` (more fields), `UserAdminSerializer` (all fields).

---

#### D -- Dependency Inversion Principle (DIP)

High-level modules should not depend on low-level modules. Both should depend on **abstractions**. Abstractions should not depend on details; details should depend on abstractions. This decouples your business logic from infrastructure concerns, making it testable and swappable.

**Violation -- business logic directly depends on a concrete database implementation:**

```python
import sqlite3


class OrderService:
    def __init__(self):
        # High-level module directly depends on low-level module
        self.connection = sqlite3.connect("orders.db")

    def place_order(self, order_data: dict) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO orders (product, qty) VALUES (?, ?)",
            (order_data["product"], order_data["qty"]),
        )
        self.connection.commit()
```

Testing `OrderService` requires a real SQLite database. Switching to PostgreSQL means rewriting the service.

**Fix -- depend on an abstraction, inject the implementation:**

```python
from abc import ABC, abstractmethod


class OrderRepository(ABC):
    """Abstraction -- owned by the high-level module."""
    @abstractmethod
    def save(self, order_data: dict) -> None: ...


class SqliteOrderRepository(OrderRepository):
    """Low-level detail -- implements the abstraction."""
    def __init__(self, db_path: str = "orders.db"):
        import sqlite3
        self.connection = sqlite3.connect(db_path)

    def save(self, order_data: dict) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO orders (product, qty) VALUES (?, ?)",
            (order_data["product"], order_data["qty"]),
        )
        self.connection.commit()


class OrderService:
    """High-level module depends on abstraction, not on SQLite."""
    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def place_order(self, order_data: dict) -> None:
        # Business validation here...
        self.repository.save(order_data)


# In production:
service = OrderService(SqliteOrderRepository())

# In tests:
class FakeOrderRepository(OrderRepository):
    def __init__(self):
        self.saved_orders: list[dict] = []

    def save(self, order_data: dict) -> None:
        self.saved_orders.append(order_data)

fake = FakeOrderRepository()
service = OrderService(fake)
service.place_order({"product": "Widget", "qty": 3})
print(fake.saved_orders)
```

The test path runs with no database at all and prints:

```text
[{'product': 'Widget', 'qty': 3}]
```

**How to read this output:** `OrderService.place_order` ran its business validation and called `repository.save`, but because we injected `FakeOrderRepository`, "saving" just appended to an in-memory list -- no SQLite file, no connection, no SQL. Asserting on `fake.saved_orders` lets a unit test verify *what* the service tried to persist without spinning up a database, which is the concrete payoff of DIP: tests run in milliseconds and stay deterministic. The exact same `OrderService` instead receives `SqliteOrderRepository()` in production, so the business logic is written and tested once and the storage backend becomes a swappable detail.

> **Common pitfall:** Injecting a fake is only sound if the fake honors the same contract as the real adapter. If `SqliteOrderRepository.save` enforces a NOT NULL column or a uniqueness constraint that `FakeOrderRepository` silently ignores, your tests pass while production rejects the write. Keep fakes faithful, and back them with a small set of integration tests against the real adapter.

In a Django project, DIP is applied by injecting service dependencies. Instead of importing `MyModel.objects.filter(...)` directly inside a view, pass a repository or service object. This is especially valuable when you need to test views without hitting the database or when you want to swap backends.

> **Key Takeaway:** SOLID principles are not academic ideals. They are practical tools for reducing coupling, improving testability, and making code easier to change. Apply them when complexity warrants it -- a simple script does not need interface segregation. But as a system grows, violating these principles leads to fragile, untestable code that resists change.

---

### Other Key Principles

#### DRY (Don't Repeat Yourself)

Every piece of knowledge should have a single, unambiguous, authoritative representation in the system. When business logic is duplicated across multiple locations, a change in requirements means hunting down every copy -- and missing one means bugs. However, **premature abstraction is worse than duplication**. As Sandi Metz famously said: "Duplication is far cheaper than the wrong abstraction." The wrong abstraction creates a tangled dependency that is harder to unwind than having two copies of similar code.

A practical rule of thumb: wait for **three occurrences** before abstracting. When you see the same logic in three places, you have enough examples to understand the true shape of the abstraction.

```python
# Duplication: tax calculation repeated in three places
class InvoiceService:
    def calculate_invoice_total(self, subtotal: float) -> float:
        tax = subtotal * 0.08  # duplicated tax logic
        return subtotal + tax

class ReceiptService:
    def calculate_receipt_total(self, subtotal: float) -> float:
        tax = subtotal * 0.08  # duplicated tax logic
        return subtotal + tax

class QuoteService:
    def calculate_quote_total(self, subtotal: float) -> float:
        tax = subtotal * 0.08  # duplicated tax logic
        return subtotal + tax


# After three occurrences, extract:
class TaxCalculator:
    TAX_RATE = 0.08

    @classmethod
    def calculate_tax(cls, subtotal: float) -> float:
        return subtotal * cls.TAX_RATE


class InvoiceService:
    def calculate_invoice_total(self, subtotal: float) -> float:
        return subtotal + TaxCalculator.calculate_tax(subtotal)
```

In a Django project, DRY manifests as model managers for reusable queries, shared template tags, utility modules, and base serializer classes. But beware: if two serializers happen to look similar now but serve different stakeholders, forcing them into a shared base class creates coupling that will hurt later.

---

#### KISS (Keep It Simple, Stupid)

Choose the simplest solution that solves the problem. Complexity is the enemy of reliability, readability, and maintainability. As Brian Kernighan wrote: "Everyone knows that debugging is twice as hard as writing a program in the first place. So if you're as clever as you can be when you write it, how will you ever debug it?"

This principle pushes back against premature optimization, over-engineering, and clever tricks. A straightforward `for` loop is often better than a dense generator expression nested inside a `map()` call, even if the latter saves a few characters.

```python
# Over-engineered: a "flexible" configuration system
class ConfigMeta(type):
    _registry = {}
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        mcs._registry[name] = cls
        return cls

class BaseConfig(metaclass=ConfigMeta):
    ...

# KISS alternative: just use a dictionary or dataclass
from dataclasses import dataclass

@dataclass
class AppConfig:
    debug: bool = False
    database_url: str = "sqlite:///db.sqlite3"
    secret_key: str = "change-me"

config = AppConfig(debug=True)
print(config)
```

The `@dataclass` decorator gives you a readable `__repr__` for free, so printing the instance shows:

```text
AppConfig(debug=True, database_url='sqlite:///db.sqlite3', secret_key='change-me')
```

**What's happening:** One `@dataclass` line generated `__init__`, `__repr__`, and `__eq__`, and the defaults filled in every field the caller did not override. That is the whole KISS argument in miniature: the metaclass version on the left builds a registry and custom `__new__` that a reviewer must reverse-engineer, while the dataclass produces an object whose structure is obvious at a glance and trivial to debug. Reach for the metaclass only when you genuinely need that registry behavior -- in interviews, "I'd start with a dataclass and add a metaclass only if requirements forced it" signals good judgment about complexity.

---

#### YAGNI (You Ain't Gonna Need It)

Do not build features, abstractions, or infrastructure until they are actually needed. Premature generalization wastes development time, adds complexity that must be maintained, and often guesses wrong about future requirements. Build for today's requirements and refactor when tomorrow's requirements actually arrive.

```python
# YAGNI violation: building a plugin system for a simple app
class NotificationPluginManager:
    """Supports loading plugins from disk, hot-reloading, versioning..."""
    # 200 lines of code, used by exactly one notification type

# YAGNI alternative: just send the email
def send_order_confirmation(email: str, order_id: int) -> None:
    """When you need SMS later, add it then. Not now."""
    send_email(to=email, subject=f"Order #{order_id} confirmed", body="...")
```

---

#### Composition Over Inheritance

Prefer composing objects (has-a relationships) over deep class hierarchies (is-a relationships). Inheritance creates tight coupling between parent and child: changes to the base class ripple through all subclasses (the "fragile base class" problem). Composition allows mixing and matching behaviors at runtime without rigid hierarchies.

In Python, this is especially natural because of duck typing and Protocols. You do not need a deep class tree to share behavior.

```python
# Inheritance approach -- rigid and fragile
class Animal:
    def move(self):
        print("Moving")

class FlyingAnimal(Animal):
    def move(self):
        print("Flying")

class SwimmingAnimal(Animal):
    def move(self):
        print("Swimming")

class FlyingSwimmingAnimal(FlyingAnimal, SwimmingAnimal):
    # Diamond problem! Which move() is called?
    pass


# Composition approach -- flexible and explicit
from dataclasses import dataclass, field
from typing import Protocol


class MovementStrategy(Protocol):
    def move(self) -> str: ...


class Flying:
    def move(self) -> str:
        return "Flying through the air"


class Swimming:
    def move(self) -> str:
        return "Swimming through the water"


class Walking:
    def move(self) -> str:
        return "Walking on land"


@dataclass
class Animal:
    name: str
    movements: list[MovementStrategy] = field(default_factory=list)

    def perform_moves(self) -> None:
        for m in self.movements:
            print(f"{self.name}: {m.move()}")


duck = Animal("Duck", movements=[Flying(), Swimming(), Walking()])
duck.perform_moves()
# Duck: Flying through the air
# Duck: Swimming through the water
# Duck: Walking on land
```

In a Django project, prefer mixins and composition over deep model inheritance. Use `django.db.models.Manager` objects for reusable query logic rather than building abstract base model chains. Use `LoginRequiredMixin` and `PermissionRequiredMixin` as composable pieces in class-based views.

---

#### Law of Demeter (Principle of Least Knowledge)

An object should only talk to its **immediate friends** -- objects it directly owns or receives as parameters. A chain like `order.customer.address.city.zip_code` is a code smell: it couples the caller to the internal structure of four different objects. If any link in that chain changes, the caller breaks.

```python
# Violation: reaching deep into object internals
def get_shipping_label(order) -> str:
    # Knows about order -> customer -> address -> city
    return f"Ship to: {order.customer.address.city}, {order.customer.address.zip_code}"


# Fix: ask the object to do it
class Order:
    def __init__(self, customer):
        self.customer = customer

    def shipping_label(self) -> str:
        return self.customer.shipping_label()

class Customer:
    def __init__(self, address):
        self.address = address

    def shipping_label(self) -> str:
        return self.address.format_label()

class Address:
    def __init__(self, city: str, zip_code: str):
        self.city = city
        self.zip_code = zip_code

    def format_label(self) -> str:
        return f"{self.city}, {self.zip_code}"


# Now the caller only talks to its immediate friend:
def get_shipping_label(order: Order) -> str:
    return f"Ship to: {order.shipping_label()}"
```

> **Common pitfall:** The Law of Demeter is about *behavior*, not about counting dots. Fluent builders (`query.filter(...).order_by(...).limit(10)`) and Django's chained QuerySets are long dot-chains that do *not* violate it, because each call returns the same kind of object rather than exposing a different object's internals. The smell is reaching *through* foreign objects (`a.b.c.d`), not chaining methods on one. Applied too literally, the law spawns an explosion of pass-through "wrapper" methods that add indirection without decoupling anything.

---

#### Separation of Concerns

Divide a system into distinct sections, each addressing a separate concern. The classic layered approach separates **presentation** (what the user sees), **business logic** (the rules of the domain), and **data access** (how data is stored and retrieved). Cross-cutting concerns like logging, authentication, and caching are handled by middleware, decorators, or aspect-oriented techniques rather than being sprinkled throughout the business logic.

In a Django project, this means:

- **Views** handle HTTP request/response (presentation concern)
- **Services** contain business logic (not in views, not in models)
- **Models** define data structure and database interaction (persistence concern)
- **Middleware** handles auth, logging, CORS (cross-cutting concerns)

```python
# Violation: view contains business logic, database queries, AND formatting
from django.http import JsonResponse

def create_order(request):
    data = json.loads(request.body)
    # Business rule buried in view
    if data["quantity"] > 100:
        data["discount"] = 0.1
    # Direct database manipulation in view
    order = Order.objects.create(**data)
    # Notification logic in view
    send_email(order.customer.email, "Order placed!")
    return JsonResponse({"id": order.id, "total": order.total})


# Fix: separate concerns
# services/order_service.py
class OrderService:
    def create_order(self, order_data: dict) -> Order:
        order_data = self._apply_bulk_discount(order_data)
        order = self.order_repo.save(order_data)
        self.notification_service.notify_order_placed(order)
        return order

    def _apply_bulk_discount(self, data: dict) -> dict:
        if data["quantity"] > 100:
            data["discount"] = 0.1
        return data

# views.py
def create_order(request):
    data = json.loads(request.body)
    order = order_service.create_order(data)
    return JsonResponse(OrderSerializer(order).data)
```

---

#### Convention Over Configuration

Adopt reasonable defaults and only require explicit configuration when deviating from those defaults. This reduces boilerplate and cognitive load. Django is a prime example: placing models in `models.py`, views in `views.py`, templates in a `templates/` directory, and URL patterns in `urls.py` -- all by convention. Rails popularized this with its naming conventions that automatically wire models to database tables.

The benefit is that a new team member can navigate a project without reading extensive configuration files. The trade-off is that "magic" can confuse developers who do not know the conventions.

> **Key Takeaway:** These principles (DRY, KISS, YAGNI, composition over inheritance, Law of Demeter, separation of concerns, convention over configuration) are guidelines, not laws. They sometimes conflict -- DRY and KISS may pull in opposite directions. The skill lies in knowing which principle to prioritize for a given situation. When in doubt, favor simplicity and readability.

---

#### Tell, Don't Ask

The Tell-Don't-Ask principle says you should **tell objects what to do** rather than **asking them for their data and making decisions on their behalf**. When you pull state out of an object, branch on it, and then mutate the object from the outside, you have scattered that object's behavior across its callers -- the logic that should live *with* the data now lives everywhere the data is used. This is the procedural mindset wearing an object-oriented costume, and it is the root cause of the anemic domain model anti-pattern.

```python
# Ask (smell): caller reaches in, decides, and mutates from outside
class Account:
    def __init__(self, balance: float):
        self.balance = balance

def withdraw(account: Account, amount: float) -> None:
    # The withdrawal rule lives HERE, not on the object that owns the data
    if account.balance >= amount:
        account.balance -= amount
    else:
        raise ValueError("Insufficient funds")


# Tell: the object owns its own invariant
class Account:
    def __init__(self, balance: float):
        self._balance = balance

    def withdraw(self, amount: float) -> None:
        if amount > self._balance:
            raise ValueError("Insufficient funds")
        self._balance -= amount

    @property
    def balance(self) -> float:
        return self._balance


acct = Account(100.0)
acct.withdraw(30.0)
print(acct.balance)
```

```text
70.0
```

**How to read this output:** The caller never inspected `_balance` or applied the overdraft rule -- it just *told* the account to withdraw, and the account enforced its own invariant. The payoff is that the "you cannot overdraw" rule now has exactly one home. In the "ask" version, every place that withdraws must remember to re-check the balance first, and the day someone forgets is the day you ship a negative-balance bug. In interviews this is the concrete answer to "why is an anemic domain model bad?" -- behavior and the data it guards belong together.

> **Common pitfall:** Tell-Don't-Ask does not mean "no getters ever." Reporting, serialization, and read-only views legitimately need to read state. The principle targets the case where a caller reads state *in order to make a decision the object should be making itself*. A DTO or read model is allowed to be a bag of data; a domain entity is not.

---

#### The Twelve-Factor App

The Twelve-Factor App is a checklist (from the Heroku team) for building cloud-native, horizontally-scalable, deployable services. It predates Kubernetes but maps almost perfectly onto containers and orchestrators. The twelve factors:

1. **Codebase** -- one codebase tracked in version control, many deploys (dev, staging, prod) from it.
2. **Dependencies** -- explicitly declare and isolate dependencies (`requirements.txt`/`pyproject.toml` + a virtualenv or image), never rely on system-wide packages.
3. **Config** -- store config in the *environment*, not in code. Anything that differs between deploys (DB URLs, credentials, feature flags) is an env var.
4. **Backing services** -- treat databases, caches, queues, and SMTP as attached resources reached by URL/credentials, swappable without code changes.
5. **Build, release, run** -- strictly separate the build stage (compile/package), the release stage (build + config), and the run stage (execute). Releases are immutable and versioned.
6. **Processes** -- execute the app as one or more **stateless** processes. Any state that must persist goes to a backing service.
7. **Port binding** -- export the service via a port; the app is self-contained and does not rely on runtime injection of a web server.
8. **Concurrency** -- scale out via the process model (run more identical processes), not by making one process bigger.
9. **Disposability** -- fast startup and graceful shutdown; processes can be started or killed at a moment's notice (essential for autoscaling and rolling deploys).
10. **Dev/prod parity** -- keep development, staging, and production as similar as possible (same backing services, same OS via containers) to shrink the "works on my machine" gap.
11. **Logs** -- treat logs as event streams written to stdout; let the platform aggregate and route them. Do not manage log files in the app.
12. **Admin processes** -- run one-off admin tasks (migrations, shell, backfills) as separate processes against the same release, not as special-cased code paths.

```python
# Factor III + IV: config from the environment, backing services as URLs
import os

DATABASE_URL = os.environ["DATABASE_URL"]        # postgres://user:pass@host:5432/db
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# Same code runs unchanged in every environment -- only the env vars differ.
print(f"debug={DEBUG} db_host={DATABASE_URL.split('@')[-1]}")
```

```text
debug=false db_host=prod-db.internal:5432/db
```

**How to read this output:** The application code is identical across laptop, CI, staging, and production -- only the injected environment changed, so the same image promoted through the pipeline behaves correctly everywhere (factor V: build once, configure per release). The practical payoff of the whole list is concentrated in factors 3, 6, and 11: **config-from-env + stateless processes + logs-to-stdout** are precisely what make horizontal scaling, container orchestration, and zero-downtime rolling deploys possible. Most "why won't this scale?" or "why does it break behind a load balancer?" incidents trace directly back to a violation -- a session stored in a local dict (breaks factor 6 the moment you add a second replica), a secret baked into the image (factor 3), or a log file the container loses on restart (factor 11).

---

#### Coupling and Cohesion (Deep Cuts)

The earlier sections introduced tight vs. loose coupling and high vs. low cohesion. Two more rigorous vocabularies let you *measure* and *talk precisely* about coupling, which matters when you have to justify a refactor or draw a service boundary.

**Afferent and efferent coupling.** For a given module or package:

- **Afferent coupling (Ca)** -- the number of other components that depend *on* this one ("incoming"). High Ca means many things will break if you change this module: it carries high responsibility.
- **Efferent coupling (Ce)** -- the number of other components this one depends *on* ("outgoing"). High Ce means this module is fragile: it breaks when any of its many dependencies change.
- **Instability `I = Ce / (Ca + Ce)`** -- a number from 0 to 1. `I = 0` is maximally *stable* (lots of things depend on it, it depends on nothing); `I = 1` is maximally *unstable* (depends on everything, nothing depends on it). The guiding rule (the Stable Abstractions Principle): stable packages should be *abstract* (so they can be extended without modification), and unstable packages are where concrete, frequently-changing detail belongs. A concrete class that everything depends on is a refactoring trap.

**Connascence** is a finer-grained vocabulary than "coupling" for *how* two pieces of code are connected. Two elements are connascent if changing one requires changing the other to keep the system correct. The forms, roughly from weakest to strongest:

- **Connascence of Name** -- agreement on a name (a method called `save`). Weakest; rename tools handle it.
- **Connascence of Type** -- agreement on a type (a parameter must be an `int`).
- **Connascence of Meaning** -- agreement on the meaning of a value (a magic `1` means "active"). Fix with named constants/enums.
- **Connascence of Position** -- agreement on order of arguments (`func(lat, lon)` vs `func(lon, lat)`). Fix with keyword arguments.
- **Connascence of Algorithm** -- both sides must use the same algorithm (e.g., the same checksum or hashing on each end).
- **Connascence of Execution (order)** -- things must happen in a specific order (`init()` before `run()`).
- **Connascence of Timing** -- correctness depends on timing (a race condition, a sleep-based wait).
- **Connascence of Value** -- several values must change together (the four corners of a rectangle, a min/max pair).
- **Connascence of Identity** -- two references must point to the *same* object instance.

Two axes matter more than memorizing the list. **Static connascence** (visible in the source: name, type, position) is far cheaper than **dynamic connascence** (only visible at runtime: timing, execution order, identity, value), because the compiler and your editor can help with static forms but cannot see dynamic ones. And connascence that is **local** (inside one module/function) is tolerable even at high strength, while connascence that is **distant** (spanning modules, services, or repos) should be kept as weak as possible -- ideally just connascence of name via a published interface. The refactoring heuristic: *as the distance between two elements grows, reduce the strength of their connascence.* A magic number shared across two microservices (distant connascence of meaning) is a far worse smell than the same magic number used twice inside one function.

```python
# Connascence of Position (fragile): caller must remember argument order
def make_point(x, y, z): ...
make_point(1, 2, 3)   # which is which? Swap two and it silently misbehaves.

# Connascence of Name (stronger contract, weaker coupling): keyword-only
def make_point(*, x: int, y: int, z: int): ...
make_point(z=3, x=1, y=2)   # order-independent; the names carry the contract
```

**Package by feature vs. package by layer.** *Package by layer* groups code by technical role -- all models in `models/`, all views in `views/`, all services in `services/`. A single feature is then smeared across every directory, so a change to "orders" touches `models/order.py`, `views/order_view.py`, and `services/order_service.py`, and the high coupling between those files is hidden by the directory structure. *Package by feature* groups by business capability -- an `orders/` package containing its own models, views, and services. This raises cohesion (everything about orders is in one place), localizes coupling (the tangle is inside one package where it is honest), and -- not coincidentally -- makes the package a ready-made seam if you later extract it into a service. Feature packaging is the structural expression of high cohesion plus the bounded-context idea from DDD.

> **Key Takeaway:** "Reduce coupling" is too vague to act on. Instability (`Ce/(Ca+Ce)`) tells you *which* modules are risky to change and which should be abstract; connascence tells you *what kind* of coupling you have and -- via the distance/strength rule -- which instances to attack first. Package by feature so that the coupling you cannot remove is at least localized and visible.

---

#### Common Anti-Patterns

Knowing the named anti-patterns gives you a shared vocabulary for code review and design discussions -- "this is turning into a god object" lands faster than a paragraph of explanation.

- **God object / blob** -- one class (or module) that knows and does everything: it has dozens of methods, reaches into every part of the system, and has a sky-high afferent coupling. Every change risks it; nobody fully understands it. Fix by splitting along responsibilities (SRP) and pushing behavior to the objects that own the relevant data.
- **Anemic domain model** -- domain objects are bare bags of getters and setters, with all the actual business logic sitting in "service" or "manager" procedures. It is object-oriented in name only and is the direct violation of Tell-Don't-Ask. Push behavior and invariants back onto the entities and value objects. (Note: an anemic *DTO* at a boundary is fine -- the smell is specifically an anemic *domain* model.)
- **Spaghetti vs. lasagna** -- spaghetti code has tangled, unstructured control flow where everything jumps to everything; lasagna (or "ravioli/baklava") code is the opposite failure mode -- so many thin pass-through layers that a simple call traverses six files of ceremony adding no value. Both hurt. Aim for the *right number* of meaningful boundaries, not zero and not infinity.
- **Big ball of mud** -- a system with no discernible architecture, where every part depends on every other part and structure has eroded into entropy. It is, empirically, the most common architecture in the wild. The point is not that you will never have one, but that fighting its entropy must be a *deliberate, continuous* effort, not a one-time cleanup.
- **Premature optimization / premature abstraction** -- adding complexity (a cache, a generic framework, an extra layer of indirection) before there is evidence it is needed. It pairs with YAGNI: you pay the cost of the abstraction now and often discover later that you abstracted along the wrong axis. Optimize against measurements, abstract against the Rule of Three.
- **Magic / hidden coupling** -- behavior that "just happens" through Django signals, monkeypatching, import side effects, or global mutable state, so that reading the call site tells you nothing about what will actually run. It makes debugging archaeology. Prefer explicit calls; reserve magic for genuine framework-level cross-cutting concerns.
- **Distributed monolith** -- the worst-of-both-worlds outcome of a bad microservices split: services that are so chatty and tightly coupled that they must be deployed together and a change to one forces changes to several. You pay the full operational tax of distribution (network, partial failure, deployment complexity) while getting none of the independence that justifies it. It is usually caused by drawing service boundaries that do not align with bounded contexts. (Covered further in the Architectural Styles chapter.)

> **Common pitfall:** Anti-pattern labels are diagnostic tools, not insults to throw in review. The useful move is to name the *force* that produced the anti-pattern (deadline pressure, unclear ownership, a wrong early abstraction) and propose the specific refactor (extract class, push behavior down, collapse a pointless layer), rather than just declaring code "bad."

---

> [!NOTE]
> **Beginner's Mental Model — Clean/Hexagonal Architecture:**
> Think of the application core as a smartphone. The phone has defined ports (like a USB-C socket or Bluetooth connection). It doesn't care if you plug in a charger, a pair of headphones, or a keyboard—as long as the accessory has the matching connector (the adapter). The phone's core logic (making calls, running apps) is completely isolated from how it gets power or outputs sound, making it easy to swap accessories without redesigning the phone itself.

### Clean Architecture / Hexagonal Architecture

Imagine a modern television set. The TV has a core display screen and internal processors that decode signals, but it does not have a built-in, unchangeable DVD player, cable box, or game console glued inside its frame. Instead, the TV provides standardized plugs on the back—like HDMI and USB ports. You can plug in a PlayStation, an Apple TV, or a laptop. The television does not care *what* is plugged into the port, as long as the cable fits the socket. This is the core philosophy of Clean and Hexagonal Architecture. The core business rules of your application (the TV screen and processor) are completely isolated from external details like databases, web frameworks, and third-party APIs (the game consoles and players). By defining clear boundaries and interfaces—known as 'ports'—your core code remains untouched even if you completely swap out your database from PostgreSQL to MongoDB, or switch your web framework from Django to FastAPI. You simply build a new 'adapter' (like a new cable) to connect the external tool to the existing port.

Clean Architecture (Robert C. Martin) and Hexagonal Architecture (Alistair Cockburn) share the same core insight: **dependencies should point inward**, toward the domain. The core business logic should have zero knowledge of frameworks, databases, or external services. Those are details that belong in outer layers.

#### The Dependency Rule

The fundamental rule: **source code dependencies must point inward**. Inner layers define interfaces (ports); outer layers implement them (adapters). The domain never imports from the web framework. The web framework imports from the domain.

```
+-----------------------------------------------------------------------+
|  Frameworks & Drivers (outermost)                                     |
|  Django, FastAPI, PostgreSQL driver, Redis client, HTTP clients       |
|                                                                       |
|   +---------------------------------------------------------------+   |
|   |  Interface Adapters                                           |   |
|   |  Controllers, Presenters, Gateways, Repositories (impl)      |   |
|   |                                                               |   |
|   |   +-------------------------------------------------------+   |   |
|   |   |  Use Cases / Application Layer                        |   |   |
|   |   |  Application services, command/query handlers         |   |   |
|   |   |                                                       |   |   |
|   |   |   +-----------------------------------------------+   |   |   |
|   |   |   |  Entities / Domain Layer (innermost)          |   |   |   |
|   |   |   |  Domain models, value objects, domain         |   |   |   |
|   |   |   |  services, repository interfaces (ports)      |   |   |   |
|   |   |   +-----------------------------------------------+   |   |   |
|   |   |                                                       |   |   |
|   |   +-------------------------------------------------------+   |   |
|   |                                                               |   |
|   +---------------------------------------------------------------+   |
|                                                                       |
+-----------------------------------------------------------------------+

         Dependencies point INWARD -->  -->  -->
```

#### Layers Explained (Inside-Out)

1. **Entities / Domain Layer** -- Pure business objects and rules. No framework imports. An `Order` entity knows how to calculate its total and validate business rules. Repository interfaces (ports) are defined here but not implemented.

2. **Use Cases / Application Layer** -- Orchestrates the flow of data to and from entities. A `PlaceOrderUseCase` coordinates validation, persistence, and notification. It depends on domain objects and repository interfaces, not on concrete implementations.

3. **Interface Adapters** -- Converts data between the format most convenient for use cases and the format most convenient for external agents (database, web, etc.). Django views, REST serializers, and ORM repository implementations live here.

4. **Frameworks & Drivers** -- The outermost layer. Django itself, the PostgreSQL driver, the Redis client, HTTP libraries. These are details that can be swapped.

#### Hexagonal Architecture (Ports and Adapters)

Hexagonal architecture uses the metaphor of a hexagon with ports on its edges. Ports are interfaces that define what the application needs (e.g., "I need to save an order") or what it provides (e.g., "I can process an order"). Adapters are concrete implementations that connect those ports to the outside world.

```
                        +---------------------+
                        |   REST Controller   |
                        |    (Driving Adapter) |
                        +----------+----------+
                                   |
                                   v
                    +--------------+---------------+
       +----------->|         Input Port           |
       |            |      (OrderService ABC)      |
       |            +--------------+---------------+
       |                           |
       |            +--------------v---------------+
       |            |                              |
       |            |      APPLICATION CORE        |
       |            |                              |
       |            |   Domain Models + Use Cases  |
       |            |                              |
       |            +--------------+---------------+
       |                           |
       |            +--------------v---------------+
       |            |        Output Port           |
       +------------|   (OrderRepository ABC)      |
                    +--------------+---------------+
                                   |
                                   v
                        +----------+----------+
                        | PostgreSQL Adapter   |
                        | (Driven Adapter)     |
                        +---------------------+

    Driving Adapters          APPLICATION         Driven Adapters
    (trigger actions)           CORE              (called by core)
    - REST API               (pure logic)         - Database
    - CLI                                         - Email service
    - Message consumer                            - Message queue
```

#### Practical Example in Python

```python
# ---- Domain Layer (innermost, no framework imports) ----

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class Order:
    """Domain entity."""
    id: str | None
    customer_id: str
    items: list[dict]
    total: float = 0.0

    def calculate_total(self) -> None:
        self.total = sum(item["price"] * item["qty"] for item in self.items)
        if self.total > 500:
            self.total *= 0.95  # Business rule: 5% discount over $500


class OrderRepository(ABC):
    """Port -- defines what persistence the domain needs."""
    @abstractmethod
    def save(self, order: Order) -> Order: ...

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order | None: ...


class NotificationPort(ABC):
    """Port -- defines what notifications the domain needs."""
    @abstractmethod
    def send_order_confirmation(self, order: Order) -> None: ...


# ---- Use Case Layer ----

class PlaceOrderUseCase:
    """Application service -- orchestrates the flow."""
    def __init__(self, repo: OrderRepository, notifier: NotificationPort):
        self.repo = repo
        self.notifier = notifier

    def execute(self, customer_id: str, items: list[dict]) -> Order:
        order = Order(id=None, customer_id=customer_id, items=items)
        order.calculate_total()
        saved_order = self.repo.save(order)
        self.notifier.send_order_confirmation(saved_order)
        return saved_order


# ---- Adapter Layer (outermost, framework-specific) ----

class DjangoOrderRepository(OrderRepository):
    """Driven adapter -- implements the port using Django ORM."""
    def save(self, order: Order) -> Order:
        from myapp.models import OrderModel  # Django import only here
        obj = OrderModel.objects.create(
            customer_id=order.customer_id,
            items=order.items,
            total=order.total,
        )
        order.id = str(obj.pk)
        return order

    def find_by_id(self, order_id: str) -> Order | None:
        from myapp.models import OrderModel
        try:
            obj = OrderModel.objects.get(pk=order_id)
            return Order(
                id=str(obj.pk),
                customer_id=obj.customer_id,
                items=obj.items,
                total=obj.total,
            )
        except OrderModel.DoesNotExist:
            return None


class EmailNotificationAdapter(NotificationPort):
    """Driven adapter -- sends email."""
    def send_order_confirmation(self, order: Order) -> None:
        from django.core.mail import send_mail
        send_mail(
            subject=f"Order {order.id} confirmed",
            message=f"Your total is ${order.total:.2f}",
            from_email="shop@example.com",
            recipient_list=[order.customer_id],  # simplified
        )


# ---- Wiring (in Django view or DI container) ----

def place_order_view(request):
    use_case = PlaceOrderUseCase(
        repo=DjangoOrderRepository(),
        notifier=EmailNotificationAdapter(),
    )
    order = use_case.execute(
        customer_id=request.user.email,
        items=json.loads(request.body)["items"],
    )
    return JsonResponse({"order_id": order.id, "total": order.total})
```

#### When to Use This Architecture

The cost of clean/hexagonal architecture is more files, more indirection, and more boilerplate. This investment pays off for **complex domains** where business rules are the competitive advantage, where you need to swap infrastructure components, or where thorough unit testing of business logic is critical.

For simple CRUD applications, start simple: Django views calling services calling the ORM directly. Extract interfaces and ports when you actually need testability or swappability. Do not over-architect a todo app.

A practical progression:

1. **Start:** Views -> Models (simple Django)
2. **Grow:** Views -> Services -> Models (separate business logic)
3. **Scale:** Views -> Use Cases -> Domain Models + Repository Interfaces -> ORM Adapters (full hexagonal)

> **Key Takeaway:** Clean Architecture and Hexagonal Architecture are about protecting your business logic from infrastructure details. Dependencies point inward. The domain defines ports (interfaces); the infrastructure provides adapters (implementations). Start simple and introduce these patterns as complexity demands it.

*Last reviewed: 2026-06-08*
