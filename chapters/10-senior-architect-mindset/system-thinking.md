[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 10.2 System Thinking

> [!NOTE]
> **Beginner's Mental Model — Trade-offs:**
> Think of system design trade-offs like **buying a car**. You want a car that is lightning fast (performance), has massive cargo space (scale), is incredibly cheap (cost), and is completely safe (reliability). However, in reality, you cannot have all four. If you want a cheap, high-cargo vehicle, it won't be fast. If you want a fast sports car, it will be expensive and have zero cargo space. In software engineering, every decision is a trade-off: you must choose which features to prioritize and which ones you are willing to sacrifice based on your requirements.

### Trade-off Analysis Framework

Every architectural decision involves trade-offs. There is no perfect choice -- only choices that are better or worse for a specific context. The mark of a senior engineer is not knowing the "right" answer but being able to articulate the trade-offs clearly and make a deliberate, well-reasoned choice.

#### The Three Questions

Before diving into options, answer three fundamental questions:

1. **What are we optimizing for?** Every system has primary objectives. A trading platform optimizes for latency. A social media feed optimizes for availability. An accounting system optimizes for consistency. Make the optimization target explicit because it determines the direction of every downstream decision.

2. **What are we willing to sacrifice?** You cannot have everything. If you optimize for consistency, you sacrifice some availability (CAP theorem). If you optimize for speed of delivery, you sacrifice some code quality. If you optimize for flexibility, you sacrifice simplicity. Name the sacrifice explicitly so the team is aligned.

3. **What is the reversibility?** Jeff Bezos distinguishes between one-way doors (irreversible decisions) and two-way doors (easily reversible decisions). For two-way doors, decide quickly and iterate. For one-way doors, invest more time in analysis. Database schema choices, public API contracts, programming language selection, and architectural style (monolith vs. microservices) are typically one-way doors. Library choices, internal API designs, and configuration parameters are typically two-way doors.

#### Common Trade-offs in Backend Systems

**Consistency vs. Availability** -- The CAP theorem states that in the presence of a network partition, you must choose between consistency and availability. In practice, this manifests as: do you return stale data to keep the system available, or do you return an error to maintain consistency? Banking systems choose consistency. Social media feeds choose availability.

**Latency vs. Throughput** -- Batching increases throughput but adds latency (you wait to accumulate a batch). Streaming reduces latency but may reduce throughput (per-message overhead). The right choice depends on your use case: real-time chat needs low latency; bulk data processing needs high throughput.

**Simplicity vs. Flexibility** -- A simple system with hardcoded behavior is easy to understand and debug but hard to adapt. A flexible system with plugin architectures and configuration-driven behavior handles more use cases but is harder to reason about and more likely to harbor subtle bugs. Default to simplicity; add flexibility only when you have concrete evidence it is needed.

**Speed of Delivery vs. Code Quality** -- Shipping fast with shortcuts (skipping tests, hardcoding values, copying code) gets features out sooner but increases maintenance cost and defect rate over time. The right balance depends on the stage of the product: early-stage startups validating a hypothesis should lean toward speed; mature products serving millions of users should lean toward quality.

**Build vs. Buy** -- Building gives you control and customization; buying gives you speed and reduced maintenance. Build when the capability is a core differentiator for your business. Buy when it is commodity infrastructure (authentication, payment processing, email sending, monitoring).

**Monolith vs. Microservices** -- Monoliths are simpler to develop, test, deploy, and debug. Microservices enable independent scaling, independent deployment, and technology diversity. Start with a monolith; extract services only when you have clear, evidence-based reasons (team scaling, independent scaling needs, different technology requirements).

#### Trade-off Analysis Matrix Example

Below is a filled-in evaluation matrix for a real decision: choosing a primary database for a new e-commerce platform that handles product catalog, orders, and user data.

```
TRADE-OFF ANALYSIS MATRIX
==========================
Decision: Primary database for e-commerce platform
Date: 2025-10-20
Stakeholders: Backend team, DBA, Product, SRE

Requirements Summary:
- ACID transactions for order processing
- Complex queries for product search and reporting
- Expected 10M products, 500K daily orders, 5M registered users
- 99.95% availability target
- Team of 8 backend engineers

Criteria Weights (1-5, where 5 = critical):

+------------------------+--------+------------+------------+------------+
| Criterion              | Weight | PostgreSQL | MySQL 8    | MongoDB    |
+------------------------+--------+------------+------------+------------+
| ACID Compliance        |   5    |  10        |   9        |   6        |
|                        |        | Full ACID, | Full ACID, | Multi-doc  |
|                        |        | strong     | mature     | txns since |
|                        |        | isolation  | InnoDB     | 4.0, less  |
|                        |        | levels     |            | mature     |
+------------------------+--------+------------+------------+------------+
| Query Flexibility      |   4    |  10        |   7        |   6        |
|                        |        | CTEs,      | Good SQL   | Aggregation|
|                        |        | window     | support,   | pipeline   |
|                        |        | functions, | fewer      | is powerful|
|                        |        | JSONB,     | advanced   | but complex|
|                        |        | full-text  | features   |            |
+------------------------+--------+------------+------------+------------+
| Scalability            |   4    |   7        |   8        |  10        |
|                        |        | Vertical + | Good read  | Native     |
|                        |        | read       | replicas,  | sharding,  |
|                        |        | replicas;  | good       | horizontal |
|                        |        | Citus for  | sharding   | scale      |
|                        |        | horizontal | (Vitess)   |            |
+------------------------+--------+------------+------------+------------+
| Team Expertise         |   3    |   9        |   7        |   4        |
|                        |        | 6 of 8     | 3 of 8     | 1 of 8    |
|                        |        | engineers  | engineers  | engineers  |
|                        |        | proficient | proficient | proficient |
+------------------------+--------+------------+------------+------------+
| Operational Maturity   |   3    |   9        |   9        |   7        |
|                        |        | Decades of | Decades of | Mature but |
|                        |        | production | production | different  |
|                        |        | use, great | use, great | ops model  |
|                        |        | tooling    | tooling    |            |
+------------------------+--------+------------+------------+------------+
| Cost (AWS managed)     |   2    |   8        |   8        |   6        |
|                        |        | RDS Pg:    | RDS MySQL: | Atlas or   |
|                        |        | ~$350/mo   | ~$350/mo   | DocumentDB:|
|                        |        | (db.r6g.lg)| (db.r6g.lg)| ~$500/mo   |
+------------------------+--------+------------+------------+------------+
| Ecosystem / Extensions |   2    |  10        |   7        |   7        |
|                        |        | PostGIS,   | Fewer      | Rich driver|
|                        |        | pg_trgm,   | extensions | ecosystem, |
|                        |        | TimescaleDB| but solid  | Atlas      |
|                        |        | pgvector   | core       | search     |
+------------------------+--------+------------+------------+------------+

WEIGHTED SCORES:
  PostgreSQL: (5x10)+(4x10)+(4x7)+(3x9)+(3x9)+(2x8)+(2x10) = 50+40+28+27+27+16+20 = 208
  MySQL 8:    (5x9)+(4x7)+(4x8)+(3x7)+(3x9)+(2x8)+(2x7)    = 45+28+32+21+27+16+14 = 183
  MongoDB:    (5x6)+(4x6)+(4x10)+(3x4)+(3x7)+(2x6)+(2x7)   = 30+24+40+12+21+12+14 = 153

DECISION: PostgreSQL
RATIONALE: Highest weighted score driven by superior ACID compliance, query
flexibility, and strong team expertise. Scalability gap can be addressed with
read replicas and Citus extension if horizontal scaling is needed in the future.
MongoDB's document model does not align well with the relational nature of
e-commerce data (orders reference products, users, addresses).

RISKS:
- Vertical scaling limits may require Citus or read replicas at ~100K daily
  orders. Mitigation: design schema with future sharding key in mind.
- JSONB columns for flexible product attributes may tempt the team to use
  PostgreSQL as a document store. Mitigation: establish guidelines for when
  to use JSONB vs. relational columns.
```

> **Common pitfall:** The matrix is easy to weaponize. If you pick the winner first and then tune the weights and scores until the math agrees, you have built a rationalization, not an analysis -- and reviewers will smell it. Set the weights from your requirements *before* you score the options, ideally with a stakeholder who was not in the room when you formed your opinion. A matrix where every criterion conveniently favors your preferred choice is a red flag, not a result.

> **Key Takeaway:** A trade-off matrix does not make the decision for you -- it structures your thinking and makes it auditable. The weights reveal your priorities. The scores reveal your assumptions. Both can be challenged, discussed, and refined. The goal is not mathematical precision but transparent, systematic reasoning.

---

### Constraints First

The single most common mistake in technical decision-making is jumping to a solution before the problem is fully understood. Engineers love solutions; we reach for the database, the framework, the pattern we already know, and then retrofit the requirements to justify it. The senior discipline is the opposite: **clarify the constraints before you evaluate a single option.** A solution can only be judged "good" or "bad" relative to the requirements it must satisfy, so until those are written down, any debate about options is unanchored.

Separate the two kinds of requirements explicitly:

- **Functional requirements** describe *what the system does*: the features, the operations, the inputs and outputs. "Users can place an order," "admins can issue refunds," "the system sends a confirmation email." These are usually what stakeholders volunteer first.
- **Non-functional requirements (NFRs)** describe *how well it must do it*, and these are where architectures live or die: consistency model, latency targets (p50/p99), throughput, availability SLA, durability, security and compliance obligations (PCI, HIPAA, GDPR), cost ceiling, and the deadline. NFRs are frequently left implicit, and implicit NFRs are where projects fail -- nobody said "must be strongly consistent" until money went missing, and nobody said "p99 under 200ms" until the page felt sluggish under load.

The reason to surface NFRs first is that they are the constraints that actually eliminate options. Two designs can both satisfy every functional requirement and yet only one survives a "99.99% availability across two regions on a $2,000/month budget" constraint. If you choose the design first and discover the binding NFR later, you have already spent the budget that the constraint would have saved you. Pin the numbers down -- "how many requests per second?", "how stale can this data be?", "what is the recovery point objective?" -- even if the answer is a rough range, because a range still rules out the obviously-infeasible.

A practical habit: before any design discussion, write a short requirements block (functional bullets, then NFR bullets with concrete numbers, then hard constraints like budget, deadline, and existing-stack compatibility). This block is exactly the input the trade-off matrix above needs -- the weights in that matrix should fall straight out of the NFRs you just listed. When requirements are vague, the highest-leverage move is not to start building; it is to ask the clarifying questions that turn "make it fast" into "p99 under 200ms at 5,000 RPS."

> **Key Takeaway:** Requirements before options, and non-functional requirements before functional ones, because the NFRs are the constraints that actually decide the architecture. A solution proposed before the constraints are known is a guess wearing a confidence costume.

---

### Prefer Boring Technology

There is a strong, well-documented bias in engineering toward novelty: new languages, new databases, new frameworks feel exciting and look good on a resume. The senior counter-instinct, articulated memorably by Dan McKinley, is to **prefer boring technology** -- technology that is mature, well-understood, and predictable -- and to treat your appetite for novelty as a scarce, budgeted resource.

The mental model is **innovation tokens**. Imagine a team has only about three innovation tokens to spend. Each genuinely new, unproven, exotic technology you adopt costs one token. The reason the budget is so small is that "boring" does not mean "bad" -- it means the failure modes are *known*. A decade-old database has had its sharp edges discovered, documented, and Stack-Overflowed by thousands of teams before you; when it breaks at 3 a.m., someone has already written the runbook. A brand-new datastore has unknown failure modes that you will discover personally, in production, during an incident. The hidden costs of novelty -- operational burden, scarce hiring pool, immature tooling, thin documentation, no battle-tested patterns -- are systematically underestimated because they show up later, after the exciting "getting started" tutorial is over.

The discipline is therefore not "never use new technology" but **spend your innovation tokens where they create real differentiation.** If your product's entire value proposition is real-time collaborative editing, spend a token on the cutting-edge CRDT library that makes that possible -- that is where novelty buys you something a competitor cannot easily copy. But do not *also* run an exotic database, an experimental message queue, and a fashionable new language for the parts of the system that are pure commodity (auth, billing, CRUD). Those should be aggressively boring, so that all of your scarce risk budget and team attention concentrate on the one place that matters. Every undifferentiated component you build on novel tech is a token spent on something that earns you nothing.

This connects directly to the simplicity-versus-flexibility and build-versus-buy trade-offs above: boring, proven, often-bought technology for the commodity 90% of the system; deliberate, well-justified novelty for the differentiating 10%.

> **Key Takeaway:** You have roughly three innovation tokens. Spend them on the technology that makes your product uniquely valuable, and make everything else as boring as possible. Choosing exciting tech for an undifferentiated problem is paying a permanent operational tax for a one-time dopamine hit.

---

> [!NOTE]
> **Beginner's Mental Model — Bottlenecks:**
> Imagine a **six-lane highway that suddenly narrows down to a single lane** at a toll booth. No matter how fast cars drive on the six lanes, the total throughput of the highway is completely limited by how fast cars can pass through the single toll lane. The toll booth is the **bottleneck**. In system design, upgrading your fast application servers (the six lanes) won't make your app faster if your database is struggling to handle queries (the toll booth). To optimize a system, you must identify and widen the narrowest part.

### Back-of-Envelope Estimation

Back-of-envelope estimation is the ability to quickly approximate the scale of a system: how many servers you need, how much storage, what throughput, what latency. This skill is essential for system design (both in interviews and in real architecture work) because it separates feasible designs from fantasy.

#### Know Your Numbers

Memorize these reference points. They do not need to be exact -- order of magnitude is what matters.

**Time conversions:**

- 1 day = 86,400 seconds (round to ~100,000 for estimation)
- 1 month = ~2.5 million seconds
- 1 year = ~31.5 million seconds (round to ~30 million)

**Request rate conversions:**

- 1 million requests/day = ~12 requests/second
- 100 million requests/day = ~1,200 requests/second
- 1 billion requests/day = ~12,000 requests/second

**Latency reference points (order of magnitude):**

- L1 cache access: ~1 nanosecond
- L2 cache access: ~10 nanoseconds
- Main memory (RAM) access: ~100 nanoseconds
- SSD random read: ~100 microseconds (100,000 ns)
- Network round-trip within same datacenter: ~500 microseconds
- Network round-trip cross-continent: ~100 milliseconds
- HDD disk seek: ~10 milliseconds

**Storage reference points:**

- 1 ASCII character = 1 byte
- A typical database row (user profile) = 500 bytes to 2 KB
- A typical JSON API response = 1-10 KB
- A high-resolution photo = 2-5 MB
- 1 minute of HD video = 100-150 MB

**Powers of 2 (essential for quick math):**

- 2^10 = 1,024 ~ 1 Thousand (1 KB)
- 2^20 = 1,048,576 ~ 1 Million (1 MB)
- 2^30 = ~1 Billion (1 GB)
- 2^40 = ~1 Trillion (1 TB)

#### Step-by-Step Walkthrough: Design Twitter's Home Timeline

Let us walk through a complete back-of-envelope estimation for one of the most classic system design scenarios: serving Twitter's home timeline (the feed of tweets from people you follow).

**Step 1: Establish scale assumptions**

```
- Total users:           400 million
- Daily active users:    200 million (50% DAU/MAU ratio)
- Average follows:       200 accounts per user
- New tweets per day:    500 million (includes retweets)
- Average tweet size:    300 bytes (text + metadata, excluding media)
- Timeline reads/day:    Each DAU checks timeline ~10 times/day
- Timeline size:         Show the 200 most recent tweets from followed accounts
```

**Step 2: Estimate read QPS (Queries Per Second)**

```
Timeline reads per day = 200M DAU x 10 reads/day = 2 billion reads/day
Average QPS = 2 billion / 100,000 seconds = 20,000 QPS
Peak QPS (assume 3x average) = 60,000 QPS
```

**Step 3: Estimate write QPS**

```
New tweets per day = 500 million
Average QPS = 500M / 100,000 = 5,000 QPS
Peak QPS = 15,000 QPS (3x)
```

Observation: This is a **read-heavy** system (4:1 read-to-write ratio). This suggests we should optimize for reads, potentially using precomputed timelines (fan-out on write).

**Step 4: Estimate storage for tweets**

```
Tweets per day:          500 million
Average tweet size:      300 bytes (text + metadata)
Daily tweet storage:     500M x 300B = 150 GB/day
Annual tweet storage:    150 GB x 365 = ~55 TB/year
With replication (3x):   ~165 TB/year
5-year projection:       ~825 TB (before compression)
```

**Step 5: Estimate storage for precomputed timelines**

If we precompute timelines (fan-out on write), we store the last 200 tweet IDs for each active user:

```
Timeline entry:          tweet_id (8 bytes) + timestamp (8 bytes) = 16 bytes
Entries per user:        200
Timeline size per user:  200 x 16 bytes = 3.2 KB
All DAU timelines:       200M x 3.2 KB = 640 GB
With overhead (pointers, metadata): ~1 TB
```

This fits comfortably in a Redis cluster. At ~$25/GB/month for Redis on cloud, that is ~$25,000/month for timeline cache -- expensive but feasible for a company at Twitter's scale.

**Step 6: Estimate fan-out cost**

When a user tweets, we need to write that tweet ID to each follower's timeline:

```
Average followers: 200 (for normal users)
Fan-out writes per tweet: 200 writes
Total fan-out writes/day: 500M tweets x 200 = 100 billion writes/day
Fan-out QPS: 100B / 100K = 1,000,000 writes/second (!)
```

This is a huge number. This is why Twitter uses a hybrid approach: fan-out on write for normal users (< 10K followers) and fan-out on read for celebrity accounts (millions of followers). A celebrity tweet would generate billions of fan-out writes -- it is cheaper to merge celebrity tweets into the timeline at read time.

> **Common pitfall:** The average of 200 followers hides the real cost. Fan-out writes are dominated by the tail of the distribution, not the average -- a single account with 100 million followers generates as many writes as 500,000 ordinary users tweeting once. Estimating with the mean alone makes fan-out-on-write look affordable; the celebrity tail is exactly what breaks it. Always ask "what does the worst case look like?" not just "what does the average look like?"

**Step 7: Estimate bandwidth**

```
Timeline response: 200 tweets x 300 bytes = 60 KB per request
Peak read QPS: 60,000
Peak read bandwidth: 60,000 x 60 KB = 3.6 GB/second outbound

Tweet ingestion: 15,000 tweets/sec (peak) x 300 bytes = 4.5 MB/second inbound
```

Outbound bandwidth of 3.6 GB/s is significant but manageable with a CDN and multiple edge servers.

**Step 8: Estimate server count**

```
Assume a single application server handles 10,000 QPS (with connection pooling,
caching, and optimized I/O).

Timeline read servers: 60,000 peak QPS / 10,000 = 6 servers (minimum)
With redundancy (3x for failover): 18 servers

In practice, you would have more servers (50-100+) for:
- Geographic distribution
- Failure tolerance
- Headroom for traffic spikes beyond 3x
- Different tiers (API, fan-out workers, timeline assembly)
```

**Step 9: Summarize and sanity-check**

```
+-----------------------------+-------------------+
| Metric                      | Estimate          |
+-----------------------------+-------------------+
| Peak read QPS               | 60,000            |
| Peak write QPS              | 15,000            |
| Peak fan-out writes/sec     | 1,000,000         |
| Daily tweet storage         | 150 GB            |
| Timeline cache (RAM)        | ~1 TB             |
| Peak outbound bandwidth     | 3.6 GB/s          |
| Min application servers     | 18 (with 3x)      |
+-----------------------------+-------------------+
```

Sanity check: These numbers are in the right ballpark for a system of Twitter's scale. The fan-out write volume of 1M/sec confirms that a naive fan-out-on-write approach for all users is impractical, validating the need for the hybrid approach.

#### Estimate vs. Actual: Calibrate Over Time

The same humility that applies to sizing systems applies even more sharply to estimating *work*. An estimate exists to support a decision -- should we commit to this quarter? do we need to cut scope? -- not to predict the future with precision. Communicate estimates as **ranges with explicit assumptions** ("3 to 5 days, assuming the third-party API behaves like its docs claim"), never as false-precision single numbers, because a single number is read as a promise and a range is read as the uncertainty it actually is.

The way you get better at estimating is not by thinking harder up front; it is by **tracking estimate versus actual and feeding the gap back into your next estimate.** Almost every engineer is systematically optimistic, because we estimate the happy-path coding time and forget the long tail: integration, edge cases, code review back-and-forth, testing, deployment, the meeting that derails a morning, the dependency that is broken. Record what you estimated and what it actually took, look at the ratio over many tasks, and you will discover a personal (and team) fudge factor -- it is common to find that real elapsed time runs 1.5x to 2x the naive estimate. Apply that multiplier deliberately rather than re-learning it through every missed deadline.

> **Common pitfall:** Treating an estimate as a commitment, and then never comparing it to the actual. A team that estimates but never measures the error never improves -- it just keeps being surprised in the same direction. The cheapest calibration data you will ever get is the difference between what you said and what happened; throwing it away guarantees the next estimate is exactly as wrong as the last.

> **Key Takeaway:** Back-of-envelope estimation is not about getting exact numbers. It is about getting the right order of magnitude so you can make informed architectural decisions. The process matters more than the result: it forces you to think about scale, identify bottlenecks, and validate (or invalidate) design approaches before writing a single line of code.

---

### Incident Management

Incidents are inevitable in any system of sufficient complexity. The question is not whether they will happen but how well your team handles them. Effective incident management minimizes impact, accelerates recovery, and -- most importantly -- drives systemic improvements that prevent recurrence.

#### The Incident Lifecycle

The incident lifecycle has five phases, each with distinct goals and activities:

**1. Detect** -- The faster you detect an incident, the less damage it causes. Detection should be primarily automated through monitoring and alerting. Key detection mechanisms include: synthetic monitoring (probes that simulate user actions and alert on failure), error rate alerts (alert when the error rate exceeds a threshold, e.g., >1% of requests returning 5xx), latency alerts (alert when p99 latency exceeds SLA), business metric alerts (alert when order volume drops >30% compared to the same hour last week), and customer reports (the least desirable detection method, as it means your monitoring has a gap).

**2. Triage** -- Once detected, quickly assess the scope and severity. Is this affecting all users or a subset? Is it a total outage or degraded performance? What services are involved? Assign a severity level (see classification below) and assemble the appropriate response team.

**3. Mitigate** -- The immediate priority is to stop the bleeding, not to find the root cause. Mitigation strategies include: rolling back the most recent deployment (the most common cause of incidents), toggling a feature flag to disable the problematic feature, scaling up resources if the issue is capacity-related, failing over to a secondary region or database replica, applying a hotfix (only if the fix is simple and well-understood), or shedding load by returning cached responses or enabling rate limiting. The goal of mitigation is to restore service for users. Root cause analysis comes later.

**4. Resolve** -- After mitigation stabilizes the system, apply the permanent fix. This may involve a proper code fix (rather than the hotfix applied during mitigation), infrastructure changes, configuration updates, or data repairs. Verify that the resolution is complete: confirm that error rates have returned to baseline, latency is normal, and no secondary issues have emerged.

**5. Postmortem** -- After the incident is fully resolved, conduct a blameless postmortem to learn from it and prevent recurrence. This is the most important phase because it is what transforms an incident from a crisis into an improvement opportunity.

#### Roles During an Incident

Clear roles prevent chaos. Three roles are essential:

**Incident Commander (IC)** -- Owns the overall response. Makes decisions about severity, communication, and escalation. Does NOT debug the issue personally -- they coordinate. The IC's job is to ensure the right people are engaged, decisions are being made, and stakeholders are informed.

**Technical Lead** -- The engineer (or engineers) actively debugging and fixing the issue. They report findings and proposed actions to the IC, who approves or redirects.

**Communication Lead** -- Manages external and internal communication. Posts updates to the status page, notifies affected customers, updates stakeholders in the incident channel. Frequency depends on severity: SEV1 gets updates every 15 minutes, SEV2 every 30 minutes.

#### On-Call Best Practices

On-call rotations should be weekly or bi-weekly, with the rotation scheduled well in advance. Every alert that pages an on-call engineer should have a corresponding runbook: a step-by-step guide that any engineer on the team can follow to diagnose and mitigate the issue. The format should be: Alert name --> What it means --> How to diagnose --> How to mitigate --> When to escalate.

If an on-call engineer is paged more than twice per shift for non-actionable alerts, the alerting is broken and must be fixed. Alert fatigue is dangerous -- it trains engineers to ignore alerts, and the one they ignore will be the real incident.

Compensate on-call fairly. Engineers who carry pagers outside business hours are providing a service that has a real cost (interrupted sleep, restricted freedom, stress). Many organizations provide additional pay, compensatory time off, or both.

#### Incident Classification

```
+-------+-------------------+-------------------------------+------------------+
| Level | Name              | Description                   | Response SLA     |
+-------+-------------------+-------------------------------+------------------+
| SEV1  | Critical          | Complete outage or data loss   | Respond: 5 min   |
|       |                   | affecting all or most users.   | Mitigate: 30 min |
|       |                   | Revenue-impacting. Security    | Update: every    |
|       |                   | breach. All hands on deck.     | 15 minutes       |
+-------+-------------------+-------------------------------+------------------+
| SEV2  | Major Degradation | Significant feature broken     | Respond: 15 min  |
|       |                   | or major performance issue     | Mitigate: 1 hour |
|       |                   | affecting many users. Core     | Update: every    |
|       |                   | functionality impaired.        | 30 minutes       |
+-------+-------------------+-------------------------------+------------------+
| SEV3  | Minor Issue       | Non-critical feature broken    | Respond: 1 hour  |
|       |                   | or minor performance issue     | Mitigate: 4 hours|
|       |                   | affecting some users.          | Update: as needed|
+-------+-------------------+-------------------------------+------------------+
| SEV4  | Cosmetic / Low    | Minor bug, UI glitch, or      | Respond: 1 day   |
|       |                   | issue with workaround. No      | Fix: next sprint |
|       |                   | significant user impact.       | No formal updates|
+-------+-------------------+-------------------------------+------------------+
```

> **Common pitfall:** Severity inflation and severity timidity are both dangerous. Teams that page everyone at SEV1 for minor degradations train responders to ignore the pager (alert fatigue), while teams that under-declare to avoid scrutiny rob themselves of the response resources and postmortem rigor a real outage demands. Define severity by concrete, measurable user impact -- not by who is watching or how stressful the incident feels in the moment.

#### Blameless Postmortem

The principle of blameless postmortems is not that nobody is accountable -- it is that the focus is on systemic causes rather than individual blame. The question is not "who messed up?" but "what about our systems, processes, and safeguards allowed this to happen, and how do we fix those?"

When people fear blame, they hide information. When they feel safe, they share the full truth, and the full truth is what you need to actually fix the problem.

#### Incident Postmortem Template with Example

```
=========================================================================
INCIDENT POSTMORTEM
=========================================================================

TITLE: Payment Processing Outage Due to Database Connection Pool Exhaustion
INCIDENT ID: INC-2025-0847
DATE OF INCIDENT: 2025-09-12
SEVERITY: SEV1
DURATION: 47 minutes (14:23 UTC - 15:10 UTC)
AUTHOR: Sarah Chen (Incident Commander)
POSTMORTEM DATE: 2025-09-14

=========================================================================
1. EXECUTIVE SUMMARY
=========================================================================

On September 12, 2025, the payment processing service experienced a complete
outage lasting 47 minutes. During this period, no customer payments could be
processed, resulting in an estimated $180,000 in delayed revenue and
approximately 12,000 failed checkout attempts. The root cause was database
connection pool exhaustion triggered by a slow query introduced in a deployment
90 minutes before the incident.

=========================================================================
2. IMPACT
=========================================================================

- Duration: 47 minutes (14:23 - 15:10 UTC)
- Users affected: ~12,000 users attempted checkout during the outage
- Revenue impact: ~$180,000 in delayed transactions (most recovered after
  resolution as users retried)
- Permanently lost transactions: estimated 800-1,200 ($12,000-$18,000)
  where users abandoned and did not return
- Downstream impact: Order fulfillment pipeline was delayed by 2 hours
  as the backlog of orders was processed
- Customer support: 340 support tickets filed; support team worked 6 extra
  hours to clear the queue
- SLA impact: Monthly uptime dropped from 99.97% to 99.89%, breaching our
  99.95% SLA with two enterprise customers

=========================================================================
3. TIMELINE (all times UTC)
=========================================================================

12:52  Deployment v2.34.0 released to production. Included 14 changes,
       among them a new query for the "order history" feature that joins
       5 tables without a covering index.

13:00  No immediate issues observed. Deployment marked as successful.

14:15  Slow query begins to accumulate as afternoon traffic ramps up.
       Database connection pool utilization climbs from 40% to 75%.

14:20  Connection pool utilization reaches 90%. p99 latency for payment
       API increases from 200ms to 1,800ms.

14:23  [ALERT] PaymentService error rate exceeds 5% threshold.
       On-call engineer (David) is paged.

14:25  David acknowledges the page and joins the incident channel.
       Declares SEV2 initially.

14:28  David checks dashboards. Sees 100% connection pool utilization
       and rapidly climbing error rate (now 40%). Escalates to SEV1.
       Incident Commander (Sarah) and Communication Lead (Maria) join.

14:32  Maria posts first status page update: "We are investigating issues
       with payment processing. Payments may fail or be delayed."

14:35  David identifies that all connections are held by a slow query
       (avg execution time: 12 seconds, expected: <100ms). The query
       is traced to the order-history endpoint.

14:38  David proposes mitigation: roll back to v2.33.0. Sarah approves.

14:40  Rollback initiated via CI/CD pipeline.

14:48  Rollback deployment completes. New pods are healthy but database
       connection pool is still saturated with long-running queries.

14:50  David manually kills the 47 long-running query sessions in the
       database.

14:55  Connection pool utilization drops to 30%. Error rate decreasing.

15:05  Error rate returns to baseline (<0.1%). Latency normal.

15:10  Sarah declares incident resolved. Maria updates status page:
       "Payment processing has been restored. We are monitoring."

15:30  Maria sends follow-up: "All systems operating normally. Some
       customers may need to retry their checkout."

=========================================================================
4. ROOT CAUSE ANALYSIS
=========================================================================

The root cause was a new database query introduced in v2.34.0 for the
"order history" feature. The query performed a JOIN across 5 tables
(orders, order_items, products, payments, shipments) with a WHERE clause
filtering on user_id and date range.

The query was missing a composite index on orders(user_id, created_at).
In development and staging, the query performed well because the dataset
was small (10,000 orders). In production, with 45 million orders, the
query required a full table scan, taking 12+ seconds per execution.

As afternoon traffic increased, more users accessed order history. Each
request held a database connection for 12+ seconds. The connection pool
(max: 50 connections) was exhausted within minutes. Once exhausted, ALL
requests to the payment service -- not just order history -- failed
because they could not acquire a database connection.

5 WHYS:
1. Why did payments fail? -- Database connections were exhausted.
2. Why were connections exhausted? -- A slow query held connections for 12s.
3. Why was the query slow? -- Missing composite index on a 45M-row table.
4. Why was the missing index not caught? -- Staging has only 10K rows;
   the query was fast there. No production-scale query review process.
5. Why is there no production-scale query review? -- We have not
   established a process for reviewing query EXPLAIN plans against
   production data volumes before deployment.

=========================================================================
5. CONTRIBUTING FACTORS
=========================================================================

- The payment service shared a single database connection pool between
  all endpoints (order history, payment processing, refunds). A slow
  query on one endpoint starved all others.
- The connection pool size (50) was not monitored with a proactive alert.
  The alert that fired was based on error rate, which is a lagging
  indicator. A connection pool utilization alert at 80% would have given
  us 3-5 minutes of earlier warning.
- The deployment contained 14 changes, making it harder to identify the
  problematic change during the incident.
- There was no circuit breaker or timeout on the order-history endpoint
  that would have caused it to fail fast rather than hold connections.

=========================================================================
6. WHAT WENT WELL
=========================================================================

- Alert fired within 3 minutes of impact starting.
- On-call engineer responded within 2 minutes of page.
- Escalation to SEV1 was prompt (3 minutes after joining).
- Rollback was smooth and completed in 10 minutes.
- Communication to customers was timely and clear.
- Team collaboration in the incident channel was focused and efficient.

=========================================================================
7. WHAT WENT POORLY
=========================================================================

- The slow query was not caught during code review or in staging.
- Rollback alone did not fix the issue because in-flight queries
  continued holding connections. We had to manually kill queries.
- The connection pool saturation was not detected until it caused errors.
- The deployment was too large (14 changes), slowing root cause analysis.

=========================================================================
8. ACTION ITEMS
=========================================================================

| # | Action                                        | Owner   | Due        | Status  |
|---|-----------------------------------------------|---------|------------|---------|
| 1 | Add composite index on orders(user_id,        | David   | 2025-09-16 | Done    |
|   | created_at) and re-deploy order history feature|        |            |         |
| 2 | Add connection pool utilization alert at 80%   | SRE     | 2025-09-19 | Done    |
| 3 | Implement per-endpoint database connection     | Backend | 2025-10-01 | Pending |
|   | pools (isolate order-history from payments)    |         |            |         |
| 4 | Add query timeout of 5 seconds on all database | Backend | 2025-09-23 | Done    |
|   | queries with circuit breaker fallback          |         |            |         |
| 5 | Establish query review checklist: all new      | Tech    | 2025-09-30 | Pending |
|   | queries must include EXPLAIN plan reviewed     | Lead    |            |         |
|   | against production row counts                  |         |            |         |
| 6 | Reduce max deployment batch size to 5 changes  | DevOps  | 2025-09-23 | Done    |
| 7 | Populate staging DB with production-scale data | SRE     | 2025-10-15 | Pending |
|   | (anonymized) for performance testing           |         |            |         |
| 8 | Add runbook for "connection pool exhaustion"   | David   | 2025-09-19 | Done    |
|   | scenario including manual query kill steps     |         |            |         |

=========================================================================
9. LESSONS LEARNED
=========================================================================

- A query that performs well on 10K rows can be catastrophic on 45M rows.
  Database performance testing must use production-scale data volumes.
- Shared connection pools create blast radius problems. Isolating
  connection pools per feature area (or using separate databases) limits
  the impact of any single slow query.
- Rollback is necessary but not always sufficient. Long-running database
  operations survive application rollback. Runbooks must include database-
  level remediation steps.
```

> **Key Takeaway:** Incidents are learning opportunities. A team that conducts thorough, blameless postmortems and follows through on action items will see its incident rate decline over time. A team that skips postmortems -- or writes them but never acts on the action items -- will keep having the same incidents. The action items table is the most important part of a postmortem. Track completion rigorously.

---

### Technology Evaluation

Choosing technologies -- frameworks, databases, languages, cloud services, third-party tools -- is one of the most consequential decisions an engineering team makes. A poor technology choice can haunt a team for years through maintenance burden, hiring difficulty, performance limitations, or vendor lock-in. A strong evaluation process reduces the risk of costly mistakes.

#### The ThoughtWorks Technology Radar Model

The Technology Radar, popularized by ThoughtWorks, provides a useful classification framework for how your organization relates to technologies:

**Adopt** -- These are proven technologies that your organization has used successfully in production. You have expertise, tooling, and confidence. Use them as default choices for new projects. Examples for a typical backend team might include: PostgreSQL, Spring Boot, Docker, Kubernetes, GitHub Actions.

**Trial** -- These are technologies you have investigated and believe are promising. They are ready for use on a real (but non-critical) project to gain production experience. The goal is to move them to Adopt or back to Assess based on what you learn. Example: "We have studied Apache Pulsar and believe it may be better than Kafka for our multi-tenant use case. We will use it for the internal analytics pipeline as a trial."

**Assess** -- These are technologies on your radar that look interesting but you have not yet invested time in understanding deeply. You should explore them through reading, conference talks, small prototypes, or community engagement. The goal is to decide whether to promote them to Trial or drop them. Example: "WebAssembly for server-side plugins looks promising. We should assess it this quarter."

**Hold** -- These are technologies you have decided NOT to adopt, either because they are being phased out, because they did not pass evaluation, or because they are risky for your context. "Hold" does not mean "bad" -- it means "not for us, not now." Existing use continues with maintenance but no new adoption. Example: "We are placing MongoDB on Hold for transactional workloads after our evaluation showed it does not meet our ACID requirements. Existing MongoDB instances for analytics will continue to be maintained."

Maintaining a team-level Technology Radar creates transparency about technology choices and prevents the "resume-driven development" problem where engineers introduce technologies because they want to learn them, not because they are the best choice for the team.

#### Evaluation Criteria

When evaluating a technology, assess it across these dimensions:

**Maturity** -- How long has it been in production use by the broader community? Is it past version 1.0? Have the breaking changes settled down? Mature technologies have known failure modes and documented solutions. Immature technologies have unknown failure modes that you will discover in production.

**Community size and activity** -- A large, active community means more Stack Overflow answers, more tutorials, more libraries and integrations, and more shared operational knowledge. Check GitHub stars (as a rough proxy), contributor count, commit frequency, and the responsiveness of maintainers to issues and PRs.

**Documentation quality** -- Poor documentation multiplies onboarding time and increases the chance of misuse. Evaluate: Are there comprehensive getting-started guides? Is the API reference complete? Are there examples for common use cases? Is the documentation kept up to date with the latest version?

**Maintenance activity** -- Check the release frequency, the age of the newest release, and the number of open issues and their age. A project with 2,000 open issues and no release in 12 months is at risk. A project with frequent releases and responsive maintainers is healthy.

**License** -- Understand the license and its implications. MIT and Apache 2.0 are permissive and low-risk. AGPL requires you to open-source your own code if you distribute it. Some licenses have changed unexpectedly (e.g., Elasticsearch's license change from Apache 2.0 to SSPL). Evaluate vendor lock-in risk.

**Security track record** -- Check for CVEs (Common Vulnerabilities and Exposures). How quickly are security issues patched? Is there a responsible disclosure process? Does the project have a security audit history?

**Migration path** -- How difficult is it to migrate away from this technology if you need to? Technologies with standard interfaces (SQL databases, S3-compatible storage, OpenTelemetry-compatible observability) are lower risk than those with proprietary protocols and data formats.

**Team skill gap** -- How many engineers on your team have experience with this technology? What is the learning curve? Is there a training budget and timeline? Hiring: how many candidates in your market know this technology?

#### Technology Evaluation Scorecard Example

Below is a filled-in scorecard for evaluating a web framework for a new backend API service.

```
TECHNOLOGY EVALUATION SCORECARD
================================
Evaluated by: Backend Architecture Team
Date: 2025-08-10
Purpose: Select web framework for new Order Management API service
Current stack: Java 17 + Spring Boot 3.x (existing services)

+----------------------------+--------+-------------+----------+-----------+
| Criterion                  | Weight | Spring Boot | Quarkus  | Go + Gin  |
|                            | (1-5)  | 3.x (Java)  | (Java)   |           |
+----------------------------+--------+-------------+----------+-----------+
| Maturity                   |   4    |  10         |   7      |   9       |
| (production track record)  |        | 10+ years,  | 4 years, | Go: 12yr, |
|                            |        | dominant in | growing  | Gin: 8yr  |
|                            |        | enterprise  | adoption |           |
+----------------------------+--------+-------------+----------+-----------+
| Community & Ecosystem      |   4    |  10         |   7      |   8       |
| (libraries, integrations)  |        | Largest     | Smaller  | Large Go  |
|                            |        | Java eco    | but      | ecosystem,|
|                            |        |             | active   | fewer     |
|                            |        |             |          | enterprise|
|                            |        |             |          | libs      |
+----------------------------+--------+-------------+----------+-----------+
| Performance (throughput,   |   3    |   7         |   9      |  10       |
| startup time, memory)      |        | Good thru-  | GraalVM  | Excellent |
|                            |        | put, slow   | native:  | all-round |
|                            |        | startup,    | fast     | low mem,  |
|                            |        | high memory | start,   | fast start|
|                            |        |             | low mem  |           |
+----------------------------+--------+-------------+----------+-----------+
| Team Expertise             |   5    |  10         |   6      |   3       |
| (current skills, learning  |        | All 8 devs  | Java exp | 1 dev has |
|  curve)                    |        | proficient  | helps,   | Go exp,   |
|                            |        |             | but new  | significant|
|                            |        |             | patterns | ramp-up   |
+----------------------------+--------+-------------+----------+-----------+
| Hiring Market              |   3    |   9         |   5      |   7       |
| (availability of talent)   |        | Very large  | Niche    | Growing   |
|                            |        | talent pool | pool     | but fewer |
|                            |        |             |          | enterprise|
|                            |        |             |          | candidates|
+----------------------------+--------+-------------+----------+-----------+
| Operational Consistency    |   4    |  10         |   7      |   4       |
| (fits existing infra,      |        | Same as all | Same JVM | Different |
| CI/CD, monitoring)         |        | our other   | but diff | build,    |
|                            |        | services    | build    | deploy,   |
|                            |        |             | tooling  | monitor   |
+----------------------------+--------+-------------+----------+-----------+
| Documentation Quality      |   2    |  10         |   8      |   7       |
|                            |        | Excellent   | Good,    | Good but  |
|                            |        |             | well     | scattered |
|                            |        |             | written  | across    |
|                            |        |             |          | community |
+----------------------------+--------+-------------+----------+-----------+
| License & Vendor Risk      |   2    |   9         |   9      |  10       |
|                            |        | Apache 2.0, | Apache   | BSD, no   |
|                            |        | VMware/     | 2.0, Red | vendor    |
|                            |        | Broadcom    | Hat      | dependency|
|                            |        | backing     | backing  |           |
+----------------------------+--------+-------------+----------+-----------+

WEIGHTED SCORES:
  Spring Boot: (4x10)+(4x10)+(3x7)+(5x10)+(3x9)+(4x10)+(2x10)+(2x9)
             = 40+40+21+50+27+40+20+18 = 256

  Quarkus:     (4x7)+(4x7)+(3x9)+(5x6)+(3x5)+(4x7)+(2x8)+(2x9)
             = 28+28+27+30+15+28+16+18 = 190

  Go + Gin:    (4x9)+(4x8)+(3x10)+(5x3)+(3x7)+(4x4)+(2x7)+(2x10)
             = 36+32+30+15+21+16+14+20 = 184

RECOMMENDATION: Spring Boot 3.x

RATIONALE:
Spring Boot scores highest due to dominant team expertise and operational
consistency with our existing service fleet. While Go + Gin offers superior
raw performance and Quarkus offers a modern Java experience with better
startup characteristics, neither advantage outweighs the cost of reduced
team productivity during the learning curve and the operational burden of
supporting a heterogeneous stack.

If startup time and memory become critical requirements (e.g., for
serverless deployment), Quarkus should be re-evaluated as it shares the
Java ecosystem while offering significant improvements in those areas.

DECISION: Proceed with Spring Boot 3.x.
FOLLOW-UP: Re-assess Quarkus in Q2 2026 if we pursue serverless migration.
```

#### Proof of Concept Guidelines

When the evaluation scorecard does not produce a clear winner, or when the decision is high-stakes and irreversible, run a Proof of Concept (PoC). A PoC is not an MVP -- it does not test business value. It tests **technical feasibility**: "Can this technology actually do what we need it to do under realistic conditions?"

PoC rules:

1. **Time-box strictly**: 1-2 weeks maximum. If you cannot answer your key questions in that time, scope the PoC down.
2. **Define specific hypotheses**: "We believe Kafka can handle 50K events/sec with <100ms latency on a 3-broker cluster" is testable. "Let's try Kafka and see how it goes" is not.
3. **Use realistic workloads**: Test with production-like data volumes, traffic patterns, and failure scenarios. A PoC that only tests the happy path with toy data is worthless.
4. **Document findings**: Write a PoC report that describes what was tested, what was found, what surprised you, and your recommendation. This becomes an input to the ADR.
5. **PoC code is throwaway**: Make this explicit. PoC code is written to learn, not to ship. It will not have tests, error handling, or production-quality structure, and that is fine. Do not let PoC code leak into production.

> **Key Takeaway:** Technology decisions should be deliberate, not accidental. Evaluate technologies systematically using a scorecard that weights criteria by your actual priorities. Run PoCs for high-stakes decisions. Maintain a Technology Radar so the whole team knows what is adopted, what is being evaluated, and what is off-limits. The best technology choice is not the best technology in the abstract -- it is the best technology for your team, your context, and your constraints.

*Last reviewed: 2026-06-08*
