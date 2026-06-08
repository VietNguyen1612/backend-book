# Comprehensive Homework: 05-api-design

[Back to Chapter](../README.md) | [Back to Book Index](../../../README.md)

## RESTful APIs: Rate Limiter

Implement a Token Bucket rate limiter for an API endpoint.
**Implement in**: `hw_rate_limit.py`

## Beyond REST: Simple GraphQL Resolver

Write a mock GraphQL resolver that handles resolving nested entity data without N+1 issues.
**Implement in**: `hw_graphql.py`

## Auth: JWT Minting

Create functions to mint and verify HMAC-based JSON Web Tokens (without using third-party JWT libraries).
**Implement in**: `hw_auth.py`

## RESTful APIs: Sliding-Window Rate Limiter

Implement a per-client sliding-window rate limiter that allows at most N requests per time window (distinct from the token-bucket exercise above).
**Implement in**: `rate_limiter.py`

## Auth: WebAuthn Assertion Verification

Verify a simplified WebAuthn authentication assertion: check the challenge, origin, RP ID hash, signature, and sign-count monotonicity (signature verification is provided).
**Implement in**: `hw_webauthn.py`
