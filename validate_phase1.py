#!/usr/bin/env python3
"""
validate_phase1.py — Phase 1 Manual Validation for NarraBridge

GOAL: Prove that retrieval + LLM can produce useful narrative translation
      for trust-eval BEFORE writing any agent code.

WHAT IT DOES:
  1. Reads trust-eval AGENTS.md + research plan → extracts tech profile
  2. Constructs problem-semantic queries (NLP terms → 情报学报 terms)
  3. Searches OpenSearch 情报学报 index with each query
  4. Feeds results + tech profile to LLM for analysis
  5. Saves output to outputs/phase1_trust_eval.md

USAGE:
  python3 validate_phase1.py [--project ~/trust-eval] [--skip-llm]

PREREQUISITES:
  - OpenSearch running on 127.0.0.1:9202 (情报学报 index)
  - LiteLLM gateway on 127.0.0.1:1878 (vLLM with Qwen)
  - trust-eval project at ~/trust-eval
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.project_reader import extract_tech_profile
from tools.opensearch_search import text_search, index_health


# ── Configuration ──────────────────────────────────────────────────────────

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:1878/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-27b-reasoning")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "not-needed")
QINGBAO_MINERU_DIR = os.path.expanduser("~/qingbao_search/mineru_output")
OUTPUT_DIR = Path(__file__).parent / "outputs"


# ── Step 1: Extract Tech Profile ──────────────────────────────────────────


def step1_extract_profile(project_path: str) -> dict:
    """Extract a structured technical profile from the project."""
    print("=" * 60)
    print("STEP 1: Extracting technical profile...")
    print("=" * 60)
    profile = extract_tech_profile(project_path)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile


# ── Step 2: Construct Queries ──────────────────────────────────────────────


def step2_construct_queries(profile: dict) -> list[dict]:
    """
    Translate NLP terms from the tech profile into 情报学报 search queries.
    Each query is annotated with the translation rationale.
    """
    print("\n" + "=" * 60)
    print("STEP 2: Constructing problem-semantic queries...")
    print("=" * 60)

    queries = [
        {
            "nlp_terms": "post-hoc verification, audit",
            "qingbao_query": "情报分析 可信度 评估 后验 验证",
            "rationale": "trust-eval的核心创新是生成后审计，情报学报上对应'后验检验''可信度评估'",
        },
        {
            "nlp_terms": "multi-agent, pipeline",
            "qingbao_query": "多智能体 情报 分析 协同 生成",
            "rationale": "ABMS是10-agent流水线，情报学报上对应'多智能体协同''情报分析框架'",
        },
        {
            "nlp_terms": "RAG, retrieval, fact-checking",
            "qingbao_query": "检索增强 情报 事实验证 知识检索",
            "rationale": "pipeline中有检索和引用溯源，对应情报学'检索增强''事实验证'",
        },
        {
            "nlp_terms": "AI content quality, credibility",
            "qingbao_query": "人工智能 生成 内容 质量 控制 可信",
            "rationale": "通用的AI生成内容质量控制也是情报学关注方向",
        },
        {
            "nlp_terms": "citation tracing, provenance",
            "qingbao_query": "引用 溯源 情报 分析 信息 来源",
            "rationale": "citation_tracker模块对应情报学的信息溯源/来源可靠性",
        },
    ]

    # Add domain-specific queries based on profile
    if "NLI verification" in profile.get("tech_stack", []):
        queries.append(
            {
                "nlp_terms": "NLI, entailment, semantic",
                "qingbao_query": "语义 推理 蕴含 关系 验证 情报",
                "rationale": "NLI验证模块对应情报学的语义推理和关系验证",
            }
        )

    for i, q in enumerate(queries):
        print(f"\n[{i+1}] NLP: {q['nlp_terms']}")
        print(f"    → 情报学报: {q['qingbao_query']}")
        print(f"    理由: {q['rationale']}")

    return queries


# ── Step 3: Search OpenSearch ──────────────────────────────────────────────


def step3_search(queries: list[dict]) -> dict:
    """Execute all queries against OpenSearch and deduplicate results."""
    print("\n" + "=" * 60)
    print("STEP 3: Searching 情报学报 OpenSearch...")
    print("=" * 60)

    # Verify index health
    health = index_health()
    print(f"\nIndex health: {json.dumps(health, ensure_ascii=False)}")

    all_papers = {}
    for i, q in enumerate(queries):
        query_text = q["qingbao_query"]
        print(f"\n--- Query {i+1}: {query_text} ---")
        results = text_search(query_text, top_k=5)
        for j, r in enumerate(results):
            pid = r["id"]
            print(f"  [{j+1}] {r['title']} (score={r['score']:.2f}, id={pid})")
            if pid not in all_papers:
                r["matched_queries"] = [query_text]
                all_papers[pid] = r
            else:
                all_papers[pid]["matched_queries"].append(query_text)

    # Sort by score and deduplicate
    ranked = sorted(all_papers.values(), key=lambda x: x["score"], reverse=True)
    print(f"\nTotal unique papers found: {len(ranked)}")
    return {"queries": queries, "papers": ranked[:15]}


# ── Step 4: Read Paper Content ─────────────────────────────────────────────


def step4_read_papers(search_results: dict) -> list[dict]:
    """Read the minerU output for each paper to get full text context."""
    print("\n" + "=" * 60)
    print("STEP 4: Reading minerU outputs...")
    print("=" * 60)

    enriched = []
    for paper in search_results["papers"]:
        pid = paper["id"]
        mineru_path = Path(QINGBAO_MINERU_DIR) / f"{pid}.md"
        if mineru_path.exists():
            content = mineru_path.read_text(encoding="utf-8")
            # Extract intro/method sections
            intro = _extract_section(content, ["引言", "引言", "前言", "1.", "一、"])
            method = _extract_section(content, ["方法", "模型", "框架", "2.", "二、", "3.", "三、"])
            paper["intro_excerpt"] = intro[:1500] if intro else "未找到引言"
            paper["method_excerpt"] = method[:1500] if method else "未找到方法章节"
            paper["has_full_text"] = True
            print(f"  ✅ {pid}: intro={len(intro)} chars, method={len(method)} chars")
        else:
            paper["intro_excerpt"] = "minerU output not found"
            paper["method_excerpt"] = "minerU output not found"
            paper["has_full_text"] = False
            print(f"  ⚠️  {pid}: minerU output not found")
        enriched.append(paper)

    return enriched


def _extract_section(content: str, patterns: list[str]) -> str:
    """Extract a section of text matching one of the patterns."""
    content_lower = content
    for pat in patterns:
        idx = content_lower.find(pat)
        if idx >= 0:
            # Take ~3000 chars from the match point
            return content[idx : idx + 3000]
    return ""


# ── Step 5: LLM Analysis ──────────────────────────────────────────────────


def step5_llm_analyze(profile: dict, search_results: dict, papers: list[dict]) -> str:
    """Feed all collected data to LLM for narrative translation analysis."""
    print("\n" + "=" * 60)
    print("STEP 5: LLM Analysis...")
    print("=" * 60)

    # Build the prompt
    prompt = _build_analysis_prompt(profile, search_results, papers)
    print(f"Prompt length: {len(prompt)} chars")

    if "--skip-llm" in sys.argv:
        print("\n⚠️  --skip-llm flag set. Saving prompt only.")
        return f"# LLM Analysis (SKIPPED)\n\n## Prompt that would be sent\n\n```\n{prompt[:2000]}...\n```"

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            temperature=0.3,
            max_tokens=4096,
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        output = response.content
        print(f"LLM output: {len(output)} chars")
        return output

    except ImportError:
        print("⚠️  langchain not installed. Run: pip3 install langchain-core langchain")
        return "# LLM Analysis (ERROR: langchain not installed)\n\n## Prompt\n\n" + prompt[
            :3000
        ]
    except Exception as e:
        print(f"⚠️  LLM call failed: {e}")
        return f"# LLM Analysis (ERROR: {e})\n\n## Prompt\n\n{prompt[:3000]}"


def _build_analysis_prompt(profile: dict, search_results: dict, papers: list[dict]) -> str:
    """Build the LLM analysis prompt."""
    # Tech profile summary
    tech_summary = json.dumps(profile, ensure_ascii=False, indent=2)

    # Paper summaries
    paper_texts = []
    for p in papers:
        paper_texts.append(
            f"""
