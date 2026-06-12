[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 6.4 Back-of-Envelope Calculations

Back-of-envelope calculations (also called Fermi estimates) help you quickly determine the scale of a system and make informed architecture decisions before any benchmark exists. Every design in section 6.3 rested on a sizing judgment made early, with incomplete information: whether the data fits on one machine, whether a cache absorbs the read load, how many workers a queue needs. Those judgments cannot wait for a load test -- by the time you can benchmark, the architecture is already chosen. Estimation is how we make them defensible, and in a system design interview it demonstrates that you think about scale before diving into design.

After working through this section, you should be able to answer questions like: how many requests per second is 100 million per month, really? Does five years of data fit on a single database server, or does it force a partitioned store? How much memory does a cache need to absorb 80% of reads? How many WebSocket servers does 10 million daily users imply, and how many worker threads does a notification queue need at peak? None of these require precision -- they require the right order of magnitude, stated with explicit assumptions.

We proceed in two steps. First we establish the reference numbers worth memorizing -- latencies, throughputs, storage sizes, and time-scale conversions that anchor every estimate. Then we apply them in three full walkthroughs of increasing statefulness: a URL shortener (read-heavy, cache-dominated), a chat system (storage- and connection-dominated), and a notification system (throughput- and worker-dominated). Each walkthrough ends by naming the one number that actually drives the architecture.

## Reference Numbers to Memorize

Estimates are only as fast as your recall of the underlying constants, so we start by laying out the small table of numbers that every calculation in this section -- and most you will do in practice -- is built from. You do not need them to many digits; you need the right power of ten.

```
LATENCY NUMBERS:
  L1 cache reference .................. 0.5 ns
  L2 cache reference ..................   7 ns
  RAM reference .......................  100 ns
  SSD random read .................... 150 us    (150,000 ns)
  HDD random read ....................  10 ms    (10,000,000 ns)
  Network round-trip (same DC) .......   0.5 ms
  Network round-trip (cross-country) ..  40 ms
  Network round-trip (cross-ocean) ...  150 ms

THROUGHPUT:
  SSD sequential read ................  1 GB/s
  HDD sequential read ................  100 MB/s
  Network (1 Gbps link) ..............  125 MB/s
  Network (10 Gbps link) .............  1.25 GB/s

STORAGE:
  1 ASCII character ..................  1 byte
  1 UUID (string) ....................  36 bytes
  1 UUID (binary) ....................  16 bytes
  1 IPv4 address .....................  4 bytes
  1 Unix timestamp ...................  4 bytes (32-bit) or 8 bytes (64-bit)
  Average tweet ......................  ~300 bytes (metadata + text)
  Average web page ...................  ~2 MB
  Average photo (compressed) .........  ~200 KB
  Average short video (1 min) ........  ~10 MB

SCALE:
  Seconds in a day ...................  86,400   (~10^5)
  Seconds in a month .................  2,592,000 (~2.5 * 10^6)
  Seconds in a year ..................  31,536,000 (~3 * 10^7)
  1 million requests/day .............  ~12 requests/second
  1 billion requests/day .............  ~12,000 requests/second
```

The two latency numbers worth internalizing above all others: an SSD read (~150 us) is roughly **65x faster** than an HDD read (~10 ms), and a same-datacenter round-trip (~0.5 ms) is roughly **300x faster** than a cross-ocean one (~150 ms). In an interview these ratios are what let you say "this should be served from a replica in-region, not over a trans-Atlantic call" without reaching for exact figures.

> **Common pitfall:** Mixing up the unit prefixes is the single most common way these estimates go wrong. 1 us = 1,000 ns, 1 ms = 1,000 us = 1,000,000 ns, and 1 GB/s = 1,000 MB/s. A misplaced factor of 1,000 turns "fits on one box" into "needs a cluster," so write the units next to every number and check that the powers of ten line up before you trust the verdict.

## Walkthrough Example 1: URL Shortener Scale Estimation

With the reference numbers in hand, we can put the method to work. We begin with the gentlest case -- a URL shortener -- because it exercises the full sequence (writes, reads, storage, cache, bandwidth) while keeping every individual calculation small.

**Problem**: Design a URL shortener that handles 100 million new URLs per month and a 100:1 read-to-write ratio. Estimate the storage, bandwidth, and caching requirements.

```
WRITE (URL creation):
  100 million URLs / month
  = 100,000,000 / (30 * 86,400) seconds
  = 100,000,000 / 2,592,000
  ~= 40 URLs created per second

READ (redirects):
  100:1 read-to-write ratio
  = 40 * 100 = 4,000 redirects per second

STORAGE (for 5 years):
  Each URL record:
    short_code:   7 bytes
    long_url:     average 200 bytes
    created_at:   8 bytes
    expires_at:   8 bytes
    user_id:      16 bytes (UUID)
    TOTAL:        ~250 bytes per record

  Total records in 5 years:
    100,000,000 * 12 * 5 = 6 billion records

  Total storage:
    6,000,000,000 * 250 bytes = 1.5 TB

  Verdict: 1.5 TB fits comfortably on a single modern database server.
  But at 4,000 reads/sec, you will want read replicas and caching.

CACHING (Redis):
  Apply the 80/20 rule: 20% of URLs get 80% of traffic.
  Cache the top 20% of daily accessed URLs.

  Daily unique URLs accessed:
    4,000 req/sec * 86,400 sec/day = 345,600,000 requests/day
    Assume 10% are unique URLs = ~35 million unique URLs/day

  Cache top 20%: 35,000,000 * 0.2 = 7 million URLs
  Memory: 7,000,000 * 250 bytes = 1.75 GB

  Verdict: 1.75 GB easily fits in a single Redis instance.
  This cache would handle ~80% of all redirect traffic.

BANDWIDTH:
  Incoming (write): 40 req/sec * 250 bytes = 10 KB/s (negligible)
  Outgoing (read):  4,000 req/sec * 250 bytes = 1 MB/s (negligible)

  Verdict: Bandwidth is not a bottleneck for this system.
```

Notice the shape of the answer: writes are trivial (40/sec, 10 KB/s), storage is comfortable on one box (1.5 TB), and the entire system is dominated by the **4,000 reads/sec**. That is the number that drives the architecture toward read replicas plus a cache, and the 80/20 estimate shows a 1.75 GB Redis instance can absorb ~80% of it. In an interview, calling out "this is a read-heavy system" before computing anything earns more credit than the arithmetic itself.

> **Key Takeaway:** Let the read-to-write ratio decide the architecture. A 100:1 ratio means the cache and read replicas are the design, not an afterthought -- size them first, then confirm the write path and storage are the easy parts.

## Walkthrough Example 2: Chat System Scale Estimation

The URL shortener was forgiving: everything fit on one box except the read path. Our second walkthrough removes that comfort. A chat system is stateful -- it holds millions of long-lived connections and accumulates storage far faster -- so the same estimation steps now produce numbers that force distribution.

**Problem**: Design a chat system for 10 million daily active users (DAU). Each user sends an average of 40 messages per day. Estimate the storage, connection, and message throughput requirements.

```
MESSAGES:
  Total messages per day: 10,000,000 * 40 = 400,000,000 messages/day
  Messages per second: 400,000,000 / 86,400 ~= 4,600 messages/second
  Peak (3x average): ~14,000 messages/second

MESSAGE STORAGE (for 5 years):
  Average message size:
    message_id:       16 bytes (UUID)
    conversation_id:  16 bytes
    sender_id:        16 bytes
    body:             200 bytes (average text)
    timestamp:        8 bytes
    metadata:         50 bytes (read receipts, etc.)
    TOTAL:            ~300 bytes per message

  Daily: 400,000,000 * 300 bytes = 120 GB/day
  Yearly: 120 GB * 365 = 43.8 TB/year
  5 years: ~220 TB

  Verdict: This requires a distributed database (Cassandra, DynamoDB)
  with horizontal partitioning by conversation_id.

WEBSOCKET CONNECTIONS:
  10 million DAU, assume 30% are online simultaneously at peak.
  = 3,000,000 concurrent WebSocket connections.

  Each WebSocket connection uses ~10 KB of server memory.
  Total memory: 3,000,000 * 10 KB = 30 GB

  If each server handles ~50,000 connections:
  Servers needed: 3,000,000 / 50,000 = 60 WebSocket servers

  Verdict: 60 servers is manageable. Use connection draining
  during deployments to avoid dropping active connections.

PRESENCE (Redis):
  Each online user has a presence key in Redis.
  Key: "presence:{user_id}" (average 30 bytes for key + value)
  3,000,000 online users * 30 bytes = 90 MB

  User-to-server mapping:
  HSET user_connections: 3,000,000 entries * 40 bytes = 120 MB

  Verdict: ~210 MB total. Trivial for Redis.
```

The decisive number here is storage: 220 TB over five years is what rules out a single relational instance and forces a horizontally partitioned store. Equally important is the **3x peak multiplier** on throughput (~14,000 msg/sec) and the stateful WebSocket fan-out -- 3 million long-lived connections is a capacity-planning problem (60 servers, connection draining on deploy) that a stateless HTTP service never has.

> **Common pitfall:** Sizing for the daily average instead of the peak. Traffic is bursty -- a chat system spikes at evenings, an e-commerce system spikes during flash sales -- and a system provisioned for the 4,600/sec average will fall over at the 14,000/sec peak. Always carry a peak factor (this book uses 3x for chat, 5x for flash sales) through the throughput and worker-count math, and state the multiplier as an explicit assumption.

> **Key Takeaway:** For a stateful, high-volume system, storage growth over the retention window and peak concurrent connections are the two numbers that pick your database and your server count. Compute both before anything else.

## Walkthrough Example 3: Notification System Scale Estimation

The first two examples sized storage and connections; the final one sizes work. A notification system is dominated by outbound calls to third-party providers, so the estimate must account for per-call latency, provider rate limits, and batching -- factors the earlier walkthroughs never touched.

**Problem**: A notification system for an e-commerce platform with 50 million registered users. On average, each user receives 3 notifications per day. Estimate throughput and worker capacity.

```
THROUGHPUT:
  Total notifications/day: 50,000,000 * 3 = 150,000,000/day
  Notifications/second (average): 150,000,000 / 86,400 ~= 1,736/sec
  Peak (5x during flash sales): ~8,680/sec

CHANNEL BREAKDOWN (estimated):
  60% in-app only:     90,000,000/day  (1,042/sec avg)
  25% in-app + push:   37,500,000/day  (434/sec avg)
  10% in-app + email:  15,000,000/day  (174/sec avg)
  5%  all channels:     7,500,000/day  (87/sec avg)

  Total push:  37,500,000 + 7,500,000 = 45,000,000/day
  Total email: 15,000,000 + 7,500,000 = 22,500,000/day

EMAIL WORKER CAPACITY:
  SendGrid rate limit: ~600 emails/sec per account
  Average send time: ~50ms per API call
  Each worker thread handles: 1000ms / 50ms = 20 emails/sec
  Workers needed at peak: 22,500,000 / 86,400 * 5x peak = ~1,302/sec
  Threads needed: 1,302 / 20 = 66 threads (~7 servers with 10 threads each)

PUSH WORKER CAPACITY:
  FCM supports batching (up to 500 tokens per request).
  Batch send time: ~100ms
  Each worker: 500 / 0.1 = 5,000 pushes/sec
  Peak push rate: 45,000,000 / 86,400 * 5 = ~2,604/sec
  Workers needed: 2,604 / 5,000 = 1 worker (with headroom, use 3)

STORAGE (notification log, 1 year):
  Each notification record: ~200 bytes
  150,000,000/day * 365 * 200 bytes = 10.95 TB/year

  Verdict: Manageable with a partitioned database. Partition by
  user_id for efficient "show my notifications" queries.
```

The interesting result is how cheap the workers are: even at a 5x flash-sale peak, email needs ~66 threads (~7 servers) and push needs a single worker. That asymmetry comes straight from the per-channel cost -- a serial SendGrid call at 50 ms versus an FCM batch of 500 tokens in 100 ms is a 100x difference in per-worker throughput. The lesson for real systems: **batching is the lever**, and you should reach for the provider's batch API before scaling out worker count.

> **Key Takeaway:** Throughput per worker is dominated by per-item latency and batch size, not by raw request volume. When a queue backs up, first ask whether the downstream call can be batched -- it is usually cheaper than adding servers.

> **Key Takeaway**: Back-of-envelope calculations are not about getting exact numbers. They are about getting the right order of magnitude. The difference between 100 requests/second and 100,000 requests/second determines whether you need a single server or a distributed cluster. Always start with the daily active users, derive the operations per second, estimate storage per record, multiply out over your retention period, and then determine how many servers/instances each component needs. Present your assumptions clearly -- they matter more than the final numbers.

## Summary

The method of this section is deliberately mechanical: start from daily active users or daily volume, divide by 86,400 (~10^5) seconds to get operations per second, apply a peak multiplier (3x for chat, 5x for flash sales), estimate bytes per record, multiply out over the retention window, and only then ask what each component needs. The reference numbers make this fast. One million requests per day is ~12 per second; a billion is ~12,000. An SSD random read (~150 us) is ~65x faster than an HDD read (~10 ms), and a same-datacenter round-trip (~0.5 ms) is ~300x faster than a cross-ocean one (~150 ms). A record is typically a few hundred bytes, so a billion of them is a few hundred gigabytes -- single-server territory -- while 5 years of chat history (~220 TB) is not.

The three walkthroughs each surfaced one decisive number. For the URL shortener it was 4,000 reads/sec, pushing the design toward replicas and a 1.75 GB cache. For the chat system it was 220 TB of storage and 3 million concurrent connections, forcing a partitioned store and 60 stateful servers. For the notification system it was per-call latency and batch size, where a 500-token FCM batch made one worker do the work of a hundred serial senders. The pattern repeats: the estimate's job is to find the number that picks the architecture, with assumptions stated plainly.

Two of those walkthroughs leaned on a cache to absorb most of the load; the next section, 6.5 Caching & CDN Deep-Dive, examines how those caches actually behave -- and misbehave -- in production.

*Last reviewed: 2026-06-08*

**Next:** [6.5 Caching & CDN Deep-Dive](caching-and-cdn.md)
