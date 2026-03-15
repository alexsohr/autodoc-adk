## ADDED Requirements

### Requirement: Namespace isolation
The system SHALL deploy all application components into a dedicated Kubernetes namespace named `autodoc`.

#### Scenario: Namespace creation
- **WHEN** the manifests are applied to a Kubernetes cluster
- **THEN** a namespace named `autodoc` SHALL be created if it does not already exist, and all subsequent resources SHALL be created within this namespace

### Requirement: API server deployment
The system SHALL deploy the FastAPI application as a Kubernetes Deployment with a corresponding Service.

#### Scenario: API server running
- **WHEN** the API Deployment is applied
- **THEN** the API SHALL run with the `Dockerfile.api` image, expose port 8080 via a ClusterIP Service, and pass health checks on `GET /health`

#### Scenario: API environment configuration
- **WHEN** the API pods start
- **THEN** they SHALL receive DATABASE_URL from the `autodoc-db-credentials` Secret, PREFECT_API_URL pointing to the in-cluster Prefect API Service, and all other configuration from the `autodoc-config` ConfigMap

### Requirement: Prefect API server deployment
The system SHALL deploy the Prefect API server as a Kubernetes Deployment with a corresponding Service, running in API-only mode.

#### Scenario: Prefect API server running
- **WHEN** the Prefect API Deployment is applied
- **THEN** it SHALL run with the `prefecthq/prefect:3-latest` image (which bundles `prefect-redis`), execute `prefect server start --no-services` (with `PREFECT_SERVER_API_HOST=0.0.0.0` env var), expose port 4200 via a ClusterIP Service, and connect to the external PostgreSQL `prefect` database and Redis

#### Scenario: Prefect API server environment
- **WHEN** the Prefect API server pods start
- **THEN** they SHALL have the following environment variables set: `PREFECT_API_DATABASE_CONNECTION_URL` from Secret, `PREFECT_SERVER_API_HOST=0.0.0.0`, `PREFECT_API_DATABASE_MIGRATE_ON_START=false`, and all Redis messaging env vars (`PREFECT_MESSAGING_BROKER`, `PREFECT_MESSAGING_CACHE`, `PREFECT_SERVER_EVENTS_CAUSAL_ORDERING`, `PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE`, `PREFECT_REDIS_MESSAGING_HOST`, `PREFECT_REDIS_MESSAGING_PORT`)

#### Scenario: Prefect API horizontal scaling
- **WHEN** the prod overlay is applied
- **THEN** the Prefect API Deployment SHALL support multiple replicas (2+) since the `--no-services` mode is stateless

### Requirement: Prefect background services deployment
The system SHALL deploy Prefect background services as a separate Kubernetes Deployment running as a singleton.

#### Scenario: Background services running
- **WHEN** the Prefect background services Deployment is applied
- **THEN** it SHALL run with the `prefecthq/prefect:3-latest` image, execute `prefect server services start`, connect to the same PostgreSQL and Redis as the Prefect API server, and run with exactly `replicas: 1`

#### Scenario: Background services environment
- **WHEN** the Prefect background services pod starts
- **THEN** it SHALL have the same database and Redis environment variables as the Prefect API server

### Requirement: Prefect worker deployments
The system SHALL deploy two Prefect worker Deployments — one for `orchestrator-pool` and one for `k8s-pool`.

#### Scenario: Orchestrator worker running
- **WHEN** the orchestrator worker Deployment is applied
- **THEN** a Prefect worker SHALL poll the `orchestrator-pool` work pool, use the `prefect-worker` ServiceAccount, and connect to the in-cluster Prefect API Service

#### Scenario: Scope worker running
- **WHEN** the scope worker Deployment is applied
- **THEN** a Prefect worker SHALL poll the `k8s-pool` work pool, use the `prefect-worker` ServiceAccount, and connect to the in-cluster Prefect API Service

#### Scenario: Worker image includes prefect-kubernetes
- **WHEN** worker pods start
- **THEN** the worker image SHALL include the `prefect-kubernetes` package to support kubernetes-type work pools

### Requirement: Redis connection configuration
The system SHALL configure Redis connectivity for all Prefect server components via environment variables.

#### Scenario: Redis credentials Secret
- **WHEN** the K8s manifests are applied
- **THEN** a Secret named `autodoc-redis-credentials` SHALL exist containing `PREFECT_REDIS_MESSAGING_HOST` and `PREFECT_REDIS_MESSAGING_PORT` keys

