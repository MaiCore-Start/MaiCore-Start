# -*- coding: utf-8 -*-
"""
插件管理模块
负责插件的查询、安装、卸载和管理
"""
import shutil
import structlog
import requests
import os
import subprocess
import datetime
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from packaging.version import parse as parse_version, Version, InvalidVersion
from ..modules.config_manager import config_mgr

logger = structlog.get_logger(__name__)

class PluginManager:
    REPO_BASE = "https://raw.githubusercontent.com/Mai-with-u/plugin-repo/main"
    PLUGINS_INDEX_URL = f"{REPO_BASE}/plugins.json"
    PLUGINS_DETAILS_URL = f"{REPO_BASE}/plugin_details.json"
    CACHE_FILE = os.path.join(os.getcwd(), "config", "plugin_cache.json")

    def __init__(self, ui):
        self.ui = ui
        self.console = ui.console
        self.plugins_index: List[Dict[str, str]] = []
        self.plugins_details: List[Dict[str, Any]] = []
        self.current_page = 0
        self.show_all = False
        self.page_size = 10

    def check_git_available(self) -> bool:
        """检查系统是否安装了Git"""
        return shutil.which("git") is not None

    def fetch_plugin_data(self, force_update: bool = False) -> bool:
        """从远程仓库获取插件数据"""
        # 如果不是强制更新，尝试从缓存加载
        if not force_update and self._load_from_cache():
            return True

        try:
            self.ui.print_info("正在获取插件列表...")
            resp = requests.get(self.PLUGINS_INDEX_URL, timeout=10)
            resp.raise_for_status()
            self.plugins_index = resp.json()

            resp_details = requests.get(self.PLUGINS_DETAILS_URL, timeout=10)
            resp_details.raise_for_status()
            self.plugins_details = resp_details.json()
            
            # 保存到缓存
            self._save_to_cache()
            return True
        except Exception as e:
            logger.error("Fetch plugin data failed", error=str(e))
            self.ui.print_error(f"获取插件列表失败: {e}")
            
            # 如果获取失败，尝试加载过期缓存作为后备
            if self._load_from_cache(ignore_expiry=True):
                self.ui.print_warning("已加载本地缓存数据（可能已过期）。")
                return True
                
            return False

    def _load_from_cache(self, ignore_expiry: bool = False) -> bool:
        """从缓存加载数据"""
        try:
            if not os.path.exists(self.CACHE_FILE):
                return False
            
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            last_updated = data.get("last_updated", 0)
            # 每天更新一次（24小时 = 86400秒）
            if not ignore_expiry and (time.time() - last_updated > 86400):
                return False
            
            self.plugins_index = data.get("index", [])
            self.plugins_details = data.get("details", [])
            return True
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return False

    def _save_to_cache(self):
        """保存数据到缓存"""
        try:
            data = {
                "last_updated": time.time(),
                "index": self.plugins_index,
                "details": self.plugins_details
            }
            # 确保目录存在
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def is_compatible(self, plugin: Dict[str, Any], instance_version: str) -> bool:
        """检查插件是否兼容当前实例版本"""
        if instance_version == "classical":
            return False

        manifest = plugin.get("manifest", {})
        host_app = manifest.get("host_application", {})
        
        # main/dev 仅显示兼容最新的插件（即没有设置 max_version）
        if instance_version in ["main", "dev"]:
            return "max_version" not in host_app

        # 语义化版本检查
        try:
            inst_v = parse_version(instance_version)
            min_v_str = host_app.get("min_version")
            max_v_str = host_app.get("max_version")

            if min_v_str:
                if inst_v < parse_version(min_v_str):
                    return False
            
            if max_v_str:
                if inst_v > parse_version(max_v_str):
                    return False
            
            return True
        except InvalidVersion:
            # 如果版本号无法解析，默认不兼容（或者可以策略宽松一点，但这里从严）
            return False

    def get_filtered_plugins(self, instance_version: str) -> List[Dict[str, Any]]:
        """获取过滤后的插件列表（倒序）"""
        # 默认显示最新的（从后往前）
        plugins = list(reversed(self.plugins_details))
        
        if not self.show_all:
            plugins = [p for p in plugins if self.is_compatible(p, instance_version)]
        
        return plugins

    def _calculate_match_score(self, plugin: Dict[str, Any], query: str) -> int:
        """计算搜索匹配分数"""
        m = plugin.get("manifest", {})
        score = 0
        query = query.lower()

        name = m.get("name", "").lower()
        keywords = [k.lower() for k in m.get("keywords", [])]
        desc = m.get("description", "").lower()
        author_name = m.get("author", {}).get("name", "").lower()
        pid = plugin.get("id", "").lower()
        license_str = m.get("license", "").lower()

        # 权重：名称(100) > 关键词(80) > 简介(60) > 作者(40) > ID(20) > 许可(10)
        if query in name: score += 100
        if any(query in k for k in keywords): score += 80
        if query in desc: score += 60
        if query in author_name: score += 40
        if query in pid: score += 20
        if query in license_str: score += 10

        return score

    def search_plugins(self, query: str, instance_version: str) -> List[Dict[str, Any]]:
        """加权模糊搜索"""
        query = query.strip().lower()
        if not query:
            return []

        results = []
        
        source_plugins = self.get_filtered_plugins(instance_version)
        
        for plugin in source_plugins:
            score = self._calculate_match_score(plugin, query)
            if score > 0:
                results.append((score, plugin))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in results]

    def _get_repo_url(self, plugin_id: str) -> Optional[str]:
        for p in self.plugins_index:
            if p.get("id") == plugin_id:
                return p.get("repositoryUrl")
        return None

    def display_plugin_table(self, plugins: List[Dict[str, Any]], title: str = "可用插件"):
        """显示插件表格"""
        table = Table(title=title, show_lines=True, header_style="bold magenta", expand=True)
        table.add_column("序号", style="dim", width=4)
        table.add_column("名称", style="cyan", ratio=2)
        table.add_column("作者", style="blue", ratio=1)
        table.add_column("版本", style="green", ratio=1)
        table.add_column("兼容版本", style="yellow", ratio=1)
        table.add_column("简介", ratio=4)

        for idx, plugin in enumerate(plugins, 1):
            m = plugin.get("manifest", {})
            host_app = m.get("host_application", {})
            min_v = host_app.get("min_version", "?")
            max_v = host_app.get("max_version", "最新")
            compat_str = f"{min_v} ~ {max_v}"
            
            table.add_row(
                str(idx),
                m.get("name", "Unknown"),
                m.get("author", {}).get("name", "Unknown"),
                m.get("version", "0.0.0"),
                compat_str,
                (m.get("description", "")[:40] + "...") if len(m.get("description", "")) > 40 else m.get("description", "")
            )
        self.console.print(table)

    def show_plugin_menu(self):
        """显示插件管理菜单"""
        if not self.check_git_available():
            self.ui.print_error("未检测到 Git，插件管理功能不可用。")
            self.ui.pause()
            return

        # 1. 选择实例
        configs = config_mgr.config.get_all_configurations()
        maibot_configs = {k: v for k, v in configs.items() if v.get("bot_type") == "MaiBot"}
        
        if not maibot_configs:
            self.ui.print_warning("没有找到 MaiBot 类型的实例。")
            self.ui.pause()
            return

        self.ui.show_instance_list(maibot_configs)
        instance_serial = self.ui.get_input("请输入要管理插件的实例序列号: ")
        
        target_config = None
        target_name = None
        for name, cfg in maibot_configs.items():
             if str(cfg.get("serial_number")) == instance_serial or str(cfg.get("absolute_serial_number")) == instance_serial:
                 target_config = cfg
                 target_name = name
                 break
        
        if not target_config:
            self.ui.print_warning("无效的实例序列号。")
            self.ui.pause()
            return

        instance_version = target_config.get("version_path", "0.0.0")
        if instance_version == "classical":
            self.ui.print_warning("Classical 版本不支持插件功能。")
            self.ui.pause()
            return

        # 获取数据 (默认不强制更新，使用缓存)
        if not self.fetch_plugin_data(force_update=False):
            self.ui.pause()
            return

        while True:
            self.ui.clear_screen()
            self.ui.components.show_title(f"插件管理 - {target_config.get('nickname_path', target_name)}", symbol="plugin")
            
            all_filtered = self.get_filtered_plugins(instance_version)
            total_pages = (len(all_filtered) + self.page_size - 1) // self.page_size
            if total_pages == 0: total_pages = 1
            if self.current_page >= total_pages: self.current_page = 0
            
            start_idx = self.current_page * self.page_size
            end_idx = start_idx + self.page_size
            current_batch = all_filtered[start_idx:end_idx]
            
            title = f"可用插件 (第 {self.current_page + 1}/{total_pages} 页) - {'[全部]' if self.show_all else '[仅兼容]'}"
            self.display_plugin_table(current_batch, title)
            
            self.console.print("\n[操作选项]")
            self.console.print(r" \[1-10] 选择插件查看详情")
            self.console.print(r" \[/*关键词*/] 搜索插件")
            self.console.print(rf" \[A] 切换：{'显示全部' if not self.show_all else '仅兼容'}")
            if total_pages > 1:
                nav_options = []
                if self.current_page > 0:
                    nav_options.append("[P] 上一页")
                if self.current_page < total_pages - 1:
                    nav_options.append("[N] 下一页")
                if nav_options:
                    self.console.print(f" \{' '.join(nav_options)}")
            self.console.print(r" \[M] 插件管理菜单 (刷新/扫描/管理/导入)")
            self.console.print(r" \[Q] 返回")
            
            choice = self.ui.get_input("请选择操作: ")
            choice_upper = choice.upper()
            
            if choice_upper == 'Q':
                break
            elif choice_upper == 'A':
                self.show_all = not self.show_all
                self.current_page = 0
                continue
            elif choice_upper == 'N' and total_pages > 1 and self.current_page < total_pages - 1:
                self.current_page += 1
                continue
            elif choice_upper == 'P' and total_pages > 1 and self.current_page > 0:
                self.current_page -= 1
                continue
            elif choice_upper == 'M':
                self.show_manage_submenu(target_name, target_config)
                continue
            elif choice.startswith("/*") and choice.endswith("*/"):
                keyword = choice[2:-2]
                search_results = self.search_plugins(keyword, instance_version)
                self.show_search_results(search_results, target_name, target_config)
                continue
            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(current_batch):
                    selected_plugin = current_batch[idx-1]
                    self.show_plugin_details(selected_plugin, target_name, target_config)
                else:
                    self.ui.print_warning("无效的序号。")
                    self.ui.pause()
            else:
                pass

    def show_manage_submenu(self, instance_name: str, instance_config: Dict[str, Any]):
        """显示插件管理子菜单"""
        while True:
            self.ui.clear_screen()
            self.ui.components.show_title(f"插件管理菜单 - {instance_config.get('nickname_path', instance_name)}", symbol="plugin")
            
            self.console.print("\n[功能选项]")
            self.console.print(r" \[R] 刷新插件列表 | \[S] 扫描本地插件 | \[M] 管理已安装 | \[Q] 返回")
            self.console.print(r" \[I] 导入本地插件文件夹 | \[U] 检查更新")
            
            choice = self.ui.get_input("请选择操作: ")
            choice_upper = choice.upper()
            
            if choice_upper == 'Q':
                break
            elif choice_upper == 'R':
                self.fetch_plugin_data(force_update=True)
                self.ui.print_success("插件列表已刷新。")
                self.ui.pause()
            elif choice_upper == 'S':
                self.scan_local_plugins(instance_name, instance_config)
                self.ui.pause()
            elif choice_upper == 'M':
                self.manage_installed_plugins(instance_name, instance_config)
            elif choice_upper == 'I':
                self.import_local_plugin_folder(instance_name, instance_config)
                self.ui.pause()
            elif choice_upper == 'U':
                self.check_for_updates(instance_name, instance_config)

    def import_local_plugin_folder(self, instance_name: str, instance_config: Dict[str, Any]):
        """导入本地插件文件夹"""
        bot_path = instance_config.get("mai_path")
        if not bot_path or not os.path.exists(bot_path):
             self.ui.print_error("实例路径无效或不存在。")
             return

        source_path = self.ui.get_input("请输入插件文件夹路径: ")
        if not os.path.isdir(source_path):
            self.ui.print_error("输入的路径无效或不是文件夹。")
            return

        manifest_path = os.path.join(source_path, "_manifest.json")
        init_path = os.path.join(source_path, "plugin.py")
        
        if not (os.path.exists(manifest_path) and os.path.exists(init_path)):
            self.ui.print_error("文件夹中缺少 _manifest.json 或 plugin.py，不是有效的插件目录。")
            return

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # 简单验证
            if not manifest.get("name") or not manifest.get("version"):
                self.ui.print_warning("插件 manifest 缺少必要信息 (name, version)。")
                if not self.ui.confirm("是否继续导入？"):
                    return
            
            plugin_folder_name = os.path.basename(os.path.normpath(source_path))
            target_plugins_dir = os.path.join(bot_path, "plugins")
            if not os.path.exists(target_plugins_dir):
                os.makedirs(target_plugins_dir)
                
            target_path = os.path.join(target_plugins_dir, plugin_folder_name)
            
            if os.path.exists(target_path):
                self.ui.print_warning(f"目标目录已存在: {target_path}")
                if not self.ui.confirm("是否覆盖？"):
                    return
                # 删除旧目录
                def on_rm_error(func, path, exc_info):
                    os.chmod(path, 0o777)
                    func(path)
                shutil.rmtree(target_path, onerror=on_rm_error)

            # 复制目录
            self.ui.print_info("正在复制插件文件...")
            shutil.copytree(source_path, target_path)
            
            # 注册插件
            # 使用文件夹名作为ID，或者尝试从manifest中获取ID（如果标准规定了的话，这里假设用文件夹名或者让用户确认）
            # 这里的逻辑是：如果导入的是标准插件包，通常文件夹名就是ID
            plugin_id = plugin_folder_name
            
            self._add_plugin_to_config(instance_name, plugin_id)
            self.ui.print_success(f"插件 {manifest.get('name')} ({plugin_id}) 导入成功！")
            
        except Exception as e:
            self.ui.print_error(f"导入插件失败: {e}")

    def scan_local_plugins(self, instance_name: str, instance_config: Dict[str, Any]):
        """扫描本地插件并导入"""
        bot_path = instance_config.get("mai_path")
        if not bot_path or not os.path.exists(bot_path):
             self.ui.print_error("实例路径无效或不存在。")
             return

        plugins_dir = os.path.join(bot_path, "plugins")
        if not os.path.exists(plugins_dir):
            self.ui.print_warning("插件目录不存在。")
            return

        self.ui.print_info(f"正在扫描本地插件: {plugins_dir}")
        found_plugins = []
        
        try:
            for item in os.listdir(plugins_dir):
                plugin_path = os.path.join(plugins_dir, item)
                if os.path.isdir(plugin_path):
                    manifest_path = os.path.join(plugin_path, "_manifest.json")
                    init_path = os.path.join(plugin_path, "plugin.py")
                    
                    if os.path.exists(manifest_path) and os.path.exists(init_path):
                        # 验证manifest
                        try:
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                manifest = json.load(f)
                            
                            required_keys = ["manifest_version", "name", "version", "description", "author"]
                            if all(k in manifest for k in required_keys) and "name" in manifest.get("author", {}):
                                found_plugins.append((item, manifest))
                            else:
                                logger.warning(f"插件 {item} 的 _manifest.json 格式不正确")
                        except Exception as e:
                            logger.warning(f"读取插件 {item} 的 _manifest.json 失败: {e}")
        except Exception as e:
            self.ui.print_error(f"扫描过程发生错误: {e}")
            return

        if not found_plugins:
            self.ui.print_info("未发现新的有效本地插件。")
            return

        self.ui.print_success(f"发现 {len(found_plugins)} 个有效插件，开始导入...")
        
        imported_count = 0
        for plugin_id, manifest in found_plugins:
            # 检查是否已注册
            installed_list = instance_config.get("plugins", [])
            is_registered = False
            if isinstance(installed_list, list):
                for p in installed_list:
                    if p.get("id") == plugin_id:
                        is_registered = True
                        break
            
            if not is_registered:
                self._add_plugin_to_config(instance_name, plugin_id)
                self.console.print(f" [green]+[/green] 已注册插件: {manifest.get('name')} ({plugin_id})")
                imported_count += 1
            else:
                self.console.print(f" [yellow]=[/yellow] 插件已存在: {manifest.get('name')} ({plugin_id})")

        if imported_count > 0:
            self.ui.print_success(f"成功导入 {imported_count} 个新插件。")
        else:
            self.ui.print_info("所有插件均已注册，无需更新。")

    def show_search_results(self, results: List[Dict[str, Any]], instance_name: str, instance_config: Dict[str, Any]):
        """显示搜索结果"""
        while True:
            self.ui.clear_screen()
            self.display_plugin_table(results, "搜索结果")
            
            self.console.print("\n[操作选项]")
            self.console.print(r" \[数字] 查看详情")
            self.console.print(r" \[Q] 返回上一级")
            
            choice = self.ui.get_input("请选择操作: ")
            
            if choice.upper() == 'Q':
                break
            
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(results):
                    selected_plugin = results[idx-1]
                    self.show_plugin_details(selected_plugin, instance_name, instance_config)
                else:
                    self.ui.print_warning("无效的序号。")
                    self.ui.pause()

    def show_plugin_details(self, plugin_data: Dict[str, Any], instance_name: str, instance_config: Dict[str, Any]):
        """显示插件详情并提供安装选项"""
        self.ui.clear_screen()
        m = plugin_data.get("manifest", {})
        
        keywords = ", ".join(m.get("keywords", []))
        host_app = m.get("host_application", {})
        compat_str = f"{host_app.get('min_version', '?')} ~ {host_app.get('max_version', '最新')}"
        
        detail_text = (
            f"[bold]ID:[/bold] {plugin_data.get('id')}\n"
            f"[bold cyan]名称:[/bold cyan] {m.get('name')}\n"
            f"[bold green]版本:[/bold green] {m.get('version')}\n"
            f"[bold blue]作者:[/bold blue] {m.get('author', {}).get('name')}\n"
            f"[bold]简介:[/bold] {m.get('description')}\n"
            f"[bold yellow]兼容版本:[/bold yellow] {compat_str}\n"
            f"[bold]开源许可:[/bold] {m.get('license')}\n"
            f"[bold]清单版本:[/bold] {m.get('manifest_version')}\n"
            f"[bold]关键词:[/bold] {keywords}\n"
            f"[bold]语言:[/bold] {m.get('default_locale', 'N/A')}\n"
        )
        
        self.console.print(Panel(Text.from_markup(detail_text), title="插件详情", expand=False))
        
        # 检查是否已安装
        is_installed = False
        installed_list = instance_config.get("plugins", [])
        if isinstance(installed_list, list):
             for p in installed_list:
                 if p.get("id") == plugin_data.get("id"):
                     is_installed = True
                     break
        
        self.console.print("\n[操作选项]")
        if is_installed:
             self.console.print(r" \[U] 卸载 (已安装)")
             self.console.print(r" \[I] 重新安装")
        else:
             self.console.print(r" \[I] 安装")
        self.console.print(r" \[Q] 返回")
        
        choice = self.ui.get_input("请选择操作: ").upper()
        
        if choice == 'I':
            self.install_plugin(plugin_data, instance_name, instance_config)
        elif choice == 'U' and is_installed:
            if self.ui.confirm("确定要卸载此插件吗？"):
                self.uninstall_plugin(plugin_data.get("id"), instance_name, instance_config)
                self.ui.pause()

    def install_plugin(self, plugin_data: Dict[str, Any], instance_name: str, instance_config: Dict[str, Any]):
        """安装插件"""
        plugin_id = plugin_data.get("id")
        repo_url = self._get_repo_url(plugin_id)
        
        if not repo_url:
            self.ui.print_error("未找到插件仓库地址。")
            self.ui.pause()
            return
            
        bot_path = instance_config.get("mai_path")
        if not bot_path or not os.path.exists(bot_path):
             self.ui.print_error("实例路径无效或不存在。")
             self.ui.pause()
             return

        plugins_dir = os.path.join(bot_path, "plugins")
        target_dir = os.path.join(plugins_dir, plugin_id)
        
        if os.path.exists(target_dir):
            if not self.ui.confirm("插件目录已存在，是否覆盖安装？"):
                return
            try:
                def on_rm_error(func, path, exc_info):
                    os.chmod(path, 0o777)
                    func(path)
                shutil.rmtree(target_dir, onerror=on_rm_error)
            except Exception as e:
                self.ui.print_error(f"删除旧目录失败: {e}")
                self.ui.pause()
                return
        
        # 确保 plugins 目录存在
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)

        self.ui.print_info(f"正在从 {repo_url} 克隆插件...")
        try:
            result = subprocess.run(["git", "clone", repo_url, target_dir], capture_output=True, text=True)
            
            if result.returncode == 0:
                # 更新配置
                self._add_plugin_to_config(instance_name, plugin_id)
                self.ui.print_success(f"插件 {plugin_id} 安装成功！")
            else:
                self.ui.print_error(f"Git clone 失败: {result.stderr}")
            
            self.ui.pause()
        except Exception as e:
            self.ui.print_error(f"安装过程发生错误: {e}")
            self.ui.pause()

    def _add_plugin_to_config(self, instance_name: str, plugin_id: str):
        """添加插件记录到config.toml"""
        configs = config_mgr.config.get_all_configurations()
        if instance_name in configs:
            config = configs[instance_name]
            if "plugins" not in config or not isinstance(config["plugins"], list):
                config["plugins"] = []
            
            # 移除旧记录（如果存在）
            config["plugins"] = [p for p in config["plugins"] if p.get("id") != plugin_id]
            
            # 添加新记录
            config["plugins"].append({
                "id": plugin_id,
                "installed_at": datetime.datetime.now().isoformat()
            })
            config_mgr.config.save()

    def _remove_plugin_from_config(self, instance_name: str, plugin_id: str):
        """从config.toml移除插件记录"""
        configs = config_mgr.config.get_all_configurations()
        if instance_name in configs:
            config = configs[instance_name]
            if "plugins" in config and isinstance(config["plugins"], list):
                config["plugins"] = [p for p in config["plugins"] if p.get("id") != plugin_id]
                config_mgr.config.save()

    def manage_installed_plugins(self, instance_name: str, instance_config: Dict[str, Any]):
        """管理已安装插件"""
        while True:
            self.ui.clear_screen()
            installed_list = instance_config.get("plugins", [])
            
            if not installed_list or not isinstance(installed_list, list):
                self.ui.print_info("当前实例未安装任何插件。")
                self.ui.pause()
                return

            table = Table(title="已安装插件", show_lines=True, header_style="bold magenta", expand=True)
            table.add_column("序号", width=4)
            table.add_column("ID", style="cyan")
            table.add_column("安装时间", style="dim")
            
            for idx, p in enumerate(installed_list, 1):
                table.add_row(str(idx), p.get("id", "Unknown"), p.get("installed_at", "N/A"))
            
            self.console.print(table)
            self.console.print("\n[操作选项]")
            self.console.print(r" \[数字] 选择插件进行卸载")
            self.console.print(r" \[Q] 返回")
            
            choice = self.ui.get_input("请选择操作: ")
            
            if choice.upper() == 'Q':
                break
            
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(installed_list):
                    plugin_to_remove = installed_list[idx-1]
                    plugin_id = plugin_to_remove.get("id")
                    if self.ui.confirm(f"确定要卸载插件 {plugin_id} 吗？"):
                        self.uninstall_plugin(plugin_id, instance_name, instance_config)
                        self.ui.pause()
                else:
                    self.ui.print_warning("无效的序号。")
                    self.ui.pause()

    def uninstall_plugin(self, plugin_id: str, instance_name: str, instance_config: Dict[str, Any]):
        """卸载插件"""
        bot_path = instance_config.get("mai_path")
        if not bot_path:
             self.ui.print_error("实例路径无效。")
             return

        target_dir = os.path.join(bot_path, "plugins", plugin_id)
        
        try:
            if os.path.exists(target_dir):
                def on_rm_error(func, path, exc_info):
                    os.chmod(path, 0o777)
                    func(path)
                shutil.rmtree(target_dir, onerror=on_rm_error)
            else:
                self.ui.print_warning("插件目录不存在，仅清除配置记录。")
            
            self._remove_plugin_from_config(instance_name, plugin_id)
            self.ui.print_success(f"插件 {plugin_id} 卸载成功！")
        except Exception as e:
            self.ui.print_error(f"卸载失败: {e}")

    def check_for_updates(self, instance_name: str, instance_config: Dict[str, Any]):
        """检查插件更新"""
        self.ui.print_info("正在检查更新...")
        # 确保拥有最新的远程数据
        if not self.fetch_plugin_data(force_update=False):
             self.ui.print_error("无法获取远程插件信息，无法检查更新。")
             self.ui.pause()
             return

        bot_path = instance_config.get("mai_path")
        if not bot_path:
             self.ui.print_error("实例路径无效。")
             self.ui.pause()
             return

        installed_list = instance_config.get("plugins", [])
        if not installed_list:
            self.ui.print_info("没有已安装的插件。")
            self.ui.pause()
            return

        updates = []
        
        for p_rec in installed_list:
            p_id = p_rec.get("id")
            # 查找本地 manifest
            local_plugin_dir = os.path.join(bot_path, "plugins", p_id)
            manifest_path = os.path.join(local_plugin_dir, "_manifest.json")
            
            if not os.path.exists(manifest_path):
                continue
                
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    local_manifest = json.load(f)
                local_version_str = local_manifest.get("version", "0.0.0")
            except Exception:
                continue

            # 查找远程信息
            remote_plugin = next((rp for rp in self.plugins_details if rp.get("id") == p_id), None)
            if not remote_plugin:
                continue
            
            remote_manifest = remote_plugin.get("manifest", {})
            remote_version_str = remote_manifest.get("version", "0.0.0")
            
            try:
                if parse_version(remote_version_str) > parse_version(local_version_str):
                    updates.append({
                        "id": p_id,
                        "name": local_manifest.get("name", p_id),
                        "local_version": local_version_str,
                        "remote_version": remote_version_str,
                        "path": local_plugin_dir
                    })
            except Exception:
                pass

        if not updates:
            self.ui.print_success("所有插件均为最新版本！")
            self.ui.pause()
            return

        while True:
            self.ui.clear_screen()
            self.ui.components.show_title("发现更新", symbol="update")
            
            table = Table(title=f"发现 {len(updates)} 个可用更新", show_lines=True, header_style="bold magenta", expand=True)
            table.add_column("序号", width=4)
            table.add_column("插件名称", style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("当前版本", style="yellow")
            table.add_column("最新版本", style="green")
            
            for idx, up in enumerate(updates, 1):
                table.add_row(
                    str(idx),
                    up["name"],
                    up["id"],
                    up["local_version"],
                    up["remote_version"]
                )
            
            self.console.print(table)
            self.console.print("\n[操作选项]")
            self.console.print(r" \[A] 更新全部")
            self.console.print(r" \[数字] 更新单个")
            self.console.print(r" \[Q] 返回")
            
            choice = self.ui.get_input("请选择操作: ").upper()
            
            if choice == 'Q':
                break
            elif choice == 'A':
                for up in updates:
                    self._perform_update(up, instance_name)
                self.ui.pause()
                break
            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(updates):
                    self._perform_update(updates[idx-1], instance_name)
                    updates.pop(idx-1)
                    if not updates:
                        self.ui.print_success("所有更新已完成！")
                        self.ui.pause()
                        break
                    self.ui.pause()
                else:
                    self.ui.print_warning("无效的序号。")
                    self.ui.pause()

    def _perform_update(self, update_info: Dict[str, Any], instance_name: str):
        """执行更新操作"""
        p_id = update_info["id"]
        path = update_info["path"]
        name = update_info["name"]
        
        self.ui.print_info(f"正在更新 {name} ({p_id})...")
        
        # 检查是否是 git 仓库
        git_dir = os.path.join(path, ".git")
        if os.path.exists(git_dir) and self.check_git_available():
            try:
                res = subprocess.run(["git", "pull"], cwd=path, capture_output=True, text=True)
                if res.returncode == 0:
                    self.ui.print_success(f"{name} 更新成功！")
                    self._add_plugin_to_config(instance_name, p_id)
                else:
                    self.ui.print_error(f"{name} 更新失败: {res.stderr}")
            except Exception as e:
                self.ui.print_error(f"{name} 更新出错: {e}")
        else:
            # 不是 git 仓库，尝试重新安装
            repo_url = self._get_repo_url(p_id)
            if repo_url:
                if self.ui.confirm(f"{name} 不是 Git 仓库，是否删除并重新克隆以更新？"):
                    try:
                        def on_rm_error(func, path, exc_info):
                            os.chmod(path, 0o777)
                            func(path)
                        shutil.rmtree(path, onerror=on_rm_error)
                        
                        res = subprocess.run(["git", "clone", repo_url, path], capture_output=True, text=True)
                        if res.returncode == 0:
                            self.ui.print_success(f"{name} 重新安装成功！")
                            self._add_plugin_to_config(instance_name, p_id)
                        else:
                            self.ui.print_error(f"{name} 重新安装失败: {res.stderr}")
                    except Exception as e:
                         self.ui.print_error(f"{name} 更新出错: {e}")
            else:
                 self.ui.print_warning(f"无法更新 {name}: 未找到远程仓库地址且不是 Git 仓库。")
