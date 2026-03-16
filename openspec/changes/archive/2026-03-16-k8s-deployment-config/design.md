## Context

The autodoc-adk application consists of these runtime components:

1. **API server** (FastAPI) — serves REST endpoints, triggers jobs, proxies Prefect status
2. **Prefect API server** — orchestration API + UI, backed by PostgreSQL and Redis
3. **Prefect background services** — schedulers, event handlers, and background workers (singleton)
4. **Prefect workers** — poll work pools and launch flow runs as K8s Jobs
5. **Flow runners** — heavyweight pods (AI/LLM libs) that execute documentation generation flows
6. **Redis** — required by Prefect 3 for messaging, caching, event ordering, and lease storage

Currently deployed via Docker Compose (`deployment/`) with three Docker images:
- `Dockerfile.api` — lightweight FastAPI
- `Dockerfile.worker` — Prefect worker (polls work pools, needs `prefect-kubernetes` for K8s pools)
- `Dockerfile.flow` — heavy flow runner with all AI dependencies + source code

Three deployment profiles are supported:
1. **dev** — All services via Docker Compose (PostgreSQL, Redis, Prefect, API, Worker)
2. **dev-k8s** — PostgreSQL + Redis via Docker, application components on K8s
3. **prod** — Full K8s, external managed PostgreSQL and Redis

The Kubernetes cluster must be 1.23+ for TTL controller GA support.

## Goals / Non-Goals

**Goals:**
- Deploy all application components (API, Prefect API, Prefect background services, workers) in a `autodoc` K8s namespace
- Add Redis as a required Prefect 3 dependency across all deployment profiles
- Split Prefect server into scalable API + singleton background services
- Enable Prefect to launch flow runs as isolated K8s Jobs with proper resource limits
- Implement differential Job cleanup: succeeded Jobs cleaned within 10 minutes, failed Jobs retained 24 hours
- Refactor `_submit_flow()` to use `run_deployment()` for K8s environments
- Retries re-execute entire flow (task result caching deferred until shared storage is provisioned)
- Provide Ingress for API and Prefect UI with TLS support
- Support three deployment profiles via Kustomize overlays and Docker Compose
- Keep manifests CI-ready (image tags parameterized, secrets externalized)

**Non-Goals:**
- In-cluster PostgreSQL deployment (external managed DB in prod, Docker in dev)
- CI/CD pipeline configuration (manifests are CI-ready but pipeline definition is separate)
- Horizontal Pod Autoscaling (can be added later; initial deployment uses fixed replicas)
- Service mesh (Istio/Linkerd) integration
- Monitoring/alerting stack deployment (OpenTelemetry collector, Grafana, etc.)
- Database migration management (handled by separate process in prod)
- Shared workspace storage (NFS, S3) — each Job clones independently into emptyDir
- `cleanup_orphan_workspaces` in K8s — emptyDir auto-cleans; scheduled flow is dev Docker Compose only

## Decisions

### D1: Namespace isolation

**Decision**: All K8s resources deployed in a dedicated `autodoc` namespace.

**Rationale**: Provides resource quota boundaries, RBAC isolation, and clean multi-tenant separation. Network policies can be scoped to the namespace.

**Alternatives considered**:
- Shared namespace with labels: Rejected — weaker isolation, harder to apply resource quotas per-application.

### D2: Redis for Prefect 3

**Decision**: Add Redis 7 as a required component for Prefect 3 server. In dev, Redis runs in Docker Compose. In dev-k8s, Redis runs in Docker alongside PostgreSQL. In prod, Redis is an external managed service (ElastiCache, Memorystore, etc.) configured via K8s Secrets.

**AMENDED**: Redis is added to the dev `docker-compose.yml`, but the Prefect server in dev uses `prefecthq/prefect:3-python3.11` in combined mode **without** Redis env vars. The `3-latest` image bundles asyncpg 0.30+ which defaults to SSL and fails against the local PostgreSQL container (which does not have SSL configured). In K8s deployments, `3-latest` is used with Redis. Redis still runs in dev Docker Compose for the dev-k8s profile (infrastructure-only), where K8s-deployed Prefect components connect to it.

