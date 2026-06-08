"""Observability Homework: Tracing Span context manager.

Implement a context manager that acts as a tracing 'Span', recording how long
the wrapped block takes to execute.
"""

import time  # hint: capture time.monotonic() in __enter__ and __exit__


class Span:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        # TODO: Record the start time here.
        # Return self so callers can do `with Span("x") as span:`.
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO: Calculate and log duration
        pass
