# Quickstart: AutoDoc ADK Documentation Generator

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose (for PostgreSQL + Prefect Server)
- Git
- A GitHub or Bitbucket repository to document

## Option A: Full Docker Stack (Quickest)

Start all services with a single command:

```bash
# Clone and enter the project
git clone <repo-url> autodoc-adk
cd autodoc-adk

# Copy environment configuration
cp .env.example .env

# Start all services (PostgreSQL, Prefect Server, Worker, API)
make up

# Run database migrations
make migrate
```

Services available at:
- **API**: http://localhost:8080
- **Prefect UI**: http://localhost:4200
- **PostgreSQL**: localhost:5432 (autodoc + prefect databases)

## Option B: Hybrid Development (Recommended for Development)

Run infrastructure in Docker, API and worker natively for fast iteration:

```bash
# Start infrastructure only (PostgreSQL + Prefect Server)
make dev-up

# In terminal 1: Register flow deployments
make deploy-local

# In terminal 2: Start the Prefect worker
make worker

# In terminal 3: Start the API with hot reload
make api
```

## Setup

### 1. Install Dependencies

```bash
# Install dependencies (uv creates venv automatically)
uv sync
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Required: Database
DATABASE_URL=postgresql+asyncpg://autodoc:autodoc@localhost:5432/autodoc

# Required: Prefect
PREFECT_API_URL=http://localhost:4200/api
PREFECT_WORK_POOL=local-dev
AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev

# Required: Default LLM model (used when agent-specific var is unset)
DEFAULT_MODEL=gemini-2.5-flash

# Optional: Per-agent model overrides (provider-prefixed strings)
# Supports: gemini-* (native), vertex_ai/*, azure/*, bedrock/*
STRUCTURE_GENERATOR_MODEL=gemini-2.5-flash
STRUCTURE_CRITIC_MODEL=gemini-2.5-flash
PAGE_GENERATOR_MODEL=gemini-2.5-flash
PAGE_CRITIC_MODEL=gemini-2.5-flash
README_GENERATOR_MODEL=gemini-2.5-flash
README_CRITIC_MODEL=gemini-2.5-flash

# Required: Embedding model
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072

# Provider credentials (set only for providers you use)
# --- Google Vertex AI (for vertex_ai/* models) ---
# VERTEXAI_PROJECT=your-gcp-project
# VERTEXAI_LOCATION=us-central1
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# --- Azure OpenAI (for azure/* models) ---
# AZURE_API_KEY=your-key
# AZURE_API_BASE=https://your-resource.openai.azure.com
# AZURE_API_VERSION=2024-06-01

# --- AWS Bedrock (for bedrock/* models) ---
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret
# AWS_REGION_NAME=us-east-1

# Optional: GitHub token for private repos
GITHUB_DEFAULT_TOKEN=ghp_...

# Optional: Session archival
SESSION_ARCHIVE_BUCKET=autodoc-sessions
```

### 3. Run Migrations

```bash
make migrate
```

## Basic Usage

### Register a Repository

```bash
curl -X POST http://localhost:8080/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://github.com/org/my-repo",
    "provider": "github",
    "branch_mappings": {"main": "main"},
    "public_branch": "main"
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://github.com/org/my-repo",
  "provider": "github",
  "org": "org",
  "name": "my-repo",
  "branch_mappings": {"main": "main"},
  "public_branch": "main",
  "created_at": "2026-02-15T10:00:00Z"
}
```

### Trigger Documentation Generation

```bash
# First run (no stored commit SHA → full generation)
curl -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "550e8400-e29b-41d4-a716-446655440000",
    "branch": "main"
  }'
```

The system auto-determines full vs. incremental mode based on whether any WikiStructure exists for the repository and branch in the database (per spec FR-003a).

### Check Job Status

```bash
curl http://localhost:8080/jobs/{job_id}
```

### Search Documentation

```bash
# Hybrid search (default) — combines text + semantic via RRF
curl "http://localhost:8080/documents/{repo_id}/search?query=authentication&search_type=hybrid"

# Text-only search
curl "http://localhost:8080/documents/{repo_id}/search?query=authentication&search_type=text"

# Semantic search
curl "http://localhost:8080/documents/{repo_id}/search?query=how+does+auth+work&search_type=semantic"
```

### Force Full Regeneration

```bash
curl -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "550e8400-e29b-41d4-a716-446655440000",
    "branch": "main",
    "force": true
  }'
```

### Dry Run (Structure Only)

```bash
curl -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "550e8400-e29b-41d4-a716-446655440000",
    "branch": "main",
    "dry_run": true
  }'
```

## Testing

```bash
# Run all tests
make test

# Unit tests only
make test-unit

# Integration tests (requires running PostgreSQL)
make test-integration

# Test individual agents in isolation via ADK WebUI
adk web src/agents/structure_extractor
adk web src/agents/page_generator
adk web src/agents/readme_distiller
```

## Monitoring

- **Prefect UI**: http://localhost:4200 — primary ops dashboard for flow runs, task states, retry history
- **API Job Status**: `GET /jobs/{id}` — programmatic access to job status, quality reports, token usage
- **Health Check**: `GET /health` — dependency status (database, Prefect, OTel)

## Repository Configuration

Place a `.autodoc.yaml` in your repository root (or in sub-directories for monorepo scopes):

```yaml
version: 1

include:
  - src/
  - lib/

exclude:
  - "*.test.*"
  - __pycache__/

style:
  audience: "junior-developer"
  tone: "tutorial"
  detail_level: "comprehensive"

custom_instructions: |
  DPU stands for "Data Processing Unit".
  Always document error handling patterns.

readme:
  output_path: "README.md"
  max_length: null
  include_toc: true
  include_badges: true

pull_request:
  auto_merge: false
  reviewers: ["@team-leads"]
```

## Webhook Setup (Optional)

Configure your Git provider to send push webhooks to:

```
POST http://your-host:8080/webhooks/push
```

The system detects the provider from request headers, extracts the repo URL and branch, and auto-triggers an incremental update if the repository is registered and the branch is in the configured documentation branches.
