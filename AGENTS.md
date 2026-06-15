# AGENTS.md — NarraBridge

> **Read this first.** This file describes what has been BUILT and what remains.
> See `PLAN.md` for the original design rationale.

---

## 0. Current Status

| Phase | Status | What exists |
|:-----:|:------:|-------------|
| ① Manual validation | ✅ Done | `validate_phase1.py` + `outputs/phase1_trust_eval.md` |
| ② Agent pipeline | ✅ Done | `__init__.py` (460 lines, 3 pipelines) |
| ③ Terminology dictionary | ✅ Done | `knowledge/terminology.yml` (extracted from 477 papers) |
| ④ Web UI | ✅ Done | `ui/app.py` (Gradio, 3 tabs) |
| ⑤ Refinement | 🔴 Current | Polish, bug fixes, edge cases |

---

## 1. Architecture (what was built)

The assistant chose a **pragmatic hybrid architecture**:

### Pipeline driver: Plain Python + LangChain

The main pipeline (`__init__.py`) does NOT use deepagents' agent loop. Instead:

1. **Python handles all I/O** — OpenSearch queries, file reads, JSON parsing
2. **LLM handles reasoning** — via `run_structured_agent()` using `ChatOpenAI.with_structured_output()`
3. **Data flows between steps as Python dicts**

```
translate_pipeline(project_path)
  │
  ├─[Step 1] extract_tech_profile()           ← Python (tools/project_reader.py)
  │   └─ writes outputs/trust-eval/tech_profile.json
  │
  ├─[Step 2] text_search() × 5 queries        ← Python (tools/opensearch_search.py)
  │   └─ run_structured_agent("problem_mapper") ← LLM
  │   └─ writes problem_mapping.json
  │
  ├─[Step 3] get_paper_sections() × 10        ← Python (tools/paper_reader.py)
  │   └─ run_structured_agent("narrative_extractor") ← LLM
  │   └─ writes narrative_patterns.json
  │
  ├─[Step 4] run_structured_agent("paper_generator") ← LLM
  │   └─ writes paper_draft.md
  │
  └─[Step 5] run_structured_agent("peer_reviewer") ← LLM
      └─ writes review_report.md
```

### Agent definitions: deepagents wrappers

Files in `agents/` wrap each agent with `create_deep_agent()`, but the main pipeline calls `run_structured_agent()` directly — NOT the deepagents agent loop.

### Terminology dictionary

`knowledge/terminology.yml` was already extracted from 477 papers. It's injected into prompts and used for terminology auditing.

---

## 2. Key Implementation Details

### `run_structured_agent()` — the core LLM call pattern

```python
# __init__.py, line 29-95
def run_structured_agent(prompt_name: str, schema_key: str, input_data: dict) -> dict:
    # 1. Load system prompt from prompts/{prompt_name}.md
    # 2. Inject terminology dictionary (up to 200 terms)
    # 3. Load JSON schema from schemas/agent_io.json
    # 4. Create ChatOpenAI with with_structured_output(method="json_mode")
    # 5. Invoke with schema hint appended to system prompt
    # 6. Return structured dict
```

**Why `json_mode` instead of `function_calling`?**
The assistant found `json_mode` more stable with your local vLLM (port 1878).

### Model configuration

```python
# config.py
LLM_BASE_URL = "http://127.0.0.1:1878/v1"
LLM_MODEL = "qwen-27b-reasoning"
LLM_API_KEY = "sk-ym-...2025"
```

LiteLLM gateway at 1878 proxies to the vLLM server on Sichuan. The assistant switched to 1878 (from 8000 direct) because `with_structured_output` had hanging issues on the raw vLLM port.

### OpenSearch queries

```python
# tools/opensearch_search.py — queries against field "content"
def text_search(query: str, top_k: int = 5) -> list[dict]:
    client.search(index="情报学报", body={
        "query": {"match": {"content": query}},
        "size": top_k,
    })
```

**Critical fix made by assistant:** The original skeleton used `text` field but the actual OpenSearch index uses `content`.

### Terminology injection

```python
# __init__.py, line 37-49
term_dict_path = Path(__file__).parent / "knowledge" / "terminology.yml"
if term_dict_path.exists():
    terms = yaml.safe_load(f)
    # Inject first 200 terms into system prompt
```

---

## 3. Remaining Work (Phase ⑤ Refinement)

### 3.1 Known issues to fix

