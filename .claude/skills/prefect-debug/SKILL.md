---
name: prefect-debug
description: Troubleshoot Prefect workflows — diagnose failed/stuck/late flow runs, inspect task runs, view logs, check work pools, cancel runs, and manage state. Use this skill whenever the user mentions Prefect workflow issues, flow run failures, stuck or pending runs, work pool problems, worker connectivity, deployment troubleshooting, or wants to inspect what's happening in Prefect. Even if they just say "something's wrong with the pipeline" or "my job isn't running", this skill likely applies.
---

# Prefect Workflow Troubleshooting

You are diagnosing Prefect 3 workflow issues on a self-hosted Prefect Server (Docker, port 4200).

**Scope: This is a diagnostic skill.** Focus on investigating and explaining what's wrong. Do not write new code, create tests, or refactor project files. If you identify code-level fixes needed, describe them in your analysis but don't implement them unless the user explicitly asks.

## Architecture Context

This project (autodoc-adk) uses:
- **Three work pools**: `orchestrator-pool` (kubernetes, limit 10), `k8s-pool` (kubernetes, limit 50), `local-dev` (process)
- **K8s job per scope**: Each documentation scope runs as a separate K8s job via `run_deployment()`
- **Orchestrator + worker separation**: Parent flows in `orchestrator-pool`, scope workers in `k8s-pool`
- **Flow types**: `full_generation_flow`, `incremental_update_flow`, `scope_processing_flow`
- **Job statuses in app DB**: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED

## CLI Tool

A dedicated CLI is bundled at `.claude/skills/prefect-debug/scripts/prefect_debug.py`. Use it for all Prefect queries — it's more readable and repeatable than raw curl.

**Important: Run the script with `uv run python`** (not bare `python`) since this project uses uv for dependency management. The script uses only stdlib so it doesn't need extra deps, but `python` may not be on PATH in uv-managed environments.

```bash
# Quick reference (always use `uv run python`, not `python`)
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py health
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py diagnose [--hours 24] [--stuck-threshold 60] [--late-threshold 15]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py flow-runs [--state FAILED CRASHED] [--flow-name X] [--limit 20]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py flow-run <id>
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py children <parent-id>
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py task-runs --flow-run-id <id> [--state FAILED]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py task-run <id>
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py logs --flow-run-id <id> [--level ERROR] [--search "traceback"]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py work-pools [--workers]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py deployments
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py cancel <id>
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py set-state <id> FAILED [--message "reason"]
uv run uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py trigger <deployment-id> [--params '{"key": "val"}']
```

All commands support `--json` for raw output. Override URL: `--api-url http://host:port/api` or `PREFECT_API_URL` env var.

**Short ID prefixes work everywhere.** You don't need to copy full UUIDs — `flow-run 844e0247` will auto-resolve to the full ID via prefix matching. This works for `flow-run`, `children`, `task-run`, `cancel`, and `set-state` commands. If a prefix is ambiguous, the CLI lists matches and exits.

**Flow names are resolved automatically.** The `flow-runs` and `flow-run` commands resolve the raw `flow_id` to human-readable flow names (e.g., `scope_processing_flow`) via the `/flows/filter` API.

## Troubleshooting Workflow

Follow this sequence. Each step builds on the previous — don't skip ahead.

### Step 1: Health Check
```bash
uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py health
```
If unreachable, check Docker: `docker ps | grep prefect`

### Step 2: Diagnostics
```bash
uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py diagnose
```
This checks: server health, work pools + workers, failed/crashed runs, stuck runs (RUNNING too long), late runs (SCHEDULED/PENDING past expected start), and an activity summary.

### Step 3: Data Not Found? Check the Server

If `diagnose` shows zero activity or the expected flow runs are missing, the run likely happened on a **different Prefect Server instance** (e.g., production vs. local dev). This is common — ask the user which environment the run was on, or try:
```bash
# Point at a different server
uv run python .claude/skills/prefect-debug/scripts/prefect_debug.py --api-url http://<other-host>:4200/api flow-runs --limit 10
```
Also check the application database for job records that might reference a `prefect_flow_run_id` you can look up.

### Step 4: Drill Down Based on Findings

**FAILED/CRASHED runs:**
1. Get detail: `flow-run <id>` — check the state message
2. Check task-level failures: `task-runs --flow-run-id <id> --state FAILED`
3. View error logs: `logs --flow-run-id <id> --level ERROR`
4. Search for tracebacks: `logs --flow-run-id <id> --search "traceback"`
5. For parent flows, check children: `children <id>`

**STUCK runs (RUNNING too long):**
1. Inspect the run: `flow-run <id>`
2. Check children: `children <id>` — is a child stuck?
3. Check workers: `work-pools --workers` — are they alive?
4. Look for deadlocks: are both `orchestrator-pool` AND `k8s-pool` at capacity?
5. If truly stuck: `cancel <id>`

**LATE runs (SCHEDULED/PENDING not starting):**
1. Check work pools and workers: `work-pools --workers`
2. No workers? They need to be started. Check Docker: `docker ps | grep worker`
3. Pool paused? Check pool status field
4. Concurrency limit reached? Compare RUNNING count vs pool limit

**No workers registered:**
- Check Docker: `docker ps | grep worker`
- Check worker logs: `docker logs <worker-container>`
- For local dev: ensure `make worker` or `prefect worker start --pool local-dev` is running

