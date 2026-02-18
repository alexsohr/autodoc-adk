<!-- FOR AI AGENTS -->

# agents/ -- AI Documentation Agents

This package contains the three documentation agents for the autodoc-adk project. Each agent uses a Generator+Critic loop pattern where a Generator LlmAgent produces content and a separate Critic LlmAgent evaluates it against a weighted rubric. The Critic can use a different LLM model to avoid self-reinforcing bias.

## Agents

| Agent | Class | Output Type | Criterion Floors | Uses MCP Filesystem |
|-------|-------|-------------|------------------|---------------------|
| StructureExtractor | `structure_extractor/agent.py` | `WikiStructureSpec` | `coverage >= 5.0` | Yes |
| PageGenerator | `page_generator/agent.py` | `GeneratedPage` | `accuracy >= 5.0` | Yes |
| ReadmeDistiller | `readme_distiller/agent.py` | `ReadmeOutput` | None | No |

All agents subclass `BaseAgent[T]` (defined in `base.py`) and implement `async def run(input_data, session_service, session_id) -> AgentResult[T]`.

## File Layout

```
agents/
  __init__.py              -> Exports: AgentResult, BaseAgent, EvaluationResult, TokenUsage
  base.py                  -> BaseAgent[T] abstract class (ABC, Generic[T])
  common/
    __init__.py            -> Exports: AgentResult, EvaluationResult, QualityLoopConfig,
                              TokenUsage, build_style_section, create_filesystem_toolset,
                              run_quality_loop
    agent_result.py        -> TokenUsage dataclass, AgentResult[T] generic wrapper
    evaluation.py          -> EvaluationResult dataclass (score, passed, feedback,
                              criteria_scores, criteria_weights)
    loop.py                -> run_quality_loop() orchestration, QualityLoopConfig,
                              _extract_token_usage(), _check_below_floor()
    prompts.py             -> build_style_section() for audience/tone/detail injection
    mcp_tools.py           -> create_filesystem_toolset(repo_path) via npx MCP server
  structure_extractor/
    __init__.py            -> Exports: StructureExtractor, StructureExtractorInput,
                              WikiStructureSpec, SectionSpec, PageSpec
    agent.py               -> StructureExtractor(BaseAgent[WikiStructureSpec])
    schemas.py             -> PageSpec, SectionSpec, WikiStructureSpec, StructureExtractorInput
    prompts.py             -> Generator/Critic system prompts for structure extraction
  page_generator/
    __init__.py            -> Exports: PageGenerator, PageGeneratorInput, GeneratedPage
    agent.py               -> PageGenerator(BaseAgent[GeneratedPage]) -- GOLDEN SAMPLE
    schemas.py             -> GeneratedPage, PageGeneratorInput
    prompts.py             -> PAGE_GENERATOR_SYSTEM_PROMPT, PAGE_CRITIC_SYSTEM_PROMPT,
                              build_generator_system_prompt(), build_generator_message(),
                              build_critic_message()
  readme_distiller/
    __init__.py            -> Exports: ReadmeDistiller, ReadmeDistillerInput, ReadmeOutput
    agent.py               -> ReadmeDistiller(BaseAgent[ReadmeOutput])
    schemas.py             -> ReadmeOutput, ReadmeDistillerInput
    prompts.py             -> Generator/Critic system prompts for README distillation
```

## Golden Samples

Use `page_generator/` as the reference implementation when creating a new agent.

| To learn about | Read | Key patterns |
|----------------|------|--------------|
| Agent implementation | `page_generator/agent.py` | Subclass `BaseAgent[T]`, implement `async def run()`, create Generator+Critic `LlmAgent` instances, call `run_quality_loop()` |
| Input/output schemas | `page_generator/schemas.py` | Input dataclass with all fields (including style_*), output dataclass |
| Prompt construction | `page_generator/prompts.py` | `build_generator_system_prompt()`, `build_generator_message()`, `build_critic_message()`; critic prompt defines JSON output format with criteria weights |
| Quality loop internals | `common/loop.py` | `run_quality_loop()` with `QualityLoopConfig`, per-attempt sessions, critic failure resilience |

## Core Pattern: Generator+Critic Loop

The loop in `common/loop.py` (`run_quality_loop()`) works as follows:

1. Generator produces output from `initial_message` (attempt 1) or `initial_message + feedback` (subsequent attempts).
2. Generator output is parsed via `parse_output` callback into type `T`.
3. Critic evaluates the raw generator text and returns JSON with `score`, `criteria_scores`, `feedback`.
4. Critic output is parsed via `parse_evaluation` callback into `EvaluationResult`.
5. Quality gate checks: `score >= quality_threshold` AND no per-criterion floor violations.
6. If gate passes, return immediately. Otherwise, feed `evaluation.feedback` back to Generator and retry.
7. After `max_attempts`, return the best-scoring attempt regardless.

Each attempt uses a unique ADK session ID (`{session_id}-gen-{attempt}-{uuid}`) so conversation history does not leak between attempts.

If the Critic LLM fails (exception during run or parse), the attempt auto-passes with `score = quality_threshold` and a warning is logged. The pipeline never crashes due to Critic failure.

## Key Types

