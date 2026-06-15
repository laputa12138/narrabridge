import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

def get_agent():
    """
    创建并返回 Project Reader 代理。负责梳理技术画像并确保其严格符合输出格式契约。
    """
    # 读取系统提示词
    prompt_path = Path(__file__).parent.parent / "prompts" / "project_reader.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 读取输出 JSON Schema
    schema_path = Path(__file__).parent.parent / "schemas" / "agent_io.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    output_schema = schema_data["Agent1_ProjectReader"]["output"]

    # 创建大模型客户端，设置超时，防止意外挂起
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2,
        max_tokens=4096
    )

    # 实例化无特殊工具的纯生成式 Agent，避免大模型 tool-calling 死循环
    agent = create_deep_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        name="project_reader"
    )
    return agent
