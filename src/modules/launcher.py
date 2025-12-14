"""
麦麦启动器模块
负责启动和管理麦麦实例及其相关组件。
"""
import os
import shutil
import subprocess
import time
import threading
import webbrowser
import structlog
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import psutil
from rich.table import Table

from ..ui.interface import ui
from ..utils.common import check_process, validate_path
from ..utils.version_detector import is_legacy_version
from .multi_launch import multi_launch_manager, port_manager, port_replacer

logger = structlog.get_logger(__name__)

# --- 内部辅助类 ---

class _ProcessManager:
    """
    内部进程管理器。
    负责在新CMD窗口中启动、跟踪和停止进程。
    """
    def __init__(self):
        self.running_processes: List[Dict[str, Any]] = []

    def start_in_new_cmd(self, command: str, cwd: str, title: str) -> Optional[subprocess.Popen]:
        """在新的CMD窗口中启动命令。"""
        try:
            # 构造在新控制台中执行的命令
            full_command = f'cmd /k "chcp 65001 && title {title} && cd /d "{cwd}" && {command}"'
            logger.info("在新控制台启动进程", title=title, command=full_command, cwd=cwd)

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NEW_CONSOLE

            process = subprocess.Popen(
                full_command,
                cwd=cwd,
                shell=False, # shell=False更安全，且CREATE_NEW_CONSOLE需要它
                creationflags=creationflags
            )
            
            process_info = {
                "process": process,
                "title": title,
                "command": command,
                "cwd": cwd,
                "start_time": time.time()
            }
            self.running_processes.append(process_info)
            ui.print_success(f"组件 '{title}' 启动成功！")
            return process
        except Exception as e:
            ui.print_error(f"组件 '{title}' 启动失败: {e}")
            logger.error("进程启动失败", title=title, error=str(e))
            return None

    def stop_all(self):
        """停止所有由该管理器启动的进程。"""
        # 创建一个pid列表的副本进行迭代，因为stop_process会修改running_processes列表
        pids_to_stop = [info["process"].pid for info in self.running_processes if info.get("process")]
        
        if not pids_to_stop:
            return

        stopped_count = 0
        for pid in pids_to_stop:
            if self.stop_process(pid):
                stopped_count += 1
        
        if stopped_count > 0:
            ui.print_info(f"已成功停止 {stopped_count} 个相关进程。")

    def get_running_processes_info(self) -> List[Dict]:
        """获取当前仍在运行的进程信息，包括资源占用。"""
        active_processes = []
        # 过滤掉已经结束的进程
        self.running_processes = [p for p in self.running_processes if p["process"].poll() is None]
        for info in self.running_processes:
            try:
                p = psutil.Process(info["process"].pid)
                info["pid"] = p.pid
                # CPU percent is now calculated in show_running_processes to avoid conflicts
                info["memory_mb"] = p.memory_info().rss / (1024 * 1024)
                info["running_time"] = time.time() - info["start_time"]
                active_processes.append(info)
            except psutil.NoSuchProcess:
                # 获取pid用于日志记录，如果process对象不存在则返回None
                pid = getattr(info.get("process"), 'pid', None)
                logger.warning("进程已消失，无法获取信息", pid=pid)
            except Exception as e:
                logger.error("获取进程信息失败", error=str(e))
        return active_processes

    def stop_process(self, pid: int) -> bool:
        """通过PID停止单个进程及其子进程。"""
        process_info = next((info for info in self.running_processes if info.get("process") and info["process"].pid == pid), None)
        
        if not process_info:
            logger.warning("尝试停止一个非托管进程", pid=pid)
            return False

        title = process_info["title"]
        try:
            # 优先使用 taskkill (仅限Windows) 来确保终止整个进程树
            if os.name == 'nt':
                # /F: 强制终止
                # /T: 终止进程树
                # /PID: 指定进程ID
                kill_command = ["taskkill", "/F", "/T", "/PID", str(pid)]
                result = subprocess.run(
                    kill_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW # 防止弹出窗口
                )
                if result.returncode == 0 or "已终止" in result.stdout or "terminated" in result.stdout.lower():
                    logger.info("已通过 taskkill 成功终止进程树", pid=pid, title=title)
                elif "not found" in result.stderr.lower(): # 进程已经不存在
                     logger.warning("尝试停止的进程已不存在 (taskkill)", pid=pid)
                else:
                    # 如果taskkill失败，回退到psutil方法
                    logger.warning("taskkill 失败，回退到 psutil", pid=pid, stderr=result.stderr)
                    parent = psutil.Process(pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
            else:
                # 对于非Windows系统，使用psutil
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
            
            ui.print_success(f"进程 '{title}' (PID: {pid}) 已成功请求停止。")

        except psutil.NoSuchProcess:
            logger.warning("尝试停止的进程已不存在 (psutil)", pid=pid)
            # 进程已不存在，也视为成功
        except Exception as e:
            logger.error("终止进程时发生未知错误", pid=pid, title=title, error=str(e))
            ui.print_error(f"停止进程 '{title}' (PID: {pid}) 失败: {e}")
            return False
        finally:
            # 无论成功与否，都从管理列表中移除
            if process_info in self.running_processes:
                self.running_processes.remove(process_info)
        
        return True

    def restart_process(self, pid: int) -> bool:
        """通过PID重启单个进程。"""
        process_info = next((info for info in self.running_processes if info.get("process") and info["process"].pid == pid), None)
            
        if process_info:
            command = process_info["command"]
            cwd = process_info["cwd"]
            title = process_info["title"]
            
            ui.print_info(f"正在重启进程 '{title}' (PID: {pid})...")
            
            if self.stop_process(pid):
                time.sleep(1) # 等待端口释放等
                new_process = self.start_in_new_cmd(command, cwd, title)
                if new_process:
                    ui.print_success(f"进程 '{title}' 重启成功。")
                    return True
            
            ui.print_error(f"进程 '{title}' (PID: {pid}) 重启失败。")
            return False
        else:
            ui.print_warning(f"未找到PID为 {pid} 的进程，无法重启。")
            return False


class _LaunchComponent:
    """
    可启动组件的基类。
    """
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_enabled = False

    def check_enabled(self):
        """检查该组件是否根据配置启用。"""
        raise NotImplementedError

    def get_launch_details(self) -> Optional[Tuple[str, str, str]]:
        """获取启动所需的命令、工作目录和窗口标题。"""
        raise NotImplementedError

    def start(self, process_manager: _ProcessManager) -> bool:
        """启动组件。"""
        if not self.is_enabled:
            ui.print_warning(f"组件 '{self.name}' 未启用或配置无效，跳过启动。")
            return False
        
        details = self.get_launch_details()
        if not details:
            ui.print_error(f"无法获取组件 '{self.name}' 的启动详情。")
            return False
            
        command, cwd, title = details
        return process_manager.start_in_new_cmd(command, cwd, title) is not None


# --- 具体组件实现 ---

class _MongoDbComponent(_LaunchComponent):
    """MongoDB组件。"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("MongoDB", config)
        self.check_enabled()

    def check_enabled(self):
        self.is_enabled = self.config.get("install_options", {}).get("install_mongodb", False)

    def get_launch_details(self) -> Optional[Tuple[str, str, str]]:
        # 不再需要启动详情，因为我们将检测系统服务
        return None

    def start(self, process_manager: _ProcessManager) -> bool:
        if not self.is_enabled:
            return True # 如果没配置，也算作"成功"
        
        # 检查系统服务中的MongoDB服务是否启动
        try:
            # 使用sc query命令检查MongoDB服务状态
            result = subprocess.run(["sc", "query", "MongoDB"], capture_output=True, text=True, timeout=10)
            
            if "RUNNING" in result.stdout:
                ui.print_info("MongoDB服务已经在运行。")
                logger.info("MongoDB服务已经在运行")
                return True
            elif "STOPPED" in result.stdout:
                ui.print_warning("MongoDB服务未启动。")
                ui.print_info("请前往系统服务管理页面手动启动MongoDB服务。")
                
                # 尝试打开系统服务管理程序
                services_lnk = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Administrative Tools\services.lnk"
                if os.path.exists(services_lnk):
                    try:
                        os.startfile(services_lnk)
                        ui.print_success("已打开系统服务管理程序，请找到MongoDB服务并手动启动。")
                    except Exception as e:
                        ui.print_warning(f"无法自动打开系统服务管理程序: {e}")
                        ui.print_info("请手动打开'运行'对话框(win+R)，输入'services.msc'来打开系统服务管理程序。")
                else:
                    ui.print_info("请手动打开'运行'对话框(win+R)，输入'services.msc'来打开系统服务管理程序。")
                    ui.print_info("在服务列表中找到“MongoDB Server(MongoDB)”服务，右键点击并选择'启动'。")
                
                return False
            else:
                ui.print_warning("未找到MongoDB服务。")
                ui.print_info("请确认MongoDB是否已正确安装为系统服务。")
                return False
                
        except subprocess.TimeoutExpired:
            ui.print_error("检查MongoDB服务状态超时。")
            logger.error("检查MongoDB服务状态超时")
            return False
        except Exception as e:
            ui.print_error(f"检查MongoDB服务状态时发生错误: {e}")
            logger.error("检查MongoDB服务状态时发生错误", error=str(e))
            return False


class _NapCatComponent(_LaunchComponent):
    """NapCat组件，通过自动检测支持OneKey和Shell版本。"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("NapCat", config)
        self.check_enabled()

    def check_enabled(self):
        self.is_enabled = self.config.get("install_options", {}).get("install_napcat", False)

    def _is_shell_version(self) -> bool:
        """通过检测特征启动脚本文件来判断是否为NapCat.Shell版本。"""
        napcat_path = self.config.get("napcat_path", "")
        if not napcat_path:
            return False
        
        napcat_dir = os.path.dirname(napcat_path)
        if not os.path.isdir(napcat_dir):
            return False
            
        shell_scripts = [
            "launcher.bat", "launcher-user.bat",
            "launcher-win10.bat", "launcher-win10-user.bat"
        ]
        
        return any(os.path.exists(os.path.join(napcat_dir, script)) for script in shell_scripts)

    def get_launch_details(self) -> Optional[Tuple[str, str, str]]:
        """
        获取OneKey版本的启动详情。
        Shell版本有独立的启动逻辑，不使用此方法。
        """
        napcat_path = self.config.get("napcat_path", "")
        if not (napcat_path and os.path.exists(napcat_path) and napcat_path.lower().endswith('.exe')):
            logger.error("NapCat路径无效", path=napcat_path)
            return None
        
        # 如果是Shell版本，则此方法不适用
        if self._is_shell_version():
            return None
            
        # OneKey版本的启动命令
        command = f'"{napcat_path}"'
        if qq_account := self.config.get("qq_account"):
            command += f" {qq_account}"
        cwd = os.path.dirname(napcat_path)
        title = f"NapCatQQ - {self.config.get('version_path', 'N/A')}"
        return command, cwd, title

    def _try_launch_shell_script(
        self, script_path: str, napcat_dir: str, process_manager: _ProcessManager, qq_account: Optional[str] = None
    ) -> Optional[bool]:
        """
        尝试启动单个NapCat.Shell脚本，并与用户确认结果。
        """
        if not os.path.exists(script_path):
            logger.warning("NapCat.Shell 启动脚本不存在", path=script_path)
            return None

        script_name = os.path.basename(script_path)
        command = f'"{script_name}"'
        if qq_account:
            command += f" {qq_account}"
        
        title = f"NapCatQQ - {self.config.get('version_path', 'N/A')} (Shell)"
        
        process = process_manager.start_in_new_cmd(command, napcat_dir, title)
        if not process:
            return False

        time.sleep(3)

        ui.print_warning("NapCat可能启动失败，这应该不是您或我们的问题，我们可以换一种方式启动...")
        if ui.confirm("您的NapCat启动成功了吗？"):
            return True
        else:
            ui.print_info(f"正在停止可能失败的 NapCat 进程 (PID: {process.pid})...")
            process_manager.stop_process(process.pid)
            time.sleep(1)
            return False

    def start(self, process_manager: _ProcessManager) -> bool:
        if not self.is_enabled:
            return True
            
        if check_process("NapCatWinBootMain.exe"):
            ui.print_info("NapCat 已经在运行。")
            logger.info("NapCat已经在运行")
            return True
            
        if not self._is_shell_version():
            # OneKey版本的默认启动方式
            ui.print_info("检测到 NapCat (OneKey) 版本，正在尝试启动...")
            if super().start(process_manager):
                time.sleep(3)
                return True
            return False

        # --- NapCat.Shell版本的特殊启动逻辑 ---
        ui.print_info("检测到 NapCat (Shell) 版本，正在尝试启动...")
        napcat_path = self.config.get("napcat_path", "")
        if not napcat_path or not os.path.exists(os.path.dirname(napcat_path)):
            ui.print_error(f"NapCat路径配置错误或目录不存在: {napcat_path}")
            return False
            
        napcat_dir = os.path.dirname(napcat_path)
        
        import platform
        is_win10 = platform.release() == "10"
        
        preferred_script, fallback_script = (
            ("launcher-win10-user.bat", "launcher-win10.bat") if is_win10
            else ("launcher-user.bat", "launcher.bat")
        )

        qq_for_login = None
        if ui.confirm("是否为 NapCat.Shell 启用快速登录？"):
            qq_for_login = self.config.get("qq_account")
            if qq_for_login:
                ui.print_info(f"将使用QQ号 {qq_for_login} 进行快速登录。")
            else:
                ui.print_warning("配置中未找到有效的QQ号 (qq_account)，将不使用快速登录。")

        preferred_path = os.path.join(napcat_dir, preferred_script)
        fallback_path = os.path.join(napcat_dir, fallback_script)

        ui.print_info(f"步骤 1/2: 尝试使用首选脚本 '{preferred_script}'")
        result = self._try_launch_shell_script(preferred_path, napcat_dir, process_manager, qq_for_login)

        if result is True:
            return True

        if result is False or result is None:
            ui.print_info(f"步骤 2/2: 尝试使用备用脚本 '{fallback_script}'")
            if self._try_launch_shell_script(fallback_path, napcat_dir, process_manager, qq_for_login):
                return True

        ui.print_error("所有 NapCat (Shell) 启动方式均已尝试失败。")
        return False


class _AdapterComponent(_LaunchComponent):
    def __init__(self, config: Dict[str, Any]):
        super().__init__("适配器", config)
        self.check_enabled()

    def check_enabled(self):
        opts = self.config.get("install_options", {})
        version = self.config.get("version_path", "")
        self.is_enabled = opts.get("install_adapter", False) and not is_legacy_version(version)

    def get_launch_details(self) -> Optional[Tuple[str, str, str]]:
        adapter_path = self.config.get("adapter_path", "")
        valid, _ = validate_path(adapter_path, check_file="main.py")
        if not valid:
            logger.error("适配器路径无效", path=adapter_path)
            return None
        
        python_cmd = MaiLauncher._get_python_command(self.config, adapter_path)
        command = f"{python_cmd} main.py"
        bot_nickname = self.config.get('nickname_path', '适配器')
        version = self.config.get('version_path', 'N/A')
        title = f"{bot_nickname} - 适配器 v{version}"
        return command, adapter_path, title
    
    def start(self, process_manager: _ProcessManager) -> bool:
        if not self.is_enabled:
            return True
        
        # 获取bot类型以检查是否为MoFox_bot
        bot_type = self.config.get("bot_type", "MaiBot")
        adapter_path = self.config.get("adapter_path", "")
        
        # 对于MoFox_bot类型，如果适配器目录不存在，仅提醒用户并跳过启动
        if bot_type == "MoFox_bot" and adapter_path and not os.path.exists(adapter_path):
            ui.print_warning("MoFox_bot启动时检测到适配器目录不存在，将跳过适配器启动")
            ui.print_info("适配器目录路径: " + adapter_path)
            return True
        
        ui.print_info("尝试启动适配器...")
        if super().start(process_manager):
            time.sleep(2) # 等待适配器启动
            return True
        return False


class _WebUIComponent(_LaunchComponent):
    def __init__(self, config: Dict[str, Any]):
        super().__init__("WebUI", config)
        self.check_enabled()

    def check_enabled(self):
        self.is_enabled = self.config.get("install_options", {}).get("install_webui", False)

    def _resolve_bun_command(self, webui_path: str) -> Optional[str]:
        """Try to find a bun executable either globally or within the project."""
        candidates = [
            "bun.exe",
            "bun.cmd",
            "bun"
        ] if os.name == "nt" else ["bun"]

        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        local_bin = os.path.join(
            webui_path,
            "node_modules",
            ".bin",
            "bun.cmd" if os.name == "nt" else "bun"
        )
        if os.path.exists(local_bin):
            return local_bin

        return None

    def start(self, process_manager: _ProcessManager) -> bool:
        if not self.is_enabled:
            return True
        
        ui.print_info("尝试启动 MaiBot 控制面板...")
        webui_path = self.config.get("webui_path", "")
        if not (webui_path and os.path.exists(webui_path)):
            ui.print_error("WebUI路径无效或不存在")
            return False

        version = self.config.get('version_path', 'N/A')
        bun_cmd = self._resolve_bun_command(webui_path)
        if bun_cmd:
            bun_exec = f'"{bun_cmd}"'
        else:
            bun_exec = "bun"
            ui.print_warning("未在系统中找到bun，将尝试直接执行 'bun run dev'。")

        # 控制面板使用bun dev服务器，统一监听7999端口
        command = f"{bun_exec} run dev -- --port 7999"
        title = f"MaiBot 控制面板 - {version}"
        process = process_manager.start_in_new_cmd(command, webui_path, title)
        if not process:
            return False

        url = "http://localhost:7999"
        ui.print_info(f"正在打开浏览器访问 {url} ...")
        try:
            webbrowser.open(url)
        except Exception as exc:
            ui.print_warning(f"自动打开浏览器失败，请手动访问 {url} ({exc})")

        return True


class _MaiComponent(_LaunchComponent):
    def __init__(self, config: Dict[str, Any]):
        bot_type = config.get("bot_type", "MaiBot")
        component_name = "MoFox本体" if bot_type == "MoFox_bot" else "麦麦本体"
        super().__init__(component_name, config)
        self.is_enabled = True # 本体总是启用

    def get_launch_details(self) -> Optional[Tuple[str, str, str]]:
        # 根据bot_type字段选择正确的路径字段
        bot_type = self.config.get("bot_type", "MaiBot")  # 获取bot类型，默认为MaiBot
        if bot_type == "MoFox_bot":
            mai_path = self.config.get("mofox_path", "")
        else:
            mai_path = self.config.get("mai_path", "")
        
        version = self.config.get("version_path", "")
        
        if is_legacy_version(version):
            run_bat = os.path.join(mai_path, "run.bat")
            if not os.path.exists(run_bat):
                logger.error("旧版本麦麦缺少run.bat", path=run_bat)
                return None
            command = f'"{run_bat}"'
        else:
            python_cmd = MaiLauncher._get_python_command(self.config, mai_path)
            # 根据bot类型确定启动文件
            if bot_type == "MoFox_bot":
                start_file = "bot.py"
            else:
                start_file = "bot.py"
            command = f"{python_cmd} {start_file}"
            
        bot_nickname = self.config.get('nickname_path', bot_type)
        title = f"{bot_nickname} - {self.name} v{version}"
        return command, mai_path, title
    
    def start(self, process_manager: _ProcessManager) -> bool:
        ui.print_info(f"尝试启动{self.name}...")
        return super().start(process_manager)


# --- 主启动器类 ---

class MaiLauncher:
    """
    麦麦启动器。
    负责验证配置、展示菜单和协调各个组件的启动。
    """
    def __init__(self):
        self._process_manager = _ProcessManager()
        self._components: Dict[str, _LaunchComponent] = {}
        self._config: Optional[Dict[str, Any]] = None
        self._process_cache: Dict[int, psutil.Process] = {}

    @staticmethod
    def _get_python_command(config: Dict[str, Any], cwd: str) -> str:
        """获取Python命令，优先使用虚拟环境。"""
        venv_path = config.get("venv_path", "")
        if venv_path and os.path.exists(venv_path):
            py_exe = os.path.join(venv_path, "Scripts" if os.name == 'nt' else "bin", "python.exe" if os.name == 'nt' else "python")
            if os.path.exists(py_exe):
                logger.info("使用虚拟环境Python", path=py_exe)
                return f'"{py_exe}"'
        
        # 检查工作目录下的常见虚拟环境
        for venv_dir in ["venv", ".venv", "env"]:
            py_exe = os.path.join(cwd, venv_dir, "Scripts" if os.name == 'nt' else "bin", "python.exe" if os.name == 'nt' else "python")
            if os.path.exists(py_exe):
                logger.info("使用项目内虚拟环境Python", path=py_exe)
                return f'"{py_exe}"'

        logger.info("使用系统Python")
        return "python"

    def _register_components(self, config: Dict[str, Any]):
        """根据配置注册所有可用的组件。"""
        self._config = config
        self._components = {
            "mongodb": _MongoDbComponent(config),
            "napcat": _NapCatComponent(config),
            "adapter": _AdapterComponent(config),
            "webui": _WebUIComponent(config),
            "mai": _MaiComponent(config),
        }

    def validate_configuration(self, config: Dict[str, Any]) -> list:
        """验证配置的有效性。"""
        errors = []
        
        # 根据bot_type字段选择正确的路径字段
        bot_type = config.get("bot_type", "MaiBot")  # 获取bot类型，默认为MaiBot
        if bot_type == "MoFox_bot":
            mai_path = config.get("mofox_path", "")
        else:
            mai_path = config.get("mai_path", "")
        
        valid, msg = validate_path(mai_path, check_file="bot.py")
        if not valid:
            errors.append(f"麦麦本体路径: {msg}")

        version = config.get("version_path", "")
        if is_legacy_version(version):
            valid, msg = validate_path(mai_path, check_file="run.bat")
            if not valid:
                errors.append(f"旧版麦麦本体路径缺少run.bat: {msg}")

        # 注册组件以进行后续检查
        self._register_components(config)

        if self._components['adapter'].is_enabled:
            # 对于MoFox_bot类型，适配器目录可以不存在，仅提醒用户
            if bot_type == "MoFox_bot":
                adapter_path = config.get("adapter_path", "")
                if adapter_path and not os.path.exists(adapter_path):
                    # MoFox_bot可以不存在适配器目录，仅记录警告而非错误
                    logger.warning("MoFox_bot启动时检测到适配器目录不存在，将跳过适配器启动", path=adapter_path)
                elif adapter_path and os.path.exists(adapter_path):
                    # 如果适配器目录存在，则验证main.py文件
                    main_file = os.path.join(adapter_path, "main.py")
                    if not os.path.exists(main_file):
                        errors.append(f"适配器路径: 缺少必需文件: main.py")
            else:
                # 对于其他bot类型，严格验证适配器路径
                adapter_path = config.get("adapter_path", "")
                valid, msg = validate_path(adapter_path, check_file="main.py")
                if not valid:
                    errors.append(f"适配器路径: {msg}")

        if self._components['napcat'].is_enabled:
            napcat_path = config.get("napcat_path", "")
            if not (napcat_path and os.path.exists(napcat_path) and napcat_path.lower().endswith('.exe')):
                errors.append("NapCat路径: 无效或文件不存在。")
        
        return errors

    def show_launch_menu(self, config: Dict[str, Any]) -> bool:
        """根据bot类型显示不同的启动菜单并处理用户选择。"""
        self._register_components(config)
        bot_type = config.get("bot_type", "MaiBot")

        ui.clear_screen()
        ui.console.print("[🚀 启动选择菜单]", style=ui.colors["primary"])
        ui.console.print("="*50)
        ui.console.print(f"实例版本: {config.get('version_path', '未知')}")
        ui.console.print(f"实例昵称: {config.get('nickname_path', '未知')}")
        ui.console.print(f"Bot 类型: {bot_type}")
        ui.console.print("\n[可用组件]", style=ui.colors["info"])
        
        # 打印组件状态
        for comp in self._components.values():
            if "本体" not in comp.name:
                ui.console.print(f"  • {comp.name}: {'✅ 可用' if comp.is_enabled else '❌ 未配置'}")
        # Find and print the main component last
        main_comp = next((c for c in self._components.values() if "本体" in c.name), None)
        if main_comp:
            ui.console.print(f"  • {main_comp.name}: ✅ 可用")

        # 根据 bot_type 定义菜单
        if bot_type == "MaiBot":
            menu_options = {
                "1": ("主程序+适配器", ["mai", "adapter"]),
                "2": ("主程序+适配器+NapCatQQ", ["mai", "adapter", "napcat"]),
                "3": ("主程序+适配器+检查MongoDB", ["mai", "adapter", "mongodb"]),
                "4": ("主程序+适配器+NapCatQQ+检查MongoDB", ["mai", "adapter", "napcat", "mongodb"]),
            }
            # 如果控制面板可用，添加包含控制面板的启动选项
            if self._components['webui'].is_enabled:
                menu_options["5"] = ("主程序+适配器+控制面板", ["mai", "adapter", "webui"])
                menu_options["6"] = ("主程序+适配器+NapCat+控制面板", ["mai", "adapter", "napcat", "webui"])
        elif bot_type == "MoFox_bot":
            menu_options = {
                "1": ("主程序", ["mai"]),
                "2": ("主程序+适配器", ["mai", "adapter"]),
                "3": ("主程序+NapCatQQ", ["mai", "napcat"]),
                "4": ("主程序+适配器+NapCatQQ", ["mai", "adapter", "napcat"]),
            }
        else:
            # 默认或未知bot类型的菜单
            menu_options = {
                "1": ("仅启动主程序", ["mai"]),
            }

        ui.console.print("\n[预设启动项]", style=ui.colors["success"])
        for key, (text, _) in menu_options.items():
            ui.console.print(f" [{key}] {text}")
        
        ui.console.print(f" [H] 高级启动项", style=ui.colors["warning"])
        ui.console.print(f" [M] 多开启动（同时启动多个配置）", style=ui.colors["secondary"])
        ui.console.print(f" [Q] 返回", style=ui.colors["exit"])

        while True:
            choice = ui.get_input("请选择启动方式: ").strip().upper()
            if choice == 'Q':
                return False
            if choice == 'H':
                return self._show_advanced_launch_menu()
            if choice == 'M':
                return self._show_multi_launch_menu()
            if choice in menu_options:
                # 检查所选选项中的组件是否都已启用
                _, components_to_start = menu_options[choice]
                all_enabled = True
                for comp_name in components_to_start:
                    if not self._components[comp_name].is_enabled:
                        ui.print_error(f"组件 '{self._components[comp_name].name}' 未配置或未启用，无法使用该启动项。")
                        all_enabled = False
                        break
                if all_enabled:
                    return self.launch(components_to_start)
            else:
                ui.print_error("无效选项，请重新选择。")

    def _show_advanced_launch_menu(self) -> bool:
        """显示高级启动菜单，支持多选。"""
        ui.clear_screen()
        ui.console.print("[🛠️ 高级启动项]", style=ui.colors["warning"])
        ui.console.print("="*50)
        ui.console.print("可多选，请使用英文逗号','分隔选项（例如: 1,3）")

        advanced_options = {
            "1": ("主程序", "mai"),
            "2": ("适配器", "adapter"),
            "3": ("NapCatQQ", "napcat"),
            "4": ("检查MongoDB", "mongodb"),
            "5": ("控制面板", "webui"),
        }
        
        for key, (text, comp_name) in advanced_options.items():
            is_enabled = self._components[comp_name].is_enabled
            status = '✅ 可用' if is_enabled else '❌ 未配置'
            ui.console.print(f" [{key}] {text} - {status}")

        ui.console.print(f" [Q] 返回", style=ui.colors["exit"])

        while True:
            choices_str = ui.get_input("请选择要启动的组件: ").strip().upper()
            if choices_str == 'Q':
                return False

            choices = [c.strip() for c in choices_str.split(',')]
            components_to_start = []
            valid_choices = True

            for choice in choices:
                if choice in advanced_options:
                    _, comp_name = advanced_options[choice]
                    if self._components[comp_name].is_enabled:
                        components_to_start.append(comp_name)
                    else:
                        ui.print_error(f"组件 '{self._components[comp_name].name}' 未配置，无法启动。")
                        valid_choices = False
                        break
                else:
                    ui.print_error(f"无效选项 '{choice}'。")
                    valid_choices = False
                    break
            
            if valid_choices and components_to_start:
                return self.launch(list(dict.fromkeys(components_to_start))) # 去重并保持顺序
            elif valid_choices and not components_to_start:
                ui.print_warning("未选择任何有效组件。")

    def _show_multi_launch_menu(self) -> bool:
        """显示多开启动菜单，允许同时启动多个配置。"""
        from ..core.config import config_manager
        
        ui.clear_screen()
        ui.console.print("[🚀 多开启动助手]", style=ui.colors["secondary"])
        ui.console.print("="*50)
        
        all_configs = config_manager.get_all_configurations()
        if not all_configs:
            ui.print_error("没有可用的配置")
            ui.pause()
            return False
        
        if len(all_configs) < 2:
            ui.print_warning("至少需要2个配置才能进行多开")
            ui.pause()
            return False
        
        # 显示可用的配置
        ui.console.print("\n[可用配置列表]", style=ui.colors["info"])
        config_list = list(all_configs.items())
        for i, (config_name, config) in enumerate(config_list, 1):
            nickname = config.get("nickname_path", "未知")
            version = config.get("version_path", "未知")
            bot_type = config.get("bot_type", "MaiBot")
            ui.console.print(f" [{i}] {config_name}: {nickname} (版本: {version}, 类型: {bot_type})")

        ui.console.print("\n其它操作:", style=ui.colors["info"])
        ui.console.print(f" [D] 检测本地多开（扫描进程与端口）", style=ui.colors["secondary"])
        
        # 让用户选择要启动的配置
        ui.console.print("\n请选择要多开的配置 (使用逗号','分隔，例如: 1,2,3)，或输入 D 执行检测:")
        choices_str = ui.get_input("请输入选择: ").strip()

        if choices_str.upper() == "D":
            self._detect_multi_open()
            ui.pause()
            return False
        
        try:
            choices = [int(c.strip()) for c in choices_str.split(',')]
            selected_configs = []
            
            for choice in choices:
                if 1 <= choice <= len(config_list):
                    config_name, config = config_list[choice - 1]
                    selected_configs.append((config_name, config))
                else:
                    ui.print_error(f"无效的选择: {choice}")
                    return False
            
            if len(selected_configs) < 2:
                ui.print_warning("请至少选择2个配置")
                ui.pause()
                return False
            
            # 显示选中的配置和分配的端口
            ui.console.print("\n[多开配置确认]", style=ui.colors["success"])
            ports = []
            try:
                for i, (config_name, config) in enumerate(selected_configs):
                    port = port_manager.get_available_port(
                        preferred_port=8000 + i * 10,
                        offset=i
                    )
                    ports.append(port)
                    ui.console.print(f"  • {config_name}: 端口 {port}")
            except RuntimeError as e:
                ui.print_error(f"端口分配失败: {str(e)}")
                ui.pause()
                return False
            
            # 确认启动
            if not ui.confirm("\n确认要以上述配置进行多开启动吗？"):
                ui.print_info("已取消多开启动")
                ui.pause()
                return False
            
            # 执行多开启动
            return self._launch_multiple_instances(selected_configs, ports)
            
        except (ValueError, IndexError) as e:
            ui.print_error(f"输入格式错误: {str(e)}")
            ui.pause()
            return False

    def _detect_multi_open(self):
        """检测本地正在运行的多开实例，输出简报。"""
        from rich.table import Table
        from rich.panel import Panel
        import json, os, time

        ui.print_info("🔎 正在检测本地多开实例...")
        report = multi_launch_manager.detect_local_instances()
        processes = report.get("processes", [])
        suspected = report.get("suspected_instances", [])
        ports = report.get("ports", [])

        # 进程表
        proc_table = Table(title="进程匹配（可能的Bot相关进程）", show_header=True, header_style="bold magenta")
        proc_table.add_column("PID", justify="right", style="cyan", no_wrap=True)
        proc_table.add_column("名称", style="yellow")
        if not processes:
            proc_table.add_row("-", "无匹配进程")
        else:
            for p in processes:
                pid = str(p.get("pid", "-"))
                name = str(p.get("name", "未知"))
                proc_table.add_row(pid, name)

        # 端口表（最多展示30条）
        port_table = Table(title="端口占用（可能相关）", show_header=True, header_style="bold magenta")
        port_table.add_column("端口", justify="right", style="cyan", no_wrap=True)
        port_table.add_column("PID", justify="right", style="yellow", no_wrap=True)
        port_table.add_column("状态", style="green")
        if not ports:
            port_table.add_row("-", "-", "无相关端口")
        else:
            shown = 0
            for item in sorted(ports, key=lambda x: (x.get('port', 0), x.get('pid') or 0)):
                port_table.add_row(str(item.get('port')), str(item.get('pid') or "-"), str(item.get('status') or ""))
                shown += 1
                if shown >= 30:
                    break

        # 疑似实例表
        sus_table = Table(title="疑似多开实例（进程关联端口）", show_header=True, header_style="bold magenta")
        sus_table.add_column("PID", justify="right", style="cyan", no_wrap=True)
        sus_table.add_column("名称", style="yellow")
        sus_table.add_column("端口", style="green")
        if not suspected:
            sus_table.add_row("-", "-", "未发现疑似实例")
        else:
            for s in suspected:
                ports_str = ",".join(map(str, s.get('ports', []))) or "无"
                sus_table.add_row(str(s.get('pid')), str(s.get('name')), ports_str)

        # 输出为三个分块
        ui.console.print(Panel(proc_table, border_style="cyan"))
        ui.console.print(Panel(port_table, border_style="cyan"))
        ui.console.print(Panel(sus_table, border_style="cyan"))

        # 自动保存 JSON 报告到 Temporary/
        try:
            ts = time.strftime("%Y%m%d-%H%M%S")
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            temp_dir = os.path.join(root_dir, "Temporary")
            os.makedirs(temp_dir, exist_ok=True)
            out_path = os.path.join(temp_dir, f"detect_multi_open_report_{ts}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            ui.print_success(f"检测报告已保存：{out_path}")
            # 提示是否打开报告目录
            if ui.confirm("是否打开报告目录？"):
                try:
                    import subprocess
                    if os.name == 'nt':
                        subprocess.Popen(["explorer", temp_dir])
                    else:
                        subprocess.Popen(["xdg-open", temp_dir])
                except Exception as e:
                    ui.print_warning(f"打开目录失败：{e}")
        except Exception as e:
            ui.print_warning(f"报告保存失败：{e}")

        ui.print_success("\n✅ 本地多开检测完成")

    def _launch_multiple_instances(self, configs: List[Tuple[str, Dict]], ports: List[int]) -> bool:
        """
        使用真正的并行启动多个Bot实例，支持失败回滚
        
        Args:
            configs: [(config_name, config_dict), ...] 的列表
            ports: [port1, port2, ...] 的列表
            
        Returns:
            是否启动成功
        """
        import threading
        from ..core.config import config_manager
        
        ui.print_info("🚀 开始多开启动流程（并行启动）...")
        
        # 第一阶段：配置备份和预处理
        ui.print_info("\n📋 第一阶段：配置备份...")
        config_backups = {}
        
        for (config_name, config), allocated_port in zip(configs, ports):
            try:
                # 获取Bot路径
                bot_path_key = "mai_path" if config.get("bot_type") == "MaiBot" else "mofox_path"
                bot_path = config.get(bot_path_key, "")
                
                if not bot_path:
                    ui.print_error(f"实例 {config_name} 的Bot路径为空")
                    return False
                
                # 备份配置文件
                config_path = os.path.join(bot_path, "config", "bot_config.toml")
                if os.path.exists(config_path):
                    backup_path = multi_launch_manager.backup_config(config_path)
                    if backup_path:
                        config_backups[config_name] = (config_path, backup_path)
                    else:
                        ui.print_warning(f"无法备份配置文件: {config_path}")
                
                # 注册实例到多开管理器
                if not multi_launch_manager.register_instance(
                    config_name,
                    bot_path,
                    config_name,
                    allocated_port
                ):
                    ui.print_error(f"无法注册实例: {config_name}")
                    return False
                
                # 准备环境（替换端口）
                if not multi_launch_manager.prepare_instance_environment(config_name):
                    ui.print_warning(f"实例 {config_name} 的环境准备失败，但将尝试继续启动")
                
                multi_launch_manager.mark_config_modified(config_path)
                
            except Exception as e:
                ui.print_error(f"准备实例 {config_name} 时出错: {str(e)}")
                logger.error("准备实例失败", config_name=config_name, error=str(e))
                # 回滚已做的改动
                multi_launch_manager.rollback_all()
                return False
        
        # 第二阶段：并行启动所有实例
        ui.print_info("\n🚀 第二阶段：并行启动实例...")
        
        launch_results = {}
        instance_threads = []
        results_lock = threading.Lock()
        
        def launch_instance_thread(config_name: str, config: Dict, allocated_port: int):
            """线程函数：启动单个实例"""
            try:
                ui.print_info(f"[{config_name}] 正在启动...(端口: {allocated_port})")
                
                # 更新配置中的端口信息
                config_manager.set_configuration_port(config_name, allocated_port)
                config_manager.save()
                
                # 为这个实例启动组件
                old_config = self._config
                self._config = config
                self._register_components(config)
                
                success = True
                component_results = {}
                
                # 启动MongoDB（如果需要）
                if self._components['mongodb'].is_enabled:
                    if not self._components['mongodb'].start(self._process_manager):
                        ui.print_warning(f"[{config_name}] MongoDB启动失败，但将继续")
                        component_results['mongodb'] = False
                    else:
                        component_results['mongodb'] = True
                
                # 启动其他组件
                launch_order = ["napcat", "webui", "adapter", "mai"]
                for comp_name in launch_order:
                    if self._components[comp_name].is_enabled:
                        if not self._components[comp_name].start(self._process_manager):
                            component_results[comp_name] = False
                            if comp_name == "mai":
                                ui.print_error(f"[{config_name}] 主程序启动失败")
                                success = False
                                break
                            else:
                                ui.print_warning(f"[{config_name}] {self._components[comp_name].name} 启动失败")
                        else:
                            component_results[comp_name] = True
                
                # 恢复配置
                self._config = old_config
                
                with results_lock:
                    launch_results[config_name] = {
                        "success": success,
                        "components": component_results
                    }
                    
                    if success:
                        multi_launch_manager.mark_instance_launched(config_name)
                        ui.print_success(f"✅ [{config_name}] 启动成功")
                    else:
                        ui.print_error(f"❌ [{config_name}] 启动失败")
                        
            except Exception as e:
                ui.print_error(f"[{config_name}] 启动时出错: {str(e)}")
                logger.error("启动实例线程出错", config_name=config_name, error=str(e))
                
                with results_lock:
                    launch_results[config_name] = {
                        "success": False,
                        "error": str(e)
                    }
        
        # 创建并启动所有线程
        for (config_name, config), allocated_port in zip(configs, ports):
            thread = threading.Thread(
                target=launch_instance_thread,
                args=(config_name, config, allocated_port),
                daemon=False
            )
            instance_threads.append(thread)
            thread.start()
            # 添加小延迟以避免资源竞争
            time.sleep(0.5)
        
        # 等待所有线程完成（设置超时）
        timeout_per_instance = 120  # 每个实例最多等待120秒
        total_timeout = timeout_per_instance * len(instance_threads)
        
        ui.print_info(f"\n⏳ 等待所有实例启动完成（最多等待 {total_timeout} 秒）...")
        
        for thread in instance_threads:
            thread.join(timeout=total_timeout)
        
        # 第三阶段：检查结果并处理失败
        ui.print_info("\n📊 第三阶段：检查启动结果...")
        
        all_success = all(result.get("success", False) for result in launch_results.values())
        successful_instances = [name for name, result in launch_results.items() if result.get("success", False)]
        failed_instances = [name for name, result in launch_results.items() if not result.get("success", False)]
        
        # 显示启动结果
        ui.print_info("\n" + "="*60)
        
        if successful_instances:
            ui.print_success(f"🎉 成功启动 {len(successful_instances)} 个实例:")
            for instance in successful_instances:
                ui.console.print(f"  ✅ {instance}")
        
        if failed_instances:
            ui.print_error(f"❌ {len(failed_instances)} 个实例启动失败:")
            for instance in failed_instances:
                error_info = launch_results[instance].get("error", "未知错误")
                ui.console.print(f"  ❌ {instance}: {error_info}")
        
        ui.print_info("="*60)
        
        # 如果有失败的实例，执行回滚
        if not all_success:
            ui.print_warning("\n🔄 检测到启动失败，正在执行回滚...")
            rollback_results = multi_launch_manager.rollback_all()
            
            if rollback_results:
                success_rollbacks = sum(1 for v in rollback_results.values() if v)
                ui.print_info(f"✅ 回滚完成：{success_rollbacks}/{len(rollback_results)} 个配置文件已恢复")
                for config_path, success in rollback_results.items():
                    status = "✅ 已恢复" if success else "❌ 恢复失败"
                    ui.print_info(f"  {status}: {config_path}")
            else:
                ui.print_warning("⚠️  没有需要回滚的配置")
        else:
            ui.print_success("✅ 所有实例启动成功！")
            # 清理备份文件
            multi_launch_manager.cleanup_backups()
            ui.print_info("🧹 已清理备份文件")
        
        ui.pause()
        return all_success

    def launch(self, components_to_start: List[str]) -> bool:
        """根据给定的组件列表启动。"""
        if not self._config:
            ui.print_error("配置未加载，无法启动。")
            return False

        # 确保MongoDB总是最先启动
        if self._components['mongodb'].is_enabled:
            if not self._components['mongodb'].start(self._process_manager):
                ui.print_warning("MongoDB启动失败，但将继续尝试启动其他组件。")
        
        # 处理全栈启动
        if "full_stack" in components_to_start:
            components_to_start = [name for name, comp in self._components.items() if comp.is_enabled and name != "mongodb"]

        # 按顺序启动组件
        launch_order = ["napcat", "webui", "adapter", "mai"]
        final_success = True
        
        for comp_name in launch_order:
            if comp_name in components_to_start:
                if not self._components[comp_name].start(self._process_manager):
                    # 麦麦本体是核心，如果它失败了，整个启动就算失败
                    if comp_name == "mai":
                        final_success = False
                        break
        
        if final_success:
            ui.print_success("🎉 启动流程完成！")
        else:
            ui.print_error("核心组件'麦麦本体'启动失败，请检查日志。")

        return final_success

    def stop_all_processes(self):
        """停止所有由启动器启动的进程。"""
        ui.print_info("正在停止所有相关进程...")
        self._process_manager.stop_all()
    
    def stop_process(self, pid: int) -> bool:
        """停止单个托管进程。"""
        return self._process_manager.stop_process(pid)

    def restart_process(self, pid: int) -> bool:
        """重启单个托管进程。"""
        return self._process_manager.restart_process(pid)

    def get_managed_pids(self) -> List[int]:
        """获取所有当前受管进程的PID列表。"""
        # 添加启动器自身的PID
        pids = [os.getpid()]
        # 添加所有由_process_manager管理的子进程PID
        pids.extend([info["process"].pid for info in self._process_manager.running_processes if info.get("process") and info["process"].poll() is None])
        return pids

    def show_running_processes(self):
        """以表格形式显示当前正在运行的进程状态，并使用缓存计算CPU。"""
        managed_procs_info = self._process_manager.get_running_processes_info()
        
        table = Table(title="[📊 进程状态管理]", show_header=True, header_style="bold magenta")
        table.add_column("PID", style="dim", width=8)
        table.add_column("进程名称", style="cyan", no_wrap=True)
        table.add_column("CPU %", style="green", justify="right")
        table.add_column("内存 (MB)", style="yellow", justify="right")
        table.add_column("运行时间 (s)", style="blue", justify="right")

        current_pids = {info["process"].pid for info in managed_procs_info}
        current_pids.add(os.getpid())

        # 清理已结束进程的缓存
        for pid in list(self._process_cache.keys()):
            if pid not in current_pids:
                del self._process_cache[pid]
        
        all_process_meta = [{"pid": os.getpid(), "title": "麦麦启动器 (主程序)"}]
        for info in managed_procs_info:
            all_process_meta.append({"pid": info["process"].pid, "title": info["title"], "start_time": info["start_time"]})

        if not all_process_meta:
            ui.print_info("当前没有由本启动器启动的正在运行的进程。")
            return table

        for meta in all_process_meta:
            pid = meta["pid"]
            try:
                p = self._process_cache.get(pid)
                if p is None:
                    p = psutil.Process(pid)
                    p.cpu_percent()  # 第一次调用返回0，但会初始化计时器
                    self._process_cache[pid] = p
                    cpu_percent = 0.0
                else:
                    cpu_percent = p.cpu_percent() # 后续调用将返回有意义的值
                
                memory_mb = p.memory_info().rss / (1024 * 1024)
                running_time = time.time() - (meta.get("start_time") or p.create_time())

                table.add_row(
                    str(pid),
                    meta['title'],
                    f"{cpu_percent:.2f}",
                    f"{memory_mb:.2f}",
                    f"{int(running_time)}"
                )
            except (psutil.NoSuchProcess, Exception) as e:
                logger.warning("获取进程信息失败", pid=pid, error=str(e))
                if pid in self._process_cache:
                    del self._process_cache[pid]
        
        return table

    def get_process_details(self, pid: int) -> Optional[Dict[str, Any]]:
        """获取单个进程的详细信息（不包括冲突的CPU数据）。"""
        try:
            p = psutil.Process(pid)
            managed_info = next((info for info in self._process_manager.running_processes if info.get("process") and info["process"].pid == pid), None)
            
            details = {
                "PID": p.pid,
                "名称": p.name(),
                "状态": p.status(),
                "内存 (MB)": f"{p.memory_info().rss / (1024 * 1024):.2f}",
                "启动时间": datetime.fromtimestamp(p.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
                "命令行": " ".join(p.cmdline()),
                "工作目录": p.cwd(),
                "父进程ID": p.ppid(),
            }
            if managed_info:
                details["托管标题"] = managed_info["title"]

            return details
        except (psutil.NoSuchProcess, Exception) as e:
            logger.warning("获取进程详细信息失败", pid=pid, error=str(e))
            return None


# 全局启动器实例
launcher = MaiLauncher()
