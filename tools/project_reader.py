"""
tools/project_reader.py — Extract a structured technical profile from a codebase.

Reads AGENTS.md, README.md, key docs, and representative source files
to produce a TechProfile JSON conforming to schemas/agent_io.json.
"""

import os
import re
import json
from pathlib import Path
from typing import Optional


def extract_tech_profile(project_path: str) -> dict:
    """
    Extract a structured technical profile from a project directory.

    Args:
        project_path: Absolute path to the project root (e.g., ~/trust-eval)

    Returns:
        TechProfile dict matching Agent1_ProjectReader output schema
    """
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        return {"error": f"Project path does not exist: {root}"}

    profile = {
        "tech_stack": _extract_tech_stack(root),
        "core_innovation": _extract_innovation(root),
        "experimental_setup": _extract_experimental_setup(root),
        "existing_results": _extract_results(root),
        "modules": _extract_modules(root),
    }
    return profile


def _read_file(path: Path) -> str:
    """Read a file, return empty string on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_tech_stack(root: Path) -> list[str]:
    """Extract high-level technology categories from project docs."""
    stack = set()

    # Read AGENTS.md and README.md for tech stack mentions
    for fname in ["AGENTS.md", "README.md"]:
        content = _read_file(root / fname)
        if not content:
            continue

        lower = content.lower()

        # Check for technology patterns
        patterns = {
            "multi-agent": r"multi.?agent|多.?agent|多智能体",
            "RAG": r"\brag\b|retrieval.?augmented|检索增强",
            "LLM orchestration": r"orchestrat|编排|pipeline",
            "fact verification": r"fact.?verif|事实.?验证|atomic.?fact",
            "NLI verification": r"\bnli\b|entailment|蕴含",
            "citation tracking": r"citation.?track|引用.?追踪|溯源",
            "post-hoc audit": r"post.?hoc|posterior.?verif|后验|审计",
            "Reranker": r"rerank|重排",
            "embedding": r"embedding|向量化|embed",
            "document parsing": r"mineru|pdf.?pars|文档解析",
        }

        for label, pattern in patterns.items():
            if re.search(pattern, lower):
                stack.add(label)

    return sorted(stack)


def _extract_innovation(root: Path) -> str:
    """Extract the core innovation statement from project docs."""
    # Try AGENTS.md first — usually has a clear "核心思想" section
    content = _read_file(root / "AGENTS.md")
    if not content:
        content = _read_file(root / "README.md")

    if not content:
        return "未在文档中找到"

    # Look for innovation markers
    patterns = [
        r"核心思想[：:]\s*(.+?)(?:\n|$)",
        r"方法概述.*?\n(.+?)(?:\n\n|\n#)",
        r"## Method.*?\n(.+?)(?:\n\n|\n#)",
    ]

    for pat in patterns:
        match = re.search(pat, content, re.DOTALL)
        if match:
            return match.group(1).strip()[:300]

    return "未在文档中找到"


def _extract_experimental_setup(root: Path) -> dict:
    """Extract experimental configuration from project docs."""
    setup = {
        "dataset": "未在文档中找到",
        "dataset_size": 0,
        "topic": "未在文档中找到",
        "evaluation_metrics": [],
        "baseline": "未在文档中找到",
    }

    # Read AGENTS.md and docs for experiment info
    content = _read_file(root / "AGENTS.md")

    # Check docs directory
    docs_dir = root / "docs"
    if docs_dir.exists():
        for doc in sorted(docs_dir.glob("*.md")):
            if "方案" in doc.name or "实验" in doc.name or "plan" in doc.name.lower():
                content += "\n" + _read_file(doc)

    if not content:
        return setup

    # Dataset
    dataset_match = re.search(r"(?:dataset|数据)[：:]\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if dataset_match:
        setup["dataset"] = dataset_match.group(1).strip()
        # Try to extract size
        size_match = re.search(r"(\d+)\s*(?:份|篇|个|documents)", content)
        if size_match:
            setup["dataset_size"] = int(size_match.group(1))

    # Topic
    topic_match = re.search(r"(?:topic|主题|theme)[：:]\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if topic_match:
        setup["topic"] = topic_match.group(1).strip()

    # Evaluation metrics
    metric_patterns = [
        r"(?:指标|metric|score)[：:]\s*(.+?)(?:\n|$)",
        r"CSS",
        r"NLI",
        r"accuracy",
        r"citation accuracy",
    ]
    for pat in metric_patterns:
        for match in re.finditer(pat, content[-5000:], re.IGNORECASE):
            setup["evaluation_metrics"].append(match.group(0).strip())

    # Deduplicate
    setup["evaluation_metrics"] = list(dict.fromkeys(setup["evaluation_metrics"]))

    # Baseline
    baseline_match = re.search(r"(?:baseline|对照|基线)[：:]\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if baseline_match:
        setup["baseline"] = baseline_match.group(1).strip()

    return setup


def _extract_results(root: Path) -> str:
    """Extract existing results summary."""
    content = _read_file(root / "AGENTS.md")

    # Also check output directory for result files
    output_dir = root / "output"
    if output_dir.exists():
        result_files = list(output_dir.glob("*.md"))
        if result_files:
            content += "\n" + _read_file(result_files[0])[:2000]

    if not content:
        return "未在文档中找到"

    # Look for results section
    patterns = [
        r"(?:结果|result|成果|进展)[：:]\s*(.+?)(?:\n\n|\n#|\Z)",
        r"(?:##.*?结果.*?\n)(.+?)(?:\n##|\Z)",
    ]

    for pat in patterns:
        match = re.search(pat, content, re.DOTALL)
        if match:
            return match.group(1).strip()[:500]

    return "未在文档中找到"


def _extract_modules(root: Path) -> list[dict]:
    """Extract system module list from project structure."""
    modules = []

    # From AGENTS.md structure section
    agents_md = _read_file(root / "AGENTS.md")
    if not agents_md:
        agents_md = _read_file(root / "README.md")

    # Look for module listings in markdown tables or lists
    # Pattern: | module_name | purpose | ...
    table_pattern = r"\|\s*(?:`)?([a-zA-Z_][\w/._-]+)(?:`)?\s*\|\s*(.+?)\s*\|"
    for match in re.finditer(table_pattern, agents_md):
        name = match.group(1).strip()
        purpose = match.group(2).strip()
        if name and purpose and name not in ["---", "Module", "模块", "File", "文件"]:
            modules.append({"name": name, "purpose": purpose, "file": ""})

    # If no table found, scan for Python files in core/ and agents/
    if not modules:
        for subdir in ["core", "agents"]:
            subdir_path = root / subdir
            if subdir_path.exists():
                for py_file in sorted(subdir_path.glob("*.py")):
                    content = _read_file(py_file)
                    # Extract docstring
                    doc_match = re.search(r'"""(.+?)"""', content, re.DOTALL)
                    purpose = doc_match.group(1).strip().split("\n")[0] if doc_match else "未标注"
                    modules.append(
                        {
                            "name": py_file.stem,
                            "purpose": purpose[:200],
                            "file": str(py_file.relative_to(root)),
                        }
                    )

    return modules[:15]  # Cap at 15 modules


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/trust-eval")
    profile = extract_tech_profile(path)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
