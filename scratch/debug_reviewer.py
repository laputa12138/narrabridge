import os
import json
import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# 设置环境配置
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:1878/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-27b-reasoning")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-ym-...2025")

def _trim_narrative_template(template: dict, max_terms: int = 50) -> dict:
    import copy
    trimmed = copy.deepcopy(template)
    if "terminology_mapping" in trimmed and isinstance(trimmed["terminology_mapping"], list):
        trimmed["terminology_mapping"] = trimmed["terminology_mapping"][:max_terms]
    return trimmed

def debug_reviewer_invocation():
    print("=== 开始 Peer Reviewer 详细调试 ===")
    
    # 1. 加载 paper_draft.md
    draft_path = Path("/home/yuanming/narrabridge/outputs/trust-eval/paper_draft.md")
    if not draft_path.exists():
        print("❌ 找不到 paper_draft.md")
        return
    draft_content = draft_path.read_text(encoding="utf-8")
    
    # 2. 构造 input
    dummy_draft = {
        "title_suggestions": ["科技创新弱信号感知的多智能体协同生成与后验检验方法研究"],
        "introduction": draft_content[:2000],
        "related_work": draft_content[2000:4000],
        "methods": draft_content[4000:],
        "suggested_experiments": []
    }
    
    # 加载叙事模板
    patterns_path = Path("/home/yuanming/narrabridge/outputs/trust-eval/narrative_patterns.json")
    narrative_template = {}
    if patterns_path.exists():
        narrative_template = json.loads(patterns_path.read_text(encoding="utf-8"))
        print("✅ 成功加载 narrative_patterns.json")
    
    input_rev = {
        "paper_draft": dummy_draft,
        "narrative_template": _trim_narrative_template(narrative_template, max_terms=50)
    }
    
    # 3. 准备 System Prompt
    prompt_path = Path("/home/yuanming/narrabridge/prompts/peer_reviewer.md")
    system_prompt = prompt_path.read_text(encoding="utf-8")
    
    # 尝试注入術語字典
    term_dict_path = Path("/home/yuanming/narrabridge/knowledge/terminology.yml")
    if term_dict_path.exists():
        with open(term_dict_path, "r", encoding="utf-8") as f:
            terms = yaml.safe_load(f)
        if terms:
            term_text = "\n\n## 行业术语及学术句式规范对照字典\n在阅读、重构、翻译与评审论文时，请遵循以下规范术语和学术表达映射：\n"
            for t in terms[:200]:
                term_text += f"- `{t.get('nlp_term')}` -> `{t.get('qingbao_term')}` ({t.get('rationale', '')})\n"
            system_prompt += term_text
            print("✅ 成功在 system prompt 中注入術語表")

    # 4. 加载 output schema
    schema_path = Path("/home/yuanming/narrabridge/schemas/agent_io.json")
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    raw_schema = schema_data["Agent5_PeerReviewer"]["output"]
    wrapped_schema = {
        "type": "object",
        "title": "Agent5_PeerReviewer_Output",
        "properties": raw_schema,
        "required": list(raw_schema.keys())
    }

    # 5. 实例化客户端
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2,
        max_tokens=4096,
        timeout=180
    )
    
    structured_llm = llm.with_structured_output(wrapped_schema, method="json_mode")
    
    print("\n--- 大模型输入 HumanMessage 数据展示 ---")
    print(json.dumps(input_rev, ensure_ascii=False, indent=2)[:1000] + "\n...已截断...")
    
    print("\n🚀 发起大模型评审调用...")
    try:
        res = structured_llm.invoke([
            SystemMessage(content=system_prompt + "\n\n请严格返回一个符合输出要求的 JSON 对象，绝对不要包含任何 Markdown 格式的包裹（如 ```json），也不要返回多余的说明文字。"),
            HumanMessage(content=f"输入数据如下：\n{json.dumps(input_rev, ensure_ascii=False)}")
        ])
        print("✅ 调用成功！")
        print("\n--- 大模型返回 JSON 数据展示 ---")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        
        # 写入临时文件供分析
        out_debug = Path("/home/yuanming/narrabridge/scratch/debug_reviewer_output.json")
        out_debug.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ 原始大模型输出已保存至: {out_debug}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_reviewer_invocation()
