[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 5.2 Beyond REST

### GraphQL

> [!NOTE]
> **Beginner's Mental Model — GraphQL:**
> Think of a traditional REST API as a fixed set menu at a restaurant: you order Item #3, and you get exactly what's on that plate, even if you only wanted the side salad. GraphQL, on the other hand, is a buffet. You walk up with a plate and request exactly the food items you want, in the exact quantities you need, and nothing more.

**Schema-First Design**

GraphQL uses a strongly typed schema to define the shape of your API. The schema declares types (the data structures), queries (read operations), and mutations (write operations). Clients can request exactly the fields they need, no more and no less. The schema also supports introspection -- clients can query the schema itself to discover available types and operations, making the API self-documenting.

Here is a complete example using Strawberry, a modern Python GraphQL library:

```python
# schema.py -- Strawberry GraphQL example
import strawberry
from typing import Optional

# --- Types ---
@strawberry.type
class User:
    id: int
    name: str
    email: str

@strawberry.type
class Post:
    id: int
    title: str
    content: str
    author: User

# --- In-memory data ---
USERS = {
    1: User(id=1, name="Alice", email="alice@example.com"),
    2: User(id=2, name="Bob", email="bob@example.com"),
}

POSTS = [
    Post(id=1, title="GraphQL Intro", content="...", author=USERS[1]),
    Post(id=2, title="REST vs GraphQL", content="...", author=USERS[2]),
]

# --- Input types ---
@strawberry.input
class CreateUserInput:
    name: str
    email: str

# --- Query & Mutation ---
@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: int) -> Optional[User]:
        return USERS.get(id)

    @strawberry.field
    def users(self) -> list[User]:
        return list(USERS.values())

    @strawberry.field
    def posts(self) -> list[Post]:
        return POSTS

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, input: CreateUserInput) -> User:
        new_id = max(USERS.keys()) + 1
        user = User(id=new_id, name=input.name, email=input.email)
        USERS[new_id] = user
        return user

schema = strawberry.Schema(query=Query, mutation=Mutation)

# --- FastAPI integration ---
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

app = FastAPI()
app.include_router(GraphQLRouter(schema), prefix="/graphql")
```

And the equivalent with Graphene (an older but still widely used library):

```python
# schema.py -- Graphene example
import graphene

class UserType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    email = graphene.String()

class Query(graphene.ObjectType):
    user = graphene.Field(UserType, id=graphene.Int(required=True))
    users = graphene.List(UserType)

    def resolve_user(self, info, id):
        # Fetch from database
        return {"id": id, "name": "Alice", "email": "alice@example.com"}

    def resolve_users(self, info):
        return [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ]

class CreateUser(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)

    user = graphene.Field(UserType)

    def mutate(self, info, name, email):
        user = {"id": 3, "name": name, "email": email}
        return CreateUser(user=user)

class Mutation(graphene.ObjectType):
    create_user = CreateUser.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
```

Example GraphQL queries and their responses:

```bash
# Query a specific user with only the fields we need
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ user(id: 1) { name email } }"
  }'

# Response:
# {
#   "data": {
#     "user": { "name": "Alice", "email": "alice@example.com" }
#   }
# }

# Query posts with nested author data
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ posts { title author { name } } }"
  }'

# Response:
# {
#   "data": {
#     "posts": [
#       { "title": "GraphQL Intro", "author": { "name": "Alice" } },
#       { "title": "REST vs GraphQL", "author": { "name": "Bob" } }
#     ]
#   }
# }

# Mutation to create a user
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createUser(input: {name: \"Charlie\", email: \"charlie@example.com\"}) { id name } }"
  }'
```

**Resolvers**

Resolvers are the functions that fetch data for each field in the schema. Every field in a GraphQL type has a corresponding resolver. When a query is executed, the GraphQL engine walks the query tree and calls the appropriate resolver for each field. Resolvers can pull data from any source: a database, a REST API, a cache, or a computation.

The resolver chain works hierarchically. If a `Post` type has an `author` field of type `User`, the engine first resolves the `Post`, then calls the `author` resolver on the result to resolve the nested `User`.

> [!NOTE]
> **Beginner's Mental Model — DataLoader:**
> Imagine a waiter who needs to bring drinks to 10 guests. A naive waiter would walk to the bar, grab one drink, walk back to the table, and repeat this 10 times (the N+1 problem). A smart waiter using a **DataLoader** waits until everyone has placed their order, walks to the bar once with a large tray, collects all 10 drinks in a single batch, and distributes them all at once.

**The N+1 Problem and DataLoader**

The N+1 problem is the most common performance pitfall in GraphQL. Consider a query that fetches 50 posts with their authors. The naive approach executes 1 query for the posts, then 50 individual queries for each author -- 51 queries total.

DataLoader solves this by batching and caching within a single request. Instead of fetching one author at a time, it collects all requested author IDs, executes a single batch query, and distributes results back to each resolver.

```python
# dataloader.py -- Strawberry DataLoader example
import strawberry
from strawberry.dataloader import DataLoader
from typing import Optional

# Simulate a database
USER_DB = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
}

async def batch_load_users(keys: list[int]) -> list[Optional[dict]]:
    """
    This function is called ONCE with ALL requested user IDs.
    Instead of N queries, we execute 1 query:
    SELECT * FROM users WHERE id IN (1, 2, 3, ...)
    """
    print(f"Batch loading users: {keys}")  # You'll see this called once
    return [USER_DB.get(key) for key in keys]

@strawberry.type
class User:
    id: int
    name: str
    email: str

@strawberry.type
class Post:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.types.Info) -> Optional[User]:
        # This uses the DataLoader -- even if 50 posts call this,
        # batch_load_users runs once with all 50 author IDs.
        data = await info.context["user_loader"].load(self.author_id)
        if data:
            return User(**data)
        return None

@strawberry.type
class Query:
    @strawberry.field
    def posts(self) -> list[Post]:
        return [
            Post(id=1, title="Post A", author_id=1),
            Post(id=2, title="Post B", author_id=2),
            Post(id=3, title="Post C", author_id=1),  # same author as Post A
        ]

async def get_context():
    return {"user_loader": DataLoader(load_fn=batch_load_users)}

schema = strawberry.Schema(query=Query)
```

When a client runs `{ posts { title author { name } } }` against this schema, the three posts reference only two distinct authors (IDs 1 and 2, since Post A and Post C share author 1). The server log shows a single batched call:

```text
Batch loading users: [1, 2]
```

**How to read this output:** The line prints exactly once even though three `author` resolvers fired -- that is the whole point. DataLoader gathers every `.load()` call made during one tick of the event loop, deduplicates and batches the keys, then invokes `batch_load_users` a single time with `[1, 2]` (per-request caching collapses the duplicate request for ID 1, so the batch carries only the distinct keys). Without DataLoader you would instead see three separate "Batch loading users" lines -- the N+1 pattern. In production this is the difference between 1 `SELECT ... WHERE id IN (...)` and 50 round-trips per request; it is also the single most common GraphQL question in system-design interviews.

> **Common pitfall:** A DataLoader caches and batches only within one request, so you must create a fresh loader per request (as `get_context` does here). Sharing one loader instance across requests leaks stale data between users and is a real-world correctness bug, not just an optimization miss.

**Pagination: Relay-Style Connections**

GraphQL has a standardized pagination pattern called Relay connections. It uses cursors for consistent pagination and provides metadata about whether more pages exist:

```graphql
query {
  users(first: 10, after: "cursor_abc123") {
    edges {
      node {
        id
        name
        email
      }
      cursor
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
```

Response:

```json
{
  "data": {
    "users": {
      "edges": [
        { "node": {"id": 11, "name": "User 11"}, "cursor": "Y3Vyc29yXzEx" },
        { "node": {"id": 12, "name": "User 12"}, "cursor": "Y3Vyc29yXzEy" }
      ],
      "pageInfo": {
        "hasNextPage": true,
        "hasPreviousPage": true,
        "startCursor": "Y3Vyc29yXzEx",
        "endCursor": "Y3Vyc29yXzEy"
      }
    }
  }
}
```

The four pieces of the connection envelope each have a specific job, and knowing the vocabulary is the difference between "I've seen this shape" and "I understand the spec":

- **`node`** -- the actual domain object (the `User`). This is what a naive list endpoint would have returned directly.
- **`edge`** -- a wrapper around a single `node` that pairs it with its `cursor` and is the natural home for *relationship* metadata. For example, an edge on a `friends` connection can carry `friendedAt` -- a property of the connection between the two records, not of either record itself. This is why connections wrap nodes in edges instead of returning a bare list.
- **`cursor`** -- an opaque, per-item pointer (typically base64). The client never parses it; it passes it back as `after:` (or `before:`) to resume from exactly that position. Because it encodes the sort key rather than an offset, it is stable under concurrent inserts and deletes.
- **`pageInfo`** -- page-level metadata: `hasNextPage`/`hasPreviousPage` let the UI enable or disable the next/prev buttons without a count query, and `startCursor`/`endCursor` are shortcuts to the first and last edge cursors for paging in either direction.

The connection also conventionally exposes `totalCount` when the backend can afford it, but Relay deliberately makes that optional precisely because `COUNT(*)` is expensive on large tables -- the same reason REST cursor pagination prefers a "fetch one extra to detect more" trick over a count.

**Authorization**

GraphQL allows authorization at multiple granularity levels. You can protect entire types, individual fields, or specific resolver logic. Directive-based authorization is a clean declarative approach:

```python
# Field-level authorization with Strawberry
import strawberry
from functools import wraps

def admin_only(func):
    @wraps(func)
    def wrapper(self, info: strawberry.types.Info, **kwargs):
        user = info.context.get("current_user")
        if not user or "admin" not in user.get("roles", []):
            raise PermissionError("Admin access required")
        return func(self, info, **kwargs)
    return wrapper

@strawberry.type
class User:
    id: int
    name: str
    email: str                # Anyone can see

    @strawberry.field
    def ssn(self, info: strawberry.types.Info) -> str:
        # Only admins can see SSN
        user = info.context.get("current_user")
        if not user or "admin" not in user.get("roles", []):
            return "***-**-****"
        return "123-45-6789"
```

Always implement query depth limiting and complexity analysis to prevent abusive queries that could overwhelm your server:

```python
# Depth limiting prevents deeply nested queries like:
# { user { posts { author { posts { author { posts { ... } } } } } } }

# With Strawberry, you can add query validation extensions:
from strawberry.extensions import QueryDepthLimiter

schema = strawberry.Schema(
    query=Query,
    extensions=[QueryDepthLimiter(max_depth=10)],
)
```

Depth limiting alone is not enough. A query can be *shallow yet enormous* -- `{ users(first: 1000) { posts(first: 1000) { comments(first: 1000) { author { name } } } } }` is only four levels deep but asks for up to a billion objects. **Query complexity analysis** assigns each field a cost (often weighted by its `first`/`last` pagination argument so a list multiplies the cost of its children) and rejects the request before execution if the total exceeds a budget. This is what stops a single crafted query from exhausting CPU, memory, and database connections -- the GraphQL equivalent of rate limiting, since one POST can do the damage of thousands of REST calls.

```python
# Cost-based limiting: budget the whole query, not just its depth
from strawberry.extensions import QueryDepthLimiter, MaxTokensLimiter

schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),   # caps nesting
        MaxTokensLimiter(max_token_count=1000),  # caps overall query size
    ],
)
# Dedicated cost libraries (e.g. graphql-core cost validators, or
# Apollo's @cost directive) let you weight individual fields and
# multiply by list-size arguments for a true complexity score.
```

In production you also enforce **persisted queries** (the client registers approved query documents by hash and sends only the hash), so arbitrary attacker-authored queries never reach the server at all -- the strongest defense, since depth and complexity limits only constrain queries you have already agreed to run.

**When to Choose GraphQL vs REST**

GraphQL excels when: (a) multiple clients (web, mobile, IoT) need different data shapes from the same API, (b) data is deeply nested and would require many REST round-trips, (c) the frontend team needs to iterate rapidly without waiting for backend changes.

REST is better when: (a) your API is simple CRUD with flat resources, (b) HTTP caching matters (REST caching works out of the box, while GraphQL requires more effort since everything is POST), (c) you need file uploads (GraphQL file uploads are cumbersome), (d) the API is primarily server-to-server.

> **Key Takeaway:** GraphQL trades simplicity for flexibility. It shines in complex, multi-client environments but introduces challenges around caching, authorization complexity, and the N+1 problem. DataLoader is not optional -- it is a requirement for any production GraphQL API.

### gRPC

> [!NOTE]
> **Beginner's Mental Model — gRPC:**
> Imagine two remote offices communicating. Instead of writing long letters in plain text (like JSON) and posting them in mailboxes (REST over HTTP/1.1), they install a high-speed intercom system (gRPC over HTTP/2). They speak in a highly compressed code language (Protocol Buffers binary format) that only they understand. It's incredibly fast, direct, and eliminates any guesswork because both ends must strictly follow the same pre-defined script (the `.proto` file).

**Protocol Buffers (protobuf)**

gRPC uses Protocol Buffers as its interface definition language and serialization format. You define your service and message types in `.proto` files, then use the `protoc` compiler to generate client and server code in any supported language. Protobuf messages are serialized to a compact binary format that is 5-10x smaller than JSON and 5-10x faster to serialize/deserialize.

Here is a complete example. First, the `.proto` definition:

```protobuf
// user_service.proto
syntax = "proto3";

package userservice;

// The service definition
service UserService {
  // Unary RPC -- simple request/response
  rpc GetUser (GetUserRequest) returns (UserResponse);
  rpc CreateUser (CreateUserRequest) returns (UserResponse);
  rpc ListUsers (ListUsersRequest) returns (ListUsersResponse);

  // Server streaming -- server sends a stream of responses
  rpc WatchUsers (WatchUsersRequest) returns (stream UserEvent);

  // Client streaming -- client sends a stream of requests
  rpc BulkCreateUsers (stream CreateUserRequest) returns (BulkCreateResponse);

  // Bidirectional streaming
  rpc Chat (stream ChatMessage) returns (stream ChatMessage);
}

// Message definitions
message GetUserRequest {
  int32 id = 1;
}

message CreateUserRequest {
  string name = 1;
  string email = 2;
}

message UserResponse {
  int32 id = 1;
  string name = 2;
  string email = 3;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
}

message ListUsersResponse {
  repeated UserResponse users = 1;
  string next_page_token = 2;
}

message WatchUsersRequest {}

message UserEvent {
  string event_type = 1;  // "created", "updated", "deleted"
  UserResponse user = 2;
}

message BulkCreateResponse {
  int32 created_count = 1;
}

message ChatMessage {
  string sender = 1;
  string text = 2;
}
```

Generate Python code from the proto file:

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc \
  -I. \
  --python_out=. \
  --grpc_python_out=. \
  user_service.proto
```

This generates `user_service_pb2.py` (message classes) and `user_service_pb2_grpc.py` (service stubs).

**Implementing the gRPC Server**

```python
# server.py -- gRPC server implementation
import grpc
from concurrent import futures
import user_service_pb2 as pb2
import user_service_pb2_grpc as pb2_grpc
import time

USERS = {}
NEXT_ID = 1

class UserServiceServicer(pb2_grpc.UserServiceServicer):

    def GetUser(self, request, context):
        """Unary RPC: single request, single response."""
        user = USERS.get(request.id)
        if not user:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"User {request.id} not found")
            return pb2.UserResponse()
        return user

    def CreateUser(self, request, context):
        """Unary RPC: create a user."""
        global NEXT_ID
        user = pb2.UserResponse(
            id=NEXT_ID, name=request.name, email=request.email
        )
        USERS[NEXT_ID] = user
        NEXT_ID += 1
        return user

    def ListUsers(self, request, context):
        """Unary RPC: list users with pagination."""
        all_users = list(USERS.values())
        page_size = request.page_size or 10
        start = int(request.page_token) if request.page_token else 0
        page = all_users[start:start + page_size]
        next_token = str(start + page_size) if start + page_size < len(all_users) else ""
        return pb2.ListUsersResponse(users=page, next_page_token=next_token)

    def WatchUsers(self, request, context):
        """Server streaming: push events to client."""
        # In a real app, this would listen to a message bus
        while context.is_active():
            # Simulate an event every 2 seconds
            event = pb2.UserEvent(
                event_type="heartbeat",
                user=pb2.UserResponse(id=0, name="system", email=""),
            )
            yield event
            time.sleep(2)

    def BulkCreateUsers(self, request_iterator, context):
        """Client streaming: receive a stream of create requests."""
        count = 0
        global NEXT_ID
        for request in request_iterator:
            user = pb2.UserResponse(
                id=NEXT_ID, name=request.name, email=request.email
            )
            USERS[NEXT_ID] = user
            NEXT_ID += 1
            count += 1
        return pb2.BulkCreateResponse(created_count=count)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server running on port 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
