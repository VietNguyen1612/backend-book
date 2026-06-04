[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 9.1 Testing Pyramid

The testing pyramid is a model that guides how you distribute your automated tests across different layers. At the base sits a large number of fast, isolated unit tests. In the middle are integration tests that verify how components work together with real dependencies. At the top are fewer, slower end-to-end and performance tests. The goal is to catch as many bugs as possible at the lowest (cheapest) layer while still verifying that the entire system works when assembled.

### Unit Tests

#### Test a Single Unit in Isolation

A unit test exercises one function, method, or class in complete isolation from the rest of the system. External dependencies such as databases, HTTP APIs, filesystems, and message queues are replaced with test doubles so that the test runs entirely in memory. This isolation guarantees that a failure points directly at the code under test, not at some transient infrastructure issue. Unit tests should execute in well under one second each, allowing you to run hundreds or thousands of them as part of your normal development workflow. The primary focus of unit tests is business logic -- the rules, calculations, and state transitions that define what your application actually does.

```python
# order_service.py
from datetime import date

class CouponExpiredError(Exception):
    pass

class OrderService:
    def __init__(self, coupon_repo, order_repo):
        self.coupon_repo = coupon_repo
        self.order_repo = order_repo

    def apply_coupon(self, order_id: str, coupon_code: str) -> float:
        coupon = self.coupon_repo.get_by_code(coupon_code)
        if coupon.expiry_date < date.today():
            raise CouponExpiredError(f"Coupon {coupon_code} expired on {coupon.expiry_date}")
        order = self.order_repo.get(order_id)
        discount = order.total * (coupon.discount_percent / 100)
        order.total -= discount
        self.order_repo.save(order)
        return order.total
```

```python
# test_order_service.py
from datetime import date
from unittest.mock import MagicMock
from order_service import OrderService, CouponExpiredError
import pytest

def test_expired_coupon_raises_validation_error():
    # Arrange
    coupon_repo = MagicMock()
    coupon_repo.get_by_code.return_value = MagicMock(
        expiry_date=date(2020, 1, 1),
        discount_percent=10,
    )
    order_repo = MagicMock()
    service = OrderService(coupon_repo, order_repo)

    # Act & Assert
    with pytest.raises(CouponExpiredError, match="expired on 2020-01-01"):
        service.apply_coupon("order-1", "SAVE10")


def test_valid_coupon_applies_discount():
    # Arrange
    coupon_repo = MagicMock()
    coupon_repo.get_by_code.return_value = MagicMock(
        expiry_date=date(2099, 12, 31),
        discount_percent=20,
    )
    order = MagicMock(total=100.0)
    order_repo = MagicMock()
    order_repo.get.return_value = order
    service = OrderService(coupon_repo, order_repo)

    # Act
    result = service.apply_coupon("order-1", "SAVE20")

    # Assert
    assert result == 80.0
    order_repo.save.assert_called_once_with(order)
```

#### Arrange-Act-Assert (AAA) Pattern

Every unit test should follow the AAA pattern: **Arrange** the preconditions and inputs, **Act** by calling the code under test, and **Assert** that the outcome matches expectations. This three-phase structure makes tests immediately readable -- a developer can scan any test and know what is being set up, what is being exercised, and what is being verified. Keep each test focused on one assertion concept (though you may use multiple `assert` statements if they verify different facets of the same logical outcome). Name your tests descriptively so that a failure message reads like a sentence: `test_expired_coupon_raises_validation_error` tells you exactly what went wrong without opening the file.

```python
# conftest.py -- shared fixtures live here; pytest discovers this file automatically
import pytest
from unittest.mock import MagicMock
from datetime import date


@pytest.fixture
def coupon_repo():
    """Provides a mock coupon repository pre-configured with a valid coupon."""
    repo = MagicMock()
    repo.get_by_code.return_value = MagicMock(
        expiry_date=date(2099, 12, 31),
        discount_percent=15,
    )
    return repo


@pytest.fixture
def order_repo():
    """Provides a mock order repository with a sample order."""
    repo = MagicMock()
    repo.get.return_value = MagicMock(total=200.0)
    return repo


@pytest.fixture
def order_service(coupon_repo, order_repo):
    """Wires up an OrderService with mock dependencies."""
    from order_service import OrderService
    return OrderService(coupon_repo, order_repo)
```

```python
# test_with_fixtures.py
def test_apply_valid_coupon_reduces_total(order_service, order_repo):
    # Arrange -- handled by fixtures

    # Act
    new_total = order_service.apply_coupon("order-42", "SAVE15")

    # Assert
    assert new_total == 170.0  # 200 - 15% = 170
    order_repo.save.assert_called_once()
```

#### Parametrize for Exhaustive Case Coverage

When the same logic must hold across many inputs, use `pytest.mark.parametrize` to avoid duplicating test functions. Each parameter set becomes its own test case with its own pass/fail result. This is especially powerful for boundary values, equivalence classes, and error conditions.

```python
import pytest

def calculate_shipping(weight_kg: float) -> float:
    """Shipping cost tiers by package weight."""
    if weight_kg <= 0:
        raise ValueError("Weight must be positive")
    if weight_kg <= 1:
        return 5.0
    if weight_kg <= 5:
        return 10.0
    if weight_kg <= 20:
        return 25.0
    return 50.0


@pytest.mark.parametrize(
    "weight, expected_cost",
    [
        (0.1, 5.0),      # lightest package
        (1.0, 5.0),      # boundary: exactly 1 kg
        (1.01, 10.0),    # just over 1 kg
        (5.0, 10.0),     # boundary: exactly 5 kg
        (5.01, 25.0),    # just over 5 kg
        (20.0, 25.0),    # boundary: exactly 20 kg
        (20.01, 50.0),   # just over 20 kg
        (100.0, 50.0),   # very heavy
    ],
    ids=[
        "lightest", "boundary-1kg", "over-1kg", "boundary-5kg",
        "over-5kg", "boundary-20kg", "over-20kg", "very-heavy",
    ],
)
def test_shipping_cost_tiers(weight, expected_cost):
    assert calculate_shipping(weight) == expected_cost


@pytest.mark.parametrize("invalid_weight", [0, -1, -0.01])
def test_shipping_rejects_non_positive_weight(invalid_weight):
    with pytest.raises(ValueError, match="Weight must be positive"):
        calculate_shipping(invalid_weight)
```

#### Edge Cases

Thorough unit tests go beyond the "happy path." You must deliberately test empty inputs (empty strings, empty lists, zero-length collections), null or `None` values where the type system permits them, boundary values at the exact transitions of conditional logic, very large inputs that might trigger timeouts or memory issues, special characters and Unicode strings that could break parsing or serialization, and concurrent access patterns if the code is expected to be thread-safe. Each of these categories represents a class of real bugs that will eventually surface in production if left untested.

```python
@pytest.mark.parametrize(
    "input_text, expected",
    [
        ("", []),                            # empty string
        ("hello", ["hello"]),                # single word
        ("hello world", ["hello", "world"]), # normal case
        ("  leading", ["leading"]),          # leading whitespace
        ("trailing  ", ["trailing"]),        # trailing whitespace
        ("\u00e9\u00e0\u00fc", ["\u00e9\u00e0\u00fc"]),  # Unicode accents
        ("a" * 10_000, ["a" * 10_000]),      # very long input
    ],
)
def test_tokenize_handles_edge_cases(input_text, expected):
    assert tokenize(input_text) == expected
```

#### Property-Based Testing with Hypothesis

Traditional example-based tests check specific inputs against known outputs. Property-based testing inverts this: you define invariants (properties) that must hold for *all possible* inputs, and the Hypothesis framework generates hundreds of random test cases automatically. When a test fails, Hypothesis "shrinks" the failing input to the smallest, simplest example that still reproduces the bug. This approach routinely discovers edge cases that a human tester would never think to write by hand -- off-by-one errors, integer overflows, Unicode normalization issues, and more.

```python
from hypothesis import given, settings, assume
from hypothesis import strategies as st


def encode(text: str) -> str:
    """Run-length encode a string: 'aaabbc' -> 'a3b2c1'."""
    if not text:
        return ""
    result = []
    count = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1]:
            count += 1
        else:
            result.append(f"{text[i - 1]}{count}")
            count = 1
    result.append(f"{text[-1]}{count}")
    return "".join(result)


def decode(encoded: str) -> str:
    """Decode a run-length encoded string: 'a3b2c1' -> 'aaabbc'."""
    result = []
    i = 0
    while i < len(encoded):
        char = encoded[i]
        i += 1
        num_str = ""
        while i < len(encoded) and encoded[i].isdigit():
            num_str += encoded[i]
            i += 1
        result.append(char * int(num_str))
    return "".join(result)


# Property: decode(encode(x)) == x for all strings of alphabetic characters
@given(st.text(alphabet=st.characters(whitelist_categories=("L",)), min_size=0, max_size=50))
@settings(max_examples=500)
def test_encode_decode_roundtrip(text):
    """Encoding and then decoding must return the original string."""
    assert decode(encode(text)) == text


# Property: encoded length is always at least as long as 2 * number of distinct runs
@given(st.text(alphabet="abc", min_size=1, max_size=100))
def test_encode_length_is_reasonable(text):
    encoded = encode(text)
    assert len(encoded) >= 2  # at minimum one char + one digit
```

> **Key Takeaway:** The testing pyramid puts unit tests at the foundation because they are fast, cheap, and precise. Use the AAA pattern for clarity, parametrize for breadth, fixtures and `conftest.py` for reuse, and Hypothesis for discovering the edge cases you did not think of. Aim for high coverage of business logic first; infrastructure wiring gets covered by integration tests.

---

### Integration Tests

#### Test Component Interactions with Real Dependencies

Integration tests verify that your code works correctly when it talks to real external systems -- databases, caches, message brokers, and third-party APIs. Unlike unit tests that replace dependencies with mocks, integration tests spin up actual instances (often via Docker containers) so you can catch problems like incorrect SQL, serialization mismatches, misconfigured connection pools, and transaction isolation bugs. These tests are inherently slower than unit tests, so you run fewer of them, but they catch an entirely different class of defect.

The `testcontainers` library lets you start disposable Docker containers from within your test suite. Each test run gets a fresh, isolated database with no leftover state from previous runs.

```python
# test_integration_db.py
import pytest
import sqlalchemy
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def postgres_engine():
    """Start a real PostgreSQL container for the duration of this test module."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        engine = sqlalchemy.create_engine(postgres.get_connection_url())
        # Run migrations or create schema
        with engine.begin() as conn:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE books (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    isbn VARCHAR(13) UNIQUE NOT NULL,
                    price NUMERIC(10, 2) NOT NULL
                )
            """))
        yield engine


def test_insert_and_query_book(postgres_engine):
    # Arrange
    with postgres_engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO books (title, isbn, price) VALUES (:t, :i, :p)"),
            {"t": "Clean Code", "i": "9780132350884", "p": 34.99},
        )

    # Act
    with postgres_engine.connect() as conn:
        row = conn.execute(
            sqlalchemy.text("SELECT title, price FROM books WHERE isbn = :i"),
            {"i": "9780132350884"},
        ).fetchone()

    # Assert
    assert row.title == "Clean Code"
    assert float(row.price) == 34.99


def test_unique_isbn_constraint(postgres_engine):
    with postgres_engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO books (title, isbn, price) VALUES (:t, :i, :p)"),
            {"t": "Refactoring", "i": "9780201485677", "p": 47.99},
        )

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        with postgres_engine.begin() as conn:
            conn.execute(
                sqlalchemy.text("INSERT INTO books (title, isbn, price) VALUES (:t, :i, :p)"),
                {"t": "Duplicate", "i": "9780201485677", "p": 9.99},
            )
```

#### API Tests

API tests send real HTTP requests to your application endpoints and verify the full request/response cycle: URL routing, input validation, serialization, authentication, authorization, and correct status codes. In Django, `TestCase` and Django REST Framework's `APIClient` make this straightforward.

```python
# tests/test_api_books.py (Django REST Framework example)
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from books.models import Book
from django.contrib.auth.models import User


class BookAPITest(TestCase):
    """Integration tests for the /api/books/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="reader", password="testpass123")
        self.client.force_authenticate(user=self.user)
        self.book = Book.objects.create(
            title="Domain-Driven Design",
            isbn="9780321125217",
            price=54.99,
        )

    def test_list_books_returns_200(self):
        response = self.client.get("/api/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Domain-Driven Design")

    def test_create_book_with_valid_data(self):
        payload = {"title": "Designing Data-Intensive Applications", "isbn": "9781449373320", "price": 39.99}
        response = self.client.post("/api/books/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(isbn="9781449373320").exists())

    def test_create_book_with_missing_title_returns_400(self):
        payload = {"isbn": "9781234567890", "price": 19.99}
        response = self.client.post("/api/books/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_unauthenticated_request_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/books/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
```

#### Database Tests

Database integration tests validate that your migrations run cleanly, queries return correct results, constraints enforce data integrity, and transactions behave as expected. In Django, `TransactionTestCase` disables the default test transaction wrapping, letting you test actual commit/rollback behavior, signals that fire on commit, and concurrency-related issues.

```python
from django.test import TransactionTestCase
from books.models import Book
from django.db import IntegrityError


class BookDatabaseTest(TransactionTestCase):
    """Tests that run each in their own transaction (slower but more realistic)."""

    def test_isbn_uniqueness_enforced_at_db_level(self):
        Book.objects.create(title="Book A", isbn="1234567890123", price=10.00)
        with self.assertRaises(IntegrityError):
            Book.objects.create(title="Book B", isbn="1234567890123", price=20.00)

    def test_price_cannot_be_negative(self):
        """Assumes a CHECK constraint: price >= 0."""
        with self.assertRaises(IntegrityError):
            Book.objects.create(title="Free Book", isbn="0000000000000", price=-5.00)
```

#### Test Doubles: Stubs, Mocks, Fakes, and Spies

Understanding the vocabulary of test doubles is essential for writing clean tests. A **stub** returns canned data and has no assertions on how it was called -- you use it to control the indirect inputs to the code under test. A **mock** goes further: it records how it was called and you assert on those interactions (e.g., "was `send_email` called exactly once with this recipient?"). A **fake** is a lightweight but working implementation -- an in-memory database, a local SMTP server -- that behaves realistically but avoids heavy infrastructure. A **spy** wraps the real implementation, allowing it to execute normally while recording calls for later inspection.

```python
from unittest.mock import patch, MagicMock, call


# --- Stub example: control what the dependency returns ---
def test_get_user_profile_with_stub():
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = {"id": 1, "name": "Alice", "email": "alice@example.com"}

    profile = get_user_profile(user_repo, user_id=1)

    assert profile["name"] == "Alice"


# --- Mock example: verify interactions ---
def test_order_completion_sends_email():
    email_service = MagicMock()
    order_service = OrderCompletionService(email_service=email_service)

    order_service.complete(order_id="ord-99")

    email_service.send.assert_called_once_with(
        to="customer@example.com",
        subject="Order ord-99 confirmed",
    )


# --- patch example: replace a module-level dependency ---
@patch("myapp.services.payment_gateway.charge")
def test_checkout_calls_payment_gateway(mock_charge):
    mock_charge.return_value = {"status": "success", "transaction_id": "txn-123"}

    result = checkout(cart_id="cart-1", amount=49.99)

    mock_charge.assert_called_once_with(amount=49.99, currency="USD")
    assert result["transaction_id"] == "txn-123"


# --- patch as context manager for fine-grained control ---
def test_retry_logic_on_transient_failure():
    with patch("myapp.clients.inventory.check_stock") as mock_check:
        # Fail twice, then succeed
        mock_check.side_effect = [ConnectionError, ConnectionError, {"qty": 10}]

        result = check_stock_with_retry(sku="ABC-123", max_retries=3)

        assert result["qty"] == 10
        assert mock_check.call_count == 3


# --- Spy example: wrap real implementation ---
def test_cache_is_populated_after_first_call():
    real_repo = BookRepository()
    with patch.object(real_repo, "find_by_isbn", wraps=real_repo.find_by_isbn) as spy:
        # First call hits the real method
        book1 = cached_lookup(real_repo, isbn="9780132350884")
        # Second call should use cache, not the repo
        book2 = cached_lookup(real_repo, isbn="9780132350884")

        spy.assert_called_once()  # only one real call, second was cached
        assert book1 == book2
```

> **Key Takeaway:** Integration tests catch the bugs that unit tests cannot -- mismatched SQL, serialization errors, broken authentication flows, and constraint violations. Use testcontainers for disposable real databases, Django's `TestCase`/`APIClient` for API-level verification, and understand the four types of test doubles so you choose the right tool for each situation.

---

### Performance Testing

#### Load Testing

Load testing determines how your system behaves under expected and peak traffic. You simulate concurrent users sending requests and measure response times, throughput, and error rates. **Locust** is a Python-native load testing tool that defines user behavior as plain Python code, making it natural for backend developers who already work in the Python ecosystem. It supports distributed load generation across multiple machines and provides a real-time web UI for monitoring test runs.

```python
# locustfile.py
from locust import HttpUser, task, between, tag


class BookstoreUser(HttpUser):
    """Simulates a typical bookstore API user."""

    # Each simulated user waits 1-3 seconds between requests
    wait_time = between(1, 3)

    def on_start(self):
        """Called once when a simulated user starts. Perform login."""
        response = self.client.post("/api/auth/login/", json={
            "username": "loadtest_user",
            "password": "testpassword123",
        })
        self.token = response.json()["token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @tag("read")
    @task(10)  # weight: 10x more likely than writes
    def browse_books(self):
        self.client.get("/api/books/", name="/api/books/ [list]")

    @tag("read")
    @task(5)
    def view_book_detail(self):
        self.client.get("/api/books/42/", name="/api/books/:id [detail]")

    @tag("read")
    @task(3)
    def search_books(self):
        self.client.get("/api/books/?search=python", name="/api/books/?search= [search]")

    @tag("write")
    @task(1)
    def add_to_cart(self):
        self.client.post("/api/cart/items/", json={
            "book_id": 42,
            "quantity": 1,
        }, name="/api/cart/items/ [add]")
```

Run it from the command line:

```bash
# Start with web UI (default: http://localhost:8089)
locust -f locustfile.py --host=http://localhost:8000

# Headless mode for CI pipelines
locust -f locustfile.py --host=http://localhost:8000 \
    --headless -u 200 -r 20 --run-time 5m \
    --csv=results/load_test
```

#### Types of Performance Tests

There are four distinct types of performance tests, each answering a different question. **Load testing** simulates expected traffic levels to verify that the system meets its SLA under normal conditions. **Stress testing** pushes traffic beyond the system's designed capacity to find the breaking point -- at what concurrency level do error rates spike or response times become unacceptable? **Soak testing** (also called endurance testing) runs a sustained moderate load for hours or days to detect slow resource leaks: memory that grows monotonically, database connections that are never returned to the pool, or disk usage that creeps up. **Spike testing** sends a sudden burst of traffic (for example, simulating a flash sale) to verify that auto-scaling, rate limiting, and circuit breakers respond correctly.

#### Metrics That Matter

The metrics you collect during performance tests determine what you can learn. **Response time** should be measured at multiple percentiles: p50 (median) tells you the typical experience, p95 tells you the experience for most users, and p99 reveals the worst-case tail latency that a significant fraction of users still hits. **Throughput** measured in requests per second tells you how much work the system can do. **Error rate** (percentage of 4xx and 5xx responses) shows when the system begins failing. **Resource usage** -- CPU utilization, memory consumption, database connection pool saturation, and disk I/O -- helps you identify which resource becomes the bottleneck first.

#### Benchmarking and Regression Detection

Establish a performance baseline by running your load test suite against a known-good version of the system and recording the key metrics. After every significant change, re-run the same tests and compare. Integrate this into your CI pipeline: if p95 latency increases by more than 10% or throughput drops by more than 5%, fail the build. This catches performance regressions before they reach production, when they are cheap to fix and the offending commit is easy to identify.

```python
# Example: pytest-benchmark for micro-benchmarks of hot code paths
import pytest

def fibonacci(n):
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def test_fibonacci_benchmark(benchmark):
    result = benchmark(fibonacci, 100)
    assert result == 354224848179261915075
```

> **Key Takeaway:** Performance testing is not optional for production systems. Use Locust for realistic load simulation, measure percentile latencies (not just averages), and automate regression detection in CI so you never ship a slow change unknowingly.
