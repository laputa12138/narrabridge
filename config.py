import os

# 大模型接口配置 (修改为 LiteLLM 网关，避免 8000 原生端口在 with_structured_output 中的挂起问题)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:1878/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-27b-reasoning")
# LiteLLM 接口需要的密钥鉴权
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-ym-...2025")

# OpenSearch配置
OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "127.0.0.1")
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", "9202"))
QINGBAO_INDEX = os.environ.get("QINGBAO_INDEX", "情报学报")

# 文献解析目录
QINGBAO_MINERU_DIR = os.environ.get("QINGBAO_MINERU_DIR", os.path.expanduser("~/qingbao_search/mineru_output"))