```

**Implementing the gRPC Client**

```python
# client.py -- gRPC client
import grpc
import user_service_pb2 as pb2
import user_service_pb2_grpc as pb2_grpc

def run():
    channel = grpc.insecure_channel("localhost:50051")
    stub = pb2_grpc.UserServiceStub(channel)

    # Unary: create a user
    response = stub.CreateUser(
        pb2.CreateUserRequest(name="Alice", email="alice@example.com")
    )
    print(f"Created: {response.id} - {response.name}")

    # Unary: get a user
    response = stub.GetUser(pb2.GetUserRequest(id=1))
    print(f"Fetched: {response.name} ({response.email})")

    # Server streaming: watch for events
    for event in stub.WatchUsers(pb2.WatchUsersRequest()):
        print(f"Event: {event.event_type}")
        break  # just read one for demo

    # Client streaming: bulk create
    def generate_users():
        for name in ["Bob", "Charlie", "Diana"]:
            yield pb2.CreateUserRequest(name=name, email=f"{name.lower()}@example.com")

    result = stub.BulkCreateUsers(generate_users())
    print(f"Bulk created: {result.created_count} users")

if __name__ == "__main__":
    run()
```

With the server running, the client prints:

```text
Created: 1 - Alice
Fetched: Alice (alice@example.com)
Event: heartbeat
Bulk created: 3 users
```

**How to read this output:** Each line maps to one RPC pattern. `Created`/`Fetched` are unary calls -- a single request and a single response, the gRPC equivalent of `POST` then `GET`. `Event: heartbeat` is one frame pulled from the *server-streaming* `WatchUsers` call; the loop `break`s after one, but the server would keep yielding every two seconds over the same open HTTP/2 stream. `Bulk created: 3 users` is the *client-streaming* result: the client streamed three `CreateUserRequest` messages and the server replied once with the count. Note IDs depend on server state -- because the server holds users in an in-memory dict that resets on restart, a fresh run gives Alice `id=1`; re-running against a still-live server would continue from where it left off, a classic source of "works once, fails on replay" confusion in stateful demos.

**Communication Patterns**

gRPC supports four communication patterns, each suited to different use cases:

| Pattern              | Description                     | Use Case                        |
|----------------------|---------------------------------|---------------------------------|
| Unary                | Single request, single response | Standard CRUD operations        |
| Server streaming     | Single request, stream response | Live feeds, file downloads      |
| Client streaming     | Stream request, single response | File uploads, bulk ingestion    |
| Bidirectional stream | Stream both directions          | Chat, real-time collaboration   |

**HTTP/2 Foundation**

gRPC is built on HTTP/2, which provides multiplexing (multiple requests over a single TCP connection), header compression (HPACK), and binary framing. This means lower latency and better connection utilization compared to HTTP/1.1 REST. A single gRPC connection can handle many concurrent RPCs without head-of-line blocking.

**Interceptors**

Interceptors are gRPC's equivalent of middleware. They allow you to add cross-cutting concerns such as authentication, logging, metrics, and retry logic:

```python
# Logging interceptor
import grpc, time

