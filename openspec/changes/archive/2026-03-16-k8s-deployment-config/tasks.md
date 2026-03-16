## 1. Directory Structure & Namespace

- [x] 1.1 Create `deployment/k8s/base/`, `deployment/k8s/overlays/dev-k8s/`, `deployment/k8s/overlays/prod/`, and `deployment/k8s/job-templates/` directory structure
- [x] 1.2 Create `base/namespace.yaml` defining the `autodoc` namespace
- [x] 1.3 Create `base/kustomization.yaml` referencing all base resources

## 2. Docker Compose Updates

- [x] 2.1 Update `deployment/docker-compose.yml` — add Redis 7 service, add Redis messaging env vars to Prefect server (combined mode, no `--no-services`), replace `--host 0.0.0.0` with `PREFECT_SERVER_API_HOST=0.0.0.0` env var, update image to `prefecthq/prefect:3-latest`
- [x] 2.2 Update `deployment/docker/docker-compose.dev.yml` — add Redis service, remove `prefect-server` service (dev-k8s profile is infra-only: PostgreSQL + Redis), expose ports for K8s connectivity
- [x] 2.3 Update `deployment/docker/Dockerfile.worker` — add `RUN pip install prefect-kubernetes` for K8s work pool support

## 3. Secrets & ConfigMap

