[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 12.1 Communication

Effective communication is arguably the single highest-leverage skill a backend engineer can develop. You may write flawless code, but if you cannot explain your design decisions, convey risk to stakeholders, or leave behind documentation that others can follow, the impact of your work shrinks dramatically. This section covers the concrete artifacts and practices that separate engineers who merely code from engineers who lead.

### Technical Writing

#### RFC / Design Document

An RFC (Request for Comments) or Design Document is the single most important written artifact an engineer produces outside of code itself. It forces you to think through a problem before writing a line of implementation, surfaces disagreements early when they are cheap to resolve, and creates a durable record of *why* a system was built the way it was.

A strong RFC contains these sections:

1. **Problem Statement** -- State the problem in terms your audience cares about. Quantify it. "Our checkout service times out under peak load" is vague. "P99 checkout latency exceeds 5 seconds when order volume surpasses 2,000 requests per minute, causing an estimated 12% cart abandonment increase during flash sales" gives people something concrete to evaluate.

2. **Proposed Solution** -- Describe the architecture, data flow, API contracts, and behavioral changes. Use diagrams. Be specific enough that another engineer could implement the solution from your document alone.

3. **Alternatives Considered** -- List at least two alternatives you evaluated and explain why you rejected them. This demonstrates rigor and pre-empts the most common review questions. A reviewer who was about to suggest "why not just use Redis?" will see that you already evaluated that path.

4. **Trade-offs** -- Every design has trade-offs. Call them out explicitly. Consistency vs. availability, complexity vs. flexibility, build vs. buy. Acknowledging trade-offs does not weaken your proposal; it strengthens it.

5. **Rollout Plan** -- How will you get from the current state to the proposed state without breaking production? Include migration strategy, feature flags, canary deployment percentages, and rollback triggers.

6. **Metrics for Success** -- Define measurable outcomes. "Improve performance" is not a metric. "Reduce P99 checkout latency from 5.2s to under 800ms at 3,000 RPM within 30 days of full rollout" is.

The most important practice: **circulate the RFC and collect feedback before writing implementation code.** A one-week review period that catches a fundamental flaw saves months of wasted work.

##### Complete RFC Template with Filled-In Example

```
=============================================================
RFC: Migrate Order Service from Synchronous to Async Processing
=============================================================

Author:       Jane Park (jane.park@company.com)
Status:       In Review
Created:      2026-03-10
Last Updated: 2026-03-18
Reviewers:    @backend-team, @platform-team, @product-checkout

-------------------------------------------------------------
1. Problem Statement
-------------------------------------------------------------

The Order Service currently processes all order submissions
synchronously. When a customer clicks "Place Order," the
request thread blocks while the service:

  (a) Validates inventory (calls Inventory Service, ~120ms P50)
  (b) Processes payment (calls Payment Gateway, ~800ms P50)
  (c) Reserves stock (writes to PostgreSQL, ~40ms P50)
  (d) Sends confirmation email (calls Email Service, ~200ms P50)

Total synchronous chain: ~1,160ms P50, ~5,200ms P99.

During flash sales (>2,000 RPM), the Tomcat thread pool
(max 200 threads) is fully saturated. Excess requests queue
and eventually time out (30s). Monitoring data from the
March 1 flash sale:

  - 14% of checkout attempts received HTTP 503
  - Estimated revenue loss: $48,000 in a 45-minute window
  - Three Severity-2 incidents filed in the last quarter

-------------------------------------------------------------
2. Proposed Solution
-------------------------------------------------------------

Decompose the synchronous chain into two phases:

Phase 1 -- Synchronous (customer-facing):
  - Validate inventory (optimistic check, read replica)
  - Accept the order, write to "orders" table with status
    PENDING, return HTTP 202 Accepted with order ID

Phase 2 -- Asynchronous (background):
  - Publish OrderCreated event to Kafka topic "order.events"
  - Payment Worker consumes event, calls Payment Gateway
    - On success: publish PaymentCompleted event
    - On failure: publish PaymentFailed event, notify user
  - Inventory Worker consumes PaymentCompleted, reserves stock
  - Notification Worker sends confirmation email

Architecture Diagram:

  [Client] --> [Order API] --> [PostgreSQL]
                    |
                    v
              [Kafka: order.events]
                /       |        \
               v        v         v
         [Payment   [Inventory  [Notification
          Worker]    Worker]     Worker]

API Contract Change:

  Before: POST /orders  --> 200 { order_id, status: "confirmed" }
  After:  POST /orders  --> 202 { order_id, status: "pending" }

  New:    GET /orders/{id}/status --> 200 { status: "pending"|
            "confirmed"|"failed" }

  New:    WebSocket /orders/{id}/updates (push status changes)

-------------------------------------------------------------
3. Alternatives Considered
-------------------------------------------------------------

Alternative A: Vertical scaling (increase thread pool, add
  more instances).
  Rejected because: Linear cost increase. Does not fix the
  fundamental coupling. Payment Gateway latency spikes would
  still cascade.

Alternative B: Reactive/non-blocking framework (Spring WebFlux).
  Rejected because: Requires rewriting the entire service.
  Team has limited reactive programming experience. Higher
  risk, longer timeline (~4 months vs. ~6 weeks).

Alternative C: Use RabbitMQ instead of Kafka.
  Viable, but Kafka is already operated by the platform team
  with established monitoring. Adding RabbitMQ introduces a
  new operational dependency.

-------------------------------------------------------------
4. Trade-offs
-------------------------------------------------------------

- Eventual consistency: The customer sees "pending" before
  payment is confirmed. Mitigated by WebSocket push updates
  (median confirmation time: <2s in staging tests).

- Operational complexity: Three new worker services to deploy
  and monitor. Mitigated by using the existing Kubernetes
  deployment pipeline and shared Helm charts.

- Failure modes: Kafka consumer lag could delay orders.
  Mitigated by consumer lag alerting (threshold: 1,000
  messages) and auto-scaling consumer group.

- Idempotency requirement: Workers must handle duplicate
  messages. Each worker will use an idempotency key
  (order_id + event_type) stored in Redis with 24h TTL.

-------------------------------------------------------------
5. Rollout Plan
-------------------------------------------------------------

Week 1-2: Implement async path behind feature flag
          (async_checkout_enabled, default: false).
Week 3:   Deploy to staging. Run load tests simulating
          5,000 RPM. Validate P99 < 500ms for Phase 1.
Week 4:   Enable for 5% of production traffic (canary).
          Monitor: error rate, consumer lag, payment
          success rate. Rollback trigger: error rate > 1%
          or consumer lag > 5,000 for > 5 minutes.
Week 5:   Ramp to 25%, then 50%, then 100% over 3 days
          if metrics remain healthy.
Week 6:   Remove synchronous code path. Clean up feature flag.

Rollback procedure: Disable feature flag. All traffic
returns to synchronous path instantly. No data migration
needed because the orders table schema is unchanged.

-------------------------------------------------------------
6. Metrics for Success
-------------------------------------------------------------

| Metric                         | Current     | Target       |
|--------------------------------|-------------|--------------|
| POST /orders P99 latency       | 5,200ms     | < 500ms      |
| HTTP 503 rate during peak      | 14%         | < 0.1%       |
| Order processing success rate  | 97.2%       | > 99.5%      |
| Time to order confirmation     | N/A (sync)  | < 5s P99     |
| Estimated revenue recovery     | -$48k/event | ~$0/event    |

Measurement window: 30 days after 100% rollout.

-------------------------------------------------------------
7. Open Questions
-------------------------------------------------------------

- Should we support a "fast path" that skips async for
  low-value orders (< $10)? Deferring to product review.
- Do we need a dead-letter queue strategy for permanently
  failed payments? Proposing DLQ with manual review dashboard.

-------------------------------------------------------------
8. References
-------------------------------------------------------------

- Incident report INC-2026-0142 (March 1 flash sale)
- Kafka operational runbook: /wiki/platform/kafka-runbook
- Payment Gateway SLA documentation: /wiki/vendor/payment-gw
```

#### README

A README is the front door of your project. When another engineer encounters your repository for the first time, the README determines whether they can get productive in minutes or waste hours guessing. A good README answers three questions immediately:

**What does this service do?** One to three sentences. Not a novel. "The Order Service accepts customer orders via REST API, coordinates payment processing, inventory reservation, and order fulfillment. It is the primary write path for the e-commerce checkout flow."

**How do I run it locally?** Step-by-step commands that a new team member can copy-paste on their first day. Include prerequisites (Java version, Docker, environment variables), the exact commands to build and start, and how to verify it is running (e.g., a health check URL).

**How do I contribute?** Branch naming conventions, test requirements, code review expectations, and deployment process.

The most common README failure mode is *staleness*. A README that describes the project as it existed six months ago is worse than no README, because it actively misleads. Treat README updates as part of your definition of done for any change that alters setup steps, dependencies, or core behavior.

#### Runbooks

A runbook is a step-by-step operational procedure designed to be followed under pressure -- often at 3 AM during an incident. The quality of your runbooks directly determines your team's mean time to recovery (MTTR).

A good runbook is written for the *least experienced on-call engineer* on your team. It assumes no prior context about the specific failure. It uses concrete commands, not vague instructions. "Check the database" is useless. "Run `SELECT count(*) FROM pg_stat_activity WHERE state = 'active';` and compare against the pool max of 100" is actionable.

Every runbook should include:

- **Title and scope**: What system and what failure mode this covers.
- **Symptoms**: What alerts fire, what the user experience looks like, what dashboards show.
- **Diagnosis steps**: Ordered sequence of checks to confirm the root cause.
- **Remediation steps**: Exact commands or actions to resolve the issue.
- **Escalation path**: When to escalate, and to whom.
- **Post-incident**: What to document and where.

Runbooks must be tested. An untested runbook will fail when you need it most. Schedule quarterly "runbook drills" where an engineer follows the runbook verbatim against a staging environment. Update the runbook based on where they get stuck.

##### Runbook Template with Example: Database Connection Pool Exhaustion

```
=============================================================
RUNBOOK: Database Connection Pool Exhaustion -- Order Service
=============================================================

Last tested: 2026-02-15
Owner: Backend Team (#backend-oncall in Slack)
Severity: SEV-2 (user-facing degradation)

-------------------------------------------------------------
1. Symptoms
-------------------------------------------------------------

ALERTS THAT FIRE:
  - "OrderService HikariCP active connections > 90%"
    (PagerDuty, routes to #backend-oncall)
  - "OrderService P99 latency > 3s"
  - "PostgreSQL active connections > 80% of max_connections"

USER-VISIBLE IMPACT:
  - Checkout requests return HTTP 503 or time out after 30s
  - Order confirmation page shows spinner indefinitely

DASHBOARD:
  - Grafana: https://grafana.internal/d/order-service-db
    Panel "HikariCP Pool Usage" shows active connections
    near or at maximum (currently configured: 50)

-------------------------------------------------------------
2. Diagnosis Steps
-------------------------------------------------------------

Step 1: Confirm connection pool saturation.

  Open Grafana dashboard above. Check panel "HikariCP Pool
  Usage." If active connections equals maximum pool size (50)
  AND pending connection requests are increasing, pool
  exhaustion is confirmed.

Step 2: Check for long-running queries.

  Connect to the read replica (to avoid adding load):

    psql -h db-replica.internal -U oncall -d orders

  Run:

    SELECT pid, now() - query_start AS duration, state, query
    FROM pg_stat_activity
    WHERE datname = 'orders'
      AND state != 'idle'
    ORDER BY duration DESC
    LIMIT 20;

  Look for queries running longer than 30 seconds. Common
  culprits:
    - Full table scans on the "order_items" table (missing
      index on order_id after a recent migration)
    - Lock contention from batch updates to the "inventory"
      table

Step 3: Check for connection leaks.

  In Kibana (https://kibana.internal), search for:

    service:order-service AND "connection is not available"

  If you see "Connection is not available, request timed out
  after 30000ms" errors increasing, this confirms the pool
  is exhausted faster than connections are returned.

  Check application logs for stack traces around unreturned
  connections:

    kubectl logs -l app=order-service --since=15m | \
      grep -A 5 "HikariPool-1 - Connection leak detection"

Step 4: Check if the database itself is the bottleneck.

    SELECT count(*) FROM pg_stat_activity;

  Compare against max_connections (currently 200). If total
  connections across all services approach 200, the problem
  may be database-wide, not specific to Order Service.

-------------------------------------------------------------
3. Remediation Steps
-------------------------------------------------------------

OPTION A: Kill long-running queries (if found in Step 2).

  For each problematic PID:

    SELECT pg_terminate_backend(<pid>);

  This immediately frees the connection. Verify pool usage
  drops on the Grafana dashboard within 60 seconds.

OPTION B: Restart Order Service pods (if connection leak
  suspected).

    kubectl rollout restart deployment/order-service \
      -n production

  This cycles pods gracefully (rolling restart). Monitor
  during restart:
    - Ensure at least 2 of 4 pods remain healthy at all times
    - Watch HikariCP pool usage reset to baseline (~10 active)

OPTION C: Temporarily increase pool size (buys time for
  root cause analysis).

  Update ConfigMap:

    kubectl edit configmap order-service-config -n production

  Change:
    HIKARI_MAXIMUM_POOL_SIZE: "50"  -->  "75"

  Then restart pods (Option B). WARNING: Ensure total
  connections across all services will not exceed PostgreSQL
  max_connections (200). Current allocation:
    - Order Service: 50 x 4 pods = 200 (already at limit!)
    - Do NOT increase without also increasing max_connections.

OPTION D: Enable query timeout as a circuit breaker.

  If queries are running indefinitely due to lock contention:

    ALTER DATABASE orders SET statement_timeout = '30s';

  This will kill any query exceeding 30 seconds. Remove this
  setting after the incident:

    ALTER DATABASE orders RESET statement_timeout;

-------------------------------------------------------------
4. Escalation
-------------------------------------------------------------

Escalate to SEV-1 if:
  - Remediation steps do not reduce pool usage within 15 min
  - Multiple services are affected (database-wide issue)
  - Data corruption is suspected (e.g., partial writes)

Escalation contacts:
  - Database team: #dba-oncall in Slack, PagerDuty "DBA Primary"
  - Order Service tech lead: Jane Park (phone in PagerDuty)

-------------------------------------------------------------
5. Post-Incident
-------------------------------------------------------------

  - File an incident report in /wiki/incidents/
  - Update this runbook if any steps were inaccurate
  - If root cause was a missing index or schema issue, file
    a ticket for the next sprint
  - Review connection pool configuration as part of quarterly
    capacity planning
```

The single highest-value command in that runbook is the Step 2 query against `pg_stat_activity`. At 3 AM, the on-call engineer who runs it sees something like (PIDs, durations, and SQL text vary by incident):

```text
  pid  |    duration     | state  |                         query
-------+-----------------+--------+--------------------------------------------------------
 18244 | 00:04:12.882190 | active | UPDATE inventory SET reserved = reserved + $1 WHERE ...
 18102 | 00:03:58.114007 | active | SELECT * FROM order_items WHERE order_id = $1
 17995 | 00:03:51.770233 | active | SELECT * FROM order_items WHERE order_id = $1
 18301 | 00:00:00.004118 | active | SELECT pid, now() - query_start AS duration, state, ...
(4 rows)
```

**How to read this output:** Sort by `duration` descending and the culprit jumps out. Here, one `UPDATE inventory` has been holding a row lock for over four minutes, and behind it several `SELECT * FROM order_items` queries are piling up because they are blocked or doing full table scans — each one holding a connection from the pool the whole time. That is exactly how pool exhaustion happens: it is rarely "too much traffic," it is a handful of slow queries each pinning a connection. The last row (a few milliseconds) is your own diagnostic query, which you ignore. In an incident this single screen tells you which `pid` to feed into `pg_terminate_backend()` (Remediation Option A) and whether the root cause is lock contention or a missing index — the difference between a 60-second fix and a follow-up schema ticket.

> **Common pitfall:** `pg_terminate_backend()` frees the connection immediately, but if the underlying cause is a missing index or an unbounded query, the next request simply re-creates the same long-running query and you are back where you started within minutes. Killing queries buys time; it is not the fix. Always pair Option A with `statement_timeout` (Option D) or the schema fix so the problem cannot silently recur.

#### ADRs (Architecture Decision Records)

An ADR is a short document that captures a single architectural decision: the context, the decision itself, and the consequences. Unlike an RFC, which is written *before* a decision is made to solicit feedback, an ADR is written *after* the decision to record it for posterity.

ADRs solve a specific and painful problem: six months from now, someone (possibly you) will look at a piece of the system and ask "why on earth did we do it this way?" Without an ADR, the answer lives only in the memories of people who may have left the company.

Keep ADRs lightweight. A good ADR is one page. Use a consistent format:

- **Title**: A short noun phrase. "Use Kafka for inter-service events."
- **Status**: Proposed, Accepted, Deprecated, Superseded.
- **Context**: What forces are at play? What constraints exist?
- **Decision**: What did we decide? State it plainly.
- **Consequences**: What becomes easier? What becomes harder? What risks did we accept?

Store ADRs in version control alongside the code they describe (e.g., `docs/adr/0012-use-kafka-for-events.md`). This ensures they are versioned, searchable, and discoverable by anyone reading the repository.

> **Key Takeaway -- Technical Writing**: The documents you write (RFCs, READMEs, runbooks, ADRs) are force multipliers. A well-written RFC prevents weeks of wasted implementation. A good runbook shaves hours off incident recovery. A clear ADR prevents the same architectural debate from recurring every quarter. Invest in your writing the same way you invest in your code: draft, review, revise, and maintain.

### Stakeholder Communication

#### Translating Technical Concepts to Business Impact

The most common communication failure among backend engineers is describing *what* they are doing in technical terms without connecting it to *why it matters* to the business. Your engineering manager, product manager, and executive sponsors do not need to understand connection pooling or Kafka consumer groups. They need to understand risk, cost, timeline, and user impact.

The translation formula is: **Technical change --> User/Business effect --> Quantified impact.**

Here are concrete before-and-after examples:

**Example 1: Database Migration**

- BEFORE (technical-only): "We need to run a PostgreSQL migration to add partitioning to the orders table and backfill data. This requires taking a maintenance window."
- AFTER (business-aware): "We need 30 minutes of read-only mode for the checkout system next Tuesday at 2 AM ET. During this window, customers can browse and view their order history, but cannot place new orders. This one-time maintenance will reduce our database query times by roughly 60%, which means faster checkout page loads for customers and positions us to handle the projected 3x order volume during the holiday season without additional database hardware costs (estimated savings: $24,000/year)."

**Example 2: Technical Debt**

- BEFORE: "We need to refactor the payment module. The code is spaghetti and it is really hard to add new payment providers."
- AFTER: "Adding a new payment provider currently takes 6-8 weeks of engineering time because the payment code was not designed for extensibility. Our competitor launched Apple Pay last month. If we refactor the payment module first (3 weeks), every subsequent payment provider integration drops to 1-2 weeks. This means we can launch Apple Pay, Google Pay, and Klarna within the next quarter instead of only completing one."

**Example 3: Infrastructure Cost**

- BEFORE: "We should migrate from EC2 to Kubernetes. It is more modern and gives us better orchestration."
- AFTER: "Our current infrastructure costs $18,000/month and requires manual scaling that takes 20-30 minutes during traffic spikes. During those 20-30 minutes, roughly 8% of users experience errors. Migrating to Kubernetes enables auto-scaling that responds in under 2 minutes, reducing user-facing errors during spikes to near zero. The migration will also reduce our monthly infrastructure bill to approximately $12,000 through more efficient resource utilization. The migration takes 8 weeks and has no user-facing downtime."

**Example 4: Security Vulnerability**

- BEFORE: "We have a critical CVE in our log4j dependency and need to patch immediately."
- AFTER: "A security vulnerability was publicly disclosed that affects our order processing system. If exploited, an attacker could gain access to our production servers and potentially customer data. The industry-wide severity rating is 10 out of 10. We need to deploy a patch within 24 hours. The patch itself is low-risk (a library version update) and requires no downtime. Delaying exposes us to regulatory penalties under our data protection obligations and potential breach notification requirements."

#### Estimating Honestly

Engineers face constant pressure to give optimistic estimates. Resist this. An honest estimate protects both you and your stakeholders. When an estimate slips, trust erodes -- and trust is the foundation of your professional reputation.

Use **ranges** rather than point estimates. A range communicates your uncertainty, which is itself valuable information. "2-4 weeks" tells your manager that there are unknowns you have not yet resolved. "3 weeks" implies a false precision that will be held against you when it takes 4.

When constructing an estimate, break the work into tasks, estimate each task independently, and then add contingency:

- Sum of individual task estimates: your base case.
- Add 20-30% for integration work, unexpected issues, and code review cycles.
- If you are working with an unfamiliar technology or a poorly documented legacy system, add another 20-30%.

Communicate your assumptions. "This estimate assumes the Payment Gateway API documentation is accurate and we will not need to reverse-engineer their behavior" tells your stakeholder exactly what could cause a delay.

> **Common pitfall:** Do not bury your contingency inside a single padded point estimate (quietly turning a 3-week base case into "5 weeks" and presenting only "5 weeks"). When the work finishes early, you look like you sandbagged; when it slips anyway, the hidden buffer is already spent and you have nothing left to absorb the surprise. State the base case, the contingency, and the assumptions separately so stakeholders can see your reasoning and renegotiate scope rather than just the number.

#### Saying No Constructively

"No" is one of the most important words in an engineer's vocabulary, but it must be delivered with alternatives and reasoning, not as a blunt refusal.

The framework: **Acknowledge --> Explain the trade-off --> Offer alternatives.**

- BAD: "No, we cannot do that in two weeks."
- GOOD: "I understand the urgency of launching before the competitor. If we scope it to just credit card payments and defer Apple Pay to a follow-up release, we can ship a solid solution in two weeks. The full scope including Apple Pay would take four to five weeks. Which approach fits your priorities better?"

This approach shows that you are aligned with the business goal (launching quickly), you understand the constraints, and you are offering a path forward rather than a roadblock.

> **Key Takeaway -- Stakeholder Communication**: Your ability to influence decisions is directly proportional to your ability to communicate in terms your audience cares about. Executives care about revenue, risk, and timeline. Product managers care about user experience and competitive position. Translate accordingly. An engineer who can say "this refactoring will save us $80,000 in engineering time over the next year" will get that refactoring approved. An engineer who says "the code is messy and hard to work with" will not.

---
