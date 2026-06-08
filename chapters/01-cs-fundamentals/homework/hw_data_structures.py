"""Data Structures Homework: LRU Cache.

Implement an LRU (Least Recently Used) Cache from scratch using a Hash Map
and a Doubly Linked List for O(1) get/put operations.

Expected behavior:
    - get(key): return the value if present, otherwise -1.
    - put(key, value): insert/update; evict the least-recently-used entry
      once capacity is exceeded.
"""


class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        # TODO: Initialize your hash map and dummy head/tail nodes here

    def get(self, key: int) -> int:
        # TODO: Implement get method
        pass

    def put(self, key: int, value: int) -> None:
        # TODO: Implement put method
        pass


if __name__ == "__main__":
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    print(cache.get(1))       # returns 1
    cache.put(3, 3)           # evicts key 2
    print(cache.get(2))       # returns -1 (not found)
