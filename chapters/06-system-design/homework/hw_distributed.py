"""Distributed Systems Homework: Consistent Hashing.

Implement a consistent hashing ring with virtual nodes (replicas) so that
adding or removing a node only remaps a small fraction of keys.
"""

import hashlib
import bisect


class ConsistentHashRing:
    def __init__(self, replicas=3):
        self.replicas = replicas
        self.ring = dict()
        self.sorted_keys = []

    def add_node(self, node: str):
        # TODO: Add a node and its replicas to the ring
        pass

    def remove_node(self, node: str):
        # TODO: Remove a node and its replicas from the ring
        pass

    def get_node(self, key: str) -> str:
        # TODO: Return the node responsible for the given key
        pass


if __name__ == "__main__":
    ring = ConsistentHashRing(replicas=3)
    ring.add_node("server-a")
    ring.add_node("server-b")
    print("Key 'user42' maps to:", ring.get_node("user42"))