**Rationale**: Prefect 3's official self-hosted deployment requires Redis for:
- `PREFECT_MESSAGING_BROKER: prefect_redis.messaging`
- `PREFECT_MESSAGING_CACHE: prefect_redis.messaging`
- `PREFECT_SERVER_EVENTS_CAUSAL_ORDERING: prefect_redis.ordering`
- `PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE: prefect_redis.lease_storage`

Without Redis, Prefect 3 server cannot function correctly for event processing and background services. However, in dev Docker Compose the combined-mode Prefect server operates without Redis using in-process alternatives.

**Alternatives considered**:
- In-cluster Redis for all profiles: Rejected — production should use managed services for reliability and operational simplicity.
- Skip Redis (use Prefect without it): Not viable for K8s/prod — Prefect 3 requires it for split API + background services mode.

### D3: Prefect server split — API + Background Services

**Decision**: Split Prefect server into two separate K8s Deployments:
1. **prefect-api** (scalable, replicas configurable): `prefect server start --no-services` (with `PREFECT_SERVER_API_HOST=0.0.0.0` env var)
2. **prefect-background-services** (singleton, replicas=1): `prefect server services start`

Both require Redis and PostgreSQL env vars. The API serves the UI and REST endpoints. Background services handle scheduling, event processing, and other async work.

**Rationale**: This is the official Prefect 3 production deployment pattern. The `--no-services` flag separates the API (stateless, horizontally scalable) from background workers (stateful, must be singleton). Using a single combined process (`prefect server start` without `--no-services`) works for dev but doesn't scale.

**Alternatives considered**:
- Single combined Deployment: Works for dev Docker Compose but prevents horizontal scaling of the API in K8s.
- Sidecar pattern: Couples API and services lifecycle, prevents independent scaling.

### D4: Three deployment profiles

**Decision**: Support three deployment profiles:

```
Profile 1: dev (Docker Compose only)
┌─────────────────────────────────────────────────────┐
│ docker-compose.yml                                  │
│ ┌────────┐ ┌───────┐ ┌──────────────┐ ┌──────────┐│
│ │Postgres│ │ Redis │ │Prefect Server│ │   API    ││
│ │        │ │       │ │(combined)    │ │          ││
│ └────────┘ └───────┘ │+ bg services │ └──────────┘│
│                      └──────────────┘ ┌──────────┐│
│                      ┌──────────────┐ │  Worker  ││
│                      │Prefect Worker│ │(local-dev││
│                      │(local-dev)   │ │  pool)   ││
│                      └──────────────┘ └──────────┘│
└─────────────────────────────────────────────────────┘

Profile 2: dev-k8s (hybrid)
┌─────────────────────────┐  ┌────────────────────────────┐
│ Docker Compose (infra)  │  │ Kubernetes (autodoc ns)    │
│ ┌────────┐ ┌──────────┐│  │ ┌─────────────────────────┐│
│ │Postgres│ │  Redis   ││  │ │ Prefect API (--no-svc)  ││
│ └────────┘ └──────────┘│  │ │ Prefect BG Services     ││
│                         │  │ │ Orchestrator Worker     ││
│                         │  │ │ Scope Worker            ││
│                         │  │ │ API Server              ││
│                         │  │ │ Ingress                 ││
│                         │  │ └─────────────────────────┘│
└─────────────────────────┘  └────────────────────────────┘

Profile 3: prod (full K8s)
┌──────────────────────┐  ┌────────────────────────────────┐
│ External Managed     │  │ Kubernetes (autodoc ns)        │
│ ┌────────┐           │  │ ┌───────────────────────────┐  │
│ │Cloud DB│ (Postgres)│  │ │ Prefect API (replicas: 2+)│  │
│ └────────┘           │  │ │ Prefect BG Services (1)   │  │
│ ┌────────┐           │  │ │ Orchestrator Worker       │  │
│ │Managed │ (Redis)   │  │ │ Scope Worker              │  │
│ │Redis   │           │  │ │ API Server (replicas: 2+) │  │
│ └────────┘           │  │ │ Ingress + TLS             │  │
│                      │  │ │ Job Cleanup CronJob       │  │
│                      │  │ └───────────────────────────┘  │
└──────────────────────┘  └────────────────────────────────┘
```

