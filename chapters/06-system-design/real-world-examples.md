[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 6.3 Real-World System Design Examples

### URL Shortener

A URL shortener takes a long URL (like `https://example.com/products/electronics/laptops?sort=price&page=3`) and produces a short alias (like `https://short.ly/a3Xk9p`) that redirects to the original. This is a classic system design problem because it touches on key generation, storage, caching, and analytics.

```
ARCHITECTURE:

 +----------+       +------------------+       +------------------+
 |  Client  |------>|  Load Balancer   |------>|  API Servers     |
 | (Browser)|       |  (nginx / ALB)   |       |  (Stateless)     |
 +----------+       +------------------+       +--+----------+----+
                                                   |          |
                          +------------------------+          |
                          |                                   |
                    +-----v------+                     +------v------+
                    |   Redis    |                     |  PostgreSQL |
                    |   Cache    |                     |  / DynamoDB |
                    | (hot URLs) |                     | (all URLs)  |
                    +------------+                     +------+------+
                                                              |
                                                       +------v------+
                                                       |    Kafka    |
                                                       | (click      |
                                                       |  events)    |
                                                       +------+------+
                                                              |
                                                       +------v------+
                                                       |  Analytics  |
                                                       |  Service    |
                                                       | (ClickHouse)|
                                                       +-------------+

REDIRECT FLOW (read path -- hot path):
  Client --GET /a3Xk9p--> LB --> API Server
                                     |
                                     +--> Check Redis cache
                                     |      HIT: return 301 redirect
                                     |      MISS: query database
                                     |              |
                                     |              +--> Store in Redis
                                     |              +--> Return 301 redirect
                                     |
                                     +--> Publish click event to Kafka (async)

CREATE FLOW (write path):
  Client --POST /shorten {url}--> LB --> API Server
                                             |
                                             +--> Validate URL
                                             +--> Generate short code
                                             +--> Store in DB
                                             +--> Store in Redis cache
                                             +--> Return short URL
```

**Short Code Generation** is the core algorithmic challenge. Several approaches exist:

- **Counter-Based (Auto-Increment ID + Base62 Encoding)**: Use a database auto-increment ID (or a distributed counter like Redis INCR or a Snowflake ID generator) and encode it in Base62 (a-z, A-Z, 0-9). ID 1000000 encodes to "4c92" (4 characters). Pros: no collisions, compact. Cons: predictable (users can enumerate URLs), requires a centralized counter.
- **Hash-Based**: Compute MD5 or SHA-256 of the long URL and take the first 6-7 characters. Pros: deterministic (same URL always produces the same short code), no centralized state. Cons: collision risk (must check for collisions and retry), longer codes needed to reduce collision probability.
- **Random ID (nanoid/UUID)**: Generate a random string of 6-7 characters. Pros: unpredictable, no centralized counter. Cons: must check for collisions, not deterministic.

With 6 characters of Base62 encoding, you get 62^6 = 56.8 billion unique codes -- more than enough for most use cases. 7 characters gives 3.5 trillion.

**Storage** is straightforward. This is an overwhelmingly read-heavy workload: for every URL created, it will be clicked hundreds or thousands of times. A reasonable estimate is a 100:1 read-to-write ratio. The primary data model is simple: `short_code -> (long_url, created_at, expires_at, user_id)`. A key-value store like DynamoDB or Cassandra is a natural fit, though PostgreSQL works fine at moderate scale.

**Caching** follows the 80/20 rule (Pareto principle): 20% of URLs generate 80% of traffic. Cache the hottest URLs in Redis using cache-aside with a reasonable TTL (e.g., 24 hours). For a service handling 100 million clicks per day, if the top 20% of URLs fit in cache, you serve 80 million clicks from Redis without touching the database.

**Analytics** should be decoupled from the redirect path (the hot path). Every click publishes an event to Kafka containing the short code, timestamp, IP address, User-Agent, and Referer header. A separate analytics pipeline consumes these events, extracts geo-location from the IP, parses the device type from the User-Agent, and stores aggregated data in a time-series database (ClickHouse, TimescaleDB) or a data warehouse.

**Additional Features**: Custom aliases (let users choose their own short code), link expiration (TTL on the short code), rate limiting (prevent abuse -- limit URL creation per user/IP), and abuse prevention (check submitted URLs against known spam/malware databases like Google Safe Browsing).

> **Key Takeaway:** A URL shortener is deceptively simple but exercises every read-heavy system design muscle: pick a short-code scheme that matches your constraints (Base62-on-counter for compactness, hash for determinism, random for unpredictability), accept the 100:1 read/write ratio by caching the hot 20% in Redis, and push analytics off the redirect path onto an async event stream so a click never waits on a write.

### Distributed Rate Limiter

Rate limiting controls how many requests a client can make within a time window. It protects services from abuse, ensures fair usage, and prevents cascading failures from traffic spikes.

```
ARCHITECTURE:

                      +-------------------+
                      |   Client Request  |
                      +--------+----------+
                               |
                      +--------v----------+
                      |   API Gateway /   |
                      |   Load Balancer   |
                      +--------+----------+
                               |
               +---------------+---------------+
               |                               |
      +--------v----------+          +--------v----------+
      |  App Server 1     |          |  App Server 2     |
      |  +-------------+  |          |  +-------------+  |
      |  | Local Rate   |  |          |  | Local Rate   |  |
      |  | Limiter (L1) |  |          |  | Limiter (L1) |  |
      |  +------+------+  |          |  +------+------+  |
      +--------+----------+          +--------+----------+
               |                               |
               +---------------+---------------+
                               |
                      +--------v----------+
                      |     Redis         |
                      |  (Shared State)   |
                      |                   |
                      |  Lua scripts for  |
                      |  atomic ops       |
                      +-------------------+

FLOW:
  1. Request arrives at App Server
  2. Local rate limiter checks in-memory counter (fast, approximate)
     - If clearly over limit: reject immediately (no Redis call)
     - If clearly under limit: allow (optimistic)
     - If near limit: check Redis (accurate)
  3. Redis Lua script atomically: read count -> increment -> check limit
  4. Return allow/deny decision
```

Here are Python/Redis implementations of the three major rate limiting algorithms:

```python
import time
import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


# =============================================================================
# Algorithm 1: Token Bucket
# =============================================================================
# The bucket holds up to `capacity` tokens. Tokens are added at `refill_rate`
# per second. Each request consumes one token. If the bucket is empty, the
# request is denied. This algorithm allows bursts up to the bucket capacity.

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])   -- tokens per second
local now = tonumber(ARGV[3])

-- Get current bucket state
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- Initialize if first request
if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Calculate tokens to add since last refill
local elapsed = now - last_refill
local new_tokens = elapsed * refill_rate
tokens = math.min(capacity, tokens + new_tokens)

-- Try to consume a token
local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

-- Save state
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 1)

return {allowed, tokens}
"""


def token_bucket_check(user_id: str, capacity: int = 10, refill_rate: float = 1.0) -> bool:
    """
    Check if a request is allowed under the token bucket algorithm.

    Args:
        user_id: Identifier for the rate limit subject (user, IP, API key).
        capacity: Maximum burst size (bucket capacity).
        refill_rate: Tokens added per second.

    Returns:
        True if the request is allowed, False if rate-limited.
    """
    key = f"ratelimit:token_bucket:{user_id}"
    now = time.time()

    result = redis_client.eval(TOKEN_BUCKET_SCRIPT, 1, key, capacity, refill_rate, now)
    allowed, remaining_tokens = result

    if not allowed:
        print(f"RATE LIMITED: user={user_id}, remaining_tokens={remaining_tokens:.1f}")
    return bool(allowed)


# =============================================================================
# Algorithm 2: Sliding Window Log
# =============================================================================
# Uses a Redis sorted set where each request is stored with its timestamp
# as the score. To check the rate, we count entries within the window.
# Most accurate but uses the most memory (stores every request timestamp).

SLIDING_WINDOW_LOG_SCRIPT = """
local key = KEYS[1]
local window_size = tonumber(ARGV[1])   -- window in seconds
local max_requests = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local request_id = ARGV[4]

-- Remove entries outside the window
local window_start = now - window_size
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests in window
local current_count = redis.call('ZCARD', key)

if current_count < max_requests then
    -- Add this request
    redis.call('ZADD', key, now, request_id)
    redis.call('EXPIRE', key, window_size + 1)
    return {1, max_requests - current_count - 1}
else
    return {0, 0}
end
"""


def sliding_window_check(
    user_id: str,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> bool:
    """
    Check if a request is allowed under the sliding window log algorithm.

    Args:
        user_id: Identifier for the rate limit subject.
        max_requests: Maximum requests allowed in the window.
        window_seconds: Size of the sliding window in seconds.

    Returns:
        True if the request is allowed, False if rate-limited.
    """
    import uuid

    key = f"ratelimit:sliding_window:{user_id}"
    now = time.time()
    request_id = f"{now}:{uuid.uuid4().hex[:8]}"

    result = redis_client.eval(
        SLIDING_WINDOW_LOG_SCRIPT, 1, key, window_seconds, max_requests, now, request_id
    )
    allowed, remaining = result
    return bool(allowed)


# =============================================================================
# Algorithm 3: Fixed Window Counter
# =============================================================================
# The simplest algorithm. Count requests per fixed time window (e.g., per minute).
# Uses Redis INCR + EXPIRE. Very memory-efficient (one counter per user per window).
# Weakness: a burst at the boundary of two windows can allow 2x the limit.

def fixed_window_check(
    user_id: str,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> bool:
    """
    Check if a request is allowed under the fixed window counter algorithm.

    Args:
        user_id: Identifier for the rate limit subject.
        max_requests: Maximum requests allowed per window.
        window_seconds: Size of each fixed window in seconds.

    Returns:
        True if the request is allowed, False if rate-limited.
    """
    # Window key includes the current time window identifier
    window_id = int(time.time()) // window_seconds
    key = f"ratelimit:fixed_window:{user_id}:{window_id}"

    # INCR is atomic -- returns the new count after increment
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds + 1)  # +1 to ensure cleanup
    results = pipe.execute()

    current_count = results[0]

    if current_count > max_requests:
        print(f"RATE LIMITED: user={user_id}, count={current_count}/{max_requests}")
        return False
    return True


# =============================================================================
# Usage Example: Rate Limiting Middleware
# =============================================================================

def rate_limit_middleware(request):
    """Example middleware that applies rate limiting to an API request."""
    # Identify the client (API key, user ID, or IP address)
    client_id = request.headers.get("X-API-Key") or request.remote_addr

    # Apply different limits based on endpoint
    if request.path.startswith("/api/search"):
        allowed = token_bucket_check(client_id, capacity=5, refill_rate=1.0)
    elif request.path.startswith("/api/create"):
        allowed = sliding_window_check(client_id, max_requests=10, window_seconds=60)
    else:
        allowed = fixed_window_check(client_id, max_requests=100, window_seconds=60)

    if not allowed:
        return {
            "status": 429,
            "headers": {"Retry-After": "60"},
            "body": {"error": "Too Many Requests"},
        }

    return None  # Allow the request to proceed
```

To see the behavior, imagine driving `token_bucket_check` in a tight loop against a fresh bucket (`capacity=5, refill_rate=1.0`) and firing 8 requests faster than one per second:

```python
for i in range(8):
    allowed = token_bucket_check("user42", capacity=5, refill_rate=1.0)
    print(f"request {i}: allowed={allowed}")
```

The output looks something like this (the exact `remaining_tokens` depends on how much wall-clock time elapsed between calls, since tokens refill continuously):

```text
request 0: allowed=True
request 1: allowed=True
request 2: allowed=True
request 3: allowed=True
request 4: allowed=True
RATE LIMITED: user=user42, remaining_tokens=0.0
request 5: allowed=False
RATE LIMITED: user=user42, remaining_tokens=0.0
request 6: allowed=False
RATE LIMITED: user=user42, remaining_tokens=0.0
request 7: allowed=False
```

**How to read this output:** The first five requests drain the bucket's initial `capacity=5` tokens and are allowed. The sixth request finds the bucket empty (`remaining_tokens=0.0`) and is rejected. This is the defining property of token bucket: it permits a *burst* up to `capacity`, then throttles down to the steady `refill_rate`. If you paused for one second after the burst, exactly one token would refill and exactly one more request would succeed. In an interview, this is the answer to "how do you allow occasional bursts but enforce a long-run average?" -- the bucket size sets the burst, the refill rate sets the average.

> **Common pitfall:** The Redis Lua script runs atomically, but `now = time.time()` is computed on the *application* server before the call. If your app servers' clocks drift, two servers can compute different refill amounts for the same bucket, producing slightly inconsistent decisions. Pass a single authoritative timestamp (or use Redis's own `TIME` command inside the script) when clock skew matters.

