# -*- coding: utf-8 -*-
"""
NapCat部署器
负责NapCat的下载、安装和配置
可以引用napcat_downloader或独立实现
"""
import fnmatch
import os
import platform
import shutil
import subprocess
import tempfile
import time
import zipfile
from typing import Dict, List, Optional
import structlog
import requests

from .base_deployer import BaseDeployer
from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class NapCatDeployer(BaseDeployer):
    """NapCat部署器"""
    
    def __init__(self):
        super().__init__()
        self.napcat_repo = "NapNeko/NapCatQQ"
        self._napcat_versions_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5分钟缓存
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache_timestamp is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_duration
    
    def get_napcat_versions(self, force_refresh: bool = False) -> List[Dict]:
        """获取NapCat版本列表 - 从GitHub API获取最新5个版本及其实际资产"""
        # 检查缓存
        if not force_refresh and self._is_cache_valid() and self._napcat_versions_cache:
            return self._napcat_versions_cache
        
        # 重试配置
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # 从GitHub API获取NapCatQQ的最新releases
                url = f"{self.github_api_base}/repos/{self.napcat_repo}/releases"
                headers = {"Accept": "application/vnd.github.v3+json"}
                
                if attempt == 0:
                    ui.print_info("正在获取 NapCatQQ 的最新版本信息...")
                else:
                    ui.print_info(f"重试获取版本信息... (尝试 {attempt + 1}/{max_retries})")
                
                response = requests.get(url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                
                releases = response.json()
                
                # 获取最新的5个版本
                latest_releases = releases[:5] if isinstance(releases, list) else []
                
                napcat_versions = []
                for release in latest_releases:
                    tag_name = release.get("tag_name", "")
                    release_name = release.get("name", tag_name)
                    assets = release.get("assets", [])
                    
                    # 过滤并分类资产
                    shell_assets = []
                    framework_onekey_assets = []
                    shell_onekey_assets = []
                    
                    for asset in assets:
                        asset_name = asset.get("name", "")
                        # Shell基础版（NapCat.Shell.zip）
                        if asset_name == "NapCat.Shell.zip":
                            shell_assets.append(asset)
                        # Framework一键包（NapCat.Framework.Windows.OneKey.zip）
                        elif "Framework" in asset_name and "OneKey" in asset_name and "Windows" in asset_name:
                            framework_onekey_assets.append(asset)
                        # Shell一键包（NapCat.Shell.Windows.OneKey.zip）
                        elif "Shell" in asset_name and "OneKey" in asset_name and "Windows" in asset_name:
                            shell_onekey_assets.append(asset)
                    
                    # 优先添加Shell基础版
                    for asset in shell_assets:
                        napcat_versions.append({
                            "name": f"{tag_name}-shell",
                            "display_name": f"{tag_name} 基础版 (推荐)",
                            "description": "最推荐的版本，适合大多数用户",
                            "published_at": release.get("published_at", ""),
                            "download_url": asset.get("browser_download_url", ""),
                            "size": asset.get("size", 0),
                            "changelog": release.get("body", "暂无更新日志"),
                            "asset_name": asset.get("name", ""),
                            "version": tag_name
                        })
                    
                    # 添加Framework一键包
                    for asset in framework_onekey_assets:
                        napcat_versions.append({
                            "name": f"{tag_name}-framework-onekey",
                            "display_name": f"{tag_name} 有头一键包",
                            "description": "带QQ界面的一键包版本，适合挂机器人的同时附体发消息",
                            "published_at": release.get("published_at", ""),
                            "download_url": asset.get("browser_download_url", ""),
                            "size": asset.get("size", 0),
                            "changelog": release.get("body", "暂无更新日志"),
                            "asset_name": asset.get("name", ""),
                            "version": tag_name
                        })
                    
                    # 添加Shell一键包
                    for asset in shell_onekey_assets:
                        napcat_versions.append({
                            "name": f"{tag_name}-shell-onekey",
                            "display_name": f"{tag_name} 无头一键包",
                            "description": "无界面的一键包版本",
                            "published_at": release.get("published_at", ""),
                            "download_url": asset.get("browser_download_url", ""),
                            "size": asset.get("size", 0),
                            "changelog": release.get("body", "暂无更新日志"),
                            "asset_name": asset.get("name", ""),
                            "version": tag_name
                        })
                
                # 更新缓存
                self._napcat_versions_cache = napcat_versions
                self._cache_timestamp = time.time()
                
                logger.info("成功获取NapCat版本列表", count=len(napcat_versions))
                return napcat_versions
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    ui.print_warning(f"获取版本列表失败: {error_msg}，等待 {retry_delay} 秒后重试...")
                    logger.warning("获取NapCat版本列表失败，准备重试", 
                                 error=error_msg,
                                 attempt=attempt + 1,
                                 max_retries=max_retries)
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # 指数退避
                else:
                    ui.print_error(f"获取NapCat版本列表失败（已重试{max_retries}次）：{error_msg}")
                    logger.error("获取NapCat版本列表失败，重试耗尽", 
                               error=error_msg,
                               total_attempts=max_retries)
        
        # 理论上不会到这里，但作为保险返回默认版本
        return self._get_default_napcat_versions()
    
    def _get_default_napcat_versions(self) -> List[Dict]:
        """获取默认的NapCat版本列表"""
        napcat_versions = [
            {
                "name": "v4.8.90-shell",
                "display_name": "v4.8.90 基础版 (推荐)",
                "description": "基础版本，适合大多数用户",
                "published_at": "2024-12-01T00:00:00Z",
                "download_url": "https://github.com/NapNeko/NapCatQQ/releases/download/v4.8.90/NapCat.Shell.zip",
                "size": 45 * 1024 * 1024,  # 估算45MB
                "changelog": "v4.8.90 稳定版本",
                "asset_name": "NapCat.Shell.zip",
                "version": "v4.8.90"
            }
        ]
        return napcat_versions
    
    def select_napcat_version(self) -> Optional[Dict]:
        """显示NapCat版本选择菜单"""
        ui.clear_screen()
        ui.components.show_title("选择NapCat版本", symbol="🐱")
        
        # 获取版本列表
        versions = self.get_napcat_versions()
        
        if not versions:
            ui.print_error("无法获取NapCat版本列表")
            return None
        
        # 创建版本表格
        from rich.table import Table
        table = Table(
            show_header=True,
            header_style=ui.colors["table_header"],
            title="[bold]NapCat 可用版本[/bold]",
            title_style=ui.colors["primary"],
            border_style=ui.colors["border"],
            show_lines=True
        )
        table.add_column("选项", style="cyan", width=6, justify="center")
        table.add_column("版本", style=ui.colors["primary"], width=20)
        table.add_column("类型", style="yellow", width=15, justify="center")
        table.add_column("说明", style="green")
        
        # 显示版本信息
        for i, version in enumerate(versions, 1):
            version_type = "基础版" if "基础版" in version["display_name"] else "一键包"
            table.add_row(
                f"[{i}]",
                version["display_name"],
                version_type,
                version.get("description", "")[:40]
            )
        
        ui.console.print(table)
        ui.console.print("\n[Enter] 使用默认版本(第一个选项)  [Q] 取消下载", style=ui.colors["info"])
        ui.console.print("提示：推荐使用基础版，适合大多数用户", style=ui.colors["success"])
        
        while True:
            choice = ui.get_input(f"请选择版本序号 (1-{len(versions)}，直接回车使用默认): ").strip()
            
            # 如果用户直接按回车，使用默认版本(第一个选项)
            if choice == "":
                ui.print_info(f"使用默认版本: {versions[0]['display_name']}")
                return versions[0]
            
            if choice.upper() == 'Q':
                ui.print_info("用户取消NapCat下载")
                return None
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(versions):
                    selected = versions[idx]
                    ui.print_info(f"已选择版本: {selected['display_name']}")
                    return selected
                else:
                    ui.print_error(f"无效的序号，请输入 1-{len(versions)} 之间的数字")
            except ValueError:
                ui.print_error("请输入有效的数字或直接回车使用默认版本")
    
    def install_napcat(self, deploy_config: Dict, bot_path: str) -> str:
        """
        安装NapCat
        
        Args:
            deploy_config: 部署配置
            bot_path: Bot路径
            
        Returns:
            NapCat路径
        """
        ui.console.print("\n[🐱 第三步：安装NapCat]", style=ui.colors["primary"])
        
        napcat_version = deploy_config["napcat_version"]
        install_dir = deploy_config["install_dir"]
        
        ui.print_info(f"开始安装NapCat {napcat_version['display_name']}...")
        
        napcat_exe = self.download_napcat(napcat_version, install_dir)
        if napcat_exe:
            # 等待用户完成安装并进行3次检测
            napcat_path = self._wait_for_napcat_installation(install_dir)
            if napcat_path:
                ui.print_success("✅ NapCat安装并检测完成")
                logger.info("NapCat安装成功", path=napcat_path)
                return napcat_path
            else:
                ui.print_error("❌ NapCat路径检测失败")
                ui.print_warning("⚠️ 您可以稍后手动配置NapCat路径")
                logger.warning("NapCat路径检测失败，用户需手动配置")
                return ""
        else:
            ui.print_error("❌ NapCat下载失败")
            ui.print_warning("⚠️ 请稍后手动下载和配置NapCat")
            logger.error("NapCat下载失败")
            return ""
    
    def download_napcat(self, napcat_version: Dict, install_dir: str) -> Optional[str]:
        """下载并解压NapCat"""
        try:
            ui.print_info(f"开始下载NapCat {napcat_version['display_name']}...")
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                download_url = napcat_version["download_url"]
                filename = napcat_version.get("asset_name", os.path.basename(download_url))
                temp_file = os.path.join(temp_dir, filename)
                
                if not self.download_file(download_url, temp_file):
                    return None
                
                # 解压到NapCat目录
                napcat_dir = os.path.join(install_dir, "NapCat")
                os.makedirs(napcat_dir, exist_ok=True)
                
                ui.print_info("正在解压NapCat...")
                
                if filename.endswith('.zip'):
                    with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                        zip_ref.extractall(napcat_dir)
                else:
                    # 如果是其他格式，直接复制
                    shutil.copy2(temp_file, napcat_dir)
                
                ui.print_success("NapCat下载完成")
                logger.info("NapCat下载成功", version=napcat_version['display_name'], path=napcat_dir)
                
                # 查找NapCat安装程序
                installer_exe = None
                napcat_exe = None
                
                for root, dirs, files in os.walk(napcat_dir):
                    for file in files:
                        # 查找安装程序
                        if file.lower() == 'napcatinstaller.exe':
                            installer_exe = os.path.join(root, file)
                        # 查找NapCat可执行文件
                        elif file.lower().endswith('.exe') and 'napcat' in file.lower():
                            napcat_exe = os.path.join(root, file)
                
                # 如果找到安装程序，询问是否自动安装
                if installer_exe and os.path.exists(installer_exe):
                    ui.print_info(f"找到NapCat安装程序: {installer_exe}")
                    
                    if ui.confirm("是否自动运行NapCat安装程序？"):
                        installer_success = self.run_napcat_installer(installer_exe)
                        if installer_success:
                            ui.print_success("NapCat安装程序已成功启动")
                            return napcat_exe or napcat_dir
                        else:
                            ui.print_error("NapCat安装程序启动失败")
                            return None
                    else:
                        ui.print_info("您可以稍后手动运行安装程序")
                        ui.print_info(f"安装程序位置: {installer_exe}")
                        ui.print_info("安装完成后，系统将自动检测NapCat位置")
                else:
                    ui.print_warning("未找到NapCatInstaller.exe，跳过自动安装")
                
                # 如果没有安装程序或用户选择不安装，尝试查找现有的NapCat
                existing_napcat = self.find_installed_napcat(install_dir)
                if existing_napcat:
                    return existing_napcat
                    
                return napcat_exe or napcat_dir
                
        except Exception as e:
            ui.print_error(f"NapCat下载失败：{str(e)}")
            logger.error("NapCat下载失败", error=str(e))
            return None
    
    def find_installed_napcat(self, install_dir: str) -> Optional[str]:
        """
        查找已安装的NapCat主程序
        优先查找无头版本(Shell)，其次查找有头版本(Framework)
        
        Args:
            install_dir: 安装目录
            
        Returns:
            NapCat主程序路径(NapCatWinBootMain.exe)，如果未找到则返回None
        """
        try:
            # 优先查找无头版本 NapCat.34740.Shell\NapCatWinBootMain.exe
            shell_pattern = "NapCat.*.Shell"
            shell_exe_name = "NapCatWinBootMain.exe"
            install_dir = os.path.join(install_dir, "NapCat")  # 确保安装目录正确
            
            # 首先检查根目录下是否有可执行文件（适配NapCat.Shell版本）
            root_exe_path = os.path.join(install_dir, shell_exe_name)
            if os.path.exists(root_exe_path):
                ui.print_success(f"找到NapCat无头版本（根目录）: {root_exe_path}")
                logger.info("发现NapCat Shell版本（根目录）", path=root_exe_path)
                return root_exe_path
            
            # 遍历安装目录，查找匹配的Shell目录
            for item in os.listdir(install_dir):
                item_path = os.path.join(install_dir, item)
                if os.path.isdir(item_path) and fnmatch.fnmatch(item, shell_pattern):
                    shell_exe_path = os.path.join(item_path, shell_exe_name)
                    if os.path.exists(shell_exe_path):
                        ui.print_success(f"找到NapCat无头版本: {shell_exe_path}")
                        logger.info("发现NapCat Shell版本", path=shell_exe_path)
                        return shell_exe_path
            
            # 如果没找到Shell版本，查找有头版本 NapCat.34740.Framework\NapCatWinBootMain.exe
            framework_pattern = "NapCat.*.Framework"
            
            for item in os.listdir(install_dir):
                item_path = os.path.join(install_dir, item)
                if os.path.isdir(item_path) and fnmatch.fnmatch(item, framework_pattern):
                    framework_exe_path = os.path.join(item_path, shell_exe_name)
                    if os.path.exists(framework_exe_path):
                        ui.print_success(f"找到NapCat有头版本: {framework_exe_path}")
                        logger.info("发现NapCat Framework版本", path=framework_exe_path)
                        return framework_exe_path
            
            ui.print_warning("未找到已安装的NapCat主程序")
            logger.warning("未找到NapCat主程序", search_dir=install_dir)
            return None
            
        except Exception as e:
            ui.print_warning(f"查找NapCat安装时出错: {str(e)}")
            logger.error("查找NapCat安装异常", error=str(e))
            return None
    
    def run_napcat_installer(self, installer_path: str) -> bool:
        """
        运行NapCat安装程序
        
        Args:
            installer_path: 安装程序路径
            
        Returns:
            是否成功启动安装程序
        """
        try:
            if not os.path.exists(installer_path):
                ui.print_error("安装程序文件不存在")
                return False
            
            installer_dir = os.path.dirname(installer_path)
            installer_name = os.path.basename(installer_path)
            
            ui.print_info("正在启动NapCat安装程序...")
            logger.info("启动NapCat安装程序", installer_path=installer_path)
            
            # 在Windows上直接启动安装程序
            if platform.system() == "Windows":
                subprocess.Popen([installer_path], cwd=installer_dir)
                ui.print_success("NapCat安装程序已启动")
                return True
            else:
                ui.print_warning("非Windows系统暂不支持自动安装")
                return False
                
        except Exception as e:
            ui.print_error(f"启动安装程序失败: {str(e)}")
            logger.error("启动NapCat安装程序失败", error=str(e))
            return False
    
    def _wait_for_napcat_installation(self, install_dir: str) -> Optional[str]:
        """等待NapCat安装完成并检测路径"""
        ui.print_info("等待NapCat安装完成...")
        ui.print_warning("请在弹出的安装窗口中完成NapCat安装")
        ui.print_info("安装完成后，按回车键开始检测NapCat路径(若您安装的是基础版[NapCat.Shell]，则可以直接回车检测，不必等待安装完成)")
        
        # 等待用户确认安装完成
        ui.pause("NapCat安装完成后按回车继续...")
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            ui.print_info(f"正在进行第 {attempt}/{max_attempts} 次NapCat路径检测...")
            
            # 检测是否有新的NapCat安装
            napcat_path = self.find_installed_napcat(install_dir)
            if napcat_path:
                ui.print_success(f"✅ 检测到NapCat安装：{napcat_path}")
                logger.info("NapCat路径检测成功", path=napcat_path, attempt=attempt)
                return napcat_path
            
            if attempt < max_attempts:
                ui.print_warning(f"❌ 第 {attempt} 次检测未找到NapCat，等待5秒后进行下一次检测...")
                time.sleep(5)  # 等待5秒后再进行下一次检测
            else:
                ui.print_error(f"❌ 已完成 {max_attempts} 次检测，均未找到NapCat安装")
        
        ui.print_error("NapCat路径检测失败，请检查以下可能的原因：")
        ui.console.print("  • NapCat安装程序未正常完成安装")
        ui.console.print("  • 安装目录与预期不符")
        ui.console.print("  • 需要手动配置NapCat路径")
        logger.error("NapCat路径检测失败", install_dir=install_dir, max_attempts=max_attempts)
        return None
    
    def clear_napcat_versions_cache(self):
        """清除NapCat版本缓存"""
        self._napcat_versions_cache = None
        self._cache_timestamp = None
        logger.info("NapCat版本缓存已清除")
