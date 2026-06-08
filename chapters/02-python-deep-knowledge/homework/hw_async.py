"""Async Homework: Miniature Event Loop.

Use generator-based coroutines to simulate a tiny async event loop.

Generator-coroutine protocol hint:
    - A coroutine is a generator function: each ``yield`` is a point where it
      suspends and hands control back to the loop.
    - The loop drives a coroutine with ``next(coro)`` (or ``coro.send(value)``
      to resume it and pass a value back to the awaiting ``yield``).
    - When the generator is exhausted it raises ``StopIteration``; catch that to
      know the task is complete, then drop it from the scheduler.
"""


class EventLoop:
    def __init__(self):
        self.tasks = []

    def add_task(self, coro):
        pass

    def run_until_complete(self):
        # TODO: Iterate over tasks using `send()` or `next()`,
        # rescheduling each task until it raises StopIteration.
        pass
