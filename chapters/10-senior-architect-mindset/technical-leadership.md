[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 10.1 Technical Leadership

The previous chapters of this book have been about technical depth: data modeling, distributed systems, performance, security, testing. With this chapter we change register. Past a certain level of seniority, your impact is no longer measured chiefly by the code you write but by the decisions you shape, the documents you circulate, and the reviews you give -- artifacts of influence that outlive any single codebase. A well-reasoned decision record is still useful five years after the engineer who wrote it has left; a healthy review culture keeps catching defects long after any individual fix is forgotten. Technical leadership is the discipline of producing those durable artifacts deliberately rather than by accident.

By the end of this section you should be able to answer a set of practical questions. Which decisions deserve a written record, and what must that record capture for it to be worth keeping? How do you circulate a design so that objections surface while they are still cheap to address? How do you make technical debt visible -- and negotiable -- to people who do not read code? And what separates a code review that catches real defects from one that litigates style?

We proceed in roughly the order these practices appear in a decision's life. We start with Architecture Decision Records, the durable "minutes" of an architectural choice. We then step back to the RFC / design-doc process that produces those decisions in the first place. From deliberate decisions we turn to the undeliberate ones: technical debt management, including how to classify debt, quantify it in business terms, and decide between refactoring and rewriting. Finally we close with code review excellence, the daily practice through which all of these standards are actually enforced.

## Architecture Decision Records (ADR)

Of all the artifacts a technical leader produces, the decision record is the simplest and the most durable, so it is where we begin.

An Architecture Decision Record is a short document that captures a single significant architectural decision along with its full context. The most important aspect of an ADR is that it records **why** a decision was made, not merely what was decided. Teams that only document the "what" find themselves relitigating the same debates months later because nobody remembers the constraints, trade-offs, and reasoning that shaped the original choice.

A well-written ADR includes three core sections. The **Context** section describes the problem, the forces at play (technical constraints, team capabilities, deadlines, regulatory requirements), and any relevant background. The **Decision** section states clearly what was chosen and, briefly, what alternatives were considered and rejected. The **Consequences** section is perhaps the most valuable: it captures both the positive outcomes and the trade-offs, risks, and potential downsides that the team knowingly accepted.

ADRs prevent re-litigation of old decisions. When a new engineer joins the team and asks "why are we using Kafka instead of RabbitMQ?", the answer is a link to an ADR rather than a 30-minute meeting that pulls three senior engineers off their work. ADRs should be lightweight -- roughly one page per decision -- and stored alongside the code in version control so they evolve with the project.

ADRs should be written for decisions that are architecturally significant: choices that affect the structure of the system, are difficult to reverse, or have long-term implications. You do not need an ADR for choosing a logging library, but you absolutely need one for choosing your primary database, your inter-service communication pattern, or your authentication strategy.

### Complete ADR Template Example

Below is a filled-in ADR for a realistic scenario: choosing a message broker for an event-driven microservices platform.

```
# ADR-0042: Choosing Apache Kafka as the Primary Message Broker

## Date
2025-11-15

## Status
Accepted

## Context

Our platform is transitioning from a synchronous REST-based architecture to an
event-driven microservices architecture. We need a message broker that will serve
as the backbone for inter-service communication.

Key requirements:
- Handle 50,000+ events per second at peak load (current peak is 12,000/s,
  projected to grow 4x in 18 months based on business roadmap).
- Guarantee at-least-once delivery for critical business events (order placement,
  payment processing, inventory updates).
- Support event replay capability so new consumers can reprocess historical events
  when onboarding new services.
- Retain messages for at least 7 days for debugging, auditing, and reprocessing.
- Operate within our existing Kubernetes-based infrastructure on AWS.

Team context:
- Two of eight backend engineers have production experience with Kafka.
- No team members have production experience with Pulsar.
- Five engineers have used RabbitMQ in previous projects.

Constraints:
- Budget ceiling of $3,000/month for infrastructure costs related to messaging.
- Must be in production within 3 months.
- Must support our primary languages: Java (Spring Boot) and Python.

## Options Considered

### Option A: Apache Kafka (Confluent Platform, self-managed on EKS)
- Excellent throughput (millions of messages/second).
- Native event replay via log-based retention.
- Mature ecosystem (Kafka Streams, Kafka Connect, Schema Registry).
- Operational complexity: requires ZooKeeper (or KRaft for newer versions),
  careful partition management, and tuning.

### Option B: RabbitMQ
- Simpler to operate and more familiar to the team.
- Traditional message queue model; does not natively support event replay.
- Lower throughput ceiling under high-volume scenarios.
- Excellent for task queues and RPC patterns, less suited for event streaming.

### Option C: Amazon MSK (Managed Kafka)
- Reduces operational burden compared to self-managed Kafka.
- Higher cost ($1,800-2,500/month for a minimal production cluster).
- Less control over configuration and version upgrades.

### Option D: Apache Pulsar
- Strong replay and multi-tenancy features.
- Smaller community and ecosystem compared to Kafka.
- No team experience; steep learning curve.

## Decision

We will adopt **Apache Kafka (self-managed on EKS using Strimzi operator)** as
our primary message broker.

Rationale:
1. Kafka's log-based architecture natively supports event replay, which is a
   hard requirement for our use case.
2. Throughput benchmarks show Kafka handles our projected peak (50K events/sec)
   with significant headroom on a 3-broker cluster.
3. The Strimzi Kubernetes operator simplifies deployment, scaling, and monitoring
   within our existing EKS infrastructure.
4. Two team members have production Kafka experience and will lead the rollout
   and train others.
5. Estimated infrastructure cost: $1,200/month (3x m5.xlarge instances), well
   within budget.

We chose self-managed over Amazon MSK because MSK's cost is nearly double for
our cluster size, and Strimzi gives us full control over version and config.

We chose Kafka over RabbitMQ because RabbitMQ does not support native event
replay without bolting on additional infrastructure (e.g., storing events in a
separate database), which defeats the purpose.

## Consequences

### Positive
- Native event replay allows new services to bootstrap from historical events.
- Kafka's partitioning model enables horizontal scaling of consumers.
- Rich connector ecosystem (Kafka Connect) simplifies integration with databases,
  S3, Elasticsearch.
- Strong schema evolution support via Confluent Schema Registry (Avro/Protobuf).

### Negative / Risks
- Operational complexity is higher than RabbitMQ. Mitigation: Strimzi operator
  handles most operational tasks; we will invest 2 weeks in team training.
- Learning curve for five team members unfamiliar with Kafka. Mitigation: pair
  programming sessions, internal Kafka workshop, and a shared runbook.
- Kafka is not ideal for low-latency RPC-style messaging. Mitigation: we will
  keep synchronous REST/gRPC for request-response patterns and use Kafka only
  for event streaming.
- Risk of partition skew if keys are not chosen carefully. Mitigation: establish
  partitioning guidelines in our development standards.

### Follow-Up Actions
- [ ] Set up 3-broker Kafka cluster in staging (Owner: Platform Team, Due: Dec 1)
- [ ] Conduct team Kafka workshop (Owner: Alice, Due: Dec 8)
- [ ] Migrate Order Events as pilot use case (Owner: Orders Team, Due: Jan 15)
- [ ] Establish monitoring dashboards for lag, throughput, and errors (Owner: SRE, Due: Dec 15)
- [ ] Revisit this decision in 6 months to evaluate operational experience (Owner: Tech Lead, Due: May 2026)
```

> **Common pitfall:** Never edit or delete an accepted ADR to reflect a later change of mind. ADRs are append-only. When a decision is reversed, write a *new* ADR (e.g. ADR-0061) that sets the old one's `Status` to `Superseded by ADR-0061` and explains what changed. The historical record of *why you once chose Kafka* is exactly the context that prevents the team from re-walking the same path two years later -- destroying it defeats the entire purpose.

> **Key Takeaway:** ADRs are not bureaucracy -- they are institutional memory. The cost of writing one is 30 minutes. The cost of not having one is repeated meetings, reversed decisions, and frustrated teams. Start writing ADRs today, even for decisions already made. Retroactive ADRs that capture "why we are where we are" are immensely valuable for onboarding and future planning.

---

## RFC / Design-Doc Process

An ADR records a decision *after* it has been reasoned through. A design doc (often called an RFC -- "Request for Comments" -- borrowing the term from the internet standards process) is the artifact that gets you *to* that decision. The core discipline is simple and counterintuitive to engineers who like to code: **write the design before you build anything non-trivial, and circulate it for feedback before you write production code.** The whole point is to surface objections, missing requirements, and better alternatives while they are still cheap to fix -- a paragraph rewritten in a doc costs minutes; the same flaw discovered after three weeks of implementation costs a sprint.

A design doc is not the same as an ADR, though they are complementary. The design doc is a *proposal under discussion*; it is broader, exploratory, and explicitly invites disagreement. Once the discussion converges, the resulting commitments are distilled into one or more ADRs (the durable "we decided X because Y"). Think of the RFC as the conversation and the ADR as the minutes.

A useful design doc answers, in roughly this order:

- **Problem / motivation** -- What are we trying to solve, and why now? Who is affected if we do nothing?
- **Goals and non-goals** -- An explicit non-goals list is one of the highest-value sections; it prevents scope creep and tells reviewers what *not* to comment on.
- **Requirements and constraints** -- Functional and non-functional requirements (latency, throughput, consistency, compliance, budget, deadline). State the constraints up front so the design is evaluated against them.
- **Proposed design** -- The actual approach: data model, APIs, component diagram, key flows, and how it handles failure.
- **Alternatives considered** -- The options you rejected and *why*. Reviewers often probe exactly here, so doing this honestly earns trust and pre-empts the "did you consider X?" comments.
- **Risks, rollout, and open questions** -- Migration plan, backward compatibility, observability, and the questions you genuinely want feedback on.

The process matters as much as the template. Set a clear review window (e.g. "comments by Friday"), tag the specific reviewers whose sign-off you need rather than spraying it to a 50-person channel, and resolve comments in the doc itself so the reasoning is preserved. A design doc that nobody reads is theater; gate it behind a lightweight norm such as "any change estimated at more than ~1 week, or touching a public API or data model, needs a one-page design doc and at least two approvals before implementation starts." Smaller changes should *not* require a doc -- forcing RFCs on trivial work teaches people to route around the process.

The most common failure mode is writing the doc *after* the code is already written, to satisfy a checkbox. At that point the author is psychologically committed to their implementation and the doc becomes a defense rather than an inquiry; reviewers can feel it and stop engaging. Write it first, when changing your mind is still cheap.

> **Key Takeaway:** The design doc is where you change your mind cheaply. Code is expensive to write and even more expensive to throw away, so move the disagreement upstream into prose where rewriting a paragraph is free. A good RFC culture trades a day of writing and review for weeks of avoided rework and surfaces the objection that would otherwise have shown up in production.

---

## Technical Debt Management

ADRs and design docs govern the decisions a team makes deliberately. But every system also carries the residue of decisions made under deadline pressure, with incomplete knowledge, or without anyone noticing a decision was being made at all. Managing that residue -- consciously, visibly, and in language the business understands -- is the third leadership discipline.

Technical debt is the implied cost of future rework caused by choosing an expedient solution now instead of a better approach that would take longer. Like financial debt, technical debt is not inherently bad -- sometimes borrowing is the right business decision -- but unmanaged debt compounds and eventually cripples a team's ability to deliver.

### The Tech Debt Quadrant

Martin Fowler's Technical Debt Quadrant classifies debt along two axes: **reckless vs. prudent** and **deliberate vs. inadvertent**. Understanding which quadrant a piece of debt falls into helps you decide how to address it.

```
                    Deliberate                        Inadvertent
            +------------------------------+------------------------------+
            |                              |                              |
            |  "We don't have time for     |  "What's layering?"          |
            |   design."                   |                              |
            |                              |  The team didn't know        |
  Reckless  |  The team knew better but    |  enough to recognize they    |
            |  chose to cut corners with   |  were making a mess. Often   |
            |  no plan to revisit. This    |  caused by lack of skills    |
            |  debt is dangerous because   |  or experience. Address by   |
            |  it accumulates silently.    |  investing in training and   |
            |                              |  code reviews.               |
            |  ACTION: Stop doing this.    |  ACTION: Train the team.     |
            |  Institute code reviews and  |  Pair junior devs with       |
            |  minimum quality gates.      |  senior engineers.           |
            |                              |                              |
            +------------------------------+------------------------------+
            |                              |                              |
            |  "Ship now, refactor later." |  "Now we know how we         |
            |                              |   should have done it."      |
            |  A conscious decision to     |                              |
  Prudent   |  take on debt with a clear   |  The team did the best they  |
            |  understanding of the cost   |  could with the knowledge    |
            |  and a plan to pay it back.  |  they had at the time.       |
            |  This is sometimes the       |  Learning reveals a better   |
            |  RIGHT business call.        |  approach. This is natural   |
            |                              |  and healthy.                |
            |  ACTION: Track it. Schedule  |  ACTION: Refactor when the   |
            |  repayment. Set a deadline.  |  area is next touched.       |
            |                              |  Boy Scout Rule.             |
            |                              |                              |
            +------------------------------+------------------------------+
```

### Quantifying Impact

Technical debt must be communicated in business terms, not engineering jargon. Telling leadership "our code is messy" achieves nothing. Instead, quantify the impact using metrics that business stakeholders care about:

- **Developer velocity**: Track how long features take to ship. If a feature that "should" take 3 days consistently takes 2 weeks because engineers spend 80% of their time navigating tangled code or working around fragile systems, that is a measurable cost. Compare velocity trends over quarters.
- **Incident frequency**: Count production incidents per month and attribute them to root causes. If 60% of your SEV2 incidents trace back to the same legacy subsystem, you have a quantifiable argument for investment. Calculate the cost: (number of incidents) x (average engineer-hours per incident) x (average hourly cost).
- **Onboarding time**: Measure how long it takes a new engineer to make their first meaningful contribution. If onboarding takes 3 months instead of 3 weeks because the codebase is incomprehensible, that is a direct hiring cost multiplier.
- **Feature delivery time**: Track cycle time from "work started" to "in production." Increasing cycle times often correlate with accumulating debt.

Present a concrete case: "Our payment service has accumulated significant debt. In the last quarter, it caused 14 production incidents (42 engineer-hours of incident response), slowed feature delivery by an estimated 35%, and took our newest hire 8 weeks to become productive in. Investing 4 weeks of a 3-person team to refactor the core payment pipeline would reduce incident rate by an estimated 60% and improve feature velocity by 25%, paying for itself within 2 quarters."

### Strategies for Managing Debt

**The Boy Scout Rule** -- "Leave the code better than you found it." When an engineer touches a file to implement a feature, they make one small improvement: rename an unclear variable, extract a method, add a missing test, update a stale comment. No single change is large enough to be risky, but the cumulative effect over weeks and months is substantial. This works best for Prudent/Inadvertent debt.

**Dedicated debt sprints** -- Reserve one sprint every 4-6 sprints entirely for debt reduction. The advantage is focused, uninterrupted time to tackle larger refactoring efforts. The disadvantage is that feature delivery pauses, which can be politically difficult.

**Debt tax (20% of sprint capacity)** -- Allocate a fixed percentage of every sprint's capacity to debt work. This is often the most sustainable approach because it provides consistent, predictable investment without requiring special approval. Engineers pick items from the tech debt backlog each sprint. The 20% figure is a starting point; adjust based on how much debt you carry.

**Tech debt backlog** -- Maintain a separate, prioritized backlog of debt items. Each item should describe the debt, its impact (using the quantification metrics above), the proposed fix, and the estimated effort. Review this backlog monthly and ensure the highest-impact items are being addressed.

> **Common pitfall:** The 20% debt tax and the dedicated debt sprint both quietly collapse under deadline pressure -- the first feature emergency "borrows" the debt capacity, and it never comes back. If debt work isn't a tracked, sized item on the *same* board as feature work (with the same definition of done), it is invisible to planning and will always lose the prioritization fight. Protect the allocation by making it explicit and reporting on it, not by relying on goodwill.

### When to Rewrite vs. Refactor

Rewriting a system from scratch is almost always more expensive and risky than teams anticipate. Joel Spolsky famously called it "the single worst strategic mistake that any software company can make." Rewriting is appropriate **only** when all three conditions are met:

1. The current architecture **fundamentally** cannot support the requirements (not "it's messy" but "it physically cannot scale to the needed level" or "the core data model is wrong in ways that can't be migrated incrementally").
2. The team **deeply understands the domain** and the existing system's behavior, including its undocumented edge cases and implicit business rules. If you do not understand the old system thoroughly, you will recreate its bugs and miss its hidden features.
3. There is clear **business justification** with executive sponsorship, because a rewrite will slow feature delivery for months and carries significant risk of failure.

In all other cases, prefer incremental refactoring using techniques like the Strangler Fig pattern (gradually replacing components behind a facade), Branch by Abstraction (introducing an abstraction layer, building the new implementation behind it, then switching), or parallel running (running old and new systems side by side and comparing outputs).

> **Key Takeaway:** Technical debt is a tool, not a sin. The goal is not zero debt -- it is conscious, tracked, and managed debt. The most damaging debt is the debt you do not know you have. Make debt visible, quantify its cost in business terms, and pay it down systematically.

---

## Code Review Excellence

Decision records, design docs, and a debt backlog operate on the scale of weeks and quarters. The instrument of technical leadership that operates daily -- and through which all the standards above are actually enforced or quietly eroded -- is the code review.

Code review is one of the highest-leverage activities in software engineering. Studies consistently show that code review catches 60-90% of defects before they reach production, which is a higher defect detection rate than most testing strategies. Beyond defect detection, code reviews spread knowledge across the team, enforce consistency, mentor junior engineers, and create a shared sense of ownership.

### What to Review

**Correctness** -- Does the code actually do what it claims to do? Walk through the logic mentally or on paper. Check edge cases: what happens with empty inputs, null values, maximum-size collections, concurrent access? Verify that error handling is complete -- not just the happy path.

**Design** -- Is the code well-structured? Does it follow established patterns in the codebase? Is responsibility clearly separated? Are abstractions at the right level (not too abstract, not too concrete)? Does it introduce unnecessary coupling between modules? Would you be comfortable maintaining this code a year from now?

**Readability** -- Can another engineer understand this code without asking the author for an explanation? Are names descriptive and precise? Is the control flow straightforward or does it require mental gymnastics to follow? Are complex sections documented with comments that explain "why," not "what"?

**Testability** -- Is the code accompanied by appropriate tests? Are the tests meaningful (not just asserting that the code runs, but verifying behavior)? Can the code be tested in isolation, or does it have hard dependencies on databases, network services, or global state?

**Security** -- Is user input validated and sanitized? Are SQL queries parameterized? Are secrets kept out of code and logs? Are authorization checks in place? Is sensitive data encrypted in transit and at rest? Are dependencies up to date and free of known vulnerabilities?

**Performance** -- Are there obvious performance problems: N+1 queries, unbounded loops, loading entire datasets into memory, missing database indexes for queried columns? Is the code making unnecessary network calls or disk reads?

Importantly, **style and formatting should be automated**, not argued about in reviews. Use linters (ESLint, Pylint, Checkstyle), formatters (Prettier, Black, google-java-format), and pre-commit hooks. Every minute spent debating tabs versus spaces in a code review is a minute not spent catching real bugs.

### Giving Constructive Feedback

The way feedback is delivered matters as much as the feedback itself. Code review is a social process, and poorly delivered feedback can damage trust, discourage contribution, and create adversarial relationships.

**Explain why**, not just what. "This should be a separate function" is less useful than "Extracting this into a separate function would let us test the validation logic independently and reuse it in the batch processing endpoint that has the same rules."

**Suggest alternatives** rather than just pointing out problems. "This approach will have performance issues with large datasets" becomes actionable when followed by "Consider using a streaming approach with pagination, similar to how we handle it in OrderExportService."

**Ask questions rather than dictate.** "Have you considered using a builder pattern here?" invites discussion. "Use a builder pattern here" shuts it down. The author may have a good reason for their approach that you have not considered.

**Praise good code.** When you see a clever solution, a well-written test, or a thoughtful comment, say so. Positive reinforcement is a powerful teaching tool and makes the review process more collaborative.

**Distinguish severity levels.** Not all feedback is equally important. Use prefixes like "nit:" for minor style suggestions, "suggestion:" for non-blocking improvements, and "blocker:" for issues that must be addressed before merging. This helps authors prioritize their response.

### Review Size

Research from SmartBear's study of Cisco's code review practices shows that review effectiveness drops dramatically after about 400 lines of meaningful changes (excluding generated code, test fixtures, and configuration). Beyond that threshold, reviewers begin to skim and miss defects.

Break large changes into stacked PRs (also called PR chains or dependent PRs). Each PR in the stack should be a logically coherent unit: one PR introduces the database migration, the next adds the repository layer, the next adds the service logic, and the last adds the API endpoint. Each PR is small enough to review thoroughly, and the stack tells a clear narrative of the overall change.

### Code Review Checklist Example

The following checklist can be adapted and used by reviewers on your team. Not every item applies to every PR -- use judgment.

```
CODE REVIEW CHECKLIST
=====================

PR: ____________________  Author: ________________  Reviewer: ________________
Date: __________________  Size: ___ lines changed

CORRECTNESS
[ ] Logic is correct and handles edge cases (nulls, empty collections, boundary values)
[ ] Error handling is complete (failures are caught, logged, and surfaced appropriately)
[ ] Concurrency is handled correctly (no race conditions, proper use of locks/atomics)
[ ] Database transactions have appropriate isolation levels and rollback handling
[ ] External API calls have timeouts, retries with backoff, and circuit breakers where appropriate

DESIGN
[ ] Code follows established patterns and conventions in this codebase
[ ] Single Responsibility: each class/function does one thing well
[ ] Dependencies flow in the right direction (no circular dependencies, no upward layer violations)
[ ] No unnecessary coupling introduced between modules or services
[ ] Public API surface is minimal and well-designed (no leaky abstractions)

READABILITY
[ ] Names are descriptive and follow project naming conventions
[ ] Complex logic is commented with "why" explanations
[ ] No dead code, commented-out code, or TODO items without tracking tickets
[ ] Functions are short enough to understand at a glance (<30 lines as a guideline)

TESTING
[ ] New logic is covered by unit tests
[ ] Edge cases and error paths are tested, not just the happy path
[ ] Tests are independent (no shared mutable state, no order dependency)
[ ] Integration tests cover critical cross-component interactions
[ ] Test names clearly describe the scenario and expected outcome

SECURITY
[ ] User input is validated and sanitized
[ ] No SQL injection, XSS, or CSRF vulnerabilities
[ ] Secrets are not hardcoded (no API keys, passwords, or tokens in code)
[ ] Sensitive data is not logged or exposed in error messages
[ ] Authorization checks are in place (not just authentication)

PERFORMANCE
[ ] No N+1 query problems (check ORM-generated SQL)
[ ] Database queries use appropriate indexes (check EXPLAIN plan for new queries)
[ ] No unbounded collections loaded into memory
[ ] Pagination is used for list endpoints
[ ] Caching is used appropriately (and cache invalidation is correct)

OPERATIONAL READINESS
[ ] Logging is sufficient for debugging but not excessive
[ ] Metrics and alerts are added for new critical paths
[ ] Feature flags are used for risky changes
[ ] Database migrations are backward-compatible (can roll back without data loss)
[ ] Configuration changes are documented

NOTES / COMMENTS:
_____________________________________________________________________________
_____________________________________________________________________________
```

> **Key Takeaway:** Code review is not a gate to slow people down -- it is a collaborative practice that improves code quality, spreads knowledge, and builds team cohesion. Invest in making your review process efficient (small PRs, automated style checks, clear checklists) and humane (constructive tone, clear severity levels, praise for good work).

## Summary

The common thread of this section is that technical leadership is exercised through durable, written artifacts rather than through authority. An Architecture Decision Record captures the *why* of a significant choice -- context, decision, consequences -- so the team is not forced to relitigate it later. Write one whenever a decision shapes the system's structure, is hard to reverse, or has long-term implications, and treat the record as append-only: a reversed decision gets a new ADR that supersedes the old one, never an edit that erases the history.

The RFC / design-doc process is how you arrive at decisions worth recording. The discipline is to write the design before the code, while changing your mind still costs minutes rather than sprints; the RFC is the conversation, the ADR its minutes. Gate it with a lightweight norm -- roughly, any change over a week of work or touching a public API or data model -- and resist demanding docs for trivial changes.

Technical debt is a tool, not a sin. Fowler's quadrant tells you how to respond to each kind of debt; quantifying its cost in incidents, velocity, and onboarding time tells the business why it matters. Pay it down through a protected, tracked allocation, and reach for a rewrite only when the architecture fundamentally cannot meet requirements, the team deeply understands the existing system, and the business explicitly sponsors the cost.

Finally, code review is where these standards live or die day to day: review correctness, design, and security; automate style; keep changes under roughly 400 lines; and deliver feedback that explains, suggests, and distinguishes blockers from nits.

These practices govern how decisions are made and enforced; the next section, 10.2 System Thinking, turns to how senior engineers reason about the systems those decisions create.

---

*Last reviewed: 2026-06-08*

**Next:** [10.2 System Thinking](system-thinking.md)
