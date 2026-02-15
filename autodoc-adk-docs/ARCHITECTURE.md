# AutoDoc ADK Architecture Document

> **Purpose**: This document captures the architecture of the existing AutoDoc v2 system for reference when building a new version using Google Agent Development Kit (ADK).

## Executive Summary

AutoDoc is an AI-powered repository documentation generator that:
- Analyzes Git repositories automatically
- Generates comprehensive, searchable wiki documentation
- Provides conversational AI for codebase questions (RAG)
- Supports webhooks for real-time documentation updates

---

## Current Technology Stack

### Backend Infrastructure
| Component | Current | Purpose |
|-----------|---------|---------|
| Web Framework | FastAPI | Async HTTP API server |
| Agent Orchestration | LangGraph | AI workflow management |
| Database | MongoDB + Beanie ODM | Document storage with vector search |
| LLM Providers | OpenAI, Google Gemini, Ollama | Multi-provider LLM support |
| Embeddings | OpenAI/Gemini/Ollama | Vector embeddings for semantic search |
| Filesystem Tools | MCP (Model Context Protocol) | Agent file access |
| Logging | structlog | Structured JSON logging |
| Retry Logic | tenacity | Exponential backoff retries |

### Agent Architecture Components
| Component | Current Implementation |
|-----------|----------------------|
| Workflow Engine | LangGraph StateGraph |
| Agent Pattern | React agents with structured output |
| Tool Framework | LangChain BaseTool |
| Middleware | Custom middleware stack (retry, summarization, memory) |
| State Management | TypedDict with reducers |
| Checkpointing | MemorySaver |

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer (FastAPI)                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │  Repositories│ │    Chat     │ │    Wiki     │ │       Webhooks          ││
│  │   /api/v2/  │ │  /chat/     │ │  /wiki/     │ │  /webhooks/github       ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Service Layer                                     │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │ RepositoryService│ │   ChatService   │ │   WikiService   │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Workflow Orchestrator                                │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    WorkflowOrchestrator                                 │ │
│  │  - FULL_ANALYSIS: validate → process_docs → generate_wiki → finalize  │ │
│  │  - DOCUMENT_PROCESSING: validate → process_docs → finalize            │ │
│  │  - WIKI_GENERATION: validate → generate_wiki → finalize               │ │
│  │  - INCREMENTAL_UPDATE: detect_changes → update → finalize             │ │
│  │  - CHAT_RESPONSE: retrieve_context → generate → finalize              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  Document Agent      │ │    Wiki Agent        │ │    Chat Agent        │
│  ──────────────────  │ │  ──────────────────  │ │  ──────────────────  │
│  - Clone repository  │ │  - Extract structure │ │  - Retrieve context  │
│  - Build file tree   │ │  - Fan-out pages     │ │  - Generate response │
│  - Extract docs      │ │  - Generate content  │ │  - Format citations  │
│  - Apply exclusions  │ │  - Fan-in aggregate  │ │                      │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Tool Layer                                      │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌───────────────┐│
│  │ RepositoryTool │ │  EmbeddingTool │ │   ContextTool  │ │    LLMTool    ││
│  │ - clone        │ │ - embed        │ │ - search       │ │ - generate    ││
│  │ - analyze      │ │ - store        │ │ - rank         │ │ - analyze     ││
│  │ - discover     │ │ - search       │ │ - extract      │ │ - document    ││
│  └────────────────┘ └────────────────┘ └────────────────┘ └───────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    MCP Filesystem Tools                                  ││
│  │  - read_text_file       - read_multiple_files                           ││
│  │  - list_directory       - directory_tree                                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Repository Layer                                   │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │ RepositoryRepository│ │CodeDocumentRepository│ │WikiStructureRepository│  │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │ ChatSessionRepository│ │  QuestionRepository │ │   AnswerRepository  │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MongoDB Database                                   │
│  ┌─────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────┐   │
│  │ repositories│ │ code_documents│ │ wiki_structures│ │  wiki_memories  │   │
│  └─────────────┘ └───────────────┘ └───────────────┘ └─────────────────┘   │
│  ┌─────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────┐   │
│  │chat_sessions│ │   questions   │ │    answers    │ │      users      │   │
│  └─────────────┘ └───────────────┘ └───────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Patterns

### 1. Full Repository Analysis Workflow