class LoggingInterceptor(grpc.UnaryUnaryClientInterceptor):
    def intercept_unary_unary(self, continuation, client_call_details, request):
        method = client_call_details.method
        start = time.time()
        response = continuation(client_call_details, request)
        elapsed = time.time() - start
        print(f"gRPC {method} completed in {elapsed:.3f}s")
        return response

# Use interceptor on the client
channel = grpc.intercept_channel(
    grpc.insecure_channel("localhost:50051"),
    LoggingInterceptor(),
)
```

Once this channel is used, every unary call emits a timing line before its result is returned to the caller:

```text
gRPC /userservice.UserService/CreateUser completed in 0.004s
gRPC /userservice.UserService/GetUser completed in 0.001s
```

**What's happening:** The method name arrives fully qualified as `/<package>.<Service>/<Method>` -- the same path gRPC puts on the wire as an HTTP/2 `:path` header -- which is exactly the label you want when exporting these timings to Prometheus or a tracing backend. Because the interceptor wraps `continuation`, the cross-cutting concern (timing here, but equally auth tokens or retries) lives in one place instead of being copy-pasted into every stub call. Sub-millisecond latencies like `0.001s` are typical for local unary RPCs and reflect protobuf's compact binary encoding; the exact figures vary by machine and network.

**When to Choose gRPC**

gRPC is ideal for inter-service communication (especially in polyglot environments where services are written in different languages), performance-critical paths, streaming data, and scenarios where well-defined service contracts are important. REST remains better for public-facing APIs (browser compatibility), simpler tooling and debugging (you can test REST with curl), and when human-readable payloads matter.

> **Key Takeaway:** gRPC provides substantially better performance than REST for internal service-to-service communication. Protocol Buffers enforce strong contracts and generate client code in any language. Use gRPC internally and expose REST (or GraphQL) externally.

### WebSocket & Server-Sent Events

> [!NOTE]
> **Beginner's Mental Model — WebSockets:**
> Traditional HTTP is like sending letters: you send a letter, and the server sends one back, then the connection closes. If you want more updates, you must send another letter. A **WebSocket** is like opening a phone call: once you dial and the other side picks up (the handshake), the line stays open indefinitely. Both you and the server can talk at the same time whenever you have something to say, without the overhead of redialing.

**WebSocket**

WebSocket provides full-duplex, persistent communication over a single TCP connection. The connection starts as an HTTP request that is "upgraded" to the WebSocket protocol. Once established, both the client and server can send messages at any time without the overhead of establishing new connections. This makes WebSocket ideal for real-time applications: chat, gaming, live collaboration, and trading platforms.

Here is a WebSocket server and client implemented with FastAPI:

```python
# websocket_server.py -- FastAPI WebSocket example
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

