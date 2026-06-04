# Chapter 3: Software Architecture

[Back to Book Index](../../README.md)

This chapter covers the foundational principles, patterns, and architectural styles that guide how backend systems are designed and organized. It progresses from small-scale design decisions (principles and patterns) to large-scale system organization (architectural styles), with practical Python and Django examples throughout.

---

## Table of Contents

### [3.1 Design Principles](design-principles.md)

Core principles for writing maintainable, testable, and flexible code.

- **SOLID Principles** -- Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **Other Key Principles** -- DRY, KISS, YAGNI, Composition Over Inheritance, Law of Demeter, Separation of Concerns, Convention Over Configuration
- **Clean Architecture / Hexagonal Architecture** -- Dependency rule, layers (domain, use cases, adapters, frameworks), ports and adapters, practical Python example

### [3.2 Design Patterns](design-patterns.md)

Reusable solutions to common software design problems, organized by intent.

- **Creational Patterns** -- Factory Method, Abstract Factory, Builder, Singleton, Prototype
- **Structural Patterns** -- Adapter, Decorator, Facade, Proxy, Composite
- **Behavioral Patterns** -- Observer, Strategy, Command, Chain of Responsibility, State, Repository, Unit of Work, CQRS

### [3.3 Architectural Styles](architectural-styles.md)

High-level strategies for organizing entire systems, with implications for deployment, scaling, and team structure.

- **Monolith** -- Modular monolith structure, benefits, when to move away
- **Microservices** -- Characteristics, data ownership, communication patterns, Saga pattern, Strangler Fig migration
- **Event-Driven Architecture** -- Event Sourcing, event types, event bus options (Kafka, RabbitMQ, EventBridge), idempotency
- **Domain-Driven Design (DDD)** -- Bounded Context, Aggregates, Value Objects, Domain Events, Anti-Corruption Layer, Context Mapping

---

## Homework

Hands-on exercises for this chapter -- see [homework/questions.md](homework/questions.md). Skeleton files (`hw_*.py`) live alongside the questions in the [`homework/`](homework/) folder.

[Back to Book Index](../../README.md)
