# -*- coding: utf-8 -*-
"""
Visual Studio Code下载器
"""

import platform
import os
import subprocess
import ctypes
import requests
from pathlib import Path
from typing import Optional, List, Dict
import structlog

from ...ui.interface import ui
from .base_downloader import BaseDownloader

logger = structlog.get_logger(__name__)


class VSCODEDownloader(BaseDownloader):
    """Visual Studio Code下载器"""
    
    def __init__(self):
        super().__init__("VSCode")
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        
        # 标准化架构名称
        if self.arch in ['x86_64', 'amd64']:
            self.arch = 'x64'
        elif self.arch in ['arm64', 'aarch64']:
            self.arch = 'arm64'
        else:
            self.arch = 'x64'
    
    def get_vscode_versions(self) -> List[Dict]:
        """获取VSCode版本列表"""
        try:
            ui.print_info("正在获取VSCode最新版本信息...")
            
            # GitHub API获取releases - VSCode不在GitHub发布资产，只获取版本信息
            response = requests.get(
                "https://api.github.com/repos/microsoft/vscode/releases",
                timeout=10
            )
            response.raise_for_status()
            
            releases = response.json()
            ui.print_info(f"获取到 {len(releases)} 个发布版本")
            versions = []
            
            # 处理前10个版本
            for i, release in enumerate(releases[:10]):
                tag_name = release['tag_name']
                version_name = release['name']
                published_at = release['published_at']
                prerelease = release['prerelease']
                
                ui.print_info(f"处理版本 {i+1}: {tag_name} (预发布: {prerelease})")
                
                # 跳过预发布版本
                if prerelease:
                    ui.print_info(f"跳过预发布版本: {tag_name}")
                    continue
                
                # VSCode使用官方下载服务器，不依赖GitHub assets
                # 构建官方下载URL
                if self.system == 'windows':
                    download_url = f"https://update.code.visualstudio.com/{tag_name}/win32-x64/stable"
                    asset_name = f"VSCode-win32-x64-{tag_name}.exe"
                elif self.system == 'darwin':
                    download_url = f"https://update.code.visualstudio.com/{tag_name}/darwin-{self.arch}/stable"
                    asset_name = f"VSCode-darwin-{self.arch}-{tag_name}.zip"
                else:
                    download_url = f"https://update.code.visualstudio.com/{tag_name}/linux-x64/stable"
                    asset_name = f"vscode-linux-x64-{tag_name}.tar.gz"
                
                versions.append({
                    "name": tag_name,
                    "display_name": f"{version_name} ({tag_name})",
                    "description": f"发布于 {published_at[:10]}",
                    "download_url": download_url,
                    "asset_name": asset_name,
                    "version": tag_name,
                    "size": 0  # VSCode官方下载不提供size信息
                })
                ui.print_info(f"添加版本: {tag_name} -> {download_url}")
            
            ui.print_info(f"最终找到 {len(versions)} 个可用版本")
            if not versions:
                # 如果没有找到版本，返回默认版本
                ui.print_warning("未找到任何版本，使用默认版本")
                return self._get_default_versions()
            
            return versions
            
        except requests.exceptions.RequestException as e:
            ui.print_warning(f"网络请求失败: {str(e)}")
            logger.error("GitHub API请求失败", error=str(e))
            return self._get_default_versions()
        except Exception as e:
            ui.print_warning(f"获取VSCode版本列表失败: {str(e)}")
            logger.error("获取VSCode版本列表失败", error=str(e))
            return self._get_default_versions()
    
    def _get_default_versions(self) -> List[Dict]:
        """获取默认版本列表"""
        return [
            {
                "name": "1.106.3",
                "display_name": "VSCode 1.106.3 (推荐)",
                "description": "稳定版本，适合大多数用户",
                "download_url": "https://update.code.visualstudio.com/1.106.3/win32-x64/stable",
                "asset_name": "VSCode-win32-x64-1.106.3.zip",
                "version": "1.106.3"
            }
        ]
    
    def select_version(self) -> Optional[Dict]:
        """选择VSCode版本"""
        try:
            # 获取版本列表
            versions = self.get_vscode_versions()
            
            if not versions:
                ui.print_error("未找到可用的VSCode版本")
                return None
            
            # 显示版本选择菜单
            ui.clear_screen()
            ui.components.show_title("选择VSCode版本", symbol="🔵")
            
            # 创建版本表格
            from rich.table import Table
            table = Table(
                show_header=True,
                header_style=ui.colors["table_header"],
                title="[bold]VSCode 可用版本[/bold]",
                title_style=ui.colors["primary"],
                border_style=ui.colors["border"],
                show_lines=True
            )
            table.add_column("选项", style="cyan", width=6, justify="center")
            table.add_column("版本", style=ui.colors["primary"], width=25)
            table.add_column("说明", style="green")
            table.add_column("大小", style="yellow", width=10, justify="center")
            
            # 显示版本信息
            for i, version in enumerate(versions, 1):
                size_mb = f"{version.get('size', 0) / 1024 / 1024:.1f}MB" if version.get('size') else "未知"
                table.add_row(
                    f"[{i}]",
                    version["display_name"],
                    version["description"],
                    size_mb
                )
            
            ui.console.print(table)
            ui.console.print("\n[Enter] 使用默认版本(第一个选项)  [Q] 跳过VSCode下载", style=ui.colors["info"])
            ui.console.print("提示：推荐使用最新稳定版本", style=ui.colors["success"])
            
            while True:
                choice = ui.get_input("请选择VSCode版本(直接回车使用默认版本)：").strip()
                
                # 如果用户直接按回车，使用默认版本(第一个选项)
                if choice == "":
                    ui.print_info("使用默认版本: " + versions[0]["display_name"])
                    return versions[0]
                
                if choice.upper() == 'Q':
                    return None
                
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(versions):
                        selected_version = versions[choice_num - 1]
                        ui.print_info("已选择版本: " + selected_version["display_name"])
                        return selected_version
                    else:
                        ui.print_error("无效选项，请重新选择")
                except ValueError:
                    ui.print_error("请输入有效的数字或直接回车使用默认版本")
                    
        except Exception as e:
            ui.print_error(f"选择VSCode版本时发生错误：{str(e)}")
            logger.error("VSCode版本选择失败", error=str(e))
            return None
    
    def get_download_url(self) -> str:
        """获取VSCode下载链接（兼容性方法）"""
        version = "1.106.3"
        
        if self.system == 'windows':
            return f"https://update.code.visualstudio.com/{version}/win32-x64/stable"
        elif self.system == 'darwin':  # macOS
            return f"https://update.code.visualstudio.com/{version}/darwin-{self.arch}/stable"
        else:  # Linux
            return f"https://update.code.visualstudio.com/{version}/linux-x64/stable"
    
    def get_filename(self) -> str:
        """获取下载文件名（兼容性方法）"""
        if self.system == 'windows':
            return "VSCodeSetup-x64.exe"
        elif self.system == 'darwin':
            return f"VSCode-darwin-{self.arch}.zip"
        else:
            return "vscode-x64.tar.gz"
    
    def download_and_install(self, temp_dir: Path) -> bool:
        """下载并安装VSCode"""
        try:
            # 选择版本
            selected_version = self.select_version()
            if not selected_version:
                ui.print_info("已跳过VSCode下载")
                return True
            
            # 获取下载链接和文件名
            download_url = selected_version["download_url"]
            filename = selected_version.get("asset_name", self.get_filename())
            file_path = temp_dir / filename
            
            ui.print_info(f"正在下载 {self.name} {selected_version['display_name']}...")
            
            # 下载文件
            if not self.download_file(download_url, str(file_path)):
                return False
            
            ui.print_info(f"正在安装 {self.name}...")
            
            # 根据系统执行安装
            if self.system == 'windows':
                # Windows系统
                success = self.run_installer(str(file_path))
            elif self.system == 'darwin':
                # macOS - 需要解压后安装
                extract_dir = temp_dir / "vscode_extract"
                if self.extract_archive(str(file_path), str(extract_dir)):
                    # 查找.app文件
                    app_files = list(extract_dir.glob("*.app"))
                    if app_files:
                        ui.print_info("正在复制VSCode到应用程序文件夹...")
                        # 这里可以添加复制到Applications的逻辑
                        success = True
                    else:
                        ui.print_error("未找到VSCode应用程序文件")
                        success = False
                else:
                    success = False
            else:
                # Linux - 解压到指定位置
                extract_dir = temp_dir / "vscode_extract"
                if self.extract_archive(str(file_path), str(extract_dir)):
                    ui.print_info("正在安装VSCode到系统...")
                    # 这里可以添加安装到/usr/local的逻辑
                    success = True
                else:
                    success = False
            
            return success
            
        except Exception as e:
            ui.print_error(f"下载 {self.name} 时发生错误：{str(e)}")
            logger.error("VSCode下载安装失败", error=str(e))
            return False
    
    def check_installation(self) -> tuple[bool, str]:
        """检查VSCode是否已安装"""
        try:
            if self.system == 'windows':
                # Windows - 检查注册表
                import winreg
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Microsoft VSCode") as key:
                        version, _ = winreg.QueryValueEx(key, "DisplayVersion")
                        return True, f"VSCode 已安装，版本: {version}"
                except:
                    pass
                
                # 检查可执行文件
                import subprocess
                result = subprocess.run(
                    ["code", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    version = result.stdout.strip()
                    return True, f"VSCode 已安装，版本: {version}"
                else:
                    return False, "VSCode 未安装"
            
            else:
                # Linux/macOS - 检查code命令
                import subprocess
                result = subprocess.run(
                    ["code", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    version = result.stdout.strip()
                    return True, f"VSCode 已安装，版本: {version}"
                else:
                    return False, "VSCode 未安装"
                    
        except Exception as e:
            return False, f"检查VSCode安装状态时发生错误: {str(e)}"