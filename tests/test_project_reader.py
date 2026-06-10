import pytest
import os
from tools.project_reader import extract_tech_profile

def test_extract_tech_profile():
    """测试从项目目录提取技术画像的功能，验证各字段的结构和提取正确性。"""
    # 使用 trust-eval 作为测试目标
    project_path = os.path.expanduser("~/trust-eval")
    profile = extract_tech_profile(project_path)
    
    assert isinstance(profile, dict)
    assert "error" not in profile
    
    # 验证关键的画像指标
    assert "tech_stack" in profile
    assert isinstance(profile["tech_stack"], list)
    assert len(profile["tech_stack"]) > 0
    
    # 验证核心创新描述
    assert "core_innovation" in profile
    assert isinstance(profile["core_innovation"], str)
    
    # 验证模块列表
    assert "modules" in profile
    assert isinstance(profile["modules"], list)
    if len(profile["modules"]) > 0:
        for module in profile["modules"]:
            assert "name" in module
            assert "purpose" in module
