# Chapter 5: API Design & Integration

This chapter covers the principles, protocols, and patterns for designing robust backend APIs. From foundational REST conventions through modern alternatives like GraphQL and gRPC, to securing your services with authentication and authorization, this chapter provides the practical knowledge needed to build APIs that are consistent, performant, and secure.

## Table of Contents

### [5.1 RESTful APIs](restful-apis.md)
The foundation of web API design. Covers REST principles (resources, URIs, HTTP methods, status codes, HATEOAS), best practices for versioning, pagination, filtering, error handling, idempotency, rate limiting, and bulk operations, as well as API documentation with OpenAPI/Swagger.

**Key topics:** REST principles, HTTP methods and status codes, URL path versioning, cursor-based pagination, consistent error formats, idempotency keys, rate limiting with Redis, bulk operations, OpenAPI specs, design-first workflow

### [5.2 Beyond REST](beyond-rest.md)
Alternative API paradigms for when REST is not the best fit. Covers GraphQL (schema design, resolvers, DataLoader, Relay pagination, authorization), gRPC (Protocol Buffers, streaming patterns, interceptors), WebSocket and Server-Sent Events for real-time communication, and asynchronous messaging with RabbitMQ, Kafka, Celery, and webhooks.

**Key topics:** GraphQL with Strawberry and Graphene, N+1 problem and DataLoader, gRPC with Protocol Buffers, HTTP/2 multiplexing, WebSocket scaling with Redis Pub/Sub, SSE for streaming, RabbitMQ exchanges and dead letter queues, Kafka consumer groups, Celery task workflows, webhook HMAC signing, AsyncAPI

### [5.3 Authentication & Authorization](authentication-and-authorization.md)
Securing your APIs. Covers authentication mechanisms (OAuth 2.0 flows, JWT with RS256, refresh token rotation, API keys, session-based auth, SSO with OIDC/SAML) and authorization models (RBAC, ABAC, OPA policy engine, PostgreSQL row-level security, principle of least privilege).

**Key topics:** OAuth 2.0 Authorization Code + PKCE, Client Credentials flow, JWT creation and verification, refresh token rotation, API key hashing and rotation, session cookies, OIDC and SAML, RBAC with FastAPI dependencies, ABAC policy engine, OPA and Rego, PostgreSQL RLS, least privilege

---

[Back to Book Index](../../README.md)
