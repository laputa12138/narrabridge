"""
narrabridge/orchestrator.py — 5-agent pipeline powered by deepagents.

Phase 2 core. Uses deepagents features:
  ▸ `create_deep_agent` — create isolated agents with bounded context
  ▸ `FilesystemBackend` — each agent gets its own sandboxed workspace
  ▸ `subagents` — pre-configured delegation targets (Phase 2.8)
  ▸ Built-in context compression middleware — auto-summarizes long threads
  ▸ Built-in filesystem tools — agents can read/write outputs autonomously
  ▸ `interrupt_on` — human-in-the-loop for quality gates (Phase 2.8)

Pipeline:
  Agent 1 (Project Reader) → Agent 2 (Problem Mapper) → Agent 3 (Narrative Extractor)
                                                                  ↓
  Agent 4 (Paper Generator) ←──────────────────────────────────────┘
       ↓
  Agent 5 (Peer Reviewer)

Each agent runs sequentially. Agent N receives Agent N-1's output as input.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend


# ── Paths ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"

LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-27b-reasoning")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:1878/v1")
QINGBAO_MINERU_DIR = os.path.expanduser("~/qingbao_search/mineru_output")


# ── Tools ──────────────────────────────────────────────────────────────────

def search_qingbao(query: str, top_k: int = 5) -> str:
    """Search the 情报学报 knowledge base for papers matching a Chinese query.

    Use this to find papers about specific intelligence studies topics.
    Always translate NLP terms into intelligence studies terminology first.
    Example: 'multi-agent verification' → '多智能体 情报 验证'

    Args:
        query: Chinese search query
        top_k: Number of results (default 5)
    """
    from tools.opensearch_search import text_search

    results = text_search(query, top_k=top_k)
    if not results:
        return "No results found. Try different Chinese search terms."
    lines = [f"### Search: {query}\n"]
    for i, r in enumerate(results):
        lines.append(f"{i+1}. **{r['title']}** (id={r['id']}, score={r['score']:.2f})")
        lines.append(f"   {r['content_snippet'][:300]}")
    return "\n".join(lines)


def read_paper_section(paper_id: str, section: str = "intro") -> str:
    """Read a specific section from a paper's minerU output.

    Args:
        paper_id: Paper ID from 情报学报 (e.g., 'paper_001')
        section: 'intro' (引言), 'method' (方法), 'experiment' (实验), or 'full' (全文)
    """
    path = Path(QINGBAO_MINERU_DIR) / f"{paper_id}.md"
    if not path.exists():
        return f"Paper {paper_id} not found in minerU outputs."

    content = path.read_text(encoding="utf-8")
    if section == "full":
        return content[:8000]  # truncated for context management

    # Simple heuristic section extraction
    markers = {
        "intro": ["引言", "引言", "前言", "1.", "一、"],
        "method": ["方法", "模型", "框架", "2.", "二、", "3.", "三、"],
        "experiment": ["实验", "评估", "验证", "4.", "四、", "5.", "五、"],
    }
    for marker in markers.get(section, []):
        idx = content.find(marker)
        if idx >= 0:
            return content[idx : idx + 5000]
    return content[:2000]


# ── Agent Factory ──────────────────────────────────────────────────────────

def _load_prompt(filename: str) -> str:
    """Load a system prompt from prompts/."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _create_agent(
    name: str,
    prompt_file: str,
    tools: list,
    output_dir: Path,
) -> Any:
    """Create a deepagents agent with sandboxed filesystem and tools.

    deepagents features in use:
      - FilesystemBackend(virtual_mode=True, root_dir=...) →
          Agent's file operations are sandboxed to output_dir.
          Built-in tools: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`.
      - system_prompt → Loaded from prompts/*.md. This defines agent personality.
      - tools → Custom Python functions the agent can call via tool calling.
      - Context compression → Built-in middleware auto-summarizes when
          conversation gets too long. No config needed.

    Args:
        name: Agent name (for logging)
        prompt_file: Filename in prompts/ (e.g., 'project_reader.md')
        tools: List of callable functions
        output_dir: Sandbox root for this agent's files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    return create_deep_agent(
        # Model in "provider:model" format per deepagents convention
        model=f"openai:{LLM_MODEL}",
        # Custom model kwargs for our self-hosted vLLM
        # deepagents passes these through to langchain's init_chat_model
        tools=tools,
        system_prompt=_load_prompt(prompt_file),
        # Sandboxed filesystem: agent can only write inside output_dir
        backend=FilesystemBackend(
            root_dir=str(output_dir),
            virtual_mode=True,
        ),
        name=name,
        debug=False,
    )


def _invoke_agent(agent: Any, message: str) -> str:
    """Invoke a deepagents agent and extract the text response.

    deepagents returns a LangGraph CompiledStateGraph. We invoke it and
    extract the last AI message content.
    """
    result = agent.invoke({"messages": [{"role": "user", "content": message}]})
    # Extract the last message from the agent's response
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        # Handle LangChain message objects
        if hasattr(last_msg, "content"):
            return str(last_msg.content)
        if isinstance(last_msg, dict):
            return last_msg.get("content", str(last_msg))
    return str(result)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from agent text output."""
    # Try ```json ... ``` block first
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try bare JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return {"raw": text[:500]}


