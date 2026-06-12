# Backend Developer Knowledge Base

**Mid → Senior → Architect Level · Python/Django Flavored · Framework-Agnostic Principles**

**[🔎 Search this book](search.md)**

---

## How This Book Is Organized

The twelve chapters are grouped into five parts, ordered so that each part stands on the ones before it. Read front to back if you can -- every section ends with a **Next** link that follows this order, and each opens with a summary of what it assumes. Or jump in anywhere: the part introductions below tell you where you are landing.

---

## Part I: Foundations (Chapters 1–2)

Everything in this book ultimately runs as processes, sockets, and bytes -- written here in Python. Part I builds that base twice over: first the computer science that is true in every language (data structures, algorithms, operating systems, networking), then Python itself, down to the interpreter, so the later chapters can say "the GIL" or "an epoll loop" without stopping to explain.

### [1. Computer Science Fundamentals](chapters/01-cs-fundamentals/README.md)

The bedrock of everything else. Data structures (arrays, hash tables, trees, graphs, bloom filters, skip lists), algorithm complexity analysis, sorting, dynamic programming, and string algorithms. Operating system internals: processes, threads, memory management, I/O models, file systems, and Linux fundamentals (cgroups, namespaces, systemd). Networking deep dive: TCP/IP, HTTP/1.1 → HTTP/2 → HTTP/3, DNS, TLS/SSL, and network debugging tools.

| Section | Deep Dive |
|---|---|
| 1.1 Data Structures | [data-structures.md](chapters/01-cs-fundamentals/data-structures.md) |
| 1.2 Algorithms & Complexity | [algorithms-and-complexity.md](chapters/01-cs-fundamentals/algorithms-and-complexity.md) |
| 1.3 Operating Systems | [operating-systems.md](chapters/01-cs-fundamentals/operating-systems.md) |
| 1.4 Networking | [networking.md](chapters/01-cs-fundamentals/networking.md) |

---

### [2. Python Deep Knowledge](chapters/02-python-deep-knowledge/README.md)

Beyond syntax into how Python actually works. Language internals (data model, GIL, CPython bytecode, memory management), async programming (asyncio, event loop, structured concurrency), advanced patterns (decorators, generators, type hints, dataclasses/enums, dates & money, strings & encoding, serialization, pattern matching), and the modern Python tooling ecosystem (logging, subprocess, packaging).

| Section | Deep Dive |
|---|---|
| 2.1 Language Internals | [language-internals.md](chapters/02-python-deep-knowledge/language-internals.md) |
| 2.2 Async Programming | [async-programming.md](chapters/02-python-deep-knowledge/async-programming.md) |
| 2.3 Advanced Patterns | [advanced-patterns.md](chapters/02-python-deep-knowledge/advanced-patterns.md) |
| 2.4 Packaging & Tooling | [packaging-and-tooling.md](chapters/02-python-deep-knowledge/packaging-and-tooling.md) |

---

## Part II: Designing the Backend (Chapters 3–5)

With the fundamentals in place, Part II turns to the decisions that shape a single service: the principles and patterns that keep a codebase changeable as it grows, the database where the hardest state lives, and the API surface through which everyone else consumes your work.

### [3. Software Architecture](chapters/03-software-architecture/README.md)

Principles and patterns that stand the test of time. SOLID, the Twelve-Factor App, coupling/cohesion & connascence, Clean and Hexagonal Architecture, and when to apply (or not apply) them. Creational, structural, behavioral, enterprise, and concurrency/reliability patterns (circuit breaker, bulkhead, saga, outbox) with practical Python context. Architectural styles: monolith, microservices, event-driven, serverless, and Domain-Driven Design.

| Section | Deep Dive |
|---|---|
| 3.1 Design Principles | [design-principles.md](chapters/03-software-architecture/design-principles.md) |
| 3.2 Design Patterns | [design-patterns.md](chapters/03-software-architecture/design-patterns.md) |
| 3.3 Architectural Styles | [architectural-styles.md](chapters/03-software-architecture/architectural-styles.md) |

---

### [4. Databases & Data](chapters/04-databases-and-data/README.md)

Everything about storing and querying data. PostgreSQL deep dive: storage internals (WAL, buffer pool, MVCC), query optimization, indexing strategies, transactions & isolation anomalies, partitioning, window functions, JSONB, full-text search. NoSQL & specialized: Redis, MongoDB, Cassandra/wide-column, graph and vector databases, Elasticsearch, OLTP vs OLAP/columnar. Data management: migrations, multi-tenancy, storing money & time, connection management, Kafka/CDC pipelines, and dimensional modeling.

