# -*- coding: utf-8 -*-
"""
MongoDB下载器
"""

import platform
import os
import subprocess
import ctypes
from pathlib import Path
from typing import Optional
import structlog

from ...ui.interface import ui
from .base_downloader import BaseDownloader

logger = structlog.get_logger(__name__)


class MongoDBDownloader(BaseDownloader):
    """MongoDB下载器"""
    
    def __init__(self):
        super().__init__("MongoDB")
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        
        # 标准化架构名称
        if self.arch in ['x86_64', 'amd64']:
            self.arch = 'x86_64'
        elif self.arch in ['arm64', 'aarch64']:
            self.arch = 'arm64'
        else:
            self.arch = 'x86_64'
    
    def get_download_url(self) -> str:
        """获取MongoDB下载链接"""
        version = "7.0.4"
        
        if self.system == 'windows':
            return f"https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-{version}.msi"
        elif self.system == 'darwin':  # macOS
            return f"https://fastdl.mongodb.org/macos/mongodb-macos-{self.arch}-{version}.dmg"
        else:  # Linux
            return f"https://fastdl.mongodb.org/linux/mongodb-linux-{self.arch}-{version}.tgz"
    
    def get_filename(self) -> str:
        """获取下载文件名"""
        version = "7.0.4"
        
        if self.system == 'windows':
            return f"mongodb-windows-x86_64-{version}.msi"
        elif self.system == 'darwin':
            return f"mongodb-macos-{self.arch}-{version}.dmg"
        else:
            return f"mongodb-linux-{self.arch}-{version}.tgz"
    
    def download_and_install(self, temp_dir: Path) -> bool:
        """下载并安装MongoDB"""
        try:
            # 获取下载链接和文件名
            download_url = self.get_download_url()
            filename = self.get_filename()
            file_path = temp_dir / filename
            
            ui.print_info(f"正在下载 {self.name}...")
            
            # 下载文件
            if not self.download_file(download_url, str(file_path)):
                return False
            
            ui.print_info(f"正在安装 {self.name}...")
            
            # 根据系统执行安装
            if self.system == 'windows':
                # ✅ Windows系统 - 使用专门的方法
                success = self._install_mongodb_windows(str(file_path))
            elif self.system == 'darwin':
                # macOS - 提示用户手动安装
                ui.print_info("MongoDB for macOS 需要手动安装")
                ui.print_info(f"请打开下载的文件: {file_path}")
                if ui.confirm("是否打开MongoDB安装包？"):
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
                ui.print_info("MongoDB for Linux 推荐使用包管理器安装")
                ui.print_info("例如: sudo apt install mongodb (Ubuntu/Debian)")
                ui.print_info("或者: sudo yum install mongodb (CentOS/RHEL)")
                ui.print_info("或者从官方仓库安装最新版本")
                return True
            
            return success
            
        except Exception as e:
            ui.print_error(f"下载 {self.name} 时发生错误：{str(e)}")
            logger.error("MongoDB下载安装失败", error=str(e))
            return False
    
    def _install_mongodb_windows(self, msi_path: str) -> bool:
        """在Windows上安装MongoDB（使用msiexec）"""
        try:
            ui.print_info(f"正在运行安装程序: {os.path.basename(msi_path)}")
            
            # 检查文件是否存在
            if not os.path.exists(msi_path):
                ui.print_error(f"安装文件不存在: {msi_path}")
                return False
            
            # 检查是否有管理员权限
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            
            if is_admin:
                # 已有管理员权限，直接使用 msiexec 安装
                ui.print_info("正在以管理员权限安装...")
                result = subprocess.run(
                    ["msiexec", "/i", msi_path, "/passive", "/norestart"],
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
                
                # 使用 ShellExecuteW 以管理员身份运行 msiexec
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",  # 请求管理员权限
                    "msiexec",
                    f'/i "{msi_path}" /passive /norestart',
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
            logger.error("安装程序运行异常", installer=msi_path, error=str(e))
            return False
    
    def check_installation(self) -> tuple[bool, str]:
        """检查MongoDB是否已安装"""
        try:
            import subprocess
            result = subprocess.run(
                ["mongod", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 解析版本信息
                version_line = result.stdout.split('\n')[0]
                return True, f"MongoDB 已安装，版本: {version_line}"
            else:
                return False, "MongoDB 未安装"
                
        except Exception as e:
            return False, f"检查MongoDB安装状态时发生错误: {str(e)}"