class ConnectionManager:
    """Manages active WebSocket connections for a chat room."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from this client
            data = await websocket.receive_text()

            # Broadcast to all connected clients
            await manager.broadcast(f"Room {room_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"A user left room {room_id}")
```

JavaScript client connecting to the WebSocket:

```javascript
// browser_client.js
const ws = new WebSocket("ws://localhost:8000/ws/chat/general");

ws.onopen = () => {
    console.log("Connected");
    ws.send("Hello, everyone!");
};

ws.onmessage = (event) => {
    console.log("Received:", event.data);
};

ws.onclose = (event) => {
    console.log("Disconnected, reconnecting...");
    // Implement exponential backoff reconnection
    setTimeout(() => { /* reconnect logic */ }, 1000);
};
```

**Server-Sent Events (SSE)**

SSE is a simpler alternative to WebSocket when you only need server-to-client communication. It is built on standard HTTP, which means it works through proxies and load balancers without special configuration, and the browser's `EventSource` API automatically handles reconnection. SSE is perfect for live feeds, notifications, progress updates, and streaming LLM responses.

```python
# sse_server.py -- FastAPI SSE example
import asyncio, json, time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

async def event_generator(request: Request):
    """
    Generator that yields SSE-formatted events.
    SSE format: "data: <payload>\n\n"
    Optional: "event: <type>\n" and "id: <id>\n" before the data line.
    """
    counter = 0
    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            break

        counter += 1
        event_data = {
            "counter": counter,
            "timestamp": time.time(),
            "message": f"Event number {counter}",
        }

        # SSE format: each event ends with two newlines
        yield f"event: update\nid: {counter}\ndata: {json.dumps(event_data)}\n\n"

        await asyncio.sleep(1)  # Send an event every second

@app.get("/events")
async def sse_endpoint(request: Request):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

Testing with curl:

```bash
curl -N http://localhost:8000/events

# Output (streaming):
# event: update
# id: 1
# data: {"counter": 1, "timestamp": 1711324800.0, "message": "Event number 1"}
#
# event: update
# id: 2
# data: {"counter": 2, "timestamp": 1711324801.0, "message": "Event number 2"}
```

A practical example -- streaming LLM responses via SSE:

```python
# llm_streaming.py -- Stream LLM responses to the client
import asyncio, json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

async def stream_llm_response(prompt: str, request: Request):
    """Simulates streaming tokens from an LLM."""
    tokens = f"The answer to '{prompt}' is that you need to consider ".split()

    for token in tokens:
        if await request.is_disconnected():
            break
        yield f"data: {json.dumps({'token': token})}\n\n"
        await asyncio.sleep(0.1)  # Simulate token generation delay

    yield f"data: {json.dumps({'token': '[DONE]'})}\n\n"

@app.get("/api/v1/chat/stream")
async def chat_stream(prompt: str, request: Request):
    return StreamingResponse(
        stream_llm_response(prompt, request),
        media_type="text/event-stream",
    )
```

JavaScript client consuming the SSE stream:

```javascript
// SSE client with automatic reconnection
const eventSource = new EventSource("/events");

eventSource.addEventListener("update", (event) => {
    const data = JSON.parse(event.data);
    console.log("Update:", data);
});

eventSource.onerror = (error) => {
    console.error("SSE error, browser will auto-reconnect:", error);
};
```

**WebSocket Scaling**

A single server can handle tens of thousands of WebSocket connections, but when you have multiple server instances behind a load balancer, you face a problem: a message sent to server A needs to reach clients connected to server B. There are two main solutions:

1. **Sticky sessions** -- The load balancer routes all requests from the same client to the same server. Simple, but limits horizontal scaling and creates uneven load distribution.

2. **External pub/sub** -- All servers subscribe to a shared message bus (typically Redis Pub/Sub or Kafka). When a message arrives on any server, it is published to the bus, and all servers forward it to their connected clients.

```python
# websocket_with_redis.py -- Scaling WebSockets with Redis Pub/Sub
import asyncio, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

app = FastAPI()
redis_client = redis.Redis()

async def redis_listener(websocket: WebSocket, channel: str):
    """Subscribe to Redis and forward messages to WebSocket."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())
    except Exception:
        await pubsub.unsubscribe(channel)