### Step 5: Go Deeper — Check Source Code

When Prefect API data alone doesn't explain the issue (e.g., the flow crashed but logs don't show why, or the app DB shows RUNNING but Prefect shows CRASHED), investigate the flow source code:

- **Flow definitions**: `src/flows/full_generation.py`, `src/flows/incremental_update.py`
- **How flows are submitted**: `src/api/routes/jobs.py` — check if flows run in-process (`asyncio.create_task`) vs. via deployment (`run_deployment`)
- **Reconciliation**: `src/flows/tasks/reconcile.py` — catches orphaned RUNNING jobs
- **Error handling**: Check whether the flow's exception handlers can actually run during the observed failure mode (e.g., process kill bypasses Python exception handlers)

This step often reveals architectural issues the API data can't show — like flows running in-process being vulnerable to API restarts, or missing `prefect_flow_run_id` storage breaking reconciliation.

## Prefect REST API Quick Reference

**Base URL**: `http://localhost:4200/api` — the full OpenAPI spec is at `docs/prefect-api/openapi.json`.

### State Types

| State | Terminal? | Description |
|-------|-----------|-------------|
| `SCHEDULED` | No | Awaiting scheduled start |
| `PENDING` | No | Awaiting execution resources |
| `RUNNING` | No | Currently executing |
| `COMPLETED` | Yes | Finished successfully |
| `FAILED` | Yes | Execution failed |
| `CANCELLED` | Yes | User-cancelled |
| `CANCELLING` | No | Cancellation in progress |
| `CRASHED` | Yes | Infrastructure died unexpectedly |
| `PAUSED` | No | Temporarily suspended |

### Key Endpoints

```
POST /api/flow_runs/filter          — List/filter flow runs
GET  /api/flow_runs/{id}            — Get specific flow run
POST /api/flow_runs/{id}/set_state  — Set state (cancel, force-complete)
POST /api/flow_runs/count           — Count matching flow runs
GET  /api/flow_run_states/?flow_run_id={id}  — State history

POST /api/task_runs/filter          — List/filter task runs
GET  /api/task_runs/{id}            — Get specific task run

POST /api/logs/filter               — Query logs (text search supported)

POST /api/work_pools/filter         — List work pools
GET  /api/work_pools/{name}         — Get work pool by name
POST /api/work_pools/{name}/workers/filter  — List workers

POST /api/deployments/filter        — List deployments
POST /api/deployments/{id}/create_flow_run  — Trigger a run

GET  /api/admin/version             — Server version
```

### Filter Patterns

```json
{
  "sort": "START_TIME_DESC",
  "limit": 50,
  "flow_runs": {
    "state": { "type": { "any_": ["FAILED", "CRASHED"] } },
    "start_time": { "after_": "2026-03-10T00:00:00Z" },
    "name": { "like_": "%generation%" },
    "parent_flow_run_id": { "any_": ["<uuid>"] }
  },
  "flows": { "name": { "any_": ["full_generation_flow"] } },
  "work_pools": { "name": { "any_": ["k8s-pool"] } }
}
```

**Log levels**: DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50

**Sort options**: FlowRunSort: `START_TIME_DESC`, `START_TIME_ASC`, `EXPECTED_START_TIME_ASC`, `END_TIME_DESC`, `NAME_ASC` | TaskRunSort: `EXPECTED_START_TIME_ASC`, `NAME_ASC` | LogSort: `TIMESTAMP_ASC`, `TIMESTAMP_DESC`

## Common autodoc-adk Issues

1. **Stale RUNNING job in app DB**: Flow crashed in Prefect but app DB still shows RUNNING because exception handlers couldn't execute (process killed). Fix: restart API to trigger `reconcile_stale_jobs`, or manually UPDATE the job to FAILED.

2. **Orchestrator deadlock**: `orchestrator-pool` full (10 concurrent) while child flows in `k8s-pool` also at capacity. Check both pools' RUNNING counts vs limits.

3. **Scope worker OOM**: K8s jobs for AI-heavy scope workers may OOM. Look for CRASHED state with infrastructure failure messages.

4. **LLM API failures**: Rate limits (HTTP 429) or timeouts in page generation / critic loops. Check task-level FAILED states and search logs for "429" or "timeout".

5. **Database connection pool exhaustion**: Too many concurrent flows. Search logs for "connection pool" or "asyncpg" errors. Check pool_size and max_overflow settings.

6. **Missing infrastructure**: No work pools, no deployments, no workers — flows can't be picked up. Run `prefect work-pool create`, `prefect deploy --all`, start workers.

7. **In-process flow vulnerability**: Flows run via `asyncio.create_task()` in the API process are killed by API restarts/hot-reload. Look for "cancelled by the runtime environment" crash messages. Fix: use `run_deployment()` to submit to work pools instead.

## Notes

- The OpenAPI spec at `docs/prefect-api/openapi.json` is Prefect Cloud format. Self-hosted server uses simpler paths (no account/workspace prefix).
- All datetimes are ISO 8601 UTC. Filter endpoints use POST.
- `force: true` on `set_state` bypasses orchestration rules — use with caution.
- `CANCELLING` is transitional; the worker transitions it to `CANCELLED`.