**Rationale**: Three profiles cover the full development lifecycle:
- **dev**: Fast iteration, no K8s required. Docker Compose with Prefect in combined mode.
- **dev-k8s**: Test K8s deployment locally (minikube/kind) while keeping infra lightweight in Docker.
- **prod**: Full production deployment with managed external services.

**Alternatives considered**:
- Two profiles only (dev + prod): Rejected — no way to test K8s deployment without also provisioning managed services.
- Everything in K8s for all profiles: Rejected — overly complex for local development.

### D5: Two Prefect workers for two work pools

**Decision**: Deploy two separate Prefect worker Deployments — one for `orchestrator-pool` and one for `k8s-pool`.

**Rationale**: Matches the existing `prefect.yaml` architecture that uses separate pools to prevent deadlock (orchestrators waiting on scope workers in the same pool). Each worker polls exactly one pool. The orchestrator worker has lower concurrency (limit 10) while the scope worker has higher concurrency (limit 50).

**Alternatives considered**:
- Single worker polling multiple pools: Rejected — Prefect workers poll one pool each. Multiple `--pool` flags are not supported in Prefect 3.
- Single pool with priority: Rejected — creates deadlock risk when orchestrator Jobs consume all slots.

### D6: K8s Job templates via Prefect work pool base job template

**Decision**: Configure the `orchestrator-pool` and `k8s-pool` work pools with base job templates (JSON) that encode:
- Container image (Flow Runner image with commit SHA tag)
- Resource requests/limits
- TTL cleanup policy (`ttlSecondsAfterFinished: 86400`)
- Service account, namespace, labels
- `emptyDir` volume mount at `/tmp/autodoc-workspaces`
- Environment variables from ConfigMap + Secrets

**AMENDED**: Prefect's KubernetesWorker imposes specific requirements on the base job template:
- `completions: 1` and `parallelism: 1` MUST be set in the Job spec (validation fails without them)
- Container name MUST be `prefect-job` (not configurable — the worker looks for this name to inject environment and command overrides)
- `namespace` MUST be set at the `job_configuration` level (not just `job_manifest.metadata.namespace`) — the worker reads the config-level field to determine where to create Jobs
- `imagePullPolicy: IfNotPresent` MUST be set when using `:latest` tags with locally-built images (K8s defaults to `Always`, which fails for images not in a remote registry)

**Chosen cleanup approach**: Set `ttlSecondsAfterFinished: 86400` as the default in the base job template (all Jobs retained 24h as fail-safe). Deploy a `job-cleanup` CronJob (runs every 5 minutes) that deletes succeeded Jobs older than 5 minutes. This achieves: success = cleaned up quickly, failure = retained 24 hours.

**Rationale**: The K8s TTL controller applies a single TTL value regardless of success/failure. To get differential behavior, we need a cleanup mechanism for the success case while letting the TTL controller handle the failure case.

Templates are applied via `prefect work-pool create --base-job-template ./template.json` and stored in the repo at `deployment/k8s/job-templates/`.

**Alternatives considered**:
- Single TTL value for all Jobs: Rejected — can't differentiate success/failure retention.
- Prefect-managed cleanup: Rejected — Prefect doesn't manage K8s Job resources after creation.
- Finalizer-based approach: Rejected — overly complex for this use case.

### D7: External PostgreSQL and Redis via Secrets

**Decision**: In prod, both PostgreSQL and Redis connection parameters are stored in K8s Secrets:
- `autodoc-db-credentials` — `DATABASE_URL` and `PREFECT_API_DATABASE_CONNECTION_URL`
- `autodoc-redis-credentials` — `PREFECT_REDIS_MESSAGING_HOST`, `PREFECT_REDIS_MESSAGING_PORT`

