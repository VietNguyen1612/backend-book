[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 9.1 Testing Pyramid

> [!NOTE]
> **Beginner's Mental Model — The Testing Pyramid:**
> Imagine building a **new house**:
>
> - **Unit Tests (Testing individual bricks):** Before laying a single brick, you test if each brick is solid and doesn't crumble under pressure. These tests are extremely fast and cheap to perform.
> - **Integration Tests (Testing plumbing and wiring):** Once the walls are up, you test if the pipes connect to the boiler without leaking and if the switches turn on the correct lights. These take more time and effort to set up because they involve real connections.
> - **End-to-End/E2E Tests (Living in the house):** You walk through the front door, turn on the TV, flush the toilet, and cook a meal to see if the whole house works together for a resident. This is highly realistic but slow, expensive, and difficult to do for every single corner of the house.
> The pyramid says you should have a massive foundation of brick-tests (unit), a good amount of plumbing-tests (integration), and only a few walkthroughs (E2E) on top.

The testing pyramid is a model that guides how you distribute your automated tests across different layers. At the base sits a large number of fast, isolated unit tests. In the middle are integration tests that verify how components work together with real dependencies. At the top are fewer, slower end-to-end and performance tests. The goal is to catch as many bugs as possible at the lowest (cheapest) layer while still verifying that the entire system works when assembled.

The classic failure mode is the inverted pyramid -- the **"ice cream cone"** -- where a team has a thick layer of slow, brittle end-to-end tests on top and almost no unit tests at the bottom. Such a suite takes ages to run, fails intermittently for reasons unrelated to the change under test, and gives imprecise failure messages, so developers stop trusting it. The corrective instinct is to "push coverage down the pyramid": every bug that an E2E test could catch but a faster unit or integration test could catch *just as well* belongs at the lower layer.

#### Testing Trophy vs. Pyramid

The pyramid is a heuristic, not a law. A widely cited counterpoint is Kent C. Dodds's **"testing trophy,"** which argues that for many modern applications -- especially those that are thin layers of glue over frameworks, databases, and libraries -- integration tests deliver the most *confidence per dollar*. The trophy shape (from bottom to top) is a base of static analysis (type checking, linting), then a moderate number of unit tests, a **large bulge of integration tests**, and a thin cap of E2E tests. The reasoning is that in a service that is mostly wiring -- routing, serialization, an ORM query, an HTTP call -- a unit test of any single layer in isolation tells you little, because the bugs live in the *seams between* layers, which only an integration test exercises.

The two models are not really in conflict; they answer the same question for different architectures. A library with rich, algorithm-heavy domain logic (a date-math library, a pricing engine) genuinely wants a fat unit-test base -- the pyramid. A CRUD web service that mostly translates HTTP to SQL wants a fat integration middle -- the trophy. The senior takeaway is to let the *shape of your code* dictate the shape of your test distribution rather than dogmatically chasing one diagram: write the test at the lowest layer that can still give you genuine confidence about the behavior you care about.

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

Running these two tests with `pytest -v test_order_service.py` prints something like:

```text
test_order_service.py::test_expired_coupon_raises_validation_error PASSED [ 50%]
test_order_service.py::test_valid_coupon_applies_discount PASSED          [100%]

============================== 2 passed in 0.03s ===============================
```

**How to read this output:** The `0.03s` total is the whole point of the pyramid's base -- because both `MagicMock` repos run in memory with no database or network, the suite finishes in milliseconds, so you can run thousands of these on every save. The `[ 50%]` / `[100%]` markers are pytest's progress through the collected tests, and each `PASSED` line names the exact test, so a failure here reads like a sentence telling you precisely which business rule broke. In an interview, the takeaway to articulate is that the speed and the pinpoint failure messages are what make unit tests the cheapest place to catch a bug.

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

Running `pytest -v` expands each parameter set into its own reportable test:

```text
test_shipping.py::test_shipping_cost_tiers[lightest] PASSED
test_shipping.py::test_shipping_cost_tiers[boundary-1kg] PASSED
test_shipping.py::test_shipping_cost_tiers[over-1kg] PASSED
test_shipping.py::test_shipping_cost_tiers[boundary-5kg] PASSED
test_shipping.py::test_shipping_cost_tiers[over-5kg] PASSED
test_shipping.py::test_shipping_cost_tiers[boundary-20kg] PASSED
test_shipping.py::test_shipping_cost_tiers[over-20kg] PASSED
test_shipping.py::test_shipping_cost_tiers[very-heavy] PASSED
test_shipping.py::test_shipping_rejects_non_positive_weight[0] PASSED
test_shipping.py::test_shipping_rejects_non_positive_weight[-1] PASSED
test_shipping.py::test_shipping_rejects_non_positive_weight[-0.01] PASSED

============================== 11 passed in 0.02s ==============================
```

**How to read this output:** The `ids=[...]` labels appear in brackets after the test name, which is exactly why naming your cases pays off -- if `[boundary-5kg]` had failed, the report would name the failing boundary directly instead of leaving you to count anonymous `[3]`-style indices. Note that one parametrized function produced eleven independently-reported results: a single off-by-one in the `<=` comparisons would fail only the relevant boundary case while the rest stayed green, isolating the defect for you.

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
@given(st.text(alphabet=st.characters(categories=("L",)), min_size=0, max_size=50))
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

When the roundtrip property holds, Hypothesis runs all 500 generated examples silently and the test simply passes. Its real value shows up on failure -- if `decode`/`encode` had a bug, the report looks like:

```text
Falsifying example: test_encode_decode_roundtrip(
    text='AA',
)
...
AssertionError: assert 'A2' == 'AA'
```

**How to read this output:** The `Falsifying example` is the minimal input Hypothesis arrived at after *shrinking* -- it may have first failed on a 40-character random string, then repeatedly simplified it down to the two-character `'AA'` that still triggers the bug. That shrinking is the feature that makes property-based testing worth the setup: instead of a noisy 40-char counterexample, you get the smallest reproduction, which is what you would paste into a regression test or a bug report. In practice this is how teams catch the Unicode and boundary cases nobody thought to enumerate by hand.

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

Running `pytest -v test_integration_db.py` produces something like (container pull/start time varies):

```text
Pulling image postgres:16-alpine
Container started: 7f3a9c1b2d4e
Waiting for database to be ready...

test_integration_db.py::test_insert_and_query_book PASSED   [ 50%]
test_integration_db.py::test_unique_isbn_constraint PASSED  [100%]

============================== 2 passed in 4.81s ==============================
```

**How to read this output:** Note the `4.81s` versus the milliseconds the unit suite took -- almost all of it is spinning up a real Postgres container, which is exactly why integration tests sit higher and thinner on the pyramid. Because the fixture is `scope="module"`, that container starts once and both tests share it; if it were function-scoped you would pay the startup cost per test. The payoff is that `test_unique_isbn_constraint` exercises the *real* `UNIQUE` constraint raising a genuine `IntegrityError` -- a class of bug a `MagicMock` repo can never catch, since a mock will happily "accept" a duplicate insert.

> **Common pitfall:** testcontainers requires a running Docker daemon. In CI this means the job needs Docker-in-Docker or a mounted Docker socket, and the first run is slow because the image must be pulled -- cache the image in CI so every build does not re-download it.

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

#### Test Doubles: Dummies, Stubs, Mocks, Fakes, and Spies

> [!NOTE]
> **Beginner's Mental Model — Mocks vs. Stubs:**
> Imagine you are testing a **detective script** in a play:
>
> - **A Stub is like a helpful bystander (an informant):** When the detective asks, "Where did the suspect go?", the stub simply replies with a pre-scripted answer: "They ran down Elm Street." The stub doesn't care who is asking or how many times; it just supplies the necessary information so the detective can continue their investigation.
> - **A Mock is like a wiretap or a spy log:** It sits quietly during the play, but at the end, you check its records to verify: "Did the detective make exactly one phone call to the chief of police, and did they pass the correct suspect name?" The mock's job is to verify *actions and behavior*, not just supply answers.

Understanding the vocabulary of test doubles is essential for writing clean tests. A **dummy** is an object passed only to satisfy a parameter list -- it is never actually used by the code path under test (for example, a placeholder `logger` you must supply to a constructor but whose calls you do not care about). A **stub** returns canned data and has no assertions on how it was called -- you use it to control the indirect inputs to the code under test. A **mock** goes further: it records how it was called and you assert on those interactions (e.g., "was `send_email` called exactly once with this recipient?"). A **fake** is a lightweight but working implementation -- an in-memory database, a local SMTP server -- that behaves realistically but avoids heavy infrastructure. A **spy** wraps the real implementation, allowing it to execute normally while recording calls for later inspection.

These five terms (dummy, stub, spy, mock, fake) come from Gerard Meszaros's *xUnit Test Patterns*; the distinction that matters in practice is between *state verification* (assert on the return value or resulting state -- stubs and fakes support this) and *interaction verification* (assert on which calls were made -- mocks and spies support this).

**Don't over-mock.** The most common test-double mistake is mocking too much. When you replace every collaborator with a `MagicMock`, your test stops verifying your code and starts verifying your mocks: it passes as long as the production code calls the methods you scripted, even if those methods would behave completely differently in reality. Such tests are also brittle -- they break whenever you refactor internal call sequences, because they are coupled to *how* the code works rather than *what* it produces. The rule of thumb is to mock at architectural boundaries -- the seams where your code talks to the outside world (databases, HTTP clients, message brokers, the clock, the filesystem) -- and to use real objects or fakes for your own internal classes. A test that mocks a domain object you wrote is usually a smell that the test is verifying implementation detail.

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

#### External Third-Party Services: Fakes, Sandboxes, and Record-Replay

Integration tests must talk to *something*, but they should almost never hit a real third-party API (Stripe, Twilio, a partner's REST service) in CI. Doing so makes the suite slow, flaky (their uptime becomes your build's uptime), non-deterministic, and occasionally expensive or destructive -- nobody wants their CI run to send real SMS messages or charge real cards. There are three responsible alternatives, in rough order of fidelity.

1. **Provider sandboxes.** Many vendors ship a dedicated test environment (Stripe test mode, PayPal sandbox, Twilio test credentials) that mimics the real API but operates on fake money and fake data. Sandboxes give the highest fidelity because the vendor maintains them, but they are still a network dependency, so reserve them for a small set of end-to-end "does our integration actually work against their contract" tests rather than your everyday suite.
2. **Local fakes.** Run a lightweight in-memory or containerized stand-in that implements the subset of the API you use -- for AWS this is `moto` or LocalStack; for a generic HTTP dependency it is a `WireMock`/`responses`/`httpx.MockTransport` server you program with canned responses. Fakes are fast and fully offline, at the cost of drifting from the real API if the vendor changes it.
3. **Record-replay (VCR-style).** Tools like `vcrpy` (Python) record real HTTP interactions to a "cassette" file on the first run, then replay them from disk on every subsequent run -- so CI never touches the network, but the recorded responses are real vendor payloads.

```python
# pip install vcrpy
import vcr
import requests

# First run: makes a real call and writes fixtures/exchange_rates.yaml.
# Every run after: replays from the cassette, no network involved.
@vcr.use_cassette(
    "fixtures/exchange_rates.yaml",
    record_mode="once",                # record if cassette missing, else replay
    filter_headers=["authorization"],  # never persist secrets to the cassette
)
def test_currency_conversion_uses_live_rate():
    resp = requests.get("https://api.exchange.example/v1/latest?base=USD")
    assert resp.status_code == 200
    assert resp.json()["rates"]["EUR"] > 0
```

```text
tests/test_currency.py::test_currency_conversion_uses_live_rate PASSED   [100%]
============================== 1 passed in 0.04s ==============================
```

**How to read this output:** The `0.04s` is the tell -- a test that nominally calls an external exchange-rate API finished in milliseconds because `vcrpy` replayed `fixtures/exchange_rates.yaml` from disk instead of hitting the network. That is what makes the test deterministic and CI-safe: the vendor could be down and this still passes identically. The `filter_headers=["authorization"]` line is the non-negotiable detail to mention in an interview -- cassettes are committed to the repo, so you must scrub credentials before they are written, or you leak secrets into version control. The trade-off to name is staleness: a cassette captures the API as it was on record day, so you periodically delete and re-record (`record_mode="all"`) to catch contract drift the replay would otherwise hide.

> **Common pitfall:** record-replay can mask a real breakage. If the vendor changes their response shape but your cassette still holds the old payload, the test stays green while production fails. Pair a large replayed suite with a *small* set of sandbox/live "smoke" tests run on a schedule (not on every commit) so contract drift is caught somewhere.

> **Key Takeaway:** Integration tests catch the bugs that unit tests cannot -- mismatched SQL, serialization errors, broken authentication flows, and constraint violations. Use testcontainers for disposable real databases, Django's `TestCase`/`APIClient` for API-level verification, and understand the five types of test doubles so you choose the right tool for each situation.

---

### Performance Testing

#### Load Testing

Load testing determines how your system behaves under expected and peak traffic. You simulate concurrent users sending requests and measure response times, throughput, and error rates. **Locust** is a Python-native load testing tool that defines user behavior as plain Python code, making it natural for backend developers who already work in the Python ecosystem. It supports distributed load generation across multiple machines and provides a real-time web UI for monitoring test runs.

Locust is not the only option, and in an interview it helps to know where each tool fits. **k6** (Grafana) scripts scenarios in JavaScript, runs as a single fast Go binary with low resource overhead per virtual user, and has first-class thresholds and CI/Grafana integration -- it is the common default for modern CI pipelines and "tests as code" load testing. **Gatling** is JVM-based, scripts in a Scala (or Java/Kotlin) DSL, generates rich HTML reports, and is favored in Java/Scala shops for high-throughput tests from a single node. **JMeter** is the long-established Apache tool with a GUI for building plans and an enormous plugin ecosystem (JDBC, JMS, LDAP, and more); it can drive non-HTTP protocols that the others cannot, but its thread-per-virtual-user model makes it heavier and its XML test plans harder to diff in version control. The selection heuristic: pick the tool whose scripting language your team already maintains (Python -> Locust, JS -> k6, JVM -> Gatling), and reach for JMeter when you need a protocol or a packaged plugin the code-first tools lack. The metrics that matter -- percentile latencies, throughput, error rate -- are identical regardless of which tool produces them.

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

In headless mode Locust prints a periodic stats table and a final aggregate summary that looks like (numbers depend entirely on your system under test):

```console
Type     Name                              # reqs    # fails |   Avg   Min   Max  Med | req/s failures/s
--------|---------------------------------|--------|---------|------|-----|-----|----|------|----------
GET      /api/books/ [list]                 18204     0(0.00%) |    42    11   310   38 | 121.4    0.00
GET      /api/books/:id [detail]             9102     0(0.00%) |    35     9   288   31 |  60.7    0.00
GET      /api/books/?search= [search]        5461    12(0.22%) |   118    21   940   95 |  36.4    0.08
POST     /api/cart/items/ [add]              1820     3(0.16%) |    66    18   512   58 |  12.1    0.02
--------|---------------------------------|--------|---------|------|-----|-----|----|------|----------
         Aggregated                         34587    15(0.04%) |    52     9   940   40 | 230.6    0.10

Response time percentiles (approximated)
Type     Name                              50%   75%   90%   95%   99%  100%
GET      /api/books/ [list]                 38    55    88   120   240   310
```

**How to read this output:** The `name=` labels you set in the locustfile are what group these rows -- without them, `/api/books/42/` and `/api/books/43/` would each be a separate line and the stats would be useless, so grouping by route template is essential. The `@task` weights show up in the request counts: `browse_books` (weight 10) drove ~18k requests while `add_to_cart` (weight 1) drove ~1.8k, roughly the 10:1 ratio you configured. The number that matters most for an SLA is the `95%`/`99%` percentile column, not `Avg` -- here the `search` endpoint's p99 of 940 ms is the tail latency a meaningful slice of real users actually feel, even though the average looks healthy. The `--csv` flag writes the same data to files so CI can diff it against a baseline.

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

`pytest-benchmark` runs the target many times and prints a statistics table (exact timings vary by machine):

```text
------------------------------- benchmark: 1 tests -------------------------------
Name (time in us)        Min      Max     Mean   StdDev   Median     OPS  Rounds
----------------------------------------------------------------------------------
test_fibonacci_benchmark 4.21    18.93     4.58    0.91     4.39  218.1K   42153
----------------------------------------------------------------------------------
```

**How to read this output:** Unlike a normal `pytest` run, the `benchmark` fixture calls `fibonacci(100)` thousands of times (`Rounds=42153`) so the statistics are stable rather than a single noisy timing. Focus on `Median` and `Min`, not `Max` -- `Max` is usually an outlier caused by the OS scheduler or GC pausing the process, whereas the median reflects steady-state cost. The reason to commit these numbers is regression detection: `pytest-benchmark` can save this run as a baseline (`--benchmark-autosave`) and fail CI if a later commit makes the median regress beyond a threshold, catching the slow change at the exact commit that introduced it.

> **Key Takeaway:** Performance testing is not optional for production systems. Use Locust for realistic load simulation, measure percentile latencies (not just averages), and automate regression detection in CI so you never ship a slow change unknowingly.

*Last reviewed: 2026-06-08*