#### Scenario: Redis env vars on Prefect components
- **WHEN** Prefect API server and background services pods start
- **THEN** they SHALL have `PREFECT_MESSAGING_BROKER=prefect_redis.messaging`, `PREFECT_MESSAGING_CACHE=prefect_redis.messaging`, `PREFECT_SERVER_EVENTS_CAUSAL_ORDERING=prefect_redis.ordering`, `PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE=prefect_redis.lease_storage`, and Redis host/port from the `autodoc-redis-credentials` Secret

### Requirement: Database credentials Secret
The system SHALL store database connection parameters in a Kubernetes Secret named `autodoc-db-credentials`.

#### Scenario: Secret structure
- **WHEN** the Secret is created
- **THEN** it SHALL contain keys for `DATABASE_URL` (asyncpg connection string for the `autodoc` database) and `PREFECT_API_DATABASE_CONNECTION_URL` (asyncpg connection string for the `prefect` database)

#### Scenario: Secret consumption
- **WHEN** API, Prefect server, or flow runner pods start
- **THEN** they SHALL read database credentials exclusively from the `autodoc-db-credentials` Secret via `secretKeyRef`

### Requirement: Application ConfigMap
The system SHALL store non-sensitive configuration in a ConfigMap named `autodoc-config`.

#### Scenario: ConfigMap contents
- **WHEN** the ConfigMap is created
- **THEN** it SHALL contain all non-secret environment variables: model names, quality thresholds, concurrency limits, embedding settings, `CLONE_DIR=/tmp/autodoc-workspaces` (matching emptyDir mount point), and feature flags as defined in `src/config/settings.py`

### Requirement: API key Secrets
The system SHALL store LLM provider API keys in a Kubernetes Secret named `autodoc-api-keys`.

#### Scenario: API key Secret structure
- **WHEN** the Secret is created
- **THEN** it SHALL contain keys for `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and optionally `GITHUB_DEFAULT_TOKEN`, `AZURE_API_KEY`, and AWS credential keys

### Requirement: RBAC for Prefect workers
The system SHALL create a ServiceAccount, Role, and RoleBinding granting Prefect workers permission to manage K8s Jobs in the `autodoc` namespace.

#### Scenario: ServiceAccount permissions
- **WHEN** the `prefect-worker` ServiceAccount is created with its Role
- **THEN** it SHALL have permissions to create, get, list, watch, and delete Jobs, Pods, and Pod logs within the `autodoc` namespace

#### Scenario: Worker pods use ServiceAccount
- **WHEN** Prefect worker pods start
- **THEN** they SHALL use the `prefect-worker` ServiceAccount

### Requirement: Ingress for API and Prefect UI
The system SHALL create an Ingress resource routing external traffic to the API and Prefect UI services.

#### Scenario: API routing
- **WHEN** a request arrives at the API host path
- **THEN** the Ingress SHALL route it to the API Service on port 8080

#### Scenario: Prefect UI routing
- **WHEN** a request arrives at the Prefect host path
- **THEN** the Ingress SHALL route it to the Prefect API Service on port 4200

#### Scenario: TLS termination
- **WHEN** TLS is configured via annotation or Secret reference
- **THEN** the Ingress SHALL terminate TLS and serve HTTPS traffic

#### Scenario: Configurable ingress class
- **WHEN** the manifests are applied
- **THEN** the Ingress SHALL use a configurable `ingressClassName` (defaulting to `nginx`)

### Requirement: Docker Compose updates for Redis and Prefect 3
The system SHALL update existing Docker Compose files to add Redis and align with Prefect 3 official deployment patterns.

#### Scenario: Full-stack Docker Compose
- **WHEN** `docker-compose.yml` is used for the dev profile
- **THEN** it SHALL include a Redis 7 service, update the Prefect server to use combined mode (without `--no-services` for simplicity), and add all Redis messaging environment variables

#### Scenario: Dev infrastructure Docker Compose
- **WHEN** `docker-compose.dev.yml` is used for the dev-k8s profile
- **THEN** it SHALL include PostgreSQL and Redis services only (prefect-server service removed), with ports exposed for K8s pods to connect from the cluster

### Requirement: Worker Dockerfile update
The system SHALL update `Dockerfile.worker` to include the `prefect-kubernetes` package.

#### Scenario: Package installation
- **WHEN** the worker image is built
- **THEN** it SHALL install `prefect-kubernetes` via `pip install prefect-kubernetes` to enable kubernetes-type work pool support
