import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

def get_agent():
    """
    创建并返回 Problem Mapper 代理。负责根据传入的技术画像和候选文献结果，建立学术对应关系。
    """
    # 读取系统提示词
    prompt_path = Path(__file__).parent.parent / "prompts" / "problem_mapper.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 读取输出 JSON Schema
    schema_path = Path(__file__).parent.parent / "schemas" / "agent_io.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    output_schema = schema_data["Agent2_ProblemMapper"]["output"]

    # 创建大模型客户端
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2,
        max_tokens=4096
    )

    # 设为空 tools，由外部 Python 预先检索出文献后喂给大模型，防止大模型做多次检索连接而产生延迟或挂起
    agent = create_deep_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        name="problem_mapper"
    )
    return agent
