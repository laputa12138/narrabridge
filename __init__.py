import os
import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tools.project_reader import extract_tech_profile
from tools.opensearch_search import text_search
from tools.paper_reader import get_paper_sections
from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

# 确保 outputs 目录存在
OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def run_structured_agent(prompt_name: str, schema_key: str, input_data: dict) -> dict:
    """
    运行一个结构化的大模型代理节点（基于原生 LangChain 直连 vLLM，彻底防止网络挂起）。
    """
    # 1. 读取系统提示词
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 2. 读取输出 JSON Schema 并进行顶层顶级包裹
    schema_path = Path(__file__).parent / "schemas" / "agent_io.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    raw_schema = schema_data[schema_key]["output"]
    
    # 包装为 OpenAI 规范的 Function/JSON Schema 顶级格式
    wrapped_schema = {
        "type": "object",
        "title": f"{schema_key}_Output",
        "properties": raw_schema,
        "required": list(raw_schema.keys())
    }

    # 3. 实例化大模型客户端，直连 vLLM 8000 端口
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2,
        max_tokens=4096,
        timeout=180  # 3分钟超时防护
    )
    
    # 使用 LangChain 原生的 with_structured_output 约束大模型返回 JSON
    structured_llm = llm.with_structured_output(wrapped_schema)
    
    # 4. 发起调用并返回强类型约束下的结构化数据字典
    res = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"输入数据如下：\n{json.dumps(input_data, ensure_ascii=False)}")
    ])
    return res


