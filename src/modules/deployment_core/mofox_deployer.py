# -*- coding: utf-8 -*-
"""
MoFox-Core部署器
负责MoFox-Core的部署逻辑
"""
import os
import re
import shutil
import tempfile
from typing import Dict, Optional, Tuple
import structlog

from .base_deployer import BaseDeployer
from .version_manager import VersionManager
from .mofox_webui_deployer import MoFoxWebUIDeployer
from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class MoFoxBotDeployer(BaseDeployer):
    """MoFox-Core部署器"""
    
    def __init__(self):
        super().__init__()
        self.repo = "MoFox-Studio/MoFox-Core"
        self.version_manager = VersionManager(self.repo)
        self.webui_deployer = MoFoxWebUIDeployer()
    
    def install_bot(self, deploy_config: Dict) -> Optional[str]:
        """
        安装MoFox-Core主体
        
        Args:
            deploy_config: 部署配置
            
        Returns:
            MoFox-Core安装路径，失败返回None
        """
        ui.console.print("\n[📦 第一步：安装MoFox-Core]", style=ui.colors["primary"])
        
        selected_version = deploy_config["selected_version"]
        install_dir = deploy_config["install_dir"]
        
        # 使用实例名称作为父目录，与MaiBot保持一致
        nickname = deploy_config.get("nickname", "MoFox-Core_instance")
        instance_dir = os.path.join(install_dir, nickname)
        target_dir = os.path.join(instance_dir, "MoFox-Core")
        
        # 创建实例目录
        os.makedirs(instance_dir, exist_ok=True)
        
        # 检查目标目录是否已存在
        if os.path.exists(target_dir):
            ui.print_warning(f"目标目录已存在，将先删除: {target_dir}")
            try:
                shutil.rmtree(target_dir)
            except Exception as e:
                ui.print_error(f"删除旧目录失败: {str(e)}")
                return None
        
        # 确定分支名称
        version_name = selected_version.get("name", "main")
        version_type = selected_version.get("type", "release")
        
        if version_type == "branch":
            branch = version_name
        else:
            # 对于release版本，使用main分支
            branch = "main"
        
        # 优先使用Git clone，失败时回退到下载压缩包
        fallback_url = selected_version.get("download_url")
        
        if self.download_with_git_fallback(self.repo, target_dir, branch, fallback_url):
            ui.print_success("✅ MoFox-Core安装完成")
            logger.info("MoFox-Core安装成功", path=target_dir, method="git_or_download")
            return target_dir
        else:
            ui.print_error("MoFox-Core安装失败")
            return None
    
    def setup_config_files(self, deploy_config: Dict, bot_path: str, 
                          adapter_path: str = "", napcat_path: str = "",
                          mongodb_path: str = "", webui_path: str = "") -> bool:
        """
        设置MoFox-Core配置文件
        
        Args:
            deploy_config: 部署配置
            bot_path: MoFox-Core路径
            adapter_path: 适配器路径
            napcat_path: NapCat路径
            mongodb_path: MongoDB路径
            webui_path: WebUI路径
            
        Returns:
            是否设置成功
        """
        ui.console.print("\n[⚙️ 第六步：配置文件设置]", style=ui.colors["primary"])
        
        version_name = deploy_config.get("selected_version", {}).get("name", "")

        try:
            # 准备路径
            config_dir = os.path.join(bot_path, "config")
            template_dir = os.path.join(bot_path, "template")
            
            # 1. 处理Bot主程序配置文件
            ui.print_info("正在设置MoFox-Core配置文件...")
            
            os.makedirs(config_dir, exist_ok=True)
            ui.print_info(f"为 MoFox-Core v{version_name} 创建标准配置文件...")
            
            # 复制 bot_config_template.toml (通用)
            bot_config_template = os.path.join(template_dir, "bot_config_template.toml")
            bot_config_target = os.path.join(config_dir, "bot_config.toml")
            if os.path.exists(bot_config_template):
                shutil.copy2(bot_config_template, bot_config_target)
                ui.print_success("✅ bot_config.toml 配置完成")
            else:
                ui.print_warning(f"⚠️ 未找到模板: {bot_config_template}")

            # MoFox-Core需要model_config.toml
            model_config_template = os.path.join(template_dir, "model_config_template.toml")
            model_config_target = os.path.join(config_dir, "model_config.toml")
            if os.path.exists(model_config_template):
                shutil.copy2(model_config_template, model_config_target)
                ui.print_success("✅ model_config.toml 配置完成")
            else:
                ui.print_warning(f"⚠️ 未找到模板: {model_config_template}")

            # 复制 template.env (所有版本都需要)
            env_template = os.path.join(template_dir, "template.env")
            env_target = os.path.join(bot_path, ".env")
            if os.path.exists(env_template):
                shutil.copy2(env_template, env_target)
                try:
                    with open(env_target, 'r+', encoding='utf-8') as f:
                        content = f.read()
                        content = re.sub(r'PORT=\d+', 'PORT=8000', content) if 'PORT=' in content else content + '\nPORT=8000\n'
                        f.seek(0)
                        f.write(content)
                        f.truncate()
                    ui.print_success("✅ .env 配置完成 (PORT=8000)")
                except Exception as e:
                    ui.print_warning(f"⚠️ .env 文件PORT修改失败: {str(e)}")
            else:
                ui.print_warning(f"⚠️ 未找到环境变量模板文件")

            # 2. 处理外置适配器配置文件（如果安装了外置适配器）
            is_external_adapter = deploy_config.get("install_adapter", False)
            if is_external_adapter and adapter_path and adapter_path not in ["无需适配器", "跳过适配器安装"]:
                ui.print_info("正在设置外置适配器配置文件...")
                ui.console.print("\n[ℹ️  外置适配器提醒]", style=ui.colors["info"])
                ui.console.print("墨狐已经将适配器作为插件内置在主程序中。", style="white")
                ui.console.print("如需获取外置适配器，请访问：", style="white")
                ui.console.print("https://github.com/MoFox-Studio/NapCat-Adapter", style="#46AEF8")
                
                adapter_template_dir = os.path.join(adapter_path, "template")
                if os.path.exists(adapter_template_dir):
                    for file in os.listdir(adapter_template_dir):
                        if file.endswith(('.toml', '.json', '.yaml')):
                            source_file = os.path.join(adapter_template_dir, file)
                            target_filename = file.replace('template_', '').replace('_template', '')
                            target_file = os.path.join(adapter_path, target_filename)
                            try:
                                shutil.copy2(source_file, target_file)
                                ui.print_success(f"✅ 适配器配置文件: {target_filename}")
                            except Exception as e:
                                ui.print_warning(f"⚠️ 适配器配置文件复制失败: {file} - {str(e)}")
            else:
                ui.print_info("使用MoFox-Core内置适配器，无需额外配置")

            # 3. 配置提示
            if napcat_path:
                ui.print_info("NapCat配置提醒:")
                ui.console.print("  • 请参考 https://docs.mai-mai.org/manual/adapters/napcat.html")

            if mongodb_path:
                ui.print_info("MongoDB配置完成:")
                ui.console.print(f"  • MongoDB路径: {mongodb_path}")
            
            if webui_path:
                ui.print_info("MoFox-Core后台管理WebUI配置完成:")
                ui.console.print(f"  • WebUI路径: {webui_path}")
            
            ui.print_success("✅ 配置文件设置完成")
            return True
            
        except Exception as e:
            ui.print_error(f"配置文件设置失败: {str(e)}")
            logger.error("配置文件设置失败", error=str(e))
            return False
    
    def install_webui(self, deploy_config: Dict, bot_path: str) -> Tuple[bool, str]:
        """
        安装MoFox WebUI
        
        Args:
            deploy_config: 部署配置
            bot_path: MoFox-Core路径
            
        Returns:
            (是否成功, WebUI路径)
        """
        ui.console.print("\n[🌐 MoFox WebUI安装]", style=ui.colors["primary"])
        
        try:
            # 检查是否需要安装WebUI
            if not deploy_config.get("install_mofox_webui", False):
                ui.print_info("用户选择不安装MoFox WebUI")
                return True, ""
            
            # 使用WebUI部署器安装
            success, webui_path = self.webui_deployer.install_webui(deploy_config, bot_path)
            
            if success:
                ui.print_success("✅ MoFox WebUI安装完成")
                return True, webui_path
            else:
                ui.print_error("❌ MoFox WebUI安装失败")
                return False, ""
                
        except Exception as e:
            ui.print_error(f"MoFox WebUI安装失败: {str(e)}")
            logger.error("MoFox WebUI安装失败", error=str(e))
            return False, ""
