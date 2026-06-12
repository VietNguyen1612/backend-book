[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 5.1 RESTful APIs

## REST Principles

**Resources Identified by URIs**

REST (Representational State Transfer) is an architectural style that models everything as a *resource*. Each resource is identified by a URI (Uniform Resource Identifier), and the URI should use nouns, not verbs. The resource name describes *what* you are accessing, while the HTTP method describes *what you are doing* to it.

Bad design uses verbs in the URL:

```
GET /getUser?id=123
POST /createUser
POST /deleteUser?id=123
```

Good design uses nouns and lets HTTP methods convey the action:

```
GET    /users/123      # Retrieve user 123
POST   /users           # Create a new user
PUT    /users/123       # Replace user 123 entirely
PATCH  /users/123       # Partially update user 123
DELETE /users/123       # Delete user 123
```

Collections are represented by the plural noun (`/users`), and individual items are addressed by appending an identifier (`/users/123`). Nested resources model relationships: `/users/123/orders` returns orders belonging to user 123.

Here is a minimal FastAPI application that demonstrates these principles:

```python
# app.py -- FastAPI REST resource example
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional

app = FastAPI(title="User API", version="1.0.0")

# --- Models ---
class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserOut(BaseModel):
    id: int
    name: str
    email: str

# In-memory store for demonstration
_db: dict[int, dict] = {}
_next_id = 1

# --- Endpoints ---
@app.get("/users", response_model=list[UserOut])
def list_users():
    return list(_db.values())

@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    global _next_id
    record = {"id": _next_id, **user.model_dump()}
    _db[_next_id] = record
    _next_id += 1
    return record

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    if user_id not in _db:
        raise HTTPException(status_code=404, detail="User not found")
    return _db[user_id]

@app.put("/users/{user_id}", response_model=UserOut)
def replace_user(user_id: int, user: UserCreate):
    if user_id not in _db:
        raise HTTPException(status_code=404, detail="User not found")
    _db[user_id] = {"id": user_id, **user.model_dump()}
    return _db[user_id]

@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, user: UserUpdate):
    if user_id not in _db:
        raise HTTPException(status_code=404, detail="User not found")
    stored = _db[user_id]
    for key, value in user.model_dump(exclude_unset=True).items():
        stored[key] = value
    return stored

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int):
    if user_id not in _db:
        raise HTTPException(status_code=404, detail="User not found")
    del _db[user_id]
```

The equivalent in Django REST Framework:

```python
# views.py -- Django REST Framework example
from rest_framework import viewsets, serializers, status
from rest_framework.response import Response
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email"]

class UserViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet automatically provides list, create,
    retrieve, update, partial_update, and destroy actions.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

# urls.py
from rest_framework.routers import DefaultRouter
from .views import UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet)
urlpatterns = router.urls
```

**HTTP Methods as Verbs**

Each HTTP method carries specific semantics. Understanding idempotency (whether repeating the same request produces the same result) is essential for building reliable APIs:

| Method  | Purpose         | Idempotent | Safe | Request Body |
|---------|-----------------|------------|------|--------------|
| GET     | Read resource   | Yes        | Yes  | No           |
| POST    | Create resource | No         | No   | Yes          |
| PUT     | Full replace    | Yes        | No   | Yes          |
| PATCH   | Partial update  | No*        | No   | Yes          |
| DELETE  | Remove resource | Yes        | No   | Optional     |
| HEAD    | Headers only    | Yes        | Yes  | No           |
| OPTIONS | Allowed methods | Yes        | Yes  | No           |

*PATCH can be made idempotent depending on how the patch document is structured (e.g., JSON Merge Patch is idempotent, while JSON Patch may not be).

Example curl requests illustrating each method:

```bash
# GET -- retrieve a user
curl -X GET http://localhost:8000/users/1 \
  -H "Accept: application/json"

# Response: 200 OK
# {"id": 1, "name": "Alice", "email": "alice@example.com"}

# POST -- create a user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob", "email": "bob@example.com"}'

# Response: 201 Created
# {"id": 2, "name": "Bob", "email": "bob@example.com"}

# PUT -- full replace
curl -X PUT http://localhost:8000/users/2 \
  -H "Content-Type: application/json" \
  -d '{"name": "Robert", "email": "robert@example.com"}'

# Response: 200 OK
# {"id": 2, "name": "Robert", "email": "robert@example.com"}

# PATCH -- partial update
curl -X PATCH http://localhost:8000/users/2 \
  -H "Content-Type: application/json" \
  -d '{"name": "Bobby"}'

# Response: 200 OK
# {"id": 2, "name": "Bobby", "email": "robert@example.com"}

# DELETE -- remove a user
curl -X DELETE http://localhost:8000/users/2

# Response: 204 No Content
```

**Status Codes**

HTTP status codes communicate the outcome of a request. They are grouped by category, and choosing the correct code is critical for client-side error handling:

*2xx -- Success:*

- **200 OK** -- The request succeeded. Used for successful GET, PUT, PATCH.
- **201 Created** -- A new resource was created. Used for successful POST. Should include a `Location` header pointing to the new resource.
- **204 No Content** -- Success with no response body. Typically used for DELETE.

*3xx -- Redirection:*

- **301 Moved Permanently** -- Resource permanently moved. Clients should update bookmarks.
- **302 Found** -- Temporary redirect (historically ambiguous about method change).
- **307 Temporary Redirect** -- Like 302 but guarantees the method is not changed.
- **308 Permanent Redirect** -- Like 301 but guarantees the method is not changed.

*4xx -- Client Errors:*

- **400 Bad Request** -- Malformed syntax, invalid request body.
- **401 Unauthorized** -- Authentication required or failed. Should include `WWW-Authenticate` header.
- **403 Forbidden** -- Authenticated but not authorized for the resource.
- **404 Not Found** -- Resource does not exist.
- **409 Conflict** -- Request conflicts with current state (e.g., duplicate creation).
- **422 Unprocessable Entity** -- Syntactically valid but semantically invalid (e.g., validation errors).
- **429 Too Many Requests** -- Rate limit exceeded. Should include `Retry-After` header.

*5xx -- Server Errors:*

- **500 Internal Server Error** -- Unexpected server failure.
- **502 Bad Gateway** -- Upstream server returned an invalid response.
- **503 Service Unavailable** -- Server overloaded or down for maintenance. Should include `Retry-After` header.

**HATEOAS (Hypermedia as the Engine of Application State)**

HATEOAS is the constraint that responses should include hyperlinks to related resources and available actions. This allows clients to navigate the API without hardcoding URLs. In theory, a client only needs to know the entry point, and the API guides it from there.

```json
{
  "id": 42,
  "name": "Alice",
  "email": "alice@example.com",
  "_links": {
    "self":   {"href": "/users/42", "method": "GET"},
    "update": {"href": "/users/42", "method": "PUT"},
    "delete": {"href": "/users/42", "method": "DELETE"},
    "orders": {"href": "/users/42/orders", "method": "GET"}
  }
}
```

While HATEOAS is part of the formal REST definition (as described by Roy Fielding), it is rarely implemented fully in practice. Most real-world APIs settle for "pragmatic REST" -- well-designed URIs and HTTP methods without full hypermedia controls. If you do implement it, consider established formats like HAL (Hypertext Application Language) or JSON:API.

**Richardson Maturity Model**

The Richardson Maturity Model is a four-level scale (Leonard Richardson) that grades how "RESTful" an API actually is. It is the standard interview framing for "what makes an API REST?" and maps the constraints above onto increasing levels of maturity.

- **Level 0 -- The Swamp of POX (Plain Old XML).** A single URI and a single HTTP method (almost always `POST`) used as an RPC tunnel. The endpoint is an opaque method dispatcher; the action lives in the request body, not the URL or verb. SOAP and most XML-RPC services sit here: `POST /api` with a body that names the operation.
- **Level 1 -- Resources.** The API introduces multiple URIs, one per resource (`/users`, `/orders/42`), but still funnels everything through one verb (typically `POST`). You now address *things*, but you have not yet used HTTP methods to express *actions*.
- **Level 2 -- HTTP Verbs.** Resources are combined with the correct HTTP methods and status codes: `GET` to read, `POST` to create, `PUT`/`PATCH` to update, `DELETE` to remove, with `200`/`201`/`404`/etc. conveying outcome. This is where idempotency and caching start working as designed. The overwhelming majority of "REST APIs" in production live exactly here -- and that is generally considered good enough.
- **Level 3 -- Hypermedia Controls (HATEOAS).** Responses carry links describing the next available actions, so clients discover the state machine at runtime rather than hardcoding URLs (the `_links` block shown above).

```text
Level 0:  POST /api            (1 URI, 1 verb -- RPC tunnel)
Level 1:  POST /users/42       (many URIs, still 1 verb)
Level 2:  GET  /users/42  -> 200      (URIs + verbs + status codes)
          POST /users     -> 201
Level 3:  GET  /users/42  -> 200 + _links: {orders, deactivate, ...}
```

**How to read this output:** the jump that actually matters in practice is Level 1 -> Level 2 -- that is the line between an RPC-over-HTTP service and a real REST API, because only Level 2 lets the HTTP infrastructure (caches, proxies, retries on idempotent verbs) do its job. Level 3 is desirable but optional; saying "most production APIs are pragmatic Level 2" is the correct, senior answer in an interview, not a confession of cutting corners.

**Content Negotiation**

Content negotiation lets a single resource be served in different *representations* -- formats, encodings, languages, or API versions -- chosen by request headers rather than separate URLs. The client states its preferences and the server picks the best match it can produce.

- **`Accept`** -- what representation the client *wants back*. `Accept: application/json` asks for JSON; `Accept: application/json, application/xml;q=0.9` asks for JSON but will take XML (the `q` value is a 0-1 preference weight). If the server cannot satisfy it, it returns `406 Not Acceptable`.
- **`Content-Type`** -- what the client is *sending* in the request body (on `POST`/`PUT`/`PATCH`). If the server does not understand it, it returns `415 Unsupported Media Type`.
- **`Accept-Encoding`** -- which compression the client supports (`gzip`, `br`, `zstd`). The server compresses the body and echoes its choice in the `Content-Encoding` response header. This is transparent to application code but cuts payload size dramatically over the wire.
- **Versioning via `Accept`** -- a custom media type embeds the API version, e.g. `Accept: application/vnd.myapi.v2+json` (the header-versioning approach covered under *Versioning* above). The `vnd.` prefix marks it as a vendor-specific media type.

The server also advertises what it returns. A well-behaved response echoes the negotiated choices and lists the headers that affected selection in `Vary`, so caches do not serve the wrong representation:

```text
GET /users/42
Accept: application/json
Accept-Encoding: gzip, br

HTTP/1.1 200 OK
Content-Type: application/json
Content-Encoding: gzip
Vary: Accept, Accept-Encoding
```

**How to read this output:** the `Vary: Accept, Accept-Encoding` header is the load-bearing detail. It tells every cache between client and server that the response body depends on those two request headers, so a gzipped JSON copy is never handed to a client that asked for XML or cannot decompress. Omitting `Vary` is a classic production bug: a CDN caches one representation and serves it to everyone, so a mobile client that requested `application/vnd.myapi.v1+json` silently receives the v2 body cached for someone else.

> **Key Takeaway:** The core of REST is a clean division of labor: the URI names the *resource* (a noun) and the HTTP method names the *action*, while the status code reports the *outcome*. Get those three right -- nouns in paths, correct method semantics including idempotency, and accurate status codes -- and you have a predictable API even without full HATEOAS, which most teams skip.

## API Design Best Practices

**Versioning**

APIs evolve over time, and breaking changes are inevitable. Versioning strategies let you introduce new behavior without disrupting existing clients. The three most common approaches are:

1. **URL path versioning** (most common and most visible):

   ```
   GET /api/v1/users/123
   GET /api/v2/users/123
   ```

2. **Header versioning** (cleaner URLs, harder to test in a browser):

   ```bash
   curl -H "Accept: application/vnd.myapi.v2+json" \
        http://localhost:8000/users/123
   ```

3. **Query parameter versioning** (simple but can pollute caching):

   ```
   GET /users/123?version=2
   ```

URL path versioning is the most widely adopted because it is explicit, easy to understand, and works well with API gateways, documentation tools, and browser testing. Here is how to implement it in FastAPI:

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()

v1_router = APIRouter(prefix="/api/v1")
v2_router = APIRouter(prefix="/api/v2")

@v1_router.get("/users/{user_id}")
def get_user_v1(user_id: int):
    return {"id": user_id, "name": "Alice"}          # v1: flat

@v2_router.get("/users/{user_id}")
def get_user_v2(user_id: int):
    return {                                           # v2: richer
        "data": {"id": user_id, "name": "Alice"},
        "meta": {"api_version": "2.0"},
    }

app.include_router(v1_router)
app.include_router(v2_router)
```

**Pagination**

Returning all records in a single response is impractical for large datasets. There are three main pagination strategies, each with different trade-offs:

*Offset-based pagination* is the simplest. The client specifies a page number and page size. The server uses SQL `OFFSET` and `LIMIT` to fetch the window.

```bash
curl "http://localhost:8000/api/v1/users?page=2&limit=20"
```

```json
{
  "data": [ {"id": 21, "name": "..."}, {"id": 22, "name": "..."} ],
  "pagination": {
    "page": 2,
    "limit": 20,
    "total": 153
  }
}
```

The downside: if rows are inserted or deleted between page requests, items can be skipped or duplicated. Also, large offsets are slow because the database must scan through all preceding rows.

*Cursor-based pagination* solves the consistency problem. Instead of a page number, the client passes an opaque cursor (typically a base64-encoded pointer to the last item seen). The server fetches items after that cursor.

```bash
curl "http://localhost:8000/api/v1/users?cursor=eyJpZCI6IDIwfQ&limit=20"
```

```json
{
  "data": [ {"id": 21, "name": "..."}, {"id": 22, "name": "..."} ],
  "pagination": {
    "next_cursor": "eyJpZCI6IDQwfQ",
    "has_more": true
  }
}
```

*Keyset pagination* is a variation that uses the actual sort column value(s) as the cursor. It is highly efficient because it can leverage database indexes directly.

```bash
curl "http://localhost:8000/api/v1/users?after_id=100&limit=20"
```

The corresponding SQL: `SELECT * FROM users WHERE id > 100 ORDER BY id LIMIT 20;`

Running that query against a populated table returns something like:

```text
 id  | name      | created_at
-----+-----------+---------------------
 101 | User 101  | 2025-01-02 09:14:00
 102 | User 102  | 2025-01-02 09:15:31
 ...
 120 | User 120  | 2025-01-02 10:02:11
(20 rows)
```

**How to read this output:** Notice there is no `OFFSET` — the `WHERE id > 100` predicate jumps straight to the right slice using the primary-key index, so the database reads ~20 rows instead of scanning the 100 it would skip with `OFFSET 100`. That difference is invisible at this scale but becomes the gap between a 5ms and a multi-second query at page 50,000, which is exactly the "deep pagination" failure interviewers probe and that takes down production list endpoints on large tables.

FastAPI implementation of cursor-based pagination:

```python
import base64, json
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.get("/api/v1/users")
def list_users(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    # Decode cursor
    after_id = 0
    if cursor:
        after_id = json.loads(base64.b64decode(cursor))["id"]

    # Query database (pseudo-code)
    # users = db.execute(
    #     "SELECT * FROM users WHERE id > :after ORDER BY id LIMIT :lim",
    #     {"after": after_id, "lim": limit + 1},
    # )
    users = [{"id": after_id + i, "name": f"User {after_id + i}"}
             for i in range(1, limit + 2)]  # demo data

    has_more = len(users) > limit
    users = users[:limit]

    next_cursor = None
    if has_more and users:
        next_cursor = base64.b64encode(
            json.dumps({"id": users[-1]["id"]}).encode()
        ).decode()

    return {
        "data": users,
        "pagination": {
            "next_cursor": next_cursor,
            "has_more": has_more,
        },
    }
```

Calling the endpoint with no cursor (`GET /api/v1/users?limit=3`) returns:

```text
{
  "data": [
    {"id": 1, "name": "User 1"},
    {"id": 2, "name": "User 2"},
    {"id": 3, "name": "User 3"}
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6IDN9",
    "has_more": true
  }
}
```

**How to read this output:** The handler deliberately asks the database for `limit + 1` rows; if it gets back more than `limit`, it knows there is at least one more page, sets `has_more: true`, and trims the extra row before responding. That is why you get a `next_cursor` here — it is the base64 encoding of `{"id": 3}`, the id of the last row actually returned. The client treats it as opaque and simply echoes it back on the next call (`?cursor=eyJpZCI6IDN9`); it should never decode or fabricate it. This "fetch one extra to detect more" trick avoids a second `COUNT(*)` query just to compute `has_more`, which matters because `COUNT(*)` on a large table is itself a slow scan.

> **Common pitfall:** Cursor pagination assumes a stable, unique sort key. If you paginate on a non-unique column (e.g. `created_at` with duplicate timestamps), rows sharing the boundary value get skipped or repeated across pages. Always include a tiebreaker like `(created_at, id)` in both the `ORDER BY` and the cursor.

**Filtering and Sorting**

A well-designed API allows clients to filter, sort, and select only the fields they need. This reduces payload size and eliminates the need for custom endpoints.

```bash
# Filter active users, sort by newest first, return only id and name
curl "http://localhost:8000/api/v1/users?status=active&sort=-created_at&fields=id,name"
```

The minus sign (`-`) before a field name indicates descending order. Multiple sort criteria can be comma-separated: `sort=-created_at,name`.

Field selection (also called sparse fieldsets) lets the client request only the columns it needs:

```bash
curl "http://localhost:8000/api/v1/users?fields=id,name,email"
```

This is especially valuable for mobile clients on slow networks. Keep the filtering and sorting patterns consistent across every endpoint in your API.

```python
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.get("/api/v1/users")
def list_users(
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: Optional[str] = Query(None, description="Sort field, prefix - for desc"),
    fields: Optional[str] = Query(None, description="Comma-separated field names"),
):
    # Build query dynamically based on parameters
    query = "SELECT * FROM users WHERE 1=1"
    params = {}

    if status:
        query += " AND status = :status"
        params["status"] = status

    if sort:
        direction = "DESC" if sort.startswith("-") else "ASC"
        column = sort.lstrip("-")
        allowed = {"created_at", "name", "email"}
        if column in allowed:
            query += f" ORDER BY {column} {direction}"

    # Execute query, then filter fields in serialization
    results = [{"id": 1, "name": "Alice", "email": "a@b.com",
                "status": "active", "created_at": "2025-01-01"}]

    if fields:
        requested = set(fields.split(","))
        results = [{k: v for k, v in r.items() if k in requested}
                   for r in results]

    return {"data": results}
```

For the request `GET /api/v1/users?status=active&sort=-created_at&fields=id,name`, the response is the filtered, field-trimmed projection:

```text
{
  "data": [
    {"id": 1, "name": "Alice"}
  ]
}
```

**How to read this output:** Only `id` and `name` survive because `fields=id,name` drove the sparse-fieldset filter — `email`, `status`, and `created_at` were dropped during serialization even though the row carries them. The detail that matters for production and interviews is the `allowed = {"created_at", "name", "email"}` allowlist guarding the `ORDER BY`: because `column` is interpolated directly into the SQL string (it cannot be a bound parameter — you cannot parameterize a column name), an attacker passing `sort=-(SELECT ...)` would otherwise inject. Checking the column against a fixed set before f-stringing it is what makes this safe.

> **Common pitfall:** Filter and sort values can usually be bound as query parameters, but identifiers (column and table names) cannot. Reviewers should treat any f-string or concatenation that places user input into a SQL identifier position as a SQL-injection finding unless it is gated by an allowlist exactly like the one above.

**Error Format**

A consistent error response structure across every endpoint makes client-side error handling predictable and debuggable. Every error response should include a machine-readable code, a human-readable message, and -- for validation errors -- a list of per-field details.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Not a valid email address"
      },
      {
        "field": "name",
        "message": "Name must be at least 2 characters"
      }
    ]
  }
}
```

In FastAPI, you can achieve this with custom exception handlers:

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in error["loc"][1:]),
            "message": error["msg"],
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": details,
            }
        },
    )

