## ADDED Requirements

### Requirement: Flow runner Job template
The system SHALL define a Kubernetes Job template used by Prefect work pools to launch flow runner pods.

#### Scenario: Job template structure
- **WHEN** a Prefect work pool creates a K8s Job for a flow run
- **THEN** the Job SHALL use the Flow Runner image (`Dockerfile.flow`), mount an `emptyDir` volume at `/tmp/autodoc-workspaces`, set resource requests/limits, and run in the `autodoc` namespace with the `prefect-worker` ServiceAccount

#### Scenario: Job labels and annotations
- **WHEN** a flow runner Job is created
- **THEN** it SHALL carry labels identifying `app: autodoc-flow-runner`, the work pool name, the flow name, and the Prefect flow run ID

#### Scenario: Job environment configuration
- **WHEN** a flow runner Job pod starts
- **THEN** it SHALL receive environment variables from the `autodoc-config` ConfigMap, `autodoc-db-credentials` Secret, `autodoc-api-keys` Secret, and `PREFECT_API_URL` pointing to the in-cluster Prefect API Service

### Requirement: Per-Job repository clone with emptyDir
Each flow runner K8s Job SHALL clone the repository into an `emptyDir` volume. Scope processing runs in-process within the orchestrator Job (D13 AMENDED).

#### Scenario: Orchestrator Job clones for scope discovery and processing
- **WHEN** an orchestrator flow runner Job starts
- **THEN** it SHALL clone the repository with `--depth 1` into an `emptyDir`-backed directory, discover `.autodoc.yaml` scope configurations, and process all scopes in-process using the local `repo_path`

#### Scenario: Scope processing runs in-process (AMENDED)
- **WHEN** scope processing is invoked by the orchestrator flow
- **THEN** `scope_processing_flow` SHALL run in-process within the orchestrator K8s Job (not as a separate K8s Job), receiving the orchestrator's `repo_path` directly. This applies to ALL deployment profiles (dev, dev-k8s, prod). The original design of dispatching scopes via `run_deployment()` is deferred because `run_deployment()` returns a `FlowRun` status object, not the flow's return value (`ScopeProcessingResult`).

#### Scenario: Workspace auto-cleanup on pod termination
- **WHEN** a flow runner K8s Job pod terminates (success or failure)
- **THEN** the `emptyDir` volume and all cloned repository data SHALL be automatically deleted by Kubernetes

### Requirement: scope_processing_flow receives repo_path (AMENDED)
The `scope_processing_flow` SHALL receive a local filesystem `repo_path` parameter in all deployment profiles, since it runs in-process within the orchestrator Job.

#### Scenario: All modes receive repo_path
- **WHEN** `scope_processing_flow` is invoked by the orchestrator flow in any deployment profile (dev, dev-k8s, prod)
- **THEN** it SHALL receive `repo_path` directly from the orchestrator's clone and skip cloning. The original design of receiving `clone_input` for K8s mode is deferred along with separate K8s Job dispatch (D13 AMENDED).

### Requirement: cleanup_orphan_workspaces not deployed to K8s
The `cleanup_orphan_workspaces` scheduled Prefect flow SHALL NOT be deployed to K8s environments since emptyDir volumes handle workspace lifecycle automatically.

#### Scenario: Prod Prefect deployments exclude orphan cleanup
- **WHEN** Prefect flows are deployed with `prefect deploy -n <name>` (selective deployment, D15)
- **THEN** the `cleanup_orphan_workspaces` deployment SHALL NOT be included in the deployed set for K8s work pools

#### Scenario: Dev cleanup retained
- **WHEN** Prefect flows are deployed for the dev profile
- **THEN** the `dev-cleanup` deployment for `cleanup_orphan_workspaces` SHALL remain active for Docker Compose environments

### Requirement: Successful Job cleanup
The system SHALL remove K8s Jobs that completed successfully within a short time window.

#### Scenario: Successful Job removed
- **WHEN** a flow runner K8s Job completes with status `Succeeded`
- **THEN** the Job and its Pods SHALL be deleted within 10 minutes of completion