**Multi-Tier Rate Limiting** combines a fast local (in-memory) rate limiter on each application server with a globally accurate Redis-based limiter. The local limiter handles the common case (clearly under or over the limit) without any network call. Only borderline cases consult Redis. This reduces Redis load significantly under high traffic.

> **Key Takeaway:** The three algorithms trade memory for accuracy: fixed window is cheapest (one counter) but allows 2x bursts at window boundaries; sliding window log is exact but stores every timestamp; token bucket sits in between and is the usual default because it cleanly separates burst size from sustained rate. Whichever you pick, make the increment-and-check atomic (a Redis Lua script or pipeline) so concurrent requests across servers cannot both slip through on the same remaining slot.

### Chat System

A real-time chat system requires persistent bidirectional connections, reliable message delivery, online presence tracking, and efficient storage for potentially billions of messages.

```
ARCHITECTURE:

 +---------+    WebSocket    +------------------+
 | Client  |<-------------->| WebSocket Server |
 | (Web /  |                | (Connection Mgr) |
 | Mobile) |                +--------+---------+
 +---------+                         |
                                     |  Internal gRPC
              +----------------------+----------------------+
              |                      |                      |
     +--------v-------+    +--------v--------+    +--------v--------+
     | Message Service |    | Presence Service|    | Media Service   |
     | (validation,    |    | (online status, |    | (file upload,   |
     |  routing,       |    |  last seen,     |    |  thumbnails,    |
     |  persistence)   |    |  typing)        |    |  CDN URLs)      |
     +--------+--------+    +--------+--------+    +--------+--------+
              |                      |                      |
     +--------v--------+    +-------v--------+     +-------v--------+
     |     Kafka        |    |    Redis       |     |    S3 / CDN    |
     | (message bus)    |    | (presence hash,|     | (images, video,|
     |                  |    |  user->server) |     |  files)        |
     +---------+--------+    +----------------+     +----------------+
               |
     +---------v--------+
     |   PostgreSQL /    |
     |   Cassandra       |
     | (message storage, |
     |  partitioned by   |
     |  conversation_id  |
     |  + timestamp)     |
     +-------------------+

MESSAGE DELIVERY FLOW:

  Alice (Server 1)                                      Bob (Server 3)
       |                                                     |
  1.   |---> WebSocket msg: {to: "bob", body: "hello"} -->|  |
       |                                                  |  |
  2.   |    Message Service validates and persists        |  |
       |    to database + publishes to Kafka              |  |
       |                                                  |  |
  3.   |    Kafka consumer reads message                  |  |
       |    Looks up Bob's server in Redis:               |  |
       |      HGET user_connections bob --> "server_3"    |  |
       |                                                  |  |
  4.   |    Forwards message to Server 3 via internal gRPC|  |
       |                                                     |
  5.   |                   Server 3 pushes via WebSocket --->|
       |                                                     |
  6.   |                   Bob's client sends read receipt -->|
       |                                                     |

PRESENCE TRACKING:

  Each connected client sends a heartbeat every 30 seconds.
  The WebSocket server writes to Redis:

    SET presence:{user_id} "online" EX 45
    HSET user_connections {user_id} {server_id}

  When the TTL expires (no heartbeat for 45s), the user is considered offline.
  Presence changes are published via Redis Pub/Sub to interested subscribers.
```

