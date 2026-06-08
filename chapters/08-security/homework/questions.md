# Comprehensive Homework: 08-security

[Back to Chapter](../README.md) | [Back to Book Index](../../../README.md)

## App Sec: Sanitizer

Write a function that sanitizes HTML input to prevent basic XSS attacks.
**Implement in**: `hw_app_sec.py`

## Infra Sec: Secret Rotation

Simulate a secret rotation strategy by updating a mock Vault and invalidating old sessions.
**Implement in**: `hw_infra_sec.py`

## App Sec: Secure the Vulnerable App

Refactor a deliberately insecure module to fix three flaws: a SQL injection (use parameterized queries), a hardcoded API secret (read from an environment variable), and a path-traversal bug (validate/sanitize the file path).
**Implement in**: `secure_app.py`
