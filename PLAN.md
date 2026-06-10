# PLAN.md — NarraBridge

> **Last updated:** 2026-06-10
> **Current phase:** ① Manual validation
>
> **👉 For implementation instructions, see [AGENTS.md](AGENTS.md).**
> This file is the architecture reference. AGENTS.md is the executable dev spec.

---

## 1. Project goal

Build an AI-powered product that helps NLP/LLM practitioners write intelligence studies
papers by **translating engineering narratives into discipline-specific academic language**,
grounded in a domain knowledge base of 477 full-text papers from *情报学报*.

### What it is NOT

- ❌ A method improvement tool ("which baseline should I add?")
- ❌ A general academic writing assistant
- ❌ A language polish tool

### What it IS

- ✅ A narrative translation engine (engineering → intelligence studies)
- ✅ A domain-grounded writing guide (evidence from real published papers)
- ✅ A discipline-specific peer reviewer

---

## 2. Core insight

The user's bottleneck is neither technical capability nor academic writing skills — it's
**knowing how to frame an NLP system as answering an intelligence studies question**.

This requires:
1. Understanding the **problem taxonomy** of intelligence studies (what counts as a research question)
2. Knowing the **narrative conventions** (how problems are introduced, how methods are described)
3. Mastering the **terminology** (what words do published papers actually use)

All three are encoded in the 477 papers. NarraBridge extracts and operationalizes them.

---

## 3. Three use scenarios

### Scene 1: Entry guidance

```
Input:  "I build RAG systems and multi-agent pipelines. What can I do in intelligence studies?"
Output:
  · Your skills match these intelligence studies problem areas: [list with evidence]
  · Here's how similar problems are framed in 情报学报: [excerpts from 5 papers]
  · Suggested research questions: [3-5 concrete formulations]
```

### Scene 2: Code-to-paper translation (primary)

```
Input:  trust-eval project directory (code + docs + README)
Output:
  · Technical profile: what your system does in engineering terms
  · Problem mapping: what intelligence studies question this answers
  · Introduction draft: problem definition in discipline-appropriate language
  · Related work: classified bibliography with rationale
  · Methods section: translated from technical docs
  · Experiment checklist: what's missing vs. peer papers
```

### Scene 3: Peer review

```
Input:  A paper draft (Chinese, targeting 情报学报)
Output:
  · Terminology audit: your word choices vs. published norms
  · Structure comparison: your sections vs. peer papers
  · Citation audit: coverage of key papers in the subfield
  · Contribution framing audit: "we built a system" → "we solve a problem"
```

---

## 4. Architecture

### 4.1 Agent orchestration layer

