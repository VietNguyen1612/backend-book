# Comprehensive Homework: 03-software-architecture

[Back to Chapter](../README.md) | [Back to Book Index](../../../README.md)

## Principles: SOLID Refactoring

Refactor a monolithic God-class into single-responsibility classes.
**Implement in**: `hw_solid.py`

## Patterns: Observer

Implement the Observer pattern for an Eventbus that handles pub/sub events.
**Implement in**: `hw_patterns.py`

## Styles: Hexagonal Architecture

Define Ports (Interfaces) and Adapters for a hypothetical 'User Service'.
**Implement in**: `hw_architecture.py`

## Styles: Refactor to Hexagonal (Ports & Adapters)

Take the tightly-coupled `register_user` function (direct SQLite + SMTP calls) and refactor it into a Hexagonal Architecture: define repository/notifier ports, concrete adapters, and a use case that depends only on the ports.
**Implement in**: `refactoring.py`
