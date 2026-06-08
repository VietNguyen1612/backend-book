"""Algorithms Homework: Topological Sort."""

from collections import deque  # hint: Kahn's algorithm uses a queue of zero-in-degree nodes


def topological_sort(graph: dict) -> list:
    """Return a topological ordering of nodes in a dependency graph.

    Input: graph as an adjacency dict, e.g. {"a": ["b", "c"], "b": ["c"], "c": []},
    where graph[node] lists the nodes that `node` points to (its dependents/successors).
    Output: a list of nodes such that every node appears before the nodes it points to.
    """
    # TODO: Implement DFS or Kahn's algorithm to sort nodes
    pass