class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )
```

**Idempotency**

Idempotency means that making the same request multiple times produces the same result as making it once. GET, PUT, and DELETE are naturally idempotent, but POST is not. For operations that must not be duplicated (such as charging a credit card), the client sends an `Idempotency-Key` header with a unique value. The server stores the result keyed by that value, and if the same key is sent again, it returns the stored result without re-executing the operation.

```bash
# Client sends a unique key with the payment request
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"amount": 99.99, "currency": "USD", "recipient": "merchant_42"}'

# If the network fails and the client retries with the same key,
# the server returns the original response without charging again.
```

A simple implementation using Redis:

```python
import json, hashlib
from fastapi import FastAPI, Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis

app = FastAPI()
r = redis.Redis()

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST":
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        cache_key = f"idempotency:{idem_key}"

        # Check for cached response
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return Response(
                content=data["body"],
                status_code=data["status"],
                media_type="application/json",
            )

        # Execute the request
        response = await call_next(request)

        # Cache the response for 24 hours
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        r.setex(cache_key, 86400, json.dumps({
            "status": response.status_code,
            "body": body.decode(),
        }))

        return Response(
            content=body,
            status_code=response.status_code,
            media_type="application/json",
        )

app.add_middleware(IdempotencyMiddleware)
```

**Rate Limiting**

Rate limiting protects your API from abuse and ensures fair usage across clients. The server should communicate rate limit status through standard headers so clients can self-regulate:

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 73
X-RateLimit-Reset: 1711324800
```

