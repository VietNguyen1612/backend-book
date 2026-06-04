# Chapter 2: Python Deep Knowledge

[Back to Book Index](../../README.md)

This chapter dives deep into the Python language and its ecosystem -- from the internal mechanics of CPython to advanced programming patterns and modern tooling. It covers everything a backend engineer needs to write efficient, well-structured, and production-ready Python code.

## Table of Contents

### [2.1 Language Internals](language-internals.md)
A thorough exploration of how Python works under the hood. Covers the data model (objects, `__slots__`, descriptors, metaclasses, MRO, dunder methods), memory management and garbage collection (reference counting, generational GC, weak references, memory profiling, interning), the GIL and its workarounds (threading vs multiprocessing, free-threaded Python), and CPython internals (bytecode, frame objects, pymalloc).

### [2.2 Async Programming](async-programming.md)
Everything about asynchronous programming in Python. Covers the `asyncio` event loop and cooperative multitasking, `gather`/`wait`/`create_task`, synchronization primitives, structured concurrency with `TaskGroup`, async frameworks (FastAPI, ASGI servers, Django async), and common async patterns (connection pooling, backpressure, cancellation/timeouts, testing async code).

### [2.3 Advanced Patterns](advanced-patterns.md)
Key design patterns and language features for writing expressive Python. Covers decorators and context managers (function/class-based decorators, `@contextlib.contextmanager`, `ExitStack`), generators and iterators (lazy evaluation, `yield from`, the iterator protocol, `itertools`), type hints and static analysis (annotations, generics, `Protocol`, `TypedDict`, mypy, Pydantic), and concurrency patterns (`concurrent.futures`, multiprocessing, threading primitives).

### [2.4 Packaging & Tooling](packaging-and-tooling.md)
Modern Python project setup and development workflow. Covers dependency management (`pyproject.toml`, Poetry, pip-tools, uv, virtual environments), code quality (Ruff linter/formatter, pre-commit hooks, pytest testing framework), and profiling and optimization (cProfile, line_profiler, py-spy, practical optimization strategies).

---

## Homework

Hands-on exercises for this chapter -- see [homework/questions.md](homework/questions.md). Skeleton files (`hw_*.py`) live alongside the questions in the [`homework/`](homework/) folder.

[Back to Book Index](../../README.md)
