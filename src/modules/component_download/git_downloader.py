# -*- coding: utf-8 -*-
"""
Git下载器
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


class GitDownloader(BaseDownloader):
    """Git下载器"""
    
    def __init__(self):
        super().__init__("Git")
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        
        # 标准化架构名称
        if self.arch in ['x86_64', 'amd64']:
            self.arch = '64'
        elif self.arch in ['arm64', 'aarch64']:
            self.arch = 'arm64'
        else:
            self.arch = '64'
    
    def get_git_versions(self) -> List[Dict]:
        """获取Git版本列表"""
        try:
            ui.print_info("正在获取Git最新版本信息...")
            
            # GitHub API获取releases
            response = requests.get(
                "https://api.github.com/repos/git-for-windows/git/releases",
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
                
                ui.print_info(f"处理版本 {i+1}: {tag_name}")
                
                # 查找Windows 64位安装包 - 放宽条件
                found_asset = None
                for asset in release['assets']:
                    asset_name = asset['name']
                    ui.print_info(f"  检查资产: {asset_name}")
                    if ('64-bit.exe' in asset_name and
                        'preview' not in asset_name.lower() and
                        'test' not in asset_name.lower()):
                        found_asset = asset
                        ui.print_info(f"  找到Git安装包: {asset_name}")
                        break
                
                if found_asset:
                    versions.append({
                        "name": tag_name,
                        "display_name": f"{version_name} ({tag_name})",
                        "description": f"发布于 {published_at[:10]}",
                        "download_url": found_asset['browser_download_url'],
                        "asset_name": found_asset['name'],
                        "version": tag_name,
                        "size": found_asset['size']
                    })
                    ui.print_info(f"添加版本: {tag_name}")
                else:
                    ui.print_info(f"未找到适合的安装包: {tag_name}")
            
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
            ui.print_warning(f"获取Git版本列表失败: {str(e)}")
            logger.error("获取Git版本列表失败", error=str(e))
            return self._get_default_versions()
    
    def _get_default_versions(self) -> List[Dict]:
        """获取默认版本列表"""
        return [
            {
                "name": "v2.43.0.windows.1",
                "display_name": "Git 2.43.0 (推荐)",
                "description": "稳定版本，适合大多数用户",
                "download_url": "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/Git-2.43.0.0-64-bit.exe",
                "asset_name": "Git-2.43.0.0-64-bit.exe",
                "version": "v2.43.0.windows.1"
            }
        ]
    
    def select_version(self) -> Optional[Dict]:
        """选择Git版本"""
        try:
            # 获取版本列表
            versions = self.get_git_versions()
            
            if not versions:
                ui.print_error("未找到可用的Git版本")
                return None
            
            # 显示版本选择菜单
            ui.clear_screen()
            ui.components.show_title("选择Git版本", symbol="🟠")
            
            # 创建版本表格
            from rich.table import Table
            table = Table(
                show_header=True,
                header_style=ui.colors["table_header"],
                title="[bold]Git 可用版本[/bold]",
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
            ui.console.print("\n[Enter] 使用默认版本(第一个选项)  [Q] 跳过Git下载", style=ui.colors["info"])
            ui.console.print("提示：推荐使用最新稳定版本", style=ui.colors["success"])
            
            while True:
                choice = ui.get_input("请选择Git版本(直接回车使用默认版本)：").strip()
                
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
            ui.print_error(f"选择Git版本时发生错误：{str(e)}")
            logger.error("Git版本选择失败", error=str(e))
            return None
    
    def get_download_url(self) -> str:
        """获取Git下载链接（兼容性方法）"""
        if self.system == 'windows':
            # Git for Windows 官方下载链接格式
            return "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/Git-2.43.0.0-64-bit.exe"
        elif self.system == 'darwin':  # macOS
            return f"https://sourceforge.net/projects/git-osx-installer/files/git-2.43.0-intel-universal-mavericks.dmg/download"
        else:  # Linux
            return "https://github.com/git/git/archive/refs/tags/v2.43.0.tar.gz"
    
    def get_filename(self) -> str:
        """获取下载文件名（兼容性方法）"""
        if self.system == 'windows':
            return "Git-2.43.0.0-64-bit.exe"
        elif self.system == 'darwin':
            return "git-2.43.0.dmg"
        else:
            return "git-2.43.0.tar.gz"
    
    def download_and_install(self, temp_dir: Path) -> bool:
        """下载并安装Git"""
        try:
            # 选择版本
            selected_version = self.select_version()
            if not selected_version:
                ui.print_info("已跳过Git下载")
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
                # ✅ Windows系统 - 使用专门的方法
                success = self._install_git_windows(str(file_path))
            elif self.system == 'darwin':
                # macOS - 提示用户手动安装
                ui.print_info("Git for macOS 需要手动安装")
                ui.print_info(f"请打开下载的文件: {file_path}")
                if ui.confirm("是否打开Git安装包？"):
                    try:
                        import os
                        os.system(f"open '{file_path}'")
                        ui.print_info("已尝试打开安装包，请按照提示完成安装")
                        return True
                    except Exception as e:
                        ui.print_error(f"打开安装包失败: {str(e)}")
                        return False
                return True
            else:
                # Linux - 提示使用包管理器
                ui.print_info("Git for Linux 推荐使用包管理器安装")
                ui.print_info("例如: sudo apt install git (Ubuntu/Debian)")
                ui.print_info("或者: sudo yum install git (CentOS/RHEL)")
                return True
            
            return success
            
        except Exception as e:
            ui.print_error(f"下载 {self.name} 时发生错误：{str(e)}")
            logger.error("Git下载安装失败", error=str(e))
            return False
    
    def check_installation(self) -> tuple[bool, str]:
        """检查Git是否已安装"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Git 已安装，版本: {version}"
            else:
                return False, "Git 未安装"
                
        except Exception as e:
            return False, f"检查Git安装状态时发生错误: {str(e)}"
    
    def _install_git_windows(self, installer_path: str) -> bool:
        """在Windows上安装Git（使用专门的安装方法）"""
        try:
            ui.print_info(f"正在运行安装程序: {os.path.basename(installer_path)}")
            
            # 检查文件是否存在
            if not os.path.exists(installer_path):
                ui.print_error(f"安装文件不存在: {installer_path}")
                return False
            
            # 检查是否有管理员权限
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            
            if is_admin:
                # 已有管理员权限，直接安装
                ui.print_info("正在以管理员权限安装...")
                result = subprocess.run(
                    [installer_path, "/SILENT", "/NORESTART", "/COMPONENTS=icons,ext/reg/shellhere,assoc,assoc_sh"],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode == 0:
                    ui.print_success(f"{self.name} 安装完成")
                    
                    # 等待安装完成并清理安装包
                    ui.print_info("等待安装程序完全退出...")
                    import time
                    time.sleep(3)  # 等待3秒确保安装程序完全退出
                    
                    return True
                else:
                    ui.print_error(f"安装失败，返回码: {result.returncode}")
                    if result.stderr:
                        ui.print_error(f"错误信息: {result.stderr}")
                    return False
            else:
                # 没有管理员权限，使用 ShellExecute 请求提权
                ui.print_info("正在请求管理员权限...")
                
                # 使用 ShellExecuteW 以管理员身份运行安装程序
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",  # 请求管理员权限
                    installer_path,
                    "/SILENT /NORESTART /COMPONENTS=icons,ext/reg/shellhere,assoc,assoc_sh",
                    None,
                    1  # SW_SHOWNORMAL
                )
                
                # 返回值 > 32 表示成功启动
                if ret > 32:
                    ui.print_success(f"{self.name} 安装程序已启动，请等待安装完成")
                    ui.print_info("注意：安装在后台进行，完成后请重新打开终端验证")
                    
                    # 等待一段时间让安装程序启动
                    import time
                    time.sleep(2)
                    
                    return True
                else:
                    error_messages = {
                        0: "系统内存不足",
                        2: "找不到文件",
                        3: "找不到路径",
                        5: "拒绝访问",
                        8: "内存不足",
                        26: "共享错误",
                        27: "文件关联不完整",
                        28: "DDE超时",
                        29: "DDE失败",
                        30: "DDE忙",
                        31: "没有关联的应用程序",
                        32: "DLL未找到",
                    }
                    error_msg = error_messages.get(ret, f"未知错误 (代码: {ret})")
                    ui.print_error(f"启动安装程序失败: {error_msg}")
                    return False
                    
        except subprocess.TimeoutExpired:
            ui.print_error("安装超时")
            return False
        except Exception as e:
            ui.print_error(f"运行安装程序时发生错误：{str(e)}")
            logger.error("安装程序运行异常", installer=installer_path, error=str(e))
            return False