```
┌─────────────────┐
│      START      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Validate     │  Check repository exists, URL valid
│   Repository    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Check Existing │  Skip if wiki already generated
│      Wiki       │  (unless force_regenerate)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Process      │  Clone repo, build tree, extract docs
│   Documents     │  Clean excluded files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Generate      │  Structure agent → Page agents (parallel)
│      Wiki       │  Aggregate → Store
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Finalize     │  Log metrics, return results
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      END        │
└─────────────────┘
```

### 2. Wiki Generation Fan-out/Fan-in Pattern

```
                    ┌─────────────────┐
                    │ Extract         │
                    │ Structure       │  React agent analyzes repo
                    └────────┬────────┘  → WikiStructure with N pages
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌───────────────┐┌───────────────┐┌───────────────┐
    │ Generate      ││ Generate      ││ Generate      │  Fresh agent per page
    │ Page 1        ││ Page 2        ││ Page N        │  Parallel execution
    └───────┬───────┘└───────┬───────┘└───────┬───────┘
            │                │                │
            └────────────────┼────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Aggregate     │  Merge pages via reducer
                    │   (Fan-in)      │  operator.add pattern
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Finalize      │  Save to MongoDB
                    └─────────────────┘
```

### 3. Chat/RAG Response Pattern

```
┌─────────────────┐
│  User Question  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Retrieve        │  Vector search + text search
│ Context         │  Rank by relevance/diversity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generate        │  RAG prompt with context
│ Response        │  Extract citations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Format &        │  Add citations, confidence
│ Return          │  Save Q&A pair
└─────────────────┘
```

---

## Agent Types and Responsibilities

### Document Processing Agent

**Purpose**: Prepare repository for analysis

**Inputs**:
- Repository URL
- Branch name
- Clone configuration

