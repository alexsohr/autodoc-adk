<!-- FOR AI AGENTS -->

# src/services

Business logic services used by Prefect flows and the FastAPI layer. Four modules handling .autodoc.yaml config loading/validation, embedding generation via LiteLLM, two-stage markdown chunking, and document search orchestration (text/semantic/hybrid with RRF).

## Files

| File | Purpose |
|------|---------|
| `config_loader.py` | Load/validate `.autodoc.yaml` files, auto-exclude overlapping scopes |
| `embedding.py` | Batch embedding generation and single-query embedding via LiteLLM |
| `chunking.py` | Two-stage markdown chunking: heading-aware split then recursive fallback |
| `search.py` | Search orchestrator: delegates to `SearchRepo`, maps results to API schemas |

## config_loader.py

Loads `.autodoc.yaml` files into validated dataclasses. Unknown keys warn (logged), invalid values raise `PermanentError`.

### Dataclasses

- `StyleConfig`: `audience` ("developer"), `tone` ("technical"), `detail_level` ("minimal" | "standard" | "comprehensive")
- `ReadmeConfig`: `output_path` ("README.md"), `max_length` (None = unlimited, int = word cap), `include_toc` (True), `include_badges` (False)
- `PullRequestConfig`: `auto_merge` (False), `reviewers` (list[str])
- `AutodocConfig`: `scope_path`, `version`, `include`, `exclude`, `style`, `custom_instructions`, `readme`, `pull_request`

### Key functions

`load_autodoc_config(config_path, scope_path=".")` -- loads and validates a single `.autodoc.yaml`. Returns `AutodocConfig` with defaults when file is missing or empty. Raises `PermanentError` on invalid YAML or invalid field values.

`apply_scope_overlap_exclusions(configs)` -- given all discovered configs in a repo, mutates each parent's `exclude` list to include child scope directories. Root scope (`"."`) is parent of everything. Returns the same list (mutated in place).

### Include/exclude semantics

- `include` empty = all files included
- `include` non-empty = ONLY those paths (minus `exclude`)
- `readme.output_path` is relative to the config file's directory
- `custom_instructions` is free-form text injected into agent prompts (replaces the glossary concept)

```python
from src.services.config_loader import load_autodoc_config, apply_scope_overlap_exclusions

config = load_autodoc_config("/path/to/.autodoc.yaml", scope_path="services/auth")
# config.style.detail_level -> "standard"

all_configs = [root_config, child_config]
apply_scope_overlap_exclusions(all_configs)
# root_config.exclude now contains "services/auth"
```

## embedding.py