**Connection Management**: WebSocket is the primary protocol for real-time chat because it provides full-duplex communication over a single long-lived TCP connection. Server-Sent Events (SSE) can serve as a fallback for environments where WebSocket is not available (some corporate proxies block it). The connection manager on each WebSocket server maintains a mapping of `user_id -> WebSocket connection`. A global mapping of `user_id -> server_id` is stored in a Redis hash so that any server can look up which server a user is connected to and forward messages accordingly.

**Message Storage**: Messages are stored in a database partitioned by `conversation_id` and sorted by timestamp. This makes fetching the message history for a conversation (the most common query) efficient. Recent messages (the last N per conversation) are cached in Redis for fast loading when a user opens a chat. Media attachments (images, videos, files) are uploaded to object storage (S3) and only a reference URL is stored in the message record.

**Features**:
- **Online Presence**: Each client sends a periodic heartbeat (every 30 seconds) via the WebSocket connection. The server writes a Redis key with a TTL slightly longer than the heartbeat interval (e.g., 45 seconds). If the heartbeat stops, the key expires and the user is considered offline.
- **Read Receipts**: Store a `last_read_message_id` per user per conversation. When a user reads messages, the client sends an update. The unread count for a conversation is computed as the number of messages after `last_read_message_id`.
- **Typing Indicators**: Ephemeral events that are broadcast to other participants in a conversation but never persisted to the database. They flow through the WebSocket/message routing layer just like messages but are discarded after delivery.