**Operations**:
1. Clone repository (shallow or full)
2. Build file tree structure
3. Extract documentation files (README, ARCHITECTURE.md, docs/**)
4. Load exclusion patterns (.autodoc/autodoc.json + hardcoded)
5. Physically delete excluded directories/files
6. Return clean clone path and metadata

**Outputs**:
- clone_path: Local filesystem path
- documentation_files: List of extracted doc files
- file_tree: Complete directory structure

---

### Wiki Structure Agent (React Pattern)

**Purpose**: Design wiki organization by exploring codebase

**Model**: Google Gemini 2.5 Pro (temperature=0)

**Tools Available**:
- `read_text_file`: Read single file with line range options
- `read_multiple_files`: Batch file reading

**Structured Output**: WikiStructure schema with sections and pages

**Strategy**:
1. Parse README for claims and purpose
2. Triage files using directory tree (no reads)
3. Identify key file candidates (max 25)
4. Targeted reading of high-signal files
5. Design wiki sections following learning path
6. Exit when coverage complete or diminishing returns

---

### Wiki Page Agent (React Pattern)

**Purpose**: Generate detailed documentation for single page

**Model**: Google Gemini 2.5 Pro (temperature=0)

**Tools Available**:
- `list_directory_with_sizes`: Explore directories
- `read_text_file`: Read file content
- `read_multiple_files`: Batch reading

**Structured Output**: WikiPageDetail with markdown content

**Content Requirements**:
- H3/H4/H5 structure
- Mermaid diagrams (flowchart TD only)
- Code snippets from repo
- Citations for every claim
- At least 5 distinct file citations

---

## State Management

### Workflow State Structure

```python
WorkflowState = TypedDict("WorkflowState", {
    "workflow_type": WorkflowType,
    "repository_id": str,
    "repository_url": str,
    "branch": str,
    "force_update": bool,
    "current_stage": str,
    "stages_completed": List[str],
    "error_message": Optional[str],
    "progress": int,  # 0-100
    "messages": List[BaseMessage],
    "results": Dict[str, Any]
})
```

### Wiki Workflow State with Reducer

```python
WikiWorkflowState = TypedDict("WikiWorkflowState", {
    "repository_id": str,
    "clone_path": str,
    "file_tree": str,
    "readme_content": str,
    "structure": Optional[WikiStructure],
    "pages": Annotated[List[WikiPageDetail], operator.add],  # Reducer!
    "error": Optional[str],
    "current_step": str,
    "force_regenerate": bool
})
```

### State Checkpointing

- Uses `MemorySaver()` for state persistence
- Thread-based isolation: `{workflow_type}_{repository_id}`
- Enables workflow recovery after failures
- Supports resumable long-running operations

---

## Middleware Stack

### API Layer Middleware

| Middleware | Purpose |
|------------|---------|
| RequestLoggingMiddleware | Correlation IDs, request/response logging |
| AuthMiddleware | JWT validation, user context injection |
| ErrorHandlerMiddleware | Structured error responses |
| CORSMiddleware | Cross-origin request handling |

### Agent Layer Middleware

| Middleware | Purpose |
|------------|---------|
| TodoListMiddleware | Task tracking during agent execution |
| SummarizationMiddleware | Condense long reasoning chains |
| PatchToolCallsMiddleware | Fix malformed tool calls |
| ModelRetryMiddleware | Retry LLM failures (3 attempts, exponential backoff) |
| ToolRetryMiddleware | Retry tool failures (3 attempts) |
| WikiMemoryMiddleware | Persistent memory across wiki regenerations |

---

## Tool Specifications

### RepositoryTool

**Operations**:
- `clone_repository(url, branch, clone_path, shallow)` → Clone git repo
- `analyze_repository(clone_path)` → Detect languages, frameworks
- `discover_files(clone_path, patterns, exclude)` → Find files by pattern
- `cleanup_repository(clone_path)` → Remove cloned files

**Features**:
- Windows-compatible git commands
- Configurable clone depth
- 25+ language detection
- Framework detection from package files

---

### EmbeddingTool

**Operations**:
- `generate_embeddings(text)` → Create vector embedding
- `store_embedding(document_id, embedding)` → Save to database
- `search_embeddings(query, limit)` → Vector similarity search
- `batch_process_documents(documents)` → Bulk embedding generation

**Providers**: OpenAI, Google Gemini, Ollama

**Configuration**:
- Dimensions: 128, 256, 384, 512, 768, 1024, 1536, 3072
- Value range: -1.0 to 1.0 (normalized)
- Batch size: Configurable

---

### ContextTool

**Operations**:
- `search_context(query, repository_id, limit)` → Hybrid search
- `rank_contexts(contexts, strategy)` → Relevance/diversity ranking
- `extract_code_snippets(contexts)` → Code structure extraction
- `hybrid_search(query, vector_weight, text_weight)` → Combined search

**Ranking Strategies**: relevance, recency, importance, diversity

---

### LLMTool

**Operations**:
- `generate_text(prompt, system_message)` → Text completion
- `generate_structured(prompt, schema)` → Pydantic-validated output
- `chat_completion(messages)` → Multi-turn conversation
- `stream_generation(prompt)` → Streaming response
- `analyze_code(code, analysis_type)` → Code analysis
- `generate_documentation(code, doc_type)` → Documentation generation
- `answer_question(question, context)` → RAG response

**Providers**: OpenAI, Google Gemini, Ollama

---

## Directory Structure

```
src/
├── api/                          # FastAPI Application
│   ├── main.py                   # Application entry point
│   ├── middleware/               # HTTP middleware
│   │   ├── auth.py              # JWT authentication
│   │   ├── logging.py           # Request logging
│   │   └── error_handler.py     # Error responses
│   └── routes/                   # API endpoints
│       ├── health.py            # Health checks
│       ├── repositories.py      # Repository CRUD
│       ├── chat.py              # Chat sessions & Q&A
│       ├── wiki.py              # Wiki retrieval
│       └── webhooks.py          # GitHub/Bitbucket webhooks
│
├── services/                     # Business Logic Layer
│   ├── repository_service.py    # Repository management
│   ├── document_service.py      # Document processing
│   ├── wiki_service.py          # Wiki generation
│   ├── chat_service.py          # Chat & RAG
│   └── auth_service.py          # Authentication
│
├── repository/                   # Data Access Layer
│   ├── base.py                  # BaseRepository generic
│   ├── database.py              # MongoDB connection
│   ├── repository_repository.py # Repository CRUD
│   ├── code_document_repository.py
│   ├── wiki_structure_repository.py
│   ├── chat_session_repository.py
│   ├── question_repository.py
│   └── answer_repository.py
│
├── agents/                       # AI Workflow Layer
│   ├── workflow.py              # Workflow orchestrator
│   ├── document_agent.py        # Document processing agent
│   ├── wiki_agent.py            # Wiki generation agent
│   ├── wiki_workflow.py         # Fan-out/fan-in workflow
│   ├── wiki_react_agents.py     # React agent factories
│   └── middleware/              # Agent middleware
│       └── wiki_memory_middleware.py
│
├── tools/                        # Agent Tools
│   ├── repository_tool.py       # Git operations
│   ├── embedding_tool.py        # Vector embeddings
│   ├── context_tool.py          # RAG context retrieval
│   └── llm_tool.py              # LLM interactions
│
├── models/                       # Data Models
│   ├── base.py                  # Base document class
│   ├── repository.py            # Repository model
│   ├── code_document.py         # Code document model
│   ├── wiki.py                  # Wiki structure model
│   ├── wiki_memory.py           # Wiki memory model
│   ├── chat.py                  # Chat models
│   └── user.py                  # User model
│
├── prompts/                      # LLM Prompts
│   └── wiki_prompts.yaml        # Wiki generation prompts
│
└── utils/                        # Utilities
    ├── config_loader.py         # Settings management
    ├── logging_config.py        # Structured logging
    ├── retry_utils.py           # Tenacity retry
    ├── storage_adapters.py      # Local/S3/MongoDB storage
    └── webhook_validator.py     # Webhook signatures
```

---

## Key Design Decisions

### 1. Fan-out/Fan-in for Page Generation

**Why**: Parallel page generation prevents sequential bottleneck
**Benefit**: N pages can be generated concurrently
**Implementation**: LangGraph Send API with operator.add reducer

### 2. Fresh Agent Context Per Page

**Why**: Prevents context pollution between pages
**Benefit**: Each page gets dedicated LLM context window
**Implementation**: New React agent instance per page worker

### 3. React Agents with MCP Tools

**Why**: Agents need intelligent filesystem exploration
**Benefit**: Dynamic file selection based on agent reasoning
**Implementation**: MCP filesystem tools wrapped for LangChain

### 4. Lazy Provider Initialization

**Why**: Reduce memory footprint
**Benefit**: Only initializes LLM/embedding providers when used
**Implementation**: Property-based lazy loading with caching

### 5. Structured Output Schemas

**Why**: Ensure LLM outputs match expected types
**Benefit**: Type-safe data extraction from LLM responses
**Implementation**: Pydantic schemas with LLM structured output

### 6. Wiki Memory System

**Why**: Maintain consistency across wiki regenerations
**Benefit**: Agents remember past decisions and patterns
**Implementation**: MongoDB collection with vector embeddings

### 7. Repository Pattern for Data Access

**Why**: Decouple business logic from database operations
**Benefit**: Testable services, swappable data stores
**Implementation**: Generic BaseRepository with domain-specific extensions

---

## Performance Characteristics

| Metric | Target |
|--------|--------|
| API Response (P50) | ≤ 500ms |
| API Response (P95) | ≤ 1500ms |
| Chat First Token | ≤ 1500ms |
| Webhook Processing | ≤ 3000ms |
| Concurrent Sessions | 100+ |
| Repository Analysis | 5-15 minutes |

---

## Security Considerations

- JWT authentication for API access
- API key authentication for service-to-service
- Webhook signature validation (HMAC-SHA256)
- Sensitive field exclusion in responses
- Input validation and sanitization
- Rate limiting (infrastructure level)

---

## External Integrations

### Git Providers
- GitHub (webhooks, API)
- Bitbucket (webhooks, API)
- GitLab (webhooks, API)

### LLM Providers
- OpenAI GPT (primary)
- Google Gemini (wiki generation)
- AWS Bedrock (enterprise)
- Ollama (local/development)

### Observability
- LangSmith (LLM tracing)
- Structured logging (JSON)
- Health check endpoints

---

## Configuration

### Environment Variables

```env
# Core
ENVIRONMENT=development|production
DEBUG=true|false
LOG_LEVEL=INFO|DEBUG|WARNING|ERROR

# API
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v2
CORS_ORIGINS=http://localhost:3000

# Database
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=autodoc_v2

# Authentication
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM Providers
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
OLLAMA_BASE_URL=http://localhost:11434

# MCP Filesystem
MCP_FILESYSTEM_ENABLED=true
MCP_FILESYSTEM_COMMAND=npx
MCP_FILESYSTEM_ARGS=-y,@anthropic/mcp-filesystem

# Observability
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=autodoc-v2
LANGSMITH_TRACING=true
```

---

*This document captures the complete architecture of AutoDoc v2 for reference during ADK-based reimplementation.*