### {p['title']} (id={p['id']}, score={p['score']:.2f})
**Matched by**: {', '.join(p.get('matched_queries', []))}
**Introduction excerpt**:
{p['intro_excerpt'][:800]}

**Method excerpt**:
{p['method_excerpt'][:800]}
"""
        )
    papers_text = "\n---\n".join(paper_texts)

    return f"""你是一个情报学报的资深作者和审稿人。你需要帮助一位 NLP 研究者将他的工程方案翻译成情报学论文。

## 项目技术画像

{tech_summary}

## 情报学报相关论文检索结果

共检索到 {len(papers)} 篇可能相关的论文：

{papers_text}

## 请回答以下问题

### 1. 问题定位
trust-eval 解决的是什么情报学问题？请用情报学报的语言重新定义研究问题。
从检索到的论文中，哪些论文讨论的是类似的问题？

### 2. 术语翻译
将以下 NLP 术语翻译为情报学报常用术语：
- multi-agent pipeline →
- post-hoc verification/audit →
- fact decomposition/NLI verification →
- citation tracking/provenance →
- ABMS (Agent-Based Modeling and Simulation) →
- TRUST audit layer →

### 3. 引言撰写
请为 trust-eval 写一段情报学报风格的引言第一段（150-200 字）。
要求：
- 不要用"随着人工智能技术的快速发展"开头
- 从情报分析的具体场景切入
- 指出当前方法的问题
- 自然引出本文研究动机

