## Why

The autodoc-adk application currently has Docker Compose deployment only, suitable for local development and single-host environments. To run in production with proper isolation, scalability, and operational resilience, the application needs Kubernetes-native deployment configuration. Each documentation generation job (full or incremental) must run as an isolated K8s Job with automatic cleanup on success and 24-hour retention on failure for debugging and retry.

## What Changes

- **New K8s manifests** for all application components: API server, Prefect API server, Prefect background services, Prefect workers, and Redis — deployed in a dedicated `autodoc` namespace.
- **Redis for Prefect 3**: Prefect 3 requires Redis for messaging, caching, event ordering, and lease storage. Redis runs in Docker for dev and dev-k8s profiles and is configured as an external managed service for production.
- **Prefect server split**: Prefect server is split into two K8s Deployments: API server (`--no-services`, horizontally scalable) and background services (`services start`, singleton).
- **K8s Job-based flow execution**: Orchestrator flows (full_generation, incremental_update) run as K8s Jobs in `orchestrator-pool`; each scope_processing_flow fans out as a separate K8s Job in `k8s-pool` via Prefect's `run_deployment()`.
- **TTL-based Job lifecycle**: Failed Jobs are retained for 24 hours (`ttlSecondsAfterFinished: 86400`). A CronJob cleans up succeeded Jobs every 5 minutes.
- **Retry API refactor**: `_submit_flow()` updated to use `run_deployment()` for K8s environments (switchable via `AUTODOC_FLOW_DEPLOYMENT_PREFIX`). Retries re-execute the entire flow from scratch (task result caching deferred to a future change when shared storage is provisioned).
- **Ingress configuration**: Standard K8s Ingress resources for API and Prefect UI with configurable ingress class and TLS support.
- **Three deployment profiles**: (1) dev — all Docker Compose, (2) dev-k8s — Docker for PostgreSQL/Redis + K8s for application, (3) prod — full K8s with external managed PostgreSQL and Redis.
- **Docker Compose updates**: Add Redis to existing Docker Compose files. Dev Docker Compose keeps Prefect server in combined mode for simplicity. Remove prefect-server from `docker-compose.dev.yml` (dev-k8s infra-only).
- **Worker image update**: Add `prefect-kubernetes` package to `Dockerfile.worker` for K8s work pool support.

## Capabilities

### New Capabilities
- `k8s-manifests`: Core Kubernetes manifests (namespace, deployments, services, configmaps, secrets, RBAC, ingress) for API, Prefect API, Prefect background services, Prefect workers, and Redis.
- `k8s-job-lifecycle`: K8s Job templates for flow execution with TTL-based cleanup policy, retry integration via `run_deployment()`, and Prefect work pool alignment.
- `k8s-kustomize-overlays`: Three deployment profiles — dev (Docker), dev-k8s (hybrid), prod (full K8s) — with Kustomize base + overlay structure.

### Modified Capabilities
<!-- No existing specs to modify — this is greenfield infrastructure configuration -->

## Impact

- **Deployment directory**: New `deployment/k8s/` directory tree with base manifests and overlays.
- **Docker Compose files**: Updated to add Redis and align with Prefect 3 official patterns. Dev keeps combined Prefect server; split is K8s only.
- **Docker images**: `Dockerfile.worker` updated to install `prefect-kubernetes` package.
- **API code**: `_submit_flow()` refactored to use `run_deployment()` when `AUTODOC_FLOW_DEPLOYMENT_PREFIX` is not `dev` (i.e., `dev-k8s` and `prod` use K8s dispatch).
- **Flow tasks**: No changes to task decorators in this change. Task result caching (for retry efficiency) deferred until shared result storage is provisioned.
- **Prefect configuration**: `prefect.yaml` production deployments must reference K8s Job templates with correct TTL settings.
- **CI/CD**: Future CI pipeline will need to build images and apply K8s manifests (out of scope for this change, but manifests should be CI-ready).
- **External dependencies**: Requires Kubernetes 1.23+ (TTL controller GA), external PostgreSQL 18+ with pgvector, external Redis 7+ (prod only), and a configured ingress controller.
