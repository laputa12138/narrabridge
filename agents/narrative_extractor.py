import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

def get_agent():
    """
    创建并返回 Narrative Extractor 代理。负责从传入的文献文本章节（引言、方法等）中对比提取学术叙事。
    """
    # 读取系统提示词
    prompt_path = Path(__file__).parent.parent / "prompts" / "narrative_extractor.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 读取输出 JSON Schema
    schema_path = Path(__file__).parent.parent / "schemas" / "agent_io.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    output_schema = schema_data["Agent3_NarrativeExtractor"]["output"]

    # 创建大模型客户端
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2,
        max_tokens=4096
    )

    # 设为空 tools，由外部 Python 读取出段落内容后统一传入，避免大模型与文件系统的多轮 tool-calling 损耗
    agent = create_deep_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        name="narrative_extractor"
    )
    return agent
