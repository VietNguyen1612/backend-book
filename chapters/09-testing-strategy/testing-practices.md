[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 9.2 Testing Practices

### Test Design Principles

#### F.I.R.S.T. Principles

The F.I.R.S.T. acronym captures five qualities that every good test should have.

**Fast.** Tests must execute quickly. A slow test suite is a test suite that developers stop running. Unit tests should complete in milliseconds each; even your full integration suite should finish in low single-digit minutes. If tests are slow, investigate: are you hitting real I/O where a mock would suffice? Are you creating unnecessary database fixtures? Are you loading a heavy framework for a pure-logic test?

**Independent.** No test should depend on the result or side effects of another test. If test B fails only when test A runs first, you have a hidden coupling -- typically shared mutable state like a database row, a module-level variable, or a file on disk. Each test must set up its own preconditions and clean up after itself (or rely on framework-level isolation like Django's per-test transaction rollback).

**Repeatable.** A test must produce the same result every time it runs, regardless of the environment, time of day, or network conditions. Flaky tests that pass sometimes and fail other times erode trust in the entire suite. Common sources of flakiness include reliance on the current time (use `freezegun` or dependency injection for clocks), random data without a fixed seed, and network calls to external services (use mocks or recorded responses).

**Self-Validating.** A test must produce an unambiguous pass or fail. There should be no manual step -- no "open the log file and check that line 47 says OK." Assert statements are the mechanism: they either pass silently or raise a clear failure with a message explaining what was expected versus what was received.

**Timely.** Tests should be written alongside the code, not weeks later as an afterthought. When you write a function, write its tests before you move on. Test-Driven Development (TDD) takes this further by writing the test *before* the implementation. Whether or not you practice strict TDD, the principle is: do not accumulate a testing debt that you will never repay.

#### Test Coverage

Test coverage measures what fraction of your code is exercised by your test suite. **Branch coverage** is strictly more informative than line coverage because it counts whether both the true and false branches of every conditional have been tested. A line that contains `if x > 0: return x` is "covered" by line coverage if any test executes it, but branch coverage also asks whether a test triggered the case where `x <= 0`.

An 80% branch coverage target is a pragmatic goal for most projects. Pushing to 100% often means writing tests for trivial code (getters, `__str__` methods, framework boilerplate) where the cost of writing and maintaining those tests exceeds the value of the bugs they would catch. Remember: coverage tells you what code was *executed*, not whether the *assertions* were meaningful. A test that runs every line but asserts nothing is worse than useless because it provides false confidence.

```ini
# pyproject.toml -- configure coverage thresholds
[tool.coverage.run]
source = ["myapp"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "def __repr__",
]
```

#### Test Data with factory_boy and Faker

Hardcoded test data scattered throughout test files is brittle and hard to maintain. When the `Book` model gains a new required field, every test that manually constructs a `Book` must be updated. **factory_boy** solves this by defining a single factory class per model, with sensible defaults for every field. Tests override only the fields relevant to their scenario; everything else gets a default. **Faker** integrates with factory_boy to generate realistic-looking data (names, emails, addresses, ISBNs), which is more readable than "test123" and can reveal bugs related to data length or character sets.

```python
# tests/factories.py
import factory
from factory import Faker, LazyAttribute, SubFactory
from books.models import Book, Author, Review
from django.contrib.auth.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = Faker("user_name")
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")


class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Author

    name = Faker("name")
    bio = Faker("paragraph", nb_sentences=3)
    birth_date = Faker("date_of_birth", minimum_age=25, maximum_age=90)


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    title = Faker("sentence", nb_words=4)
    isbn = Faker("isbn13")
    price = Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    author = SubFactory(AuthorFactory)
    published_date = Faker("date_between", start_date="-10y", end_date="today")


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    book = SubFactory(BookFactory)
    user = SubFactory(UserFactory)
    rating = Faker("random_int", min=1, max=5)
    comment = Faker("paragraph", nb_sentences=2)
```

```python
# tests/test_book_model.py
from tests.factories import BookFactory, ReviewFactory


class TestBookModel:
    def test_book_str_returns_title(self):
        book = BookFactory(title="The Pragmatic Programmer")
        assert str(book) == "The Pragmatic Programmer"

    def test_average_rating_with_multiple_reviews(self):
        book = BookFactory()
        ReviewFactory(book=book, rating=5)
        ReviewFactory(book=book, rating=3)
        ReviewFactory(book=book, rating=4)

        assert book.average_rating() == 4.0

    def test_average_rating_with_no_reviews(self):
        book = BookFactory()
        assert book.average_rating() is None

    def test_discount_price(self):
        book = BookFactory(price=100.00)
        assert book.discount_price(percent=25) == 75.00
```

Using factories means that when the `Book` model adds a `language` field with a default, you update `BookFactory` once and all existing tests continue to work.

#### Mutation Testing with mutmut

Code coverage tells you what code your tests *execute*, but it says nothing about whether your tests would *detect a bug*. Mutation testing answers that question directly. A mutation testing tool like **mutmut** makes small changes (mutations) to your source code -- replacing `>` with `>=`, changing `True` to `False`, swapping `+` with `-` -- and then runs your test suite against each mutated version. If your tests still pass despite the mutation, that mutant "survived," which means your tests are not actually verifying that behavior. A high mutation kill rate (the percentage of mutants your tests detect) is a much stronger quality signal than coverage alone.

```bash
# Install mutmut
pip install mutmut

# Run mutation testing against a specific module
mutmut run --paths-to-mutate=myapp/services/pricing.py --tests-dir=tests/

# View summary of results
mutmut results

# Inspect a surviving mutant to understand what your tests missed
mutmut show 42
```

Example output:

```
--- myapp/services/pricing.py (original)
+++ myapp/services/pricing.py (mutant 42)
@@ -15,7 +15,7 @@
 def apply_bulk_discount(quantity, unit_price):
     if quantity >= 10:
-        return unit_price * 0.9  # 10% discount
+        return unit_price * 1.9  # MUTANT: changed 0.9 to 1.9
     return unit_price
```

If mutant 42 survives, it means no test checks that the bulk discount calculation actually produces a lower price. You would add:

```python
def test_bulk_discount_reduces_price():
    original = 100.0
    discounted = apply_bulk_discount(quantity=10, unit_price=original)
    assert discounted < original
    assert discounted == 90.0
```

#### Contract Testing with Pact

In a microservices architecture, each service depends on APIs provided by other services. Traditional integration tests require all services to be running simultaneously, which is fragile and slow. **Contract testing** with Pact takes a different approach: the *consumer* (the service making the API call) defines a contract -- "I will send this request and expect this response" -- and the *provider* (the service that implements the API) independently verifies that it satisfies that contract. If both sides pass their respective tests, you can be confident the services will work together in production, without ever running them at the same time.

```python
# Consumer side: tests/test_book_consumer.py
import atexit
import pytest
from pact import Consumer, Provider

# Create a Pact between the "BookstoreWeb" consumer and the "BookService" provider
pact = Consumer("BookstoreWeb").has_pact_with(
    Provider("BookService"),
    pact_dir="./pacts",
)
pact.start_service()
atexit.register(pact.stop_service)


def test_get_book_by_isbn():
    # Define the expected interaction
    (pact
     .given("a book with ISBN 9780132350884 exists")
     .upon_receiving("a request for book by ISBN")
     .with_request("GET", "/api/books/9780132350884")
     .will_respond_with(200, body={
         "isbn": "9780132350884",
         "title": "Clean Code",
         "price": 34.99,
     }))

    with pact:
        # This makes a real HTTP call to the Pact mock server
        import requests
        response = requests.get(f"{pact.uri}/api/books/9780132350884")

        assert response.status_code == 200
        data = response.json()
        assert data["isbn"] == "9780132350884"
        assert data["title"] == "Clean Code"


def test_book_not_found():
    (pact
     .given("no book with ISBN 0000000000000 exists")
     .upon_receiving("a request for a nonexistent book")
     .with_request("GET", "/api/books/0000000000000")
     .will_respond_with(404, body={
         "detail": "Book not found",
     }))

    with pact:
        import requests
        response = requests.get(f"{pact.uri}/api/books/0000000000000")
        assert response.status_code == 404
```

The consumer test generates a Pact JSON file in `./pacts/`. The provider team then runs the Pact verifier against their actual service to confirm that every interaction in the contract is satisfied. This workflow lets teams deploy independently and catch integration issues before they reach a shared staging environment.

```bash
# Provider side: verify the contract
pact-verifier --provider-base-url=http://localhost:8000 \
    --pact-url=./pacts/bookstorebeb-bookservice.json \
    --provider-states-setup-url=http://localhost:8000/_pact/setup
```

> **Key Takeaway:** Good test practices go far beyond writing assertions. Use factory_boy to eliminate brittle test data, mutation testing to verify that your tests actually catch bugs, and contract testing to safely decouple microservice deployments. The goal is not just to have tests, but to have tests that you trust -- tests that fail when something is genuinely broken and pass when everything works.