| Issue | Priority | Where |
|-------|:--------:|-------|
| `paper_reader.py` can't find some minerU files (ID mismatch) | 🔴 High | `tools/paper_reader.py` |
| Agent 5 returns `None` for some fields when input is minimal | 🟡 Medium | `__init__.py:review_pipeline()` |
| OpenSearch queries return 0 results for some terms | 🟡 Medium | `_construct_queries_from_profile()` |
| Terminology dictionary could use more entries | 🟢 Low | `knowledge/terminology.yml` |
| Context trimming logic (50 terms) might lose important terms | 🟢 Low | `_trim_narrative_template()` |

### 3.2 Suggested improvements

1. **Better paper reader** — Use regex to map paper titles → minerU filenames instead of relying on `paper_id` field
2. **Query diversity** — `_construct_queries_from_profile()` currently uses hardcoded queries. Make them dynamically generated from the tech profile.
3. **Error recovery** — If an agent step fails, save partial results and continue (currently pipeline stops)
4. **Parallel agents** — Agents 1 and pre-search can run in parallel (currently sequential)
5. **Output comparison** — After pipeline runs, compare outputs across sessions to track quality

### 3.3 Testing checklist

- [ ] Run `python -m narrabridge translate ~/trust-eval` — confirm all 5 steps complete
- [ ] Run `python -m narrabridge entry "RAG, multi-agent, NLI"` — confirm meaningful results
- [ ] Run `python -m narrabridge review outputs/trust-eval/paper_draft.md` — confirm review generated
- [ ] Run `python tests/test_opensearch_search.py` — confirm all pass
- [ ] Run `python tests/test_project_reader.py` — confirm all pass
- [ ] Test with a second project (not trust-eval) to verify generality

---

## 4. How to continue development

### For a new AI coding assistant

```bash
# 1. Understand the architecture
cat AGENTS.md                           # This file
cat PLAN.md                             # Original design
cat __init__.py | head -100             # Core pipeline
cat config.py                           # Configuration
cat knowledge/terminology.yml | head -50  # Terminology dictionary

# 2. Verify it still works
python -m narrabridge translate ~/trust-eval

# 3. Run tests
python -m pytest tests/ -v

# 4. Pick a task from §3.1 or §3.2

# 5. Commit with Chinese message
git add -A && git commit -m "fix: 描述你的修改"
```

### Key constraints

- **DO NOT rewrite the pipeline architecture.** It works. Fix bugs, don't redesign.
- **DO NOT change the LLM endpoint** (127.0.0.1:1878/v1). It was chosen for stability.
- **DO NOT modify `schemas/agent_io.json`** without updating all agents that depend on it.
- **All paths must be absolute** — the pipeline runs from any directory.
- **Outputs go to `outputs/{project_name}/`** — never to `qingbao_search/`.

---

## 5. Data Flow Diagram

```
User runs: python -m narrabridge translate ~/trust-eval
                  │
                  ▼
         __main__.py → translate_pipeline()
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
Python I/O    LLM calls     File writes
    │             │             │
    ├─extract_   ├─run_struct-  ├─tech_profile.json
    │ tech_prof  │ ured_agent() ├─problem_mapping.json
    │             │             ├─narrative_patterns.json
    ├─text_      │             ├─paper_draft.md
    │ search()   │             └─review_report.md
    │             │
    ├─get_paper_ │
    │ sections() │
    │             │
    └─yaml.safe_ │
      load()     │
                 │
         ┌───────┴───────┐
         │               │
    ChatOpenAI    prompts/*.md
    (127.0.0.1:   schemas/agent_io.json
     1878/v1)     knowledge/terminology.yml
         │
         ▼
    vLLM Qwen-27B (Sichuan server)
```

**No external APIs. Everything local.**

---

## 6. Quick Reference

| What | Where |
|------|-------|
| Main pipeline | `__init__.py:translate_pipeline()` |
| Entry discovery | `__init__.py:entry_pipeline()` |
| Peer review | `__init__.py:review_pipeline()` |
| LLM call pattern | `__init__.py:run_structured_agent()` |
| Model config | `config.py` |
| OpenSearch search | `tools/opensearch_search.py:text_search()` |
| Tech profile extractor | `tools/project_reader.py:extract_tech_profile()` |
| Paper section reader | `tools/paper_reader.py:get_paper_sections()` |
| Agent definitions | `agents/*.py` |
| Prompts | `prompts/*.md` |
| I/O schemas | `schemas/agent_io.json` |
| Terminology | `knowledge/terminology.yml` |
| Tests | `tests/` |
| Outputs | `outputs/{project_name}/` |
