import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

def get_agent():
    """
    创建并返回 Peer Reviewer 代理。该代理模拟情报学报审稿人，对论文草稿的学术规范性、结构及引用缺陷进行详细评估。
    """
    # 读取系统提示词
    prompt_path = Path(__file__).parent.parent / "prompts" / "peer_reviewer.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 读取输出 JSON Schema
    schema_path = Path(__file__).parent.parent / "schemas" / "agent_io.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    output_schema = schema_data["Agent5_PeerReviewer"]["output"]

    # 创建大模型客户端
    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.2
    )

    # 实例化无特殊工具的审阅评估 Agent
    agent = create_deep_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        name="peer_reviewer"
    )
    return agent
