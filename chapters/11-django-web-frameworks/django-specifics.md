[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 11.1 Django Specifics (Transferable Concepts)

### Request/Response Lifecycle

#### The Middleware Chain

Every HTTP request that reaches a Django application passes through a well-defined pipeline: the request enters the middleware stack from top to bottom, hits URL routing, dispatches to a view, the view produces a response, and then the response travels back up through the middleware stack in reverse order. This is the interceptor pattern (also called a filter chain), and it is not unique to Django. Flask uses `before_request` and `after_request` hooks, FastAPI has its own middleware system built on Starlette, and Express.js uses `app.use()` middleware. Understanding this pipeline deeply is the single most important thing you can do to debug problems in any web framework, because nearly every cross-cutting concern -- authentication, logging, CORS, compression -- lives in this layer.

Here is a concrete Django middleware class that measures request processing time and injects a custom header:

```python
# myapp/middleware.py
import time
import logging

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    """
    Measures how long each request takes to process and adds
    an X-Request-Duration-Ms header to the response.
    """

    def __init__(self, get_response):
        # One-time configuration. Called once when the server starts.
        self.get_response = get_response

    def __call__(self, request):
        # Code executed BEFORE the view (and later middleware) runs.
        start_time = time.monotonic()

        # Pass the request down the chain to the next middleware / view.
        response = self.get_response(request)

        # Code executed AFTER the view has returned a response.
        duration_ms = (time.monotonic() - start_time) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"
        logger.info(
            "method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
```

Register it in `settings.py`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "myapp.middleware.RequestTimingMiddleware",   # early, so it wraps everything
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

Django middleware can also hook into specific phases by defining extra methods:

```python
class AdvancedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Called just before Django calls the view.
        Returning None means 'continue normally'.
        Returning an HttpResponse short-circuits the chain."""
        return None

    def process_exception(self, request, exception):
        """Called when a view raises an exception.
        Return None to let Django's default exception handling proceed,
        or return an HttpResponse to swallow the exception."""
        return None

    def process_template_response(self, request, response):
        """Called after the view returns a TemplateResponse (before rendering).
        Lets you modify the template or context at the last moment."""
        return response
```

**FastAPI equivalent for comparison:**

```python
# FastAPI middleware using Starlette's BaseHTTPMiddleware
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"
        return response


# app.add_middleware(RequestTimingMiddleware)
```

The conceptual structure is identical: wrap the next handler, run code before and after, optionally short-circuit.

#### URL Routing

URL routing is the mapping from an incoming URL path to the Python function (or class) that should handle it. Django uses a list of `urlpatterns` that are tried in order; the first match wins. This is analogous to route decorators in Flask (`@app.route`) and FastAPI (`@app.get`), but Django's approach separates route declarations from view code, which keeps views reusable and URL structure centralized.

```python
# myproject/urls.py  (root URL configuration)
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/books/", include("books.urls")),   # delegate to the books app
]
```

```python
# books/urls.py
from django.urls import path
from . import views

app_name = "books"  # namespace for reverse resolution

urlpatterns = [
    path("", views.BookListView.as_view(), name="book-list"),
    path("<int:pk>/", views.BookDetailView.as_view(), name="book-detail"),
    path("<int:pk>/reviews/", views.book_reviews, name="book-reviews"),
    path("by-author/<slug:author_slug>/", views.books_by_author, name="books-by-author"),
]
```

Key concepts that transfer to any framework:

- **Path parameters** (`<int:pk>`, `<slug:author_slug>`) extract values from the URL and pass them to the view.
- **Query parameters** (`?page=2&sort=title`) are accessed through `request.GET` in Django, `request.args` in Flask, or function parameters in FastAPI.
- **Reverse URL resolution** lets you generate URLs from names instead of hard-coding paths. `reverse("books:book-detail", kwargs={"pk": 42})` produces `/api/v1/books/42/`. FastAPI has `request.url_for("read_book", pk=42)`.
- **Namespacing** prevents name collisions when multiple apps define routes with the same name.

#### Views: Function-Based and Class-Based

Django supports two styles of views. Function-based views (FBVs) are plain functions that receive an `HttpRequest` and return an `HttpResponse`. Class-based views (CBVs) use inheritance and mixins to reduce boilerplate for common patterns like listing, detail, create, update, and delete.

**Function-Based View:**

```python
# books/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Book, Review


@require_http_methods(["GET"])
def book_reviews(request, pk):
    """Return all reviews for a specific book as JSON."""
    book = get_object_or_404(Book, pk=pk)
    reviews = book.reviews.select_related("author").order_by("-created_at")

    data = {
        "book": book.title,
        "reviews": [
            {
                "id": r.id,
                "author": r.author.username,
                "rating": r.rating,
                "text": r.text,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }
    return JsonResponse(data)


@require_http_methods(["GET"])
def books_by_author(request, author_slug):
    """Return all books written by a specific author."""
    books = Book.objects.filter(
        author__slug=author_slug
    ).select_related("author", "publisher")

    data = [
        {"id": b.id, "title": b.title, "isbn": b.isbn}
        for b in books
    ]
    return JsonResponse({"books": data})
```

**Class-Based View:**

```python
# books/views.py (continued)
from django.views.generic import ListView, DetailView
from django.http import JsonResponse

from .models import Book


class BookListView(ListView):
    """
    GET /api/v1/books/ -- returns a list of books.
    ListView provides pagination and queryset handling out of the box.
    """
    model = Book
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("author", "publisher")
        # Optional filtering via query params
        title_query = self.request.GET.get("title")
        if title_query:
            qs = qs.filter(title__icontains=title_query)
        return qs

    def render_to_response(self, context, **kwargs):
        books = context["object_list"]
        data = [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author.name,
                "isbn": b.isbn,
            }
            for b in books
        ]
        return JsonResponse({"books": data, "page": context["page_obj"].number})


class BookDetailView(DetailView):
    """
    GET /api/v1/books/<pk>/ -- returns details for a single book.
    """
    model = Book
    queryset = Book.objects.select_related("author", "publisher")

    def render_to_response(self, context, **kwargs):
        book = context["object"]
        data = {
            "id": book.id,
            "title": book.title,
            "author": book.author.name,
            "publisher": book.publisher.name,
            "isbn": book.isbn,
            "published_date": book.published_date.isoformat(),
            "page_count": book.page_count,
        }
        return JsonResponse(data)
```

FBVs are easier to understand and debug; CBVs reduce repetition when you have many CRUD endpoints. Most production Django codebases use a mix of both. When using Django REST Framework, you will usually use `APIView` or `ViewSet` subclasses instead of raw Django CBVs.

> **Key Takeaway:** The request/response lifecycle -- middleware wrapping a routing layer wrapping a handler -- is the universal architecture of every web framework. Learn it once in Django and you will recognize it everywhere. Middleware is for cross-cutting concerns; views are for business logic. Mixing the two leads to code that is hard to test and hard to reason about.

---

### ORM & Database Layer

#### Model Definitions and Patterns

The Django ORM follows the Active Record pattern: each model instance knows how to save itself to the database, delete itself, and query its own table. This is in contrast to SQLAlchemy's default Data Mapper pattern, where a separate session/unit-of-work layer manages persistence and the model classes are closer to plain data containers.

Here is a realistic set of models for a bookstore application:

```python
# books/models.py
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Author(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    bio = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(max_length=300)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    class Genre(models.TextChoices):
        FICTION = "FIC", "Fiction"
        NON_FICTION = "NF", "Non-Fiction"
        SCIENCE = "SCI", "Science"
        TECHNOLOGY = "TECH", "Technology"
        BIOGRAPHY = "BIO", "Biography"

    title = models.CharField(max_length=500)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="books",
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
    )
    isbn = models.CharField(max_length=13, unique=True)
    genre = models.CharField(
        max_length=4,
        choices=Genre.choices,
        default=Genre.FICTION,
    )
    published_date = models.DateField()
    page_count = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_date"]
        indexes = [
            models.Index(fields=["isbn"]),
            models.Index(fields=["genre", "is_available"]),
        ]

    def __str__(self):
        return f"{self.title} by {self.author.name}"


class Review(models.Model):
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField()  # 1-5
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("book", "author")  # one review per user per book
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review of {self.book.title} by {self.author.username}"
```

#### Migrations

The migration system records every change you make to your models as a versioned Python file. Running `python manage.py makemigrations` inspects the current state of your models and generates a migration that describes the diff from the previous state. Running `python manage.py migrate` applies pending migrations in dependency order.

```bash
# Generate migration files after model changes
python manage.py makemigrations books

# Apply all pending migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations

# Generate SQL without executing (for review)
python manage.py sqlmigrate books 0001
```

`makemigrations` reports what it detected, and `sqlmigrate` prints the exact DDL Django will run -- without touching the database:

```console
$ python manage.py makemigrations books
Migrations for 'books':
  books/migrations/0001_initial.py
    - Create model Author
    - Create model Publisher
    - Create model Book
    - Create model Review

$ python manage.py sqlmigrate books 0001
BEGIN;
--
-- Create model Author
--
CREATE TABLE "books_author" (
    "id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    "name" varchar(200) NOT NULL,
    "slug" varchar(200) NOT NULL UNIQUE,
    "bio" text NOT NULL,
    "birth_date" date NULL,
    "created_at" timestamp with time zone NOT NULL
);
-- ... more CREATE TABLE / CREATE INDEX statements ...
COMMIT;
```

**How to read this output:** `makemigrations` only describes the operations and writes a Python file -- nothing has hit the database yet, which is why migrations are reviewable in code review like any other diff. `sqlmigrate` then renders that migration as the concrete SQL for your configured backend (the `GENERATED BY DEFAULT AS IDENTITY` and `timestamp with time zone` above are PostgreSQL-specific; SQLite or MySQL output differs). In production this is your safety check: read the generated DDL before applying it so an unexpected `ALTER TABLE` rewrite or a missing index does not lock a large table during deploy. The wrapping `BEGIN;`/`COMMIT;` shows the migration runs in a transaction, so on a transactional DDL backend a failure rolls the whole migration back cleanly.

This concept applies universally: Alembic for SQLAlchemy, Flyway for Java, Knex migrations for Node.js, and Active Record migrations for Rails. The key principle is that database schema changes are version-controlled, ordered, and reproducible.

#### QuerySet Evaluation and the N+1 Problem

Django QuerySets are lazy: constructing a queryset does not execute any SQL. The query only hits the database when you iterate over the queryset, call `len()`, slice it, or explicitly evaluate it with `.exists()`, `.count()`, etc. This laziness lets you chain filters and build queries incrementally without performance cost.

However, laziness combined with related objects creates the infamous **N+1 query problem**: you execute 1 query to fetch N objects, then N additional queries to fetch a related object for each one.

**The N+1 Problem -- Before (Bad):**

```python
# BAD: This generates 1 + N queries.
# Query 1: SELECT * FROM books_book
# Then for each book: SELECT * FROM books_author WHERE id = <book.author_id>
def book_list_bad(request):
    books = Book.objects.all()  # 1 query for books
    data = []
    for book in books:
        data.append({
            "title": book.title,
            "author_name": book.author.name,       # +1 query PER book
            "publisher": book.publisher.name,       # +1 query PER book
        })
    # If there are 100 books, this executes 201 queries.
    return JsonResponse({"books": data})
```

**After (Fixed with select_related):**

```python
# GOOD: This generates exactly 1 query using SQL JOINs.
# SELECT books_book.*, books_author.*, books_publisher.*
#   FROM books_book
#   INNER JOIN books_author ON ...
#   LEFT JOIN books_publisher ON ...
def book_list_good(request):
    books = Book.objects.select_related("author", "publisher").all()
    data = []
    for book in books:
        data.append({
            "title": book.title,
            "author_name": book.author.name,       # no extra query -- already loaded
            "publisher": book.publisher.name,       # no extra query -- already loaded
        })
    # Always 1 query, regardless of how many books exist.
    return JsonResponse({"books": data})
```

**select_related vs. prefetch_related:**

`select_related` uses SQL JOINs and works for ForeignKey and OneToOneField relationships (single-valued). `prefetch_related` executes a separate query per relationship and stitches the results together in Python; it works for ManyToManyField and reverse ForeignKey relationships (multi-valued).

```python
# select_related: SQL JOIN, good for ForeignKey / OneToOne
books = Book.objects.select_related("author", "publisher").all()
# Generates: SELECT ... FROM book INNER JOIN author ON ... LEFT JOIN publisher ON ...

# prefetch_related: separate query, good for reverse FK / M2M
authors = Author.objects.prefetch_related("books").all()
# Generates:
#   Query 1: SELECT * FROM author
#   Query 2: SELECT * FROM book WHERE author_id IN (1, 2, 3, ...)
# Django then maps books to their authors in Python.

# You can combine both:
authors = Author.objects.prefetch_related(
    Prefetch(
        "books",
        queryset=Book.objects.select_related("publisher").filter(is_available=True),
        to_attr="available_books",  # stores result as a list attribute
    )
).all()

# Now: author.available_books is a plain Python list (not a queryset)
for author in authors:
    for book in author.available_books:
        print(book.title, book.publisher.name)  # no extra queries
```

Iterating this prints one line per available book, with no further database hits inside the loop:

```text
The Pragmatic Programmer O'Reilly Media
Refactoring Addison-Wesley
Clean Code Prentice Hall
```

**How to read this output:** The important thing is not the titles themselves but the query count behind them. Three queries ran total -- one for the authors, one for the prefetched books, and one (the inner `select_related("publisher")`) folded into the book query -- regardless of how many authors or books exist. Without the nested `select_related`, every `book.publisher.name` access in the loop would fire its own `SELECT`, recreating the N+1 problem one level deeper. In production this is the difference between a dashboard that renders in 30 ms and one that issues hundreds of queries and times out; verify it by watching the query count in `django-debug-toolbar` rather than trusting the code reads correctly.

#### Q Objects: Complex Lookups

Django's `Q` objects let you build queries with `OR`, `AND`, and `NOT` logic that cannot be expressed with simple keyword arguments to `.filter()`.

```python
from django.db.models import Q

# OR: books that are either fiction OR have more than 500 pages
books = Book.objects.filter(
    Q(genre=Book.Genre.FICTION) | Q(page_count__gt=500)
)

# AND with OR: available books that are (fiction OR science)
books = Book.objects.filter(
    Q(is_available=True),
    Q(genre=Book.Genre.FICTION) | Q(genre=Book.Genre.SCIENCE),
)

# NOT: books that are NOT biography
books = Book.objects.filter(~Q(genre=Book.Genre.BIOGRAPHY))

# Dynamic query building -- extremely useful for search endpoints
def search_books(request):
    filters = Q()
    if title := request.GET.get("title"):
        filters &= Q(title__icontains=title)
    if genre := request.GET.get("genre"):
        filters &= Q(genre=genre)
    if min_price := request.GET.get("min_price"):
        filters &= Q(price__gte=min_price)
    if max_price := request.GET.get("max_price"):
        filters &= Q(price__lte=max_price)

    books = Book.objects.filter(filters).select_related("author")
    # ... serialize and return
```

#### F Expressions: Database-Level Field References

`F` expressions let you reference model field values directly in the database, which avoids loading the value into Python and prevents race conditions in concurrent updates.

```python
from django.db.models import F

# Increase the price of all fiction books by 10% -- entirely in SQL
Book.objects.filter(genre=Book.Genre.FICTION).update(
    price=F("price") * 1.10
)
# Generates: UPDATE books_book SET price = price * 1.10 WHERE genre = 'FIC'

# Compare two fields on the same model: books where page_count > 2 * price
long_cheap_books = Book.objects.filter(page_count__gt=F("price") * 2)

# Atomic increment (safe under concurrent requests, no race condition)
book = Book.objects.get(pk=42)
book.page_count = F("page_count") + 1
book.save(update_fields=["page_count"])
# IMPORTANT: After using F(), the instance's field holds an F expression, not an int.
# You must refresh from the database to see the updated value:
book.refresh_from_db()
print(book.page_count)  # now an integer
```

#### Annotations and Aggregations

Annotations add computed columns to each row; aggregations collapse all rows into a single summary value.

```python
from django.db.models import Avg, Count, Max, Min, Sum, F, Value
from django.db.models.functions import Coalesce

# Annotation: add the average review rating to each book
books_with_ratings = Book.objects.annotate(
    avg_rating=Avg("reviews__rating"),
    review_count=Count("reviews"),
).filter(
    review_count__gte=5  # only books with at least 5 reviews
).order_by("-avg_rating")

for book in books_with_ratings:
    print(f"{book.title}: {book.avg_rating:.1f} stars ({book.review_count} reviews)")
```

The loop prints one line per qualifying book, highest-rated first:

```text
Clean Code: 4.8 stars (212 reviews)
The Pragmatic Programmer: 4.7 stars (188 reviews)
Designing Data-Intensive Applications: 4.6 stars (95 reviews)
```

**How to read this output:** `avg_rating` and `review_count` are columns the database computed via a `GROUP BY`, not values Python iterated to find -- the `.filter(review_count__gte=5)` even translates to a SQL `HAVING` clause. This matters because the entire ranking is done in one query inside the database engine; the alternative (pulling every review into Python and averaging by hand) would move megabytes over the wire and is the classic mistake that makes "show me the top-rated books" endpoints slow. Note that books with fewer than 5 reviews are absent, which is exactly the noise-suppression a real "popular items" feature needs.

```python
# Aggregation: get summary statistics across ALL books
stats = Book.objects.aggregate(
    total_books=Count("id"),
    avg_price=Avg("price"),
    max_price=Max("price"),
    min_price=Min("price"),
    total_pages=Sum("page_count"),
)
# stats = {"total_books": 1500, "avg_price": Decimal("29.99"), ...}

# Grouping: count books per genre
from django.db.models import Count

genre_counts = (
    Book.objects
    .values("genre")           # GROUP BY genre
    .annotate(count=Count("id"))
    .order_by("-count")
)
# [{"genre": "FIC", "count": 450}, {"genre": "TECH", "count": 320}, ...]

# Annotation with Coalesce (handle NULL averages for books with no reviews)
books = Book.objects.annotate(
    avg_rating=Coalesce(Avg("reviews__rating"), Value(0.0))
)

# Subquery annotations (e.g., most recent review date per book)
from django.db.models import Subquery, OuterRef

latest_review = (
    Review.objects
    .filter(book=OuterRef("pk"))
    .order_by("-created_at")
    .values("created_at")[:1]
)
books = Book.objects.annotate(
    latest_review_date=Subquery(latest_review)
)
```

#### Custom Managers and QuerySets

Custom managers and querysets let you encapsulate reusable query logic so your views stay clean.

```python
# books/models.py (add to Book model)

class BookQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)

    def fiction(self):
        return self.filter(genre=Book.Genre.FICTION)

    def with_ratings(self):
        return self.annotate(
            avg_rating=Coalesce(Avg("reviews__rating"), Value(0.0)),
            review_count=Count("reviews"),
        )

    def expensive(self, threshold=50):
        return self.filter(price__gte=threshold)


class BookManager(models.Manager):
    def get_queryset(self):
        return BookQuerySet(self.model, using=self._db)

    def available(self):
        return self.get_queryset().available()

    def fiction(self):
        return self.get_queryset().fiction()


# In the Book model:
# objects = BookManager()

# Usage in views:
# Book.objects.available().fiction().with_ratings().order_by("-avg_rating")
```

> **Key Takeaway:** The ORM is not a replacement for understanding SQL -- it is an abstraction on top of it. Always use `select_related` for ForeignKey/OneToOne and `prefetch_related` for reverse FK/M2M to avoid N+1 queries. Use `F` expressions for atomic database-level operations. Use `Q` objects to build dynamic filters. Learn to read the SQL that the ORM generates by calling `str(queryset.query)` or using `django-debug-toolbar`.

---

### Signals & Events

Django signals implement the observer pattern: when a particular event occurs (a model is saved, a request starts, a user logs in), Django broadcasts a signal, and any registered receiver function runs. This provides decoupling -- the code that sends the signal does not need to know about the code that handles it.

However, signals come with significant downsides. They create hidden control flow that is hard to trace in a debugger. They run synchronously inside the same database transaction (by default), so a slow or failing receiver can break seemingly unrelated operations. The general guidance is: use signals for truly decoupled, cross-cutting reactions (like invalidating a cache when any model changes), but prefer explicit service-layer function calls for important business logic.

#### Built-in Signals

The most commonly used signals are:

- `pre_save` / `post_save` -- fired before/after a model's `.save()` method
- `pre_delete` / `post_delete` -- fired before/after a model is deleted
- `m2m_changed` -- fired when a ManyToManyField is modified
- `request_started` / `request_finished` -- fired at the beginning/end of each HTTP request
- `user_logged_in` / `user_logged_out` / `user_login_failed` -- from `django.contrib.auth.signals`

#### Signal Registration

The recommended way to register signals is inside the `ready()` method of your app's `AppConfig`. This ensures signals are connected exactly once, after all apps are loaded.

```python
# books/apps.py
from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "books"

    def ready(self):
        # Import the signals module so receivers are registered.
        import books.signals  # noqa: F401
```

```python
# books/signals.py
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from .models import Book, Review

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Book)
def invalidate_book_cache(sender, instance, created, **kwargs):
    """
    Invalidate cached book data whenever a book is created or updated.
    """
    cache_key = f"book_detail:{instance.pk}"
    cache.delete(cache_key)
    cache.delete("book_list")  # also invalidate the list cache

    action = "Created" if created else "Updated"
    logger.info("%s book: %s (pk=%s)", action, instance.title, instance.pk)


@receiver(post_save, sender=Review)
def update_book_rating_cache(sender, instance, created, **kwargs):
    """
    When a review is saved, update the cached average rating for the book.
    """
    if created:
        book = instance.book
        avg_rating = book.reviews.aggregate(
            avg=models.Avg("rating")
        )["avg"]
        cache.set(f"book_rating:{book.pk}", avg_rating, timeout=3600)
        logger.info(
            "New review for '%s' -- updated avg rating to %.1f",
            book.title,
            avg_rating or 0,
        )


@receiver(post_delete, sender=Book)
def cleanup_after_book_delete(sender, instance, **kwargs):
    """
    Perform cleanup when a book is deleted.
    """
    cache.delete(f"book_detail:{instance.pk}")
    cache.delete(f"book_rating:{instance.pk}")
    logger.info("Deleted book: %s (pk=%s)", instance.title, instance.pk)
```

#### Custom Signals

You can define your own signals for domain-specific events:

```python
# books/signals.py
from django.dispatch import Signal

# Define custom signal
order_completed = Signal()  # sent when an order is completed


# In the order processing code:
# order_completed.send(sender=Order, order=order_instance, user=request.user)


# Receiver for the custom signal:
@receiver(order_completed)
def send_order_confirmation_email(sender, order, user, **kwargs):
    """Send a confirmation email when an order is completed."""
    logger.info("Sending order confirmation to %s for order %s", user.email, order.id)
    # send_mail(...)
```

#### Comparison with Other Frameworks

The observer/event pattern appears everywhere:

- **Flask:** `blinker` signals library, `@app.before_request` / `@app.after_request` hooks
- **FastAPI:** lifespan events, middleware, dependency injection for cross-cutting concerns
- **Node.js / Express:** EventEmitter, middleware hooks
- **Rails:** Active Record callbacks (`before_save`, `after_create`, etc.)

> **Key Takeaway:** Signals are powerful for decoupling, but they make control flow invisible. If a piece of logic is critical to your business rules (e.g., "when an order is placed, reduce inventory"), put it in an explicit service function that is called directly, not in a signal receiver. Reserve signals for truly optional, cross-cutting side effects like cache invalidation, audit logging, or sending notifications.

---

### Admin & Rapid Development

The Django admin is an auto-generated CRUD interface that reads your model definitions and produces a fully functional web UI for creating, reading, updating, and deleting records. It is one of Django's most distinctive features and is invaluable for internal tooling, data inspection during development, and back-office operations.

The key concept is **scaffolding** or auto-generated interfaces: Rails has `rails scaffold`, Laravel has Nova, and many ORMs provide similar tools. The Django admin goes further than most because it is highly customizable without ejecting from the framework.

#### Basic Admin Registration

```python
# books/admin.py
from django.contrib import admin
from .models import Author, Publisher, Book, Review


# Simplest form: just register the model
admin.site.register(Publisher)
```

#### Customized Admin Classes

```python
# books/admin.py
from django.contrib import admin
from django.db.models import Avg, Count
from django.utils.html import format_html

from .models import Author, Publisher, Book, Review


class BookInline(admin.TabularInline):
    """Show books inline on the Author admin page."""
    model = Book
    extra = 0  # don't show empty forms
    fields = ("title", "isbn", "genre", "price", "is_available")
    readonly_fields = ("isbn",)
    show_change_link = True


class ReviewInline(admin.StackedInline):
    """Show reviews inline on the Book admin page."""
    model = Review
    extra = 0
    readonly_fields = ("author", "created_at")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "book_count", "birth_date", "created_at")
    list_filter = ("birth_date",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BookInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(book_count=Count("books"))

    @admin.display(description="Books", ordering="book_count")
    def book_count(self, obj):
        return obj.book_count


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "genre",
        "price",
        "is_available",
        "avg_rating_display",
        "published_date",
    )
    list_filter = ("genre", "is_available", "published_date")
    search_fields = ("title", "isbn", "author__name")
    list_editable = ("is_available", "price")  # edit directly in the list view
    list_per_page = 50
    date_hierarchy = "published_date"
    raw_id_fields = ("author",)  # use a popup instead of a dropdown (better for large tables)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ReviewInline]

    fieldsets = (
        (None, {
            "fields": ("title", "author", "publisher", "isbn"),
        }),
        ("Details", {
            "fields": ("genre", "page_count", "price", "published_date", "is_available"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),  # collapsible section
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("author", "publisher").annotate(
            avg_rating=Avg("reviews__rating"),
        )

    @admin.display(description="Avg Rating", ordering="avg_rating")
    def avg_rating_display(self, obj):
        if obj.avg_rating is None:
            return "-"
        stars = round(obj.avg_rating)
        return format_html(
            '<span title="{:.1f}">{}</span>',
            obj.avg_rating,
            "*" * stars,
        )

    # Custom admin actions
    @admin.action(description="Mark selected books as available")
    def make_available(self, request, queryset):
        count = queryset.update(is_available=True)
        self.message_user(request, f"{count} book(s) marked as available.")

    @admin.action(description="Mark selected books as unavailable")
    def make_unavailable(self, request, queryset):
        count = queryset.update(is_available=False)
        self.message_user(request, f"{count} book(s) marked as unavailable.")

    actions = [make_available, make_unavailable]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("book", "author", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("book__title", "author__username", "text")
    raw_id_fields = ("book", "author")
```

> **Key Takeaway:** The Django admin is not meant to be your user-facing application. It is an internal power tool. Invest time in customizing `list_display`, `list_filter`, `search_fields`, and custom actions to make your team's life easier. For public-facing interfaces, build proper views or APIs. The admin's real value is that it gives you a complete CRUD interface for free while you focus on building the parts of your application that are unique to your business.

---
