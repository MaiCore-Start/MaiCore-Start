# -*- coding: utf-8 -*-
"""
实例运行数据查看模块
负责收集MaiBot实例的运行数据并生成统计页面
"""
import os
import json
import time
import webbrowser
import subprocess
import structlog
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..ui.interface import ui

logger = structlog.get_logger(__name__)


class InstanceStatisticsManager:
    """实例运行数据管理器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.statistics_template = self._load_statistics_template()
    
    def _load_statistics_template(self) -> str:
        """加载HTML模板"""
        template_path = self.project_root / "maibot_statistics.html"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # 如果模板文件不存在，返回默认模板
            return self._get_default_template()
    
    def _get_default_template(self) -> str:
        """获取默认HTML模板"""
        # 读取项目根目录下的maibot_statistics.html文件作为默认模板
        try:
            template_path = self.project_root / "maibot_statistics.html"
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.warning("读取默认模板失败", error=str(e))
        
        # 如果读取失败，返回一个简单的错误页面
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MaiBot 统计页面</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        .error { color: #dc3545; }
    </style>
</head>
<body>
    <h1 class="error">无法加载统计页面模板</h1>
    <p>请确保 maibot_statistics.html 文件存在于正确位置</p>
</body>
</html>"""
    
    def open_statistics_page(self, config: Optional[Dict[str, Any]] = None, instance_path: Optional[str] = None) -> bool:
        """
        打开实例的统计页面
        
        Args:
            config: 实例配置（可选）
            instance_path: 实例路径（可选）
            
        Returns:
            是否成功打开
        """
        try:
            # 确定实例路径
            if instance_path:
                target_path = instance_path
            elif config:
                mai_path = config.get("mai_path", "")
                if not mai_path:
                    ui.print_error("配置中未找到MaiBot路径")
                    return False
                target_path = mai_path
            else:
                ui.print_error("未提供实例路径或配置")
                return False
            
            # 检查统计页面是否存在
            html_path = os.path.join(target_path, "maibot_statistics.html")
            if not os.path.exists(html_path):
                ui.print_warning(f"实例统计页面不存在: {html_path}")
                ui.print_info("请确保该实例已经生成了统计页面")
                return False
            
            # 在默认浏览器中打开
            self._open_in_browser(html_path)
            
            logger.info("打开统计页面成功", path=html_path)
            return True
            
        except Exception as e:
            ui.print_error(f"打开统计页面失败: {str(e)}")
            logger.error("打开统计页面失败", error=str(e))
            return False
    
    def _generate_statistics_html(self, config: Dict[str, Any]) -> str:
        """生成统计HTML内容"""
        try:
            # 准备模板数据
            template_data = self._prepare_template_data(config)
            
            # 使用简单的字符串替换来填充模板
            html_content = self.statistics_template
            
            # 替换模板变量
            for key, value in template_data.items():
                placeholder = f"{{{{ {key} }}}}"
                html_content = html_content.replace(placeholder, str(value))
            
            return html_content
            
        except Exception as e:
            ui.print_error(f"生成HTML内容失败: {str(e)}")
            logger.error("生成HTML内容失败", error=str(e))
            raise
    
    def _collect_instance_data(self, instance_path: str, config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        从实例路径收集数据
        
        Args:
            instance_path: 实例路径
            config: 配置信息（可选）
            
        Returns:
            实例数据字典
        """
        try:
            instance_data = {
                "mai_path": instance_path,
                "serial_number": "未知",
                "nickname": "未知",
                "version_path": "未知",
                "qq_account": "未设置",
                "bot_type": "MaiBot",
                "absolute_serial_number": "未知",
                "adapter_path": "",
                "napcat_path": "",
                "mongodb_path": "",
                "webui_path": "",
                "install_options": {}
            }
            
            # 如果提供了配置信息，使用配置中的数据
            if config:
                instance_data.update(config)
            
            # 尝试从实例路径读取配置文件
            self._read_instance_config(instance_path, instance_data)
            
            return instance_data
            
        except Exception as e:
            ui.print_error(f"收集实例数据失败: {str(e)}")
            logger.error("收集实例数据失败", error=str(e))
            return None
    
    def _read_instance_config(self, instance_path: str, instance_data: Dict[str, Any]):
        """从实例路径读取配置文件"""
        try:
            # 读取 .env 文件
            env_file = os.path.join(instance_path, ".env")
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            if key.upper() == 'QQ':
                                instance_data["qq_account"] = value
                            elif key.upper() == 'NICKNAME':
                                instance_data["nickname"] = value
            
            # 读取 bot_config.toml 文件
            config_dir = os.path.join(instance_path, "config")
            if os.path.exists(config_dir):
                bot_config_file = os.path.join(config_dir, "bot_config.toml")
                if os.path.exists(bot_config_file):
                    try:
                        import tomli
                        with open(bot_config_file, 'rb') as f:
                            bot_config = tomli.load(f)
                        
                        bot_section = bot_config.get("bot", {})
                        instance_data["qq_account"] = bot_section.get("qq_account", instance_data["qq_account"])
                        instance_data["nickname"] = bot_section.get("nickname", instance_data["nickname"])
                        
                    except Exception as e:
                        logger.warning("读取bot_config.toml失败", error=str(e))
            
            # 读取 package.json 文件（如果存在）
            package_file = os.path.join(instance_path, "package.json")
            if os.path.exists(package_file):
                try:
                    with open(package_file, 'r', encoding='utf-8') as f:
                        package_data = json.load(f)
                    
                    # 尝试从package.json获取版本信息
                    version = package_data.get("version", "")
                    if version:
                        instance_data["version_path"] = version
                    
                    # 尝试从description获取昵称
                    description = package_data.get("description", "")
                    if description and instance_data["nickname"] == "未知":
                        instance_data["nickname"] = description
                        
                except Exception as e:
                    logger.warning("读取package.json失败", error=str(e))
            
            # 尝试从目录名推断昵称
            if instance_data["nickname"] == "未知":
                instance_data["nickname"] = os.path.basename(instance_path)
            
            # 尝试检测适配器路径
            adapter_paths = [
                os.path.join(instance_path, "adapter"),
                os.path.join(instance_path, "MaiBot-Napcat-Adapter"),
                os.path.join(instance_path, "napcat-adapter")
            ]
            
            for adapter_path in adapter_paths:
                if os.path.exists(adapter_path):
                    instance_data["adapter_path"] = adapter_path
                    break
            
            # 尝试检测NapCat路径
            napcat_exe = "NapCatWinBootMain.exe"
            for root, dirs, files in os.walk(instance_path):
                if napcat_exe in files:
                    instance_data["napcat_path"] = os.path.join(root, napcat_exe)
                    break
            
        except Exception as e:
            logger.warning("读取实例配置失败", error=str(e))

    def _prepare_template_data(self, config: Dict[str, Any]) -> Dict[str, str]:
        """准备模板数据"""
        # 获取基本信息
        serial_number = config.get("serial_number", "未知")
        nickname = config.get("nickname_path", "未知")
        mai_path = config.get("mai_path", "")
        version_path = config.get("version_path", "未知")
        qq_account = config.get("qq_account", "未设置")
        bot_type = config.get("bot_type", "未知")
        absolute_serial_number = config.get("absolute_serial_number", "未知")
        
        # 处理适配器状态
        adapter_path = config.get("adapter_path", "")
        if adapter_path and adapter_path not in ["跳过适配器安装", "无需适配器"]:
            adapter_status = "已配置"
            adapter_status_color = "#28a745"  # 绿色
        elif adapter_path == "无需适配器":
            adapter_status = "无需适配器"
            adapter_status_color = "#17a2b8"  # 蓝色
        else:
            adapter_status = "未配置"
            adapter_status_color = "#dc3545"  # 红色
        
        # 处理安装选项
        install_options = config.get("install_options", {})
        
        # 获取其他路径
        napcat_path = config.get("napcat_path", "")
        mongodb_path = config.get("mongodb_path", "")
        webui_path = config.get("webui_path", "")
        
        # 截断长路径用于显示
        display_mai_path = mai_path if len(mai_path) <= 50 else mai_path[:47] + "..."
        display_napcat_path = napcat_path if len(napcat_path) <= 50 else napcat_path[:47] + "..."
        display_mongodb_path = mongodb_path if len(mongodb_path) <= 50 else mongodb_path[:47] + "..."
        display_webui_path = webui_path if len(webui_path) <= 50 else webui_path[:47] + "..."
        
        # 生成时间戳
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        return {
            "serial_number": serial_number,
            "nickname": nickname,
            "mai_path": display_mai_path,
            "version_path": version_path,
            "qq_account": qq_account,
            "bot_type": bot_type,
            "absolute_serial_number": absolute_serial_number,
            "adapter_status": adapter_status,
            "adapter_status_color": adapter_status_color,
            "install_options": install_options,
            "napcat_path": display_napcat_path,
            "mongodb_path": display_mongodb_path,
            "webui_path": display_webui_path,
            "timestamp": timestamp
        }
    
    def _open_in_browser(self, file_path: str):
        """在默认浏览器中打开文件"""
        try:
            # 尝试使用webbrowser模块
            webbrowser.open(f"file://{file_path}")
        except Exception as e:
            ui.print_warning(f"使用默认浏览器打开失败: {str(e)}")
            try:
                # 备用方案：使用系统命令
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # Linux/Mac
                    subprocess.run(['xdg-open', file_path])
            except Exception as e2:
                ui.print_error(f"无法打开浏览器: {str(e2)}")
                logger.error("打开浏览器失败", error=str(e2))


# 全局实例
instance_statistics_manager = InstanceStatisticsManager()