**Scaling**: Conversations are partitioned across WebSocket servers. When Alice on Server 1 sends a message to Bob on Server 3, the message is routed through the internal message bus (Kafka or gRPC between servers). The Redis `user_connections` hash enables this routing. Adding more WebSocket servers is straightforward because the routing layer handles cross-server delivery.

> **Key Takeaway:** Real-time chat is a routing problem on top of a storage problem. The hard part is that connections are stateful and pinned to one server, so you keep a `user_id -> server_id` map in Redis and forward across servers via an internal bus -- this decoupling is what lets you scale WebSocket servers horizontally. Persist durable messages, cache the recent tail per conversation, and let ephemeral signals (typing, presence) live only in Redis with a TTL so they self-clean and never bloat your database.

### Notification System

A notification system delivers messages to users across multiple channels (email, push notifications, SMS, in-app, webhooks) with user-controlled preferences, deduplication, and reliability guarantees.

```
ARCHITECTURE:

  +------------------+    +------------------+    +------------------+
  | Order Service    |    | Auth Service     |    | Social Service   |
  | (order_placed,   |    | (password_reset, |    | (new_follower,   |
  |  order_shipped)  |    |  login_alert)    |    |  new_comment)    |
  +--------+---------+    +--------+---------+    +--------+---------+
           |                       |                       |
           +------------- Publish events to Kafka ---------+
                                   |
                          +--------v---------+
                          | Notification     |
                          | Service          |
                          | (event consumer) |
                          +--------+---------+
                                   |
                    +--------------+--------------+
                    |              |               |
           +--------v---+  +------v------+  +-----v-------+
           | User Prefs |  | Template    |  | Dedup       |
           | Service    |  | Engine      |  | Service     |
           | (opt-in/   |  | (render     |  | (idempotency|
           |  out, quiet|  |  per channel|  |  key check) |
           |  hours)    |  |  + locale)  |  |             |
           +--------+---+  +------+------+  +-----+-------+
                    |              |               |
                    +--------------+---------------+
                                   |
                    +--------------+--------------+
                    |              |               |
           +--------v---+  +------v------+  +-----v-------+
           | Priority    |  |             |  |             |
           | Queue       |  |             |  |             |
           | +--------+  |  |             |  |             |
           | |Urgent  |  |  |             |  |             |
           | +--------+  |  |             |  |             |
           | |Normal  |  |  |             |  |             |
           | +--------+  |  |             |  |             |
           | |Batch   |  |  |             |  |             |
           | +--------+  |  |             |  |             |
           +------+-------+  |             |  |             |
                  |           |             |  |             |
      +-----------+-----------+-------------+--+             |
      |           |           |             |                |
 +----v---+ +----v----+ +----v----+ +------v----+ +---------v--+
 | Email  | |  Push   | |  SMS   | | In-App    | | Webhook    |
 | Worker | | Worker  | | Worker | | Worker    | | Worker     |
 | (SES / | | (FCM /  | |(Twilio)| | (WS/SSE) | | (Slack /   |
 |SendGrid| |  APNS)  | |        | |           | |  Teams)    |
 +----+---+ +----+----+ +---+----+ +-----+-----+ +-----+-----+
      |          |           |            |              |
      +----------+-----------+------------+--------------+
                             |
                    +--------v---------+
                    | Delivery Status  |
                    | Tracker          |
                    | (sent, delivered,|
                    |  failed, bounced)|
                    +------------------+

NOTIFICATION FLOW (example: order shipped):

  1. Order Service publishes event:
     {type: "order_shipped", user_id: "u123", order_id: "o456", tracking: "..."}

  2. Notification Service consumes the event.

  3. Check deduplication: has this exact notification been sent before?
     Key: "notif:order_shipped:o456:u123" -- if exists, skip.

  4. Check user preferences:
     - User u123 wants email + push for shipping updates, NOT SMS.
     - User u123 has quiet hours 22:00-08:00 (delay if in range).

  5. Render templates per channel:
     - Email: HTML template with order details, tracking link.
     - Push: Short text "Your order #o456 has shipped! Track it here."

  6. Enqueue to priority queue (shipping = normal priority).

  7. Channel workers deliver:
     - Email worker calls SendGrid API.
     - Push worker calls FCM (Android) and APNS (iOS).

  8. Track delivery status. On failure, retry with backoff.
     After max retries, move to dead letter queue.
```

