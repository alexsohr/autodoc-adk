## MODIFIED Requirements

> **Existing K8s patterns to follow** (from `deployment/k8s/base/` and `deployment/k8s/overlays/`):
> - Label scheme: `app.kubernetes.io/part-of: autodoc` + `app.kubernetes.io/component: <name>`
> - Naming prefix: `autodoc-` (e.g., `autodoc-api`, `autodoc-web`)
> - Service type: `ClusterIP`
> - Probes: httpGet with readiness (initialDelay 10s, period 10s, timeout 5s, failureThreshold 3) and liveness (initialDelay 15s, period 30s, timeout 5s, failureThreshold 3)
> - ConfigMap: extend existing `autodoc-config` rather than creating new configmaps
> - Ingress: nginx class, TLS via `autodoc-tls` secret, `proxy-body-size: 50m` annotation
> - imagePullPolicy: `IfNotPresent`
> - Overlays: `dev-k8s` and `prod` directories under `deployment/k8s/overlays/`

### Requirement: Web frontend deployment
The system SHALL deploy the dashboard web frontend as a Kubernetes Deployment named `autodoc-web` running the nginx-based image built from `web/Dockerfile`. The Deployment SHALL follow the same manifest patterns as the existing `autodoc-api` Deployment.

#### Scenario: Web Deployment labels
- **WHEN** the web Deployment manifest is applied
- **THEN** the Deployment metadata SHALL include labels `app.kubernetes.io/part-of: autodoc` and `app.kubernetes.io/component: web`, and the pod template SHALL use `app.kubernetes.io/component: web` as the selector match label

#### Scenario: Web Deployment specification
- **WHEN** the web Deployment manifest is applied
- **THEN** the Deployment SHALL run the `autodoc-web:latest` image, expose container port 3000, set `imagePullPolicy: IfNotPresent`, and set resource requests of `100m` CPU and `256Mi` memory with limits of `500m` CPU and `512Mi` memory

#### Scenario: Web replica count in base
- **WHEN** the base Deployment manifest is applied
- **THEN** the web Deployment SHALL run with `replicas: 1`

#### Scenario: Web readiness probe
- **WHEN** the web Deployment pods start
- **THEN** each pod SHALL have a readiness probe configured as an HTTP GET to `/health` on port 3000, with `initialDelaySeconds: 10`, `periodSeconds: 10`, `timeoutSeconds: 5`, and `failureThreshold: 3`

#### Scenario: Web liveness probe
- **WHEN** the web Deployment pods are running
- **THEN** each pod SHALL have a liveness probe configured as an HTTP GET to `/health` on port 3000, with `initialDelaySeconds: 15`, `periodSeconds: 30`, `timeoutSeconds: 5`, and `failureThreshold: 3`

#### Scenario: Web environment configuration
- **WHEN** the web Deployment pods start
- **THEN** the pod SHALL load environment variables from the existing `autodoc-config` ConfigMap via `envFrom` (not a separate `web-config` ConfigMap), consistent with how the API Deployment loads configuration

### Requirement: Web frontend Service
The system SHALL expose the web frontend Deployment via a Kubernetes Service named `autodoc-web`, following the same pattern as the existing `autodoc-api` Service.

#### Scenario: Service specification
- **WHEN** the web Service manifest is applied
- **THEN** the Service SHALL be of type `ClusterIP`, expose port 3000 targeting container port 3000, and select pods matching label `app.kubernetes.io/component: web`

#### Scenario: Service labels
- **WHEN** the web Service manifest is applied
- **THEN** the Service metadata SHALL include labels `app.kubernetes.io/part-of: autodoc` and `app.kubernetes.io/component: web`

### Requirement: ConfigMap update for web frontend
The system SHALL add web-specific configuration entries to the existing `autodoc-config` ConfigMap rather than creating a separate ConfigMap.

#### Scenario: Web configuration in autodoc-config
- **WHEN** the `autodoc-config` ConfigMap is inspected
- **THEN** it SHALL contain a `WEB_API_URL` key specifying the in-cluster API endpoint (e.g., `http://autodoc-api:8080`) for the nginx reverse proxy upstream configuration

### Requirement: Ingress update for web dashboard
The system SHALL update the existing Ingress resource to add routing for the web dashboard alongside the existing API and Prefect routes.

#### Scenario: Web dashboard routing
- **WHEN** a request arrives at the root path `/` of the configured host (e.g., `autodoc.example.com`)
- **THEN** the Ingress SHALL route it to the `autodoc-web` Service on port 3000 using `pathType: Prefix`

#### Scenario: API routing preserved
- **WHEN** a request arrives at the path prefix `/api` of the configured host
- **THEN** the Ingress SHALL route it to the `autodoc-api` Service on port 8080, preserving the existing routing rule

#### Scenario: Prefect UI routing preserved
- **WHEN** a request arrives at the Prefect host (e.g., `prefect.autodoc.example.com`)
- **THEN** the Ingress SHALL route it to the `prefect-api` Service on port 4200, preserving the existing routing rule

#### Scenario: TLS and ingress class preserved
- **WHEN** the Ingress manifest is applied
- **THEN** it SHALL use `ingressClassName: nginx`, reference the existing `autodoc-tls` Secret for TLS termination, and include the annotation `nginx.ingress.kubernetes.io/proxy-body-size: "50m"`

### Requirement: Kustomize overlays for web deployment
The system SHALL include web Deployment patches in the existing `dev-k8s` and `prod` Kustomize overlays, following the same overlay structure used for other components.

#### Scenario: Dev overlay web patch
- **WHEN** the `dev-k8s` Kustomize overlay is applied
- **THEN** the web Deployment SHALL run with `replicas: 1` and use the locally-built `autodoc-web:latest` image with `imagePullPolicy: IfNotPresent`

#### Scenario: Prod overlay web patch
- **WHEN** the `prod` Kustomize overlay is applied
- **THEN** the web Deployment SHALL run with `replicas: 2` and use a registry-qualified image tag (e.g., `registry.example.com/autodoc-web:<version>`)

#### Scenario: Base Kustomize includes web resources
- **WHEN** the base `kustomization.yaml` is inspected
- **THEN** it SHALL include the web Deployment, Service, and updated ConfigMap manifests in its `resources` list