**Framework:** [deepagents](https://github.com/langchain-ai/deepagents) v0.6.8 (Python SDK, installed)

Why deepagents:
- Sub-agent spawning with isolated context windows → each agent has clean prompt + KB access
- Virtual filesystem → output artifacts persist to disk automatically
- Context compression middleware → 20+ full papers in context don't overflow
- Model-agnostic → runs against local vLLM (Qwen3.6-35B-A3B, port 8000→1878)
- MCP support → future data source extensibility

### 4.2 Five specialized agents

```
                    ┌─────────────────┐
                    │  Orchestrator    │
                    │  (deepagents)    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
    │ Project  │      │  Problem    │     │  Narrative  │
    │ Reader   │ ────▶│  Mapper     │────▶│  Extractor  │
    │          │      │             │     │             │
    └──────────┘      └─────────────┘     └─────────────┘
                                                  │
                          ┌───────────────────────┤
                          │                       │
                    ┌─────▼──────┐         ┌──────▼──────┐
                    │  Paper     │         │    Peer     │
                    │  Generator │         │  Reviewer   │
                    │            │◀────────│             │
                    └────────────┘         └─────────────┘
```

**Agent 1: Project Reader**
- Input: project path
- Reads: README, AGENTS.md, core code files, config, docs
- Output: structured JSON profile
  ```json
  {
    "tech_stack": ["multi-agent", "RAG", "post-hoc verification"],
    "core_innovation": "decoupled generation and verification",
    "experimental_setup": {"dataset": "244 USAF manuals", "topic": "ISR"},
    "existing_results": {...}
  }
  ```

**Agent 2: Problem Mapper**
- Input: technical profile from Agent 1
- Queries: OpenSearch 情报学报 with problem-semantic search
- Task: find papers that address similar *problems* (NOT similar methods)
- Translation: "ABMS + post-hoc audit" → "情报分析可信度评估 / AI生成内容质量控制"
- Output: problem type classification + top-10 related papers + 问题定义原文摘录

**Agent 3: Narrative Extractor**
- Input: top-10 papers from Agent 2
- Tasks:
  - Extract introduction structure (problem framing patterns)
  - Extract method description conventions
  - Build terminology frequency map
  - Extract experiment design norms
- Output:
  - Introduction templates (with real examples)
  - Method description templates
  - Terminology mapping table (your words vs. journal norms)
  - Minimum experiment checklist

**Agent 4: Paper Generator**
- Input: tech profile + narratives + terminology + related papers
- Tasks:
  - Write introduction ¶1 (problem definition, discipline-appropriate)
  - Write related work (classified by problem type)
  - Write methods (translate from technical docs)
  - List suggested experiments (with rationale from peer papers)
- Output: paper outline + draft sections + experiment suggestions

**Agent 5: Peer Reviewer**
- Input: paper draft + domain norms from Agent 3
- Tasks:
  - Terminology audit (your words vs. journal word frequency)
  - Structure audit (your sections vs. peer paper structure)
  - Citation audit (key papers covered?)
  - Contribution framing audit (engineering → academic)
- Output: review report + revision suggestions + evidence

### 4.3 Knowledge layer

**OpenSearch 情报学报 index:**
```
Index: 情报学报
Documents: 30,746 chunks (from 477 full-text papers)
Vector dim: 1024 (Qwen3-Embedding-0.6B compatible)
Retrieval: BM25 + Dense hybrid
API: 127.0.0.1:9202 (no auth)
```

**Structured knowledge (to be extracted):**
- Terminology dictionary: NLP terms → 情报学报 equivalents
- Narrative patterns: introduction structure templates from real papers
- Experiment checklist: common experiment types and their requirements
- Problem taxonomy: 8 types from literature_analysis.md

### 4.4 Custom tools (deepagents Tool interface)

| Tool | Function | Calls |
|------|----------|-------|
| `search_qingbao` | Vector + BM25 hybrid search on 情报学报 index | `curl 127.0.0.1:9202` |
| `read_project` | Extract technical profile from codebase | Local file reads |
| `get_paper_sections` | Fetch specific sections from minerU output | Read from qingbao_search/mineru_output/ |
| `batch_summary` | Get the batch synthesis for a paper's subfield | Read from qingbao_search/cumulative_synthesis.md |
| `term_frequency` | Check word usage frequency in the corpus | OpenSearch aggregation |
| `compare_structure` | Compare paper structure to peer norms | LLM analysis |

---

## 5. Phase plan

### Phase ① — Manual validation (current)

**Goal:** Prove the core pipeline works before writing any agent code.

**Steps:**
1. ✅ 477 papers downloaded, parsed, indexed
2. ✅ literature_analysis.md generated (8 problem types, 4 narrative modes)
3. ⬜ Read trust-eval AGENTS.md + 研究方案 → extract technical profile (manually)
4. ⬜ Search OpenSearch for problem-matched papers (manually, 3-5 queries)
5. ⬜ Feed top-5 papers + tech profile to LLM, ask it to generate:
   - Problem definition in 情报学报 style
   - Terminology mapping
   - Introduction ¶1 draft
6. ⬜ Evaluate output quality with user
7. ⬜ If good → Phase ②. If poor → diagnose and fix retrieval/prompt strategy.

**Validation criteria:**
- Agent 2 (Problem Mapper) finds at least 3 genuinely relevant papers
- Agent 4 (Paper Generator) produces an introduction that *feels like* 情报学报 language
- User judgment: "Yes, this translation direction is correct"

### Phase ② — Agent pipeline implementation

**Goal:** Implement 5-agent pipeline with deepagents.

**Tasks:**
1. Write `tools/opensearch_search.py` — Python function wrapping OpenSearch curl
2. Write `tools/project_reader.py` — parse codebase into tech profile
3. Write system prompts for all 5 agents (`prompts/*.md`)
4. Wire agents together with deepagents `create_deep_agent`
5. Implement CLI entry point
6. Run end-to-end on trust-eval case
7. Compare output with Phase ① manual results → ensure no regression

**Output:** `python -m narrabridge translate ~/trust-eval` produces a paper draft.

### Phase ③ — Terminology dictionary

**Goal:** Extract a domain terminology dictionary from 477 papers.

**Tasks:**
1. Run terminology mining across all minerU outputs
2. Build NLP → 情报学 term mapping table
3. Extract high-frequency academic phrases
4. Save as `knowledge/terminology.yml`
5. Integrate into Agent 3 and Agent 5 system prompts

### Phase ④ — Web UI

**Goal:** Gradio web interface with three entry points.

**Tasks:**
1. Build Gradio app with three tabs (Entry / Translate / Review)
2. Each tab triggers the appropriate agent pipeline
3. Real-time streaming of agent output
4. Download artifact button (paper draft, review report)
5. Deploy on port (TBD, avoid conflict with existing services)

### Phase ⑤ — Iterative refinement

**Goal:** Harden the system on real use cases.

**Tasks:**
1. Run trust-eval through the full pipeline
2. User feedback on output quality
3. Tune prompts, retrieval strategies, terminology mapping
4. Test with 2-3 additional projects

---

## 6. Technical decisions

### LLM

**Primary:** Qwen3.6-35B-A3B (served via vLLM on GPU 0-3, port 8000 → LiteLLM 1878)
**Fallback:** DeepSeek V4 Pro (API)
**Rationale:** Local model for cost and privacy; cloud fallback for when Sichuan server is busy.

### Retrieval strategy

**Hybrid:** BM25 (keyword) + Dense (vector, 1024-dim) → rerank by metadata relevance
**Query construction:** NOT "trust eval agent verification" → INSTEAD "情报分析 可信度 评估 AI 质量 控制 验证"
**Why:** The most critical engineering decision. Keyword-match queries will return zero results.
The Problem Mapper agent must do *semantic field translation* before querying.

### Output persistence

Deepagents virtual filesystem auto-saves outputs. Format:
```
outputs/
└── {project_name}/
    ├── tech_profile.json          # Agent 1 output
    ├── problem_mapping.md          # Agent 2 output
    ├── narrative_patterns.md       # Agent 3 output
    ├── paper_draft.md              # Agent 4 output
    └── review_report.md            # Agent 5 output
```

### Knowledge base freshness

The 情报学报 index covers 2025 (50 issues, 477 papers). When new issues are published:
1. Download new PDFs via the batch_download pipeline (~/qingbao_search/batch_download.py)
2. Parse via minerU Docker API (port 1881)
3. Re-index into OpenSearch (incremental)
4. Update terminology dictionary (if frequency shifts detected)

---

## 7. Risks

| Risk | Probability | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Retrieval finds irrelevant papers | Medium | High | Phase ① manual validation first. If retrieval fails, pivot to different query strategy or add paper metadata filters |
| LLM output sounds generic | Medium | Medium | Strong system prompts with few-shot examples from real 情报学报 papers |
| Term frequency is misleading (small corpus) | Low | Medium | 477 papers × average 8,000 chars = ~3.8M chars. Sufficient for terminology mining |
| Antigravity can't run deepagents | Low | Low | The code is plain Python + LangChain. Any coding agent (Claude Code, Codex) can execute it |
| Trust-eval not representative | Low | Medium | If trust-eval doesn't map well to intelligence studies, use a different case study |

---

## 8. Key design principles

1. **Retrieval quality > agent quality.** Bad retrieval → bad everything. Validate Phase ① thoroughly.
2. **Show, don't just tell.** Every suggestion must cite specific paper evidence (paper ID + excerpt).
3. **Translation, not improvement.** The system translates existing work into academic language; it does NOT suggest methodological changes unless asked.
4. **Chinese-first.** All outputs in Chinese, targeting 情报学报 conventions. English support is secondary.
5. **Separation from data.** `narrabridge/` reads from `qingbao_search/` but never writes to it. Data refinement and product development are decoupled.

---

## 9. Next action

**Today:** Start Phase ① — manually validate the core pipeline on trust-eval.

1. Read trust-eval AGENTS.md + 研究方案 → create tech profile
2. Search OpenSearch with problem-semantic queries
3. Feed results to LLM and evaluate output
4. Report to user with findings