**Channels**: Each notification channel has different characteristics and delivery APIs:
- **Email** (Amazon SES, SendGrid, Mailgun): Supports rich HTML content, attachments, and analytics (open tracking, click tracking). High throughput but relatively high latency (seconds to minutes for delivery).
- **Push Notifications** (Firebase Cloud Messaging for Android, Apple Push Notification Service for iOS): Short messages with a title and body. Platform-specific payload formats. Token management (device tokens can change or become invalid).
- **SMS** (Twilio, AWS SNS): Expensive per message. Character limits. Use only for high-value notifications (2FA codes, payment confirmations).
- **In-App** (WebSocket or SSE): Real-time delivery while the user is active. No delivery guarantee if the user is offline (fall back to other channels or store for later display).
- **Webhooks** (Slack, Microsoft Teams, custom integrations): HTTP POST to a configured URL. Useful for system-to-system notifications.

**User Preferences** are critical for notification systems. Users should be able to:
- Opt in or out of each notification type per channel (e.g., "I want order updates via email but not SMS").
- Set quiet hours (e.g., "Do not disturb between 10 PM and 8 AM in my timezone").
- Set frequency caps (e.g., "No more than 5 push notifications per hour").
A preferences matrix is stored per user: `(user_id, notification_type, channel) -> enabled/disabled`.

**Reliability**: The system should provide at-least-once delivery. This means messages may be delivered more than once, so deduplication on the consumer side is important. Each notification is assigned an idempotency key (e.g., a hash of the event type, entity ID, and user ID). Before delivering, the system checks if this key has been seen before. Failed deliveries are retried with exponential backoff. After exhausting retries, messages are moved to a dead letter queue (DLQ) for investigation. The delivery status tracker records the state of each notification (queued, sent, delivered, failed, bounced) for debugging and auditing.

> **Key Takeaway**: When designing real-world systems, start with the requirements (functional and non-functional), estimate the scale (see the next section on back-of-envelope calculations), then design the architecture layer by layer. Separate read paths from write paths. Decouple components with message queues. Cache aggressively on the read path. Make every component horizontally scalable and every operation idempotent. Draw the architecture diagram first, then dive into the details of each component.
