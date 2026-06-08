# Comprehensive Homework: 09-testing-strategy

[Back to Chapter](../README.md) | [Back to Book Index](../../../README.md)

## Pyramid: API Mocking

Use standard `unittest.mock` to mock an external API response.
**Implement in**: `hw_pyramid.py`

## Practices: Property Based

Write a mock property-based test engine that generates 100 random strings to test a parsing function.
**Implement in**: `hw_practices.py`

## Pyramid: Mocking a Payment Gateway

Write pytest tests for a `PaymentService` by mocking its `StripeAPI` dependency: cover a successful charge, a failed charge, and a negative amount raising `ValueError`.
**Implement in**: `test_payment.py`
