#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多开启动功能测试脚本
用于测试端口管理器和多开管理器的功能
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.multi_launch import (
    PortManager, 
    ConfigPortReplacer, 
    MultiLaunchManager
)
import structlog

logger = structlog.get_logger(__name__)


def test_port_manager():
    """测试端口管理器"""
    print("=" * 50)
    print("测试 PortManager")
    print("=" * 50)
    
    pm = PortManager()
    
    # 测试1: 获取单个可用端口
    print("\n测试1: 获取单个可用端口")
    try:
        port = pm.get_available_port(preferred_port=8000)
        print(f"✅ 成功获取端口: {port}")
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
    
    # 测试2: 获取多个端口
    print("\n测试2: 获取多个实例的端口")
    try:
        ports = pm.get_ports_for_instances(count=3, base_port=8000)
        print(f"✅ 成功获取端口列表: {ports}")
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
    
    # 测试3: 检查端口可用性
    print("\n测试3: 检查端口可用性")
    try:
        available = pm._is_port_available(8000)
        print(f"✅ 端口 8000 可用性: {available}")
    except Exception as e:
        print(f"❌ 失败: {str(e)}")


def test_config_port_replacer():
    """测试配置文件端口替换器"""
    print("\n" + "=" * 50)
    print("测试 ConfigPortReplacer")
    print("=" * 50)
    
    replacer = ConfigPortReplacer()
    
    # 创建测试TOML文件
    test_toml_content = """
[bot]
port = 8000
listen_port = 8001
nickname = "TestBot"
"""
    
    test_file = "/tmp/test_config.toml"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_toml_content)
    
    print("\n测试1: 替换TOML文件中的端口")
    try:
        success = replacer.replace_ports_in_config(test_file, 9000, "toml")
        if success:
            with open(test_file, 'r') as f:
                content = f.read()
            if "9000" in content:
                print(f"✅ 成功替换端口到9000")
                print(f"修改后的内容:\n{content}")
            else:
                print(f"❌ 端口替换失败")
        else:
            print(f"❌ 替换返回失败")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


def test_multi_launch_manager():
    """测试多开启动管理器"""
    print("\n" + "=" * 50)
    print("测试 MultiLaunchManager")
    print("=" * 50)
    
    mlm = MultiLaunchManager()
    
    # 测试1: 注册实例
    print("\n测试1: 注册实例")
    try:
        success = mlm.register_instance(
            instance_name="test_bot_01",
            bot_path="/path/to/bot",
            config_name="test_config_01",
            base_port=8000
        )
        if success:
            print(f"✅ 成功注册实例 test_bot_01")
            instance = mlm.get_instance_info("test_bot_01")
            print(f"   分配的端口: {instance['allocated_port']}")
        else:
            print(f"❌ 注册失败")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    
    # 测试2: 注册多个实例
    print("\n测试2: 注册多个实例")
    try:
        for i in range(2, 4):
            success = mlm.register_instance(
                instance_name=f"test_bot_{i:02d}",
                bot_path="/path/to/bot",
                config_name=f"test_config_{i:02d}",
                base_port=8000 + i * 10
            )
            if success:
                print(f"✅ 成功注册实例 test_bot_{i:02d}")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    
    # 测试3: 获取所有实例
    print("\n测试3: 获取所有已注册的实例")
    try:
        all_instances = mlm.get_all_instances()
        print(f"✅ 获取到 {len(all_instances)} 个实例:")
        for name, info in all_instances.items():
            print(f"   • {name}: 端口 {info['allocated_port']}, 状态 {info['status']}")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    
    # 测试4: 取消注册实例
    print("\n测试4: 取消注册实例")
    try:
        success = mlm.unregister_instance("test_bot_01")
        if success:
            print(f"✅ 成功取消注册 test_bot_01")
            remaining = mlm.get_all_instances()
            print(f"   剩余 {len(remaining)} 个实例")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 48 + "╗")
    print("║" + " " * 10 + "多开启动功能测试" + " " * 20 + "║")
    print("╚" + "=" * 48 + "╝")
    
    try:
        test_port_manager()
        test_config_port_replacer()
        test_multi_launch_manager()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试过程出现异常: {str(e)}")
        logger.error("测试异常", error=str(e))
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
