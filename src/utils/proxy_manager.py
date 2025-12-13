"""
网络代理管理模块
负责处理HTTP/HTTPS/SOCKS代理配置和应用
"""
import os
import structlog
from typing import Dict, Optional, Any
from src.core.p_config import p_config_manager

logger = structlog.get_logger(__name__)


class ProxyManager:
    """代理管理类，用于处理网络代理设置"""

    def __init__(self):
        self.config = p_config_manager

    def get_proxy_config(self) -> Dict[str, Any]:
        """获取代理配置"""
        return self.config.get_proxy_config()

    def is_enabled(self) -> bool:
        """检查代理是否启用"""
        return self.config.is_proxy_enabled()

    def get_proxy_url(self) -> Optional[str]:
        """
        构建代理URL
        返回格式: protocol://[username:password@]host:port
        """
        proxy_cfg = self.get_proxy_config()
        
        if not proxy_cfg.get('enabled', False):
            return None
        
        proxy_type = proxy_cfg.get('type', 'http')
        host = proxy_cfg.get('host', '').strip()
        port = proxy_cfg.get('port', '').strip()
        username = proxy_cfg.get('username', '').strip()
        password = proxy_cfg.get('password', '').strip()

        if not host or not port:
            logger.warning("代理配置不完整，缺少主机或端口")
            return None

        # 构建认证信息
        auth = ''
        if username:
            if password:
                auth = f"{username}:{password}@"
            else:
                auth = f"{username}@"

        # 构建代理URL
        if proxy_type.lower() in ['socks4', 'socks5']:
            protocol = proxy_type.lower()
        elif proxy_type.lower() == 'https':
            protocol = 'https'
        else:
            protocol = 'http'

        proxy_url = f"{protocol}://{auth}{host}:{port}"
        return proxy_url

    def get_proxies_dict(self) -> Optional[Dict[str, str]]:
        """
        获取适用于 requests 库的代理字典
        返回格式: {'http': proxy_url, 'https': proxy_url}
        """
        if not self.is_enabled():
            return None

        proxy_url = self.get_proxy_url()
        if not proxy_url:
            return None

        proxy_cfg = self.get_proxy_config()
        proxy_type = proxy_cfg.get('type', 'http')

        # 对于 SOCKS 代理，需要同时设置 http 和 https
        if proxy_type.lower() in ['socks4', 'socks5']:
            return {
                'http': proxy_url,
                'https': proxy_url
            }
        else:
            # HTTP/HTTPS 代理
            return {
                'http': proxy_url,
                'https': proxy_url
            }

    def apply_to_environment(self) -> bool:
        """
        将代理设置应用到系统环境变量
        设置 HTTP_PROXY、HTTPS_PROXY、NO_PROXY
        """
        try:
            if not self.is_enabled():
                # 清除代理环境变量
                for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 
                           'http_proxy', 'https_proxy', 'no_proxy']:
                    if key in os.environ:
                        del os.environ[key]
                logger.info("已清除代理环境变量")
                return True

            proxy_url = self.get_proxy_url()
            if not proxy_url:
                logger.warning("无法生成代理URL，跳过环境变量设置")
                return False

            proxy_cfg = self.get_proxy_config()
            exclude_hosts = proxy_cfg.get('exclude_hosts', 'localhost,127.0.0.1')

            # 设置环境变量（同时设置大小写版本以确保兼容性）
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            os.environ['http_proxy'] = proxy_url
            os.environ['https_proxy'] = proxy_url
            
            if exclude_hosts:
                os.environ['NO_PROXY'] = exclude_hosts
                os.environ['no_proxy'] = exclude_hosts

            logger.info(
                "代理环境变量已设置",
                proxy_type=proxy_cfg.get('type'),
                host=proxy_cfg.get('host'),
                port=proxy_cfg.get('port')
            )
            return True

        except Exception as e:
            logger.error("设置代理环境变量失败", error=str(e))
            return False

    def test_connection(self, test_url: str = "https://www.baidu.com") -> Dict[str, Any]:
        """
        测试代理连接
        
        Args:
            test_url: 测试用的URL
            
        Returns:
            包含测试结果的字典
        """
        try:
            import requests
            from datetime import datetime

            start_time = datetime.now()
            
            if self.is_enabled():
                proxies = self.get_proxies_dict()
                response = requests.get(
                    test_url, 
                    proxies=proxies, 
                    timeout=10,
                    verify=True
                )
            else:
                response = requests.get(test_url, timeout=10)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                'success': True,
                'status_code': response.status_code,
                'duration': duration,
                'message': f'连接成功 (耗时: {duration:.2f}秒)'
            }

        except requests.exceptions.ProxyError as e:
            logger.error("代理连接失败", error=str(e))
            return {
                'success': False,
                'error': 'ProxyError',
                'message': f'代理连接失败: {str(e)}'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout',
                'message': '连接超时'
            }
        except requests.exceptions.RequestException as e:
            logger.error("网络请求失败", error=str(e))
            return {
                'success': False,
                'error': 'RequestException',
                'message': f'请求失败: {str(e)}'
            }
        except Exception as e:
            logger.error("测试代理时发生未知错误", error=str(e))
            return {
                'success': False,
                'error': 'Unknown',
                'message': f'未知错误: {str(e)}'
            }

    def update_config(self, **kwargs) -> bool:
        """
        更新代理配置
        
        Args:
            enabled: 是否启用代理
            type: 代理类型 (http/https/socks5/socks4)
            host: 代理主机地址
            port: 代理端口
            username: 用户名（可选）
            password: 密码（可选）
            exclude_hosts: 不使用代理的主机列表
            
        Returns:
            是否保存成功
        """
        try:
            for key, value in kwargs.items():
                config_key = f"network.proxy.{key}"
                self.config.set(config_key, value)
            
            success = self.config.save()
            
            if success:
                logger.info("代理配置已更新", **kwargs)
                # 如果代理启用，立即应用到环境变量
                if kwargs.get('enabled', self.is_enabled()):
                    self.apply_to_environment()
            
            return success
            
        except Exception as e:
            logger.error("更新代理配置失败", error=str(e))
            return False

    def get_proxy_info(self) -> Dict[str, Any]:
        """
        获取代理信息摘要（不包含密码）
        
        Returns:
            代理信息字典
        """
        proxy_cfg = self.get_proxy_config()
        
        return {
            'enabled': proxy_cfg.get('enabled', False),
            'type': proxy_cfg.get('type', 'http'),
            'host': proxy_cfg.get('host', ''),
            'port': proxy_cfg.get('port', ''),
            'username': proxy_cfg.get('username', ''),
            'has_password': bool(proxy_cfg.get('password', '')),
            'exclude_hosts': proxy_cfg.get('exclude_hosts', ''),
            'proxy_url': self.get_proxy_url() if self.is_enabled() else None
        }


# 全局代理管理器实例
proxy_manager = ProxyManager()
