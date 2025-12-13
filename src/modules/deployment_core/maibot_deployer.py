# -*- coding: utf-8 -*-
"""
MaiBot部署器
负责MaiBot的部署逻辑，包括版本检测、适配器安装等
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
from ...utils.version_detector import get_version_requirements, compare_versions

logger = structlog.get_logger(__name__)


class MaiBotDeployer(BaseDeployer):
    """MaiBot部署器"""
    
    def __init__(self):
        super().__init__()
        self.repo = "MaiM-with-u/MaiBot"
        self.adapter_repo = "MaiM-with-u/MaiBot-Napcat-Adapter"
        self.version_manager = VersionManager(self.repo)
    
    def install_bot(self, deploy_config: Dict) -> Optional[str]:
        """
        安装MaiBot主体
        
        Args:
            deploy_config: 部署配置
            
        Returns:
            MaiBot安装路径，失败返回None
        """
        ui.console.print("\n[📦 第一步：安装MaiBot]", style=ui.colors["primary"])
        
        selected_version = deploy_config["selected_version"]
        install_dir = deploy_config["install_dir"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 下载源码
            ui.print_info("正在下载MaiBot源码...")
            download_url = selected_version["download_url"]
            archive_path = os.path.join(temp_dir, f"{selected_version['name']}.zip")
            
            if not self.download_file(download_url, archive_path):
                ui.print_error("MaiBot下载失败")
                return None
            
            # 解压到临时目录
            ui.print_info("正在解压MaiBot...")
            if not self.extract_archive(archive_path, temp_dir):
                ui.print_error("MaiBot解压失败")
                return None
            
            # 查找解压后的目录
            extracted_dirs = [d for d in os.listdir(temp_dir)
                            if os.path.isdir(os.path.join(temp_dir, d)) and d != "__MACOSX"]
            if not extracted_dirs:
                ui.print_error("解压后未找到项目目录")
                return None
            
            source_dir = os.path.join(temp_dir, extracted_dirs[0])
            
            # 创建目标目录并复制文件
            os.makedirs(install_dir, exist_ok=True)
            target_dir = os.path.join(install_dir, "MaiBot")
            
            # 检查目标目录是否已存在
            if os.path.exists(target_dir):
                ui.print_warning(f"目标目录已存在，将先删除: {target_dir}")
                try:
                    shutil.rmtree(target_dir)
                except Exception as e:
                    ui.print_error(f"删除旧目录失败: {str(e)}")
                    return None
            
            ui.print_info("正在安装MaiBot文件...")
            shutil.copytree(source_dir, target_dir)
            
            ui.print_success("✅ MaiBot安装完成")
            logger.info("MaiBot安装成功", path=target_dir)
            return target_dir
    
    def install_adapter(self, deploy_config: Dict, bot_path: str) -> str:
        """
        检测版本并安装适配器
        
        Args:
            deploy_config: 部署配置
            bot_path: MaiBot路径
            
        Returns:
            适配器路径或状态信息
        """
        ui.console.print("\n[🔌 第二步：检测版本并安装适配器]", style=ui.colors["primary"])
        
        # 使用配置版本信息进行判断
        selected_version = deploy_config["selected_version"]
        version_name = selected_version.get("name", "")
        display_name = selected_version.get("display_name", "")
        
        ui.print_info(f"版本名称：{version_name}")
        ui.print_info(f"显示名称：{display_name}")
        
        # 优先使用display_name进行版本判断
        version_to_check = display_name if display_name else version_name
        
        ui.print_info("适配器选择规则：")
        ui.console.print("  • 0.5.x及以下：无需适配器")
        ui.console.print("  • 0.6.x 版本：使用0.2.3版本适配器")
        ui.console.print("  • 0.7.x-0.8.x 版本：使用0.4.2版本适配器")
        ui.console.print("  • main分支：使用main分支适配器")
        ui.console.print("  • dev分支：使用dev分支适配器")
        
        # 判断是否需要适配器
        adapter_path = self._determine_adapter_requirements(version_to_check, bot_path)
        
        if adapter_path == "无需适配器":
            ui.print_success("✅ 当前版本无需适配器")
            return adapter_path
        elif "版本较低" in adapter_path or "未定义" in adapter_path or "失败" in adapter_path:
            ui.print_warning(f"⚠️ {adapter_path}")
            return adapter_path
        else:
            ui.print_success("✅ 适配器安装完成")
            return adapter_path
    
    def _determine_adapter_requirements(self, version: str, maibot_path: str) -> str:
        """确定适配器需求并安装"""
        try:
            # 检查是否已有适配器目录
            potential_adapter_paths = [
                os.path.join(maibot_path, "adapter"),
                os.path.join(maibot_path, "MaiBot-Napcat-Adapter"),
                os.path.join(maibot_path, "napcat-adapter")
            ]
            
            for path in potential_adapter_paths:
                if os.path.exists(path):
                    ui.print_info(f"发现已存在的适配器：{path}")
                    return path
            
            # 使用版本检测模块
            version_reqs = get_version_requirements(version)
            
            ui.print_info(f"版本分析结果：")
            ui.print_info(f"  版本号：{version}")
            ui.print_info(f"  是否旧版本：{version_reqs['is_legacy']}")
            ui.print_info(f"  需要适配器：{version_reqs['needs_adapter']}")
            ui.print_info(f"  适配器版本：{version_reqs['adapter_version']}")
            
            # 检查是否需要适配器
            if not version_reqs["needs_adapter"]:
                return "无需适配器"
            
            adapter_version = version_reqs["adapter_version"]
            
            # 根据适配器版本下载
            return self._download_specific_adapter_version(adapter_version, maibot_path)
                
        except Exception as e:
            ui.print_error(f"适配器处理失败：{str(e)}")
            logger.error("适配器处理异常", error=str(e))
            return "适配器处理失败"
    
    def _download_specific_adapter_version(self, adapter_version: str, maibot_path: str) -> str:
        """下载特定版本的适配器"""
        with tempfile.TemporaryDirectory() as temp_dir:
            if adapter_version in ["main", "dev"]:
                ui.print_info(f"正在下载{adapter_version}分支的适配器...")
                adapter_url = f"https://codeload.github.com/{self.adapter_repo}/zip/refs/heads/{adapter_version}"
            else:
                ui.print_info(f"正在下载v{adapter_version}版本的适配器...")
                adapter_url = f"https://codeload.github.com/{self.adapter_repo}/zip/refs/tags/{adapter_version}"
            
            adapter_zip = os.path.join(temp_dir, f"adapter_{adapter_version}.zip")
            
            if not self.download_file(adapter_url, adapter_zip):
                ui.print_warning(f"适配器下载失败")
                return f"适配器下载失败"
            
            # 解压到临时目录
            temp_extract = os.path.join(temp_dir, f"adapter_extract")
            if not self.extract_archive(adapter_zip, temp_extract):
                ui.print_warning("适配器解压失败")
                return "适配器解压失败"
            
            # 查找解压后的目录并复制到正确位置
            extracted_dirs = [d for d in os.listdir(temp_extract) 
                            if os.path.isdir(os.path.join(temp_extract, d))]
            
            # 修改：适配器安装到主程序的同父级目录下，而非主程序目录下
            maibot_parent_dir = os.path.dirname(maibot_path)
            adapter_extract_path = os.path.join(maibot_parent_dir, "MaiBot-Napcat-Adapter")
            
            if extracted_dirs:
                # 找到解压后的根目录
                source_adapter_dir = os.path.join(temp_extract, extracted_dirs[0])
                
                # 确保目标目录不存在，然后复制
                if os.path.exists(adapter_extract_path):
                    shutil.rmtree(adapter_extract_path)
                shutil.copytree(source_adapter_dir, adapter_extract_path)
                
                ui.print_success(f"适配器安装完成")
                logger.info("适配器安装成功", version=adapter_version, path=adapter_extract_path)
                return adapter_extract_path
            else:
                ui.print_warning("适配器解压后未找到目录")
                return "适配器解压失败"
    
    def setup_config_files(self, deploy_config: Dict, bot_path: str, 
                          adapter_path: str = "", napcat_path: str = "",
                          mongodb_path: str = "", webui_path: str = "") -> bool:
        """
        设置MaiBot配置文件
        
        Args:
            deploy_config: 部署配置
            bot_path: MaiBot路径
            adapter_path: 适配器路径
            napcat_path: NapCat路径
            mongodb_path: MongoDB路径
            webui_path: WebUI路径
            
        Returns:
            是否设置成功
        """
        ui.console.print("\n[⚙️ 第六步：配置文件设置]", style=ui.colors["primary"])
        
        # 获取版本信息以进行条件判断
        version_name = deploy_config.get("selected_version", {}).get("name", "")

        try:
            # 准备路径
            config_dir = os.path.join(bot_path, "config")
            template_dir = os.path.join(bot_path, "template")
            
            # 1. 处理Bot主程序配置文件
            ui.print_info("正在设置MaiBot配置文件...")
            
            # Case: MaiBot >= 0.10.0
            if compare_versions(version_name, "0.10.0") >= 0:
                os.makedirs(config_dir, exist_ok=True)
                ui.print_info("为 MaiBot >= 0.10.0 创建标准配置文件...")

                # 复制 bot_config_template.toml
                bot_config_template = os.path.join(template_dir, "bot_config_template.toml")
                bot_config_target = os.path.join(config_dir, "bot_config.toml")
                if os.path.exists(bot_config_template):
                    shutil.copy2(bot_config_template, bot_config_target)
                    ui.print_success("✅ bot_config.toml 配置完成")
                else:
                    ui.print_warning(f"⚠️ 未找到模板: {bot_config_template}")

                # 复制 model_config_template.toml
                model_config_template = os.path.join(template_dir, "model_config_template.toml")
                model_config_target = os.path.join(config_dir, "model_config.toml")
                if os.path.exists(model_config_template):
                    shutil.copy2(model_config_template, model_config_target)
                    ui.print_success("✅ model_config.toml 配置完成")
                else:
                    ui.print_warning(f"⚠️ 未找到模板: {model_config_template}")
                
                # 仅在部署MoFox_bot实例时处理插件配置
                if deploy_config.get("bot_type") == "MoFox_bot":
                    plugin_template = os.path.join(template_dir, "plugin_config_template.toml")
                    plugin_target = os.path.join(config_dir, "plugin_config.toml")
                    if os.path.exists(plugin_template):
                        shutil.copy2(plugin_template, plugin_target)
                        ui.print_success("✅ plugin_config.toml 配置完成")
                    else:
                        ui.print_warning(f"⚠️ 未找到模板: plugin_config_template.toml")
            
            # Case: 其他所有情况 (旧版MaiBot, MaiBot分支)
            else:
                os.makedirs(config_dir, exist_ok=True)
                ui.print_info(f"为 MaiBot v{version_name} 创建标准配置文件...")
                
                # 复制 bot_config_template.toml (通用)
                bot_config_template = os.path.join(template_dir, "bot_config_template.toml")
                bot_config_target = os.path.join(config_dir, "bot_config.toml")
                if os.path.exists(bot_config_template):
                    shutil.copy2(bot_config_template, bot_config_target)
                    ui.print_success("✅ bot_config.toml 配置完成")
                else:
                    ui.print_warning(f"⚠️ 未找到模板: {bot_config_template}")

                # 非classical分支需要model_config.toml
                version_info = deploy_config.get("selected_version", {})
                is_maibot_branch_not_classical = (
                    version_info.get("type") == "branch" and
                    version_info.get("name") != "classical"
                )

                if is_maibot_branch_not_classical:
                    model_config_template = os.path.join(template_dir, "model_config_template.toml")
                    model_config_target = os.path.join(config_dir, "model_config.toml")
                    if os.path.exists(model_config_template):
                        shutil.copy2(model_config_template, model_config_target)
                        ui.print_success("✅ model_config.toml 配置完成")
                    else:
                        ui.print_warning(f"⚠️ 未找到模板: {model_config_template}")

                # 特定旧版的 lpmm_config.toml
                if (compare_versions(version_name, "0.6.3") >= 0 and 
                    compare_versions(version_name, "0.10.0") < 0):
                    lpmm_template = os.path.join(template_dir, "lpmm_config_template.toml")
                    lpmm_target = os.path.join(config_dir, "lpmm_config.toml")
                    if os.path.exists(lpmm_template):
                        shutil.copy2(lpmm_template, lpmm_target)
                        ui.print_success("✅ lpmm_config.toml 配置完成")
                    else:
                        ui.print_warning(f"⚠️ 未找到模板: lpmm_config_template.toml")

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

            # 2. 处理适配器配置文件
            if adapter_path and adapter_path not in ["无需适配器", "跳过适配器安装"] and not ("失败" in adapter_path):
                ui.print_info("正在设置适配器配置文件...")
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
                    ui.print_info("适配器无需额外配置文件")

            # 3. 配置提示
            if napcat_path:
                ui.print_info("NapCat配置提醒:")
                ui.console.print("  • 请参考 https://docs.mai-mai.org/manual/adapters/napcat.html")

            if mongodb_path:
                ui.print_info("MongoDB配置完成:")
                ui.console.print(f"  • MongoDB路径: {mongodb_path}")
            
            if webui_path:
                ui.print_info("WebUI配置完成:")
                ui.console.print(f"  • WebUI路径: {webui_path}")
            
            ui.print_success("✅ 配置文件设置完成")
            return True
            
        except Exception as e:
            ui.print_error(f"配置文件设置失败: {str(e)}")
            logger.error("配置文件设置失败", error=str(e))
            return False