Async embedding service using `litellm.aembedding()`. Model and dimensions from `Settings` (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE`).

### Key functions

`generate_embeddings(texts, *, model=None, dimensions=None, batch_size=None)` -- batch-embeds text chunks. Processes in batches of `batch_size` (default from `EMBEDDING_BATCH_SIZE` setting). Returns `list[list[float]]` preserving input order. Raises `TransientError` on API failure.

`embed_query(query, *, model=None, dimensions=None)` -- convenience wrapper for single text. Calls `generate_embeddings` with `batch_size=1`. Returns a single `list[float]`.

```python
from src.services.embedding import generate_embeddings, embed_query

vectors = await generate_embeddings(["chunk 1", "chunk 2"])  # batch
query_vec = await embed_query("search query")                # single
```

## chunking.py

Two-stage markdown chunking. Uses `tiktoken` with `cl100k_base` encoding for token counting.

### ChunkResult dataclass

`content`, `heading_path` (list[str]), `heading_level` (int), `token_count` (int), `start_char` (int), `end_char` (int), `has_code` (bool)

### Pipeline

1. **Stage 1** -- `_split_by_headings(content)`: Splits on ATX headings (`# ` through `###### `). Skips headings inside fenced code blocks. Returns `_Section` objects with `heading_path` tracking (nested heading stack).
2. **Stage 2** -- for sections exceeding `max_tokens`:
   - `_recursive_split(text, max_tokens)`: Tries separators in order: `"\n\n"`, `"\n"`, `". "`, `" "`. Greedily merges parts until limit exceeded, recurses with next separator for oversized chunks.
   - `_apply_overlap(fragments, overlap_tokens)`: Prepends trailing tokens from previous fragment to each subsequent one (token-level overlap decoded back to text).
   - `_merge_small_chunks(fragments, min_tokens)`: Merges undersized fragments with nearest neighbour.

### Key functions

`chunk_markdown(content, *, max_tokens=512, overlap_tokens=50, min_tokens=50)` -- full pipeline. Returns `list[ChunkResult]` ordered by position in original content.

`chunk_markdown_from_settings(content)` -- convenience wrapper reading `CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `CHUNK_MIN_TOKENS` from `get_settings()`.

```python
from src.services.chunking import chunk_markdown_from_settings

chunks = chunk_markdown_from_settings(markdown_content)
for chunk in chunks:
    print(chunk.heading_path, chunk.token_count, chunk.has_code)
```

## search.py

Search orchestrator. Validates search type, generates query embeddings when needed, delegates to `SearchRepo` methods, maps repo-layer result types to API `SearchResult` schema with extracted snippets.

### Key function

`search_documents(*, query, search_type, repository_id, branch, scope=None, limit=10, search_repo)` -- main entry point.

- `search_type="text"` -- calls `search_repo.text_search()`, maps via `_map_text_result()`
- `search_type="semantic"` -- calls `embed_query()` then `search_repo.semantic_search()`, maps via `_map_semantic_result()` (includes `best_chunk_content`, `best_chunk_heading_path`)
- `search_type="hybrid"` -- calls `embed_query()` then `search_repo.hybrid_search()` (RRF with k=60), maps via `_map_hybrid_result()`

Returns `SearchResponse(results, total, search_type)`. Raises `PermanentError` for invalid `search_type`.

### Internal helpers

- `_extract_snippet(content, max_length=200)` -- strips leading heading markers, truncates at word boundary with `"..."` suffix
- `_map_text_result`, `_map_semantic_result`, `_map_hybrid_result` -- convert repo-layer typed results to API `SearchResult`

### Dependencies

- `src.api.schemas.documents.SearchResponse`, `SearchResult` -- API response types
- `src.database.repos.search_repo.SearchRepo` -- data access (injected as parameter)
- `src.services.embedding.embed_query` -- query embedding for semantic/hybrid

## Heuristics

| When | Do |
|------|----|
| Need `.autodoc.yaml` config | Call `load_autodoc_config(path)` -- handles validation and warnings |
| Need embeddings for text | Call `generate_embeddings(texts)` for batch, `embed_query(query)` for single |
| Need to chunk markdown | Call `chunk_markdown_from_settings(content)` for default params |
| Adding a new search type | Add method to `SearchRepo`, add result type, add mapping function and branch in `search_documents()` |
| Changing chunk parameters | Modify `Settings` env vars (`CHUNK_MAX_TOKENS`, etc.), not code defaults |
| Changing embedding model | Update `EMBEDDING_MODEL` env var -- this is a breaking change requiring full re-generation of all embeddings |
| Adding new `.autodoc.yaml` fields | Add to the appropriate dataclass, known-keys set, and parsing function in `config_loader.py` |

## Boundaries

**Always:**
- Use `load_autodoc_config()` for `.autodoc.yaml` parsing -- never parse YAML directly elsewhere
- Use `chunk_markdown_from_settings()` for default chunking parameters
- Use `generate_embeddings()` for batch operations (not `embed_query` in a loop)
- Pass `search_repo` as a parameter to `search_documents()` (dependency injection, not internal construction)

**Ask first:**
- Changing chunking algorithm or parameters (affects all existing chunks)
- Changing embedding model or dimensions (breaking change, full re-generation required)
- Adding new config sections to `.autodoc.yaml` (needs plan-level alignment)
- Modifying search ranking or RRF parameters (k=60, penalty rank=1000)
- Changing the recursive split separator order in `chunking.py`

**Never:**
- Parse `.autodoc.yaml` manually outside `config_loader.py`
- Call embedding API without batching (use `generate_embeddings`, not raw `litellm.aembedding` in a loop)
- Change chunk size defaults without considering existing embeddings in the database
- Import `SearchRepo` result types in service consumers -- use `SearchResult` from API schemas instead
- Modify `_extract_snippet` to return markdown (it intentionally strips heading markers for plain-text output)
