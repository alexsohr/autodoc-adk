#!/usr/bin/env python3
"""Prefect Workflow Troubleshooting CLI.

Queries a Prefect Server REST API (self-hosted at port 4200) to inspect,
diagnose, and manage flow runs, task runs, work pools, deployments, and logs.

Usage:
    python scripts/prefect_debug.py <command> [options]

Environment:
    PREFECT_API_URL  Base URL for the Prefect API (default: http://localhost:4200/api)

Reference: docs/prefect-api/openapi.json (Prefect Cloud OpenAPI 3.1 spec)
Note: Self-hosted Prefect Server uses simpler paths without account/workspace prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

import os

PREFECT_API_URL = os.environ.get("PREFECT_API_URL", "http://localhost:4200/api")

# StateType enum from openapi.json
STATE_TYPES = [
    "SCHEDULED", "PENDING", "RUNNING", "COMPLETED",
    "FAILED", "CANCELLED", "CRASHED", "PAUSED", "CANCELLING",
]
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "CRASHED"}
PROBLEM_STATES = {"FAILED", "CRASHED", "CANCELLING"}

# Log levels
LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
LOG_LEVEL_NAMES = {v: k for k, v in LOG_LEVELS.items()}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api(method: str, path: str, body: dict | None = None) -> Any:
    """Make an HTTP request to the Prefect API."""
    url = f"{PREFECT_API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw)
    except HTTPError as e:
        body_text = e.read().decode(errors="replace")
        print(f"HTTP {e.code} {e.reason}: {body_text}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        print(f"Is Prefect Server running at {PREFECT_API_URL}?", file=sys.stderr)
        sys.exit(1)


def api_get(path: str) -> Any:
    return _api("GET", path)


def api_post(path: str, body: dict) -> Any:
    return _api("POST", path, body)


def api_patch(path: str, body: dict) -> Any:
    return _api("PATCH", path, body)


def api_delete(path: str) -> Any:
    return _api("DELETE", path)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def fmt_time(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return str(ts)[:19]


def fmt_duration(start: str | None, end: str | None) -> str:
    if not start:
        return "-"
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime.now(timezone.utc)
        delta = e - s
        total = int(delta.total_seconds())
        if total < 60:
            return f"{total}s"
        if total < 3600:
            return f"{total // 60}m {total % 60}s"
        return f"{total // 3600}h {(total % 3600) // 60}m"
    except (ValueError, AttributeError):
        return "-"


def fmt_state(state: dict | None, state_type: str | None = None, state_name: str | None = None) -> str:
    if state:
        st = state.get("type", state_type or "?")
        sn = state.get("name", state_name or "?")
    else:
        st = state_type or "?"
        sn = state_name or "?"
    colors = {
        "COMPLETED": "\033[32m",  # green
        "RUNNING": "\033[36m",    # cyan
        "FAILED": "\033[31m",     # red
        "CRASHED": "\033[31;1m",  # bold red
        "CANCELLED": "\033[33m",  # yellow
        "CANCELLING": "\033[33m",
        "SCHEDULED": "\033[34m",  # blue
        "PENDING": "\033[90m",    # gray
        "PAUSED": "\033[35m",     # magenta
    }
    reset = "\033[0m"
    color = colors.get(st, "")
    return f"{color}{sn}({st}){reset}"


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Commands: Health
# ---------------------------------------------------------------------------

def cmd_health(_args: argparse.Namespace) -> None:
    """Check Prefect server health and version."""
    print(f"Prefect API: {PREFECT_API_URL}")
    try:
        version = api_get("/admin/version")
        print(f"Server version: {version}")
    except SystemExit:
        print("Server unreachable!")
        return

    try:
        settings = api_get("/admin/settings")
        print(f"Server settings: {json.dumps(settings, indent=2)[:500]}")
    except SystemExit:
        pass


# ---------------------------------------------------------------------------
# Commands: Flow Runs
# ---------------------------------------------------------------------------

def cmd_flow_runs(args: argparse.Namespace) -> None:
    """List/filter flow runs."""
    body: dict[str, Any] = {
        "sort": args.sort,
        "limit": args.limit,
        "offset": args.offset,
    }

    flow_run_filter: dict[str, Any] = {}

    if args.state:
        states = [s.upper() for s in args.state]
        flow_run_filter["state"] = {"type": {"any_": states}}

    if args.name:
        flow_run_filter["name"] = {"like_": f"%{args.name}%"}

    if args.since:
        flow_run_filter["start_time"] = {"after_": args.since}

    if args.deployment_id:
        flow_run_filter["deployment_id"] = {"any_": [args.deployment_id]}

    if args.parent_id:
        flow_run_filter["parent_flow_run_id"] = {"any_": [args.parent_id]}

    if flow_run_filter:
        body["flow_runs"] = flow_run_filter

    if args.flow_name:
        body["flows"] = {"name": {"any_": [args.flow_name]}}

    if args.work_pool:
        body["work_pools"] = {"name": {"any_": [args.work_pool]}}

    runs = api_post("/flow_runs/filter", body)

    if args.json:
        print_json(runs)
        return

    if not runs:
        print("No flow runs found.")
        return

    print(f"{'ID':<38} {'NAME':<30} {'STATE':<25} {'STARTED':<20} {'DURATION':<10} {'FLOW':<20}")
    print("-" * 150)
    for r in runs:
        print(
            f"{r['id']:<38} "
            f"{(r.get('name') or '-')[:29]:<30} "
            f"{fmt_state(r.get('state'), r.get('state_type'), r.get('state_name')):<35} "
            f"{fmt_time(r.get('start_time')):<20} "
            f"{fmt_duration(r.get('start_time'), r.get('end_time')):<10} "
            f"{(r.get('flow_name') or '-')[:19]:<20}"
        )

    print(f"\nShowing {len(runs)} flow runs (offset={args.offset})")


def cmd_flow_run_detail(args: argparse.Namespace) -> None:
    """Get detailed info for a specific flow run."""
    run = api_get(f"/flow_runs/{args.id}")

    if args.json:
        print_json(run)
        return

    print(f"Flow Run: {run.get('name', '-')}")
    print(f"  ID:            {run['id']}")
    print(f"  Flow:          {run.get('flow_name', run.get('flow_id', '-'))}")
    print(f"  Deployment:    {run.get('deployment_id', '-')}")
    print(f"  State:         {fmt_state(run.get('state'), run.get('state_type'), run.get('state_name'))}")
    msg = (run.get("state") or {}).get("message", "")
    if msg:
        print(f"  State Message: {msg}")
    print(f"  Started:       {fmt_time(run.get('start_time'))}")
    print(f"  Ended:         {fmt_time(run.get('end_time'))}")
    print(f"  Duration:      {fmt_duration(run.get('start_time'), run.get('end_time'))}")
    print(f"  Run Count:     {run.get('run_count', '-')}")
    print(f"  Work Pool:     {run.get('work_pool_name', '-')}")
    print(f"  Tags:          {run.get('tags', [])}")
    print(f"  Parameters:    {json.dumps(run.get('parameters', {}), default=str)[:200]}")
    if run.get("parent_task_run_id"):
        print(f"  Parent Task:   {run['parent_task_run_id']}")

    # Get state history
    try:
        states = api_get(f"/flow_run_states/?flow_run_id={run['id']}")
        if states:
            print(f"\n  State History ({len(states)} transitions):")
            for s in states:
                print(f"    {fmt_time(s.get('timestamp'))} -> {fmt_state(s)}")
    except SystemExit:
        pass


def cmd_flow_run_children(args: argparse.Namespace) -> None:
    """List child flow runs of a parent flow run."""
    body = {
        "flow_runs": {"parent_flow_run_id": {"any_": [args.id]}},
        "sort": "EXPECTED_START_TIME_ASC",
        "limit": args.limit,
    }
    runs = api_post("/flow_runs/filter", body)

    if args.json:
        print_json(runs)
        return

    if not runs:
        print("No child flow runs found.")
        return

    print(f"Child flow runs of {args.id}:\n")
    print(f"{'ID':<38} {'NAME':<30} {'STATE':<25} {'STARTED':<20} {'DURATION':<10}")
    print("-" * 130)
    for r in runs:
        print(
            f"{r['id']:<38} "
            f"{(r.get('name') or '-')[:29]:<30} "
            f"{fmt_state(r.get('state'), r.get('state_type'), r.get('state_name')):<35} "
            f"{fmt_time(r.get('start_time')):<20} "
            f"{fmt_duration(r.get('start_time'), r.get('end_time')):<10}"
        )


# ---------------------------------------------------------------------------
# Commands: Task Runs
# ---------------------------------------------------------------------------

def cmd_task_runs(args: argparse.Namespace) -> None:
    """List task runs for a flow run."""
    body: dict[str, Any] = {
        "sort": args.sort,
        "limit": args.limit,
    }

    task_filter: dict[str, Any] = {}
    if args.flow_run_id:
        task_filter["flow_run_id"] = {"any_": [args.flow_run_id]}
    if args.state:
        task_filter["state"] = {"type": {"any_": [s.upper() for s in args.state]}}
    if args.name:
        task_filter["name"] = {"like_": f"%{args.name}%"}

    if task_filter:
        body["task_runs"] = task_filter

    runs = api_post("/task_runs/filter", body)

    if args.json:
        print_json(runs)
        return

    if not runs:
        print("No task runs found.")
        return

    print(f"{'ID':<38} {'NAME':<35} {'STATE':<25} {'STARTED':<20} {'DURATION':<10}")
    print("-" * 135)
    for r in runs:
        print(
            f"{r['id']:<38} "
            f"{(r.get('name') or '-')[:34]:<35} "
            f"{fmt_state(r.get('state'), r.get('state_type'), r.get('state_name')):<35} "
            f"{fmt_time(r.get('start_time')):<20} "
            f"{fmt_duration(r.get('start_time'), r.get('end_time')):<10}"
        )


def cmd_task_run_detail(args: argparse.Namespace) -> None:
    """Get detailed info for a specific task run."""
    run = api_get(f"/task_runs/{args.id}")
    if args.json:
        print_json(run)
        return

    print(f"Task Run: {run.get('name', '-')}")
    print(f"  ID:            {run['id']}")
    print(f"  Flow Run:      {run.get('flow_run_id', '-')}")
    print(f"  State:         {fmt_state(run.get('state'), run.get('state_type'), run.get('state_name'))}")
    msg = (run.get("state") or {}).get("message", "")
    if msg:
        print(f"  State Message: {msg}")
    print(f"  Started:       {fmt_time(run.get('start_time'))}")
    print(f"  Ended:         {fmt_time(run.get('end_time'))}")
    print(f"  Duration:      {fmt_duration(run.get('start_time'), run.get('end_time'))}")
    print(f"  Run Count:     {run.get('run_count', '-')}")
    print(f"  Tags:          {run.get('tags', [])}")


# ---------------------------------------------------------------------------
# Commands: Logs
# ---------------------------------------------------------------------------

def cmd_logs(args: argparse.Namespace) -> None:
    """View logs for a flow run or task run."""
    body: dict[str, Any] = {
        "sort": "TIMESTAMP_DESC" if args.reverse else "TIMESTAMP_ASC",
        "limit": args.limit,
        "offset": args.offset,
    }

    log_filter: dict[str, Any] = {}
    if args.flow_run_id:
        log_filter["flow_run_id"] = {"any_": [args.flow_run_id]}
    if args.task_run_id:
        log_filter["task_run_id"] = {"any_": [args.task_run_id]}
    if args.level:
        min_level = LOG_LEVELS.get(args.level.upper(), 20)
        log_filter["level"] = {"ge_": min_level}
    if args.search:
        log_filter["text"] = {"query": args.search[:200]}

    if log_filter:
        body["logs"] = log_filter

    logs = api_post("/logs/filter", body)

    if args.json:
        print_json(logs)
        return

    if not logs:
        print("No logs found.")
        return

    for entry in logs:
        level = LOG_LEVEL_NAMES.get(entry.get("level", 0), "?")
        ts = fmt_time(entry.get("timestamp"))
        msg = entry.get("message", "")
        name = entry.get("name", "")

        level_colors = {
            "ERROR": "\033[31m", "CRITICAL": "\033[31;1m",
            "WARNING": "\033[33m", "INFO": "\033[0m", "DEBUG": "\033[90m",
        }
        color = level_colors.get(level, "")
        reset = "\033[0m"
        print(f"{color}{ts} [{level:8s}] {name}: {msg}{reset}")

    print(f"\n--- {len(logs)} log entries (offset={args.offset}) ---")


# ---------------------------------------------------------------------------
# Commands: Work Pools
# ---------------------------------------------------------------------------

def cmd_work_pools(args: argparse.Namespace) -> None:
    """List work pools and their status."""
    body: dict[str, Any] = {"limit": args.limit}
    if args.name:
        body["work_pools"] = {"name": {"any_": [args.name]}}

    pools = api_post("/work_pools/filter", body)

    if args.json:
        print_json(pools)
        return

    if not pools:
        print("No work pools found.")
        return

    print(f"{'NAME':<25} {'TYPE':<15} {'STATUS':<12} {'CONCURRENCY':<15} {'DEFAULT QUEUE':<20}")
    print("-" * 90)
    for p in pools:
        cl = p.get("concurrency_limit")
        cl_str = str(cl) if cl is not None else "unlimited"
        print(
            f"{p.get('name', '-'):<25} "
            f"{p.get('type', '-'):<15} "
            f"{p.get('status', '-'):<12} "
            f"{cl_str:<15} "
            f"{p.get('default_queue_id', '-')[:19]:<20}"
        )

    # Show workers for each pool
    if args.workers:
        for p in pools:
            name = p.get("name", "")
            print(f"\n  Workers in '{name}':")
            try:
                workers = api_post(f"/work_pools/{name}/workers/filter", {"limit": 50})
                if not workers:
                    print("    (none)")
                    continue
                for w in workers:
                    last_hb = fmt_time(w.get("last_heartbeat_time"))
                    print(f"    {w.get('name', '-'):<30} status={w.get('status', '?'):<10} last_heartbeat={last_hb}")
            except SystemExit:
                print("    (error fetching workers)")


# ---------------------------------------------------------------------------
# Commands: Deployments
# ---------------------------------------------------------------------------

def cmd_deployments(args: argparse.Namespace) -> None:
    """List deployments."""
    body: dict[str, Any] = {
        "sort": "NAME_ASC",
        "limit": args.limit,
    }

    dep_filter: dict[str, Any] = {}
    if args.name:
        dep_filter["name"] = {"like_": f"%{args.name}%"}
    if args.paused is not None:
        dep_filter["paused"] = {"eq_": args.paused}

    if dep_filter:
        body["deployments"] = dep_filter

    if args.work_pool:
        body["work_pools"] = {"name": {"any_": [args.work_pool]}}

    deps = api_post("/deployments/filter", body)

    if args.json:
        print_json(deps)
        return

    if not deps:
        print("No deployments found.")
        return

    print(f"{'ID':<38} {'NAME':<35} {'FLOW':<20} {'STATUS':<10} {'WORK POOL':<15}")
    print("-" * 120)
    for d in deps:
        paused = "paused" if d.get("paused") else "active"
        print(
            f"{d['id']:<38} "
            f"{(d.get('name') or '-')[:34]:<35} "
            f"{(d.get('flow_id') or '-')[:19]:<20} "
            f"{paused:<10} "
            f"{(d.get('work_pool_name') or '-')[:14]:<15}"
        )


# ---------------------------------------------------------------------------
# Commands: Cancel / Set State
# ---------------------------------------------------------------------------

def cmd_cancel(args: argparse.Namespace) -> None:
    """Cancel a flow run."""
    result = api_post(f"/flow_runs/{args.id}/set_state", {
        "state": {"type": "CANCELLING", "message": args.message or "Cancelled via prefect_debug.py"},
        "force": args.force,
    })
    print(f"Cancel request sent for flow run {args.id}")
    if result:
        print(f"Result: {json.dumps(result, default=str)}")


def cmd_set_state(args: argparse.Namespace) -> None:
    """Force-set the state of a flow run."""
    state_type = args.state_type.upper()
    if state_type not in STATE_TYPES:
        print(f"Invalid state type: {state_type}. Must be one of: {STATE_TYPES}", file=sys.stderr)
        sys.exit(1)

    result = api_post(f"/flow_runs/{args.id}/set_state", {
        "state": {"type": state_type, "message": args.message or f"Force-set to {state_type} via prefect_debug.py"},
        "force": args.force,
    })
    print(f"State set to {state_type} for flow run {args.id}")
    if result:
        print(f"Result: {json.dumps(result, default=str)}")


# ---------------------------------------------------------------------------
# Commands: Diagnose
# ---------------------------------------------------------------------------

def cmd_diagnose(args: argparse.Namespace) -> None:
    """Run a comprehensive diagnostic on the Prefect environment."""
    print("=" * 60)
    print("PREFECT DIAGNOSTIC REPORT")
    print(f"Server: {PREFECT_API_URL}")
    print(f"Time:   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # 1. Server health
    print("\n--- Server Health ---")
    try:
        version = api_get("/admin/version")
        print(f"  Version: {version}")
    except SystemExit:
        print("  ERROR: Server unreachable!")
        return

    # 2. Work pools
    print("\n--- Work Pools ---")
    try:
        pools = api_post("/work_pools/filter", {"limit": 50})
        for p in pools or []:
            name = p.get("name", "?")
            status = p.get("status", "?")
            cl = p.get("concurrency_limit")
            print(f"  {name}: type={p.get('type','?')} status={status} concurrency={cl or 'unlimited'}")

            # Check workers
            try:
                workers = api_post(f"/work_pools/{name}/workers/filter", {"limit": 50})
                if not workers:
                    print(f"    WARNING: No workers registered!")
                else:
                    for w in workers:
                        print(f"    Worker: {w.get('name','?')} status={w.get('status','?')} heartbeat={fmt_time(w.get('last_heartbeat_time'))}")
            except SystemExit:
                pass
    except SystemExit:
        print("  ERROR: Could not list work pools")

    # 3. Problem flow runs
    since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).isoformat()
    print(f"\n--- Problem Flow Runs (last {args.hours}h) ---")
    try:
        problems = api_post("/flow_runs/filter", {
            "flow_runs": {
                "state": {"type": {"any_": list(PROBLEM_STATES)}},
                "start_time": {"after_": since},
            },
            "sort": "START_TIME_DESC",
            "limit": 20,
        })
        if not problems:
            print("  No failed/crashed/cancelling runs found.")
        else:
            for r in problems:
                state = fmt_state(r.get("state"), r.get("state_type"), r.get("state_name"))
                msg = (r.get("state") or {}).get("message", "")[:80]
                print(f"  {r['id'][:8]}.. {(r.get('name') or '-')[:25]:<25} {state}")
                if msg:
                    print(f"    Message: {msg}")
    except SystemExit:
        print("  ERROR: Could not query flow runs")

    # 4. Stuck runs (RUNNING for too long)
    print(f"\n--- Potentially Stuck Runs (RUNNING > {args.stuck_threshold}min) ---")
    try:
        threshold = (datetime.now(timezone.utc) - timedelta(minutes=args.stuck_threshold)).isoformat()
        stuck = api_post("/flow_runs/filter", {
            "flow_runs": {
                "state": {"type": {"any_": ["RUNNING"]}},
                "start_time": {"before_": threshold},
            },
            "sort": "START_TIME_ASC",
            "limit": 20,
        })
        if not stuck:
            print("  No stuck runs detected.")
        else:
            for r in stuck:
                dur = fmt_duration(r.get("start_time"), None)
                print(f"  {r['id'][:8]}.. {(r.get('name') or '-')[:25]:<25} running for {dur}")
    except SystemExit:
        print("  ERROR: Could not query running flow runs")

    # 5. Scheduled but not started
    print(f"\n--- Late Runs (SCHEDULED/PENDING, expected > {args.late_threshold}min ago) ---")
    try:
        late_threshold = (datetime.now(timezone.utc) - timedelta(minutes=args.late_threshold)).isoformat()
        late = api_post("/flow_runs/filter", {
            "flow_runs": {
                "state": {"type": {"any_": ["SCHEDULED", "PENDING"]}},
                "expected_start_time": {"before_": late_threshold},
            },
            "sort": "EXPECTED_START_TIME_ASC",
            "limit": 20,
        })
        if not late:
            print("  No late runs detected.")
        else:
            for r in late:
                expected = fmt_time(r.get("expected_start_time"))
                print(f"  {r['id'][:8]}.. {(r.get('name') or '-')[:25]:<25} expected at {expected}")
    except SystemExit:
        print("  ERROR: Could not query scheduled flow runs")

    # 6. Recent activity summary
    print(f"\n--- Activity Summary (last {args.hours}h) ---")
    for state_type in STATE_TYPES:
        try:
            count = api_post("/flow_runs/count", {
                "flow_runs": {
                    "state": {"type": {"any_": [state_type]}},
                    "start_time": {"after_": since},
                },
            })
            if count and count > 0:
                marker = " <<<" if state_type in PROBLEM_STATES else ""
                print(f"  {state_type:<15} {count}{marker}")
        except SystemExit:
            pass

    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# Commands: Trigger
# ---------------------------------------------------------------------------

def cmd_trigger(args: argparse.Namespace) -> None:
    """Trigger a flow run from a deployment."""
    body: dict[str, Any] = {}
    if args.name:
        body["name"] = args.name
    if args.params:
        try:
            body["parameters"] = json.loads(args.params)
        except json.JSONDecodeError:
            print("Invalid JSON for --params", file=sys.stderr)
            sys.exit(1)
    if args.tags:
        body["tags"] = args.tags

    result = api_post(f"/deployments/{args.deployment_id}/create_flow_run", body)
    print(f"Flow run created: {result.get('id', '?')}")
    print(f"  Name:  {result.get('name', '-')}")
    print(f"  State: {fmt_state(result.get('state'))}")


# ---------------------------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prefect Workflow Troubleshooting CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-url", help="Override PREFECT_API_URL")
    sub = parser.add_subparsers(dest="command", required=True)

    # health
    sub.add_parser("health", help="Check server health")

    # flow-runs
    fr = sub.add_parser("flow-runs", help="List/filter flow runs")
    fr.add_argument("--state", nargs="+", help="Filter by state type(s)")
    fr.add_argument("--name", help="Filter by name pattern")
    fr.add_argument("--flow-name", help="Filter by flow name")
    fr.add_argument("--deployment-id", help="Filter by deployment ID")
    fr.add_argument("--parent-id", help="Filter by parent flow run ID")
    fr.add_argument("--work-pool", help="Filter by work pool name")
    fr.add_argument("--since", help="Only runs started after this ISO datetime")
    fr.add_argument("--sort", default="START_TIME_DESC", help="Sort order")
    fr.add_argument("--limit", type=int, default=20, help="Max results")
    fr.add_argument("--offset", type=int, default=0, help="Offset")
    fr.add_argument("--json", action="store_true", help="Raw JSON output")

    # flow-run (detail)
    frd = sub.add_parser("flow-run", help="Get flow run details")
    frd.add_argument("id", help="Flow run ID")
    frd.add_argument("--json", action="store_true")

    # children
    ch = sub.add_parser("children", help="List child flow runs")
    ch.add_argument("id", help="Parent flow run ID")
    ch.add_argument("--limit", type=int, default=50)
    ch.add_argument("--json", action="store_true")

    # task-runs
    tr = sub.add_parser("task-runs", help="List task runs")
    tr.add_argument("--flow-run-id", help="Filter by flow run ID")
    tr.add_argument("--state", nargs="+", help="Filter by state type(s)")
    tr.add_argument("--name", help="Filter by name pattern")
    tr.add_argument("--sort", default="EXPECTED_START_TIME_ASC")
    tr.add_argument("--limit", type=int, default=50)
    tr.add_argument("--json", action="store_true")

    # task-run (detail)
    trd = sub.add_parser("task-run", help="Get task run details")
    trd.add_argument("id", help="Task run ID")
    trd.add_argument("--json", action="store_true")

    # logs
    lg = sub.add_parser("logs", help="View logs")
    lg.add_argument("--flow-run-id", help="Filter by flow run ID")
    lg.add_argument("--task-run-id", help="Filter by task run ID")
    lg.add_argument("--level", default="INFO", help="Minimum log level")
    lg.add_argument("--search", help="Text search in log messages")
    lg.add_argument("--reverse", action="store_true", help="Newest first")
    lg.add_argument("--limit", type=int, default=100)
    lg.add_argument("--offset", type=int, default=0)
    lg.add_argument("--json", action="store_true")

    # work-pools
    wp = sub.add_parser("work-pools", help="List work pools")
    wp.add_argument("--name", help="Filter by name")
    wp.add_argument("--workers", action="store_true", help="Show workers")
    wp.add_argument("--limit", type=int, default=50)
    wp.add_argument("--json", action="store_true")

    # deployments
    dp = sub.add_parser("deployments", help="List deployments")
    dp.add_argument("--name", help="Filter by name pattern")
    dp.add_argument("--work-pool", help="Filter by work pool")
    dp.add_argument("--paused", type=bool, help="Filter by paused status")
    dp.add_argument("--limit", type=int, default=50)
    dp.add_argument("--json", action="store_true")

    # cancel
    cn = sub.add_parser("cancel", help="Cancel a flow run")
    cn.add_argument("id", help="Flow run ID")
    cn.add_argument("--message", help="Cancellation message")
    cn.add_argument("--force", action="store_true", help="Bypass orchestration rules")

    # set-state
    ss = sub.add_parser("set-state", help="Force-set flow run state")
    ss.add_argument("id", help="Flow run ID")
    ss.add_argument("state_type", help=f"State type: {STATE_TYPES}")
    ss.add_argument("--message", help="State message")
    ss.add_argument("--force", action="store_true", default=True, help="Bypass orchestration rules")

    # diagnose
    dg = sub.add_parser("diagnose", help="Run comprehensive diagnostics")
    dg.add_argument("--hours", type=int, default=24, help="Lookback hours")
    dg.add_argument("--stuck-threshold", type=int, default=60, help="Minutes before a RUNNING run is considered stuck")
    dg.add_argument("--late-threshold", type=int, default=15, help="Minutes before a SCHEDULED run is considered late")

    # trigger
    tg = sub.add_parser("trigger", help="Trigger a deployment flow run")
    tg.add_argument("deployment_id", help="Deployment ID")
    tg.add_argument("--name", help="Flow run name")
    tg.add_argument("--params", help="JSON parameters")
    tg.add_argument("--tags", nargs="+", help="Tags")

    args = parser.parse_args()

    if args.api_url:
        global PREFECT_API_URL
        PREFECT_API_URL = args.api_url

    handlers = {
        "health": cmd_health,
        "flow-runs": cmd_flow_runs,
        "flow-run": cmd_flow_run_detail,
        "children": cmd_flow_run_children,
        "task-runs": cmd_task_runs,
        "task-run": cmd_task_run_detail,
        "logs": cmd_logs,
        "work-pools": cmd_work_pools,
        "deployments": cmd_deployments,
        "cancel": cmd_cancel,
        "set-state": cmd_set_state,
        "diagnose": cmd_diagnose,
        "trigger": cmd_trigger,
    }

    handlers[args.command](args)


if __name__ == "__main__":
    main()
