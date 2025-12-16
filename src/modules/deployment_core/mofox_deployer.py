# -*- coding: utf-8 -*-
"""
MoFox_bot部署器
负责MoFox_bot的部署逻辑
"""
import os
import re
import shutil
import tempfile
from typing import Dict, Optional
import structlog

from .base_deployer import BaseDeployer
from .version_manager import VersionManager
from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class MoFoxBotDeployer(BaseDeployer):
    """MoFox_bot部署器"""
    
    def __init__(self):
        super().__init__()
        self.repo = "MoFox-Studio/MoFox_Bot"
        self.version_manager = VersionManager(self.repo)
    
    def install_bot(self, deploy_config: Dict) -> Optional[str]:
        """
        安装MoFox_bot主体
        
        Args:
            deploy_config: 部署配置
            
        Returns:
            MoFox_bot安装路径，失败返回None
        """
        ui.console.print("\n[📦 第一步：安装MoFox_bot]", style=ui.colors["primary"])
        
        selected_version = deploy_config["selected_version"]
        install_dir = deploy_config["install_dir"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 下载源码
            ui.print_info("正在下载MoFox_bot源码...")
            download_url = selected_version["download_url"]
            archive_path = os.path.join(temp_dir, f"{selected_version['name']}.zip")
            
            if not self.download_file(download_url, archive_path):
                ui.print_error("MoFox_bot下载失败")
                return None
            
            # 解压到临时目录
            ui.print_info("正在解压MoFox_bot...")
            if not self.extract_archive(archive_path, temp_dir):
                ui.print_error("MoFox_bot解压失败")
                return None
            
            # 查找解压后的目录
            extracted_dirs = [d for d in os.listdir(temp_dir)
                            if os.path.isdir(os.path.join(temp_dir, d)) and d != "__MACOSX"]
            if not extracted_dirs:
                ui.print_error("解压后未找到项目目录")
                return None
            
            source_dir = os.path.join(temp_dir, extracted_dirs[0])
            
            # 创建目标目录并复制文件
            # 使用实例名称作为父目录，与MaiBot保持一致
            nickname = deploy_config.get("nickname", "MoFox_bot_instance")
            instance_dir = os.path.join(install_dir, nickname)
            target_dir = os.path.join(instance_dir, "MoFox_bot")
            
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
            
            ui.print_info("正在安装MoFox_bot文件...")
            shutil.copytree(source_dir, target_dir)
            
            ui.print_success("✅ MoFox_bot安装完成")
            logger.info("MoFox_bot安装成功", path=target_dir)
            return target_dir
    
    def setup_config_files(self, deploy_config: Dict, bot_path: str, 
                          adapter_path: str = "", napcat_path: str = "",
                          mongodb_path: str = "", webui_path: str = "") -> bool:
        """
        设置MoFox_bot配置文件
        
        Args:
            deploy_config: 部署配置
            bot_path: MoFox_bot路径
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
            ui.print_info("正在设置MoFox_bot配置文件...")
            
            os.makedirs(config_dir, exist_ok=True)
            ui.print_info(f"为 MoFox_bot v{version_name} 创建标准配置文件...")
            
            # 复制 bot_config_template.toml (通用)
            bot_config_template = os.path.join(template_dir, "bot_config_template.toml")
            bot_config_target = os.path.join(config_dir, "bot_config.toml")
            if os.path.exists(bot_config_template):
                shutil.copy2(bot_config_template, bot_config_target)
                ui.print_success("✅ bot_config.toml 配置完成")
            else:
                ui.print_warning(f"⚠️ 未找到模板: {bot_config_template}")

            # MoFox_bot需要model_config.toml
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
                ui.print_info("使用MoFox_bot内置适配器，无需额外配置")

            # 3. 配置提示
            if napcat_path:
                ui.print_info("NapCat配置提醒:")
                ui.console.print("  • 请参考 https://docs.mai-mai.org/manual/adapters/napcat.html")

            if mongodb_path:
                ui.print_info("MongoDB配置完成:")
                ui.console.print(f"  • MongoDB路径: {mongodb_path}")
            
            if webui_path:
                ui.print_info("MoFox_bot后台管理WebUI配置完成:")
                ui.console.print(f"  • WebUI路径: {webui_path}")
            
            ui.print_success("✅ 配置文件设置完成")
            return True
            
        except Exception as e:
            ui.print_error(f"配置文件设置失败: {str(e)}")
            logger.error("配置文件设置失败", error=str(e))
            return False