In dev-k8s, these secrets point to Docker Compose services via host networking or NodePort.

**Rationale**: Secrets allow rotation without manifest changes and keep credentials out of ConfigMaps and source control.

**Alternatives considered**:
- ConfigMap for connection strings: Rejected — contains credentials.
- External Secrets Operator: Good addition but not a hard dependency; manifests use plain Secrets.

### D8: Ingress with configurable class

**Decision**: Single Ingress resource with two hosts/paths:
- `api.<domain>` → API service (port 8080)
- `prefect.<domain>` → Prefect API service (port 4200)

Ingress class configurable via `ingressClassName`. TLS via cert-manager annotation or pre-provisioned secret.

**Alternatives considered**:
- Separate Ingress per service: Unnecessary complexity for two services.
- LoadBalancer services: Wastes external IPs, less flexible for TLS/routing.

### D9: Kustomize over Helm

**Decision**: Use Kustomize with base + overlays rather than Helm charts.

**Rationale**: Kustomize is built into kubectl, requires no additional tooling, and is simpler for configuration that's primarily about value substitution and patches.

**Alternatives considered**:
- Helm chart: More powerful but adds tooling dependency and template complexity for modest benefit here.
- Raw manifests with envsubst: Too fragile, no merge semantics.

### D10: RBAC for Prefect workers

**Decision**: Create a ServiceAccount (`prefect-worker`) with a Role granting permissions to create, get, list, watch, and delete Jobs, Pods, and Pod logs in the `autodoc` namespace. Both worker Deployments use this ServiceAccount.

**Rationale**: Prefect workers need to create K8s Jobs (for flow runs), watch their status, and read logs. Namespace-scoped Role (not ClusterRole) follows least-privilege.

### D11: Retry via run_deployment()

**Decision**: Refactor the application's `_submit_flow()` function to use Prefect's `run_deployment()` when running in K8s environments (`AUTODOC_FLOW_DEPLOYMENT_PREFIX` is `dev-k8s` or `prod`). In dev mode (prefix `dev`), keep direct in-process invocation for simplicity.

Retries re-execute the entire flow from scratch. Task result caching (via `cache_policy=INPUTS + TASK_SOURCE`) is deferred to a future change — it requires shared result storage (S3/GCS) since K8s Jobs use ephemeral emptyDir volumes and cached results are lost when the pod terminates.

**Rationale**:
1. The current `_submit_flow()` uses `asyncio.create_task()` to invoke flows directly in-process. This works in Docker Compose (API and flows share the same Python process) but not in K8s where flows must run as separate Jobs dispatched by Prefect workers.
2. Prefect's retry re-runs the **entire flow from scratch** — there is no native "resume from last successful task." Full re-execution is acceptable for now; task caching can be added later when shared storage is provisioned.

**Alternatives considered**:
- Always use `run_deployment()`: Would break the simple dev Docker Compose workflow.
- Task result caching now: Requires shared result storage backend (S3/GCS) which adds infrastructure dependency. Deferred to keep this change focused on K8s deployment.

### D12: Worker image with prefect-kubernetes

**Decision**: Add `pip install prefect-kubernetes` to `Dockerfile.worker` so that the worker can manage K8s Jobs for the `kubernetes` work pool type.

**Rationale**: The base Prefect image does not include the `prefect-kubernetes` integration. Without it, workers cannot create K8s Jobs when polling kubernetes-type work pools.

**Alternatives considered**:
- Build a custom image from scratch: Overkill — a single `pip install` suffices.

### D12b: Prefect server image

**Decision**: Use `prefecthq/prefect:3-latest` for Prefect API server and background services K8s Deployments (in `base/prefect/`). The `3-latest` tag bundles `prefect-redis`, which is required for Redis messaging. The worker Dockerfile continues to extend the base image with `pip install prefect-kubernetes`.