@app.websocket("/ws/chat/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    channel = f"chat:{room_id}"

    # Start listener task
    listener_task = asyncio.create_task(
        redis_listener(websocket, channel)
    )

    try:
        while True:
            data = await websocket.receive_text()
            # Publish to Redis so ALL servers see it
            await redis_client.publish(channel, data)
    except WebSocketDisconnect:
        listener_task.cancel()
```

Additional scaling considerations: impose connection limits per server, implement heartbeats (ping/pong frames) to detect dead connections, and use graceful reconnection with exponential backoff on the client side.

**When to Use Each**

| Technology   | Direction       | Best For                                       |
|--------------|----------------|-------------------------------------------------|
| SSE          | Server to client | Dashboards, feeds, notifications, LLM streaming |
| WebSocket    | Bidirectional   | Chat, gaming, collaborative editing              |
| HTTP Polling | Client to server | Infrequent updates, very low concurrency         |

> **Key Takeaway:** Use SSE for one-way server-to-client streaming -- it is simpler, works with standard HTTP infrastructure, and reconnects automatically. Reserve WebSocket for truly bidirectional use cases. For multi-server deployments, you will need an external pub/sub system like Redis to bridge connections across instances.

### Message Queues & Async APIs

> [!NOTE]
> **Beginner's Mental Model — Message Queues:**
> Think of a message queue as a post office. Instead of a customer (the client) waiting in line at the counter until a clerk (the worker) finishes a complex, 10-minute task, the customer drops their request in a mailbox (the message queue) and leaves. The mail clerks can retrieve requests from the box and process them one by one at their own pace. If a rush of requests arrives, they don't crash the system; they simply queue up in the mailbox until the clerks can get to them.

**RabbitMQ**

RabbitMQ implements the AMQP (Advanced Message Queuing Protocol) and provides a flexible routing model based on exchanges and queues. A producer publishes a message to an exchange, which then routes it to one or more queues based on bindings and routing rules. Consumers pull messages from queues.

The four exchange types serve different routing patterns:

- **Direct exchange** -- Routes messages to queues whose binding key exactly matches the routing key. Used for point-to-point messaging.
- **Topic exchange** -- Routes based on wildcard matching of routing keys (e.g., `order.created`, `order.*`). Used for category-based routing.
- **Fanout exchange** -- Routes to all bound queues regardless of routing key. Used for broadcast scenarios.
- **Headers exchange** -- Routes based on message header attributes rather than routing keys.

Dead letter exchanges (DLX) catch messages that cannot be processed -- rejected messages, expired messages, or messages from a full queue. This allows you to inspect and retry failed messages rather than losing them. Manual acknowledgements ensure a message is not removed from the queue until the consumer confirms successful processing. Prefetch count controls how many unacknowledged messages a consumer can hold, providing flow control.

```python
# rabbitmq_producer.py
import pika, json

connection = pika.BlockingConnection(
    pika.ConnectionParameters("localhost")
)
channel = connection.channel()

# Declare the dead-letter exchange and the failed-messages queue, and bind the
# DLQ to the DLX so dead-lettered messages actually land somewhere.
channel.exchange_declare(exchange="orders_dlx", exchange_type="direct", durable=True)
channel.queue_declare(queue="order_processing_failed", durable=True)
channel.queue_bind(
    exchange="orders_dlx",
    queue="order_processing_failed",
    routing_key="order.created",  # dead-lettered msgs keep their original routing key
)

# Declare the main exchange and processing queue. The x-dead-letter-exchange
# argument belongs on the SOURCE queue, so messages nacked or expired here are
# routed to orders_dlx (and on to order_processing_failed).
channel.exchange_declare(exchange="orders", exchange_type="topic", durable=True)
channel.queue_declare(
    queue="order_processing",
    durable=True,
    arguments={"x-dead-letter-exchange": "orders_dlx"},
)
channel.queue_bind(
    exchange="orders",
    queue="order_processing",
    routing_key="order.created",
)

# Publish a message
message = {"order_id": 123, "total": 99.99, "items": ["widget"]}
channel.basic_publish(
    exchange="orders",
    routing_key="order.created",
    body=json.dumps(message),
    properties=pika.BasicProperties(
        delivery_mode=2,         # persistent message
        content_type="application/json",
    ),
)
print("Published order event")
connection.close()
```

```python
# rabbitmq_consumer.py
import pika, json, traceback

connection = pika.BlockingConnection(
    pika.ConnectionParameters("localhost")
)
channel = connection.channel()

# Prefetch: only deliver 1 message at a time to this consumer
channel.basic_qos(prefetch_count=1)

def process_order(ch, method, properties, body):
    try:
        order = json.loads(body)
        print(f"Processing order {order['order_id']}")

        # ... actual processing logic ...

        # Acknowledge successful processing
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        traceback.print_exc()
        # Reject and send to dead letter queue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

channel.basic_consume(
    queue="order_processing",
    on_message_callback=process_order,
    auto_ack=False,  # Manual acknowledgement for reliability
)

print("Waiting for orders...")
channel.start_consuming()
```

With the producer publishing an `order.created` event, the consumer blocks until a message arrives, then prints:

```text
Waiting for orders...
Processing order 123
```

**What's happening:** `start_consuming()` blocks the thread and runs the callback once per delivered message -- there is no output until a message actually lands on the bound queue, which trips up people who expect the consumer to "do something" immediately. Because `auto_ack=False`, the message stays on the queue (invisible to other consumers but not deleted) until `basic_ack` fires; if the worker crashes mid-processing, RabbitMQ redelivers it, giving at-least-once delivery. A raised exception instead hits `basic_nack(requeue=False)`, which routes the poison message to the dead-letter queue rather than looping it forever -- the difference between a graceful retry pipeline and an infinite crash loop in production.

Apache Kafka is a distributed log, fundamentally different from a traditional message queue. Instead of messages being consumed and removed, they are appended to a topic's partitions and retained for a configurable period (or indefinitely). This means consumers can replay events from any point in time.

Topics are divided into partitions for parallel processing. Consumer groups coordinate so that each partition is consumed by exactly one consumer in the group, enabling horizontal scaling. Idempotent producers combined with transactions enable exactly-once semantics.

Kafka offers higher throughput than RabbitMQ (millions of messages per second) but has higher operational complexity. It is the right choice for event sourcing, log aggregation, stream processing, and any scenario where event replay is valuable.

```python
# kafka_producer.py
from confluent_kafka import Producer
import json

producer = Producer({"bootstrap.servers": "localhost:9092"})

def delivery_callback(err, msg):
    if err:
        print(f"Delivery failed: {err}")
    else:
        print(f"Delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")

# Produce events
for i in range(10):
    event = {"order_id": i, "amount": 100 + i, "event": "order_created"}
    producer.produce(
        topic="orders",
        key=str(i).encode(),        # Key determines partition
        value=json.dumps(event).encode(),
        callback=delivery_callback,
    )

producer.flush()  # Wait for all messages to be delivered
```

After `flush()` forces the delivery callbacks to fire, you see one acknowledgement per message (assuming a 3-partition topic):

```text
Delivered to orders [2] @ 14
Delivered to orders [0] @ 51
Delivered to orders [1] @ 9
Delivered to orders [2] @ 15
...
```

**How to read this output:** Each line is a *broker acknowledgement*, not just a local enqueue -- `produce()` only buffers the message; the callback runs later when the broker confirms the write, which is why `flush()` (or the callbacks may never run). The number in brackets is the partition: Kafka hashes the message `key` to pick it, so the same key always lands on the same partition, guaranteeing per-key ordering -- this is how you keep all events for one `order_id` in order while still parallelizing across partitions. The `@ N` is the offset, the message's permanent position in that partition's log; consumers track offsets to know what they have read and to replay from any point. Partition assignment and offsets depend on your topic's partition count and existing data, so exact values will differ.

```python
# kafka_consumer.py
from confluent_kafka import Consumer
import json

consumer = Consumer({
    "bootstrap.servers": "localhost:9092",
    "group.id": "order-processor",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,  # Manual commit for reliability
})

consumer.subscribe(["orders"])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Error: {msg.error()}")
            continue

        event = json.loads(msg.value())
        print(f"Processing: {event}")

        # Process the event...

        # Commit offset after successful processing
        consumer.commit(msg)
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
```

**Celery**

Celery is Python's standard distributed task queue. It uses a broker (Redis or RabbitMQ) to distribute tasks to worker processes and a result backend to store return values. Celery excels at offloading long-running or resource-intensive work from the request-response cycle.

```python
# celery_app.py -- Celery configuration
from celery import Celery

app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,       # Acknowledge after task completes (reliability)
    worker_prefetch_multiplier=1,
)
```

```python
# tasks.py -- Task definitions
from celery_app import app
from celery import chain, group, chord
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,        # 60 seconds between retries
    rate_limit="10/m",             # Max 10 executions per minute
)
def send_email(self, to: str, subject: str, body: str):
    """Send an email with automatic retry on failure."""
    try:
        logger.info(f"Sending email to {to}")
        # ... SMTP logic ...
        return {"status": "sent", "to": to}
    except ConnectionError as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)

