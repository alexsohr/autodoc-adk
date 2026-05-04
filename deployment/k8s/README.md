# AutoDoc ADK — Kubernetes Deployment

## Prerequisites

- Kubernetes 1.23+ (TTL controller GA)
- `kubectl` with Kustomize support (built-in since kubectl 1.14+)
- Docker (for building images)
- For dev-k8s: Docker Desktop with Kubernetes, minikube, or kind
- For prod: External managed PostgreSQL 18+ (pgvector), Redis 7+, and a container registry

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

2. Build Docker images (flow code is baked into the images):
   ```bash
   docker build -t autodoc-api:latest -f deployment/docker/Dockerfile.api .
   docker build -t autodoc-worker:latest -f deployment/docker/Dockerfile.worker .
   docker build -t autodoc-flow:latest -f deployment/docker/Dockerfile.flow .
   docker build -t autodoc-web:latest -f deployment/docker/Dockerfile.web .
   ```

3. Apply K8s manifests:
   ```bash
   kubectl apply -k deployment/k8s/overlays/dev-k8s
   ```

4. Apply API key secrets from `.env` (values never committed to git):
   ```bash
   ./deployment/k8s/scripts/apply-secrets.sh
   ```

5. Access the services — choose **one** of:

   **Option A: Port-forwards** (no ingress controller required):
   ```bash
   kubectl port-forward -n autodoc svc/autodoc-web 3000:3000 &     # Dashboard (serves SPA + proxies /api in-cluster)
   kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &     # Prefect dashboard + CLI
   kubectl port-forward -n autodoc svc/autodoc-api 8080:8080 &     # Direct API access (Swagger UI, curl)
   ```

   > **Path differences:** Port-forwards hit each service at its root — no path prefix.
   > The dashboard at `localhost:3000` is self-sufficient: its nginx proxies
   > `localhost:3000/api/*` to the API service in-cluster. The API port-forward
   > (`localhost:8080`) is only needed for direct access (Swagger UI, curl) and
   > serves the API **without** the `/api` prefix (e.g., `localhost:8080/health`,
   > not `localhost:8080/api/health`). Similarly, Prefect is at
   > `localhost:4200/api/...`, not `localhost:4200/prefect/api/...`.

   **Option B: Local ingress controller** (single entrypoint, path-based routing):
   If you have an nginx ingress controller running locally, the dev-k8s ingress routes
   everything through `http://localhost` with path prefixes — see
   [Ingress & Path-Based Routing](#ingress--path-based-routing).
   You still need the Prefect port-forward for CLI commands (`prefect deploy`, etc.):
   ```bash
   kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &   # Prefect CLI
   ```

6. Set up work pools:
   ```bash
   ./deployment/k8s/scripts/setup-work-pools.sh
   ```

7. Deploy Prefect flows (only the dev-k8s deployments, not `--all`):
   ```bash
   PREFECT_API_URL=http://localhost:4200/api \
     AUTODOC_FLOW_IMAGE=autodoc-flow:latest \
     prefect deploy -n dev-k8s-full-generation -n dev-k8s-scope-processing -n dev-k8s-incremental
   ```

8. Verify:

   | Service | Port-forward URL | Ingress URL |
   |---------|-----------------|-------------|
   | Dashboard | http://localhost:3000 | http://localhost/ |
   | API (Swagger UI) | http://localhost:8080/docs | http://localhost/api/docs |
   | API health check | `curl http://localhost:8080/health` | `curl http://localhost/api/health` |
   | Prefect dashboard | http://localhost:4200/dashboard | http://localhost/prefect/dashboard |

   > Note: The ingress adds path prefixes (`/api`, `/prefect`) and strips them
   > before forwarding. Port-forwards skip the ingress entirely, so services are
   > at their native paths (no prefix).

#### Networking (dev-k8s)

K8s pods need to reach Docker services on the host:

- **Docker Desktop**: Uses `host.docker.internal` (configured in dev-k8s secrets patch)
- **minikube**: Use `minikube ssh -- 'cat /etc/hosts'` to find host IP, update secrets
- **kind**: Use `docker network inspect kind` to find gateway IP

#### Prefect Dashboard (dev-k8s)

The dev-k8s overlay sets `PREFECT_UI_API_URL=http://localhost:4200/api` so the browser-side dashboard JavaScript reaches the API via your port-forward instead of the in-cluster `prefect-api:4200` hostname.

If you see "Can't connect to Server API at http://prefect-api:4200/api", ensure:
1. The port-forward is running: `kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &`
2. The `PREFECT_UI_API_URL` env var is set on the prefect-api deployment (applied by the dev-k8s overlay)

### Profile 3: prod (full K8s)

All components on K8s with external managed PostgreSQL and Redis.

1. Build and push Docker images to your registry:
   ```bash
   REGISTRY=myregistry.example.com/autodoc
   COMMIT_SHA=$(git rev-parse --short HEAD)

   docker build -t $REGISTRY/api:$COMMIT_SHA -f deployment/docker/Dockerfile.api .
   docker build -t $REGISTRY/worker:$COMMIT_SHA -f deployment/docker/Dockerfile.worker .
   docker build -t $REGISTRY/flow:$COMMIT_SHA -f deployment/docker/Dockerfile.flow .
   docker build -t $REGISTRY/web:$COMMIT_SHA -f deployment/docker/Dockerfile.web .

   docker push $REGISTRY/api:$COMMIT_SHA
   docker push $REGISTRY/worker:$COMMIT_SHA
   docker push $REGISTRY/flow:$COMMIT_SHA
   docker push $REGISTRY/web:$COMMIT_SHA
   ```

2. Update the prod overlay image tags and apply:
   ```bash
   # Edit overlays/prod/kustomization.yaml to set your registry and commit SHA
   kubectl apply -k deployment/k8s/overlays/prod
   ```

3. Set up work pools:
   ```bash
   PREFECT_API_URL=http://<prefect-api-url>:4200/api \
     ./deployment/k8s/scripts/setup-work-pools.sh
   ```

4. Deploy Prefect flows (only the prod deployments):
   ```bash
   PREFECT_API_URL=http://<prefect-api-url>:4200/api \
     AUTODOC_FLOW_IMAGE=$REGISTRY/flow:$COMMIT_SHA \
     prefect deploy -n prod-full-generation -n prod-scope-processing -n prod-incremental
   ```

## Ingress & Path-Based Routing

All external traffic enters through a single hostname and is routed by path using two Ingress resources:

| Path | Backend | Behavior |
|------|---------|----------|
| `/` | `autodoc-web:3000` | Dashboard SPA (no rewrite) |
| `/api/*` | `autodoc-api:8080` | API — prefix stripped (`/api/repositories` → `/repositories`) |
| `/prefect/*` | `prefect-api:4200` | Prefect Server — prefix stripped (`/prefect/api/health` → `/api/health`) |

The base manifests use `autodoc.example.com` as a placeholder hostname. Override it per environment:

- **ConfigMap key**: `AUTODOC_PUBLIC_HOSTNAME` sets the hostname (base: `autodoc.example.com`, dev-k8s: `localhost`)
- **Ingress patch**: Each overlay patches the Ingress `host` and `tls` fields to match

### dev-k8s

The dev-k8s overlay (`overlays/dev-k8s/patches/ingress.yaml`) sets the hostname to `localhost` and disables TLS. Access everything via port-forward or a local ingress controller.

### prod

Set `AUTODOC_PUBLIC_HOSTNAME` and the Ingress `host` / `tls` / `secretName` fields in your prod overlay to match your real domain and TLS certificate.

### Two-layer routing

Routing is handled at two layers:

1. **Ingress** (cluster edge): Routes `/api/*` and `/prefect/*` to their backend services, stripping the path prefix. Routes `/` to the web dashboard.
2. **nginx in `autodoc-web`** (container level): The web container's nginx (`nginx-web.conf.template`) also proxies `/api/*` to `autodoc-api:8080` using the `API_UPSTREAM` config var. This lets the SPA make API calls from the browser regardless of whether the ingress is present (e.g., port-forward directly to the web service).

## Docker Images

Flow code is baked into the Docker images — no remote code storage (Git, S3) is needed at runtime. The `prefect.yaml` uses `build: []` (skip Prefect's image build) and `pull: [set_working_directory: /app]` (code is already in the container).

| Image | Dockerfile | Purpose |
|-------|-----------|---------|
| `autodoc-api` | `Dockerfile.api` | FastAPI REST API server |
| `autodoc-worker` | `Dockerfile.worker` | Prefect worker (polls work pools, creates K8s Jobs) |
| `autodoc-flow` | `Dockerfile.flow` | Flow runner with all AI dependencies + source code |
| `autodoc-web` | `Dockerfile.web` | Web dashboard (nginx serving React SPA, reverse proxies `/api` to API) |

The `AUTODOC_FLOW_IMAGE` env var (default: `autodoc-flow:latest`) controls which image the work pools use for flow runner K8s Jobs.

## Work Pool Setup

Two work pools are required:

| Pool | Type | Concurrency | Purpose |
|------|------|-------------|---------|
| `orchestrator-pool` | kubernetes | 10 | Parent flows (full_generation, incremental_update) |
| `k8s-pool` | kubernetes | 50 | Scope processing workers |

Use the setup script (auto-detects `prefect` or `uv run prefect`, waits for API):

```bash
kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &
./deployment/k8s/scripts/setup-work-pools.sh
```

Or configure manually:

```bash
prefect work-pool create orchestrator-pool --type kubernetes
prefect work-pool set-concurrency-limit orchestrator-pool 10
prefect work-pool update orchestrator-pool \
  --base-job-template deployment/k8s/job-templates/orchestrator-job-template.json

prefect work-pool create k8s-pool --type kubernetes
prefect work-pool set-concurrency-limit k8s-pool 50
prefect work-pool update k8s-pool \
  --base-job-template deployment/k8s/job-templates/scope-job-template.json
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

**Pods stuck in ImagePullBackOff**:
For dev-k8s with Docker Desktop, images must be built locally with the exact names used in the manifests (`autodoc-api:latest`, `autodoc-worker:latest`, `autodoc-web:latest`). The base manifests set `imagePullPolicy: IfNotPresent` to use local images. If using minikube, load images with `minikube image load`.

**Prefect dashboard says "Can't connect to Server API"**:
The Prefect UI runs in your browser and needs to reach the API. The dev-k8s overlay sets `PREFECT_UI_API_URL=http://localhost:4200/api` for this. Ensure your port-forward is active: `kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &`.

**Pods can't reach PostgreSQL/Redis (dev-k8s)**:
Check that Docker services are running and ports are exposed. Verify `host.docker.internal` resolves from inside the cluster.

**Flow runner Jobs stay Pending**:
Check work pool status: `prefect work-pool inspect orchestrator-pool`. Verify workers are running and polling. Check that the `autodoc-flow` image is available.

**Job cleanup not working**:
Check CronJob status: `kubectl get cronjobs -n autodoc`. The cleanup CronJob needs the `autodoc-job-cleanup` ServiceAccount with correct RBAC.

**Prefect background services issues**:
Only one instance should run (`replicas: 1`). Check logs: `kubectl logs -n autodoc -l app.kubernetes.io/component=prefect-background-services`.

**Dashboard not loading or API calls failing**:
The web dashboard container proxies `/api/*` requests to the `autodoc-api` service. Verify the API service is running and reachable: `kubectl get svc -n autodoc autodoc-api`. Check nginx logs: `kubectl logs -n autodoc -l app.kubernetes.io/component=web`.
