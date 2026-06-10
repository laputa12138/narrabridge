import os
from pathlib import Path

QINGBAO_MINERU_DIR = os.environ.get("QINGBAO_MINERU_DIR", os.path.expanduser("~/qingbao_search/mineru_output"))

# 全局缓存：将规范化后的标题映射到其对应的本地 qbxb md 文件路径
_title_to_file_map = None


def _build_title_map():
    """遍历本地所有 qbxb md 文件并根据第一行标题建立缓存。"""
    global _title_to_file_map
    if _title_to_file_map is not None:
        return
    
    _title_to_file_map = {}
    dir_path = Path(QINGBAO_MINERU_DIR)
    if not dir_path.exists():
        print(f"[paper_reader] 警告: mineru 目录不存在: {dir_path}")
        return

    # 扫描所有 qbxb_*.md 文件
    count = 0
    for path in dir_path.glob("qbxb_*.md"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#"):
                        # 提取标题并进行去标点和空格规范化
                        title = line.lstrip("#").strip()
                        if title:
                            norm_title = "".join(c for c in title if c.isalnum())
                            _title_to_file_map[norm_title] = path
                            count += 1
                            break
        except Exception as e:
            print(f"[paper_reader] 扫描文件 {path.name} 出错: {e}")
            continue
    print(f"[paper_reader] 已成功构建标题与本地文件映射映射表，共扫描到 {count} 篇有效文献。")


def get_paper_sections(paper_id: str, title: str = "") -> dict:
    """
    根据论文 ID 或标题读取其 minerU 输出的 markdown 全文，并自动提取引言和方法论章节。

    Args:
        paper_id: 情报学报论文ID
        title: 论文标题，若提供，当通过 ID 找不到文件时，将使用标题进行匹配
        
    Returns:
        包含 intro_excerpt (引言片段) 和 method_excerpt (方法片段) 的字典
    """
    pid = paper_id.replace(".md", "")
    mineru_path = Path(QINGBAO_MINERU_DIR) / f"{pid}.md"
    
    # 如果基于 ID 的文件不存在，但提供了标题，则尝试通过标题映射匹配
    if not mineru_path.exists() and title:
        _build_title_map()
        norm_title = "".join(c for c in title if c.isalnum())
        if norm_title in _title_to_file_map:
            mineru_path = _title_to_file_map[norm_title]
            print(f"[paper_reader] 成功将哈希 ID {pid} 和标题 '{title}' 关联映射至本地文献: {mineru_path.name}")

    result = {
        "id": pid,
        "intro_excerpt": "未找到引言",
        "method_excerpt": "未找到方法章节",
        "has_full_text": False
    }

    if mineru_path.exists():
        try:
            content = mineru_path.read_text(encoding="utf-8")
            # 提取引言片段
            intro = _extract_section(content, ["引言", "前言", "1.", "一、"])
            # 提取方法片段
            method = _extract_section(content, ["方法", "模型", "框架", "2.", "二、", "3.", "三、"])
            
            result["intro_excerpt"] = intro[:1500] if intro else "未找到引言"
            result["method_excerpt"] = method[:1500] if method else "未找到方法章节"
            result["has_full_text"] = True
        except Exception as e:
            print(f"[paper_reader] 读取论文 {mineru_path.name} 错误: {e}")
    else:
        print(f"[paper_reader] 找不到该论文的本地 md 全文文件 (ID: {pid}, 标题: {title})")

    return result


def _extract_section(content: str, patterns: list[str]) -> str:
    """在文本中根据关键词匹配并截取约3000字符的章节片段。"""
    for pat in patterns:
        idx = content.find(pat)
        if idx >= 0:
            return content[idx : idx + 3000]
    return ""

