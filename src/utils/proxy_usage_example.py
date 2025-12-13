"""
网络代理使用示例
展示如何在程序中使用代理功能
"""
import requests
from src.utils.proxy_manager import proxy_manager


def example_1_basic_usage():
    """示例1: 基本使用 - 检查代理是否启用"""
    print("=== 示例1: 检查代理状态 ===")
    
    if proxy_manager.is_enabled():
        print("✓ 代理已启用")
        proxy_info = proxy_manager.get_proxy_info()
        print(f"  类型: {proxy_info['type']}")
        print(f"  地址: {proxy_info['host']}:{proxy_info['port']}")
    else:
        print("✗ 代理未启用")


def example_2_requests_library():
    """示例2: 在 requests 库中使用代理"""
    print("\n=== 示例2: requests 库使用代理 ===")
    
    # 获取代理字典（如果代理未启用则返回 None）
    proxies = proxy_manager.get_proxies_dict()
    
    try:
        # 发起请求，如果代理启用则会自动使用
        response = requests.get(
            'https://api.github.com',
            proxies=proxies,
            timeout=10
        )
        print(f"✓ 请求成功，状态码: {response.status_code}")
        
    except requests.exceptions.ProxyError:
        print("✗ 代理连接失败")
    except Exception as e:
        print(f"✗ 请求失败: {e}")


def example_3_environment_variables():
    """示例3: 通过环境变量使用代理"""
    print("\n=== 示例3: 环境变量方式 ===")
    
    # 应用到环境变量（很多库会自动读取这些环境变量）
    success = proxy_manager.apply_to_environment()
    
    if success:
        print("✓ 代理环境变量已设置")
        # 之后使用 requests 等库时会自动使用环境变量中的代理
        # 无需手动传递 proxies 参数
    else:
        print("✗ 设置环境变量失败")


def example_4_test_connection():
    """示例4: 测试代理连接"""
    print("\n=== 示例4: 测试代理连接 ===")
    
    result = proxy_manager.test_connection('https://www.baidu.com')
    
    if result['success']:
        print(f"✓ {result['message']}")
    else:
        print(f"✗ {result['message']}")


def example_5_update_proxy():
    """示例5: 程序化更新代理配置"""
    print("\n=== 示例5: 更新代理配置 ===")
    
    # 启用代理
    success = proxy_manager.update_config(
        enabled=True,
        type='http',
        host='127.0.0.1',
        port='7890',
        username='',
        password='',
        exclude_hosts='localhost,127.0.0.1,*.local'
    )
    
    if success:
        print("✓ 代理配置已更新")
    else:
        print("✗ 更新配置失败")


def example_6_conditional_proxy():
    """示例6: 条件性使用代理"""
    print("\n=== 示例6: 条件性使用代理 ===")
    
    def make_request(url: str, use_proxy: bool = True):
        """
        发起请求，可选择是否使用代理
        
        Args:
            url: 目标URL
            use_proxy: 是否使用代理（即使代理已启用）
        """
        proxies = None
        if use_proxy and proxy_manager.is_enabled():
            proxies = proxy_manager.get_proxies_dict()
        
        try:
            response = requests.get(url, proxies=proxies, timeout=10)
            return response
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    # 使用代理
    print("使用代理访问...")
    make_request('https://api.github.com', use_proxy=True)
    
    # 不使用代理
    print("不使用代理访问...")
    make_request('https://api.github.com', use_proxy=False)


def example_7_download_with_proxy():
    """示例7: 使用代理下载文件"""
    print("\n=== 示例7: 使用代理下载文件 ===")
    
    proxies = proxy_manager.get_proxies_dict()
    
    try:
        url = 'https://www.python.org/static/img/python-logo.png'
        response = requests.get(url, proxies=proxies, stream=True, timeout=30)
        
        if response.status_code == 200:
            # 这里只是示例，实际使用时应该保存到文件
            content_length = len(response.content)
            print(f"✓ 下载成功，文件大小: {content_length} 字节")
        else:
            print(f"✗ 下载失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"✗ 下载失败: {e}")


if __name__ == '__main__':
    """运行所有示例"""
    print("网络代理使用示例\n" + "="*50)
    
    example_1_basic_usage()
    example_2_requests_library()
    example_3_environment_variables()
    example_4_test_connection()
    # example_5_update_proxy()  # 取消注释以测试更新配置
    example_6_conditional_proxy()
    example_7_download_with_proxy()
    
    print("\n" + "="*50)
    print("所有示例执行完毕")