@app.task
def generate_report(report_type: str, user_id: int):
    """Long-running report generation."""
    logger.info(f"Generating {report_type} report for user {user_id}")
    # ... heavy computation ...
    return {"report_url": f"/reports/{report_type}_{user_id}.pdf"}

@app.task
def resize_image(image_path: str, sizes: list):
    """Resize an uploaded image to multiple sizes."""
    results = []
    for size in sizes:
        # ... image processing ...
        results.append(f"{image_path}_{size}.jpg")
    return results

@app.task
def notify_completion(results):
    """Callback after a group of tasks finishes."""
    logger.info(f"All tasks done. Results: {results}")
```

```python
# Using Celery in a FastAPI endpoint
from fastapi import FastAPI
from tasks import send_email, generate_report, resize_image, notify_completion
from celery import chain, group, chord

app = FastAPI()

@app.post("/api/v1/users/{user_id}/welcome")
async def send_welcome(user_id: int):
    # Fire-and-forget: send email asynchronously
    task = send_email.delay(
        to=f"user{user_id}@example.com",
        subject="Welcome!",
        body="Thanks for signing up.",
    )
    return {"task_id": task.id, "status": "queued"}

@app.get("/api/v1/tasks/{task_id}")
async def check_task(task_id: str):
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,       # PENDING, STARTED, SUCCESS, FAILURE
        "result": result.result if result.ready() else None,
    }