| Section | Deep Dive |
|---|---|
| 4.1 Relational Databases (PostgreSQL) | [relational-databases.md](chapters/04-databases-and-data/relational-databases.md) |
| 4.2 NoSQL & Specialized | [nosql-and-specialized.md](chapters/04-databases-and-data/nosql-and-specialized.md) |
| 4.3 Data Management | [data-management.md](chapters/04-databases-and-data/data-management.md) |

---

### [5. API Design & Integration](chapters/05-api-design/README.md)

Building and consuming APIs the right way. RESTful API design (versioning, pagination, error handling, idempotency), GraphQL, gRPC, WebSocket/SSE, message queues (RabbitMQ, Kafka, Celery). Authentication (OAuth 2.0, JWT, sessions) and authorization (RBAC, ABAC, policy engines), plus passwordless auth with WebAuthn and passkeys.

| Section | Deep Dive |
|---|---|
| 5.1 RESTful APIs | [restful-apis.md](chapters/05-api-design/restful-apis.md) |
| 5.2 Beyond REST | [beyond-rest.md](chapters/05-api-design/beyond-rest.md) |
| 5.3 Authentication & Authorization | [authentication-and-authorization.md](chapters/05-api-design/authentication-and-authorization.md) |
| 5.4 WebAuthn & Passkeys | [webauthn-and-passkeys.md](chapters/05-api-design/webauthn-and-passkeys.md) |

---

## Part III: Systems at Scale (Chapters 6–7)

One well-designed service is not yet a system. Part III is about what changes when load and machine count grow: scaling and distributed systems with worked end-to-end designs, then the infrastructure -- containers, pipelines, observability -- that keeps it all running in production.

### [6. System Design](chapters/06-system-design/README.md)

Thinking at scale. Horizontal/vertical scaling, load balancing algorithms, caching strategies (cache-aside, write-through, stampede & hot-key handling), CAP/PACELC, quorums, and consistency models. Distributed systems: consensus (Raft), logical/vector clocks, distributed unique IDs, distributed locking, service communication patterns, circuit breakers. Real-world designs: URL shortener, rate limiter, chat, notifications, news feed, typeahead, geo/proximity, object storage, payments, and a Dynamo-style distributed cache.

| Section | Deep Dive |
|---|---|
| 6.1 Scalability | [scalability.md](chapters/06-system-design/scalability.md) |
| 6.2 Distributed Systems | [distributed-systems.md](chapters/06-system-design/distributed-systems.md) |
| 6.3 Real-World Examples | [real-world-examples.md](chapters/06-system-design/real-world-examples.md) |
| 6.4 Back-of-Envelope Estimation | [back-of-envelope.md](chapters/06-system-design/back-of-envelope.md) |
| 6.5 Caching & CDN Deep-Dive | [caching-and-cdn.md](chapters/06-system-design/caching-and-cdn.md) |

---

### [7. Infrastructure & DevOps](chapters/07-infrastructure-devops/README.md)

Running code in production. Docker (multi-stage builds, security, layer caching, registries, OCI runtime) and Kubernetes (pods, deployments, services, HPA/VPA/Cluster Autoscaler, scheduling, Helm, Kustomize, Operators, GitOps). CI/CD pipelines, deployment strategies (blue-green, canary, feature flags), Infrastructure as Code (Terraform/OpenTofu, Pulumi, immutable infra). Observability & operations: structured logging, Prometheus metrics, distributed tracing, error tracking/APM, on-call & runbooks, and FinOps.

| Section | Deep Dive |
|---|---|
| 7.1 Containerization | [containerization.md](chapters/07-infrastructure-devops/containerization.md) |
| 7.2 CI/CD & Deployment | [cicd-and-deployment.md](chapters/07-infrastructure-devops/cicd-and-deployment.md) |
| 7.3 Observability | [observability.md](chapters/07-infrastructure-devops/observability.md) |

---

## Part IV: Quality & Trust (Chapters 8–9)

A system that scales is still a liability if it leaks data or breaks on every deploy. Part IV covers defense -- application and infrastructure security, from the OWASP Top 10 to secrets and compliance -- and confidence: a testing strategy that catches each bug at the cheapest layer able to catch it.

### [8. Security](chapters/08-security/README.md)

Protecting your systems and data. OWASP Top 10 (injection, XSS, CSRF, SSRF, broken auth/access control), input validation, security headers, CORS. Cryptography fundamentals (password hashing, symmetric/asymmetric, HMAC, signatures, AEAD, key management). Infrastructure security: secrets management (Vault, AWS/GCP, workload identity), encryption, dependency scanning/SBOM, zero-trust, and compliance & privacy (GDPR/CCPA, PCI-DSS, SOC 2/ISO 27001).

| Section | Deep Dive |
|---|---|
| 8.1 Application Security | [application-security.md](chapters/08-security/application-security.md) |
| 8.2 Infrastructure Security | [infrastructure-security.md](chapters/08-security/infrastructure-security.md) |