def translate_pipeline(project_path: str):
    """
    场景 2：代码到论文一键翻译（原生高效版）。
    在外部通过 Python 执行所有的 OpenSearch 检索和文件 I/O 读取，整合数据后交由大模型完成学术翻译。
    """
    proj_path = Path(project_path).expanduser().resolve()
    project_name = proj_path.name
    proj_output_dir = OUTPUTS_DIR / project_name
    proj_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n============================================================")
    print(f"🚀 开始 NarraBridge 翻译管道: {project_name}")
    print(f"============================================================")

    # 1. 提取技术特征画像 (由 Python 直接完成物理提取，避开大模型冗余调用)
    print("\n[Step 1/5] 正在提取技术特征画像...")
    tech_profile = extract_tech_profile(str(proj_path))
    
    profile_path = proj_output_dir / "tech_profile.json"
    profile_path.write_text(json.dumps(tech_profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 技术画像提取完成，已保存至: {profile_path.relative_to(Path.cwd())}")

    # 2. 外部设计检索词并查询 OpenSearch，接着运行 Agent 2 (Problem Mapper)
    print("\n[Step 2/5] 正在通过 Python 进行 OpenSearch 文献并行检索与过滤...")
    queries = _construct_queries_from_profile(tech_profile)
    
    all_papers = {}
    for i, q in enumerate(queries):
        query_text = q["qingbao_query"]
        results = text_search(query_text, top_k=5)
        for r in results:
            pid = r["id"]
            if pid not in all_papers:
                r["matched_queries"] = [query_text]
                all_papers[pid] = r
            else:
                all_papers[pid]["matched_queries"].append(query_text)
                
    ranked_papers = sorted(all_papers.values(), key=lambda x: x["score"], reverse=True)[:10]
    print(f"🔍 OpenSearch 检索完毕，共筛选出 {len(ranked_papers)} 篇高度相关的《情报学报》论文。")

    print("→ 正在运行 Problem Mapper 进行学术问题与术语映射定位...")
    input_mapper = {
        "tech_profile": tech_profile,
        "candidate_papers": ranked_papers,
        "query_translations_reference": queries
    }
    problem_mapping = run_structured_agent("problem_mapper", "Agent2_ProblemMapper", input_mapper)
    
    mapping_path = proj_output_dir / "problem_mapping.json"
    mapping_path.write_text(json.dumps(problem_mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 问题映射匹配完成，已保存至: {mapping_path.relative_to(Path.cwd())}")

    # 3. 外部读取 minerU 文献片段，运行 Agent 3 (Narrative Extractor)
    print("\n[Step 3/5] 正在通过 Python 读取文献引言/方法片段...")
    top_papers = problem_mapping.get("top_papers", ranked_papers)
    enriched_papers = []
    for paper in top_papers:
        pid = paper.get("id")
        title = paper.get("title", "")
        sections = get_paper_sections(pid, title)
        paper_info = {
            "id": pid,
            "title": paper.get("title", "未知"),
            "intro_excerpt": sections.get("intro_excerpt", ""),
            "method_excerpt": sections.get("method_excerpt", "")
        }
        enriched_papers.append(paper_info)
    print(f"🔍 成功读取了 {len(enriched_papers)} 篇文献的全文片段。")

    print("→ 正在运行 Narrative Extractor 提取论文叙事特征...")
    narrative_template = run_structured_agent("narrative_extractor", "Agent3_NarrativeExtractor", enriched_papers)
    
    narrative_path = proj_output_dir / "narrative_patterns.json"
    narrative_path.write_text(json.dumps(narrative_template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 叙事模式提取完成，已保存至: {narrative_path.relative_to(Path.cwd())}")

    # 4. 运行 Agent 4: Paper Generator
    print("\n[Step 4/5] 正在运行 Paper Generator 撰写学术论文草稿...")
    input_gen = {
        "tech_profile": tech_profile,
        "problem_mapping": problem_mapping,
        "narrative_template": narrative_template
    }
    paper_draft = run_structured_agent("paper_generator", "Agent4_PaperGenerator", input_gen)
    
    draft_md = _format_paper_draft(paper_draft)
    draft_path = proj_output_dir / "paper_draft.md"
    draft_path.write_text(draft_md, encoding="utf-8")
    print(f"✅ 论文草稿生成完毕，已保存至: {draft_path.relative_to(Path.cwd())}")

    # 5. 运行 Agent 5: Peer Reviewer
    print("\n[Step 5/5] 正在运行 Peer Reviewer 生成学术评审报告...")
    input_rev = {
        "paper_draft": paper_draft,
        "narrative_template": narrative_template
    }
    review_report = run_structured_agent("peer_reviewer", "Agent5_PeerReviewer", input_rev)
    
    report_md = _format_review_report(review_report)
    report_path = proj_output_dir / "review_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"✅ 同行评审意见生成完毕，已保存至: {report_path.relative_to(Path.cwd())}")
    print(f"\n============================================================")
    print(f"🎉 翻译管道运行成功！全部产物位于 outputs/{project_name}/ 目录下")
    print(f"============================================================")


def entry_pipeline(query: str):
    """
    场景 1：学术切入点引导。
    根据用户的 NLP 技术栈，提供可能的情报学匹配方向和类似论文。
    """
    print(f"\n💡 开始学术方向发现引导: 关键字 = '{query}'")
    dummy_profile = {
        "tech_stack": [query],
        "core_innovation": f"基于 {query} 技术的学术应用尝试",
        "experimental_setup": {},
        "existing_results": "",
        "modules": []
    }
    
    queries = _construct_queries_from_profile(dummy_profile)
    all_papers = {}
    for q in queries:
        results = text_search(q["qingbao_query"], top_k=5)
        for r in results:
            all_papers[r["id"]] = r
    ranked_papers = sorted(all_papers.values(), key=lambda x: x["score"], reverse=True)[:5]

    input_mapper = {
        "tech_profile": dummy_profile,
        "candidate_papers": ranked_papers,
        "query_translations_reference": queries
    }
    output = run_structured_agent("problem_mapper", "Agent2_ProblemMapper", input_mapper)
    
    print("\n" + "="*50)
    print(f"🌟 推荐情报学研究方向: {output.get('problem_type', '未知')}")
    print(f"🎯 推荐可信度评估置信分数: {output.get('confidence', 0.0)}")
    
    print("\n📚 推荐可供学习和引用的《情报学报》相似文献:")
    for paper in output.get("top_papers", []):
        print(f"- **[{paper.get('id')}] {paper.get('title')}**")
        print(f"  * 推荐理由: {paper.get('relevance_reason')}")
        print(f"  * 论文中典型的问题描述: \"{paper.get('excerpt')}\"")
        
    print("\n🔍 推荐的学术检索对照映射:")
    for term in output.get("query_translations", []):
        print(f"- `{term.get('nlp_term')}` 对应情报学专用词 `\"{term.get('qingbao_term')}\"`")
    print("="*50)


def review_pipeline(draft_path: str):
    """
    场景 3：论文同行评审。
    读取已有的 Markdown 草稿，运行评审代理生成审计报告。
    """
    path = Path(draft_path).expanduser().resolve()
    if not path.exists():
        print(f"❌ 找不到草稿文件: {path}")
        return
        
    print(f"\n🔬 开始对草稿进行同行评审: {path.name}")
    draft_content = path.read_text(encoding="utf-8")
    
    dummy_draft = {
        "title_suggestions": [path.name],
        "introduction": draft_content[:2000],
        "related_work": draft_content[2000:4000],
        "methods": draft_content[4000:],
        "suggested_experiments": []
    }
    
    # 尝试自动检测并加载同级目录下的叙事模式/术语映射库，以保障评审时有据可依
    narrative_template = {}
    patterns_path = path.parent / "narrative_patterns.json"
    if patterns_path.exists():
        try:
            narrative_template = json.loads(patterns_path.read_text(encoding="utf-8"))
            print(f"🔍 自动检测并成功加载同级叙事对照参考库: {patterns_path.name}")
        except Exception as e:
            print(f"⚠️  加载同级叙事对照参考库时出错: {e}")

    input_rev = {
        "paper_draft": dummy_draft,
        "narrative_template": narrative_template
    }
    report = run_structured_agent("peer_reviewer", "Agent5_PeerReviewer", input_rev)
    
    report_md = _format_review_report(report)
    out_path = path.parent / f"{path.stem}_review_report.md"
    out_path.write_text(report_md, encoding="utf-8")
    
    print("\n" + "="*50)
    print(f"📋 评审评级: {report.get('overall_assessment', '未知')}")
    print(f"📝 核心意见摘要:\n{report.get('summary', '无')}")
    print(f"✅ 详细的评审报告已保存至: {out_path}")
    print("="*50)


def _construct_queries_from_profile(profile: dict) -> list[dict]:
    """根据技术画像，智能推导 5-6 个合适的情报学检索查询词（复用 Phase 1 翻译逻辑）。"""
    queries = [
        {
            "nlp_terms": "post-hoc verification, audit",
            "qingbao_query": "情报分析 可信度 评估 后验 验证",
            "rationale": "生成后独立验证，情报学报上对应后验检验或可信度评估",
        },
        {
            "nlp_terms": "multi-agent, pipeline",
            "qingbao_query": "多智能体 情报 分析 协同 生成",
            "rationale": "多智能体协同流水线，对应情报分析协同机制",
        },
        {
            "nlp_terms": "RAG, retrieval, fact-checking",
            "qingbao_query": "检索增强 情报 事实验证 知识检索",
            "rationale": "检索和溯源，对应检索增强与事实审计",
        },
        {
            "nlp_terms": "AI content quality, credibility",
            "qingbao_query": "人工智能 生成 内容 质量 控制 可信",
            "rationale": "AI生成内容的质量控制与信任治理",
        },
        {
            "nlp_terms": "citation tracing, provenance",
            "qingbao_query": "引用 溯源 情报 分析 信息 来源",
            "rationale": "追踪到出处，对应文献引用溯源和可信源分析",
        }
    ]
    if "NLI verification" in profile.get("tech_stack", []) or "NLI" in str(profile):
        queries.append({
            "nlp_terms": "NLI, entailment, semantic",
            "qingbao_query": "语义 推理 蕴含 关系 验证 情报",
            "rationale": "语义推理关系匹配，对应语义蕴含验证"
        })
    return queries


def _format_paper_draft(data: dict) -> str:
    """将 Paper Generator 的输出格式化为 Markdown 文本。"""
    titles = "\n".join(f"- {t}" for t in data.get("title_suggestions", []))
    experiments = "\n".join(
        f"#### {i+1}. {exp.get('name')}\n- **合理性论证**: {exp.get('rationale')}\n- **对齐文献**: `{exp.get('paper_reference')}`"
        for i, exp in enumerate(data.get("suggested_experiments", []))
    )
    
    return f"""# 论文草稿与学术对齐生成报告

## 候选标题建议
{titles}

---

## 1. 引言 (Introduction)
{data.get("introduction", "未生成")}

---

## 2. 相关工作 (Related Work)
{data.get("related_work", "未生成")}

---

## 3. 方法论 (Methodology)
{data.get("methods", "未生成")}

---

## 4. 实验补齐建议与差距分析

### 4.1 情报学报同类实验差距分析
{data.get("experiment_gap_analysis", "未生成")}

### 4.2 建议补齐的对比实验列表
{experiments}
"""


def _format_review_report(data: dict) -> str:
    """将 Peer Reviewer 的输出格式化为 Markdown 评审意见书。"""
    terms = "\n".join(
        f"| {t.get('your_word')} | {t.get('suggested')} | {t.get('paper_evidence')} |"
        for t in data.get("terminology_issues", [])
    )
    structures = "\n".join(
        f"| {s.get('section')} | {s.get('issue')} | {s.get('peer_paper_comparison')} |"
        for s in data.get("structure_issues", [])
    )
    citations = "\n".join(
        f"- **应补引文献**: {c.get('should_cite')}\n  * **推荐理由**: {c.get('reason')}"
        for c in data.get("citation_gaps", [])
    )
    framing = "\n".join(f"- {f}" for f in data.get("contribution_framing_issues", []))

    return f"""# 《情报学报》同行评审意见报告

## 一、 总体审稿结论
**评估评级：** `{data.get('overall_assessment', '未知')}`

### 审稿总体摘要
{data.get('summary', '无')}

---

## 二、 术语规范审计意见
情报学报对学术规范术语有较高要求，请将原工程术语进行规范替换：

| 原始工程词汇 (Your Word) | 建议替换学术词汇 (Suggested) | 学报文献依据与例句 (Evidence) |
|---|---|---|
{terms}

---

## 三、 论文结构与布局评审意见
与同类录用文献布局结构比对结果如下：

| 章节板块 (Section) | 缺陷描述 (Issue) | 同行学报文献参考比对 (Comparison) |
|---|---|---|
{structures}

---

## 四、 参考文献补引建议
建议增加以下核心文献的评述和引用，以强化理论背景支撑：

{citations}

---

## 五、 学术贡献与研究定位重构建议
请纠正“仅描述搭建了一个工程系统/流水线”的工程叙事，重构为“解决情报学问题”：

{framing}
"""
