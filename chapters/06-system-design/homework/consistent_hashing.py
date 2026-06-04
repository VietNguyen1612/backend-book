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
