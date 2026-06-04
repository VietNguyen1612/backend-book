[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 7.1 Containerization

### Docker

#### Multi-Stage Builds

A multi-stage build uses multiple `FROM` statements in a single Dockerfile. The key idea is to separate the **build environment** (which contains compilers, build tools, and development dependencies) from the **runtime environment** (which contains only the final artifact and its runtime dependencies). This dramatically reduces the size of your production image -- often by 10x or more -- and shrinks the attack surface by removing unnecessary tooling.

In the build stage, you install everything needed to compile or bundle your application. In the runtime stage, you start from a minimal base image and copy only the built artifact from the previous stage. Nothing else carries over: no source code, no build tools, no intermediate files.

```dockerfile
# ============================================================
# Stage 1: Build
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (gcc, etc.) that are needed to compile
# certain Python packages with C extensions.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first. This exploits Docker layer
# caching: as long as requirements.txt doesn't change, the expensive
# pip install step is cached and not re-run.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy the rest of the source code.
COPY . .

# ============================================================
# Stage 2: Runtime
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a non-root user for security (see Security section below).
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy only the installed Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy application source code from the builder stage.
COPY --from=builder /app /app

# Switch to the non-root user.
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The resulting runtime image contains no compiler, no gcc, no build headers -- only the Python runtime and your installed packages.

The size difference is the whole point. After building both a naive single-stage image and the multi-stage one above, `docker images` shows something like (exact sizes vary by base image version and dependency set):

```console
$ docker images
REPOSITORY      TAG              IMAGE ID       SIZE
myapp           single-stage     a1b2c3d4e5f6   1.18GB
myapp           multi-stage      f6e5d4c3b2a1   214MB
```

**How to read this output:** The single-stage image carries `gcc`, `libpq-dev`, apt caches, and build headers that are only needed at build time -- roughly a gigabyte of dead weight that ships to every node, slows every `docker pull`, and widens the attack surface. The multi-stage image discarded all of it by copying only `/install` into a fresh runtime base. In an interview, "how do you shrink a Docker image?" is answered first with multi-stage builds; in production, smaller images mean faster autoscaling and rollouts because nodes pull layers in seconds, not minutes.

#### Layer Caching

Every instruction in a Dockerfile creates a layer. Docker caches each layer and reuses it if the instruction and all preceding layers have not changed. When a layer's cache is invalidated, every subsequent layer is also rebuilt. This means the order of instructions in your Dockerfile has a significant impact on build speed.

The golden rule is: **order instructions from least frequently changing to most frequently changing.** System-level dependencies change rarely, so install them first. Application dependency manifests (like `requirements.txt` or `package.json`) change occasionally, so copy and install them next. Your actual source code changes on every commit, so copy it last.

```dockerfile
# GOOD: Copy requirements.txt separately, before source code.
# If only source code changes, pip install is cached.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
```

```dockerfile
# BAD: Copying everything at once invalidates the pip install
# cache on every source code change.

COPY . .
RUN pip install --no-cache-dir -r requirements.txt
```

Additional tips for maximizing cache hits:
- Combine related `RUN` commands with `&&` to reduce layer count, but do not combine unrelated ones (that would unnecessarily invalidate caches).
- Use `--no-cache-dir` with pip to avoid storing the download cache inside the image layer.
- Use `--mount=type=cache` (BuildKit feature) for persistent build caches across builds.

You can see caching at work in the build output. When you rebuild after changing only source code (not `requirements.txt`), the expensive dependency layers are reused:

```console
$ docker build -t myapp .
 => CACHED [builder 3/5] COPY requirements.txt .
 => CACHED [builder 4/5] RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
 => [builder 5/5] COPY . .
 => exporting to image
 => => naming to docker.io/library/myapp:latest
```

**How to read this output:** The `CACHED` prefix means Docker reused a previously built layer instead of re-running the instruction. The `pip install` step -- usually the slowest part of the build -- is skipped entirely because `requirements.txt` was unchanged, turning a multi-minute rebuild into a few seconds. If you had used the BAD ordering (`COPY . .` before `pip install`), editing a single source file would invalidate the copy layer and force a full reinstall every time -- the difference between a 5-second and a 5-minute CI build.

> **Common pitfall:** Layer caching is invalidated by *content*, not just by named files. `COPY . .` is invalidated by any change in the build context, including files you do not care about -- which is exactly why a tight `.dockerignore` (next section) is part of cache hygiene, not just security.

#### Security

Running containers as the root user is a common default that should always be overridden in production. If an attacker exploits a vulnerability in your application, root access inside the container can be leveraged to escape to the host or access sensitive resources. Always create and switch to a non-root user.

Choose a minimal base image to reduce the attack surface. Alpine-based images (e.g., `python:3.12-alpine`) are very small but can cause compatibility issues with some C libraries. Distroless images from Google (e.g., `gcr.io/distroless/python3`) contain no shell, no package manager, and no utilities at all -- just the language runtime. This makes them excellent for production but harder to debug.

Scan your images for known vulnerabilities using tools like Trivy or Snyk. Integrate scanning into your CI pipeline so that builds fail if critical CVEs are detected.

Never bake secrets (API keys, database passwords, tokens) into your Docker image. They persist in image layers and can be extracted. Instead, pass secrets at runtime via environment variables, mounted secret files, or a secrets manager.

Where possible, run the container filesystem as read-only (`--read-only` flag or `readOnlyRootFilesystem: true` in Kubernetes). This prevents an attacker from writing malicious files even if they gain execution.

#### .dockerignore

The `.dockerignore` file works like `.gitignore` but for Docker's build context. When you run `docker build`, Docker sends the entire build context directory to the daemon. Without a `.dockerignore`, this includes everything -- git history, local environment files, IDE configuration, dependency caches, and test data.

A well-crafted `.dockerignore` improves build speed (less data to send), reduces image size (fewer files accidentally copied), and improves security (prevents secrets or local config from leaking into images).

```
# Version control
.git
.gitignore

# Python artifacts
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
htmlcov
.coverage

# Virtual environments
venv
.venv
env

# Environment files (may contain secrets)
.env
.env.*

# IDE and editor files
.vscode
.idea
*.swp
*.swo

# Docker files (no need to include Dockerfile in the image)
Dockerfile
docker-compose*.yml
.dockerignore

# Documentation and CI
docs
README.md
.github
```

#### Health Checks

Docker health checks allow the Docker daemon to periodically test whether a container is still functioning correctly. If the health check command returns a non-zero exit code, Docker marks the container as unhealthy. Orchestrators like Docker Swarm can then automatically restart unhealthy containers. Note that plain `docker run` does not restart unhealthy containers automatically -- it only reports the status.

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

- `--interval=30s`: Check every 30 seconds.
- `--timeout=5s`: If the check takes more than 5 seconds, consider it failed.
- `--start-period=10s`: Grace period after container start during which failures are not counted (gives the app time to initialize).
- `--retries=3`: Mark as unhealthy after 3 consecutive failures.

Once the container is running, the health state surfaces in `docker ps` under the STATUS column:

```console
$ docker ps
CONTAINER ID   IMAGE       STATUS                            PORTS
9f3a1c0b2d4e   myapp       Up 2 minutes (healthy)            0.0.0.0:8000->8000/tcp
```

**How to read this output:** The `(healthy)` annotation appears only because a `HEALTHCHECK` is defined; without one the status would just read `Up 2 minutes` and Docker would have no opinion about whether your app actually works. During the `--start-period` window it shows `(health: starting)`, and after `--retries` consecutive failures it flips to `(unhealthy)`. This matters because tools downstream -- Compose's `depends_on: condition: service_healthy`, Swarm's restart logic -- key off exactly this state, so a missing or naive health check (e.g. one that only checks the port is open, not that the app can serve a request) silently defeats your self-healing.

In Kubernetes, you do not use Docker's `HEALTHCHECK`. Instead, you use Kubernetes-native probes (`livenessProbe`, `readinessProbe`, `startupProbe`), which offer more flexible configuration and integrate with the Kubernetes service mesh and scheduling system. See the Kubernetes Probes section below.

#### Networking

Docker provides several networking modes, each suited to different use cases:

**Bridge (default):** Each container gets its own network namespace with a virtual Ethernet interface connected to a Docker-managed bridge. Containers on the same bridge can communicate by IP. Port mapping (`-p 8080:8000`) exposes container ports to the host. This is the standard mode for most single-host workloads.

**Host:** The container shares the host's network stack directly. There is no network isolation. The container's ports are the host's ports with no mapping needed. This eliminates the overhead of NAT and is useful for performance-sensitive applications, but it sacrifices isolation.

**Overlay:** Enables communication between containers across multiple Docker hosts. Used in Docker Swarm mode and some Kubernetes network plugins. Traffic is encapsulated (VXLAN) so containers on different physical machines can communicate as if on the same network.

**None:** The container has no network interface. Useful for batch processing or security-sensitive workloads that should have no network access.

In Docker Compose, each service is automatically resolvable by its service name via Docker's built-in DNS. If you define a service called `postgres`, other services in the same Compose file can reach it at hostname `postgres` on its default port.

#### Volumes

Containers are ephemeral by design: when a container is removed, all data written to its writable layer is lost. Volumes provide persistent storage that survives container restarts and removals.

**Named volumes** are managed by Docker and stored in Docker's data directory (e.g., `/var/lib/docker/volumes/`). They are the recommended way to persist data because Docker handles their lifecycle, and they work on all platforms.

**Bind mounts** map a specific host directory into the container. They are commonly used in development to mount source code into a container for live reloading. They are less portable than named volumes because they depend on the host filesystem path.

**tmpfs mounts** exist only in memory and are never written to the host filesystem. They are useful for sensitive data that should not be persisted to disk (e.g., temporary credentials) or for high-performance scratch space.

```yaml
# docker-compose.yml volume examples
services:
  postgres:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data    # Named volume for persistence
    environment:
      POSTGRES_PASSWORD: secret

  app:
    build: .
    volumes:
      - ./src:/app/src                      # Bind mount for development
      - /tmp/app-cache:/app/.cache:ro       # Read-only bind mount

volumes:
  pgdata:                                   # Declares the named volume
```

#### Docker Compose Example

Docker Compose defines multi-container applications in a single YAML file. It is the standard tool for local development environments and simple deployments. Below is a production-like example for a web application with a database, cache, and reverse proxy.

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ---- Reverse Proxy ----
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      app:
        condition: service_healthy
    restart: unless-stopped

  # ---- Application ----
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime          # Use only the runtime stage
    environment:
      DATABASE_URL: postgresql://app:secret@postgres:5432/mydb
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.25"
          memory: 128M
    restart: unless-stopped

  # ---- Database ----
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: mydb
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d mydb"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "5432:5432"
    restart: unless-stopped

  # ---- Cache ----
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

This Compose file demonstrates several best practices: health check dependencies (so the app waits for postgres to be ready), resource limits, named volumes for persistence, read-only volume mounts for configuration, and a restart policy.

> **Key Takeaway:** Containerization is about reproducibility and isolation. A well-written Dockerfile uses multi-stage builds, optimizes layer caching, runs as non-root, and keeps images minimal. Docker Compose ties multiple containers together for local development. In production, graduate to Kubernetes for orchestration, scaling, and self-healing.

---

### Kubernetes

#### Pods

A Pod is the smallest deployable unit in Kubernetes. It encapsulates one or more containers that share the same network namespace (they can reach each other on `localhost`) and the same storage volumes. In practice, most Pods run a single application container, but multi-container Pods are used for specific patterns.

The **sidecar pattern** adds a helper container alongside the main container. Common sidecars include log shippers (Fluentd/Fluent Bit), service mesh proxies (Envoy/Istio), and monitoring agents. The sidecar shares the same lifecycle and network as the main container, so it can intercept traffic or read shared log files.

**Init containers** run to completion before any regular containers start. They are used for setup tasks: waiting for a database to become available, running database migrations, downloading configuration files, or populating a shared volume. If an init container fails, Kubernetes restarts the Pod.

#### Deployments

A Deployment is the standard way to run stateless applications on Kubernetes. You declare the desired state -- which container image to run, how many replicas, what resources to allocate -- and the Deployment controller continuously works to make the actual state match.

When you update the image tag or configuration, the Deployment performs a **rolling update** by default: it creates new Pods with the updated spec, waits for them to pass readiness checks, and then terminates old Pods. At no point is the service fully down. If something goes wrong, you can roll back with `kubectl rollout undo deployment/myapp`.

Watching a rollout makes the strategy concrete. With `maxSurge: 1` and `maxUnavailable: 0` (as in the manifest below), `kubectl rollout status` reports the controller bringing up one new Pod at a time:

```console
$ kubectl set image deployment/myapp myapp=registry.example.com/myapp:1.4.3 -n production
deployment.apps/myapp image updated

$ kubectl rollout status deployment/myapp -n production
Waiting for deployment "myapp" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "myapp" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "myapp" rollout to finish: 1 old replicas are pending termination...
deployment "myapp" successfully rolled out
```

**How to read this output:** Each line marks a step in the surge-and-drain dance: a new Pod is created (surge), it must pass its readiness probe before any old Pod is terminated, and only then does an old Pod drain. Because `maxUnavailable: 0`, capacity never drops below the desired 3 -- there is no availability dip during the deploy, which is exactly the guarantee an interviewer wants you to articulate. The critical dependency is the readiness probe: if it is missing or always returns 200, Kubernetes happily routes traffic to Pods that are not actually ready, and a "successful" rollout can take down production despite the green output above.

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production
  labels:
    app: myapp
    version: v1
spec:
  replicas: 3
  revisionHistoryLimit: 5          # Keep 5 old ReplicaSets for rollback
  selector:
    matchLabels:
      app: myapp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1                  # At most 1 extra Pod during update
      maxUnavailable: 0            # Never have fewer than 3 ready Pods
  template:
    metadata:
      labels:
        app: myapp
        version: v1
    spec:
      serviceAccountName: myapp-sa
      terminationGracePeriodSeconds: 60
      containers:
        - name: myapp
          image: registry.example.com/myapp:1.4.2
          ports:
            - containerPort: 8000
              protocol: TCP
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: myapp-secrets
                  key: database-url
            - name: LOG_LEVEL
              valueFrom:
                configMapKeyRef:
                  name: myapp-config
                  key: log-level
          resources:
            requests:
              cpu: 250m           # 0.25 CPU cores guaranteed
              memory: 256Mi       # 256 MiB guaranteed
            limits:
              cpu: "1"            # Throttled above 1 core
              memory: 512Mi       # OOMKilled above 512 MiB
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 2
          startupProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30   # Up to 150s to start
          volumeMounts:
            - name: config-volume
              mountPath: /app/config
              readOnly: true
      volumes:
        - name: config-volume
          configMap:
            name: myapp-config-files
```

#### Services

A Service provides a stable network endpoint for a set of Pods. Pods are ephemeral -- they come and go as Deployments scale or Nodes fail -- so you cannot rely on individual Pod IP addresses. A Service uses label selectors to dynamically discover which Pods to route traffic to, and it provides a single DNS name and IP that remains constant.

**ClusterIP** (default) exposes the Service on an internal IP reachable only within the cluster. This is what you use for internal communication between microservices.

**NodePort** opens a specific port (30000-32767) on every Node in the cluster. External traffic to any Node's IP on that port is forwarded to the Service. Useful for development or when you have your own load balancer.

**LoadBalancer** provisions a cloud load balancer (e.g., AWS NLB/ALB, GCP LB) that routes external traffic to the Service. This is the simplest way to expose a service to the internet on cloud platforms, but each LoadBalancer Service creates a separate cloud resource (and cost).

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
  namespace: production
  labels:
    app: myapp
spec:
  type: ClusterIP
  selector:
    app: myapp                  # Routes to Pods with label app=myapp
  ports:
    - name: http
      port: 80                  # Port the Service listens on
      targetPort: 8000          # Port on the Pod to forward to
      protocol: TCP
```

#### Ingress

An Ingress resource defines rules for routing external HTTP(S) traffic to Services inside the cluster. Unlike LoadBalancer Services (which are one-to-one), a single Ingress can route traffic for many domains and paths to many different backend Services. This makes it much more cost-effective and flexible for HTTP traffic.

An Ingress on its own does nothing -- you need an **Ingress Controller** (a running Pod that watches Ingress resources and configures a reverse proxy accordingly). Popular choices include ingress-nginx, Traefik, and AWS ALB Ingress Controller.

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.example.com
      secretName: api-tls-cert          # TLS certificate from cert-manager
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 80
          - path: /api/v2
            pathType: Prefix
            backend:
              service:
                name: myapp-v2
                port:
                  number: 80
    - host: admin.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-dashboard
                port:
                  number: 80
```

#### ConfigMaps and Secrets

ConfigMaps and Secrets externalize configuration from container images, enabling the same image to run with different settings in different environments (staging vs. production) without rebuilding.

**ConfigMaps** hold non-sensitive configuration: feature flags, log levels, connection pool sizes, application settings. They can be consumed as environment variables or mounted as files.

**Secrets** are structurally identical to ConfigMaps but intended for sensitive data: passwords, API keys, TLS certificates. Values are base64-encoded in the Kubernetes API but are **not encrypted at rest by default**. For real security, enable encryption at rest on the etcd cluster, or better yet, use an external secrets manager (AWS Secrets Manager, HashiCorp Vault) with an operator like External Secrets Operator that syncs external secrets into Kubernetes Secrets.

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
  namespace: production
data:
  log-level: "info"
  max-connections: "100"
  feature-new-ui: "true"
---
# configmap-files.yaml -- mount entire config files
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config-files
  namespace: production
data:
  settings.yaml: |
    server:
      workers: 4
      timeout: 30
    cache:
      ttl: 300
      max_size: 1000
---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secrets
  namespace: production
type: Opaque
data:
  database-url: cG9zdGdyZXNxbDovL2FwcDpzZWNyZXRAcG9zdGdyZXM6NTQzMi9teWRi
  # base64-encoded: postgresql://app:secret@postgres:5432/mydb
  api-key: c3VwZXItc2VjcmV0LWFwaS1rZXk=
```

Note how trivially the "secret" is recovered -- base64 is encoding, not encryption:

```console
$ echo c3VwZXItc2VjcmV0LWFwaS1rZXk= | base64 -d
super-secret-api-key
```

**How to read this output:** Anyone with `get secret` RBAC permission, or read access to an etcd backup, can decode these values in one command -- there is no key, no password, nothing to crack. This is the single most common Kubernetes security misconception in interviews: candidates assume Secrets are encrypted because they look opaque. They are not, unless you explicitly enable encryption at rest on etcd or front them with an external secrets manager. Treat a Kubernetes Secret as "kept out of the image and out of the pod spec," not as "cryptographically protected."

#### Resource Management

Every container in Kubernetes should declare resource `requests` and `limits`. Without them, a single misbehaving container can starve other workloads on the same Node.

**Requests** define the minimum resources guaranteed to the container. The Kubernetes scheduler uses requests to decide which Node has enough capacity to place the Pod. If you request 250m CPU and 256Mi memory, Kubernetes ensures the Node has at least that much available before scheduling the Pod there.

**Limits** define the maximum resources a container can use. If a container exceeds its CPU limit, it is **throttled** (slowed down). If it exceeds its memory limit, it is **OOMKilled** (terminated and restarted). Setting memory limits is critical for preventing memory leaks from taking down entire Nodes.

CPU is measured in millicores: `1000m` equals 1 full CPU core; `250m` is one quarter of a core. Memory is measured in bytes with standard suffixes: `128Mi` (mebibytes), `1Gi` (gibibytes).

Kubernetes assigns a QoS (Quality of Service) class based on how requests and limits are configured:
- **Guaranteed:** requests equal limits for all containers. Highest priority; last to be evicted under pressure.
- **Burstable:** requests set but lower than limits. Medium priority.
- **BestEffort:** no requests or limits set. Lowest priority; first to be evicted.

When a container breaches its memory limit, the symptom is unmistakable in `kubectl describe pod`:

```console
$ kubectl describe pod myapp-7d9f8c-xk2lp -n production
...
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Wed, 04 Jun 2026 10:14:02
      Finished:     Wed, 04 Jun 2026 10:41:55
    Restart Count:  4
```

**How to read this output:** `Reason: OOMKilled` with `Exit Code: 137` (128 + signal 9, SIGKILL) means the kernel's OOM killer terminated the process for exceeding the memory `limit` -- not a bug in your code per se, but a hard ceiling you set. A climbing `Restart Count` paired with OOMKilled is the textbook fingerprint of a memory leak or an undersized limit; this is one of the most common "the pod keeps restarting, why?" debugging questions in interviews and on-call. CPU pressure looks different -- there is no kill, the container is just throttled and gets slow -- which is why you almost always set a memory limit but often leave CPU limits off to avoid needless throttling.

> **Key Takeaway:** Requests drive scheduling (where a Pod can fit), limits drive enforcement (when a Pod is throttled or killed). Always set memory requests and limits to protect Nodes from leaks; set CPU requests for fair scheduling but be cautious with CPU limits, since they throttle rather than kill. The QoS class that results determines who gets evicted first when a Node runs out of resources.

#### HPA (Horizontal Pod Autoscaler)

The Horizontal Pod Autoscaler automatically adjusts the number of Pod replicas based on observed metrics. The most common metric is CPU utilization, but you can also scale on memory, custom application metrics (request rate, queue depth), or external metrics.

HPA works by periodically (default: every 15 seconds) querying the metrics API, computing the desired replica count to bring the metric to the target value, and then updating the Deployment's replica count. It scales up quickly and scales down more conservatively (with a stabilization window) to avoid flapping.

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 3
  maxReplicas: 20
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300      # Wait 5 min before scaling down
      policies:
        - type: Percent
          value: 25                        # Scale down at most 25% at a time
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 4                         # Add at most 4 pods at a time
          periodSeconds: 60
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70           # Target 70% CPU usage
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

You can watch the autoscaler make decisions with `kubectl get hpa`:

```console
$ kubectl get hpa myapp-hpa -n production
NAME        REFERENCE          TARGETS                MINPODS   MAXPODS   REPLICAS
myapp-hpa   Deployment/myapp   cpu: 84%/70%, ...      3         20        7
```

**How to read this output:** The `TARGETS` column reads `current/target`: CPU is at 84% against a 70% target, so the HPA has scaled `REPLICAS` up to 7 to drive utilization back down. When load subsides the figure will fall below 70%, but scale-down waits out the 300-second stabilization window from the manifest before removing Pods -- this asymmetry (scale up fast, scale down slow) is deliberate and prevents thrashing during spiky traffic. A frequent gotcha surfaces here: if `TARGETS` shows `<unknown>`, the metrics-server is not installed or the Pods have no CPU `requests`, and the HPA cannot compute a percentage at all -- autoscaling silently does nothing.

For event-driven workloads (scaling based on Kafka lag, SQS queue depth, cron schedules), KEDA (Kubernetes Event-Driven Autoscaling) extends the HPA with a rich set of scalers and can even scale to zero replicas.

#### Probes

Probes are Kubernetes's mechanism for understanding the health of your application. There are three types, each serving a distinct purpose:

**Liveness Probe:** Answers "Is this container alive?" If the liveness probe fails repeatedly (exceeding `failureThreshold`), Kubernetes kills the container and restarts it. Use this to detect deadlocks, infinite loops, or corrupted state. The liveness check should be lightweight -- do not make it depend on external services (like a database), or a database outage will cause cascading restarts of your application.

**Readiness Probe:** Answers "Is this container ready to accept traffic?" If the readiness probe fails, Kubernetes removes the Pod from Service endpoints (so no traffic is routed to it) but does **not** restart it. Use this when your app needs to warm up caches, load large models into memory, or when it is temporarily unable to serve (e.g., the database connection pool is exhausted).

**Startup Probe:** Answers "Has this container finished starting up?" Until the startup probe succeeds, the liveness and readiness probes are not activated. This is essential for slow-starting applications (e.g., Java apps or ML model servers) that might fail liveness checks during their normal startup time.

Probes can use three mechanisms: HTTP GET (returns 200-399), TCP socket (connection succeeds), or exec (command returns exit code 0).

```yaml
# Probe examples within a container spec
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 15     # Wait 15s before first check
  periodSeconds: 20            # Check every 20s
  timeoutSeconds: 3            # Timeout after 3s
  failureThreshold: 3          # Restart after 3 consecutive failures
  successThreshold: 1          # 1 success to be considered alive

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 2          # Remove from service after 2 failures
  successThreshold: 1

startupProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 30         # 30 * 5s = 150s max startup time
```

#### StatefulSets

StatefulSets are designed for applications that need stable, persistent identity: databases (PostgreSQL, MySQL), distributed systems (Kafka, ZooKeeper, Cassandra), and other stateful workloads.

Unlike Deployments, where Pods are interchangeable, StatefulSet Pods have:
- **Stable network identity:** Each Pod gets a predictable hostname like `mydb-0`, `mydb-1`, `mydb-2`, accessible via a Headless Service.
- **Ordered deployment and scaling:** Pods are created in order (0, 1, 2...) and terminated in reverse order (2, 1, 0). This is critical for leader election and data replication protocols.
- **Persistent Volume per Pod:** Each Pod gets its own PersistentVolumeClaim that follows the Pod across rescheduling. If `mydb-1` is rescheduled to a different Node, it reattaches the same volume.

#### DaemonSets

A DaemonSet ensures that exactly one copy of a Pod runs on every Node in the cluster (or a subset of Nodes matching a nodeSelector). When a new Node joins the cluster, the DaemonSet automatically schedules a Pod on it; when a Node is removed, the Pod is garbage collected.

Common use cases include log collectors (Fluent Bit, Filebeat), monitoring agents (Prometheus Node Exporter, Datadog Agent), network plugins (Calico, Cilium), and storage drivers (CSI node plugins).

#### RBAC

Role-Based Access Control (RBAC) in Kubernetes restricts who can do what within the cluster. It follows the principle of least privilege: users and service accounts should have only the permissions they need.

**Role** defines permissions (which API verbs on which resources) within a specific namespace. **ClusterRole** defines permissions cluster-wide. **RoleBinding** assigns a Role to a user or service account within a namespace. **ClusterRoleBinding** assigns a ClusterRole cluster-wide.

For example, your CI/CD service account might need permission to create and update Deployments in the `production` namespace but nothing else. Your monitoring agent might need read-only access to Pods and Nodes across all namespaces.

#### Network Policies

Network Policies are firewall rules for pod-to-pod traffic. By default, all Pods in a Kubernetes cluster can communicate with each other. Network Policies allow you to restrict this, implementing a "default deny" posture where only explicitly allowed traffic flows.

This is critical for security: if one service is compromised, the attacker cannot freely probe all other services in the cluster. You can restrict traffic by namespace, by Pod label, by port, and by IP block.

Note that Network Policies require a CNI plugin that supports them (Calico, Cilium, Weave). The default kubenet does not enforce Network Policies.

> **Key Takeaway:** Kubernetes provides a declarative, self-healing platform for running containerized applications at scale. The core abstractions -- Pods, Deployments, Services, Ingress -- handle networking, scaling, and rolling updates. ConfigMaps/Secrets externalize configuration, HPA provides autoscaling, and probes ensure traffic only reaches healthy instances. Always set resource requests/limits, always configure probes, and always use RBAC and Network Policies for security.
