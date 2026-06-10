import pytest
import os
from tools.opensearch_search import index_health, text_search, hybrid_search

# 设置环境变量，确保连接到本地OpenSearch
os.environ["OPENSEARCH_HOST"] = "127.0.0.1"
os.environ["OPENSEARCH_PORT"] = "9202"
os.environ["QINGBAO_INDEX"] = "情报学报"

def test_index_health():
    """测试 OpenSearch 索引的健康状况接口。"""
    health = index_health()
    assert health["status"] == "ok"
    assert health["doc_count"] > 0
    assert "size_mb" in health

def test_text_search():
    """测试文本检索（BM25）功能，验证返回结果的结构和字段。"""
    results = text_search("情报分析", top_k=3)
    assert isinstance(results, list)
    # 如果检索到了结果，验证每个结果包含必要的字段
    if len(results) > 0:
        for item in results:
            assert "id" in item
            assert "title" in item
            assert "score" in item
            assert "content_snippet" in item

def test_hybrid_search_fallback():
    """测试混合检索，当 embedding 为 None 时应该自动退化为文本检索。"""
    results = hybrid_search("人工智能", embedding=None, top_k=3)
    assert isinstance(results, list)
    if len(results) > 0:
        for item in results:
            assert "id" in item
            assert "title" in item
