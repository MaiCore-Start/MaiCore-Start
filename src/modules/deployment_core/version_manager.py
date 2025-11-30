# -*- coding: utf-8 -*-
"""
版本管理模块
负责从GitHub获取版本列表、更新日志等
"""
import time
from typing import Dict, List, Optional
import requests
import structlog
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class VersionManager:
    """版本管理器，负责获取和管理Bot版本信息"""
    
    def __init__(self, repo: str):
        """
        初始化版本管理器
        
        Args:
            repo: GitHub仓库名称，格式为 "owner/repo"
        """
        self.repo = repo
        self.github_api_base = "https://api.github.com"
        
        # 缓存
        self._versions_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5分钟缓存
        
        # 支持的分支
        self.supported_branches = ["main", "dev", "classical","master"]
        
        # 离线模式标志
        self._offline_mode = False
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache_timestamp is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_duration
    
    def get_github_releases(self, include_prerelease: bool = True) -> List[Dict]:
        """从GitHub API获取releases信息"""
        try:
            url = f"{self.github_api_base}/repos/{self.repo}/releases"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            releases = response.json()
            if not include_prerelease:
                releases = [r for r in releases if not r.get("prerelease", False)]
            
            logger.info("成功获取releases", repo=self.repo, count=len(releases))
            return releases
                
        except requests.RequestException as e:
            ui.print_warning(f"获取releases失败: {str(e)}")
            logger.error("获取releases失败", repo=self.repo, error=str(e))
            return []
        except Exception as e:
            ui.print_error(f"获取releases时发生错误: {str(e)}")
            logger.error("获取releases异常", repo=self.repo, error=str(e))
            return []
    
    def get_github_branches(self) -> List[Dict]:
        """获取GitHub分支信息"""
        try:
            url = f"{self.github_api_base}/repos/{self.repo}/branches"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            branches = response.json()
            logger.info("成功获取branches", repo=self.repo, count=len(branches))
            return branches
            
        except requests.RequestException as e:
            ui.print_warning(f"获取分支信息失败: {str(e)}")
            logger.error("获取branches失败", repo=self.repo, error=str(e))
            return []
    
    def get_versions(self, force_refresh: bool = False) -> List[Dict]:
        """
        获取版本列表（包括releases和分支）
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            版本列表
        """
        if not force_refresh and self._is_cache_valid() and self._versions_cache:
            return self._versions_cache
        
        versions = []
        
        # 离线模式下返回默认分支
        if self._offline_mode:
            ui.print_info("离线模式：使用默认分支选项")
            versions = [
                {
                    "name": "main",
                    "display_name": "main分支 (最新开发版)",
                    "type": "branch",
                    "description": "最新开发版本，可能包含未稳定的功能",
                    "download_url": f"https://codeload.github.com/{self.repo}/zip/refs/heads/main",
                    "published_at": "",
                    "changelog": "离线模式下无法获取更新日志"
                }
            ]
            return versions
        
        # 在线模式正常获取版本信息
        try:
            # 获取releases
            ui.print_info("正在获取版本信息...")
            releases = self.get_github_releases(include_prerelease=True)
            
            for release in releases:
                version_info = {
                    "name": release.get("tag_name", ""),
                    "display_name": release.get("name", release.get("tag_name", "")),
                    "type": "release",
                    "description": release.get("body", "")[:100] + "..." if release.get("body") else "",
                    "download_url": f"https://codeload.github.com/{self.repo}/zip/refs/tags/{release.get('tag_name', '')}",
                    "published_at": release.get("published_at", ""),
                    "prerelease": release.get("prerelease", False),
                    "changelog": release.get("body", "暂无更新日志")
                }
                versions.append(version_info)
            
            # 获取分支
            branches = self.get_github_branches()
            for branch in branches:
                branch_name = branch.get("name", "")
                if branch_name in self.supported_branches:
                    version_info = {
                        "name": branch_name,
                        "display_name": f"{branch_name}分支",
                        "type": "branch",
                        "description": f"{branch_name}分支的最新代码",
                        "download_url": f"https://codeload.github.com/{self.repo}/zip/refs/heads/{branch_name}",
                        "published_at": "",
                        "changelog": "分支无固定更新日志"
                    }
                    versions.append(version_info)
            
        except Exception as e:
            ui.print_error(f"获取版本信息失败: {str(e)}")
            logger.error("获取版本信息失败", repo=self.repo, error=str(e))
            # 返回默认版本
            versions = self._get_default_versions()
        
        # 更新缓存
        self._versions_cache = versions
        self._cache_timestamp = time.time()
        
        return versions
    
    def _get_default_versions(self) -> List[Dict]:
        """获取默认版本列表（离线或失败时使用）"""
        return [
            {
                "name": "main",
                "display_name": "main分支 (默认)",
                "type": "branch",
                "description": "最新主分支版本",
                "download_url": f"https://codeload.github.com/{self.repo}/zip/refs/heads/main",
                "published_at": "",
                "changelog": "默认版本，无法获取详细信息"
            },
            {
                "name": "dev",
                "display_name": "dev分支",
                "type": "branch",
                "description": "开发分支",
                "download_url": f"https://codeload.github.com/{self.repo}/zip/refs/heads/dev",
                "published_at": "",
                "changelog": "默认版本，无法获取详细信息"
            }
        ]
    
    def show_version_menu(self, bot_name: str = "Bot") -> Optional[Dict]:
        """
        显示版本选择菜单
        
        Args:
            bot_name: Bot名称，用于显示
            
        Returns:
            选中的版本信息，如果取消则返回None
        """
        ui.clear_screen()
        ui.components.show_title(f"选择部署版本 - {bot_name}", symbol="🚀")

        # 获取版本列表
        ui.print_info("正在获取最新版本信息...")
        versions = self.get_versions()

        while not versions:
            ui.print_error("无法获取版本列表")
            if not ui.confirm("是否重试？"):
                return None
            versions = self.get_versions(force_refresh=True)

        # 创建版本表格
        from ...core.p_config import p_config_manager
        
        table = Table(
            show_header=True,
            header_style=ui.colors["table_header"],
            title=f"[bold]{bot_name} 可用版本[/bold]",
            title_style=ui.colors["primary"],
            border_style=ui.colors["border"],
            show_lines=True
        )
        table.add_column("选项", style="cyan", width=6, justify="center")
        table.add_column("版本", style=ui.colors["primary"], width=20)
        table.add_column("类型", style="yellow", width=10, justify="center")
        table.add_column("说明", style="green", width=40)
        table.add_column("发布时间", style=ui.colors["blue"], width=12, justify="center")

        # 获取要显示的版本数量
        max_display = p_config_manager.get("display.max_versions_display", 20)
        
        # 如果max_display为None、0或负数，则显示所有版本
        if max_display and max_display > 0:
            display_versions = versions[:max_display]
        else:
            display_versions = versions

        for i, version in enumerate(display_versions, 1):
            version_type = version.get("type", "release")
            published_at = version.get("published_at", "")
            
            # 格式化发布时间
            if published_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    published_str = dt.strftime("%Y-%m-%d")
                except:
                    published_str = published_at[:10] if len(published_at) >= 10 else "未知"
            else:
                published_str = "-"
            
            # 类型显示
            type_str = "分支" if version_type == "branch" else "发行版"
            if version.get("prerelease"):
                type_str = "预发布"
            
            table.add_row(
                f"[{i}]",
                version["display_name"],
                type_str,
                version.get("description", "")[:40],
                published_str
            )

        ui.console.print(table)
        ui.console.print("\n[C] 查看版本更新日志  [R] 刷新版本列表  [Q] 返回上级菜单", style=ui.colors["info"])
        
        while True:
            choice = ui.get_input(f"请选择版本序号 (1-{len(display_versions)}): ").strip()
            
            if choice.upper() == 'Q':
                return None
            
            if choice.upper() == 'R':
                ui.print_info("正在刷新版本列表...")
                versions = self.get_versions(force_refresh=True)
                return self.show_version_menu(bot_name)
            
            if choice.upper() == 'C':
                self.show_changelog_menu(display_versions)
                return self.show_version_menu(bot_name)
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(display_versions):
                    selected = display_versions[idx]
                    ui.print_info(f"已选择版本: {selected['display_name']}")
                    return selected
                else:
                    ui.print_error(f"无效的序号，请输入 1-{len(display_versions)} 之间的数字")
            except ValueError:
                ui.print_error("请输入有效的数字或命令")
    
    def show_changelog_menu(self, versions: List[Dict]):
        """显示版本更新日志菜单"""
        ui.clear_screen()
        ui.components.show_title("版本更新日志", symbol="📋")

        # 显示版本列表供选择
        table = Table(
            show_header=True,
            header_style=ui.colors["table_header"],
            border_style=ui.colors["border"]
        )
        table.add_column("序号", style="cyan", width=6, justify="center")
        table.add_column("版本", style=ui.colors["primary"], width=25)
        table.add_column("类型", style="yellow", width=10, justify="center")

        for i, version in enumerate(versions, 1):
            version_type = "分支" if version.get("type") == "branch" else "发行版"
            if version.get("prerelease"):
                version_type = "预发布"
            table.add_row(f"[{i}]", version["display_name"], version_type)

        ui.console.print(table)
        ui.console.print("\n输入版本序号查看更新日志，或按Q返回", style=ui.colors["info"])
        
        while True:
            choice = ui.get_input("请选择: ").strip()
            
            if choice.upper() == 'Q':
                return
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(versions):
                    self.show_version_changelog(versions[idx])
                    ui.pause()
                    ui.clear_screen()
                    ui.components.show_title("版本更新日志", symbol="📋")
                    ui.console.print(table)
                    ui.console.print("\n输入版本序号查看更新日志，或按Q返回", style=ui.colors["info"])
                else:
                    ui.print_error(f"无效的序号")
            except ValueError:
                ui.print_error("请输入有效的数字")
    
    def show_version_changelog(self, version: Dict):
        """显示特定版本的更新日志"""
        ui.clear_screen()
        ui.components.show_title(f"版本更新日志 - {version['display_name']}", symbol="📋")
        
        changelog = version.get("changelog", "暂无更新日志")
        
        # 使用Markdown渲染更新日志
        try:
            md = Markdown(changelog)
            panel = Panel(
                md,
                title=f"[bold]{version['display_name']}[/bold]",
                title_align="left",
                border_style=ui.colors["border"]
            )
            ui.console.print(panel)
        except Exception as e:
            # 如果Markdown渲染失败，直接显示文本
            ui.console.print(changelog)
            logger.warning("Markdown渲染失败，使用纯文本显示", error=str(e))
    
    def set_offline_mode(self, offline: bool):
        """设置离线模式"""
        self._offline_mode = offline
