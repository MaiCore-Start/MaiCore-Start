# -*- coding: utf-8 -*-
"""
UI菜单模块
负责定义和显示各种菜单
"""
import json
import random
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from .theme import COLORS, SYMBOLS


class Menus:
    """菜单类"""

    def __init__(self, console: Console):
        self.console = console
        self.colors = COLORS
        self.symbols = SYMBOLS
        self.daily_quote = self._load_daily_quote()

    def _load_daily_quote(self):
        """从JSON文件加载随机每日一言"""
        try:
            # 获取项目根目录路径
            project_root = Path(__file__).parent.parent.parent
            quote_file = project_root / "data" / "Golden_sentence.json"
            
            with open(quote_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                quotes = data.get("goldenQuotes", [])
                if quotes:
                    return random.choice(quotes)["content"]
                else:
                    return "促进多元化艺术创作发展普及"
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # 如果文件不存在或解析失败，返回默认文字
            return "促进多元化艺术创作发展普及"

    def refresh_daily_quote(self):
        """刷新每日一言"""
        self.daily_quote = self._load_daily_quote()
        return self.daily_quote

    def print_header(self):
        """打印程序头部"""
        header_text = (
 """
ooo        ooooo  .oooooo.           .oooooo..o     .                          .   
 &&.       .&&&` d&P`  `Y&b         d&P`    `Y&   .o&                        .o&  
 &&&b     d'&&& &&&                 Y&&bo.      .o&&&oo  .oooo.   ooo  q&b .o&&&oo
 & Y&&. .P  &&& &&&         &&&&&&&  `*Y&&&&o.    &&&   `P  )&&   `&&&``&P   &&&  
 &  `&&&'   &&& &&&         *******      `“Y&&b   &&&    .oP&&&    &&&       &&&  
 &    Y     &&& `&&b    ooo         oo     .d&P   &&& . d&(  &&&   &&&       &&& .
o&o        o&&&o `Y&bood&P'         &*`&&&&&P'    `&&&` `Y&&&``qo d&&&b      `&&&`
"""
        )
        self.console.print(header_text, style=self.colors["header"])
        # 每日一言和刷新选项在同一行显示，用 | 分割
        self.console.print(f"{self.daily_quote} | [R] {self.symbols['refresh']} 刷新", style=self.colors["header"])
        self.console.print(f"\n{self.symbols['rocket']} 麦麦核心启动器控制台", style=self.colors["header"])
        self.console.print("——————————", style=self.colors["border"])
        self.console.print("选择选项", style=self.colors["border"])

    def show_main_menu(self):
        """显示主菜单"""
        self.print_header()
        
        self.console.print("====>>启动类<<====")
        self.console.print(f" [A] {self.symbols['rocket']} 运行麦麦", style=self.colors["success"])
        
        self.console.print("====>>配置类<<====")
        self.console.print(f" [B] {self.symbols['config']} 配置管理（新建/修改/检查配置）", style=self.colors["warning"])
        
        self.console.print("====>>功能类<<====")
        self.console.print(f" [C] {self.symbols['knowledge']} 知识库构建", style=self.colors["secondary"])
        self.console.print(f" [D] {self.symbols['database']} 数据库迁移（MongoDB → SQLite）", style=self.colors["secondary"])
        self.console.print(f" [E] {self.symbols['plugin']} 插件管理（目前只是一个ui）", style=self.colors["primary"])
        
        self.console.print("====>>部署类<<====")
        self.console.print(f" [F] {self.symbols['deployment']} 实例部署辅助系统", style=self.colors["error"])
        
        self.console.print("====>>进程管理<<====")
        self.console.print(f" [G] {self.symbols['status']} 查看运行状态", style=self.colors["info"])
        
        self.console.print("====>>杂项类<<====")
        self.console.print(f" [H] {self.symbols['config']} 杂项（关于/程序设置）", style=self.colors["info"])
        
        self.console.print("====>>退出类<<====")
        self.console.print(f" [Q] {self.symbols['quit']} 退出程序", style=self.colors["exit"])

    def show_config_menu(self):
        """显示配置菜单"""
        panel = Panel(
            f"[{self.symbols['config']} 配置管理]",
            style=self.colors["warning"],
            title="配置管理"
        )
        self.console.print(panel)
        
        self.console.print("====>>配置新建<<====")
        self.console.print(f" [A] {self.symbols['new']} 自动检索麦麦", style=self.colors["success"])
        self.console.print(f" [B] {self.symbols['edit']} 手动配置", style=self.colors["success"])
        
        self.console.print("====>>配置管理<<====")
        self.console.print(f" [C] {self.symbols['config']} 配置管理（查看/编辑/删除配置）", style=self.colors["info"])
        
        self.console.print("====>>返回<<====")
        self.console.print(f" [Q] {self.symbols['back']} 返回上级", style=self.colors["exit"])

    def show_config_management_menu(self):
        """显示统一的配置管理菜单"""
        panel = Panel(
            f"[{self.symbols['config']} 配置管理]",
            style=self.colors["info"],
            title="配置管理"
        )
        self.console.print(panel)
        
        self.console.print("====>>配置操作<<====")
        self.console.print(f" [A] {self.symbols['view']} 查看配置详情", style=self.colors["info"])
        self.console.print(f" [B] {self.symbols['edit']} 直接编辑配置", style=self.colors["warning"])
        self.console.print(f" [C] {self.symbols['view']} 可视化编辑配置", style=self.colors["success"])
        self.console.print(f" [D] {self.symbols['validate']} 验证配置", style=self.colors["success"])
        self.console.print(f" [E] {self.symbols['new']} 新建配置集", style=self.colors["success"])
        self.console.print(f" [F] {self.symbols['delete']} 删除配置集", style=self.colors["error"])
        self.console.print(f" [G] {self.symbols['edit']} 打开配置文件", style=self.colors["info"])
        
        self.console.print("====>>返回<<====")
        self.console.print(f" [Q] {self.symbols['back']} 返回上级", style=self.colors["exit"])

    def show_instance_plugin_menu(self, instance_name: str):
        """显示实例的插件管理菜单"""
        panel = Panel(
            f"[{self.symbols['plugin']} 插件管理: {instance_name}]",
            style=self.colors["primary"],
            title="插件管理"
        )
        self.console.print(panel)
        
        self.console.print("====>> 插件操作 <<====")
        self.console.print(f" [A] {self.symbols['new']} 安装新插件", style=self.colors["success"])
        self.console.print(f" [B] {self.symbols['delete']} 卸载已安装的插件", style=self.colors["error"])
        self.console.print(f" [C] {self.symbols['view']} 查看已安装插件列表", style=self.colors["info"])
        
        self.console.print("====>> 返回 <<====")
        self.console.print(f" [Q] {self.symbols['back']} 返回主菜单", style=self.colors["exit"])

    def show_misc_menu(self):
        """显示杂项菜单"""
        panel = Panel(
            f"[{self.symbols['config']} 杂项]",
            style=self.colors["info"],
            title="杂项"
        )
        self.console.print(panel)
        
        self.console.print("====>>功能<<====")
        self.console.print(f" [A] {self.symbols['about']} 关于本程序", style=self.colors["info"])
        self.console.print(f" [B] {self.symbols['edit']} 程序设置", style=self.colors["warning"])
        self.console.print(f" [C] {self.symbols['download']} 组件下载", style=self.colors["success"])
        self.console.print(f" [D] {self.symbols['status']} 查看实例运行数据", style=self.colors["secondary"])
        
        self.console.print("====>>返回<<====")
        self.console.print(f" [Q] {self.symbols['back']} 返回上级", style=self.colors["exit"])

    def show_program_settings_menu(self, current_colors: dict, current_log_days: int, on_exit_action: str):
        """显示程序设置菜单"""
        from rich.table import Table
        panel = Panel(
            f"[{self.symbols['edit']} 程序设置]",
            style=self.colors["warning"],
            title="程序设置"
        )
        self.console.print(panel)
        
        self.console.print("在这里，你可以自定义启动器的外观主题和日志设置。")

        # 显示日志保留天数
        self.console.print("\n[bold]日志设置[/bold]")
        self.console.print(f"  日志文件保留天数: [bold yellow]{current_log_days}[/bold yellow] 天")
        
        # 显示退出设置
        self.console.print("\n[bold]退出设置[/bold]")
        action_map = {"ask": "询问", "terminate": "一律关闭", "keep": "一律保留"}
        self.console.print(f"  退出时对机器人进程的操作: [bold yellow]{action_map.get(on_exit_action, '未知')}[/bold yellow]")

        # 显示当前颜色设置
        table = Table(title="当前主题颜色", show_header=True, header_style="bold magenta")
        table.add_column("选项", style="dim", width=6)
        table.add_column("颜色名称", style="cyan")
        table.add_column("颜色值", style="yellow")

        color_keys = list(current_colors.keys())
        for i, key in enumerate(color_keys):
            value = current_colors[key]
            table.add_row(str(i + 1), key, f"[{value}]{value}[/]")
        self.console.print(table)

        self.console.print("\n====>>操作<<====")
        self.console.print(f" [L] {self.symbols['edit']} 修改日志保留天数", style=self.colors["success"])
        self.console.print(f" [E] {self.symbols['edit']} 修改退出时操作", style=self.colors["success"])
        self.console.print(f" [C] {self.symbols['edit']} 修改颜色 (输入选项数字)", style=self.colors["success"])
        self.console.print(f" [R] {self.symbols['back']} 恢复默认设置", style=self.colors["error"])
        
        self.console.print("====>>返回<<====")
        self.console.print(f" [Q] {self.symbols['back']} 返回上级", style=self.colors["exit"])
