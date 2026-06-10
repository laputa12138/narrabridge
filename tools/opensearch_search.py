"""
tools/opensearch_search.py — Query the 情报学报 OpenSearch index.

Hybrid search: BM25 (keyword) + k-NN (vector, 1024-dim).
"""

import os
import json
from typing import Optional

from opensearchpy import OpenSearch, exceptions


# ── Configuration ──────────────────────────────────────────────────────────

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "127.0.0.1")
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", "9202"))
QINGBAO_INDEX = os.environ.get("QINGBAO_INDEX", "情报学报")


# ── Client ─────────────────────────────────────────────────────────────────

_client: Optional[OpenSearch] = None


def get_client() -> OpenSearch:
    """Lazy-init OpenSearch client. Thread-safe for read operations."""
    global _client
    if _client is None:
        _client = OpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            use_ssl=False,
            verify_certs=False,
            timeout=30,
            max_retries=2,
            retry_on_timeout=True,
        )
    return _client


# ── Search ─────────────────────────────────────────────────────────────────


def text_search(query: str, top_k: int = 10) -> list[dict]:
    """
    BM25 full-text search on the 情报学报 index.

    Args:
        query: Chinese search query, e.g., "情报分析 可信度 评估"
        top_k: Number of results to return

    Returns:
        List of dicts with keys: id, title, score, content_snippet
    """
    client = get_client()
    try:
        result = client.search(
            index=QINGBAO_INDEX,
            body={
                "query": {
                    "match": {
                        "content": {
                            "query": query,
                            "operator": "or",
                        }
                    }
                },
                "size": top_k,
                "_source": ["id", "title", "content", "keywords"],
                "highlight": {
                    "fields": {
                        "content": {"fragment_size": 200, "number_of_fragments": 3}
                    }
                },
            },
        )
        return _format_results(result, top_k)
    except exceptions.OpenSearchException as e:
        print(f"[opensearch_search] Error: {e}")
        return []


def vector_search(embedding: list[float], top_k: int = 10) -> list[dict]:
    """
    k-NN vector search using the embedding field (1024-dim).

    Args:
        embedding: 1024-dim vector (from Qwen3-Embedding-0.6B or similar)
        top_k: Number of results

    Returns:
        List of dicts with keys: id, title, score, content_snippet
    """
    client = get_client()
    try:
        result = client.search(
            index=QINGBAO_INDEX,
            body={
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": embedding,
                            "k": top_k,
                        }
                    }
                },
                "_source": ["id", "title", "content", "keywords"],
            },
        )
        return _format_results(result, top_k)
    except exceptions.OpenSearchException as e:
        print(f"[opensearch_search] Error: {e}")
        return []


def hybrid_search(
    query: str,
    embedding: Optional[list[float]] = None,
    top_k: int = 10,
    text_weight: float = 0.3,
    vector_weight: float = 0.7,
) -> list[dict]:
    """
    Hybrid BM25 + k-NN search. Falls back to text-only if no embedding provided.

    Args:
        query: Chinese search query
        embedding: Optional 1024-dim vector. If None, text-only search.
        top_k: Number of results
        text_weight: BM25 score weight
        vector_weight: k-NN score weight

    Returns:
        Combined and re-ranked results
    """
    text_results = text_search(query, top_k=top_k * 2)

    if embedding is None:
        return text_results[:top_k]

    vector_results = vector_search(embedding, top_k=top_k * 2)

    # Simple score fusion: normalize and merge
    combined = {}
    for r in text_results:
        combined[r["id"]] = {"doc": r, "score": r["score"] * text_weight}

    for r in vector_results:
        score = r["score"] * vector_weight
        if r["id"] in combined:
            combined[r["id"]]["score"] += score
        else:
            combined[r["id"]] = {"doc": r, "score": score}

    ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in ranked[:top_k]]


# ── Helpers ────────────────────────────────────────────────────────────────


def _format_results(raw_result: dict, top_k: int) -> list[dict]:
    """Extract and format search results from OpenSearch response."""
    hits = raw_result.get("hits", {}).get("hits", [])
    results = []
    for hit in hits[:top_k]:
        source = hit.get("_source", {})
        results.append(
            {
                "id": source.get("id", ""),
                "title": source.get("title", ""),
                "score": hit.get("_score", 0.0),
                "content_snippet": _extract_snippet(source, hit),
                "keywords": source.get("keywords", []),
            }
        )
    return results


def _extract_snippet(source: dict, hit: dict) -> str:
    """Extract a readable snippet from content or highlight."""
    highlight = hit.get("highlight", {}).get("content", [])
    if highlight:
        return " ... ".join(highlight)[:500]
    content = source.get("content", "")
    return content[:500] if content else ""


# ── Index Health ───────────────────────────────────────────────────────────


def index_health() -> dict:
    """Check if the 情报学报 index is accessible and report document count."""
    client = get_client()
    try:
        stats = client.indices.stats(index=QINGBAO_INDEX)
        count = client.count(index=QINGBAO_INDEX)
        return {
            "status": "ok",
            "index": QINGBAO_INDEX,
            "doc_count": count.get("count", 0),
            "size_mb": stats["indices"][QINGBAO_INDEX]["total"]["store"]["size_in_bytes"]
            / (1024 * 1024),
        }
    except exceptions.OpenSearchException as e:
        return {"status": "error", "message": str(e)}


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print(json.dumps(index_health(), ensure_ascii=False, indent=2))

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\nSearching: {query}")
        results = text_search(query, top_k=5)
        for i, r in enumerate(results):
            print(f"\n[{i+1}] {r['title']} (score={r['score']:.2f})")
            print(f"    ID: {r['id']}")
            print(f"    {r['content_snippet'][:200]}...")
