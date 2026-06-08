import math
import random
import time


class StampedeProtectedCache:
    """Cache-aside helper that prevents cache stampedes (the thundering herd).

    Wrap an expensive loader so that when a hot key expires, concurrent readers
    do not all recompute at once. Implement probabilistic early expiration
    (XFetch): recompute *before* expiry with a probability that rises as the TTL
    nears, so one request refreshes the key while the rest still read the cache.
    """

    def __init__(self, ttl: float = 60.0, beta: float = 1.0):
        self.store: dict = {}          # key -> (value, delta, expiry)
        self.ttl = ttl
        self.beta = beta

    def get(self, key, loader):
        # TODO:
        #   1. If key is cached and
        #      time.time() - delta * self.beta * math.log(random.random()) < expiry,
        #      return the cached value.
        #   2. Otherwise call loader(), measure how long it takes (delta),
        #      store (value, delta, time.time() + self.ttl), and return value.
        return None


if __name__ == "__main__":
    cache = StampedeProtectedCache(ttl=5)
    print(cache.get("homepage", lambda: "rendered-html"))  # -> None until implemented