When the limit is exceeded:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711324800

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry after 30 seconds."
  }
}
```

A token-bucket rate limiter with FastAPI using Redis:

```python
import time, redis
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
r = redis.Redis()

RATE_LIMIT = 100       # requests per window
WINDOW_SECONDS = 3600  # 1 hour

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    key = f"ratelimit:{client_ip}"
    current = r.get(key)

    if current and int(current) >= RATE_LIMIT:
        ttl = r.ttl(key)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(ttl),
                "X-RateLimit-Limit": str(RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + ttl),
            },
        )

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, WINDOW_SECONDS)
    result = pipe.execute()
    count = result[0]

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(max(0, RATE_LIMIT - count))
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + r.ttl(key))
    return response
```

**Bulk Operations**

For batch workloads (importing data, updating many records at once), individual requests per item cause excessive HTTP overhead. A bulk endpoint accepts an array of items and returns per-item results, including partial success handling:

```bash
curl -X POST http://localhost:8000/api/v1/users/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"name": "Alice", "email": "alice@example.com"},
      {"name": "Bob", "email": "invalid-email"},
      {"name": "Charlie", "email": "charlie@example.com"}
    ]
  }'
```

Response with partial success (overall HTTP 207 Multi-Status or 200):

```json
{
  "results": [
    {"index": 0, "status": "created", "data": {"id": 1, "name": "Alice"}},
    {"index": 1, "status": "error", "error": {"field": "email", "message": "Invalid email"}},
    {"index": 2, "status": "created", "data": {"id": 2, "name": "Charlie"}}
  ],
  "summary": {
    "total": 3,
    "succeeded": 2,
    "failed": 1
  }
}
```

## API Documentation

**OpenAPI (Swagger)**

OpenAPI is the industry-standard specification for describing REST APIs in a machine-readable format (YAML or JSON). From a single specification file, you can auto-generate interactive documentation (Swagger UI, ReDoc), client SDKs in dozens of languages, server stubs, and test suites.

FastAPI generates OpenAPI specs automatically from your type annotations:

```python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI(
    title="User Service",
    description="Manages user accounts",
    version="1.0.0",
    servers=[{"url": "https://api.example.com", "description": "Production"}],
)

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    name: str
    email: EmailStr

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Alice", "email": "alice@example.com"}
            ]
        }
    }