---

### [9. Testing Strategy](chapters/09-testing-strategy/README.md)

Writing tests that actually catch bugs. The testing pyramid (and the trophy view): unit tests (AAA, property-based), integration & contract tests (testcontainers, test doubles, Pact, record-replay), performance testing (load, stress, soak, spike). Testing practices: F.I.R.S.T. principles, determinism (time/randomness), mutation testing, test data factories, and testing in production (canary, feature flags, shadow traffic, chaos engineering).

| Section | Deep Dive |
|---|---|
| 9.1 Testing Pyramid | [testing-pyramid.md](chapters/09-testing-strategy/testing-pyramid.md) |
| 9.2 Testing Practices | [testing-practices.md](chapters/09-testing-strategy/testing-practices.md) |

---

## Part V: From Engineer to Architect (Chapters 10–12)

The final part is about leverage beyond your own keyboard: the architect's habits of decision-making and system thinking, how the principles from the earlier parts surface in the framework you use every day (Django here, but the patterns are universal), and the communication and career skills that multiply everything else.

### [10. Senior / Architect Mindset](chapters/10-senior-architect-mindset/README.md)

How to think, not just what to know. Decision-making & trade-offs (ADRs, RFCs/design docs, one-way vs two-way doors, boring technology), technical debt management, code review excellence. System thinking: trade-off analysis, constraints-first, back-of-envelope estimation, incident management, and technology evaluation frameworks.

| Section | Deep Dive |
|---|---|
| 10.1 Technical Leadership | [technical-leadership.md](chapters/10-senior-architect-mindset/technical-leadership.md) |
| 10.2 System Thinking | [system-thinking.md](chapters/10-senior-architect-mindset/system-thinking.md) |

---

### [11. Django & Web Framework Knowledge](chapters/11-django-web-frameworks/README.md)

Framework-aware, principle-focused. Django specifics that transfer everywhere: request lifecycle, ORM patterns (Active Record vs Data Mapper), migrations, signals. Framework-agnostic patterns: middleware, request validation, background tasks, caching layers, rendering.

| Section | Deep Dive |
|---|---|
| 11.1 Django Specifics | [django-specifics.md](chapters/11-django-web-frameworks/django-specifics.md) |
| 11.2 Agnostic Patterns | [framework-agnostic-patterns.md](chapters/11-django-web-frameworks/framework-agnostic-patterns.md) |

---

### [12. Soft Skills & Career Growth](chapters/12-soft-skills-career/README.md)

The multiplier skills. Technical writing (RFCs, runbooks, ADRs), stakeholder communication, async written-first habits, collaboration & mentorship (psychological safety, reducing bus-factor). Career progression: influence & ownership, career ladders & scope, continuous learning, and what differentiates Mid from Senior from Architect.

| Section | Deep Dive |
|---|---|
| 12.1 Communication | [communication.md](chapters/12-soft-skills-career/communication.md) |
| 12.2 Career Progression | [career-progression.md](chapters/12-soft-skills-career/career-progression.md) |

---

## Homework

Each chapter ships with hands-on exercises and skeleton files (`hw_*.py`) to implement. Pick a chapter and start building.

| Chapter | Exercises |
|---|---|
| 1. CS Fundamentals | [questions.md](chapters/01-cs-fundamentals/homework/questions.md) |
| 2. Python Deep Knowledge | [questions.md](chapters/02-python-deep-knowledge/homework/questions.md) |
| 3. Software Architecture | [questions.md](chapters/03-software-architecture/homework/questions.md) |
| 4. Databases & Data | [questions.md](chapters/04-databases-and-data/homework/questions.md) |
| 5. API Design & Integration | [questions.md](chapters/05-api-design/homework/questions.md) |
| 6. System Design | [questions.md](chapters/06-system-design/homework/questions.md) |
| 7. Infrastructure & DevOps | [questions.md](chapters/07-infrastructure-devops/homework/questions.md) |
| 8. Security | [questions.md](chapters/08-security/homework/questions.md) |
| 9. Testing Strategy | [questions.md](chapters/09-testing-strategy/homework/questions.md) |
| 10. Senior / Architect Mindset | [questions.md](chapters/10-senior-architect-mindset/homework/questions.md) |
| 11. Django & Web Frameworks | [questions.md](chapters/11-django-web-frameworks/homework/questions.md) |
| 12. Soft Skills & Career | [questions.md](chapters/12-soft-skills-career/homework/questions.md) |

---

*This is a living document. Depth in any single topic could fill a book -- use this as a map of what to learn, not a substitute for deep study. Focus on principles over specific tools; frameworks change, fundamentals don't.*
