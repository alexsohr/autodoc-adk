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

#### Scenario: Full-stack Docker Compose (AMENDED — D2)
- **WHEN** `docker-compose.yml` is used for the dev profile
- **THEN** it SHALL include a Redis 7 service, use `prefecthq/prefect:3-python3.11` for the Prefect server in combined mode **without** Redis messaging environment variables (the `3-python3.11` image avoids asyncpg SSL issues with local PostgreSQL). Redis is present for the dev-k8s profile but not consumed by the dev-profile Prefect server.

#### Scenario: Dev infrastructure Docker Compose
- **WHEN** `docker-compose.dev.yml` is used for the dev-k8s profile
- **THEN** it SHALL include PostgreSQL and Redis services only (prefect-server service removed), with ports exposed for K8s pods to connect from the cluster

### Requirement: Worker Dockerfile update
The system SHALL update `Dockerfile.worker` to include the `prefect-kubernetes` package.

#### Scenario: Package installation
- **WHEN** the worker image is built
- **THEN** it SHALL install `prefect-kubernetes` via `pip install prefect-kubernetes` to enable kubernetes-type work pool support

### Requirement: Job template container name and fields (NEW — D6 AMENDED)
The system SHALL configure base job templates with fields required by Prefect's KubernetesWorker validation.

#### Scenario: Required Job spec fields
- **WHEN** a base job template is defined for a work pool
- **THEN** the Job spec SHALL include `completions: 1` and `parallelism: 1` (validation fails without them)

#### Scenario: Container name
- **WHEN** a base job template defines the flow runner container
- **THEN** the container name SHALL be `prefect-job` (the KubernetesWorker looks for this specific name to inject environment variables and command overrides)

#### Scenario: Config-level namespace
- **WHEN** a base job template defines the namespace
- **THEN** the `namespace` SHALL be set at the `job_configuration` level (not just `job_manifest.metadata.namespace`) because the worker reads the config-level field to determine where to create Jobs

#### Scenario: Image pull policy for local images
- **WHEN** a base job template uses a `:latest` tag with locally-built images
- **THEN** the container SHALL set `imagePullPolicy: IfNotPresent` (K8s defaults to `Always` for `:latest` tags, which fails for images not in a remote registry)

### Requirement: Baked-image deployment pattern (NEW — D15)
The system SHALL bake flow code into the `autodoc-flow` Docker image and configure Prefect deployments to use it without remote code storage.

#### Scenario: Flow code in image
- **WHEN** the `autodoc-flow` image is built
- **THEN** all flow source code SHALL be present at `/app` inside the image, and the `prefect.yaml` SHALL use `build: []` (skip Prefect image build)

#### Scenario: Working directory configuration
- **WHEN** Prefect deployments are defined in `prefect.yaml`
- **THEN** a top-level `pull: [set_working_directory: {directory: /app}]` step SHALL tell workers where flow code lives inside the container

#### Scenario: Image variable
- **WHEN** Prefect deployments set the flow runner image
- **THEN** they SHALL use `job_variables.image` populated via the `AUTODOC_FLOW_IMAGE` env var

#### Scenario: Selective deployment
- **WHEN** Prefect flows are deployed
- **THEN** the operator SHALL use `prefect deploy -n <name>` (selective) rather than `--all` to avoid deploying flows for inactive profiles

### Requirement: Venv relocation fix (NEW — D16)
The system SHALL build Python virtual environments at the final runtime path to avoid shebang breakage.

#### Scenario: Venv build path
- **WHEN** `Dockerfile.api` or `Dockerfile.flow` builds the Python environment
- **THEN** the venv SHALL be created at `/app/.venv` using `UV_PROJECT_ENVIRONMENT=/app/.venv` (not built at `/build/.venv` and copied)

#### Scenario: Entrypoint invocation
- **WHEN** the container entrypoint is defined
- **THEN** it SHALL use `python -m` invocation as an additional safety measure against shebang path issues

### Requirement: MCP server pre-installation (NEW — D17)
The system SHALL pre-install the MCP filesystem server in the flow runner image.

#### Scenario: Global npm installation
- **WHEN** the `autodoc-flow` image is built
- **THEN** `@modelcontextprotocol/server-filesystem` SHALL be installed globally via `npm install -g` so it is available without runtime network access

#### Scenario: No runtime download
- **WHEN** a flow runner pod executes MCP-related operations
- **THEN** the MCP server SHALL be available locally without `npx -y` downloading it at runtime (which fails in K8s pods without internet access)

### Requirement: Secret management via apply-secrets.sh (NEW — D18)
The system SHALL provide a script to load secrets from a gitignored `.env` file into K8s Secrets.

#### Scenario: Script creates/updates secrets
- **WHEN** `deployment/k8s/scripts/apply-secrets.sh` is run
- **THEN** it SHALL read API keys from the `.env` file and create/update K8s Secrets using `kubectl create secret --dry-run=client -o yaml | kubectl apply -f -` (idempotent)

#### Scenario: Placeholder values in base
- **WHEN** `base/secrets/api-keys.yaml` is inspected
- **THEN** it SHALL contain `CHANGE_ME` placeholder values as documentation of required keys, not actual secrets

#### Scenario: .env file is gitignored
- **WHEN** the repository is inspected
- **THEN** the `.env` file used by `apply-secrets.sh` SHALL be listed in `.gitignore` to prevent committing secrets

### Requirement: PREFECT_UI_API_URL for dev-k8s (NEW — D19)
The system SHALL configure the Prefect dashboard to reach the API via port-forward in dev-k8s.

#### Scenario: Dashboard API URL
- **WHEN** the dev-k8s overlay is applied
- **THEN** the Prefect API deployment SHALL have `PREFECT_UI_API_URL=http://localhost:4200/api` set as an environment variable so the browser-side dashboard JavaScript reaches the API via `kubectl port-forward`

### Requirement: Prefect client/server version alignment (NEW — D20)
The system SHALL ensure the Prefect client version in the flow runner image matches the Prefect server version.

#### Scenario: Version pinning
- **WHEN** Docker images are built
- **THEN** the Prefect client version in the flow runner image (`autodoc-flow`) and the Prefect server image SHALL be the same version to prevent 422 serialization errors

#### Scenario: Version mismatch detection
- **WHEN** a flow runner creates task runs against a Prefect server with a different version
- **THEN** the server SHALL return 422 errors due to serialization format differences between versions

### Requirement: Prefect server image per profile (AMENDED — D12b)
The system SHALL use different Prefect server images for dev Docker Compose vs K8s deployments.

#### Scenario: Dev Docker Compose image
- **WHEN** the dev Docker Compose is started
- **THEN** the Prefect server SHALL use `prefecthq/prefect:3-python3.11` (not `3-latest`) because `3-latest` bundles asyncpg 0.30+ which defaults to SSL and fails against local PostgreSQL without SSL

#### Scenario: K8s deployment image
- **WHEN** K8s manifests in `base/prefect/` are applied
- **THEN** the Prefect API server and background services SHALL use `prefecthq/prefect:3-latest` which includes `prefect-redis`

#### Scenario: Worker Dockerfile base
- **WHEN** the worker image is built from `Dockerfile.worker`
- **THEN** it SHALL extend `prefecthq/prefect:3-python3.11` (not `3-latest`) for asyncpg compatibility