- [x] 3.1 Create `base/secrets/db-credentials.yaml` — Secret `autodoc-db-credentials` with placeholder `DATABASE_URL` and `PREFECT_API_DATABASE_CONNECTION_URL` keys
- [x] 3.2 Create `base/secrets/api-keys.yaml` — Secret `autodoc-api-keys` with placeholder keys for `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `GITHUB_DEFAULT_TOKEN`
- [x] 3.3 Create `base/secrets/redis-credentials.yaml` — Secret `autodoc-redis-credentials` with placeholder `PREFECT_REDIS_MESSAGING_HOST` and `PREFECT_REDIS_MESSAGING_PORT`
- [x] 3.4 Create `base/configmap.yaml` — ConfigMap `autodoc-config` with all non-secret env vars from `src/config/settings.py` (model names, thresholds, concurrency, embedding settings, OTEL, `CLONE_DIR=/tmp/autodoc-workspaces`, Prefect Redis messaging broker/cache constants, etc.)

## 4. RBAC

- [x] 4.1 Create `base/rbac/worker-rbac.yaml` — ServiceAccount `prefect-worker`, Role with permissions for Jobs/Pods/Pods-log (create, get, list, watch, delete), and RoleBinding in `autodoc` namespace
- [x] 4.2 Create `base/rbac/cleanup-rbac.yaml` — ServiceAccount `autodoc-job-cleanup`, Role granting list/delete on Jobs, and RoleBinding

## 5. Prefect Server (API + Background Services)

- [x] 5.1 Create `base/prefect/api-deployment.yaml` — Deployment using `prefecthq/prefect:3-latest`, command `prefect server start --no-services`, env var `PREFECT_SERVER_API_HOST=0.0.0.0`, port 4200, `PREFECT_API_DATABASE_CONNECTION_URL` from Secret, Redis env vars from Secret + ConfigMap, `PREFECT_API_DATABASE_MIGRATE_ON_START=false`, readiness probe on `/api/health`
- [x] 5.2 Create `base/prefect/api-service.yaml` — ClusterIP Service on port 4200
- [x] 5.3 Create `base/prefect/background-services-deployment.yaml` — Deployment using `prefecthq/prefect:3-latest`, `replicas: 1`, command `prefect server services start`, same DB + Redis env vars as API, no Service (internal only)

## 6. Prefect Workers

- [x] 6.1 Create `base/workers/orchestrator-worker.yaml` — Deployment polling `orchestrator-pool`, using `prefect-worker` ServiceAccount, `PREFECT_API_URL` pointing to Prefect API Service, worker image with `prefect-kubernetes`
- [x] 6.2 Create `base/workers/scope-worker.yaml` — Deployment polling `k8s-pool`, using `prefect-worker` ServiceAccount, same Prefect API URL

## 7. API Server

- [x] 7.1 Create `base/api/deployment.yaml` — Deployment using API image, port 8080, env from ConfigMap + Secrets, readiness/liveness probe on `GET /health`
- [x] 7.2 Create `base/api/service.yaml` — ClusterIP Service on port 8080

## 8. Ingress

- [x] 8.1 Create `base/ingress.yaml` — Ingress resource with `ingressClassName: nginx` (configurable), two rules for API and Prefect UI hosts, TLS section with Secret reference

## 9. Job Lifecycle & Cleanup

- [x] 9.1 Create `job-templates/orchestrator-job-template.json` — Prefect work pool base job template for `orchestrator-pool` with: Flow Runner image, `emptyDir` volume at `/tmp/autodoc-workspaces`, resource requests/limits (1 CPU/2Gi req, 2 CPU/4Gi limit), `ttlSecondsAfterFinished: 86400`, `autodoc` namespace, `prefect-worker` ServiceAccount, env vars from ConfigMap + Secrets, labels
- [x] 9.2 Create `job-templates/scope-job-template.json` — Same as above for `k8s-pool` but with higher resources (2 CPU/4Gi req, 4 CPU/8Gi limit)
- [x] 9.3 Create `base/cleanup/cronjob.yaml` — CronJob `autodoc-job-cleanup` running every 5 minutes, using `autodoc-job-cleanup` ServiceAccount (from `base/rbac/cleanup-rbac.yaml`), with a script that lists Succeeded Jobs older than 5 minutes and deletes them

## 10. Resource Quota

- [x] 10.1 Create `base/resource-quota.yaml` — ResourceQuota for `autodoc` namespace with configurable CPU/memory/Job limits

## 11. Kustomize Overlays — Dev-K8s (Hybrid)

- [x] 11.1 Create `overlays/dev-k8s/kustomization.yaml` referencing `../../base`, setting image tags to `latest`, and including dev-k8s patches
- [x] 11.2 Create `overlays/dev-k8s/patches/` — Strategic merge patches for: single replicas on all Deployments, reduced flow runner resource limits, `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev-k8s`, Secret patches pointing DB/Redis to Docker Compose services (host.docker.internal or configurable), relaxed ResourceQuota

## 12. Kustomize Overlays — Prod

- [x] 12.1 Create `overlays/prod/kustomization.yaml` referencing `../../base`, setting image tags to commit SHA placeholder, and including prod patches
- [x] 12.2 Create `overlays/prod/patches/` — Strategic merge patches for: 2+ replicas on API and Prefect API, `replicas: 1` on background services, production flow runner resource limits, `AUTODOC_FLOW_DEPLOYMENT_PREFIX=prod`, `PREFECT_API_DATABASE_MIGRATE_ON_START=false`, production ResourceQuota values, placeholder Secrets for external managed PostgreSQL and Redis

## 13. Application Code Changes

- [x] 13.1 Refactor `_submit_flow()` in `src/api/routes/jobs.py` — when `AUTODOC_FLOW_DEPLOYMENT_PREFIX != "dev"`, use `run_deployment()` (from `prefect.deployments`) to dispatch flow runs via Prefect workers instead of direct `asyncio.create_task()` invocation
- [x] 13.2 Refactor `scope_processing_flow` to accept `clone_input` (url, provider, access_token) + `branch` as parameters in K8s mode — clone the repo at the start of execution instead of receiving `repo_path`. In dev mode (in-process subflow), continue accepting `repo_path` directly and skip cloning
- [x] 13.3 Update `full_generation_flow` and `incremental_update_flow` to pass `clone_input` parameters (not filesystem paths) when dispatching scope Jobs via `run_deployment()` in K8s mode
- [x] 13.4 Remove `prod-cleanup` deployment from `prefect.yaml` — `cleanup_orphan_workspaces` is not needed in K8s (emptyDir handles lifecycle). Keep `dev-cleanup` for Docker Compose environments only
- [x] 13.5 Add `dev-k8s-*` deployments to `prefect.yaml` — `dev-k8s-full-generation` (orchestrator-pool), `dev-k8s-scope-processing` (k8s-pool), `dev-k8s-incremental` (orchestrator-pool) targeting K8s work pools for the hybrid dev profile

## 14. Documentation & Validation

- [x] 14.1 Add `deployment/k8s/README.md` with: prerequisites, three deployment profiles explained, quickstart for dev-k8s overlay, production deployment steps, work pool setup commands, secret management guidance, dev-k8s networking setup, and troubleshooting
- [x] 14.2 Validate all manifests with `kubectl kustomize deployment/k8s/overlays/dev-k8s` and `kubectl kustomize deployment/k8s/overlays/prod` — ensure they produce valid YAML
- [x] 14.3 Create work pool setup script (`deployment/k8s/scripts/setup-work-pools.sh`) that creates orchestrator-pool and k8s-pool with concurrency limits and applies the base job templates from `job-templates/`
