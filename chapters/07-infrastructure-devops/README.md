# Chapter 7: Infrastructure & DevOps

[Back to Book Index](../../README.md)

This chapter covers the infrastructure and operational practices that turn application code into a reliable, scalable production system. From containerizing applications with Docker and orchestrating them with Kubernetes, through automated CI/CD pipelines and deployment strategies, to building observability with structured logging, metrics, and alerting.

## Table of Contents

### [7.1 Containerization](containerization.md)
Packaging and orchestrating applications in containers for reproducibility, isolation, and scalability.
- Docker: multi-stage builds, layer caching, security, .dockerignore, health checks, networking, volumes, Docker Compose
- Kubernetes: Pods, Deployments, Services, Ingress, ConfigMaps & Secrets, resource management, HPA, probes, StatefulSets, DaemonSets, RBAC, Network Policies

### [7.2 CI/CD & Deployment](cicd-and-deployment.md)
Automating the path from code commit to production with quality gates, deployment strategies, and infrastructure as code.
- CI/CD Pipelines: pipeline stages, parallel jobs & matrix builds, caching, secret management, artifact management, GitHub Actions example
- Deployment Strategies: blue-green, canary, rolling update, feature flags, database migration coordination
- Infrastructure as Code: Terraform, Pulumi, Ansible, drift detection

### [7.3 Observability](observability.md)
Gaining visibility into system behavior through the three pillars of observability: logs, metrics, and traces.
- Logging: structured logging with structlog, log levels, correlation IDs, log aggregation (ELK, Loki), sampling
- Metrics & Monitoring: Prometheus, Grafana & PromQL, RED method, USE method, Four Golden Signals, alerting best practices

---

## Homework

Hands-on exercises for this chapter -- see [homework/questions.md](homework/questions.md). Skeleton files (`hw_*.py`) live alongside the questions in the [`homework/`](homework/) folder.

[Back to Book Index](../../README.md)
