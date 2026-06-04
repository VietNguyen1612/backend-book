[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 7.2 CI/CD & Deployment

### CI/CD Pipelines

#### Pipeline Stages

A well-designed CI/CD pipeline automates the path from code commit to production deployment. Each stage acts as a quality gate: if any stage fails, the pipeline stops and the team is notified. The typical stages are:

1. **Lint:** Static analysis to enforce code style and catch common errors. Tools like `ruff`, `flake8`, or `eslint` run in seconds and catch issues before more expensive checks.
2. **Type Check:** For typed languages, run `mypy`, `pyright`, or TypeScript's `tsc` to verify type correctness.
3. **Unit Tests:** Fast tests that verify individual functions and classes in isolation. Aim for high coverage of business logic.
4. **Build:** Compile the application, build the Docker image, or bundle assets. This verifies that the code can actually produce a deployable artifact.
5. **Integration Tests:** Tests that exercise real interactions between components -- API endpoints, database queries, message queues. Typically run against a Docker Compose environment.
6. **Security Scan:** Scan dependencies for known vulnerabilities (`pip-audit`, `npm audit`, `trivy`). Scan the Docker image. Run SAST tools (`bandit` for Python, `semgrep`).
7. **Deploy to Staging:** Automatically deploy to a staging environment that mirrors production. Run smoke tests.
8. **Deploy to Production:** After manual approval (or automatic if all gates pass), deploy to production. Run post-deployment health checks.

#### Parallel Jobs and Matrix Builds

Independent stages should run concurrently to minimize pipeline duration. Linting, type checking, and unit tests can all run in parallel since they have no dependencies on each other. Matrix builds let you test the same code across multiple configurations -- different Python versions, different operating systems, different database versions -- in parallel.

#### Caching

CI pipelines run in clean environments each time, so without caching, every run downloads and installs all dependencies from scratch. Most CI systems let you cache directories between runs, keyed by a hash of the dependency lockfile. When `requirements.txt` (or `poetry.lock`, `package-lock.json`) doesn't change, the cached dependencies are restored in seconds instead of being reinstalled.

Docker layer caching is equally important. By pushing and pulling cache layers from a registry, subsequent image builds can skip unchanged layers, reducing build times from minutes to seconds.

#### Secret Management

CI/CD systems provide mechanisms for injecting secrets (API keys, deployment credentials, signing keys) into pipeline runs without exposing them in code. GitHub Actions uses encrypted secrets; GitLab CI uses protected variables. Key practices:

- Never echo or print secret values in logs.
- Use the CI system's masking feature to redact secrets that accidentally appear in output.
- Scope secrets to the minimum required: only specific branches, only specific environments.
- Rotate secrets regularly, especially after team member departures.
- Consider using OIDC federation (e.g., GitHub Actions OIDC with AWS) instead of long-lived credentials.

#### Artifact Management

Build artifacts (Docker images, compiled binaries, packaged bundles) should be stored in a registry or artifact repository with proper versioning. Use immutable tags -- never overwrite a tag like `latest` for production deployments. Instead, tag images with the git SHA, semantic version, or build number (e.g., `registry.example.com/myapp:v1.4.2` or `registry.example.com/myapp:abc123f`).

Popular container registries include Amazon ECR, Google Artifact Registry, GitHub Container Registry (ghcr.io), and Docker Hub.

#### GitHub Actions Example

Below is a comprehensive GitHub Actions workflow that implements all the stages discussed above.

{% raw %}
```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read
  packages: write            # For pushing to GitHub Container Registry
  id-token: write            # For OIDC authentication with cloud providers

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  PYTHON_VERSION: "3.12"

jobs:
  # ----------------------------------------------------------------
  # Stage 1: Quality checks (run in parallel)
  # ----------------------------------------------------------------
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install linter
        run: pip install ruff

      - name: Run ruff linter
        run: ruff check .

      - name: Run ruff formatter check
        run: ruff format --check .

  type-check:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-${{ hashFiles('requirements*.txt') }}
          restore-keys: pip-${{ runner.os }}-

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install mypy

      - name: Run mypy
        run: mypy app/ --strict

  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
      fail-fast: false         # Don't cancel other versions if one fails
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('requirements*.txt') }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests with coverage
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/ \
            --cov=app \
            --cov-report=xml \
            --cov-report=term-missing \
            -v

      - name: Upload coverage report
        if: matrix.python-version == '3.12'
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  # ----------------------------------------------------------------
  # Stage 2: Security scanning
  # ----------------------------------------------------------------
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Audit dependencies
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt

      - name: Run bandit (SAST)
        run: |
          pip install bandit
          bandit -r app/ -c pyproject.toml

  # ----------------------------------------------------------------
  # Stage 3: Build Docker image
  # ----------------------------------------------------------------
  build:
    name: Build & Push Image
    runs-on: ubuntu-latest
    needs: [lint, type-check, test, security-scan]
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      image-digest: ${{ steps.build-push.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build and push
        id: build-push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64

      - name: Scan image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: table
          exit-code: 1
          severity: CRITICAL,HIGH

  # ----------------------------------------------------------------
  # Stage 4: Deploy to Staging
  # ----------------------------------------------------------------
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [build]
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Configure kubectl
        uses: azure/setup-kubectl@v3

      - name: Set Kubernetes context
        uses: azure/k8s-set-context@v3
        with:
          kubeconfig: ${{ secrets.KUBE_CONFIG_STAGING }}

      - name: Deploy to staging
        run: |
          kubectl set image deployment/myapp \
            myapp=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -n staging
          kubectl rollout status deployment/myapp -n staging --timeout=300s

      - name: Run smoke tests
        run: |
          curl -sf https://staging.example.com/health || exit 1
          curl -sf https://staging.example.com/api/v1/status || exit 1

  # ----------------------------------------------------------------
  # Stage 5: Deploy to Production (manual approval via environment)
  # ----------------------------------------------------------------
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [deploy-staging]
    if: github.ref == 'refs/heads/main'
    environment: production     # Requires manual approval in GitHub settings
    steps:
      - uses: actions/checkout@v4

      - name: Configure kubectl
        uses: azure/setup-kubectl@v3

      - name: Set Kubernetes context
        uses: azure/k8s-set-context@v3
        with:
          kubeconfig: ${{ secrets.KUBE_CONFIG_PRODUCTION }}

      - name: Deploy to production
        run: |
          kubectl set image deployment/myapp \
            myapp=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -n production
          kubectl rollout status deployment/myapp -n production --timeout=300s

      - name: Post-deployment health check
        run: |
          sleep 30
          for i in $(seq 1 5); do
            if curl -sf https://api.example.com/health; then
              echo "Health check $i passed"
            else
              echo "Health check $i failed"
              exit 1
            fi
            sleep 10
          done
```
{% endraw %}

The post-deployment health check loop at the end is the kind of step whose output you read during an incident. A successful production deploy prints something like this in the Actions log:

```console
$ kubectl rollout status deployment/myapp -n production --timeout=300s
Waiting for deployment "myapp" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "myapp" rollout to finish: 1 old replicas are pending termination...
deployment "myapp" successfully rolled out

$ sleep 30 && for i in $(seq 1 5); do curl -sf https://api.example.com/health; ...
{"status":"ok"}
Health check 1 passed
{"status":"ok"}
Health check 2 passed
{"status":"ok"}
Health check 3 passed
{"status":"ok"}
Health check 4 passed
{"status":"ok"}
Health check 5 passed
```

**How to read this output:** `kubectl rollout status` blocks until every new replica is `Ready` (or the `--timeout` fires), so the job only proceeds once the new pods are actually serving — this is what turns a deploy step into a real gate rather than a fire-and-forget. The `curl -sf` flags matter: `-s` silences the progress meter and `-f` makes curl return a non-zero exit code on any HTTP 4xx/5xx, so a failing health check fails the shell loop and therefore the pipeline. If pod #2 had crash-looped, you would instead see `error: deployment "myapp" exceeded its progress deadline` and the job would go red before any traffic shifted — in an interview, this is the difference between "we deploy and hope" and "the pipeline refuses to mark a deploy successful unless the new version is healthy."

> **Common pitfall:** A passing `/health` endpoint that only checks "the process is up" gives false confidence. If health is shallow (no DB/Redis/downstream check), `rollout status` and these curls can all go green while the app is failing real requests. Make at least one readiness/health check exercise the critical dependencies.

> **Key Takeaway:** A CI/CD pipeline is your automated quality gate. Every commit passes through lint, type check, test, security scan, build, and deploy stages. Use parallelism and caching to keep pipelines fast. Use environments with manual approvals for production deployments. Never store secrets in code; use the CI system's secret management and prefer OIDC federation over long-lived credentials.

---

### Deployment Strategies

#### Blue-Green Deployment

Blue-green deployment maintains two identical production environments, called "blue" and "green." At any given time, one environment is live (serving all traffic) and the other is idle. To deploy, you deploy the new version to the idle environment, run tests against it, and then switch the load balancer or DNS to point to it. The switch is atomic: all users see the new version simultaneously.

The primary advantage is instant rollback -- if the new version has problems, switch back to the old environment. The primary disadvantage is cost: you maintain two full environments. In Kubernetes, blue-green can be implemented by running two Deployments with different labels and switching the Service selector.

#### Canary Deployment

Canary deployment routes a small percentage of production traffic (e.g., 5%) to the new version while the rest continues to hit the old version. You monitor the canary's error rate, latency, and business metrics. If everything looks good, you gradually increase the percentage (10%, 25%, 50%, 100%). If the canary shows elevated errors, you route all traffic back to the old version.

This approach minimizes blast radius: if the new version has a critical bug, only 5% of users are affected. Tools like Argo Rollouts, Flagger, and Istio provide automated canary management with metric-based promotion and automatic rollback.

#### Rolling Update

Rolling update replaces instances of the old version one (or a few) at a time. As each new instance passes its readiness check, an old instance is terminated. This is the default strategy in Kubernetes Deployments and requires no extra infrastructure. The tradeoff is that during the update, some requests hit the old version and some hit the new version. Both versions must be backwards-compatible.

#### Feature Flags

Feature flags decouple deployment from release. You deploy code containing a new feature to production, but the feature is disabled by default (behind an if-statement checking a flag). You can then enable the flag for specific users, a percentage of traffic, specific regions, or all users -- independently of deployment.

This enables:
- **Gradual rollout:** Enable for 1% of users, monitor, increase to 10%, 50%, 100%.
- **Kill switch:** If a feature causes problems, disable the flag instantly without rolling back code.
- **A/B testing:** Show different experiences to different user segments and measure impact.
- **Trunk-based development:** Merge incomplete features to main behind flags, avoiding long-lived branches.

Popular feature flag services include LaunchDarkly, Unleash, Flagsmith, and ConfigCat.

#### Database Migration Coordination

Database schema changes must be coordinated with application deployments because the old and new versions of the application may run simultaneously (during rolling updates or canary deployments). The safe approach is:

**Additive-only migrations:** Only add columns, tables, or indexes. Never remove or rename columns that the old version depends on. Deploy the migration first, then deploy the new application code.

**Expand-contract pattern (for breaking changes):**
1. **Expand:** Add the new column/table alongside the old one. Deploy code that writes to both.
2. **Migrate:** Backfill existing data from old to new.
3. **Contract:** Once all code uses the new schema, remove the old column/table in a subsequent deployment.

This multi-phase approach avoids downtime but requires careful planning and typically spans multiple deployment cycles.

> **Key Takeaway:** Deployment strategy is about controlling blast radius and rollback speed. Blue-green gives instant, atomic rollback at the cost of double infrastructure; canary limits exposure to a small percentage while you watch metrics; rolling update is the cheap default but forces both versions to coexist. Feature flags go further by decoupling deploy from release, giving you a kill switch independent of code. Whatever you choose, schema changes are the hard part: because old and new code run simultaneously during the transition, migrations must be backwards-compatible — additive-only by default, expand-contract for anything that breaks.

---

### Infrastructure as Code

#### Terraform

Terraform by HashiCorp is the most widely adopted Infrastructure as Code (IaC) tool. You declare the desired state of your infrastructure in HCL (HashiCorp Configuration Language), and Terraform computes and applies the changes needed to reach that state. It supports hundreds of providers (AWS, GCP, Azure, Cloudflare, GitHub, Kubernetes, and more).

The core workflow is:
1. `terraform init` -- Initialize the working directory, download providers.
2. `terraform plan` -- Preview what changes Terraform will make (like a dry run).
3. `terraform apply` -- Apply the changes.

**State management** is critical. Terraform tracks the current state of your infrastructure in a state file. In team environments, this state must be stored remotely (e.g., AWS S3) with locking (e.g., DynamoDB) to prevent concurrent modifications.

**Modules** allow you to create reusable, parameterized infrastructure components. Instead of duplicating resource definitions, you define a module once and instantiate it with different parameters for different environments.

```hcl
# terraform/main.tf

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state stored in S3 with DynamoDB locking
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "myapp"
    }
  }
}

# ---- Variables ----

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "myapp"
}

# ---- VPC ----

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.5.1"

  name = "${var.app_name}-${var.environment}"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment == "staging"  # Save cost in staging
  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# ---- EKS Cluster ----

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.2.1"

  cluster_name    = "${var.app_name}-${var.environment}"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 10

      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"

      labels = {
        role = "general"
      }
    }

    spot = {
      desired_size = 2
      min_size     = 0
      max_size     = 20

      instance_types = ["t3.large", "t3.xlarge", "t3a.large"]
      capacity_type  = "SPOT"

      labels = {
        role = "spot-workers"
      }

      taints = [{
        key    = "spot"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

# ---- RDS PostgreSQL ----

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "6.4.0"

  identifier = "${var.app_name}-${var.environment}"

  engine               = "postgres"
  engine_version       = "16.1"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.environment == "production" ? "db.r6g.large" : "db.t4g.medium"

  allocated_storage     = 50
  max_allocated_storage = 200

  db_name  = "myapp"
  username = "myapp"
  port     = 5432

  multi_az               = var.environment == "production"
  db_subnet_group_name   = module.vpc.database_subnet_group
  vpc_security_group_ids = [module.rds_sg.security_group_id]

  backup_retention_period = var.environment == "production" ? 30 : 7
  deletion_protection     = var.environment == "production"

  performance_insights_enabled = true
}

# ---- ECR Repository ----

resource "aws_ecr_repository" "app" {
  name                 = var.app_name
  image_tag_mutability = "IMMUTABLE"    # Prevent tag overwriting

  image_scanning_configuration {
    scan_on_push = true                  # Scan every pushed image
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Lifecycle policy: keep only the last 30 images
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 30 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# ---- Outputs ----

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "rds_endpoint" {
  value     = module.rds.db_instance_endpoint
  sensitive = true
}
```

Running `terraform plan` against this configuration (after `terraform init`) produces a diff of what Terraform intends to do. On a fresh environment with nothing yet created, the tail of the output looks something like this (resource counts and addresses vary with your modules):

```console
$ terraform plan
Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_ecr_repository.app will be created
  + resource "aws_ecr_repository" "app" {
      + arn                  = (known after apply)
      + image_tag_mutability = "IMMUTABLE"
      + name                 = "myapp"
      + repository_url       = (known after apply)
      ...
    }

  # module.vpc.aws_vpc.this[0] will be created
  + resource "aws_vpc" "this" {
      + cidr_block = "10.0.0.0/16"
      ...
    }

Plan: 78 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + ecr_repository_url    = (known after apply)
  + eks_cluster_endpoint  = (known after apply)
  + eks_cluster_name      = "myapp-production"
```

**How to read this output:** Each line is prefixed by an action symbol — `+` create, `~` change in place, `-` destroy, and `-/+` destroy-and-recreate (the dangerous one). `(known after apply)` means the value depends on something AWS assigns at creation time, so Terraform can't show it yet. The summary line `Plan: 78 to add, 0 to change, 0 to destroy` is the number you actually scrutinize in code review: on a routine change you expect a small, additive plan, so a PR that suddenly shows `0 to change, 14 to destroy` is a red flag that someone removed or renamed a resource. This is exactly why `terraform plan` doubles as drift detection — run it on a schedule against unchanged code and a non-empty plan means reality has diverged from the declared state. Because nothing is applied here, `plan` is safe to run on every PR.

> **Common pitfall:** A `-/+ destroy and then create` on a stateful resource (like the RDS instance or its `db_subnet_group`) can mean Terraform plans to delete your production database to satisfy a config change. Always read the plan, not just the exit code — and protect critical resources with `deletion_protection`, `prevent_destroy` lifecycle blocks, or `ignore_changes` so a careless apply can't wipe data.

#### Pulumi

Pulumi solves the same problem as Terraform but lets you write infrastructure definitions in real programming languages: Python, TypeScript, Go, C#, and Java. This means you can use loops, conditionals, functions, classes, unit tests, and your existing IDE tooling. Pulumi is particularly powerful when your infrastructure logic is complex or when your team is more comfortable with application languages than HCL.

#### Ansible

Ansible is a configuration management tool, not an infrastructure provisioning tool. It excels at configuring servers: installing packages, managing configuration files, starting services, running ad-hoc commands across fleets of machines. It is agentless (connects via SSH) and uses YAML playbooks to define idempotent tasks. While Terraform creates the infrastructure (VMs, networks, databases), Ansible configures what runs on that infrastructure.

#### Drift Detection

Infrastructure drift occurs when the actual state of your infrastructure diverges from its declared state in code. This happens when someone makes a manual change via the cloud console, an automated process modifies a resource, or a previous Terraform apply was interrupted.

`terraform plan` is the primary drift detection tool: it compares the declared state with the actual state and shows the differences. Run `terraform plan` in CI on a schedule (e.g., daily) to detect drift automatically. If drift is found, the team decides whether to update the code to match reality or re-apply the code to bring infrastructure back in line.

> **Key Takeaway:** Infrastructure as Code ensures that your infrastructure is versioned, reviewable, reproducible, and auditable -- just like application code. Terraform is the industry standard for provisioning cloud resources. Store state remotely with locking. Use modules for reusability. Run `terraform plan` in CI to catch drift. Pair Terraform (for infrastructure) with Ansible (for configuration) when needed.