**AMENDED**: In dev Docker Compose, use `prefecthq/prefect:3-python3.11` (not `3-latest`) due to asyncpg SSL incompatibility. The `3-latest` image includes asyncpg 0.30+ which defaults to SSL connections, and the local Docker PostgreSQL container does not have SSL configured. This causes connection failures. The `3-python3.11` image uses an older asyncpg that does not default to SSL. In K8s deployments (`base/prefect/`), `3-latest` is used because the PostgreSQL connection can be configured with appropriate SSL settings or the managed database supports SSL. The worker Dockerfile (`Dockerfile.worker`) extends `3-python3.11` (not `3-latest`) for the same asyncpg compatibility reason.

**Rationale**: The `3-python3.11` tag does NOT include `prefect-redis`. Without it, Prefect cannot connect to Redis for messaging/caching. The `3-latest` tag (Python 3.12) includes `prefect-redis` out of the box. Python 3.12 is compatible with our codebase (we require 3.11+). However, the asyncpg version bundled in `3-latest` breaks local dev PostgreSQL connectivity.

### D12c: CLONE_DIR must match emptyDir mount point

**Decision**: The `autodoc-config` ConfigMap SHALL set `CLONE_DIR=/tmp/autodoc-workspaces` to match the emptyDir volume mount point in the Job templates. This ensures `tempfile.mkdtemp(prefix="autodoc_", dir=CLONE_DIR)` creates directories inside the emptyDir volume, not in the container's ephemeral root filesystem.

**Rationale**: If `CLONE_DIR` is empty (system temp), cloned repos would be written to `/tmp` on the container filesystem instead of the emptyDir volume mount. While both are ephemeral, the emptyDir has explicit size limits and is the intended workspace volume.

### D12d: dev-k8s prefix and Prefect deployments

**Decision**: The dev-k8s profile uses `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev-k8s`. New `dev-k8s-*` deployments are added to `prefect.yaml` targeting `orchestrator-pool` and `k8s-pool` work pools. This ensures `_submit_flow()` uses `run_deployment()` (since prefix is not `dev`) and the deployments route to K8s work pools (not `local-dev`).

Prefect deployment names:
- `dev-k8s-full-generation` → `orchestrator-pool`
- `dev-k8s-scope-processing` → `k8s-pool`
- `dev-k8s-incremental` → `orchestrator-pool`

**Rationale**: The dispatch logic checks `AUTODOC_FLOW_DEPLOYMENT_PREFIX != "dev"`. If dev-k8s used the `dev` prefix, flows would run in-process via `asyncio.create_task()` inside the API pod — which doesn't have flow runner dependencies and defeats the purpose of K8s testing.

### D13: Per-Job clone with emptyDir — no shared storage

**Decision**: Each flow runner K8s Job clones the repository independently into an `emptyDir` volume. No shared filesystem (NFS, PVC) or object storage relay (S3) is used. The `emptyDir` volume is automatically cleaned up when the pod terminates.

**AMENDED**: Scope processing runs **in-process** within the orchestrator K8s Job for ALL deployment profiles. The original design of dispatching scopes as separate K8s Jobs via `run_deployment()` does not work because `run_deployment()` returns a `FlowRun` status object, not the flow's return value (`ScopeProcessingResult`). Cross-Job result serialization would require shared storage infrastructure (S3, Redis) that is not yet provisioned. This is deferred to a future change. Since scope processing runs in-process, only the orchestrator Job clones the repository, and the scope processing flow receives the local `repo_path` directly (no re-clone needed).

```
Orchestrator Job (emptyDir)
┌──────────────────────────────────────────┐
│ clone_repository()                       │
│   └→ /tmp/autodoc_xxx/                   │
│                                          │
│ discover_autodoc_configs                 │
│   └→ [scope_a, scope_b]                 │
│                                          │
│ scope_processing_flow(scope_a, repo_path)│  ← in-process
│ scope_processing_flow(scope_b, repo_path)│  ← in-process
│                                          │
│ results available directly (same process)│
│ pod dies → emptyDir gone                 │
└──────────────────────────────────────────┘
```