**BaseAgent[T]** (`base.py`):
- Abstract class with single method: `async def run(input_data: Any, session_service: Any, session_id: str) -> AgentResult[T]`

**AgentResult[T]** (`common/agent_result.py`):
- `output: T` -- the best parsed output
- `attempts: int` -- how many attempts were made
- `final_score: float` -- best score achieved
- `passed_quality_gate: bool` -- whether quality threshold was met without floor violations
- `below_minimum_floor: bool` -- whether any criterion fell below its floor
- `evaluation_history: list[EvaluationResult]` -- all evaluations across attempts
- `token_usage: TokenUsage` -- accumulated input/output/total tokens and call count

**EvaluationResult** (`common/evaluation.py`):
- `score: float` -- weighted average, 1.0-10.0
- `passed: bool` -- score >= threshold
- `feedback: str` -- improvement suggestions from Critic
- `criteria_scores: dict[str, float]` -- per-criterion scores (e.g., `{"accuracy": 8.0}`)
- `criteria_weights: dict[str, float]` -- per-criterion weights (e.g., `{"accuracy": 0.35}`)

**QualityLoopConfig** (`common/loop.py`):
- `quality_threshold: float` -- overall score threshold (default 7.0 from settings)
- `max_attempts: int` -- max Generator+Critic cycles (default 3 from settings)
- `criterion_floors: dict[str, float]` -- per-criterion minimum scores

## Configuration

Agent models and quality settings come from `src/config/settings.py`:

- `QUALITY_THRESHOLD` (float, default 7.0) -- overall quality gate
- `MAX_AGENT_ATTEMPTS` (int, default 3) -- max loop iterations
- `STRUCTURE_COVERAGE_CRITERION_FLOOR` (float, default 5.0) -- minimum coverage score for StructureExtractor
- `PAGE_ACCURACY_CRITERION_FLOOR` (float, default 5.0) -- minimum accuracy score for PageGenerator

Per-agent model selection uses `settings.get_agent_model(agent_name)` which reads env vars like `PAGE_GENERATOR_MODEL`, `PAGE_CRITIC_MODEL`, `STRUCTURE_GENERATOR_MODEL`, etc. Models are instantiated via `get_model()` in `src/config/models.py`, which routes `gemini-*` strings natively and other provider-prefixed strings (`vertex_ai/`, `azure/`, `bedrock/`) through ADK's LiteLLM wrapper.

## Code Conventions

- All agents are async (`async def run()`).
- Schemas use `dataclasses` (not Pydantic) -- these are internal types.
- Prompts live in separate `prompts.py` files, built via function calls. Never inline prompts in `agent.py`.
- Output parsing functions (`_parse_structure_output`, `_parse_page_output`, `_parse_evaluation`) are module-level functions, not class methods.
- Critic receives source file contents directly in its system prompt (via `_format_source_context()` or `build_critic_message()`) to verify code reference accuracy. The Critic does NOT get MCP filesystem tools.
- Generator gets MCP filesystem tools (StructureExtractor and PageGenerator) or works from input data alone (ReadmeDistiller).
- `build_style_section()` injects `audience`, `tone`, `detail_level`, and `custom_instructions` into Generator system prompts.
- Token usage is tracked per agent via `_extract_token_usage()` in the quality loop and accumulated in `AgentResult.token_usage`.

## Heuristics

| When | Do |
|------|----|
| Adding a new agent | Copy `page_generator/` directory structure; subclass `BaseAgent[T]`; implement `run()`; create `schemas.py`, `prompts.py`, `__init__.py` |
| Modifying prompts | Edit the relevant `prompts.py` file; never inline prompts in `agent.py` |
| Changing evaluation criteria | Update the Critic system prompt in `prompts.py` and adjust `criterion_floors` in `settings.py` |
| Debugging quality loop | Inspect `evaluation_history` in the returned `AgentResult` for score progression across attempts |
| Agent returns wrong format | Fix the `_parse_*_output()` function in `agent.py` |
| Need different model per agent | Set env var (e.g., `PAGE_CRITIC_MODEL=azure/gpt-4o`) -- see `src/config/settings.py` |
| Agent needs source file access | Use `create_filesystem_toolset(repo_path)` and pass toolset to Generator's `tools` list; close `exit_stack` in `finally` block |

## Boundaries

**Always:**
- Return `AgentResult[T]` from `run()`.
- Use `run_quality_loop()` for Generator+Critic orchestration.
- Keep prompts in `prompts.py`, schemas in `schemas.py`.
- Include source context in Critic input for accuracy verification.
- Track token usage via the quality loop's built-in accumulation.
- Use `get_model()` from `src/config/models.py` to instantiate LLM models.
- Close MCP `exit_stack` in a `finally` block when using filesystem tools.

**Ask first:**
- Changing quality thresholds or criterion floors.
- Adding new evaluation criteria to a Critic.
- Changing the Generator+Critic loop structure in `common/loop.py`.
- Adding a new agent type beyond the existing three.

**Never:**
- Inline prompts in agent code.
- Skip the Critic evaluation step.
- Use synchronous operations in agent code.
- Instantiate LLM models directly (always use `get_model()`).
- Give MCP filesystem tools to the Critic (it receives source content in its prompt instead).
- Let Critic failures crash the pipeline (auto-pass with warning).