# ── Pipeline ───────────────────────────────────────────────────────────────


def run_pipeline(project_path: str, session_id: Optional[str] = None) -> dict:
    """Run the full 5-agent translation pipeline.

    Returns dict with keys: tech_profile, problem_mapping, narrative_template,
    paper_draft, review_report, session_dir.
    """
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    project_name = Path(project_path).expanduser().name
    session_dir = OUTPUTS_DIR / project_name / session_id

    outs: dict[str, Any] = {"session_dir": str(session_dir)}

    # ── Agent 1: Project Reader ────────────────────────────────────────
    a1 = _create_agent("reader", "project_reader.md", [], session_dir / "01_reader")
    text1 = _invoke_agent(a1, f"请分析项目 {project_path}，将技术画像写入 tech_profile.json。")
    outs["tech_profile"] = _extract_json(text1)
    print(f"  ✅ Agent 1: {json.dumps(outs['tech_profile'], ensure_ascii=False)[:200]}")

    # ── Agent 2: Problem Mapper ────────────────────────────────────────
    a2 = _create_agent(
        "mapper", "problem_mapper.md",
        [search_qingbao, read_paper_section],
        session_dir / "02_mapper",
    )
    text2 = _invoke_agent(
        a2,
        f"""请将以下技术画像映射到情报学问题类型，检索OpenSearch找到相关论文。

技术画像:
```json
{json.dumps(outs['tech_profile'], ensure_ascii=False, indent=2)}
```

请将问题映射结果写入 problem_mapping.json。""",
    )
    outs["problem_mapping"] = _extract_json(text2)
    n_papers = len(outs["problem_mapping"].get("top_papers", []))
    print(f"  ✅ Agent 2: {n_papers} papers matched")

    # ── Agent 3: Narrative Extractor ───────────────────────────────────
    a3 = _create_agent(
        "extractor", "narrative_extractor.md",
        [search_qingbao, read_paper_section],
        session_dir / "03_extractor",
    )
    text3 = _invoke_agent(
        a3,
        f"""请分析以下论文的叙事模式，提取术语对照和实验规范。

相关论文:
```json
{json.dumps(outs['problem_mapping'].get('top_papers', []), ensure_ascii=False, indent=2)}
```

使用 read_paper_section 工具逐篇读取引言和方法章节。
将结果写入 narrative_template.json。""",
    )
    outs["narrative_template"] = _extract_json(text3)
    print(f"  ✅ Agent 3: narrative template extracted")

    # ── Agent 4: Paper Generator ───────────────────────────────────────
    a4 = _create_agent(
        "generator", "paper_generator.md",
        [],  # Generator only needs LLM reasoning
        session_dir / "04_generator",
    )
    text4 = _invoke_agent(
        a4,
        f"""请生成情报学报风格论文初稿。

输入:
1. 技术画像: {json.dumps(outs['tech_profile'], ensure_ascii=False)}
2. 问题类型: {json.dumps(outs['problem_mapping'], ensure_ascii=False)[:2000]}
3. 叙事模板: {json.dumps(outs['narrative_template'], ensure_ascii=False)[:2000]}

请写入 paper_draft.md。""",
    )
    outs["paper_draft"] = text4
    print(f"  ✅ Agent 4: {len(text4)} chars")

    # ── Agent 5: Peer Reviewer ─────────────────────────────────────────
    a5 = _create_agent(
        "reviewer", "peer_reviewer.md",
        [],  # Reviewer only analyzes the draft
        session_dir / "05_reviewer",
    )
    text5 = _invoke_agent(
        a5,
        f"""请审阅以下论文初稿。

论文草稿:
{text4}

叙事规范:
```json
{json.dumps(outs['narrative_template'], ensure_ascii=False)[:2000]}
```

请写入 review_report.md。""",
    )
    outs["review_report"] = text5
    print(f"  ✅ Agent 5: {len(text5)} chars")

    # ── Summary ────────────────────────────────────────────────────────
    summary = (
        f"# NarraBridge Pipeline — {project_name}\n"
        f"- Session: {session_id}\n"
        f"- Problem type: {outs['problem_mapping'].get('problem_type', 'N/A')}\n"
        f"- Papers found: {n_papers}\n"
        f"- All outputs: {session_dir}\n"
    )
    (session_dir / "SUMMARY.md").write_text(summary)
    print(f"\n📂 {session_dir}")
    return outs


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python narrabridge/orchestrator.py <project_path>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
