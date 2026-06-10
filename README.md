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
| 1 | ✅ Done | Manual validation — does retrieval + LLM produce useful output? |
| 2 | 🔴 Current | Implement 5-agent pipeline with deepagents |
| 3 | ⬜ | Terminology dictionary extraction from 477 papers |
| 4 | ⬜ | Gradio Web UI with three entry points |
| 5 | ⬜ | Iterative refinement on trust-eval case study |

---

## 阶段一实现与验证说明

### 1. 核心实现机制
阶段一（单脚本手动管道验证）的目的是在构建复杂的 Agent 编排框架之前，验证“检索匹配 + LLM 学术重构”的可行性，核心细节如下：
- **项目画像提取 (Project Profile Extraction)**：运行 `tools/project_reader.py` 对测试项目 `/home/yuanming/trust-eval` 下的文档进行扫描，提取出该项目的技术栈、核心创新（生成与确证解耦）、现有实验评估指标（CSS, NLI）和模块列表。
- **学术语义匹配与检索 (Problem-Semantic Search)**：将工程术语翻译为面向《情报学报》研究领域的情报学检索查询。纠正了 OpenSearch 底层 Mapping 字段为 `text` 字段的 Bug 后，通过本地 OpenSearch 进行了全文检索，成功检索去重出 30 篇高度相关的候选文献。
- **文献章节提取 (Section Exporter)**：自动读取 `~/qingbao_search/mineru_output` 下已用 minerU 解析出的对应 md 文献（如 `qbxb_xxx.md`），截取包含引言和方法论的核心内容片段。
- **学术级对比分析与翻译**：将提取到的技术画像与检索到的文献片段整合输入大语言模型，完成了对 trust-eval 学术研究层面的重构定位，生成了学术术语对照表和符合《情报学报》风格的引言草稿，并产出了实验补充建议报告。

### 2. 使用的语言模型 (LLM)
- **推理与总结模型**：**`qwen-27b-reasoning`**（基于四川服务器本地部署的 vLLM 实例服务）。
- **接入细节**：通过本地 `127.0.0.1:1878` 端口运行的 LiteLLM 网关进行鉴权和中转。运行中我们定位并修复了 LiteLLM 网关密钥鉴权 401 报错问题，通过获取并配置本地正确的 Master Key `sk-ym-...2025` 成功完成鉴权。由于该模型具备深度思维链推理（Reasoning）能力，产出的学术重构及学术表述具有极高的情报学品味和理论深度。

### 3. 环境与最终产出
- **运行环境**：完全在新建的 `bridge` Conda 环境（Python 3.11）中执行。
- **产出路径**：最终验证结论成功输出到 [outputs/phase1_trust_eval.md](outputs/phase1_trust_eval.md) 文件中。

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
