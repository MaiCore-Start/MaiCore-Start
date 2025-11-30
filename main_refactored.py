"""
麦麦启动器主程序
重构版本，使用结构化日志和模块化设计
"""
import sys
import os
import time
from typing import Tuple, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import structlog
from src.core.logging import setup_logging, get_logger
from src.core.config import config_manager
from src.ui.interface import ui
from src.modules.launcher import launcher
from src.modules.config_manager import config_mgr
from src.modules.knowledge import knowledge_builder
from src.utils.common import setup_console
from src.core.p_config import p_config_manager
 
# 设置日志
setup_logging()
logger = get_logger(__name__)


class MaiMaiLauncher:
    """麦麦启动器主程序类"""
    
    def __init__(self):
        self.running = True
        self._keep_processes_on_exit = False
        setup_console()
        logger.info("麦麦启动器已启动")
    
    def handle_launch_mai(self):
        """处理启动麦麦"""
        try:
            ui.clear_screen()
            # 选择配置
            config = config_mgr.select_configuration()
            if not config:
                return
            
            # 验证配置
            errors = launcher.validate_configuration(config)
            if errors:
                ui.print_error("发现配置错误：")
                for error in errors:
                    ui.console.print(f"  • {error}", style=ui.colors["error"])
                ui.pause()
                return
            
            # 显示启动选择菜单
            success = launcher.show_launch_menu(config)
            if success:
                ui.print_success("启动操作完成！")
                logger.info("用户启动操作成功")
            else:
                ui.print_info("用户取消启动操作")
                logger.info("用户取消启动操作")
            
            ui.pause()
            
        except Exception as e:
            ui.print_error(f"启动过程出错：{str(e)}")
            logger.error("启动麦麦异常", error=str(e))
            ui.pause()
    
    def handle_config_menu(self):
        """处理配置菜单"""
        self.handle_config_management()
    
    def handle_config_management(self):
        """处理配置管理"""
        while True:
            ui.show_config_menu()
            choice = ui.get_choice("请选择操作", ["A", "B", "C", "Q"])
            
            if choice == "Q":
                break
            elif choice == "A":
                # 自动检索麦麦
                name = ui.get_input("请输入新配置集名称：")
                if name:
                    configurations = config_manager.get_all_configurations()
                    if name not in configurations:
                        config_mgr.auto_detect_and_create(name)
                        ui.pause()
                    else:
                        ui.print_error("配置集名称已存在")
                        ui.pause()
            elif choice == "B":
                # 手动配置
                name = ui.get_input("请输入新配置集名称：")
                if name:
                    configurations = config_manager.get_all_configurations()
                    if name not in configurations:
                        config_mgr.manual_create(name)
                        ui.pause()
                    else:
                        ui.print_error("配置集名称已存在")
                        ui.pause()
            elif choice == "C":
                # 统一的配置管理
                self.handle_unified_config_management()
    
    def handle_unified_config_management(self):
        """处理统一的配置管理"""
        while True:
            ui.show_config_management_menu()
            
            # 显示所有配置
            configurations = config_manager.get_all_configurations()
            if not configurations:
                ui.print_warning("当前没有任何配置")
                ui.pause()
                break
            
            
            choice = ui.get_choice("请选择操作", ["A", "B", "C", "D", "E", "F", "G", "Q"])
            
            if choice == "Q":
                break
            elif choice in ["A", "B", "D", "G"]:
                # 需要选择配置的操作
                config = config_mgr.select_configuration()
                if not config:
                    continue
                
                # 找到配置名称
                config_name = None
                for name, cfg in configurations.items():
                    if cfg == config:
                        config_name = name
                        break
                
                if not config_name:
                    ui.print_error("无法找到配置名称")
                    ui.pause()
                    continue
                
                if choice == "A":
                    # 查看配置详情
                    ui.show_config_details(config_name, config)
                    ui.pause()
                elif choice == "B":
                    # 编辑配置
                    config_mgr.edit_configuration(config_name)
                
                elif choice == "D":
                    # 验证配置
                    from src.modules.launcher import launcher
                    errors = launcher.validate_configuration(config)
                    if errors:
                        ui.print_error("发现配置错误：")
                        for error in errors:
                            ui.console.print(f"  • {error}", style=ui.colors["error"])
                    else:
                        ui.print_success("配置验证通过")
                    ui.pause()
                elif choice == "G":
                    # 打开配置文件
                    config_mgr.open_config_files(config)
                    ui.pause()
            
            elif choice == "C":
                # 可视化编辑配置，直接在新窗口中运行 run_with_ui_port.py
                import subprocess
                import sys
                import os
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_with_ui_port.py")
                # Windows下用start命令新开窗口
                if sys.platform.startswith("win"):
                    subprocess.Popen(["start", "", sys.executable, script_path], shell=True)
                else:
                    subprocess.Popen([sys.executable, script_path])
                ui.print_info("已在新窗口启动可视化配置界面。请在浏览器中操作。")
                ui.pause()

            elif choice == "E":
                # 新建配置集
                name = ui.get_input("请输入新配置集名称：")
                if name and name not in configurations:
                    method_choice = ui.get_choice("选择配置方式：[A] 自动检索 [B] 手动配置", ["A", "B"])
                    if method_choice == "A":
                        config_mgr.auto_detect_and_create(name)
                    else:
                        config_mgr.manual_create(name)
                    ui.pause()
                elif name in configurations:
                    ui.print_error("配置集名称已存在")
                    ui.pause()
            elif choice == "F":
                # 删除配置集
                serial_input = ui.get_input("请输入要删除的用户序列号（多个用英文逗号分隔）：")
                if serial_input:
                    serials = [s.strip() for s in serial_input.split(',')]
                    config_mgr.delete_configurations(serials)
                    ui.pause()
    
    def handle_knowledge_menu(self):
        """处理知识库菜单"""
        while True:
            ui.clear_screen()
            ui.console.print("[🔧 知识库构建]", style=ui.colors["secondary"])
            ui.console.print("================")
            ui.console.print(">>> LPMM功能仅适用于支持LPMM知识库的版本，如'0.6.3-alpha' <<<", style=ui.colors["error"])
            
            ui.console.print(" [A] LPMM知识库一条龙构建", style=ui.colors["secondary"])
            ui.console.print(" [B] LPMM知识库文本分割", style="#02A18F")
            ui.console.print(" [C] LPMM知识库实体提取", style="#02A18F")
            ui.console.print(" [D] LPMM知识库知识图谱导入", style="#02A18F")
            ui.console.print(" [E] 旧版知识库构建（仅0.6.0-alpha及更早版本）", style="#924444")
            ui.console.print(" [Q] 返回主菜单", style="#7E1DE4")
            ui.console.print(">>> 仍使用旧版知识库的版本（如0.6.0-alpha）请选择选项 [E] <<<", style=ui.colors["error"])
            
            choice = ui.get_choice("请选择操作", ["A", "B", "C", "D", "E", "Q"])
            
            if choice == "Q":
                break
            
            # 选择配置
            config = config_mgr.select_configuration()
            if not config:
                continue
            
            if choice == "A":
                knowledge_builder.pipeline(config)
            elif choice == "B":
                knowledge_builder.text_split(config)
            elif choice == "C":
                knowledge_builder.entity_extract(config)
            elif choice == "D":
                knowledge_builder.knowledge_import(config)
            elif choice == "E":
                knowledge_builder.legacy_knowledge_build(config)
            else:
                ui.print_error("无效选项")
                ui.countdown(1)
            
            ui.pause()
    
    def handle_migration(self):
        """处理数据库迁移"""
        ui.clear_screen()
        ui.console.print("[🔄 知识库迁移]", style="#28DCF0")
        ui.console.print("MongoDB → SQLite 数据迁移")
        ui.console.print("================")
        
        knowledge_builder.migrate_mongodb_to_sqlite()
        ui.pause()
    
    def handle_deployment_menu(self):
        """处理部署菜单"""
        while True:
            ui.clear_screen()
            ui.console.print("[部署辅助系统]", style=ui.colors["primary"])
            ui.console.print("=================")
            
            ui.console.print(" [A] 实例部署", style=ui.colors["success"])
            ui.console.print(" [B] 实例更新", style=ui.colors["warning"])
            ui.console.print(" [C] 实例删除", style=ui.colors["error"])
            ui.console.print(" [Q] 返回主菜单", style="#7E1DE4")
            
            choice = ui.get_choice("请选择操作", ["A", "B", "C", "Q"])
            
            if choice == "Q":
                break
            elif choice == "A":
                # 部署新实例
                from src.modules.deployment import deployment_manager
                deployment_manager.deploy_instance()
                ui.pause()
            elif choice == "B":
                # 更新实例
                from src.modules.deployment import deployment_manager
                deployment_manager.update_instance()
                ui.pause()
            elif choice == "C":
                # 删除实例
                from src.modules.deployment import deployment_manager
                deployment_manager.delete_instance()
                ui.pause()
            else:
                ui.print_error("无效选项")
                ui.countdown(1)
    
    def handle_about_menu(self):
        """处理关于菜单"""
        ui.clear_screen()
        ui.console.print("===关于本程序===", style=ui.colors["primary"])
        ui.console.print("麦麦启动器控制台 - 重构版", style=ui.colors["primary"])
        ui.console.print("=================")
        
        ui.console.print("版本：V4.0.0-重构版", style=ui.colors["info"])
        ui.console.print("重构特性：", style=ui.colors["success"])
        ui.console.print("  • 模块化设计", style="white")
        ui.console.print("  • 结构化日志（structlog）", style="white")
        ui.console.print("  • 丰富的UI界面（rich）", style="white")
        ui.console.print("  • 改进的错误处理", style="white")
        ui.console.print("  • 更好的代码组织", style="white")
        
        ui.console.print("\n技术栈：", style=ui.colors["info"])
        ui.console.print("  • Python 3.12.8", style="white")
        ui.console.print("  • structlog - 结构化日志", style="white")
        ui.console.print("  • rich - 终端UI", style="white")
        ui.console.print("  • toml - 配置管理", style="white")        
        
        ui.console.print("\n开源许可：Apache License 2.0", style=ui.colors["secondary"])
        ui.console.print("GitHub：https://github.com/xiaoCZX/MaiMbot-initiate", style="#46AEF8")
        ui.console.print("你喜欢的话，请给个Star支持一下哦~", style="white")
        ui.console.print("欢迎加入我们的社区！（我们的QQ群聊：1025509724）", style="white")

        ui.console.print("\n感谢以下为此项目做出贡献的开发者：", style=ui.colors["header"])
        ui.console.print("  • 小城之雪 - 整个项目的提出者和主要开发者", style="white")
        ui.console.print("  • 一闪 - 为此项目的重构提供了大量支持，以及webui安装支持", style="white")
        ui.console.print("  • 其他贡献者", style="white")

        ui.pause()

    def handle_misc_menu(self):
        """处理杂项菜单"""
        while True:
            ui.show_misc_menu()
            choice = ui.get_choice("请选择操作", ["A", "B", "C", "D", "Q"])
            
            if choice == "Q":
                break
            elif choice == "A":
                self.handle_about_menu()
            elif choice == "B":
                self.handle_program_settings()
            elif choice == "C":
                self.handle_component_download()
            elif choice == "D":
                self.handle_instance_statistics()

    def handle_program_settings(self):
        """处理程序设置"""
        while True:
            # 重新加载颜色以反映实时变化
            from src.ui.theme import COLORS
            current_colors = p_config_manager.get_theme_colors()
            current_log_days = p_config_manager.get("logging.log_rotation_days", 30)
            on_exit_action = p_config_manager.get("on_exit.process_action", "ask")
            ui.show_program_settings_menu(current_colors, current_log_days, on_exit_action)
            
            choice = ui.get_choice("请选择操作", ["L", "E", "C", "R", "Q"])
            
            if choice == "Q":
                break
            
            elif choice == "L":
                # 修改日志保留天数
                while True:
                    days_input = ui.get_input("请输入新的日志文件保留天数 (例如: 30): ")
                    try:
                        new_days = int(days_input)
                        if new_days > 0:
                            p_config_manager.set("logging.log_rotation_days", new_days)
                            p_config_manager.save()
                            ui.print_success(f"日志保留天数已更新为 {new_days} 天。")
                            ui.pause()
                            break
                        else:
                            ui.print_error("请输入一个大于0的整数。")
                    except ValueError:
                        ui.print_error("无效输入，请输入一个整数。")
            
            elif choice == "E":
                # 修改退出时操作
                actions = ["ask", "terminate", "keep"]
                action_map = {"ask": "询问", "terminate": "一律关闭", "keep": "一律保留"}
                
                options_text = " / ".join([f"[{action[0].upper()}] {action_map[action]}" for action in actions])
                
                while True:
                    user_input = ui.get_input(f"请选择操作 ({options_text}): ").lower()
                    
                    selected_action = ""
                    if user_input == 'a': selected_action = "ask"
                    elif user_input == 't': selected_action = "terminate"
                    elif user_input == 'k': selected_action = "keep"

                    if selected_action in actions:
                        p_config_manager.set("on_exit.process_action", selected_action)
                        p_config_manager.save()
                        ui.print_success(f"退出时操作已更新为: {action_map[selected_action]}")
                        ui.pause()
                        break
                    else:
                        ui.print_error("无效输入。")

            elif choice == "C":
                color_keys = list(current_colors.keys())
                while True:
                    idx_input = ui.get_input("请输入要修改的颜色选项数字 (或 Q 返回): ")
                    if idx_input.upper() == 'Q':
                        break
                    
                    try:
                        idx = int(idx_input) - 1
                        if 0 <= idx < len(color_keys):
                            key_to_edit = color_keys[idx]
                            new_value = ui.get_input(f"请输入 '{key_to_edit}' 的新颜色值 (例如: #FF00FF 或 red): ")
                            p_config_manager.set(f"theme.{key_to_edit}", new_value)
                            p_config_manager.save()
                            # 动态更新导入的COLORS
                            COLORS[key_to_edit] = new_value
                            ui.print_success(f"'{key_to_edit}' 已更新为 '{new_value}'")
                            ui.pause()
                            break
                        else:
                            ui.print_error("无效的选项数字。")
                    except ValueError:
                        ui.print_error("请输入有效的数字。")

            elif choice == "R":
                if ui.confirm("确定要将所有颜色恢复为默认设置吗？此操作不可逆。"):
                    if p_config_manager.reset_to_default():
                        # 动态更新导入的COLORS
                        default_colors = p_config_manager.DEFAULT_CONFIG['theme']
                        for k, v in default_colors.items():
                            COLORS[k] = v
                        ui.print_success("已成功恢复默认颜色设置。")
                    else:
                        ui.print_error("恢复默认设置失败。")
                    ui.pause()

    def handle_component_download(self):
        """处理组件下载"""
        try:
            # 导入组件下载管理器
            from src.modules.component_download.component_manager import component_manager
            
            while True:
                ui.clear_screen()
                ui.components.show_title("组件下载中心", symbol="📥")
                
                # 显示组件选择菜单
                component_key = component_manager.show_component_download_menu()
                if not component_key:
                    break
                
                # 执行组件下载
                success = component_manager.download_component(component_key)
                if success:
                    ui.print_success(f"组件下载完成！")
                else:
                    ui.print_error(f"组件下载失败！")
                
                ui.pause()
                
        except Exception as e:
            ui.print_error(f"组件下载过程出错：{str(e)}")
            logger.error("组件下载异常", error=str(e))
            ui.pause()

    def handle_instance_statistics(self):
        """处理实例运行数据查看"""
        try:
            ui.clear_screen()
            ui.console.print("[📊 实例运行数据查看]", style=ui.colors["secondary"])
            ui.console.print("==================")
            
            ui.console.print("请选择数据来源方式（此功能目前仅支持MaiBot实例）：", style=ui.colors["info"])
            ui.console.print(" [A] 从已配置的实例中选择", style=ui.colors["success"])
            ui.console.print(" [B] 直接输入实例路径", style=ui.colors["warning"])
            ui.console.print(" [Q] 返回上级菜单", style=ui.colors["exit"])
            
            choice = ui.get_choice("请选择操作", ["A", "B", "Q"])
            
            if choice == "Q":
                return
            elif choice == "A":
                # 从已配置的实例中选择
                config = config_mgr.select_configuration()
                if not config:
                    ui.pause()
                    return
                
                # 检查是否为MaiBot
                bot_type = config.get("bot_type", "")
                if bot_type != "MaiBot":
                    ui.print_warning("此功能目前仅支持MaiBot实例")
                    ui.pause()
                    return
                
                # 导入并使用统计管理器
                try:
                    from src.modules.instance_statistics import instance_statistics_manager
                    success = instance_statistics_manager.open_statistics_page(config=config)
                    if success:
                        ui.print_success("统计页面已在浏览器中打开")
                    else:
                        ui.print_error("打开统计页面失败")
                except ImportError as e:
                    ui.print_error(f"无法导入统计模块：{str(e)}")
                    logger.error("导入统计模块失败", error=str(e))
                
                ui.pause()
                
            elif choice == "B":
                # 直接输入实例路径
                instance_path = ui.get_input("请输入MaiBot实例路径：")
                if not instance_path:
                    ui.print_warning("未输入路径")
                    ui.pause()
                    return
                
                # 验证路径是否存在
                if not os.path.exists(instance_path):
                    ui.print_error(f"路径不存在：{instance_path}")
                    ui.pause()
                    return
                
                # 检查是否为有效的MaiBot实例
                if not self._validate_maibot_instance(instance_path):
                    ui.print_warning("该路径似乎不是有效的MaiBot实例")
                    if not ui.confirm("是否继续生成统计页面？"):
                        return
                
                # 导入并使用统计管理器
                try:
                    from src.modules.instance_statistics import instance_statistics_manager
                    success = instance_statistics_manager.open_statistics_page(instance_path=instance_path)
                    if success:
                        ui.print_success("统计页面已在浏览器中打开")
                    else:
                        ui.print_error("打开统计页面失败")
                except ImportError as e:
                    ui.print_error(f"无法导入统计模块：{str(e)}")
                    logger.error("导入统计模块失败", error=str(e))
                
                ui.pause()
                
        except Exception as e:
            ui.print_error(f"查看实例运行数据过程出错：{str(e)}")
            logger.error("实例运行数据查看异常", error=str(e))
            ui.pause()
    
    def _validate_maibot_instance(self, instance_path: str) -> bool:
        """验证是否为有效的MaiBot实例"""
        try:
            # 检查关键文件是否存在
            key_files = ["bot.py", "main.py", "package.json"]
            for file in key_files:
                if not os.path.exists(os.path.join(instance_path, file)):
                    return False
            
            # 检查是否有MaiBot相关的目录结构
            subdirs = os.listdir(instance_path)
            maibot_indicators = ["src", "plugins", "config", "adapter"]
            has_maibot_structure = any(indicator in subdirs for indicator in maibot_indicators)
            
            return has_maibot_structure
            
        except Exception:
            return False

    def handle_refresh_daily_quote(self):
        """处理刷新每日一言"""
        ui.clear_screen()
        ui.console.print("[🔄 刷新每日一言]", style=ui.colors["secondary"])
        ui.console.print("==================")
        
        # 获取当前每日一言
        old_quote = ui.menus.daily_quote
        
        # 刷新每日一言
        new_quote = ui.menus.refresh_daily_quote()
        
        # 显示结果
        ui.console.print(f"原每日一言: {old_quote}", style=ui.colors["info"])
        ui.console.print(f"新每日一言: {new_quote}", style=ui.colors["success"])
        
        if old_quote != new_quote:
            ui.print_success("每日一言刷新成功！")
        else:
            ui.print_info("每日一言未发生变化（可能是随机选择了相同内容）")
        
        ui.pause()

    def handle_process_status(self):
        """处理进程状态查看，支持自动刷新和交互式命令（最终优化版）。"""
        import msvcrt
        from rich.live import Live
        from rich.panel import Panel
        from rich.text import Text
        from rich.layout import Layout
        from rich.table import Table

        should_quit_monitor = False
        while not should_quit_monitor:
            command_result = None
            # 每次处理完一个命令（如查看详情）后，重新创建一个Live实例
            with Live(auto_refresh=False, screen=True, transient=True) as live:
                input_buffer = ""
                last_data_refresh = 0
                last_ui_refresh = 0
                COMMANDS = ["stop", "restart", "details", "stopall", "quit", "q"]
                # 初始数据获取
                process_table = launcher.show_running_processes()

                while True: # Live 渲染循环
                    now = time.time()
                    
                    # --- 1. 处理输入 (非阻塞) ---
                    input_changed = False
                    if msvcrt.kbhit():
                        while msvcrt.kbhit():
                            char = msvcrt.getwch()
                        input_changed = True
                        
                        if char == '\r':  # Enter
                            command_result = self._handle_process_command(input_buffer.strip())
                            if command_result:
                                break
                            input_buffer = ""
                        elif char == '\t':  # Tab
                            parts = input_buffer.split(" ", 1)
                            # 场景1: 补全指令
                            if len(parts) == 1:
                                suggestion = next((cmd for cmd in COMMANDS if cmd.startswith(parts[0].lower()) and parts[0]), None)
                                if suggestion:
                                    input_buffer = suggestion + " " if suggestion in ["stop", "restart", "details"] else suggestion
                            # 场景2: 补全PID
                            elif len(parts) == 2 and parts[0] in ["stop", "restart", "details"]:
                                pid_prefix = parts[1]
                                if pid_prefix.isdigit() or pid_prefix == "":
                                    all_pids = launcher.get_managed_pids()
                                    matching_pid = next((str(p) for p in all_pids if str(p).startswith(pid_prefix)), None)
                                    if matching_pid:
                                        input_buffer = f"{parts[0]} {matching_pid}"

                        elif char == '\x08':  # Backspace
                            input_buffer = input_buffer[:-1]
                        elif char not in ('\x00', '\xe0'):  # 忽略功能键
                            input_buffer += char
                    
                    if command_result:
                        break

                    # --- 2. 刷新进程数据 (定时) ---
                    data_changed = False
                    if now - last_data_refresh > 2.0:
                        last_data_refresh = now
                        process_table = launcher.show_running_processes()
                        data_changed = True

                    # --- 3. 刷新UI (按需) ---
                    if input_changed or data_changed or (now - last_ui_refresh > 0.5):
                        last_ui_refresh = now
                        
                        command_table = Table.grid(padding=(0, 1))
                        command_table.add_column(style="bold yellow", width=15); command_table.add_column()
                        command_table.add_row("stop <PID>", "终止指定PID的进程"); command_table.add_row("restart <PID>", "重启指定PID的进程")
                        command_table.add_row("details <PID>", "查看指定PID的进程详情"); command_table.add_row("stopall", "终止所有受管进程")
                        command_table.add_row("q / quit", "退出状态监控")
                        command_table.add_row("Tab键", "补全指令或PID")

                        suggestion = ""
                        parts = input_buffer.split(" ", 1)
                        if len(parts) == 1 and parts[0]:
                             suggestion = next((cmd for cmd in COMMANDS if cmd.startswith(parts[0].lower()) and cmd != parts[0].lower()), "")

                        input_text = Text(f"> {input_buffer}", no_wrap=True)
                        if suggestion:
                            input_text.append(suggestion[len(input_buffer):], style="italic dim")
                        
                        if int(now * 2) % 2 == 0:
                           input_text.append("_") # ▋

                        layout = Layout()
                        layout.split_column(
                            Panel(command_table, title="[bold]可用命令[/bold]", border_style="dim"),
                            process_table,
                            Panel(input_text, border_style="cyan", title="输入命令", height=3)
                        )
                        live.update(layout)
                        live.refresh()

                    time.sleep(0.02)

            # --- 4. Live循环结束后，处理命令结果 ---
            if isinstance(command_result, dict):
                self._show_process_details(command_result)
            elif command_result == "quit":
                should_quit_monitor = True

        ui.print_info("\n已退出进程状态监控。")
        logger.info("用户退出进程状态监控")

    def _show_process_details(self, details: dict):
        """在一个专用的屏幕上显示进程详情。"""
        from rich.panel import Panel
        from rich.text import Text
        detail_text = ""
        pid = details.get("PID", "N/A")
        for key, value in details.items():
            detail_text += f"[bold cyan]{key}:[/bold cyan] {str(value)}\n"
        
        ui.clear_screen()
        ui.console.print(Panel(Text(detail_text.strip()), title=f"进程 {pid} 详细信息", border_style="yellow", subtitle="按任意键返回监控..."))
        ui.pause("") # 传入空字符串以避免默认提示

    def _handle_process_command(self, command: str) -> Any:
        """解析并执行进程管理命令，返回结果用于主循环处理。"""
        parts = command.strip().lower().split()
        if not parts: return None
        cmd, args = parts[0], parts[1:]

        if cmd in ("q", "quit"): return "quit"
        
        if cmd == "stop":
            if not args or not args[0].isdigit(): return ("message", "用法: stop <PID>", "yellow")
            pid = int(args[0])
            if launcher.stop_process(pid): return ("message", f"已发送停止命令到 PID {pid}", "green")
            return ("message", f"无法停止 PID {pid}，可能不是受管进程。", "red")

        elif cmd == "restart":
            if not args or not args[0].isdigit(): return ("message", "用法: restart <PID>", "yellow")
            pid = int(args[0])
            if launcher.restart_process(pid): return ("message", f"成功重启进程 (原PID: {pid})", "green")
            return ("message", f"无法重启 PID {pid}", "red")

        elif cmd == "stopall":
            launcher.stop_all_processes()
            return ("message", "所有受管进程已停止。", "green")

        elif cmd == "details":
            if not args or not args[0].isdigit(): return ("message", "用法: details <PID>", "yellow")
            pid = int(args[0])
            details = launcher.get_process_details(pid)
            if details: return details
            return ("message", f"无法获取 PID {pid} 的详细信息。", "red")
        
        return ("message", f"未知命令: '{cmd}'", "red")

    def run(self):
        """运行主程序"""
        try:
            logger.info("启动器主循环开始")
            
            while self.running:
                ui.show_main_menu()
                choice = ui.get_input("请输入选项").upper()
                
                logger.debug("用户选择", choice=choice)
                
                if choice == "Q":
                    has_child_processes = len(launcher.get_managed_pids()) > 1
                    action = p_config_manager.get("on_exit.process_action", "ask")

                    do_exit = False
                    # 如果没有子进程，直接退出
                    if not has_child_processes:
                        do_exit = True
                    elif action == "terminate":
                        ui.print_info("根据设置，将关闭所有托管进程...")
                        launcher.stop_all_processes()
                        do_exit = True
                    elif action == "keep":
                        ui.print_info("根据设置，将保留所有托管进程...")
                        self._keep_processes_on_exit = True
                        do_exit = True
                    else:  # "ask" or default
                        ui.print_warning("检测到有正在运行的机器人进程。")
                        while True:
                            choice_exit = ui.get_input("退出启动器时要如何处理这些进程？[K]保留 [T]关闭 [C]取消退出: ").upper()
                            if choice_exit == 'K':
                                ui.print_info("将保留所有托管进程...")
                                self._keep_processes_on_exit = True
                                do_exit = True
                                logger.info("用户选择保留进程并退出")
                                break
                            elif choice_exit == 'T':
                                ui.print_info("将关闭所有托管进程...")
                                launcher.stop_all_processes()
                                do_exit = True
                                logger.info("用户选择关闭进程并退出")
                                break
                            elif choice_exit == 'C':
                                logger.info("用户取消退出程序")
                                break  # breaks inner while, do_exit remains false
                            else:
                                ui.print_error("无效输入。")

                    if do_exit:
                        self.running = False
                        ui.print_info("感谢使用麦麦启动器！")
                        logger.info("用户退出程序")
                elif choice == "A":
                    self.handle_launch_mai()
                elif choice == "B":
                    self.handle_config_menu()
                elif choice == "C":
                    self.handle_knowledge_menu()
                elif choice == "D":
                    self.handle_migration()
                elif choice == "E":
                    # 插件管理
                    ui.show_plugin_menu()
                elif choice == "F":
                    self.handle_deployment_menu()
                elif choice == "G":
                    self.handle_process_status()
                elif choice == "H":
                    self.handle_misc_menu()
                elif choice == "R":
                    # 直接在主菜单刷新每日一言
                    old_quote = ui.menus.daily_quote
                    new_quote = ui.menus.refresh_daily_quote()
                    
                    if old_quote != new_quote:
                        ui.print_success("每日一言已刷新！")
                    else:
                        ui.print_info("每日一言未发生变化")
                    
                    # 短暂暂停后重新显示主菜单
                    time.sleep(1)
                    continue
                else:
                    ui.print_error("无效选项")
                    ui.countdown(1)
                    
        except KeyboardInterrupt:
            ui.print_info("\n程序被用户中断")
            logger.info("程序被用户中断")
        except Exception as e:
            ui.print_error(f"程序运行出错：{str(e)}")
            logger.error("程序运行异常", error=str(e))
        finally:
            # 除非明确指示，否则停止所有进程
            if not self._keep_processes_on_exit:
                launcher.stop_all_processes()
            logger.info("启动器程序结束")


def main():
    """主函数"""
    try:
        app = MaiMaiLauncher()
        app.run()
    except Exception as e:
        print(f"启动失败：{str(e)}")
        logger.error("启动失败", error=str(e))


if __name__ == "__main__":
    main()
