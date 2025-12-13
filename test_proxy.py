"""
快速测试代理功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.proxy_manager import proxy_manager
from src.core.p_config import p_config_manager


def main():
    print("="*60)
    print("网络代理功能测试")
    print("="*60)
    
    # 1. 检查配置加载
    print("\n[1/5] 检查配置文件...")
    try:
        config = p_config_manager.config
        if 'network' in config and 'proxy' in config['network']:
            print("✓ 代理配置已加载")
        else:
            print("✓ 使用默认代理配置")
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return
    
    # 2. 检查代理管理器
    print("\n[2/5] 检查代理管理器...")
    try:
        is_enabled = proxy_manager.is_enabled()
        print(f"✓ 代理管理器正常，当前状态: {'已启用' if is_enabled else '未启用'}")
    except Exception as e:
        print(f"✗ 代理管理器错误: {e}")
        return
    
    # 3. 获取代理信息
    print("\n[3/5] 获取代理信息...")
    try:
        proxy_info = proxy_manager.get_proxy_info()
        print(f"✓ 代理信息:")
        print(f"  - 启用状态: {proxy_info['enabled']}")
        print(f"  - 代理类型: {proxy_info['type']}")
        print(f"  - 主机地址: {proxy_info['host'] or '(未设置)'}")
        print(f"  - 端口号: {proxy_info['port'] or '(未设置)'}")
        print(f"  - 用户名: {proxy_info['username'] or '(未设置)'}")
        print(f"  - 密码: {'已设置' if proxy_info['has_password'] else '(未设置)'}")
        print(f"  - 排除主机: {proxy_info['exclude_hosts']}")
        if proxy_info['proxy_url']:
            print(f"  - 代理URL: {proxy_info['proxy_url'].split('@')[-1]}...")  # 隐藏认证信息
    except Exception as e:
        print(f"✗ 获取代理信息失败: {e}")
        return
    
    # 4. 测试代理字典生成
    print("\n[4/5] 测试代理字典生成...")
    try:
        proxies = proxy_manager.get_proxies_dict()
        if proxies:
            print(f"✓ 代理字典已生成:")
            for key, value in proxies.items():
                # 隐藏认证信息
                display_value = value.split('@')[-1] if '@' in value else value
                print(f"  - {key}: {display_value}")
        else:
            print("✓ 代理未启用，返回 None")
    except Exception as e:
        print(f"✗ 生成代理字典失败: {e}")
    
    # 5. 测试连接（仅在代理启用时）
    if proxy_manager.is_enabled():
        print("\n[5/5] 测试代理连接...")
        print("正在测试连接（可能需要几秒钟）...")
        try:
            result = proxy_manager.test_connection('https://www.baidu.com')
            if result['success']:
                print(f"✓ {result['message']}")
            else:
                print(f"✗ {result['message']}")
        except Exception as e:
            print(f"✗ 测试连接时出错: {e}")
    else:
        print("\n[5/5] 跳过连接测试（代理未启用）")
    
    # 总结
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    
    if not proxy_manager.is_enabled():
        print("\n💡 提示：代理当前未启用")
        print("   要启用代理，请:")
        print("   1. 运行配置 UI 并在设置中配置代理")
        print("   2. 或直接编辑 config/P-config.toml 文件")
    else:
        print("\n✓ 代理已启用并可正常使用")
    
    print("\n📖 详细使用说明请查看: PROXY_USAGE.md")
    print("💻 使用示例请查看: src/utils/proxy_usage_example.py")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
    except Exception as e:
        print(f"\n\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
