# AutoDoc ADK — Kubernetes Deployment

## Prerequisites

- Kubernetes 1.23+ (TTL controller GA)
- `kubectl` with Kustomize support (built-in since kubectl 1.14+)
- Container registry accessible from the cluster
- For dev-k8s: Docker Desktop with Kubernetes, minikube, or kind
- For prod: External managed PostgreSQL 18+ (pgvector) and Redis 7+

## Deployment Profiles

### Profile 1: dev (Docker Compose only)

All services run locally via Docker Compose. No Kubernetes required.

```bash
cd deployment
docker compose up --build -d
```

### Profile 2: dev-k8s (hybrid)

Infrastructure (PostgreSQL + Redis) in Docker, application on K8s.

1. Start infrastructure:
   ```bash
   cd deployment/docker
   docker compose -f docker-compose.dev.yml up -d
   ```

2. Apply K8s manifests:
   ```bash
   kubectl apply -k deployment/k8s/overlays/dev-k8s
   ```

3. Set up port-forward and work pools:
   ```bash
   kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &
   ./deployment/k8s/scripts/setup-work-pools.sh
   ```

4. Deploy Prefect flows (only the dev-k8s deployments, not `--all`):
   ```bash
   PREFECT_API_URL=http://localhost:4200/api \
     prefect deploy -n dev-k8s-full-generation -n dev-k8s-scope-processing -n dev-k8s-incremental
   ```

#### Networking (dev-k8s)

K8s pods need to reach Docker services on the host:

- **Docker Desktop**: Uses `host.docker.internal` (configured in dev-k8s secrets patch)
- **minikube**: Use `minikube ssh -- 'cat /etc/hosts'` to find host IP, update secrets
- **kind**: Use `docker network inspect kind` to find gateway IP

### Profile 3: prod (full K8s)

All components on K8s with external managed PostgreSQL and Redis.

1. Create secrets with real credentials:
   ```bash
   # Edit prod secrets with actual values before applying
   kubectl apply -k deployment/k8s/overlays/prod
   ```

2. Set up work pools:
   ```bash
   PREFECT_API_URL=http://<prefect-api-url>:4200/api \
     ./deployment/k8s/scripts/setup-work-pools.sh
   ```

3. Deploy Prefect flows (only the prod deployments):
   ```bash
   PREFECT_API_URL=http://<prefect-api-url>:4200/api \
     prefect deploy -n prod-full-generation -n prod-scope-processing -n prod-incremental
   ```

## Work Pool Setup

Two work pools are required:

| Pool | Type | Concurrency | Purpose |
|------|------|-------------|---------|
| `orchestrator-pool` | kubernetes | 10 | Parent flows (full_generation, incremental_update) |
| `k8s-pool` | kubernetes | 50 | Scope processing workers |

Use the setup script or configure manually:

```bash
prefect work-pool create orchestrator-pool --type kubernetes \
  --base-job-template deployment/k8s/job-templates/orchestrator-job-template.json
prefect work-pool set-concurrency-limit orchestrator-pool 10

prefect work-pool create k8s-pool --type kubernetes \
  --base-job-template deployment/k8s/job-templates/scope-job-template.json
prefect work-pool set-concurrency-limit k8s-pool 50
```

## Secret Management

Base secrets contain `CHANGE_ME` placeholders. Replace before deploying:

| Secret | Keys | Description |
|--------|------|-------------|
| `autodoc-db-credentials` | `DATABASE_URL`, `PREFECT_API_DATABASE_CONNECTION_URL` | PostgreSQL asyncpg connection strings |
| `autodoc-api-keys` | `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `GITHUB_DEFAULT_TOKEN` | LLM and provider API keys |
| `autodoc-redis-credentials` | `PREFECT_REDIS_MESSAGING_HOST`, `PREFECT_REDIS_MESSAGING_PORT` | Redis connection for Prefect |

For production, consider using External Secrets Operator or sealed-secrets.

## Troubleshooting

**Pods can't reach PostgreSQL/Redis (dev-k8s)**:
Check that Docker services are running and ports are exposed. Verify `host.docker.internal` resolves from inside the cluster.

**Flow runner Jobs stay Pending**:
Check work pool status: `prefect work-pool inspect orchestrator-pool`. Verify workers are running and polling.

**Job cleanup not working**:
Check CronJob status: `kubectl get cronjobs -n autodoc`. The cleanup CronJob needs the `autodoc-job-cleanup` ServiceAccount with correct RBAC.

**Prefect background services issues**:
Only one instance should run (`replicas: 1`). Check logs: `kubectl logs -n autodoc -l app.kubernetes.io/component=prefect-background-services`.
