# AGENTS.md — NarraBridge

> **Read this first.** This file contains everything a coding agent needs to start
> implementing NarraBridge. No external planning required.

---

## 0. What is NarraBridge?

A narrative translation engine that helps NLP/LLM practitioners write intelligence
studies papers by **re-framing engineering artifacts as answers to discipline‑specific
research questions**. Grounded in a domain knowledge base of 477 full‑text papers
from *情报学报* (indexed in OpenSearch).

**NOT a method improvement tool. NOT a generic writing assistant.** It translates
engineering language into intelligence studies academic language, using real published
papers as the translation reference.

---

## 1. Development Environment

### 1.1 Python & Dependencies

```bash
# Already installed in the system Python
pip3 install deepagents langchain-core opensearch-py gradio pyyaml 2>&1 | tail -3
```

### 1.2 Required Environment Variables

Already set in `~/.bashrc` / `~/.hermes/.env`. Verify before coding:

```bash
# OpenSearch
OPENSEARCH_URL=http://127.0.0.1:9202
QINGBAO_INDEX=情报学报

# LLM (Sichuan server via LiteLLM gateway)
LLM_BASE_URL=http://127.0.0.1:1878/v1
LLM_MODEL=qwen-27b-reasoning
LLM_API_KEY=not-needed
```

### 1.3 External Services

| Service | Address | Status |
|---------|---------|:------:|
| OpenSearch 情报学报 | `127.0.0.1:9202` | ✅ Running |
| LiteLLM gateway | `127.0.0.1:1878` | ✅ Running |
| vLLM (Qwen3.6-35B-A3B) | behind LiteLLM | ✅ Running |

Verify: `curl -s --noproxy '*' 'http://127.0.0.1:9202/' 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin)['version']['number'])"`

---

## 2. Project Structure

```
narrabridge/
├── AGENTS.md                ← ← ← YOU ARE HERE
├── PLAN.md                  # Architecture reference (read for context)
├── README.md                # Public-facing
├── requirements.txt         # Python dependencies
│
├── narrabridge/
│   └── orchestrator.py      ★ 5-agent pipeline with deepagents (Phase 2)
│
├── prompts/                 ★ System prompts for 5 agents (drafts exist, improve them)
│   ├── project_reader.md
│   ├── problem_mapper.md
│   ├── narrative_extractor.md
│   ├── paper_generator.md
│   └── peer_reviewer.md
│
├── tools/                   ★ Custom tools for deepagents
│   ├── opensearch_search.py # OpenSearch hybrid query (skeleton → full implementation)
│   └── project_reader.py    # Codebase → tech profile extractor (skeleton → full)
│
├── schemas/
│   └── agent_io.json        # Input/output schemas for all 5 agents
│
├── validate_phase1.py       # Phase 1 manual validation script
│
├── knowledge/               # Structured domain knowledge (Phase 3)
├── ui/                      # Gradio web app (Phase 4)
├── outputs/                 # Agent-generated artifacts
└── tests/                   # Unit tests
```

---

## 3. Implementation Phases (EXECUTABLE ORDER)

### Phase 1 — Manual Validation 🔴 CURRENT

**Goal:** Prove core pipeline works before writing agent code.

**Deliverable:** `validate_phase1.py` runs and produces a file `outputs/phase1_trust_eval.md`
that the user agrees is "directionally correct."

**Steps (execute in order):**

1. Read `~/trust-eval/AGENTS.md` + `~/trust-eval/docs/TRUST-EVAL-研究方案-v3.md`
   → extract a technical profile (what does the system do in engineering terms?)

2. Construct 3-5 problem-semantic OpenSearch queries (NOT keyword-match!):
   - "情报分析 可信度 评估 AI 生成 质量"
   - "多智能体 情报 分析 验证"
   - "人工智能 情报 质量控制 审计"
   - Translate: "post-hoc verification" → "后验检验 质量评估"

3. For each query, retrieve top-5 papers from OpenSearch

4. For each paper, read the minerU output (`~/qingbao_search/mineru_output/{paper_id}.md`)
   and extract: problem statement, method description, terminology used

5. Feed all results + trust-eval tech profile to the LLM, ask:
   - "trust-eval solves what intelligence studies problem?"
   - "Which 3-5 papers are closest in problem framing?"
   - "Write an introduction paragraph in 情报学报 style for trust-eval"
   - "Create a terminology mapping: NLP terms → 情报学报 terms"

6. Save output to `outputs/phase1_trust_eval.md`

7. **STOP.** Show output to user. Do NOT proceed to Phase 2 until user confirms quality.

**Key `validate_phase1.py` functions to implement:**
```python
def extract_tech_profile(project_path: str) -> dict
def construct_queries(tech_profile: dict) -> list[str]
def search_qingbao(query: str, top_k: int = 5) -> list[dict]
def read_paper(paper_id: str) -> str  # from mineru_output/
def llm_analyze(tech_profile, papers, questions) -> str
```

### Phase 2 — Agent Pipeline ⬜