### 4. 相关工作分类
trust-eval 的 related work 应该包含哪几个子方向？
请结合检索到的论文给出分类建议。

### 5. 实验补充
trust-eval 目前的实验（ISR 主题，244 份 USAF 手册，10-agent pipeline）
与情报学报同类论文相比，可能需要补充什么实验？

请用中文回答，每项分析引用具体的论文 ID 作为证据。"""


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="NarraBridge Phase 1 Validation")
    parser.add_argument(
        "--project",
        default=os.path.expanduser("~/trust-eval"),
        help="Path to project to analyze",
    )
    parser.add_argument(
        "--skip-llm", action="store_true", help="Skip LLM call, save prompt only"
    )
    parser.add_argument(
        "--query-only",
        action="store_true",
        help="Only run steps 1-4 (no LLM), for testing retrieval quality",
    )
    args = parser.parse_args()

    # Ensure output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run pipeline
    profile = step1_extract_profile(args.project)

    queries = step2_construct_queries(profile)

    search_results = step3_search(queries)
    if args.query_only:
        # Save search results for manual review
        out_path = OUTPUT_DIR / "phase1_search_results.json"
        out_path.write_text(json.dumps(search_results, ensure_ascii=False, indent=2))
        print(f"\n✅ Search results saved to {out_path}")
        print("Review these manually before running full analysis.")
        return

    papers = step4_read_papers(search_results)

    analysis = step5_llm_analyze(profile, search_results, papers)

    # Save output
    output = f"""# NarraBridge Phase 1 Validation: trust-eval

> Generated: {datetime.now().isoformat()}
> Project: {args.project}

---

## 技术画像

```json
{json.dumps(profile, ensure_ascii=False, indent=2)}
```

---

## 检索查询

{chr(10).join(f"- **{q['nlp_terms']}** → `{q['qingbao_query']}` ({q['rationale']})" for q in queries)}

---

## 检索结果 ({len(papers)} papers)

{chr(10).join(f"- [{p['id']}] **{p['title']}** (score={p['score']:.2f})" for p in papers)}

---

## LLM 分析

{analysis}

---

## 下一步

1. 人工评估以上输出的质量
2. 判断检索到的论文是否真正相关
3. 判断 LLM 的问题定位和术语翻译是否准确
4. 如果方向正确 → 进入 Phase 2（Agent 管线实现）
5. 如果方向偏差 → 调整查询策略或 prompt 后重新验证
"""

    out_path = OUTPUT_DIR / "phase1_trust_eval.md"
    out_path.write_text(output, encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"✅ Phase 1 validation complete!")
    print(f"   Output: {out_path}")
    print(f"   Size: {out_path.stat().st_size:,} bytes")
    print("=" * 60)
    print("\n⚠️  Next: Show this output to the user for quality evaluation.")
    print("   Do NOT proceed to Phase 2 until user confirms.")


if __name__ == "__main__":
    main()
