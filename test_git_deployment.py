#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Git部署功能的脚本
验证新的git clone部署逻辑是否正常工作
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_git_executable():
    """测试Git可执行文件检测"""
    print("Testing Git executable detection...")
    
    try:
        from src.modules.deployment_core.base_deployer import BaseDeployer
        deployer = BaseDeployer()
        
        git_path = deployer.get_git_executable_path()
        if git_path:
            print(f"SUCCESS: Found Git executable: {git_path}")
            return True
        else:
            print("FAILED: Git executable not found")
            return False
    except Exception as e:
        print(f"ERROR: Failed to test Git executable: {e}")
        return False

def test_mirror_speed():
    """测试镜像站测速功能"""
    print("\nTesting mirror speed detection...")
    
    try:
        from src.modules.deployment_core.base_deployer import BaseDeployer
        deployer = BaseDeployer()
        
        # 测试GitHub镜像站
        success, response_time = deployer.test_mirror_speed("https://github.com", timeout=5)
        if success:
            print(f"SUCCESS: GitHub mirror response time: {response_time:.2f}s")
        else:
            print("FAILED: GitHub mirror connection failed")
        
        # 测试其他镜像站
        mirrors = [
            "https://ghproxy.com",
            "https://bgithub.xyz",
            "https://gitclone.com"
        ]
        
        for mirror in mirrors:
            success, response_time = deployer.test_mirror_speed(mirror, timeout=5)
            if success:
                print(f"SUCCESS: {mirror} response time: {response_time:.2f}s")
            else:
                print(f"FAILED: {mirror} connection failed")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to test mirror speed: {e}")
        return False

def test_git_clone_url():
    """测试Git clone URL生成"""
    print("\nTesting Git clone URL generation...")
    
    try:
        from src.modules.deployment_core.base_deployer import BaseDeployer
        deployer = BaseDeployer()
        
        # 测试不同的仓库
        repos = [
            "MaiM-with-u/MaiBot",
            "MoFox-Studio/MoFox-Core",
            "test/repo"
        ]
        
        for repo in repos:
            clone_url = deployer.get_git_clone_url(repo)
            print(f"SUCCESS: {repo} -> {clone_url}")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to test Git clone URL generation: {e}")
        return False

def test_config_loading():
    """测试配置加载"""
    print("\nTesting configuration loading...")
    
    try:
        from src.core.p_config import p_config_manager
        
        # 获取Git配置
        git_config = p_config_manager.get("git", {})
        if git_config:
            print("SUCCESS: Git configuration loaded")
            print(f"   Mirror count: {len(git_config.get('mirrors', []))}")
            print(f"   Auto select mirror: {git_config.get('auto_select_mirror', False)}")
            print(f"   Clone depth: {git_config.get('depth', 1)}")
            return True
        else:
            print("FAILED: Git configuration loading failed")
            return False
    except Exception as e:
        print(f"ERROR: Failed to test configuration loading: {e}")
        return False

def test_deployer_instantiation():
    """测试部署器实例化"""
    print("\nTesting deployer instantiation...")
    
    try:
        from src.modules.deployment_core.maibot_deployer import MaiBotDeployer
        from src.modules.deployment_core.mofox_deployer import MoFoxBotDeployer
        
        # 测试MaiBot部署器
        maibot_deployer = MaiBotDeployer()
        print("SUCCESS: MaiBot deployer instantiated")
        
        # 测试MoFox部署器
        mofox_deployer = MoFoxBotDeployer()
        print("SUCCESS: MoFox deployer instantiated")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to test deployer instantiation: {e}")
        return False

def main():
    """主测试函数"""
    print("Starting Git deployment functionality tests...")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Git Executable Detection", test_git_executable),
        ("Mirror Speed Testing", test_mirror_speed),
        ("Git Clone URL Generation", test_git_clone_url),
        ("Deployer Instantiation", test_deployer_instantiation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTest: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"PASS: {test_name}")
            else:
                print(f"FAIL: {test_name}")
        except Exception as e:
            print(f"ERROR: {test_name} - {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("SUCCESS: All tests passed! Git deployment functionality implemented successfully.")
        return True
    else:
        print("WARNING: Some tests failed, please check the functionality.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)