**Precondition:** Phase 1 validated by user.

**Deliverable:** `python -m narrabridge translate ~/trust-eval` produces a complete paper draft.

**Tasks:**

**2.1 — Implement `tools/opensearch_search.py`**
- Full OpenSearch client with hybrid search (BM25 + k-NN)
- Error handling, timeout, retry
- Tests in `tests/test_opensearch_search.py`

**2.2 — Implement `tools/project_reader.py`**
- Parse AGENTS.md, README.md, config/*.py, core/*.py
- Extract structured tech profile per schemas/agent_io.json
- Tests in `tests/test_project_reader.py`

**2.3 — Agent 1: Project Reader**
- Load prompt from `prompts/project_reader.md`
- Use `create_deep_agent` + `project_reader.py` tool
- Test on trust-eval

**2.4 — Agent 2: Problem Mapper**
- Load prompt from `prompts/problem_mapper.md`
- Uses `opensearch_search.py` tool
- Receives Agent 1 output as input
- Test on trust-eval

**2.5 — Agent 3: Narrative Extractor**
- Load prompt from `prompts/narrative_extractor.md`
- Uses `opensearch_search.py` to fetch full paper sections
- Receives Agent 2 output as input

**2.6 — Agent 4: Paper Generator**
- Load prompt from `prompts/paper_generator.md`
- Receives Agents 1+2+3 outputs as input
- Generates: intro draft, related work, methods, experiment checklist

**2.7 — Agent 5: Peer Reviewer**
- Load prompt from `prompts/peer_reviewer.md`
- Receives Agent 4 output as input
- Generates review report

**2.8 — Orchestrator**
- Wire agents with deepagents sub-agent spawning
- CLI entry point: `narrabridge/__init__.py`
- See `narrabridge/orchestrator.py` for the reference implementation

---

## 3.5. deepagents Architecture Usage

The entire agent pipeline is built on deepagents. Here's how each feature is used:

| deepagents feature | How we use it | Where |
|-------------------|---------------|-------|
| `create_deep_agent()` | Create each of the 5 agents with custom tools + system prompt | `orchestrator.py:_create_agent()` |
| `model` (pre-initialized `ChatOpenAI`) | Points to our LOCAL vLLM at `127.0.0.1:1878/v1`, NOT OpenAI's API | `orchestrator.py:_get_model()` |
| `FilesystemBackend(virtual_mode=True)` | Each agent gets a sandboxed workspace under `outputs/{project}/{session}/{agent}/` | `orchestrator.py:_create_agent()` |
| `system_prompt` | Loaded from `prompts/*.md` — defines agent personality and instructions | `orchestrator.py:_load_prompt()` |
| `tools` parameter | Custom Python functions (`search_qingbao`, `read_paper_section`) — these query LOCAL OpenSearch at `127.0.0.1:9202` | `orchestrator.py` (function definitions) |
| Built-in filesystem tools | Agents use `write_file` to persist outputs autonomously | deepagents default (no config) |
| Context compression | Middleware auto-summarizes when 5+ papers fill context | deepagents default (no config) |

**Agent creation pattern (every agent follows this):**

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_openai import ChatOpenAI

# Pre-initialized model → points to our LOCAL vLLM (127.0.0.1:1878)
# NOT OpenAI's API. deepagents accepts pre-initialized BaseChatModel instances.
model = ChatOpenAI(
    model="qwen-27b-reasoning",
    base_url="http://127.0.0.1:1878/v1",
    api_key="not-needed",
    temperature=0.3,
    max_tokens=4096,
)

# Custom tools → query our LOCAL OpenSearch (127.0.0.1:9202)
# These functions run on the host machine, not in the LLM.
def search_qingbao(query: str, top_k: int = 5) -> str:
    """Search LOCAL 情报学报 index. Returns paper titles + snippets."""
    ...

agent = create_deep_agent(
    model=model,                            # ← Pre-initialized, points to local vLLM
    tools=[search_qingbao, read_paper_section],  # ← Local OpenSearch queries
    system_prompt=open("prompts/project_reader.md").read(),
    backend=FilesystemBackend(
        root_dir="outputs/session_001/agent1/",
        virtual_mode=True,  # Sandboxed — agent can't escape this directory
    ),
    name="problem_mapper",
)

# deepagents uses LangGraph's invoke() — standard AI agent loop
result = agent.invoke({
    "messages": [{"role": "user", "content": "Map this project to intelligence studies"}]
})

# Agent's response is in the last message
response = result["messages"][-1].content
```

**Data flow — how your local OpenSearch feeds the agent:**

```
Agent calls: search_qingbao("情报分析 可信度 评估")
     ↓
Python runs: opensearchpy → curl 127.0.0.1:9202/情报学报/_search
     ↓
Returns: top-5 papers from YOUR local 情报学报 index
     ↓
Agent reads: paper titles, snippets, scores
     ↓
Agent decides: "These papers discuss AI content quality control — this project fits"
```

**No external API calls. No web search. Everything stays local.**

This pattern is implemented once in `_create_agent()` and reused for all 5 agents.

### Phase 3 — Terminology Dictionary ⬜

**Deliverable:** `knowledge/terminology.yml` (300+ entries)

Extract from 477 minerU outputs:
- High-frequency academic terms
- NLP ↔ 情报学 term mappings
- Common experiment patterns

### Phase 4 — Web UI ⬜

Gradio app in `ui/app.py` with three tabs matching the three scenarios.
See `PLAN.md` §3 for scenario requirements.

### Phase 5 — Refinement ⬜

Iterate on trust-eval case study, tune prompts, test on 2-3 more projects.

---

## 4. Data Contracts

See `schemas/agent_io.json` for full JSON schemas. Key types:

```python
# Agent 1 → 2
TechProfile = {
    "tech_stack": list[str],
    "core_innovation": str,
    "experimental_setup": {"dataset": str, "size": int, "topic": str},
    "modules": [{"name": str, "purpose": str}],
}

# Agent 2 → 3
ProblemMapping = {
    "problem_type": str,  # from literature_analysis.md taxonomy
    "confidence": float,
    "top_papers": [{"id": str, "title": str, "relevance_reason": str, "excerpt": str}],
    "query_translations": [{"nlp_term": str, "qingbao_term": str}],
}

# Agent 3 → 4
NarrativeTemplate = {
    "intro_structure": [{"stage": str, "example_from_paper": str, "paper_id": str}],
    "method_description_conventions": list[str],
    "terminology_mapping": [{"your_word": str, "journal_word": str, "frequency": int}],
    "experiment_checklist": [{"type": str, "required": bool, "example_paper_id": str}],
}

# Agent 4 output
PaperDraft = {
    "title_suggestions": list[str],
    "introduction": str,
    "related_work": str,
    "methods": str,
    "suggested_experiments": [{"name": str, "rationale": str, "paper_reference": str}],
}

# Agent 5 output
ReviewReport = {
    "terminology_issues": [{"your_word": str, "suggested": str, "paper_evidence": str}],
    "structure_issues": [{"section": str, "issue": str, "peer_paper_comparison": str}],
    "citation_gaps": [{"should_cite": str, "reason": str}],
    "contribution_framing_issues": list[str],
}
```

---

## 5. OpenSearch Quick Reference

```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "127.0.0.1", "port": 9202}],
    use_ssl=False,
    verify_certs=False,
    timeout=30,
)

# BM25 text search
result = client.search(
    index="情报学报",
    body={
        "query": {"match": {"content": query_text}},
        "size": 10,
    }
)

# k-NN vector search (1024-dim, Qwen3-Embedding-0.6B)
result = client.search(
    index="情报学报",
    body={
        "query": {
            "knn": {
                "embedding": {
                    "vector": embedding_vector,
                    "k": 10,
                }
            }
        }
    }
)
```

**⚠️ Caution:** All `curl`/`requests` to `127.0.0.1:9202` must use `--noproxy '*'` or
`no_proxy=127.0.0.1` because mihomo intercepts localhost traffic.

---

## 6. Coding Standards

- **Language:** Python 3.10+ (same as system Python)
- **Style:** 4-space indent, snake_case, single quotes
- **LLM calls:** Use `langchain.chat_models.ChatOpenAI` with `base_url=http://127.0.0.1:1878/v1`
- **Config:** No hardcoded values. Read from `os.environ` or `narrabridge/config.py`
- **Outputs:** Write to `outputs/`, never to `qingbao_search/`
- **Tests:** pytest, run with `python -m pytest tests/ -v`
- **Commits:** Chinese commit messages preferred

---

## 7. Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| deepagents over LangGraph raw | Sub-agent context isolation + filesystem + compression out of box | 2026-06-10 |
| Local LLM over API | Cost (free GPU) + privacy | 2026-06-10 |
| BM25 + k-NN hybrid | Keyword for exact match, vector for semantic | 2026-06-10 |
| Separate from qingbao_search | Decouple data refinement from product development | 2026-06-10 |
| Phase 1 no-agent validation | Don't build agent pipeline until core retrieval quality proven | 2026-06-10 |

---

## 8. Getting Started (for a fresh coding agent)

```bash
# 1. Verify environment
python3 -c "from deepagents import create_deep_agent; print('deepagents OK')"
python3 -c "from opensearchpy import OpenSearch; print('opensearch OK')"
curl -s --noproxy '*' 'http://127.0.0.1:9202/_cat/indices?v' | grep 情报学报

# 2. Read context
cat AGENTS.md          # This file
cat PLAN.md            # Architecture
cat schemas/agent_io.json  # Data contracts
cat prompts/project_reader.md  # Start with Agent 1 prompt

# 3. Start Phase 1
python3 validate_phase1.py
```

**Your first commit should be:** running `validate_phase1.py` and showing the output.
Do NOT jump to Phase 2 agent implementation until the user confirms Phase 1 output quality.
