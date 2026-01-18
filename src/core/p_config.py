"""
麦麦启动器程序配置模块
负责程序本身配置文件的加载、保存和管理（例如UI主题）
"""
import os
import toml
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)

class PConfig:
    """程序配置管理类"""

    CONFIG_FILE = "config/P-config.toml"
    
    # 定义默认配置，特别是UI主题
    DEFAULT_CONFIG = {
        "theme": {
            "primary": "#BADFFA",
            "success": "#4AF933",
            "warning": "#F2FF5D",
            "error": "#FF6B6B",
            "info": "#6DA0FD",
            "secondary": "#00FFBB",
            "danger": "#FF6B6B",
            "exit": "#7E1DE4",
            "header": "#BADFFA",
            "title": "bold magenta",
            "border": "bright_black",
            "table_header": "bold magenta",
            "cyan": "cyan",
            "white": "white",
            "green": "green",
            "blue": "#005CFA",
            "attention": "#FF45F6"
        },
        "logging": {
            "log_rotation_days": 30
        },
        "display": {
            "max_versions_display": 20
        },
        "on_exit": {
            "process_action": "ask"
        },
        "notifications": {
            "windows_center_enabled": True
        },
        "ui": {
            "minimize_to_tray": False
        },
        "network": {
            "proxy": {
                "enabled": False,
                "type": "http",
                "host": "",
                "port": "",
                "username": "",
                "password": "",
                "exclude_hosts": "localhost,127.0.0.1"
            }
        },
        "monitor": {
            "data_refresh_interval": 2.0,
            "ui_refresh_interval": 0.3,
            "input_poll_interval": 0.05
        },
        "git": {
            "mirrors": [
                "https://github.com",
                "https://ghproxy.com/https://github.com",
                "https://bgithub.xyz",
            ],
            "auto_select_mirror": True,
            "selected_mirror": "",
            "timeout": 30,
            "depth": 1
        }
    }

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """加载配置文件，如果不存在或损坏则使用默认值"""
        try:
            if not os.path.exists(self.CONFIG_FILE):
                logger.warning("程序配置文件不存在，使用默认配置", file=self.CONFIG_FILE)
                self.config = self.DEFAULT_CONFIG.copy()
                self.save()
                return self.config
            
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = toml.load(f)
                logger.info("成功加载程序配置文件")
            
            # 可以在这里添加配置项验证逻辑，确保所有必需的键都存在
            
            return self.config
            
        except Exception as e:
            logger.error("加载程序配置文件失败，使用默认配置", error=str(e))
            self.config = self.DEFAULT_CONFIG.copy()
            return self.config

    def save(self) -> bool:
        """保存当前配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                toml.dump(self.config, f)
            logger.info("程序配置文件保存成功")
            return True
        except Exception as e:
            logger.error("保存程序配置文件失败", error=str(e))
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔的嵌套键"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default

    def set(self, key: str, value: Any) -> None:
        """设置配置值，支持点分隔的嵌套键"""
        try:
            keys = key.split('.')
            d = self.config
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value
        except Exception as e:
            logger.error("设置程序配置值失败", key=key, error=str(e))

    def get_theme_colors(self) -> Dict[str, str]:
        """获取当前主题颜色"""
        return self.get("theme", self.DEFAULT_CONFIG["theme"])

    def get_proxy_config(self) -> Dict[str, Any]:
        """获取代理配置"""
        return self.get("network.proxy", self.DEFAULT_CONFIG["network"]["proxy"])

    def is_proxy_enabled(self) -> bool:
        """检查代理是否启用"""
        return self.get("network.proxy.enabled", False)

    def reset_to_default(self) -> bool:
        """将配置重置为默认值并保存"""
        logger.info("正在将程序配置重置为默认值")
        self.config = self.DEFAULT_CONFIG.copy()
        return self.save()

# 全局程序配置实例
p_config_manager = PConfig()