# -*- coding: utf-8 -*-
"""
基础部署器类
提供通用的部署方法和工具函数
"""
import os
import platform
import shutil
import subprocess
import tempfile
import time
import venv
import zipfile
from pathlib import Path
from typing import Tuple, Optional, List
import requests
import structlog
from tqdm import tqdm

from ...ui.interface import ui

logger = structlog.get_logger(__name__)


class BaseDeployer:
    """基础部署器类，提供通用的部署方法"""
    
    def __init__(self):
        self.github_api_base = "https://api.github.com"
    
    def create_virtual_environment(self, target_dir: str) -> Tuple[bool, str]:
        """
        在目标目录创建Python虚拟环境
        
        Args:
            target_dir: 目标目录路径
            
        Returns:
            (是否成功, 虚拟环境路径或错误信息)
        """
        try:
            venv_path = os.path.join(target_dir, "venv")
            
            # 如果虚拟环境已存在，先删除
            if os.path.exists(venv_path):
                ui.print_info("检测到已存在的虚拟环境，正在重新创建...")
                shutil.rmtree(venv_path)
            
            # 创建虚拟环境
            ui.print_info("正在创建Python虚拟环境...")
            logger.info("开始创建虚拟环境", venv_path=venv_path)
            
            venv.create(venv_path, with_pip=True)
            
            # 验证虚拟环境是否创建成功
            if platform.system() == "Windows":
                python_exe = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(venv_path, "bin", "python")
            
            if not os.path.exists(python_exe):
                raise Exception("虚拟环境Python解释器未找到")
                
            ui.print_success(f"虚拟环境创建成功: {venv_path}")
            logger.info("虚拟环境创建成功", venv_path=venv_path)
            
            return True, venv_path
            
        except Exception as e:
            error_msg = f"虚拟环境创建失败: {str(e)}"
            ui.print_error(error_msg)
            logger.error("虚拟环境创建失败", error=str(e))
            return False, error_msg
    
    def install_dependencies_in_venv(self, venv_path: str, requirements_path: str) -> bool:
        """
        在虚拟环境中安装依赖
        
        Args:
            venv_path: 虚拟环境路径
            requirements_path: requirements.txt文件路径
            
        Returns:
            是否安装成功
        """
        pypi_mirrors = [
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            "https://pypi.org/simple",
            "https://mirrors.aliyun.com/pypi/simple",
            "https://pypi.douban.com/simple"
        ]
        
        def is_uv_available() -> bool:
            """检查是否可用uv"""
            try:
                subprocess.run(["uv", "--version"], capture_output=True, check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False
        
        def run_command_with_output(cmd: List[str], description: str) -> bool:
            """运行命令并实时显示输出"""
            try:
                ui.print_info(f"{description}...")
                logger.info(f"执行命令: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                if process.stdout:
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            print(f"  {line}")
                
                process.wait()
                
                if process.returncode == 0:
                    ui.print_success(f"{description}完成")
                    return True
                else:
                    ui.print_error(f"{description}失败，返回码: {process.returncode}")
                    return False
                    
            except Exception as e:
                ui.print_error(f"{description}时发生错误: {str(e)}")
                logger.error(f"{description}异常", error=str(e))
                return False
        
        try:
            if not os.path.exists(requirements_path):
                ui.print_error(f"requirements.txt 不存在: {requirements_path}")
                return False
            
            # 获取虚拟环境中的pip路径
            if platform.system() == "Windows":
                pip_exe = os.path.join(venv_path, "Scripts", "pip.exe")
                python_exe = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                pip_exe = os.path.join(venv_path, "bin", "pip")
                python_exe = os.path.join(venv_path, "bin", "python")
            
            # 检查pip是否存在
            if not os.path.exists(pip_exe):
                ui.print_error(f"虚拟环境pip未找到: {pip_exe}")
                return False
            
            ui.print_info(f"使用虚拟环境: {venv_path}")
            ui.print_info(f"安装依赖文件: {requirements_path}")
            
            # 检查是否可用uv
            use_uv = is_uv_available()
            
            if use_uv:
                ui.print_info("检测到uv包管理器，将使用uv加速安装")
                success = False
                
                # 尝试使用不同镜像源
                for i, mirror in enumerate(pypi_mirrors, 1):
                    ui.print_info(f"尝试使用镜像源 {i}/{len(pypi_mirrors)}: {mirror}")
                    cmd = [
                        "uv", "pip", "install",
                        "-r", requirements_path,
                        "--python", python_exe,
                        "-i", mirror
                    ]
                    
                    if run_command_with_output(cmd, f"使用uv从镜像源{i}安装依赖"):
                        success = True
                        break
                    
                    if i < len(pypi_mirrors):
                        ui.print_warning(f"镜像源{i}安装失败，尝试下一个...")
                
                if success:
                    ui.print_success("依赖安装完成！")
                    logger.info("依赖安装成功", method="uv")
                    return True
                else:
                    ui.print_warning("所有镜像源均失败，将尝试使用pip安装")
            
            # 使用pip安装
            ui.print_info("使用pip安装依赖...")
            
            # 先升级pip
            upgrade_cmd = [python_exe, "-m", "pip", "install", "--upgrade", "pip"]
            run_command_with_output(upgrade_cmd, "升级pip")
            
            # 尝试使用不同镜像源
            for i, mirror in enumerate(pypi_mirrors, 1):
                ui.print_info(f"尝试使用镜像源 {i}/{len(pypi_mirrors)}: {mirror}")
                cmd = [
                    pip_exe, "install",
                    "-r", requirements_path,
                    "-i", mirror
                ]
                
                if run_command_with_output(cmd, f"使用pip从镜像源{i}安装依赖"):
                    ui.print_success("依赖安装完成！")
                    logger.info("依赖安装成功", method="pip")
                    return True
                
                if i < len(pypi_mirrors):
                    ui.print_warning(f"镜像源{i}安装失败，尝试下一个...")
            
            ui.print_error("所有镜像源均失败")
            logger.error("依赖安装失败，所有镜像源均不可用")
            return False
            
        except subprocess.CalledProcessError as e:
            ui.print_error(f"依赖安装失败: {str(e)}")
            logger.error("依赖安装命令执行失败", error=str(e), returncode=e.returncode)
            return False
        except Exception as e:
            ui.print_error(f"依赖安装时发生错误: {str(e)}")
            logger.error("依赖安装异常", error=str(e))
            return False
    
    def get_venv_python_path(self, venv_path: str) -> Optional[str]:
        """
        获取虚拟环境中的Python解释器路径
        
        Args:
            venv_path: 虚拟环境路径
            
        Returns:
            Python解释器路径，如果不存在则返回None
        """
        if platform.system() == "Windows":
            python_exe = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(venv_path, "bin", "python")
        
        return python_exe if os.path.exists(python_exe) else None

    def check_network_connection(self) -> Tuple[bool, str]:
        """
        检查网络连接
        返回：(是否连接成功, 错误消息)
        """
        endpoints = [
            ("https://api.github.com", "GitHub API"),
            ("https://github.com", "GitHub"),
            ("https://pypi.tuna.tsinghua.edu.cn", "清华PyPI镜像")
        ]
        
        for url, name in endpoints:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code in [200, 301, 302]:
                    logger.info(f"网络连接正常: {name}")
                    return True, ""
            except Exception:
                continue
        
        # 尝试ping一下常见DNS
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["ping", "-n", "1", "8.8.8.8"], 
                                      capture_output=True, timeout=5)
            else:
                result = subprocess.run(["ping", "-c", "1", "8.8.8.8"], 
                                      capture_output=True, timeout=5)
            if result.returncode == 0:
                return True, ""
        except Exception:
            pass
            
        return False, "无法连接到GitHub和PyPI镜像站点"
    
    def download_file(self, url: str, filename: str, max_retries: int = 3) -> bool:
        """
        下载文件
        
        Args:
            url: 下载链接
            filename: 保存文件名
            max_retries: 最大重试次数
            
        Returns:
            是否下载成功
        """
        import os
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    ui.print_info(f"重试下载 ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                
                # 获取文件名用于显示
                file_basename = os.path.basename(filename)
                
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                
                # 显示文件大小信息
                if total_size > 0:
                    size_mb = total_size / (1024 * 1024)
                    ui.print_info(f"文件大小: {size_mb:.2f} MB")
                
                with open(filename, 'wb') as f:
                    if total_size > 0:
                        # 使用tqdm显示下载进度条
                        with tqdm(
                            total=total_size, 
                            unit='B', 
                            unit_scale=True, 
                            unit_divisor=1024,
                            desc=f"下载 {file_basename}",
                            ncols=80,
                            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
                        ) as pbar:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                    else:
                        # 如果没有文件大小信息，使用简单的进度显示
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # 每下载1MB显示一次进度
                                if downloaded % (1024 * 1024) == 0:
                                    ui.print_info(f"已下载: {downloaded / (1024 * 1024):.1f} MB")
                
                ui.print_success(f"下载完成: {file_basename}")
                logger.info("文件下载成功", url=url, filename=filename)
                return True
                
            except requests.RequestException as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    ui.print_warning(f"下载失败: {error_msg}，准备重试...")
                    logger.warning("下载失败，准备重试", error=error_msg, attempt=attempt + 1)
                else:
                    ui.print_error(f"下载失败（已重试{max_retries}次）: {error_msg}")
                    logger.error("下载失败，重试耗尽", error=error_msg, url=url)
                    return False
            except Exception as e:
                ui.print_error(f"下载时发生未知错误: {str(e)}")
                logger.error("下载异常", error=str(e), url=url)
                return False
        
        return False
    
    def extract_archive(self, archive_path: str, extract_to: str) -> bool:
        """
        解压归档文件
        
        Args:
            archive_path: 归档文件路径
            extract_to: 解压目标路径
            
        Returns:
            是否解压成功
        """
        try:
            ui.print_info(f"正在解压文件...")
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            ui.print_success("解压完成")
            logger.info("文件解压成功", archive=archive_path, target=extract_to)
            return True
        except Exception as e:
            ui.print_error(f"解压失败: {str(e)}")
            logger.error("文件解压失败", error=str(e), archive=archive_path)
            return False
