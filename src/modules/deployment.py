# -*- coding: utf-8 -*-
"""
部署系统模块 - 重构版
负责实例的部署、更新和删除操作
使用模块化的部署器来处理不同Bot类型的部署
"""
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional, Tuple
import structlog

from ..core.config import config_manager
from ..core.logging import set_console_log_level, reset_console_log_level
from ..ui.interface import ui
from ..utils.common import validate_path, open_files_in_editor
from ..utils.version_detector import compare_versions
from ..utils.notifier import windows_notifier, NotificationLogHandler
from .mongodb_installer import mongodb_installer
from .webui_installer import webui_installer

# 导入模块化的部署器
from .deployment_core import (
    MaiBotDeployer,
    MoFoxBotDeployer,
    NapCatDeployer
)

logger = structlog.get_logger(__name__)


class DeploymentManager:
    """部署管理器类 - 协调各个部署器完成部署任务"""
    
    def __init__(self):
        # 初始化各个部署器
        self.maibot_deployer = MaiBotDeployer()
        self.mofox_deployer = MoFoxBotDeployer()
        self.napcat_deployer = NapCatDeployer()
        
        # 离线模式标志
        self._offline_mode = False
        
    def deploy_instance(self) -> bool:
        """部署新实例 - 重构版本"""
        set_console_log_level("WARNING")
        notification_handler = None
        root_logger = None
        should_notify = windows_notifier.is_enabled()
        logger.info("Windows通知开关状态", enabled=should_notify)
        if should_notify:
            notification_handler = NotificationLogHandler(windows_notifier, title="部署告警")
            notification_handler.setLevel(logging.WARNING)
            notification_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
            root_logger = logging.getLogger()
            root_logger.addHandler(notification_handler)
        try:
            ui.clear_screen()
            ui.components.show_title("实例部署助手", symbol="🚀")

            if not self._check_network_for_deployment():
                return False

            deploy_config = self._get_deployment_config()
            if not deploy_config:
                return False

            if not self._confirm_deployment(deploy_config):
                return False

            ui.print_info("🚀 开始部署流程...")
            logger.info("开始部署实例", config=deploy_config)
            if should_notify:
                windows_notifier.send("部署已开始", "部署时间可能较长，我们会在部署完成或出现意外情况时通知您。")

            # 部署流程
            paths = self._run_deployment_steps(deploy_config)

            # 完成部署
            if not self._finalize_deployment(deploy_config, **paths):
                return False

            ui.print_success(f"🎉 实例 '{deploy_config['nickname']}' 部署完成！")
            
            # 定义bot_path_key以传递给后续函数
            bot_type = deploy_config.get("bot_type", "MaiBot")
            bot_path_key = "mai_path" if bot_type == "MaiBot" else "mofox_path"
            self._show_post_deployment_info(paths.get(bot_path_key, ""), deploy_config, paths.get("adapter_path", ""))

            logger.info("实例部署完成", serial=deploy_config['serial_number'])
            if should_notify:
                windows_notifier.send("部署完成", f"实例 {deploy_config['nickname']} 已成功部署。")
            return True

        except Exception as e:
            ui.print_error(f"部署失败：{str(e)}")
            logger.error("实例部署失败", error=str(e))
            if should_notify:
                windows_notifier.send("部署失败", f"实例部署失败：{str(e)}")
            return False
        finally:
            if root_logger and notification_handler:
                root_logger.removeHandler(notification_handler)
            reset_console_log_level()
    
    def _check_network_for_deployment(self) -> bool:
        """检查网络连接用于部署"""
        ui.print_info("检查网络连接...")
        network_status, message = self.maibot_deployer.check_network_connection()
        if not network_status:
            ui.print_error(f"网络连接失败: {message}")
            ui.print_info("您可以选择继续部署，但可能无法从GitHub获取版本信息")
            if not ui.confirm("是否继续部署（将使用本地缓存或默认版本）？"):
                ui.pause()
                return False
            self._offline_mode = True
            # 设置各个部署器的离线模式
            self.maibot_deployer.version_manager.set_offline_mode(True)
            self.mofox_deployer.version_manager.set_offline_mode(True)
        else:
            ui.print_success("网络连接正常")
            self._offline_mode = False
        return True
    
    def _get_deployment_config(self) -> Optional[Dict]:
        """获取部署配置信息"""
        # 询问用户要部署的Bot类型
        ui.console.print("\n[🤖 Bot类型选择]", style=ui.colors["primary"])
        ui.console.print("请选择要部署的Bot类型：")
        ui.console.print(" [1] MaiBot (默认)")
        ui.console.print(" [2] MoFox_bot")

        bot_type_choice = ui.get_input("请选择Bot类型 (1/2): ").strip()
        bot_type = "MaiBot" if bot_type_choice != "2" else "MoFox_bot"

        # 根据Bot类型选择版本管理器
        if bot_type == "MaiBot":
            version_manager = self.maibot_deployer.version_manager
        else:
            version_manager = self.mofox_deployer.version_manager

        # 选择版本
        selected_version = version_manager.show_version_menu(bot_type)
        if not selected_version:
            return None

        # 组件安装选项
        install_adapter = ui.confirm("是否需要安装适配器？")
        install_napcat = ui.confirm("是否需要安装NapCat？")
        napcat_version = None
        if install_napcat:
            napcat_version = self.napcat_deployer.select_napcat_version()
        
        # 根据Bot类型和版本条件决定是否询问MongoDB
        install_mongodb = False
        if bot_type == "MaiBot":
            # MaiBot: 版本号大于等于0.7.0，或版本号为分支且不为classical时不要询问
            version_name = selected_version.get("name", "")
            version_type = selected_version.get("type", "release")
            
            # 检查是否需要询问MongoDB
            should_ask_mongodb = True
            if version_type == "branch" and version_name != "classical":
                # 分支且不为classical，不询问
                should_ask_mongodb = False
            elif compare_versions(version_name, "0.7.0") >= 0:
                # 版本>=0.7.0，不询问
                should_ask_mongodb = False
            
            if should_ask_mongodb:
                install_mongodb = ui.confirm("是否需要安装MongoDB？")
        else:
            # MoFox_bot: 永远不要询问是否安装MongoDB
            install_mongodb = False
        
        # 根据Bot类型决定WebUI询问
        if bot_type == "MaiBot":
            install_webui = ui.confirm("是否需要安装WebUI？")
            install_mofox_admin_ui = False
        else:
            # MoFox_bot: 永远不要询问是否安装麦麦的webui
            install_webui = False
            install_mofox_admin_ui = False

        # 安装目录
        default_install_dir = os.path.join(os.getcwd(), "instances")
        ui.print_info(f"默认安装目录: {default_install_dir}")
        while True:
            install_dir_input = ui.get_input("请输入安装目录）: ").strip()
            install_dir = install_dir_input if install_dir_input else default_install_dir
            is_valid, message = validate_path(install_dir)
            if is_valid:
                try:
                    os.makedirs(install_dir, exist_ok=True)
                    ui.print_success(f"安装目录: {install_dir}")
                    break
                except Exception as e:
                    ui.print_error(f"创建目录失败: {str(e)}")
            else:
                ui.print_error(f"路径无效: {message}")

        # 实例名称（带冲突检测）
        while True:
            nickname_input = ui.get_input("请输入实例名称）: ").strip()
            
            # 如果输入为空，自动生成不冲突的默认名称
            if not nickname_input:
                base_nickname = f"{bot_type}_instance"
                nickname = base_nickname
                counter = 1
                # 自动寻找不冲突的名称
                while os.path.exists(os.path.join(install_dir, nickname)):
                    nickname = f"{base_nickname}_{counter}"
                    counter += 1
                ui.print_info(f"使用默认实例名称: {nickname}")
                break
            else:
                nickname = nickname_input
            
            # 检查昵称目录是否已存在
            nickname_dir = os.path.join(install_dir, nickname)
            if os.path.exists(nickname_dir):
                # 检查目录是否为空
                if os.listdir(nickname_dir):
                    ui.print_warning(f"⚠️ 目录 '{nickname_dir}' 已存在且不为空")
                    ui.console.print("该目录包含以下内容：", style="yellow")
                    for item in os.listdir(nickname_dir)[:5]:  # 只显示前5个
                        ui.console.print(f"  • {item}", style="yellow")
                    if len(os.listdir(nickname_dir)) > 5:
                        ui.console.print(f"  ... 还有 {len(os.listdir(nickname_dir)) - 5} 个项目", style="yellow")
                    
                    if ui.confirm("是否清空该目录并继续？"):
                        try:
                            shutil.rmtree(nickname_dir)
                            ui.print_success("已清空目录")
                            break
                        except Exception as e:
                            ui.print_error(f"清空目录失败: {str(e)}")
                            ui.print_info("请输入其他实例名称")
                            continue
                    else:
                        ui.print_info("请输入其他实例名称")
                        continue
                else:
                    # 目录存在但为空，可以使用
                    ui.print_info(f"将使用现有空目录: {nickname_dir}")
                    break
            else:
                # 目录不存在，可以使用
                break

        # 用户序列号（用于识别实例）
        existing_configs = config_manager.get_all_configurations()
        existing_serials = {cfg.get("serial_number") for cfg in existing_configs.values() if cfg.get("serial_number")}
        
        while True:
            serial_number = ui.get_input("请输入实例序列号（用于识别和管理实例）: ").strip()
            if not serial_number:
                ui.print_error("序列号不能为空，请重新输入。")
                continue
            if serial_number in existing_serials:
                ui.print_error(f"序列号 '{serial_number}' 已存在，请使用其他序列号。")
                continue
            break

        # QQ账号（可选）
        qq_account = ui.get_input("请输入QQ账号（可选，留空跳过）: ").strip()

        # 生成绝对序列号（用于内部唯一标识）
        absolute_serial_number = config_manager.generate_unique_serial()

        # 返回部署配置
        return {
            "bot_type": bot_type,
            "selected_version": selected_version,
            "install_adapter": install_adapter,
            "install_napcat": install_napcat,
            "napcat_version": napcat_version,
            "install_mongodb": install_mongodb,
            "mongodb_path": "",
            "install_webui": install_webui,
            "install_mofox_admin_ui": install_mofox_admin_ui,
            "install_dir": install_dir,
            "nickname": nickname,
            "qq_account": qq_account,
            "serial_number": serial_number,
            "absolute_serial_number": absolute_serial_number
        }
    
    def _confirm_deployment(self, deploy_config: Dict) -> bool:
        """确认部署配置"""
        ui.clear_screen()
        ui.components.show_title("确认部署配置", symbol="✅")
        
        bot_type = deploy_config.get("bot_type", "MaiBot")
        
        # 显示配置摘要
        from rich.table import Table
        table = Table(
            show_header=True,
            header_style=ui.colors["table_header"],
            title="[bold]部署配置摘要[/bold]",
            title_style=ui.colors["primary"],
            border_style=ui.colors["border"],
            show_lines=True
        )
        table.add_column("配置项", style="cyan", width=20)
        table.add_column("值", style="green", width=50)
        
        table.add_row("Bot类型", bot_type)
        table.add_row("版本", deploy_config["selected_version"]["display_name"])
        table.add_row("实例名称", deploy_config["nickname"])
        table.add_row("安装目录", deploy_config["install_dir"])
        
        if deploy_config.get("qq_account"):
            table.add_row("QQ账号", deploy_config["qq_account"])
        
        table.add_row("安装适配器", "✅" if deploy_config.get("install_adapter") else "❌")
        table.add_row("安装NapCat", "✅" if deploy_config.get("install_napcat") else "❌")
        table.add_row("安装MongoDB", "✅" if deploy_config.get("install_mongodb") else "❌")
        
        webui_text = ""
        if bot_type == "MaiBot":
            webui_text = "✅" if deploy_config.get("install_webui") else "❌"
        else:
            webui_text = "✅" if deploy_config.get("install_mofox_admin_ui") else "❌"
        table.add_row("安装WebUI", webui_text)
        
        ui.console.print(table)
        
        return ui.confirm("\n确认以上配置并开始部署？")
    
    def _run_deployment_steps(self, deploy_config: Dict) -> Dict[str, str]:
        """执行所有部署步骤"""
        bot_type = deploy_config.get("bot_type", "MaiBot")
        bot_path_key = "mai_path" if bot_type == "MaiBot" else "mofox_path"
        
        paths = {
            bot_path_key: "",
            "adapter_path": "",
            "napcat_path": "",
            "venv_path": "",
            "webui_path": "",
            "mongodb_path": deploy_config.get("mongodb_path", ""),
        }

        # 步骤1：安装Bot
        if bot_type == "MaiBot":
            paths[bot_path_key] = self.maibot_deployer.install_bot(deploy_config)
        else:
            paths[bot_path_key] = self.mofox_deployer.install_bot(deploy_config)
        
        if not paths[bot_path_key]:
            raise Exception(f"{bot_type}安装失败")

        # 步骤2：处理适配器路径
        if deploy_config.get("install_adapter"):
            if bot_type == "MaiBot":
                paths["adapter_path"] = self.maibot_deployer.install_adapter(deploy_config, paths[bot_path_key])
            else:
                # MoFox_bot可能有外置适配器
                ui.console.print("\n[🔌 第二步：适配器配置]", style=ui.colors["primary"])
                ui.print_info("MoFox_bot已内置适配器，跳过外置适配器安装")
                paths["adapter_path"] = "内置适配器"
        elif bot_type == "MoFox_bot":
            ui.print_info("检测到MoFox_bot，将记录内置适配器路径")
            # 修改：适配器安装到主程序的同父级目录下，而非主程序目录下
            bot_parent_dir = os.path.dirname(paths[bot_path_key])
            paths["adapter_path"] = os.path.join(bot_parent_dir, "MoFox_bot-Adapter")

        # 步骤3：安装NapCat
        if deploy_config.get("install_napcat") and deploy_config.get("napcat_version"):
            paths["napcat_path"] = self.napcat_deployer.install_napcat(deploy_config, paths[bot_path_key])

        # 步骤4：安装WebUI
        if bot_type == "MaiBot" and deploy_config.get("install_webui"):
            success, paths["webui_path"] = self._check_and_install_webui(deploy_config, paths[bot_path_key])
            if not success:
                ui.print_warning("WebUI安装检查失败，但部署将继续...")
        elif bot_type == "MoFox_bot" and deploy_config.get("install_mofox_admin_ui"):
            success, paths["webui_path"] = self._install_mofox_admin_ui(deploy_config)
            if not success:
                ui.print_warning("MoFox_bot后台管理WebUI安装失败，但部署将继续...")

        # 步骤5：设置Python环境
        ui.console.print("\n[🐍 第四步：设置Python环境]", style=ui.colors["primary"])
        ui.print_info("正在创建Python虚拟环境...")
        venv_success, venv_path = self.maibot_deployer.create_virtual_environment(paths[bot_path_key])
        
        if venv_success:
            requirements_path = os.path.join(paths[bot_path_key], "requirements.txt")
            
            ui.print_info("正在安装Bot本体依赖...")
            deps_success = self.maibot_deployer.install_dependencies_in_venv(venv_path, requirements_path)
            
            # 安装适配器依赖（如果适配器存在且有requirements.txt）
            adapter_deps_success = True
            adapter_path = paths.get("adapter_path", "")
            if adapter_path and adapter_path not in ["无需适配器", "内置适配器", "跳过适配器安装"] and not ("失败" in adapter_path):
                adapter_requirements_path = os.path.join(adapter_path, "requirements.txt")
                if os.path.exists(adapter_requirements_path):
                    ui.print_info("正在安装napcat适配器依赖...")
                    adapter_deps_success = self.maibot_deployer.install_dependencies_in_venv(venv_path, adapter_requirements_path)
                else:
                    ui.print_info("适配器无requirements.txt文件，跳过适配器依赖安装")

            if deps_success and adapter_deps_success:
                ui.print_success("✅ Python环境设置完成")
            else:
                ui.print_warning("⚠️ 依赖安装失败，但继续部署过程")
            
            paths["venv_path"] = venv_path
        else:
            ui.print_warning("⚠️ 虚拟环境创建失败，将使用系统Python")
            paths["venv_path"] = ""
        
        # 为MaiBot的WebUI安装后端依赖
        if bot_type == "MaiBot" and paths.get("webui_path") and paths.get("venv_path"):
            ui.console.print("\n[🔄 在虚拟环境中安装WebUI后端依赖]", style=ui.colors["primary"])
            webui_installer.install_webui_backend_dependencies(paths["webui_path"], paths["venv_path"])

        # 步骤6：配置文件设置
        if bot_type == "MaiBot":
            if not self.maibot_deployer.setup_config_files(
                deploy_config, 
                paths[bot_path_key], 
                paths.get("adapter_path", ""),
                paths.get("napcat_path", ""),
                paths.get("mongodb_path", ""),
                paths.get("webui_path", "")
            ):
                ui.print_warning("配置文件设置失败，但部署将继续...")
        else:
            if not self.mofox_deployer.setup_config_files(
                deploy_config, 
                paths[bot_path_key], 
                paths.get("adapter_path", ""),
                paths.get("napcat_path", ""),
                paths.get("mongodb_path", ""),
                paths.get("webui_path", "")
            ):
                ui.print_warning("配置文件设置失败，但部署将继续...")

        return paths

    def _finalize_deployment(self, deploy_config: Dict, **paths: str) -> bool:
        """第七步：完成部署配置"""
        bot_type = deploy_config.get("bot_type", "MaiBot")
        bot_path_key = "mai_path" if bot_type == "MaiBot" else "mofox_path"
        bot_path = paths.get(bot_path_key, "")
        
        ui.console.print("\n[⚙️ 第七步：完成部署配置]", style=ui.colors["primary"])
        adapter_path = paths["adapter_path"]
        napcat_path = paths["napcat_path"]
        venv_path = paths["venv_path"]
        webui_path = paths["webui_path"]
        mongodb_path = paths["mongodb_path"]
        
        # 创建配置
        ui.print_info("正在创建实例配置...")
        
        # 根据部署选项创建安装选项配置
        install_options = {
            "install_adapter": bool(adapter_path and adapter_path not in ["无需适配器", "跳过适配器安装"]),
            "install_napcat": deploy_config.get("install_napcat", False),
            "install_mongodb": bool(deploy_config.get("mongodb_path", "")),
            "install_webui": deploy_config.get("install_webui", False),
            "install_mofox_admin_ui": deploy_config.get("install_mofox_admin_ui", False)
        }
        
        new_config = {
            "serial_number": deploy_config["serial_number"],
            "absolute_serial_number": config_manager.generate_unique_serial(),
            "version_path": deploy_config["selected_version"]["name"],
            "nickname_path": deploy_config["nickname"],
            "bot_type": bot_type,  # 添加bot类型
            "qq_account": deploy_config.get("qq_account", ""),
            bot_path_key: bot_path,
            "adapter_path": adapter_path,
            "napcat_path": napcat_path,
            "venv_path": venv_path,
            "mongodb_path": mongodb_path,
            "webui_path": webui_path,
            "install_options": install_options
        }
        
        # 保存配置
        config_name = f"instance_{deploy_config['serial_number']}"
        if not config_manager.add_configuration(config_name, new_config):
            ui.print_error("配置保存失败")
            return False
        
        config_manager.set("current_config", config_name)
        config_manager.save()
        ui.print_success("实例配置创建完成")
        
        # 显示配置摘要
        ui.console.print("\n[📋 部署摘要]", style=ui.colors["info"])
        ui.console.print(f"实例名称：{deploy_config['nickname']}")
        ui.console.print(f"序列号：{deploy_config['serial_number']}")
        ui.console.print(f"Bot类型：{bot_type}")
        ui.console.print(f"版本：{deploy_config['selected_version']['name']}")
        ui.console.print(f"安装路径：{bot_path}")
        
        ui.console.print("\n[🔧 已安装组件]", style=ui.colors["success"])
        ui.console.print(f"  • {bot_type}主体：✅")
        ui.console.print(f"  • 适配器：{'✅' if install_options['install_adapter'] else '❌'}")
        ui.console.print(f"  • NapCat：{'✅' if install_options['install_napcat'] else '❌'}")
        ui.console.print(f"  • MongoDB：{'✅' if install_options['install_mongodb'] else '❌'}")
        webui_name = "MoFox_bot后台管理WebUI" if bot_type == "MoFox_bot" else "WebUI"
        webui_installed = install_options.get('install_webui', False) or install_options.get('install_mofox_admin_ui', False)
        ui.console.print(f"  • {webui_name}：{'✅' if webui_installed else '❌'}")
        
        ui.print_success("✅ 部署配置完成")
        logger.info("配置创建成功", config=new_config)
        return True
    
    def _show_post_deployment_info(self, bot_path: str, bot_config: Dict, adapter_path: str = ""):
        """显示部署后的信息并提供打开配置文件的选项"""
        version_info = bot_config.get("selected_version", {})
        version_name = version_info.get("name", "")
        bot_type = bot_config.get("bot_type", "MaiBot")

        is_modern_config = compare_versions(version_name, "0.10.0") >= 0
        is_maibot_branch_not_classical = (bot_type == "MaiBot" and
                                      version_info.get("type") == "branch" and
                                      version_info.get("name") != "classical")

        ui.console.print("\n[📝 后续配置提醒]", style=ui.colors["info"])
        if is_modern_config or bot_type == "MoFox_bot" or is_maibot_branch_not_classical:
            ui.console.print("1. 在 'config/model_config.toml' 文件中配置您的API密钥。", style=ui.colors["attention"])
        else:
            ui.console.print("1. 在根目录的 '.env' 文件中配置您的APIKey（MaiCore的0.10.0及以上版本已经转移至model_config.toml文件中，LPMM知识库构建所需模型亦在此文件中配置）。", style=ui.colors["attention"])

        ui.console.print("2. 修改 'config/bot_config.toml' 中的机器人配置。", style=ui.colors["attention"])

        # 检查是否有 lpmm_config.toml
        if os.path.exists(os.path.join(bot_path, 'config', 'lpmm_config.toml')):
            ui.console.print("3. 如需使用LPMM知识库，请在 'config/lpmm_config.toml'中添加用于LPMM知识库构建所需的APIKey。", style=ui.colors["attention"])

        ui.console.print("4. 如安装了NapCat，请配置QQ登录和WebSocket连接参数。", style=ui.colors["attention"])
        ui.console.print("\n您现在可以通过主菜单的启动选项来运行该实例。", style=ui.colors["success"])

        # 询问是否打开配置文件 - 在询问前发送通知
        if windows_notifier.is_enabled():
            windows_notifier.send("部署即将完成", "是否在文本编辑器中打开配置文件？")
        
        if ui.confirm("\n是否立即在文本编辑器中打开主要配置文件？"):
            files_to_open = []
            
            # 始终打开.env文件（墨狐和麦麦都要打开）
            env_file = os.path.join(bot_path, ".env")
            if os.path.exists(env_file):
                files_to_open.append(env_file)
            
            # 确定要打开的配置文件
            if is_modern_config or bot_type == "MoFox_bot" or is_maibot_branch_not_classical:
                model_config = os.path.join(bot_path, "config", "model_config.toml")
                if os.path.exists(model_config):
                    files_to_open.append(model_config)
            
            bot_config_file = os.path.join(bot_path, "config", "bot_config.toml")
            if os.path.exists(bot_config_file):
                files_to_open.append(bot_config_file)

            # 处理适配器配置文件
            is_mofox_internal_adapter = (bot_type == "MoFox_bot" and not bot_config.get("install_adapter"))

            if adapter_path and adapter_path not in ["无需适配器", "内置适配器"]:
                adapter_config_file = os.path.join(adapter_path, "config.toml")
                if os.path.exists(adapter_config_file):
                    files_to_open.append(adapter_config_file)
                elif is_mofox_internal_adapter:
                    # 如果MoFox_bot的内置适配器配置不存在，检查plugins文件夹
                    plugins_folder = os.path.join(bot_path, "config", "plugins")
                    if not os.path.exists(plugins_folder):
                        ui.print_warning("内置适配器配置文件尚未生成，请先启动一次主程序以自动创建，然后再使用本功能打开。")

            if files_to_open:
                open_files_in_editor(files_to_open)
    
    def _check_and_install_webui(self, deploy_config: Dict, bot_path: str, venv_path: str = "") -> Tuple[bool, str]:
        """检查并安装WebUI（如果需要）"""
        try:
            ui.console.print("\n[🌐 WebUI安装检查]", style=ui.colors["primary"])
            
            # 获取安装目录
            install_dir = deploy_config.get("install_dir", "")
            
            logger.info("开始WebUI安装检查", install_dir=install_dir, bot_path=bot_path)
            
            # 调用WebUI安装器进行直接安装，传入虚拟环境路径
            success, webui_path = webui_installer.install_webui_directly(install_dir, venv_path)
            
            if success:
                ui.print_success("✅ WebUI安装检查完成")
                if webui_path:
                    ui.print_info(f"WebUI安装路径: {webui_path}")
            else:
                ui.print_warning("⚠️ WebUI安装检查出现问题")
            
            return success, webui_path
            
        except Exception as e:
            ui.print_error(f"WebUI安装检查失败：{str(e)}")
            logger.error("WebUI安装检查失败", error=str(e))
            return False, ""
    
    def _install_mofox_admin_ui(self, deploy_config: Dict) -> Tuple[bool, str]:
        """安装MoFox_bot后台管理WebUI"""
        ui.console.print("\n[🦊 安装MoFox_bot后台管理WebUI]", style=ui.colors["primary"])
        
        try:
            # First, check for NodeJS
            ui.print_info("检查Node.js环境...")
            node_installed, _ = webui_installer.check_nodejs_installed()
            npm_installed, _ = webui_installer.check_npm_installed()

            if not node_installed or not npm_installed:
                ui.print_warning("未检测到Node.js或npm")
                ui.print_info("WebUI需要Node.js环境支持")
                if ui.confirm("是否自动安装Node.js？"):
                    if not webui_installer.install_nodejs():
                        ui.print_error("Node.js安装失败，跳过WebUI安装")
                        return False, ""
                else:
                    ui.print_info("已跳过WebUI安装")
                    return True, ""  # Not a failure, just skipped.

            install_dir = deploy_config["install_dir"]
            
            ui.print_info("正在下载MoFox_bot后台管理WebUI...")
            
            download_url = "https://github.com/MoFox-Studio/MoFox-UI/archive/refs/heads/main.zip"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                archive_path = os.path.join(temp_dir, "mofox_ui.zip")
                
                if not self.maibot_deployer.download_file(download_url, archive_path):
                    ui.print_error("MoFox_bot WebUI下载失败")
                    return False, ""

                # 解压
                if not self.maibot_deployer.extract_archive(archive_path, temp_dir):
                    ui.print_error("MoFox_bot WebUI解压失败")
                    return False, ""
                
                # 查找解压后的目录
                extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d)) and "MoFox-UI" in d]
                if not extracted_dirs:
                    ui.print_error("解压后未找到MoFox-UI目录")
                    return False, ""
                
                source_dir = os.path.join(temp_dir, extracted_dirs[0])
                
                # 重命名为 'webui' 并移动
                webui_path = os.path.join(install_dir, "webui")
                if os.path.exists(webui_path):
                    ui.print_warning(f"目录 '{webui_path}' 已存在，将覆盖。")
                    shutil.rmtree(webui_path)
                
                shutil.move(source_dir, webui_path)
                ui.print_success(f"WebUI源码已移动到: {webui_path}")

                # 安装依赖
                ui.print_info("正在安装WebUI依赖 (npm install)...")
                
                result = subprocess.run(
                    ["npm", "install"],
                    cwd=webui_path,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )

                if result.returncode == 0:
                    ui.print_success("✅ WebUI依赖安装完成")
                    logger.info("MoFox WebUI依赖安装成功", path=webui_path)
                    return True, webui_path
                else:
                    ui.print_error("❌ WebUI依赖安装失败")
                    ui.console.print(result.stdout)
                    ui.console.print(result.stderr)
                    logger.error("MoFox WebUI依赖安装失败", error=result.stderr)
                    return True, webui_path

        except Exception as e:
            ui.print_error(f"MoFox_bot WebUI安装失败：{str(e)}")
            logger.error("MoFox_bot WebUI安装失败", error=str(e))
            return False, ""
    
    def update_instance(self) -> bool:
        """更新实例 - 待实现"""
        ui.print_warning("实例更新功能暂未实现")
        return False
    
    def delete_instance(self) -> bool:
        """删除实例并提供备份选项 - 支持通过序列号直接匹配"""
        set_console_log_level("WARNING")
        try:
            ui.clear_screen()
            ui.components.show_title("实例删除助手", symbol="🗑️")

            # 获取所有实例配置
            configs = config_manager.get_all_configurations()
            if not configs:
                ui.print_error("当前没有可删除的实例配置！")
                return False

            # 显示所有实例
            from rich.table import Table
            table = Table(show_header=True, header_style=ui.colors["table_header"], title="[bold]可删除实例列表[/bold]", title_style=ui.colors["primary"], border_style=ui.colors["border"])
            table.add_column("实例昵称", style="green", width=20)
            table.add_column("序列号", style="yellow", width=20)
            table.add_column("安装路径", style="blue", width=40)
            table.add_column("Bot类型", style="magenta", width=12)

            config_keys = list(configs.keys())
            for key in config_keys:
                cfg = configs[key]
                bot_type = str(cfg.get("bot_type", "MaiBot"))
                bot_path = cfg.get("mai_path") if bot_type == "MaiBot" else cfg.get("mofox_path")
                bot_path = str(bot_path) if bot_path else "-"
                nickname = str(cfg.get("nickname_path", "-"))
                serial = str(cfg.get("serial_number", "-"))
                table.add_row(
                    nickname, 
                    serial, 
                    bot_path, 
                    bot_type
                )

            ui.console.print(table)
            ui.console.print("\n[Q] 取消删除", style=ui.colors["exit"])
            ui.console.print(f"提示：共有 {len(config_keys)} 个实例可删除", style=ui.colors["info"])

            # 输入序列号进行匹配
            while True:
                serial_input = ui.get_input("请输入要删除实例的序列号: ").strip()
                if serial_input.upper() == "Q":
                    ui.print_info("已取消删除操作。")
                    return False
                
                # 匹配实例
                matched_key = None
                matched_cfg = None
                for key in config_keys:
                    cfg = configs[key]
                    if str(cfg.get("serial_number", "")) == serial_input:
                        matched_key = key
                        matched_cfg = cfg
                        break
                
                if matched_cfg:
                    break
                else:
                    ui.print_error(f"未找到序列号为 '{serial_input}' 的实例，请重新输入。")

            # 显示匹配实例详情
            bot_type = matched_cfg.get("bot_type", "MaiBot")
            bot_path = matched_cfg.get("mai_path") if bot_type == "MaiBot" else matched_cfg.get("mofox_path")
            nickname = matched_cfg.get("nickname_path", "-")
            
            ui.console.print(f"\n[⚠️ 找到匹配实例]", style=ui.colors["warning"])
            ui.console.print(f"实例昵称: {nickname}", style=ui.colors["info"])
            ui.console.print(f"序列号: {serial_input}", style=ui.colors["info"])
            ui.console.print(f"Bot类型: {bot_type}", style=ui.colors["info"])
            ui.console.print(f"安装路径: {bot_path or '-'}", style=ui.colors["info"])
            
            # 严格的确认逻辑 - 第一次确认
            ui.console.print(f"\n[❗] 警告：此操作将永久删除该实例的所有文件和配置！", style="bold red")
            first_confirm = ui.get_input("请输入实例昵称以确认删除: ").strip()
            if first_confirm != nickname:
                ui.print_error(f"输入的昵称不匹配，已取消删除操作。")
                return False
            
            # 第二次确认
            second_confirm = ui.get_input(f"再次确认：请输入 'DELETE' 以继续删除操作: ").strip()
            if second_confirm != "DELETE":
                ui.print_error(f"确认失败，已取消删除操作。")
                return False

            # 获取昵称目录（父目录）
            bot_instance_dir = bot_path  # Bot实例目录 (如: D:\test\mofox\MaiBot)
            nickname_dir = os.path.dirname(bot_instance_dir) if bot_instance_dir else None  # 昵称目录 (如: D:\test\mofox)
            
            if not nickname_dir or not os.path.exists(nickname_dir):
                ui.print_error("未找到实例目录，无法继续删除操作。")
                return False
            
            # 检查昵称目录下是否存在其他组件
            other_components = []
            if nickname_dir and os.path.exists(nickname_dir):
                for item in os.listdir(nickname_dir):
                    item_path = os.path.join(nickname_dir, item)
                    if os.path.isdir(item_path):
                        # 排除Bot本体目录
                        if item_path != bot_instance_dir:
                            other_components.append((item, item_path))
            
            # 询问是否一起删除其他组件
            backup_components = False
            if other_components:
                ui.console.print(f"\n[ℹ️] 发现昵称目录下存在其他组件:", style=ui.colors["info"])
                for comp_name, _ in other_components:
                    ui.console.print(f"  - {comp_name}", style="cyan")
                backup_components = ui.confirm("是否备份这些组件？")
            
            # 备份与删除逻辑
            if ui.confirm("是否在删除前备份实例数据？"):
                try:
                    parent_dir = os.path.dirname(nickname_dir)
                    delete_target = os.path.join(parent_dir, f"{os.path.basename(nickname_dir)}-delete")
                    
                    # 如果目标已存在，先删除
                    if os.path.exists(delete_target):
                        ui.print_warning(f"目标目录已存在，将先删除: {delete_target}")
                        shutil.rmtree(delete_target)
                    
                    # 创建删除目录
                    os.makedirs(delete_target, exist_ok=True)
                    ui.print_info(f"备份将保存到: {delete_target}")
                    
                    # 备份 Bot 本体的 data 和 config 文件夹
                    bot_data_dir = os.path.join(bot_instance_dir, "data")
                    bot_config_dir = os.path.join(bot_instance_dir, "config")
                    
                    if os.path.exists(bot_data_dir):
                        target_path = os.path.join(delete_target, "data")
                        shutil.copytree(bot_data_dir, target_path, dirs_exist_ok=True)
                        ui.print_success(f"✅ 已备份: data")
                    
                    if os.path.exists(bot_config_dir):
                        target_path = os.path.join(delete_target, "config")
                        shutil.copytree(bot_config_dir, target_path, dirs_exist_ok=True)
                        ui.print_success(f"✅ 已备份: config")
                    
                    # 如果用户选择备份其他组件，复制整个组件目录
                    if backup_components and other_components:
                        for comp_name, comp_path in other_components:
                            target_comp_path = os.path.join(delete_target, comp_name)
                            shutil.copytree(comp_path, target_comp_path, dirs_exist_ok=True)
                            ui.print_success(f"✅ 已备份组件: {comp_name}")
                    
                    ui.print_success(f"备份完成: {delete_target}")
                    
                    # 删除原始昵称目录
                    ui.print_info(f"正在删除原目录: {nickname_dir}")
                    shutil.rmtree(nickname_dir)
                    ui.print_success(f"✅ 已删除原目录")
                    
                except Exception as e:
                    ui.print_error(f"备份或删除失败: {str(e)}")
                    if not ui.confirm("操作失败，是否继续尝试直接删除？"):
                        ui.print_info("已取消删除操作。")
                        return False
                    # 尝试直接删除
                    try:
                        shutil.rmtree(nickname_dir)
                        ui.print_success(f"已直接删除目录: {nickname_dir}")
                    except Exception as e2:
                        ui.print_error(f"直接删除也失败: {str(e2)}")
                        return False
            else:
                # 不备份，直接删除
                try:
                    ui.print_warning(f"将直接删除目录（不备份）: {nickname_dir}")
                    shutil.rmtree(nickname_dir)
                    ui.print_success(f"✅ 已删除目录: {nickname_dir}")
                except Exception as e:
                    ui.print_error(f"删除失败: {str(e)}")
                    return False

            # 删除配置
            if matched_key is not None and config_manager.delete_configuration(matched_key):
                ui.print_success("已删除实例配置。")
            else:
                ui.print_warning("实例配置删除失败，请手动检查。")

            config_manager.save()
            ui.print_success("实例删除操作完成！")
            logger.info("实例删除完成", serial=cfg.get("serial_number", "-"), nickname=cfg.get("nickname_path", "-"))
            return True
        except Exception as e:
            ui.print_error(f"实例删除失败: {str(e)}")
            logger.error("实例删除失败", error=str(e))
            return False
        finally:
            reset_console_log_level()


# 全局部署管理器实例
deployment_manager = DeploymentManager()