@app.post("/api/v1/complex-workflow")
async def complex_workflow():
    # Chain: tasks run sequentially, output of one feeds into the next
    workflow_chain = chain(
        generate_report.s("monthly", 1),
        # .si() = immutable signature: ignore the previous task's return value, so
        # generate_report's dict is NOT injected as send_email's first argument.
        send_email.si("admin@example.com", "Report Ready", "Your report is ready."),
    )

    # Group: tasks run in parallel
    workflow_group = group(
        resize_image.s("photo.jpg", ["thumbnail"]),
        resize_image.s("photo.jpg", ["medium"]),
        resize_image.s("photo.jpg", ["large"]),
    )

    # Chord: run a group, then call a callback with all results
    workflow_chord = chord(
        [
            generate_report.s("daily", 1),
            generate_report.s("daily", 2),
            generate_report.s("daily", 3),
        ],
        notify_completion.s(),
    )

    result = workflow_chord.apply_async()
    return {"task_group_id": result.id}
```

Run workers and monitoring:

```bash
# Start a Celery worker
celery -A celery_app worker --loglevel=info --concurrency=4

# Start the Flower monitoring dashboard
celery -A celery_app flower --port=5555
# Visit http://localhost:5555 for real-time task monitoring
```

Starting the worker prints a banner confirming the broker, the concurrency level, and the registered tasks:

```console
$ celery -A celery_app worker --loglevel=info --concurrency=4
 -------------- celery@host v5.x.x