The orchestrator clones the repo once. Scope processing runs in-process within the same pod, sharing the cloned repository via the local filesystem path. No duplicate cloning occurs.

**Workspace lifecycle is fully managed by K8s**: pod termination deletes the emptyDir. The `cleanup_workspace()` call in flow `finally` blocks remains as belt-and-suspenders. The `cleanup_orphan_workspaces` scheduled Prefect flow is **not deployed to K8s** — it is only used in the dev Docker Compose profile where pods don't manage lifecycle.

**Rationale**: emptyDir is the simplest, most performant, and most reliable option. No infrastructure dependencies (NFS, S3), no shared state between pods, no cleanup mechanisms needed. In-process scope processing eliminates the need for cross-Job result transfer and duplicate clones. Research showed NFS performs poorly for git workloads (many small files) and S3 FUSE mounts are fundamentally incompatible with git operations.

**Alternatives considered**:
- Separate K8s Jobs per scope via `run_deployment()`: Original design — rejected because `run_deployment()` returns `FlowRun` status, not flow return values. Requires shared result storage to transfer `ScopeProcessingResult` between Jobs. Deferred to future change.
- Shared RWX PVC (NFS/EFS): Rejected — poor performance for git clone (many small files), single point of failure, AWS EFS docs explicitly warn against git workloads.
- S3 relay (tar + upload + download): Rejected — unnecessary complexity for 1-3 scopes. Adds S3 dependency.
- In-cluster NFS server: Rejected — single point of failure, reported performance regressions, data loss risk.

### D14: Database migration — out of scope

**Decision**: Prefect database migrations in prod are handled by a separate, isolated process outside this change's scope. For dev Docker Compose, `PREFECT_API_DATABASE_MIGRATE_ON_START` can remain as auto-migrate is safe with a single server instance.

For K8s deployments, set `PREFECT_API_DATABASE_MIGRATE_ON_START=false`. Migrations are a prerequisite managed by the deployment pipeline.

**Rationale**: Production DB migrations should not be coupled to application startup — they need careful sequencing, rollback plans, and may involve schema changes that require coordination.

### D15: Baked-image deployment pattern (NEW)

**Decision**: Flow code is baked into the `autodoc-flow` Docker image at build time. The `prefect.yaml` uses `build: []` (skip Prefect image build) and a top-level `pull: [set_working_directory: {directory: /app}]` step to tell workers where code lives inside the container. Deployments set `job_variables.image` via the `AUTODOC_FLOW_IMAGE` env var. This eliminates the need for remote code storage (Git, S3) at runtime.

**Rationale**: K8s Jobs run in isolated pods without access to the source repository or shared filesystem. Baking code into the image ensures the flow code is available at a known path (`/app`) without requiring git clone, S3 download, or volume mounts at flow startup time. The `set_working_directory` pull step is Prefect's mechanism for telling the worker where to find flow code when it's already present in the image.

**Deployment command**: Use `prefect deploy -n <name>` (selective) rather than `--all` to avoid deploying flows for profiles that are not active.

### D16: Venv relocation fix (NEW)

**Decision**: Both `Dockerfile.api` and `Dockerfile.flow` create the Python virtual environment at `/app/.venv` (the final runtime path) using `UV_PROJECT_ENVIRONMENT=/app/.venv`. Previously the venv was built at `/build/.venv` in a builder stage and copied to `/app/.venv`, which broke all shebangs (they hardcoded `/build/.venv/bin/python`). Entrypoints use `python -m` invocation as an additional safety measure against shebang issues.

**Rationale**: Python virtual environments are not relocatable by default. Shebangs in installed scripts (e.g., `#!/build/.venv/bin/python`) break when the venv is moved to a different path. Building the venv at the final path from the start avoids this class of errors entirely.

### D17: MCP server pre-installed in flow runner image (NEW)

**Decision**: `@modelcontextprotocol/server-filesystem` is pre-installed globally in the flow runner image via `npm install -g`. Previously, `npx -y` downloaded the package at runtime, which fails in K8s pods without internet access (or in air-gapped environments).

