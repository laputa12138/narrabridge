# 🖋️ NarraBridge

> **Engineering → Intelligence Studies. Narrative translation, not method improvement.**
>
> NarraBridge bridges the gap between your NLP system and an intelligence studies paper — it
> doesn't help you improve your method; it helps you **re-frame an engineering artifact as an
> answer to a discipline-specific research question**, using a domain knowledge base of 477
> full-text papers from *情报学报* (Journal of Intelligence) as the translation reference.

---

## What problem does it solve?

```
You have:  a working system (LLM agents, RAG, verification pipeline...)
You need: an intelligence studies paper that gets accepted at 情报学报

The gap:  How do you describe your work as solving an "情报学问题" (intelligence studies problem)?
          What terminology do you use? What papers do you cite? What experiments do you add?
```

Existing tools (Paperpal, Writefull, SciSpace, even ChatGPT) can polish language. None of them
know what a proper intelligence studies paper looks like. **NarraBridge does**, because it's
built on top of a domain-specific OpenSearch index of every paper published in your target journal.

---

## Three entry points

| Scene | What you have | What NarraBridge does |
|:-----:|---------------|----------------------|
| **1. Entry** | LLM/NLP skills, no domain knowledge | Finds intelligence studies problems that match your technical stack, shows how they're framed in real papers |
| **2. Translate** | A working codebase (e.g. `trust-eval`) | Translates your engineering narrative into academic language, generates introduction / related work / method drafts, suggests missing experiments |
| **3. Review** | A paper draft | Audits terminology against published norms, compares structure to peer papers, flags deviations |

All three share the same core capability: **retrieve → compare → translate**, grounded in real
published papers rather than LLM general knowledge.

---

## Architecture

```
┌────────────────────────────────────────────────┐
│              CLI / Gradio Web UI                │
├────────────────────────────────────────────────┤
│     Orchestrator Agent (deepagents)             │
│     · Intent parsing · Agent routing            │
│     · Context management · Output persistence   │
├────────────────────────────────────────────────┤
│              5 Specialized Agents                │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐   │
│  │ Project  │ │ Problem  │ │ Narrative     │   │
│  │ Reader   │ │ Mapper   │ │ Extractor     │   │
│  └──────────┘ └──────────┘ └───────────────┘   │
│  ┌──────────┐ ┌──────────┐                     │
│  │ Paper    │ │ Peer     │                     │
│  │ Generator│ │ Reviewer │                     │
│  └──────────┘ └──────────┘                     │
├────────────────────────────────────────────────┤
│          Domain Knowledge Layer                  │
│  ┌────────────────────────────────────────┐    │
│  │  OpenSearch 情报学报 (30K chunks)        │    │
│  │  · Vector search (1024-dim)            │    │
│  │  · Hybrid BM25 + Dense retrieval       │    │
│  │  · Metadata filters (year, subdomain)  │    │
│  └────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────┐    │
│  │  Structured knowledge                  │    │
│  │  · literature_analysis.md              │    │
│  │  · Terminology dictionary              │    │
│  │  · Narrative pattern templates         │    │
│  └────────────────────────────────────────┘    │
└────────────────────────────────────────────────┘
```

**Built on** [deepagents](https://github.com/langchain-ai/deepagents) (LangChain) for agent
orchestration, context management, and sub-agent isolation. Model-agnostic — runs against any
LLM with tool-calling support, including local vLLM.

---

## Directory structure

```
narrabridge/
├── README.md                ← this file
├── PLAN.md                  ← detailed implementation plan
│
├── agents/                  ← 5 specialized agents (deepagents harness)
│   ├── project_reader.py
│   ├── problem_mapper.py
│   ├── narrative_extractor.py
│   ├── paper_generator.py
│   └── peer_reviewer.py
│
├── tools/                   ← custom tools for agents
│   ├── opensearch_search.py ← query the 情报学报 index
│   ├── project_reader.py    ← read codebase and extract tech profile
│   └── terminology.py       ← domain terminology dictionary
│
├── knowledge/               ← structured domain knowledge
│   ├── terminology.yml      ← NLP ↔ 情报学 term mappings
│   ├── narrative_patterns/  ← extracted intro/Method templates
│   └── experiment_checklist.yml ← common experiment patterns
│
├── prompts/                 ← system prompts for each agent
│   ├── project_reader.md
│   ├── problem_mapper.md
│   ├── narrative_extractor.md
│   ├── paper_generator.md
│   └── peer_reviewer.md
│
├── ui/                      ← Gradio web interface
│   └── app.py
│
├── tests/                   ← (Phase 2+)
│   └── ...
│
└── outputs/                 ← generated artifacts
    └── ...
```

---

## Phase status

| Phase | Status | Description |
|:-----:|:------:|-------------|
| 0 | ✅ Done | 477 papers downloaded, minerU-parsed, indexed in OpenSearch |
| 1 | 🔴 Current | Manual validation — does retrieval + LLM produce useful output? |
| 2 | ⬜ | Implement 5-agent pipeline with deepagents |
| 3 | ⬜ | Terminology dictionary extraction from 477 papers |
| 4 | ⬜ | Gradio Web UI with three entry points |
| 5 | ⬜ | Iterative refinement on trust-eval case study |

---

## Related projects

| Project | Relationship |
|---------|-------------|
| `qingbao_search/` | Data source — 477 情报学报 papers + minerU outputs + summaries |
| `trust-eval` | Primary case study — the first project to go through NarraBridge |
| `feynman` | Reference — research agent patterns, peer review design |
| `PaperOrchestra` | Reference — Google's multi-agent paper writing pipeline |

---

## License

MIT