--- ***** -----
-- ******* ---- Linux
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> broker:     redis://localhost:6379/0
- ** ---------- .> results:    redis://localhost:6379/1
- ** ---------- .> concurrency: 4 (prefork)
- *** --- * --- .> task events: OFF
-- ******* ----
--- ***** ----- [tasks]
 -------------- . tasks.generate_report
                . tasks.notify_completion
                . tasks.resize_image
                . tasks.send_email

[INFO] Connected to redis://localhost:6379/0
[INFO] celery@host ready.
```

**How to read this output:** The `[tasks]` block is the fast sanity check -- if a task you expected is missing here, the worker never imported it and `.delay()` calls will sit in the queue forever or raise `NotRegistered`; this is the first thing to check when "my Celery task isn't running." `concurrency: 4 (prefork)` means four OS worker processes, so CPU-bound tasks run truly in parallel (unlike threads under the GIL). `celery@host ready.` is the signal that the worker has connected to the broker and is consuming -- until that line appears, queued tasks are buffering in Redis, not executing.

**Webhooks**

Webhooks are HTTP callbacks -- when an event occurs in system A, it sends an HTTP POST to a URL registered by system B. Design considerations for a robust webhook system:

```python
# webhook_sender.py -- Sending webhooks with reliability
import hashlib, hmac, json, time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

WEBHOOK_SECRET = "whsec_your_secret_key"

def sign_payload(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=300),
)
def deliver_webhook(url: str, event: dict):
    """Deliver webhook with HMAC signature and retry with exponential backoff."""
    payload = json.dumps(event)
    signature = sign_payload(payload, WEBHOOK_SECRET)

    response = httpx.post(
        url,
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-ID": event.get("id", ""),
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response

# Receiver side -- verifying the webhook
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

@app.post("/webhooks/orders")
async def receive_webhook(request: Request):
    body = await request.body()
    signature_header = request.headers.get("X-Webhook-Signature", "")

    # Parse signature header
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp = parts.get("t", "")
    received_sig = parts.get("v1", "")

    # Verify signature
    expected_payload = f"{timestamp}.{body.decode()}"
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(), expected_payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Check timestamp to prevent replay attacks (reject if older than 5 min)
    if abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Timestamp too old")

    event = json.loads(body)
    print(f"Received event: {event}")

    # Process idempotently -- use X-Webhook-ID to deduplicate
    return {"status": "received"}
```

**AsyncAPI**

AsyncAPI is the OpenAPI equivalent for asynchronous APIs. It provides a specification format for documenting message channels, schemas, and operations for event-driven architectures. You can define your Kafka topics, RabbitMQ exchanges, and WebSocket channels in a machine-readable format and auto-generate documentation and code from it.

> **Key Takeaway:** Choose your async pattern based on the use case. Celery is the go-to for Python background tasks with retry and workflow support. RabbitMQ is best for complex routing and traditional work queues. Kafka is best for high-throughput event streaming and event replay. Always sign webhooks with HMAC and implement retry with exponential backoff.

*Last reviewed: 2026-06-08*