**Rationale**: K8s Jobs may run in network-restricted environments. Pre-installing the MCP server ensures it is available without runtime network access. Global installation via `npm install -g` makes the binary available on `PATH` without needing `npx`.

### D18: Secret management via apply-secrets.sh (NEW)

**Decision**: API key secrets are loaded from the gitignored `.env` file via `deployment/k8s/scripts/apply-secrets.sh`. The script uses `kubectl create secret --dry-run=client -o yaml | kubectl apply -f -` to create/update secrets without committing values to git. The `base/secrets/api-keys.yaml` retains `CHANGE_ME` placeholders as documentation of the required keys.

**Rationale**: Secrets must not be committed to source control. The `--dry-run=client -o yaml | kubectl apply -f -` pattern is idempotent (creates or updates) and avoids "already exists" errors. The `.env` file is gitignored and contains the actual secret values. The placeholder YAML in base serves as a template showing which keys are expected.

### D19: PREFECT_UI_API_URL for dev-k8s dashboard (NEW)

**Decision**: The dev-k8s overlay patches the Prefect API deployment with `PREFECT_UI_API_URL=http://localhost:4200/api`. This tells the browser-side Prefect dashboard JavaScript to reach the API via the port-forwarded localhost URL instead of the in-cluster service hostname.

**Rationale**: The Prefect dashboard is a single-page application that makes API calls from the user's browser. Without this setting, the dashboard JavaScript would attempt to reach the Prefect API via the in-cluster hostname (e.g., `http://prefect-api:4200/api`), which is unreachable from the developer's browser. Setting `PREFECT_UI_API_URL` to `http://localhost:4200/api` ensures the browser-side requests go through `kubectl port-forward`.

### D20: Prefect client/server version alignment (NEW)

**Decision**: The Prefect client version in the flow runner image MUST match the Prefect server version. Both must be pinned to the same version.

**Rationale**: A version mismatch between the Prefect client (in the flow runner image) and the Prefect server causes 422 errors when creating task runs. This happens because serialization formats differ between versions — the server rejects payloads from a client running a different version. Pinning both to the same version prevents these errors.

## Risks / Trade-offs

**[Risk] TTL controller race condition** → The cleanup CronJob runs every 5 minutes, so successful Jobs may persist up to ~10 minutes. Acceptable trade-off vs. complexity of event-driven cleanup.

**[Risk] Work pool base job template drift** → Base job templates are configured in Prefect (not in K8s manifests). If someone modifies them via Prefect UI, they'll drift from the intended configuration. → Mitigation: Provide templates as JSON files in the repo; apply via setup script in CI/CD.

**[Risk] Resource exhaustion from parallel scope processing** → A large monorepo with many scopes could exhaust orchestrator pod resources since scopes run in-process (D13 AMENDED). → Mitigation: Orchestrator pod resource limits prevent node exhaustion. Work pool concurrency limit (10 for orchestrator-pool) bounds concurrent orchestrator Jobs. Future change to fan out scope processing to separate K8s Jobs would distribute load.

**[Risk] Redis single point of failure** → In dev-k8s profile, Redis runs in Docker without persistence. → Mitigation: Acceptable for dev. Prod uses managed Redis with replication.

**[Risk] Prefect background services singleton** → Only one instance of `prefect server services start` should run. Multiple instances could cause duplicate event processing. → Mitigation: K8s Deployment with `replicas: 1`. Could add leader election if needed later.

**[Risk] Image pull latency for Flow Runner** → The flow runner image is large (~2GB with AI libs + Node.js). → Mitigation: Use image pull policy `IfNotPresent` for tagged images. Consider image caching for production clusters.

**[Risk] dev-k8s networking** → K8s pods need to reach Docker Compose services (PostgreSQL, Redis) running on the host. → Mitigation: Use host.docker.internal (Docker Desktop) or host network mode. Document platform-specific setup.

