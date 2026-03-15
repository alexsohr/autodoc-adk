## ADDED Requirements

### Requirement: Kustomize base structure
The system SHALL organize Kubernetes manifests using a Kustomize base directory containing all core resource definitions.

#### Scenario: Base directory contents
- **WHEN** the base `kustomization.yaml` is inspected
- **THEN** it SHALL reference all core resources: namespace, API deployment + service, Prefect API deployment + service, Prefect background services deployment, orchestrator worker deployment, scope worker deployment, RBAC resources, ConfigMap, Secrets, Ingress, and the job-cleanup CronJob

#### Scenario: Base manifests are complete
- **WHEN** `kubectl kustomize deployment/k8s/base` is run
- **THEN** it SHALL produce valid Kubernetes manifests for all components without requiring any overlay

### Requirement: Dev-k8s overlay
The system SHALL provide a dev-k8s overlay that configures the deployment for hybrid development where infrastructure (PostgreSQL, Redis) runs in Docker and application components run on K8s.

#### Scenario: Dev-k8s overlay configuration
- **WHEN** the dev-k8s overlay is applied (`kubectl apply -k deployment/k8s/overlays/dev-k8s`)
- **THEN** it SHALL set: single replica for all Deployments, reduced resource limits for flow runners, `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev-k8s`, dev-appropriate image tags (`latest`), and connection parameters pointing to Docker Compose infrastructure services (host networking or NodePort)

#### Scenario: Dev-k8s overlay inherits base
- **WHEN** the dev-k8s overlay `kustomization.yaml` is inspected
- **THEN** it SHALL reference `../../base` as its base and apply patches for dev-k8s-specific overrides

#### Scenario: Dev-k8s infrastructure connectivity
- **WHEN** the dev-k8s overlay is applied
- **THEN** the Secret patches SHALL configure PostgreSQL and Redis connection strings pointing to the host machine (e.g., `host.docker.internal` or configurable host) where Docker Compose services are running

### Requirement: Prod overlay
The system SHALL provide a prod overlay that configures the deployment for production with external managed services.

#### Scenario: Prod overlay configuration
- **WHEN** the prod overlay is applied (`kubectl apply -k deployment/k8s/overlays/prod`)
- **THEN** it SHALL set: multiple replicas for API (2+) and Prefect API (2+), production resource limits for flow runners, `AUTODOC_FLOW_DEPLOYMENT_PREFIX=prod`, production image tags (commit SHA), `PREFECT_API_DATABASE_MIGRATE_ON_START=false`, and production-grade configuration values

#### Scenario: Prod overlay inherits base
- **WHEN** the prod overlay `kustomization.yaml` is inspected
- **THEN** it SHALL reference `../../base` as its base and apply patches for prod-specific overrides

#### Scenario: Prod external services
- **WHEN** the prod overlay is applied
- **THEN** the Secrets SHALL contain placeholder values for external managed PostgreSQL and Redis connection parameters that MUST be replaced before deployment

### Requirement: Docker Compose dev profile
The system SHALL maintain Docker Compose files as the primary dev profile where all services run locally without K8s.

#### Scenario: Full-stack Docker Compose
- **WHEN** `docker-compose.yml` is started
- **THEN** it SHALL run PostgreSQL, Redis, Prefect server (combined mode), Prefect worker (local-dev pool), and the API server — all services needed for local development

#### Scenario: Infrastructure-only Docker Compose
- **WHEN** `docker-compose.dev.yml` is started for the dev-k8s profile
- **THEN** it SHALL run only PostgreSQL and Redis with ports exposed for K8s pods to connect from the cluster

### Requirement: Image tag parameterization
The system SHALL allow image tags to be overridden per environment without modifying base manifests.

#### Scenario: Image override via Kustomize
- **WHEN** an overlay sets `images` in its `kustomization.yaml`
- **THEN** the image tags for API, Worker, and Flow Runner containers SHALL be replaced with the overlay-specified values

#### Scenario: Default image tags in base
- **WHEN** base manifests are used without an overlay
- **THEN** all images SHALL use `latest` as the default tag (overridden by overlays in practice)

### Requirement: Secret placeholder pattern
The system SHALL provide Secret manifests with placeholder values that MUST be replaced before deployment.

#### Scenario: Placeholder secrets in base
- **WHEN** the base Secret manifests are inspected
- **THEN** they SHALL contain clearly marked placeholder values (e.g., `CHANGE_ME`) for all sensitive fields with comments indicating what each value should be

#### Scenario: Overlay secret patches
- **WHEN** an overlay is applied
- **THEN** it MAY patch Secret values via Kustomize `secretGenerator` or strategic merge patches, or operators MAY apply Secrets separately via CI/CD or External Secrets Operator

### Requirement: Resource quota per namespace
The system SHALL define a ResourceQuota for the `autodoc` namespace to bound total resource consumption.

#### Scenario: Quota limits
- **WHEN** the ResourceQuota is applied
- **THEN** it SHALL set maximum limits for total CPU requests, memory requests, and number of active Jobs in the namespace (configurable per overlay)

#### Scenario: Prod quota values
- **WHEN** the prod overlay is applied
- **THEN** the ResourceQuota SHALL allow sufficient resources for the expected concurrent workload: at least 10 orchestrator Jobs + 50 scope Jobs + long-running Deployments

### Requirement: Directory structure
The system SHALL organize all Kubernetes manifests under `deployment/k8s/` with a clear directory hierarchy.

#### Scenario: Directory layout
- **WHEN** the `deployment/k8s/` directory is listed
- **THEN** it SHALL contain: `base/` (core manifests + `kustomization.yaml`), `overlays/dev-k8s/` (hybrid dev patches + `kustomization.yaml`), `overlays/prod/` (production patches + `kustomization.yaml`), and `job-templates/` (Prefect work pool base job template JSON files)
