"""NoSQL Homework: Thread-safe Key-Value Store with TTL (mini-Redis)."""

import time       # hint: use time.monotonic()/time.time() for TTL expiry
import threading  # hint: guard the store with a threading.Lock for thread safety


class KVStore:
    def set(self, key, value, ttl=None):
        pass

    def get(self, key):
        # TODO: Evict if TTL expired
        pass