class UserOut(BaseModel):
    id: int
    name: str
    email: str

@app.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    summary="Create a user",
    description="Creates a new user account and returns the created record.",
    tags=["Users"],
)
def create_user(user: UserCreate):
    return {"id": 1, **user.model_dump()}

# Visit http://localhost:8000/docs for Swagger UI
# Visit http://localhost:8000/redoc for ReDoc
# GET  http://localhost:8000/openapi.json for the raw spec
```

Fetching `GET /openapi.json` returns the machine-readable contract FastAPI derived from those type hints (abridged):

```text
{
  "openapi": "3.1.0",
  "info": {"title": "User Service", "description": "Manages user accounts", "version": "1.0.0"},
  "servers": [{"url": "https://api.example.com", "description": "Production"}],
  "paths": {
    "/users": {
      "post": {
        "summary": "Create a user",
        "tags": ["Users"],
        "responses": {"201": {"description": "Successful Response", ...}},
        "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserCreate"}}}}
      }
    }
  },
  "components": {"schemas": {"UserCreate": {"properties": {"name": {"type": "string"}, "email": {"type": "string", "format": "email"}}, "required": ["name", "email"]}}}
}
```

**How to read this output:** Nothing here was hand-written — the `summary`, `tags`, and `201` came from the decorator arguments, while the `UserCreate` schema (including `format: "email"` and the `required` list) was reflected out of the Pydantic model and `EmailStr` type. This is why FastAPI's docs cannot drift from the code: the spec *is* the code, re-derived on every boot. The same `$ref`-based schema is what client-SDK generators and contract-testing tools consume, so accurate type annotations directly buy you accurate generated clients.

**Design-First Approach**

In a design-first workflow, you write the OpenAPI specification before any implementation code. This spec becomes the contract between frontend and backend teams. Both sides can work in parallel: the frontend team builds against mock data generated from the spec, while the backend team implements the actual logic.

The workflow looks like this:

1. Write the OpenAPI YAML/JSON spec collaboratively.
2. Review the API design in a pull request (catch design issues early).
3. Generate server stubs and client SDKs from the spec.
4. Implement the server logic.
5. Validate the implementation against the spec using contract tests.

Tools like `openapi-generator`, Prism (mock server), and Schemathesis (property-based testing against the spec) support this workflow.

**Living Documentation**

Documentation that drifts from the actual implementation is worse than no documentation -- it misleads consumers. Keep docs synchronized with code by:

- Auto-generating specs from code annotations (as FastAPI does).
- Running contract tests in CI that validate the implementation against the spec.
- Including clear descriptions, realistic request/response examples, error codes, and authentication requirements on every endpoint.

> **Key Takeaway:** REST APIs succeed or fail based on consistency. Pick conventions for URL structure, error format, pagination, and versioning -- then enforce them across every endpoint. Use OpenAPI as the single source of truth, and validate it automatically in CI.

*Last reviewed: 2026-06-08*
