[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 6.5 Caching & CDN Deep-Dive

Section 6.1 introduced the caching *patterns* (cache-aside, write-through, write-behind) and where a cache sits in an architecture. This section goes a level deeper into the mechanics you actually tune in production: the cache hierarchy and its latency tiers, HTTP caching semantics, how CDNs really work, the hard problem of invalidation, and the two failure modes that take caches down -- **stampedes** and **hot keys**.

### The Cache Hierarchy

A request can be answered at any of several tiers, each an order of magnitude slower than the one before it. The goal of a caching strategy is to answer as far *left* as possible.

```
  Cache hierarchy (typical latencies)
  ===================================

  Browser cache ----> CDN edge (PoP) ----> Origin shield ----> App in-process ----> Distributed ----> Database
   ~0 ms (local)       ~10-30 ms            ~20-40 ms           ~100 ns-1 us        cache (Redis)      (Postgres)
                                                                 (LRU in RAM)        ~0.5-2 ms          ~1-10 ms+

  Each tier should have a SHORTER TTL as you move right toward the source of
  truth, and absorb a LARGER share of traffic as you move left toward the user.
```

The lesson is to **layer** caches, not pick one. A fingerprinted JS bundle is served from the browser cache on repeat views, from a CDN edge for new visitors, and only rarely from your origin. A hot product row is served from a per-process LRU for microseconds, falling back to Redis, falling back to Postgres. Each tier shaves load off the next.

#### Effective latency and why hit ratio dominates

Average latency is `hit_ratio * t_hit + (1 - hit_ratio) * t_miss`. Because `t_miss` is often 10-100x `t_hit`, a *small* miss rate dominates the average:

```text
 t_hit = 1 ms, t_miss = 50 ms
   99% hit ratio -> 0.99*1 + 0.01*50 = 1.49 ms
   95% hit ratio -> 0.95*1 + 0.05*50 = 3.45 ms
   90% hit ratio -> 0.90*1 + 0.10*50 = 5.90 ms
```

**How to read these numbers:** going from 99% to 90% hit ratio is only a 9-point drop, but it nearly *quadruples* average latency, because every miss costs 50x a hit. This is why chasing the last few points of hit ratio (origin shielding, longer TTLs, stampede protection) is worth real effort, and why a cache that silently drops to an 80% hit ratio under load can look like an origin outage.

### HTTP Caching Semantics

The browser and CDN tiers are governed by HTTP response headers. Getting these right is free caching; getting them wrong either leaks stale data or defeats the cache entirely.

```text
$ curl -sI https://cdn.example.com/static/app.4f3a1c.js
HTTP/2 200
cache-control: public, max-age=31536000, immutable
etag: "4f3a1c-9e2"
age: 84210
x-cache: HIT
vary: accept-encoding
```

**How to read this output:** `max-age=31536000, immutable` says "cache for a year and never revalidate" -- safe *only* because the filename is content-hashed (`app.4f3a1c.js`), so a new build produces a new URL rather than mutating this one. `age: 84210` means the CDN has held this object ~23 hours; `x-cache: HIT` confirms it was served from the edge, not the origin. `vary: accept-encoding` tells the CDN to keep separate cached copies for gzip vs brotli vs identity, so a client never receives an encoding it cannot read. The `etag` lets a *revalidating* client send `If-None-Match: "4f3a1c-9e2"` and get a tiny `304 Not Modified` instead of the whole body.

Key directives, and when each is right:

- **`max-age`** (browser) / **`s-maxage`** (shared caches/CDN) -- the freshness lifetime. Set `s-maxage` high and `max-age` low when you can purge the CDN but not browsers.
- **`public` vs `private`** -- `private` lets the browser cache but forbids shared caches (use for per-user responses); `public` permits CDN caching.
- **`no-cache`** -- *may* store, but must revalidate with the origin before each reuse (a validator round-trip). Not the same as `no-store`, which forbids caching entirely (use for secrets).
- **`stale-while-revalidate=N`** -- serve the stale copy instantly for up to N seconds *while* refreshing in the background. This is the single most effective directive for hiding origin latency from users.
- **`stale-if-error=N`** -- serve stale on an origin 5xx/timeout, turning a hard outage into degraded-but-up.

Validators give you cheap revalidation: a strong **`ETag`** (content hash) or **`Last-Modified`** date lets the cache ask "still current?" and usually receive a 304.

In Django, set these per-view rather than globally:

```python
from django.views.decorators.cache import cache_control
from django.views.decorators.http import etag

@cache_control(public=True, max_age=60, s_maxage=600, stale_while_revalidate=30)
def product_detail(request, pk):
    ...

# Conditional GET: compute a cheap ETag and let Django return 304 automatically
@etag(lambda request, pk: f'"{Product.objects.values_list("updated_at", flat=True).get(pk=pk).timestamp()}"')
def product_json(request, pk):
    ...
```

### How CDNs Actually Work

A CDN is a globally distributed reverse-proxy cache. The mechanics worth understanding:

- **PoPs (points of presence)** terminate the user's TLS close to them and serve cache hits from the nearest edge. The win is both fewer origin trips *and* a shorter RTT for the bytes that do flow.
- **Origin shield** is an optional mid-tier: all PoPs funnel their *misses* through one shield node instead of stampeding the origin directly. With dozens of PoPs, this can be the difference between 1 origin request and 50 for the same cold object, and it raises overall hit ratio.
- **The cache key** is, by default, the URL -- plus whatever `Vary` lists, plus any query/header rules you configure. A common bug is letting a tracking query param (`?utm_source=...`) into the key, which shatters the hit ratio by creating a distinct cache entry per campaign link.
- **Invalidation: purge vs versioned URLs.** Purging (telling the CDN to drop a key) is eventually consistent and rate-limited; prefer **content-fingerprinted URLs** for static assets (`app.4f3a1c.js` + `immutable`) so a deploy *changes the URL* and never needs a purge. Reserve purge for HTML and API responses you cannot version.
- **Signed URLs / tokens** gate private content at the edge (time-limited, optionally IP-bound) without a round-trip to your origin for authorization.

### Cache Invalidation

> [!NOTE]
> **Beginner's Mental Model — Cache Invalidation:**
> Imagine you keep a notepad on your desk with a list of your friends' phone numbers (the cache) so you don't have to look them up in the city directory (the database) every time. **Cache Invalidation** is the process of updating or crossing out a number on your notepad when a friend changes their phone number. If you don't do this (or do it incorrectly), you'll keep calling the old, wrong number (serving stale data).

> "There are only two hard things in Computer Science: cache invalidation and naming things." -- Phil Karlton

The strategies, from simplest to strongest:

- **TTL expiry** -- the default. Bounded staleness, zero coordination. The right choice when "a few seconds/minutes stale" is acceptable, which is most read-heavy data.
- **Write-through / explicit invalidation** -- on a write, update or delete the cache entry. As 6.1 noted, *deleting* is safer than rewriting (the next read repopulates from the source of truth, avoiding a cached value that never matched the row).
- **Event/CDC-based** -- a change-data-capture stream (see 4.3) fans out invalidations to every tier, decoupling cache maintenance from the write path. Essential when many services cache the same data.
- **Versioned keys** -- embed a version in the key (`user:42:v7`); bumping the version atomically "invalidates" all derived entries without deleting them. Great for invalidating a whole computed view at once.
- **Negative caching** -- cache *misses* (404s) for a short TTL so an attacker requesting random non-existent IDs cannot turn every request into a database query (cache penetration). Pair with a Bloom filter for high-cardinality keyspaces.

### Cache Stampede (Thundering Herd)

> [!NOTE]
> **Beginner's Mental Model — Cache Stampede (Thundering Herd):**
> Imagine a popular restaurant has a sign in the window showing the "Special of the Day" (the cached value). Everyone looks at the sign and orders without asking the chef. Suddenly, the wind blows the sign away (the cache expires). At that exact moment, 100 hungry customers all run into the kitchen at once to ask the chef what the special is. The chef is overwhelmed by the sudden stampede and the kitchen grinds to a halt.

When a popular key expires, every concurrent request misses at once and hits the origin simultaneously -- the recomputation that was supposed to be amortized across thousands of reads now happens thousands of times in a burst, often toppling the database.

```
  Stampede on expiry of a hot key
  ===============================

   t0: key "homepage" expires
       req1 req2 req3 ... req5000   <- all MISS in the same instant
         \    \    \         /
          v    v    v       v
        +-----------------------+
        |   ORIGIN / DATABASE   |   <- 5000x the load it expected
        +-----------------------+
```

Three defenses, often combined:

1. **Single-flight (request coalescing)** -- the first miss takes a lock and recomputes; concurrent requests wait for that one result instead of all recomputing.
2. **Probabilistic early recomputation (XFetch)** -- recompute *before* expiry, with a probability that rises as the TTL approaches, so one lucky request refreshes the key while the rest are still served the cached value. No lock, no synchronized expiry.
3. **`stale-while-revalidate`** -- at the HTTP tier, serve stale and refresh in the background (the same idea, expressed in headers).

```python
import math
import random
import time

def get_with_xfetch(cache, db, key, ttl, beta=1.0):
    """Cache-aside read with probabilistic early expiration (XFetch).

    Stores (value, delta, expiry). A request recomputes early with rising
    probability as expiry nears, so the herd never all misses at once.
    """
    packed = cache.get(key)
    if packed is not None:
        value, delta, expiry = packed
        # Recompute early if now - delta*beta*ln(rand) has crossed the expiry.
        if time.time() - delta * beta * math.log(random.random()) < expiry:
            return value
    start = time.time()
    value = db.load(key)              # the expensive recomputation
    delta = time.time() - start       # how long it took (feeds the formula)
    cache.set(key, (value, delta, time.time() + ttl), ex=ttl * 2)
    return value
```

```python
# Single-flight with a short-lived Redis lock: only one worker recomputes.
def get_single_flight(r, db, key, ttl):
    value = r.get(key)
    if value is not None:
        return value
    # SET NX: only the first caller acquires the recompute lock.
    if r.set(f"lock:{key}", "1", nx=True, ex=10):
        try:
            value = db.load(key)
            r.set(key, value, ex=ttl)
            return value
        finally:
            r.delete(f"lock:{key}")
    time.sleep(0.05)                   # brief backoff, then read the freshly set value
    return r.get(key) or db.load(key)  # fallback if still cold
```

Note that Django's `cache.get_or_set()` is convenient but **not** stampede-safe -- under concurrency every missing request runs the callable. Reach for one of the patterns above on genuinely hot keys.

### Hot Keys

A *hot key* is a single key so popular that the one cache node owning it (by consistent hashing) saturates -- a stampede is a hot key in time; a hot key is concentration in space. Mitigations:

- **Local (in-process) tier** -- put a tiny, short-TTL LRU in front of the distributed cache. A 1-second local TTL on a key read 50,000x/s collapses 50,000 Redis reads into ~1, at the cost of up to 1s of extra staleness.
- **Key splitting / replication** -- store the value under N suffixed keys (`hot:0` .. `hot:N-1`) spread across nodes and have each reader pick one at random, dividing the load by N. Invalidate all N on write.
- **Client-side caching** -- Redis 6+ client-side caching (tracking) lets the server invalidate keys the client has cached, giving near-local reads with coherence.

```python
from functools import lru_cache  # illustrative; in prod use a TTL-aware cache
# A per-process L1 in front of Redis turns a hot remote key into a local read.
@lru_cache(maxsize=1024)
def _local(key, _bucket):          # _bucket = int(time.time()) // 1  -> ~1s TTL
    return redis_client.get(key)

def read_hot(key):
    return _local(key, int(time.time()))
```

> **Key Takeaway:** Caching is a hierarchy, not a single layer -- answer as close to the user as you can, with shorter TTLs toward the source of truth. Let HTTP headers (`s-maxage`, `stale-while-revalidate`, `ETag`) do the work at the browser and CDN tiers, and fingerprint static assets so deploys never need a purge. The two ways caches fail under load are stampedes (synchronize-on-expiry) and hot keys (concentrate-on-one-node); defend the first with single-flight or probabilistic early recomputation, and the second with a local tier or key splitting. And remember the math: the difference between a 99% and a 90% hit ratio is the difference between a fast service and an overloaded origin.

*Last reviewed: 2026-06-08*
