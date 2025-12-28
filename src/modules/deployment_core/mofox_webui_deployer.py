# -*- coding: utf-8 -*-
"""
MoFox WebUI部署器
负责MoFox WebUI的下载、解压和配置
"""
import os
import re
import shutil
import tempfile
import zipfile
import requests
import structlog
from typing import Dict, Optional, Tuple
from pathlib import Path

from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class MoFoxWebUIDeployer:
    """MoFox WebUI部署器"""
    
    def __init__(self):
        self.github_api_base = "https://api.github.com"
        self.repo_owner = "MoFox-Studio"
        self.repo_name = "MoFox-Core-Webui"
        
    def get_latest_release_info(self) -> Optional[Dict]:
        """获取GitHub上最新的release信息，支持重试机制"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                url = f"{self.github_api_base}/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                release_data = response.json()
                
                # 查找mofox-webui-backend.zip文件
                backend_asset = None
                for asset in release_data.get("assets", []):
                    if asset["name"] == "mofox-webui-backend.zip":
                        backend_asset = asset
                        break
                
                if not backend_asset:
                    logger.error("未找到mofox-webui-backend.zip文件")
                    return None
                    
                return {
                    "tag_name": release_data["tag_name"],
                    "name": release_data["name"],
                    "download_url": backend_asset["browser_download_url"],
                    "published_at": release_data["published_at"]
                }
                
            except requests.RequestException as e:
                retry_count += 1
                error_msg = f"获取GitHub release信息失败: {e}"
                
                if retry_count < max_retries:
                    ui.print_warning(f"{error_msg} (尝试 {retry_count}/{max_retries})")
                    ui.print_info("网络连接失败，请选择操作：")
                    ui.console.print(" [1] 重试", style="green")
                    ui.console.print(" [2] 跳过WebUI安装", style="yellow")
                    
                    while True:
                        choice = ui.get_input("请选择 (1/2): ").strip()
                        if choice == "1":
                            ui.print_info("正在重试...")
                            break
                        elif choice == "2":
                            ui.print_info("已跳过WebUI安装")
                            return None
                        else:
                            ui.print_error("无效选择，请输入 1 或 2")
                else:
                    ui.print_error(f"{error_msg} (已重试 {max_retries} 次)")
                    logger.error("获取GitHub release失败", error=str(e))
                    return None
                    
            except Exception as e:
                ui.print_error(f"解析release信息失败: {e}")
                logger.error("解析release信息失败", error=str(e))
                return None
        
        return None
    
    def download_and_extract_webui(self, deploy_config: Dict, bot_path: str) -> Tuple[bool, str]:
        """
        下载并解压MoFox WebUI到插件目录
        
        Args:
            deploy_config: 部署配置
            bot_path: MoFox Bot路径
            
        Returns:
            (是否成功, WebUI路径)
        """
        ui.console.print("\n[🦊 MoFox WebUI部署]", style=ui.colors["primary"])
        
        try:
            # 获取最新release信息
            ui.print_info("正在获取MoFox WebUI最新版本信息...")
            release_info = self.get_latest_release_info()
            if not release_info:
                ui.print_error("无法获取MoFox WebUI版本信息")
                return False, ""
            
            ui.print_info(f"最新版本: {release_info['tag_name']}")
            
            # 确定插件目录路径 - plugins目录应该在MoFox_bot文件夹下
            plugins_dir = os.path.join(bot_path, "plugins")
            
            # 如果plugins目录不存在，创建它
            if not os.path.exists(plugins_dir):
                ui.print_info("创建plugins目录...")
                os.makedirs(plugins_dir, exist_ok=True)
            
            # 目标路径
            backend_path = os.path.join(plugins_dir, "backend")
            
            # 如果已存在，先删除
            if os.path.exists(backend_path):
                ui.print_warning(f"WebUI目录已存在，将先删除: {backend_path}")
                shutil.rmtree(backend_path)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # 下载文件
                ui.print_info("正在下载MoFox WebUI...")
                archive_path = os.path.join(temp_dir, "mofox-webui-backend.zip")
                
                try:
                    response = requests.get(release_info["download_url"], timeout=300)
                    response.raise_for_status()
                    
                    with open(archive_path, 'wb') as f:
                        f.write(response.content)
                    
                    ui.print_success("下载完成")
                    
                except requests.RequestException as e:
                    ui.print_error(f"下载失败: {e}")
                    return False, ""
                
                # 解压文件
                ui.print_info("正在解压WebUI文件...")
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # 查找解压后的backend目录
                    extracted_dirs = []
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isdir(item_path):
                            extracted_dirs.append(item_path)
                    
                    if not extracted_dirs:
                        ui.print_error("解压后未找到目录")
                        return False, ""
                    
                    # 假设第一个目录是backend目录
                    backend_source = extracted_dirs[0]
                    
                    # 移动到目标位置并重命名为backend
                    ui.print_info("正在安装WebUI到插件目录...")
                    shutil.move(backend_source, backend_path)
                    
                    ui.print_success(f"✅ MoFox WebUI安装完成")
                    ui.print_info(f"安装路径: {backend_path}")
                    
                    return True, backend_path
                    
                except zipfile.BadZipFile:
                    ui.print_error("下载的文件不是有效的ZIP格式")
                    return False, ""
                except Exception as e:
                    ui.print_error(f"解压失败: {e}")
                    return False, ""
                
        except Exception as e:
            ui.print_error(f"MoFox WebUI部署失败: {e}")
            logger.error("MoFox WebUI部署失败", error=str(e))
            return False, ""
    
    def configure_api_key(self, webui_path: str, bot_path: str) -> bool:
        """
        配置bot_config.toml中的API Key
        
        Args:
            webui_path: WebUI路径
            bot_path: Bot路径
            
        Returns:
            是否配置成功
        """
        try:
            config_path = os.path.join(bot_path, "config", "bot_config.toml")
            
            if not os.path.exists(config_path):
                ui.print_warning(f"配置文件不存在: {config_path}")
                ui.print_info("配置文件将在部署过程中自动创建，请稍后手动配置API Key")
                return True  # 不算失败，只是时机未到
            
            ui.print_info("正在配置API Key...")
            
            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否已有webui配置节
            webui_section_pattern = r'\[webui\]'
            api_key_pattern = r'api_key\s*=\s*["\']?[^"\'\s]*["\']?'
            
            if re.search(webui_section_pattern, content):
                # 已有webui节，检查api_key
                if re.search(api_key_pattern, content):
                    ui.print_info("发现现有API Key配置")
                    ui.print_warning("请手动在bot_config.toml中配置WebUI的API Key")
                    return True
                else:
                    # 添加api_key到现有节
                    content = re.sub(
                        r'(\[webui\])',
                        r'\1\napi_key = ""  # 请在此处配置您的API Key',
                        content
                    )
            else:
                # 添加新的webui节
                webui_section = """

[webui]
# MoFox WebUI配置
api_key = ""  # 请在此处配置您的API Key
host = "127.0.0.1"
port = 12138
"""
                content += webui_section
            
            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            ui.print_success("✅ API Key配置完成")
            ui.print_info("请在bot_config.toml中配置您的API Key")
            return True
            
        except Exception as e:
            ui.print_error(f"配置API Key失败: {e}")
            logger.error("配置API Key失败", error=str(e))
            return False
    
    def install_webui(self, deploy_config: Dict, bot_path: str) -> Tuple[bool, str]:
        """
        完整的WebUI安装流程
        
        Args:
            deploy_config: 部署配置
            bot_path: MoFox Bot路径
            
        Returns:
            (是否成功, WebUI路径)
        """
        # 下载并解压
        success, webui_path = self.download_and_extract_webui(deploy_config, bot_path)
        if not success:
            return False, ""
        
        # 配置API Key
        self.configure_api_key(webui_path, bot_path)
        
        return True, webui_path