#### Scenario: Cleanup mechanism
- **WHEN** the cleanup CronJob runs (every 5 minutes)
- **THEN** it SHALL find all Jobs in the `autodoc` namespace with status `Succeeded` and `.status.completionTime` older than 5 minutes, and delete them

### Requirement: Failed Job retention
The system SHALL retain K8s Jobs that failed for 24 hours to allow inspection and retry.

#### Scenario: Failed Job retained
- **WHEN** a flow runner K8s Job completes with status `Failed`
- **THEN** the Job and its Pods SHALL remain in the namespace for 24 hours, with `ttlSecondsAfterFinished: 86400` ensuring automatic cleanup after the retention period

#### Scenario: Failed Job logs accessible
- **WHEN** a flow runner Job has failed and is within the 24-hour retention window
- **THEN** an operator SHALL be able to view the Job's pod logs via `kubectl logs` and the Prefect UI's log proxy

### Requirement: Retry dispatches via run_deployment
The system SHALL use Prefect's `run_deployment()` to dispatch flow runs in K8s environments, creating new K8s Jobs via Prefect workers.

#### Scenario: Retry via API in K8s mode
- **WHEN** a user calls `POST /jobs/{id}/retry` for a FAILED job and `AUTODOC_FLOW_DEPLOYMENT_PREFIX` is not `dev`
- **THEN** `_submit_flow()` SHALL call `run_deployment()` with the appropriate deployment name (e.g., `full-generation-flow/prod-full-generation`), which causes the Prefect worker to create a new K8s Job, and the original failed K8s Job SHALL remain until its 24-hour TTL expires

#### Scenario: Retry via API in dev mode
- **WHEN** a user calls `POST /jobs/{id}/retry` for a FAILED job and `AUTODOC_FLOW_DEPLOYMENT_PREFIX` is `dev`
- **THEN** `_submit_flow()` SHALL invoke the flow directly via `asyncio.create_task()` as it does today

#### Scenario: Retry for scope-level failure (AMENDED)
- **WHEN** a full_generation flow run fails due to a scope_processing_flow failure and is retried
- **THEN** a new orchestrator Job SHALL be created which clones the repository and re-processes all scopes in-process, re-executing all tasks from scratch (task result caching is deferred to a future change). Scope processing does NOT fan out to separate K8s Jobs (D13 AMENDED).

### Requirement: Job cleanup CronJob
The system SHALL deploy a Kubernetes CronJob that implements the differential cleanup policy for succeeded Jobs.

#### Scenario: CronJob deployment
- **WHEN** the manifests are applied
- **THEN** a CronJob named `autodoc-job-cleanup` SHALL be created in the `autodoc` namespace, running every 5 minutes

#### Scenario: CronJob permissions
- **WHEN** the cleanup CronJob runs
- **THEN** it SHALL use a ServiceAccount with permissions to list and delete Jobs in the `autodoc` namespace

#### Scenario: CronJob idempotency
- **WHEN** the cleanup CronJob runs and finds no succeeded Jobs to clean up
- **THEN** it SHALL complete successfully with no errors

### Requirement: Work pool concurrency limits
The system SHALL enforce concurrency limits on the Prefect work pools to prevent resource exhaustion.

#### Scenario: Orchestrator pool limit
- **WHEN** the `orchestrator-pool` work pool is configured
- **THEN** it SHALL have a concurrency limit of 10, preventing more than 10 concurrent orchestrator Jobs

#### Scenario: Scope pool limit
- **WHEN** the `k8s-pool` work pool is configured
- **THEN** it SHALL have a concurrency limit of 50, preventing more than 50 concurrent scope processing Jobs

### Requirement: Resource limits on flow runner Jobs
The system SHALL set resource requests and limits on flow runner pods to prevent node resource exhaustion.

#### Scenario: Orchestrator Job resources
- **WHEN** an orchestrator flow runner Job is created
- **THEN** the pod SHALL have configurable CPU and memory requests/limits (default: request 1 CPU / 2Gi, limit 2 CPU / 4Gi)

#### Scenario: Scope worker Job resources
- **WHEN** a scope processing flow runner Job is created
- **THEN** the pod SHALL have configurable CPU and memory requests/limits (default: request 2 CPU / 4Gi, limit 4 CPU / 8Gi)