**[Trade-off] Three profiles add complexity** → More configuration surfaces to maintain. But each profile serves a distinct purpose in the development lifecycle.

**[Trade-off] `run_deployment()` conditional logic** → `_submit_flow()` branches on deployment prefix. Simple `if/else` but adds a code path to test.

**[Trade-off] Retry re-executes entire flow** → Without task result caching, retries redo all work including previously succeeded pages. Acceptable for 1-3 scopes per repo. Can be optimized later with shared result storage + `cache_policy=INPUTS + TASK_SOURCE`.

**[Risk] Prefect client/server version mismatch** → Different Prefect versions between the flow runner image and the Prefect server cause 422 errors on task run creation due to serialization format differences (D20). → Mitigation: Pin both to the same version and validate in CI.

**[Risk] asyncpg SSL incompatibility in dev** → The `prefecthq/prefect:3-latest` image bundles asyncpg 0.30+ which defaults to SSL, breaking connections to local PostgreSQL without SSL (D2, D12b AMENDED). → Mitigation: Use `3-python3.11` image for dev Docker Compose and worker Dockerfile.

**[Trade-off] In-process scope processing limits parallelism** → Scope processing runs sequentially within the orchestrator pod (D13 AMENDED) rather than as parallel K8s Jobs. → Acceptable for 1-3 scopes per repo. Fan-out to separate K8s Jobs deferred until cross-Job result serialization is solved.

**[Trade-off] Baked image requires rebuild for code changes** → Flow code is baked into the Docker image (D15), so any code change requires an image rebuild + redeploy. → Acceptable for CI/CD workflows. Dev Docker Compose uses volume mounts for hot reload.

## Migration Plan

1. **Update Docker Compose** — Add Redis, update Prefect server to use `3-python3.11` in combined mode (without Redis env vars) for dev.
2. **Update Dockerfiles** — Add `prefect-kubernetes` to worker. Fix venv relocation in api and flow images (D16). Pre-install MCP server in flow image (D17). Ensure Prefect client version matches server (D20).
3. **Refactor `_submit_flow()`** — Add `run_deployment()` path for K8s.
4. **Build Docker images** — Build api, worker, and flow images. Tag with commit SHA for prod, `latest` for dev-k8s.
5. **Apply secrets** — Run `deployment/k8s/scripts/apply-secrets.sh` to load API keys from `.env` into K8s Secrets (D18). Must be done before deploying.
6. **Provision external services** (prod) — PostgreSQL + Redis.
7. **Apply K8s manifests** — `kubectl apply -k deployment/k8s/overlays/dev-k8s` or `deployment/k8s/overlays/prod`.
8. **Configure Prefect work pools** — Create pools with base job templates (respecting D6 AMENDED requirements: `completions`, `parallelism`, container name `prefect-job`, config-level `namespace`, `imagePullPolicy`).
9. **Set up port-forwards** (dev-k8s) — `kubectl port-forward` for Prefect API (4200) and application API (8080). Required for dashboard access (D19).
10. **Deploy Prefect flows** — `prefect deploy -n <name>` (selective, NOT `--all`) with appropriate `AUTODOC_FLOW_DEPLOYMENT_PREFIX` (D15).
11. **Verify** — Create a test job via API, observe K8s Job creation, in-process scope processing, and cleanup.

**Rollback**: Delete namespace (`kubectl delete namespace autodoc`) removes all K8s resources. Database and Redis are external and unaffected.

## Open Questions

1. **Image registry**: Which container registry (ECR, GCR, Docker Hub, GHCR)? Manifests use a placeholder `IMAGE_REGISTRY` variable.
2. **TLS certificates**: cert-manager with Let's Encrypt, or pre-provisioned certificates?
3. **Resource limits**: What are appropriate CPU/memory limits for the flow runner pods? Initial estimates: 2 CPU / 4Gi for orchestrator, 4 CPU / 8Gi for scope workers (AI inference is memory-intensive).
4. **Node pool affinity**: Should flow runner Jobs target specific node pools (e.g., high-memory nodes)?
