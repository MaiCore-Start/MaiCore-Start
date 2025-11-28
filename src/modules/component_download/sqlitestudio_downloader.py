# -*- coding: utf-8 -*-
"""
SQLiteStudio下载器
"""

import os
import platform
from pathlib import Path
from typing import Optional
import structlog

from ...ui.interface import ui
from .base_downloader import BaseDownloader

logger = structlog.get_logger(__name__)


class SQLiteStudioDownloader(BaseDownloader):
    """SQLiteStudio下载器"""
    
    def __init__(self):
        super().__init__("SQLiteStudio")
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
        """获取SQLiteStudio下载链接"""
        # SQLiteStudio是跨平台的，通常提供zip包
        version = "3.4.4"
        
        # 统一使用正确的GitHub用户名
        github_user = "pawelsalawa"
        
        if self.system == 'windows':
            return f"https://github.com/{github_user}/sqlitestudio/releases/download/{version}/SQLiteStudio-{version}-Windows.zip"
        elif self.system == 'darwin':  # macOS
            return f"https://github.com/{github_user}/sqlitestudio/releases/download/{version}/SQLiteStudio-{version}.dmg"
        else:  # Linux
            return f"https://github.com/{github_user}/sqlitestudio/releases/download/{version}/SQLiteStudio-{version}.tar.gz"
    
    def get_filename(self) -> str:
        """获取下载文件名"""
        version = "3.4.4"
        
        if self.system == 'windows':
            return f"SQLiteStudio-{version}-Windows.zip"
        elif self.system == 'darwin':
            return f"SQLiteStudio-{version}.dmg"
        else:
            return f"SQLiteStudio-{version}.tar.gz"
    
    def download_and_install(self, temp_dir: Path) -> bool:
        """下载并安装SQLiteStudio"""
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
                # Windows - 解压zip包
                extract_dir = temp_dir / "SQLiteStudio_extract"
                if self.extract_archive(str(file_path), str(extract_dir)):
                    ui.print_info("SQLiteStudio已解压到临时目录")
                    ui.print_info(f"解压位置: {extract_dir}")
                    ui.print_info("请手动将SQLiteStudio复制到您希望的位置")
                    
                    # 查找可执行文件
                    exe_files = list(extract_dir.glob("*.exe"))
                    if exe_files:
                        ui.print_info(f"找到可执行文件: {exe_files[0]}")
                        if ui.confirm("是否创建桌面快捷方式？"):
                            self._create_desktop_shortcut(exe_files[0])
                    
                    return True
                else:
                    return False
            
            elif self.system == 'darwin':
                # macOS - 提示用户手动安装
                ui.print_info("SQLiteStudio for macOS 需要手动安装")
                ui.print_info(f"请打开下载的文件: {file_path}")
                if ui.confirm("是否打开SQLiteStudio安装包？"):
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
                # Linux - 解压并提供安装说明
                extract_dir = temp_dir / "SQLiteStudio_extract"
                if self.extract_archive(str(file_path), str(extract_dir)):
                    ui.print_info("SQLiteStudio已解压到临时目录")
                    ui.print_info(f"解压位置: {extract_dir}")
                    ui.print_info("请手动将SQLiteStudio复制到您希望的位置")
                    ui.print_info("例如: sudo cp -r {extract_dir} /opt/SQLiteStudio")
                    
                    # 查找可执行文件
                    if self.arch == 'x86_64':
                        exe_files = list(extract_dir.glob("SQLiteStudio"))
                    else:
                        exe_files = list(extract_dir.glob("SQLiteStudio*"))
                    
                    if exe_files:
                        ui.print_info(f"找到可执行文件: {exe_files[0]}")
                        if ui.confirm("是否创建桌面快捷方式？"):
                            self._create_desktop_shortcut(exe_files[0])
                    
                    return True
                else:
                    return False
            
        except Exception as e:
            ui.print_error(f"下载 {self.name} 时发生错误：{str(e)}")
            logger.error("SQLiteStudio下载安装失败", error=str(e))
            return False
    
    def _create_desktop_shortcut(self, exe_path: Path):
        """创建桌面快捷方式"""
        try:
            import os
            from pathlib import Path
            
            # 获取桌面路径
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "桌面"  # 中文Windows
            
            if not desktop.exists():
                ui.print_warning("未找到桌面目录")
                return
            
            # 创建快捷方式文件
            shortcut_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=SQLiteStudio
Comment=SQLite Database Manager
Exec="{exe_path}"
Icon={exe_path.parent / "SQLiteStudio.png" if (exe_path.parent / "SQLiteStudio.png").exists() else ""}
Terminal=false
Categories=Development;Database;
"""
            
            shortcut_file = desktop / "SQLiteStudio.desktop"
            
            with open(shortcut_file, 'w', encoding='utf-8') as f:
                f.write(shortcut_content)
            
            # 在Linux上需要设置执行权限
            if self.system == 'linux':
                os.chmod(shortcut_file, 0o755)
            
            ui.print_success("桌面快捷方式已创建")
            
        except Exception as e:
            ui.print_warning(f"创建桌面快捷方式失败: {str(e)}")
    
    def check_installation(self) -> tuple[bool, str]:
        """检查SQLiteStudio是否已安装"""
        try:
            import subprocess
            
            # 检查常见安装位置
            possible_paths = [
                "sqlitestudio",
                "SQLiteStudio",
                "/usr/bin/sqlitestudio",
                "/usr/local/bin/sqlitestudio",
                os.path.expanduser("~/SQLiteStudio/sqlitestudio"),
                os.path.expanduser("~/Desktop/SQLiteStudio.desktop")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return True, f"SQLiteStudio 已安装，位置: {path}"
            
            # 尝试运行命令
            try:
                result = subprocess.run(
                    ["sqlitestudio", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    version = result.stdout.strip()
                    return True, f"SQLiteStudio 已安装，版本: {version}"
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            return False, "SQLiteStudio 未安装"
            
        except Exception as e:
            return False, f"检查SQLiteStudio安装状态时发生错误: {str(e)}"