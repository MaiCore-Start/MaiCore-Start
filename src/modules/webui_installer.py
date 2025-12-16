"""
WebUI安装模块
负责MaiMbot WebUI的下载、安装和配置
支持分支选择和Node.js环境检测
"""
import os
import subprocess
import tempfile
import shutil
import platform
import requests
import zipfile
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import structlog
from tqdm import tqdm
from ..ui.interface import ui
from ..utils.common import validate_path
from ..utils.notifier import windows_notifier

# 忽略SSL警告（用于GitHub API访问）
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

logger = structlog.get_logger(__name__)


class WebUIInstaller:
    """WebUI安装器类"""
    
    def __init__(self):
        self.webui_repo = "Mai-with-u/MaiBot-Dashboard"
        self.webui_cache_dir = Path.home() / ".maibot" / "webui_cache"
        self.dashboard_dir_name = "MaiBot-Dashboard"
        self.webui_cache_dir.mkdir(parents=True, exist_ok=True)
        self._offline_mode = False
        self._bun_candidates = ["bun", "bun.exe", "bun.cmd"]
    
    def check_nodejs_installed(self) -> Tuple[bool, str]:
        """检查Node.js是否已安装"""
        try:
            # 在Windows上，尝试不同的node命令路径
            node_commands = ["node", "node.exe"]
            
            for node_cmd in node_commands:
                try:
                    result = subprocess.run(
                        [node_cmd, "--version"], 
                        capture_output=True, 
                        text=True, 
                        timeout=10,
                        shell=True  # 在Windows上使用shell
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        logger.info("Node.js已安装", version=version, command=node_cmd)
                        return True, version
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                    continue
            
            logger.info("Node.js未安装或不可用")
            return False, ""
        except Exception as e:
            logger.info("Node.js检查异常", error=str(e))
            return False, ""
    
    def check_npm_installed(self) -> Tuple[bool, str]:
        """检查npm是否已安装"""
        try:
            # 在Windows上，尝试不同的npm命令路径
            npm_commands = ["npm", "npm.cmd"]
            
            for npm_cmd in npm_commands:
                try:
                    result = subprocess.run(
                        [npm_cmd, "--version"], 
                        capture_output=True, 
                        text=True, 
                        timeout=10,
                        shell=True  # 在Windows上使用shell
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        logger.info("npm已安装", version=version, command=npm_cmd)
                        return True, version
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                    continue
            
            logger.info("npm未安装或不可用")
            return False, ""
        except Exception as e:
            logger.info("npm检查异常", error=str(e))
            return False, ""
    
    def install_nodejs(self) -> bool:
        """安装Node.js"""
        try:
            ui.print_info("正在安装Node.js...")
            
            if platform.system() == "Windows":
                return self._install_nodejs_windows()
            else:
                ui.print_error("当前操作系统不支持自动安装Node.js，请手动安装")
                ui.print_info("请访问 https://nodejs.org/ 下载并安装Node.js")
                logger.warning("不支持的操作系统", os=platform.system())
                return False
                
        except Exception as e:
            ui.print_error(f"Node.js安装失败：{str(e)}")
            logger.error("Node.js安装失败", error=str(e))
            return False
    
    def _install_nodejs_windows(self) -> bool:
        """在Windows上安装Node.js"""
        try:
            ui.print_info("正在下载Node.js Windows安装包...")
            
            nodejs_url = "https://nodejs.org/dist/v22.20.0/node-v22.20.0-x64.msi"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                installer_path = os.path.join(temp_dir, "nodejs_installer.msi")
                
                if not self.download_file(nodejs_url, installer_path):
                    ui.print_error("Node.js安装包下载失败")
                    return False

                ui.print_info("正在安装Node.js...")
                ui.print_warning("请在弹出的安装程序中完成Node.js安装")
                
                # 使用 os.startfile 在 Windows 上更可靠，可以避免阻塞
                os.startfile(installer_path)
                
                # 等待用户完成安装
                ui.pause("安装完成后按回车继续...")
                
                # 验证安装
                return self._verify_nodejs_installation()
                
        except Exception as e:
            ui.print_error(f"Windows Node.js安装失败：{str(e)}")
            return False
    
    def _verify_nodejs_installation(self) -> bool:
        """验证Node.js安装"""
        try:
            ui.print_info("验证Node.js安装...")
            
            # 检查Node.js
            node_installed, node_version = self.check_nodejs_installed()
            if not node_installed:
                return False
            
            # 检查npm
            npm_installed, npm_version = self.check_npm_installed()
            if not npm_installed:
                return False
            
            ui.print_success(f"Node.js验证成功: {node_version}")
            ui.print_success(f"npm验证成功: {npm_version}")
            return True
            
        except Exception as e:
            ui.print_error(f"Node.js验证失败：{str(e)}")
            return False
    
    def download_file(self, url: str, filename: str, max_retries: int = 3) -> bool:
        """下载文件并显示进度，支持重试"""
        if hasattr(self, '_offline_mode') and self._offline_mode:
            ui.print_error("当前处于离线模式，无法下载文件")
            return False
            
        # 检查是否有代理设置
        proxies = {}
        # 从环境变量获取代理设置
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy
            
        if proxies:
            ui.print_info(f"使用代理设置: {proxies}")
        
        # 重试逻辑
        for retry in range(max_retries):
            try:
                ui.print_info(f"正在下载 {os.path.basename(filename)}... (尝试 {retry + 1}/{max_retries})")
                logger.info("开始下载文件", url=url, filename=filename, retry=retry+1)
                
                response = requests.get(url, stream=True, proxies=proxies, timeout=30, verify=False)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                
                with open(filename, 'wb') as file, tqdm(
                    desc=os.path.basename(filename),
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as progress_bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            progress_bar.update(len(chunk))
                
                # 验证文件大小
                if total_size > 0:
                    actual_size = os.path.getsize(filename)
                    if actual_size < total_size * 0.98:  # 允许2%的误差
                        ui.print_warning(f"文件下载不完整: 预期 {total_size} 字节, 实际 {actual_size} 字节")
                        if retry < max_retries - 1:
                            ui.print_info("将重试下载...")
                            continue
                        else:
                            ui.print_error("达到最大重试次数，文件可能不完整")
                            return False
                
                ui.print_success(f"{os.path.basename(filename)} 下载完成")
                logger.info("文件下载完成", filename=filename)
                return True
                
            except requests.RequestException as e:
                ui.print_warning(f"下载失败 (尝试 {retry + 1}/{max_retries}): {str(e)}")
                logger.warning("文件下载失败", error=str(e), url=url, retry=retry+1)
                
                if retry < max_retries - 1:
                    ui.print_info("3秒后重试...")
                    import time
                    time.sleep(3)
                    continue
                else:
                    ui.print_error("达到最大重试次数，下载失败")
                    return False
                    
        ui.print_error(f"下载失败：达到最大重试次数 {max_retries}")
        logger.error("文件下载失败", url=url)
        return False

    def _run_command(self, command: List[str], cwd: Optional[str] = None, description: str = "") -> Tuple[bool, str]:
        """Run a shell command and stream results."""
        try:
            if description:
                ui.print_info(description)
            cmd_display = " ".join(command)
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=600,
            )
            if result.returncode == 0:
                if description:
                    ui.print_success(f"{description} 完成")
                return True, result.stdout
            ui.print_error(f"命令执行失败: {cmd_display}\n{result.stderr}")
            logger.error("命令执行失败", command=cmd_display, stderr=result.stderr)
            return False, result.stderr
        except subprocess.TimeoutExpired:
            ui.print_error(f"命令超时: {cmd_display}")
            logger.error("命令超时", command=cmd_display)
            return False, "timeout"
        except Exception as exc:
            ui.print_error(f"命令执行异常: {exc}")
            logger.error("命令执行异常", command=cmd_display, error=str(exc))
            return False, str(exc)

    def _resolve_command(self, candidates: List[str]) -> Optional[str]:
        """Return the first executable found in PATH for given candidates."""
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _find_bun_executable(self, dashboard_dir: str) -> Optional[str]:
        """Locate a bun executable, preferring system PATH then local node_modules/.bin."""
        bun_cmd = self._resolve_command(self._bun_candidates)
        if bun_cmd:
            return bun_cmd
        local_bin = os.path.join(
            dashboard_dir,
            "node_modules",
            ".bin",
            "bun.cmd" if platform.system() == "Windows" else "bun"
        )
        if os.path.exists(local_bin):
            return local_bin
        return None
    def get_webui_branches(self, max_retries: int = 3) -> List[Dict]:
        """获取WebUI分支列表，支持重试机制"""
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    ui.print_info("正在获取WebUI分支列表...")
                else:
                    ui.print_info(f"重试获取WebUI分支列表... (尝试 {attempt + 1}/{max_retries})")
                
                url = f"https://api.github.com/repos/{self.webui_repo}/branches"
                response = requests.get(url, timeout=30, verify=False)  # 跳过SSL验证
                response.raise_for_status()
                
                branches_data = response.json()
                branches = []
                
                for branch in branches_data:
                    branch_info = {
                        "name": branch["name"],
                        "display_name": branch["name"],
                        "commit_sha": branch["commit"]["sha"][:7],
                        "download_url": f"https://github.com/{self.webui_repo}/archive/refs/heads/{branch['name']}.zip"
                    }
                    branches.append(branch_info)
                
                logger.info("获取WebUI分支列表成功", count=len(branches))
                return branches
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    # GitHub API 速率限制
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 指数退避：2, 4, 6秒
                        ui.print_warning(f"GitHub API速率限制，等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        ui.print_error(f"获取WebUI分支列表失败：GitHub API速率限制，已重试{max_retries}次")
                        ui.print_info("您可以：")
                        ui.console.print("  1. 等待几分钟后重试")
                        ui.console.print("  2. 使用VPN或代理")
                        ui.console.print("  3. 手动输入分支名称（如果知道）")
                        logger.error("获取WebUI分支列表失败", error=str(e))
                        return []
                else:
                    ui.print_error(f"获取WebUI分支列表失败：{str(e)}")
                    logger.error("获取WebUI分支列表失败", error=str(e))
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    ui.print_warning(f"获取失败，等待{wait_time}秒后重试... ({str(e)})")
                    time.sleep(wait_time)
                    continue
                else:
                    ui.print_error(f"获取WebUI分支列表失败：{str(e)}")
                    logger.error("获取WebUI分支列表失败", error=str(e))
                    return []
        
        # 所有重试都失败了
        ui.print_error(f"获取WebUI分支列表失败：已重试{max_retries}次，请检查网络连接或稍后重试")
        return []
    
    def show_webui_branch_menu(self) -> Optional[Dict]:
        """显示WebUI分支选择菜单，支持手动重试"""
        while True:
            try:
                ui.clear_screen()
                ui.console.print("[🌐 选择控制面板分支]", style=ui.colors["primary"])
                ui.console.print("="*40)
                
                branches = self.get_webui_branches()
                if not branches:
                    ui.print_error("无法获取WebUI分支信息")
                    
                    # 提供重试选项
                    ui.console.print("\n[重试选项]", style=ui.colors["info"])
                    ui.console.print("[R] 重试获取分支列表")
                    ui.console.print("[M] 手动输入分支名称")
                    ui.console.print("[Q] 跳过控制面板安装")
                    
                    while True:
                        choice = ui.get_input("请选择操作：").strip().upper()
                        
                        if choice == 'R':
                            # 重新获取分支列表
                            break
                        elif choice == 'M':
                            # 手动输入分支名称
                            branch_name = ui.get_input("请输入分支名称（如：main, dev等）：").strip()
                            if branch_name:
                                # 创建手动分支信息
                                manual_branch = {
                                    "name": branch_name,
                                    "display_name": branch_name,
                                    "commit_sha": "unknown",
                                    "download_url": f"https://github.com/{self.webui_repo}/archive/refs/heads/{branch_name}.zip"
                                }
                                ui.print_success(f"已选择：{manual_branch['display_name']}")
                                return manual_branch
                            else:
                                ui.print_error("分支名称不能为空")
                        elif choice == 'Q':
                            return None
                        else:
                            ui.print_error("请输入有效的选项")
                    
                    # 继续循环，重新获取分支列表
                    continue
                
                # 在显示分支选择之前发送通知提醒用户
                windows_notifier.send(
                    "即将选择控制面板分支",
                    "请选择要安装的MaiBot控制面板分支，建议选择master分支以获得最新稳定版本..."
                )
                
                # 创建分支表格
                from rich.table import Table
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("选项", style="cyan", width=6)
                table.add_column("分支名", style="white", width=20)
                table.add_column("提交SHA", style="yellow", width=10)
                table.add_column("说明", style="green")
                
                for i, branch in enumerate(branches, 1):
                    description = "主分支" if branch["name"] == "main" else f"{branch['name']}分支"
                    table.add_row(
                        f"[{i}]",
                        branch["display_name"],
                        branch["commit_sha"],
                        description
                    )
                
                ui.console.print(table)
                ui.console.print("\n[R] 刷新分支列表  [M] 手动输入分支  [Q] 跳过控制面板安装", style="#7E1DE4")
                
                while True:
                    choice = ui.get_input("请选择WebUI分支：").strip().upper()
                    
                    if choice == 'Q':
                        return None
                    elif choice == 'R':
                        # 刷新分支列表，重新获取
                        break
                    elif choice == 'M':
                        # 手动输入分支名称
                        branch_name = ui.get_input("请输入分支名称（如：main, dev等）：").strip()
                        if branch_name:
                            # 创建手动分支信息
                            manual_branch = {
                                "name": branch_name,
                                "display_name": branch_name,
                                "commit_sha": "unknown",
                                "download_url": f"https://github.com/{self.webui_repo}/archive/refs/heads/{branch_name}.zip"
                            }
                            ui.print_success(f"已选择：{manual_branch['display_name']}")
                            return manual_branch
                        else:
                            ui.print_error("分支名称不能为空")
                    else:
                        try:
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(branches):
                                selected_branch = branches[choice_idx]
                                ui.print_success(f"已选择：{selected_branch['display_name']}")
                                return selected_branch
                            else:
                                ui.print_error("选项超出范围")
                        except ValueError:
                            ui.print_error("请输入有效的数字或选项")
                
                # 如果用户选择刷新，重新获取分支列表
                if choice.upper() == 'R':
                    continue
                    
            except Exception as e:
                ui.print_error(f"显示WebUI分支菜单失败：{str(e)}")
                logger.error("显示WebUI分支菜单失败", error=str(e))
                
                # 提供重试选项
                if ui.confirm("是否重试显示分支菜单？"):
                    continue
                else:
                    return None
    
    def download_webui(self, branch_info: Dict, instance_dir: str) -> Optional[str]:
        """下载并安装MaiBot控制面板源码。"""
        try:
            ui.print_info(f"正在下载控制面板 {branch_info['display_name']}...")
            
            # 控制面板应该安装在实例目录下的MaiBot-Dashboard文件夹中
            target_dir = os.path.join(instance_dir, self.dashboard_dir_name)
            os.makedirs(instance_dir, exist_ok=True)

            with tempfile.TemporaryDirectory() as temp_dir:
                archive_path = os.path.join(temp_dir, f"dashboard_{branch_info['name']}.zip")
                response = requests.get(branch_info["download_url"], stream=True, timeout=60, verify=False)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                with open(archive_path, 'wb') as archive_file, tqdm(
                    desc=os.path.basename(archive_path),
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as progress_bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            archive_file.write(chunk)
                            progress_bar.update(len(chunk))

                extract_dir = os.path.join(temp_dir, "dashboard_extract")
                ui.print_info("正在解压控制面板...")
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                extracted_dirs = [
                    d for d in os.listdir(extract_dir)
                    if os.path.isdir(os.path.join(extract_dir, d)) and d != "__MACOSX"
                ]
                if not extracted_dirs:
                    ui.print_error("解压后未找到控制面板目录")
                    return None

                source_dir = os.path.join(extract_dir, extracted_dirs[0])
                
                # 安全地删除已存在的目录，处理文件占用问题
                if os.path.exists(target_dir):
                    ui.print_info("检测到已有控制面板目录，正在清理...")
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            shutil.rmtree(target_dir)
                            break
                        except PermissionError as e:
                            if attempt < max_retries - 1:
                                ui.print_warning(f"目录清理失败（尝试 {attempt + 1}/{max_retries}），2秒后重试...")
                                logger.warning("目录删除失败，将重试", error=str(e), attempt=attempt+1)
                                time.sleep(2)
                            else:
                                ui.print_error("无法删除旧的控制面板目录，可能有进程正在使用文件。")
                                ui.print_info("提示：请关闭所有相关的终端窗口、Node.js进程或IDE，然后重试。")
                                logger.error("目录删除失败", error=str(e))
                                raise
                
                os.makedirs(target_dir, exist_ok=True)

                ui.print_info("正在拷贝控制面板文件...")
                for item in os.listdir(source_dir):
                    src_path = os.path.join(source_dir, item)
                    dst_path = os.path.join(target_dir, item)
                    if os.path.isfile(src_path):
                        shutil.copy2(src_path, dst_path)
                    elif os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path)

                ui.print_success("控制面板源码安装完成")
                logger.info("控制面板下载成功", path=target_dir)
                return target_dir

        except Exception as e:
            ui.print_error(f"控制面板下载失败：{str(e)}")
            logger.error("控制面板下载失败", error=str(e))
            return None
    
    def install_webui_dependencies(self, dashboard_dir: str, venv_path: str = "") -> bool:
        """安装MaiBot控制面板依赖，使用 npm + bun。"""
        try:
            ui.print_info("正在安装MaiBot控制面板依赖...")

            npm_cmd = self._resolve_command(["npm", "npm.cmd"])
            if not npm_cmd:
                ui.print_error("未找到 npm 命令，无法继续安装控制面板依赖")
                return False

            bun_cmd = self._find_bun_executable(dashboard_dir)
            if bun_cmd:
                ui.print_info(f"检测到已有 bun 可执行文件: {bun_cmd}")
            else:
                npm_install_ok, _ = self._run_command(
                    [npm_cmd, "install", "bun"],
                    cwd=dashboard_dir,
                    description="安装 bun 运行时",
                )
                if not npm_install_ok:
                    ui.print_warning("npm install bun 失败，直接尝试运行 bun install。")
                bun_cmd = self._find_bun_executable(dashboard_dir)

            npx_cmd = self._resolve_command(["npx", "npx.cmd"])

            if bun_cmd:
                bun_command = [bun_cmd, "install"]
            elif npx_cmd:
                ui.print_warning("未找到 bun 可执行文件，使用 npx bun install")
                bun_command = [npx_cmd, "--yes", "bun", "install"]
            else:
                ui.print_warning("未找到 bun 可执行文件或 npx，尝试使用 npm exec bun (可能需要较长时间)")
                bun_command = [npm_cmd, "exec", "bun", "install"]

            success, _ = self._run_command(bun_command, cwd=dashboard_dir, description="执行 bun install")
            return success

        except Exception as e:
            ui.print_error(f"安装控制面板依赖时发生异常：{str(e)}")
            logger.error("安装控制面板依赖异常", error=str(e))
            return False
    
    def install_webui_backend_dependencies(self, webui_dir: str, venv_path: str = "") -> bool:
        """控制面板当前无独立后端依赖，直接返回成功。"""
        ui.print_info("控制面板无需额外后端依赖，已跳过。")
        return True

    def check_and_install_webui(self, install_dir: str, venv_path: str = "") -> Tuple[bool, str]:
        """检查并安装MaiBot控制面板"""
        try:
            ui.console.print("\n[🌐 控制面板安装选项]", style=ui.colors["primary"])
            
            # 询问是否安装控制面板
            if not ui.confirm("是否安装MaiBot控制面板？"):
                ui.print_info("已跳过控制面板安装")
                return True, ""
            
            # 检查Node.js环境
            ui.print_info("检查Node.js环境...")
            node_installed, node_version = self.check_nodejs_installed()
            npm_installed, npm_version = self.check_npm_installed()
            
            if not node_installed or not npm_installed:
                ui.print_warning("未检测到Node.js或npm")
                ui.print_info("控制面板需要Node.js环境支持")
                
                if ui.confirm("是否自动安装Node.js？"):
                    if not self.install_nodejs():
                        ui.print_error("Node.js安装失败，跳过控制面板安装")
                        return False, ""
                else:
                    ui.print_info("已跳过控制面板安装")
                    return True, ""
            else:
                ui.print_success(f"Node.js环境检测通过: {node_version}")
                ui.print_success(f"npm环境检测通过: {npm_version}")
            
            # 选择控制面板分支
            branch_info = self.show_webui_branch_menu()
            if not branch_info:
                ui.print_info("已跳过控制面板安装")
                return True, ""
            
            # 下载控制面板
            # 控制面板应该安装在实例目录中
            # install_dir 是 Bot 主程序的路径 (例如: D:/instances/test_instance/MaiBot)
            # 实例目录应该是其父目录 (例如: D:/instances/test_instance)
            instance_dir = os.path.dirname(install_dir)
            webui_dir = self.download_webui(branch_info, instance_dir)
            if not webui_dir:
                ui.print_error("控制面板下载失败")
                return False, ""
            
            # 安装控制面板依赖
            if not self.install_webui_dependencies(webui_dir, venv_path):
                ui.print_warning("依赖安装失败，但控制面板文件已下载")
                ui.print_info("可以稍后手动在控制面板目录中执行 npm install bun && bun install")
            
            ui.print_success("✅ 控制面板安装完成")
            logger.info("控制面板安装完成", path=webui_dir)
            return True, webui_dir
            
        except Exception as e:
            ui.print_error(f"控制面板安装失败：{str(e)}")
            logger.error("控制面板安装失败", error=str(e))
            return False, ""
    
    def install_webui_directly(self, install_dir: str, venv_path: str = "") -> Tuple[bool, str]:
        """直接安装控制面板，不询问用户"""
        try:
            ui.console.print("\n[🌐 控制面板安装]", style=ui.colors["primary"])
            
            # 检查Node.js环境
            ui.print_info("检查Node.js环境...")
            node_installed, node_version = self.check_nodejs_installed()
            npm_installed, npm_version = self.check_npm_installed()
            
            if not node_installed or not npm_installed:
                ui.print_warning("未检测到Node.js或npm")
                ui.print_info("控制面板需要Node.js环境支持")
                
                if ui.confirm("是否自动安装Node.js？"):
                    if not self.install_nodejs():
                        ui.print_error("Node.js安装失败，跳过控制面板安装")
                        return False, ""
                else:
                    ui.print_info("已跳过控制面板安装")
                    return False, ""
            else:
                ui.print_success(f"Node.js环境检测通过: {node_version}")
                ui.print_success(f"npm环境检测通过: {npm_version}")
            
            # 选择控制面板分支
            branch_info = self.show_webui_branch_menu()
            if not branch_info:
                ui.print_info("已跳过控制面板安装")
                return False, ""
            
            # 下载控制面板
            # 控制面板应该安装在实例目录中
            # install_dir 是 Bot 主程序的路径 (例如: D:/instances/test_instance/MaiBot)
            # 实例目录应该是其父目录 (例如: D:/instances/test_instance)
            instance_dir = os.path.dirname(install_dir)
            webui_dir = self.download_webui(branch_info, instance_dir)
            if not webui_dir:
                ui.print_error("控制面板下载失败")
                return False, ""
            
            # 安装控制面板依赖
            if not self.install_webui_dependencies(webui_dir, venv_path):
                ui.print_warning("控制面板依赖安装失败，但文件已下载")
                ui.print_info("可以稍后手动在控制面板目录中执行 npm install bun && bun install")
            
            ui.print_success("✅ 控制面板安装完成")
            logger.info("控制面板安装完成", path=webui_dir)
            return True, webui_dir
            
        except Exception as e:
            ui.print_error(f"控制面板安装失败：{str(e)}")
            logger.error("控制面板安装失败", error=str(e))
            return False, ""


# 全局WebUI安装器实例
webui_installer = WebUIInstaller()
