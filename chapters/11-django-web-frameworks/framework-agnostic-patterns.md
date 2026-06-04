[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 11.2 Web Framework-Agnostic Patterns

### Middleware / Interceptors

Middleware is the mechanism by which cross-cutting concerns are handled in web applications. A cross-cutting concern is something that affects many parts of the application but does not belong in any single view or controller: logging, authentication, CORS headers, compression, rate limiting, request ID injection, and exception handling are all classic examples.

The middleware pattern is universal. In Django, it is a class with `__call__`. In Flask, it is `before_request` / `after_request` decorators. In FastAPI/Starlette, it is `BaseHTTPMiddleware`. In Express.js, it is `app.use()`. In Java Spring, it is a `Filter` or `HandlerInterceptor`. The abstraction is always the same: a wrapper that can inspect and modify the request before it reaches the handler, and inspect and modify the response after the handler has produced it.

**Order matters.** Middleware executes in a defined order, and getting it wrong causes subtle bugs. The general rule is:

1. **Outermost**: Request ID injection, logging, timing (so they capture everything)
2. **Security**: CORS, security headers
3. **Session**: Session loading
4. **Authentication**: Identify who the user is
5. **Authorization**: Check if the user is allowed
6. **Business logic**: The actual view

Here is a practical example showing a request-ID middleware and an authentication middleware in Django, demonstrating correct ordering:

```python
# middleware/request_id.py
import uuid


class RequestIDMiddleware:
    """
    Assigns a unique ID to every request for tracing through logs,
    downstream services, and error reports.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use an existing header if set by a load balancer, otherwise generate one
        request_id = request.META.get("HTTP_X_REQUEST_ID", str(uuid.uuid4()))
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
```

```python
# middleware/auth.py
from django.http import JsonResponse


class APIKeyAuthMiddleware:
    """
    Simple API key authentication for non-admin endpoints.
    Demonstrates how middleware can short-circuit the request pipeline.
    """
    EXEMPT_PATHS = ("/admin/", "/health/", "/api/v1/public/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip authentication for exempt paths
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key or not self._is_valid_key(api_key):
            return JsonResponse(
                {"error": "Invalid or missing API key"},
                status=401,
            )

        return self.get_response(request)

    def _is_valid_key(self, key):
        from myapp.models import APIKey
        return APIKey.objects.filter(key=key, is_active=True).exists()
```

```python
# settings.py -- order matters!
MIDDLEWARE = [
    "middleware.request_id.RequestIDMiddleware",       # 1. outermost: tracing
    "django.middleware.security.SecurityMiddleware",    # 2. security headers
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "middleware.auth.APIKeyAuthMiddleware",             # 3. authentication
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
```

> **Key Takeaway:** Middleware is the right place for anything that applies to all (or most) requests. If a concern only applies to a few views, use a decorator instead. Always be deliberate about middleware ordering: tracing and logging wrap everything, security runs early, authentication must run before authorization, and authorization must run before the view. This principle holds across every web framework.

---

### Request Validation

Input validation is one of the most important responsibilities of the boundary layer of your application. Invalid data should never penetrate into your business logic or database layer. The principle is simple: validate early, fail fast, and return structured error responses.

Different frameworks provide different tools for this, but the concept is always the same: define a schema, validate incoming data against it, and return clear errors if validation fails.

#### Django REST Framework Serializers

Django REST Framework (DRF) serializers are the primary validation and serialization tool in the Django ecosystem for API development. They serve a dual purpose: validating incoming data (deserialization) and formatting outgoing data (serialization).

```python
# books/serializers.py
from rest_framework import serializers
from .models import Author, Book, Review


class AuthorSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Author
        fields = ["id", "name", "slug", "bio", "birth_date", "book_count"]
        read_only_fields = ["slug"]  # auto-generated from name


class ReviewSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "book", "author", "author_username", "rating", "text", "created_at"]
        read_only_fields = ["author", "created_at"]

    def validate_rating(self, value):
        """Field-level validation: rating must be between 1 and 5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        """Object-level validation: check cross-field constraints."""
        if len(attrs.get("text", "")) < 20:
            raise serializers.ValidationError({
                "text": "Review text must be at least 20 characters long."
            })
        return attrs

    def create(self, validated_data):
        """Set the author from the request context."""
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class BookListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views (fewer fields, no nested objects)."""
    author_name = serializers.CharField(source="author.name", read_only=True)
    avg_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author_name", "genre", "price", "avg_rating", "is_available"]


class BookDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail views (includes nested relationships)."""
    author = AuthorSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(),
        source="author",
        write_only=True,
    )
    reviews = ReviewSerializer(many=True, read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Book
        fields = [
            "id", "title", "author", "author_id", "publisher",
            "isbn", "genre", "published_date", "page_count",
            "price", "is_available", "avg_rating", "review_count",
            "reviews", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_isbn(self, value):
        if len(value) not in (10, 13):
            raise serializers.ValidationError("ISBN must be 10 or 13 characters.")
        return value
```

Using the serializers in DRF views:

```python
# books/views_api.py
from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django.db.models import Avg, Count
from django_filters.rest_framework import DjangoFilterBackend

from .models import Book, Review
from .serializers import BookListSerializer, BookDetailSerializer, ReviewSerializer


class BookPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class BookListCreateView(generics.ListCreateAPIView):
    pagination_class = BookPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["genre", "is_available"]
    search_fields = ["title", "author__name"]
    ordering_fields = ["price", "published_date", "avg_rating"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookDetailSerializer
        return BookListSerializer

    def get_queryset(self):
        return (
            Book.objects
            .select_related("author", "publisher")
            .annotate(
                avg_rating=Avg("reviews__rating"),
                review_count=Count("reviews"),
            )
        )


class BookDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BookDetailSerializer

    def get_queryset(self):
        return (
            Book.objects
            .select_related("author", "publisher")
            .prefetch_related("reviews__author")
            .annotate(
                avg_rating=Avg("reviews__rating"),
                review_count=Count("reviews"),
            )
        )


class ReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
```

When a client POSTs data that violates these rules, the serializer's `.is_valid()` returns `False` and DRF turns the collected errors into a `400 Bad Request` with a structured body. Posting a review with a too-short text and an out-of-range rating returns:

```text
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "rating": ["Rating must be between 1 and 5."],
    "text": ["Review text must be at least 20 characters long."]
}
```

**How to read this output:** Errors come back keyed by field name, with a list of messages per field -- this is the contract a frontend relies on to highlight the offending inputs, and it is why you raise `ValidationError` rather than returning a plain string. Note both a field-level error (`validate_rating`) and an object-level error (`validate`, raised as a dict) appear together: DRF accumulates every validation failure in one pass instead of stopping at the first, so the user fixes everything in a single round-trip. The 400 status (not 500) signals "the client sent bad data," keeping invalid input from ever reaching your business logic or database.

**FastAPI equivalent for comparison:**

```python
# FastAPI uses Pydantic models for validation -- same concept, different syntax.
from pydantic import BaseModel, Field, field_validator
from datetime import date


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author_id: int
    isbn: str = Field(..., min_length=10, max_length=13)
    genre: str
    price: float = Field(..., gt=0)
    published_date: date
    page_count: int = Field(default=0, ge=0)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v):
        if len(v) not in (10, 13):
            raise ValueError("ISBN must be 10 or 13 characters")
        return v


class BookResponse(BaseModel):
    id: int
    title: str
    author_name: str
    genre: str
    price: float
    avg_rating: float | None = None

    model_config = {"from_attributes": True}


# @app.post("/api/v1/books/", response_model=BookResponse)
# async def create_book(book: BookCreate): ...
```

The underlying principle is identical: define a schema, validate at the boundary, use separate schemas for input and output when needed.

> **Key Takeaway:** Never trust user input. Validate at the boundary of your application using the framework's native tools: DRF serializers for Django, Pydantic models for FastAPI, marshmallow or WTForms for Flask. Use separate serializers/schemas for list views (lightweight) and detail views (comprehensive). Field-level validators catch simple constraint violations; object-level validators enforce cross-field business rules.

---

### Background Task Processing

Many web applications need to perform work that is too slow or too unreliable to do inside an HTTP request/response cycle: sending emails, generating reports, processing images, calling third-party APIs, or running data pipelines. Background task processing offloads this work to separate worker processes that consume tasks from a message broker (like Redis or RabbitMQ).

Celery is the de facto standard for task queues in the Python ecosystem, but the concepts are universal. AWS SQS with Lambda, Sidekiq in Ruby, Bull in Node.js, and Google Cloud Tasks all follow the same pattern: a producer enqueues a task (a serialized function call), a broker stores and delivers it, and a worker picks it up and executes it.

#### Celery Integration with Django

**Project setup:**

```python
# myproject/celery.py
import os
from celery import Celery

# Set the default Django settings module for the celery program
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

app = Celery("myproject")

# Read config from Django settings, using the CELERY_ namespace
# e.g., CELERY_BROKER_URL in settings.py becomes broker_url in Celery
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()
```

```python
# myproject/__init__.py
from .celery import app as celery_app

__all__ = ("celery_app",)
```

```python
# myproject/settings.py (relevant Celery settings)
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True           # acknowledge after execution, not before
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # don't prefetch too many tasks
```

**Defining tasks:**

```python
# books/tasks.py
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds
    acks_late=True,
)
def send_review_notification(self, book_id, reviewer_username, rating):
    """
    Send an email notification to the book's author when a new review is posted.

    Design notes:
    - We pass primitive values (IDs, strings), not model instances, because
      task arguments must be JSON-serializable.
    - The task is idempotent: sending the same notification twice is harmless.
    - We use bind=True to access self for retries.
    """
    from books.models import Book  # import inside the task to avoid circular imports

    try:
        book = Book.objects.select_related("author").get(pk=book_id)
    except Book.DoesNotExist:
        logger.warning("Book %s not found, skipping notification", book_id)
        return  # don't retry -- the book was deleted

    try:
        send_mail(
            subject=f"New {rating}-star review on '{book.title}'",
            message=(
                f"{reviewer_username} left a {rating}-star review "
                f"on your book '{book.title}'."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[book.author.email] if hasattr(book.author, 'email') else [],
            fail_silently=False,
        )
        logger.info("Notification sent for book %s", book_id)
    except Exception as exc:
        logger.error("Failed to send notification: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def generate_daily_report():
    """
    Generate a daily summary report of new books and reviews.
    Typically called by Celery Beat (periodic task scheduler).
    """
    from datetime import date, timedelta
    from django.db.models import Count, Avg
    from books.models import Book, Review

    yesterday = date.today() - timedelta(days=1)

    new_books = Book.objects.filter(created_at__date=yesterday).count()
    new_reviews = Review.objects.filter(created_at__date=yesterday)
    review_stats = new_reviews.aggregate(
        count=Count("id"),
        avg_rating=Avg("rating"),
    )

    report = (
        f"Daily Report for {yesterday}\n"
        f"New books: {new_books}\n"
        f"New reviews: {review_stats['count']}\n"
        f"Average rating: {review_stats['avg_rating']:.1f}\n"
    )
    logger.info(report)
    # Could also save to a file, send to Slack, etc.
    return report


@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,       # exponential backoff: 1s, 2s, 4s, 8s, ...
    retry_backoff_max=600,    # max 10 minutes between retries
    max_retries=5,
)
def sync_book_to_search_index(self, book_id):
    """
    Sync a book's data to an external search service (e.g., Elasticsearch).

    Uses autoretry_for with exponential backoff for transient failures.
    """
    from books.models import Book

    book = Book.objects.select_related("author").get(pk=book_id)
    document = {
        "id": book.pk,
        "title": book.title,
        "author": book.author.name,
        "genre": book.genre,
        "isbn": book.isbn,
    }
    # search_client.index("books", document)
    logger.info("Indexed book %s in search", book_id)
```

When `generate_daily_report` runs (whether triggered by Celery Beat or invoked manually), the worker logs the assembled report. In your worker's stdout you would see something like:

```text
[2026-06-04 07:00:00,142: INFO/ForkPoolWorker-1] Daily Report for 2026-06-03
New books: 12
New reviews: 47
Average rating: 4.3
```

**What's happening:** The task runs inside the worker process, not the web process, so this output lands in the worker's logs, not your request logs -- a common source of confusion when developers go looking for task output in the wrong place. Note that `avg_rating` will be `None` (and the `:.1f` format string will raise) on a day with zero reviews; production tasks should guard aggregates with a default (e.g. `review_stats['avg_rating'] or 0`) before formatting.

**Calling tasks:**

```python
# In a view or signal handler:
from books.tasks import send_review_notification, sync_book_to_search_index

# Fire and forget (most common)
send_review_notification.delay(book_id=42, reviewer_username="alice", rating=5)

# With explicit options
send_review_notification.apply_async(
    args=[42, "alice", 5],
    countdown=30,            # wait 30 seconds before executing
    queue="notifications",   # route to a specific queue
)

# Chain tasks (run sequentially, passing results)
from celery import chain
chain(
    sync_book_to_search_index.s(42),
    send_review_notification.s(42, "alice", 5),
)()

# Group tasks (run in parallel)
from celery import group
group(
    sync_book_to_search_index.s(book_id)
    for book_id in [1, 2, 3, 4, 5]
)()
```

Each of these enqueue calls returns immediately -- it does not wait for the work to finish. At a shell or REPL you can see what comes back:

```text
>>> result = send_review_notification.delay(book_id=42, reviewer_username="alice", rating=5)
>>> result
<AsyncResult: 3f2a9c7e-1b4d-4e8a-9c2f-6d0e7a1b3c5d>
>>> result.id
'3f2a9c7e-1b4d-4e8a-9c2f-6d0e7a1b3c5d'
>>> result.status        # right after enqueue, before a worker picks it up
'PENDING'
```

**How to read this output:** `.delay()` returns an `AsyncResult` whose UUID is the task's handle in the result backend -- this is the value you persist if you later need to poll status or fetch the return value. The status is `PENDING` immediately because the producer only wrote a message to the broker; an actual worker has to consume and run it before the status flips to `STARTED` then `SUCCESS`. In an interview this is the key point about background tasks: the HTTP request returns in microseconds regardless of how slow the task is, which is the entire reason the pattern exists.

> **Common pitfall:** `PENDING` is also the status Celery reports for a task ID it has never heard of -- there is no separate "unknown" state. So `result.status == "PENDING"` does not prove the task is genuinely queued; it can equally mean a typo'd ID or a worker connected to a different broker.

**Periodic tasks with Celery Beat:**

```python
# myproject/settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "daily-report": {
        "task": "books.tasks.generate_daily_report",
        "schedule": crontab(hour=7, minute=0),  # every day at 7:00 AM UTC
    },
}
```

#### Task Design Principles

These principles apply regardless of which task queue you use:

1. **Idempotent:** Running the same task twice should produce the same result. Use database constraints and conditional checks to ensure this.
2. **Small and focused:** Large tasks should be broken into subtasks. This improves retry granularity and parallelism.
3. **Include all needed data in the payload:** Pass the data the task needs, not just an ID that might be deleted by the time the task runs. Or, if you must pass only an ID, handle the "not found" case gracefully.
4. **Serializable arguments:** Task arguments must be JSON-serializable (strings, numbers, lists, dicts). Never pass model instances, file handles, or database connections.
5. **Set timeouts:** Every task should have a `time_limit` and `soft_time_limit` to prevent runaway workers.

> **Key Takeaway:** Background tasks are essential for any non-trivial web application. The task queue pattern (producer-broker-worker) is universal. Design tasks to be idempotent, small, and self-contained. Use retries with exponential backoff for transient failures. Monitor your task queues with tools like Flower (Celery) or your broker's native monitoring.

---

### Caching Layer

Caching is the most effective way to improve the performance of a web application. The fundamental trade-off is simple: you exchange memory (or a fast storage layer) for computation time and database load. But the details -- what to cache, how long to cache it, and when to invalidate -- are where the complexity lives.

Django provides a unified cache framework with pluggable backends. The same API works whether you are using Redis, Memcached, a local file, or even a database table as your cache store. In production, Redis is the most common choice because it is fast, supports TTL natively, and can also serve as a Celery broker.

#### Cache Configuration

```python
# myproject/settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "db": "2",
        },
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,  # default TTL: 5 minutes
    },
}
```

#### Per-View Caching

The simplest caching strategy is to cache the entire response of a view. This is ideal for pages or API endpoints that are the same for all users and change infrequently.

```python
# books/views.py
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .models import Book


# Function-based view: cache for 15 minutes
@cache_page(60 * 15)
def book_catalog(request):
    books = Book.objects.select_related("author").filter(is_available=True)
    data = [{"id": b.id, "title": b.title, "author": b.author.name} for b in books]
    return JsonResponse({"books": data})


# Class-based view: cache for 15 minutes
@method_decorator(cache_page(60 * 15), name="dispatch")
class CachedBookListView(ListView):
    model = Book
    # ...
```

Per-view caching works by keying on the full URL (including query parameters). A request to `/api/v1/books/?page=1` and `/api/v1/books/?page=2` produce separate cache entries.

> **Common pitfall:** `cache_page` keys on the URL, not on the user. Applying it to a view that renders per-user content (a cart, a dashboard, anything behind login) will serve one user's cached response to everyone who hits the same URL -- a serious data-leak bug. Only cache responses that are genuinely identical for all callers, or vary the cache key with `Vary: Cookie`/`Authorization` headers.

#### Low-Level Cache API

For fine-grained control, use the low-level cache API directly. This lets you cache specific computations, database queries, or external API responses.

```python
from django.core.cache import cache


def get_book_detail(book_id):
    """
    Fetch book detail, using cache to avoid hitting the database on every request.
    """
    cache_key = f"book_detail:{book_id}"
    data = cache.get(cache_key)

    if data is not None:
        return data  # cache hit

    # Cache miss: query the database
    from books.models import Book
    from django.db.models import Avg, Count

    book = (
        Book.objects
        .select_related("author", "publisher")
        .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews"))
        .get(pk=book_id)
    )
    data = {
        "id": book.id,
        "title": book.title,
        "author": book.author.name,
        "publisher": book.publisher.name if book.publisher else None,
        "isbn": book.isbn,
        "avg_rating": float(book.avg_rating) if book.avg_rating else None,
        "review_count": book.review_count,
    }
    cache.set(cache_key, data, timeout=3600)  # cache for 1 hour
    return data


def get_genre_statistics():
    """
    Expensive aggregation query -- cache aggressively.
    """
    cache_key = "genre_statistics"
    stats = cache.get(cache_key)
    if stats is not None:
        return stats

    from books.models import Book
    from django.db.models import Count, Avg

    stats = list(
        Book.objects
        .values("genre")
        .annotate(
            count=Count("id"),
            avg_price=Avg("price"),
            avg_rating=Avg("reviews__rating"),
        )
        .order_by("-count")
    )
    cache.set(cache_key, stats, timeout=7200)  # cache for 2 hours
    return stats


# Other useful cache operations:
cache.set("key", "value", timeout=300)    # set with TTL
cache.get("key", default="fallback")      # get with default
cache.delete("key")                        # explicit invalidation
cache.get_or_set("key", callable, 300)     # atomic get-or-compute
cache.incr("page_views")                   # atomic increment
cache.set_many({"k1": "v1", "k2": "v2"})  # batch set
cache.get_many(["k1", "k2"])               # batch get
cache.delete_many(["k1", "k2"])            # batch delete
```

The payoff of `get_book_detail` is the gap between the first call (cache miss, hits the database) and every subsequent call (cache hit, served from Redis). Timing two calls in a shell makes it concrete:

```text
>>> import time
>>> t = time.perf_counter(); get_book_detail(42); (time.perf_counter() - t) * 1000
{'id': 42, 'title': 'Dune', 'author': 'Frank Herbert', ...}
18.7   # first call: SELECT + JOIN + two aggregates against Postgres
>>> t = time.perf_counter(); get_book_detail(42); (time.perf_counter() - t) * 1000
{'id': 42, 'title': 'Dune', 'author': 'Frank Herbert', ...}
0.4    # second call: single Redis GET, no DB round-trip
```

**How to read this output:** The exact milliseconds vary by hardware and network, but the ratio is the point -- the cached path is typically one to two orders of magnitude faster because it replaces a multi-table aggregate query with a single key lookup. This is why caching is the highest-leverage fix for a read-heavy endpoint under load: it removes work from the database, which is almost always the scarcest resource in a backend system.

#### Cache Invalidation

Cache invalidation is famously one of the two hard problems in computer science. The main strategies are:

1. **TTL-based expiry:** Set a timeout and accept stale data within that window. Simple and effective for data that does not need to be perfectly fresh.
2. **Event-based invalidation:** Delete or update cache entries when the underlying data changes. Use Django signals (as shown in the Signals section above) or explicit invalidation calls in your service layer.
3. **Cache versioning:** Include a version number in the cache key. Increment it when the schema of the cached data changes.

```python
# Pattern: explicit invalidation in a service function
def update_book_price(book_id, new_price):
    from books.models import Book

    Book.objects.filter(pk=book_id).update(price=new_price)
    # Invalidate all caches that include this book
    cache.delete(f"book_detail:{book_id}")
    cache.delete("book_catalog")
    cache.delete("genre_statistics")
```

#### Cache Stampede Prevention

A cache stampede (also called thundering herd) happens when a popular cache key expires and many concurrent requests all try to recompute it simultaneously, overwhelming the database. The `get_or_set` method helps because it is atomic, but for expensive computations you may need a lock:

```python
import time
from django.core.cache import cache


def get_expensive_data():
    cache_key = "expensive_data"
    lock_key = f"{cache_key}:lock"

    data = cache.get(cache_key)
    if data is not None:
        return data

    # Try to acquire a lock
    if cache.add(lock_key, "1", timeout=30):  # add() is atomic -- only one caller wins
        try:
            # This caller won the lock: compute and cache the data
            data = _compute_expensive_data()
            cache.set(cache_key, data, timeout=3600)
        finally:
            cache.delete(lock_key)
        return data
    else:
        # Another caller is computing -- wait briefly and retry
        time.sleep(0.5)
        return cache.get(cache_key) or _compute_expensive_data()
```

> **Key Takeaway:** Caching is not optional for production applications at any meaningful scale. Start with per-view caching for read-heavy endpoints, then move to low-level caching for specific computations as you identify bottlenecks. Always have an invalidation strategy. Use TTL as a safety net even when you have event-based invalidation, because bugs in invalidation code can cause stale data to persist forever. Redis is the standard cache backend for production Django.

---

### Template / Rendering Layer

Server-side rendering (SSR) uses a template engine to produce HTML on the server before sending it to the client. Django uses its own template language by default, but also supports Jinja2. The architectural pattern is MVT (Model-View-Template), which is Django's variant of MVC (Model-View-Controller): the Model defines data, the View handles logic and selects a template, and the Template handles presentation.

#### Server-Side Rendering

```python
# Template inheritance: base.html defines the skeleton, child templates fill in blocks.
```

{% raw %}
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My Bookstore{% endblock %}</title>
</head>
<body>
    <nav>
        <a href="{% url 'books:book-list' %}">Books</a>
    </nav>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```
{% endraw %}

{% raw %}
```html
<!-- templates/books/book_list.html -->
{% extends "base.html" %}

{% block title %}Book Catalog{% endblock %}

{% block content %}
    <h1>Books</h1>
    {% for book in books %}
        <div class="book-card">
            <h2><a href="{% url 'books:book-detail' pk=book.pk %}">{{ book.title }}</a></h2>
            <p>by {{ book.author.name }}</p>
            <p>{{ book.price|floatformat:2 }}</p>
        </div>
    {% empty %}
        <p>No books found.</p>
    {% endfor %}

    {% if is_paginated %}
        <nav>
            {% if page_obj.has_previous %}
                <a href="?page={{ page_obj.previous_page_number }}">Previous</a>
            {% endif %}
            <span>Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}</span>
            {% if page_obj.has_next %}
                <a href="?page={{ page_obj.next_page_number }}">Next</a>
            {% endif %}
        </nav>
    {% endif %}
{% endblock %}
```
{% endraw %}

Context processors inject variables that are available in every template (the logged-in user, site settings, etc.), which is Django's equivalent of global template variables in other frameworks.

#### API-Only Backends

Most modern backends serve JSON over REST or GraphQL and leave rendering to a frontend framework (React, Vue, Next.js). In this architecture, the backend's rendering layer is just JSON serialization and content negotiation.

Django REST Framework provides this out of the box with its serializers (shown above) and content negotiation system. FastAPI does the same with Pydantic models and automatic OpenAPI documentation. The shift from SSR to API-only backends means that the template layer is often not used at all, and the serializer layer becomes the primary "rendering" concern.

Key concepts for API-only backends:

- **JSON serialization**: Converting model instances to JSON-friendly dictionaries. Use serializers (DRF) or Pydantic models (FastAPI), not manual `json.dumps()` calls.
- **Content negotiation**: The server inspects the `Accept` header and returns the appropriate format (JSON, XML, HTML). DRF supports this natively.
- **HATEOAS (Hypermedia as the Engine of Application State)**: Including links to related resources in API responses. While rarely implemented in full, including `self` links and pagination links is good practice.
- **API versioning**: URL-based (`/api/v1/`, `/api/v2/`), header-based (`Accept: application/vnd.myapp.v2+json`), or query-parameter-based (`?version=2`). URL-based is the most common and the simplest to understand.

> **Key Takeaway:** The choice between server-side rendering and API-only architecture depends on your application's needs. SSR is simpler for content-heavy sites and better for SEO. API-only backends are the right choice when you have a JavaScript frontend, a mobile app, or multiple clients consuming the same data. Most new projects choose API-only. Regardless of which you choose, the principles of separation (data layer, logic layer, presentation layer) remain the same.
