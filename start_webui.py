import subprocess
import os
import threading
import time
import webbrowser

def run_command(command, cwd):
    """在一个指定的目录中运行一个命令"""
    print(f"在目录 '{cwd}' 中运行命令: {' '.join(command)}")
    # 在Windows上使用 shell=True 来确保命令能被正确解释
    is_windows = os.name == 'nt'
    process = subprocess.Popen(command, cwd=cwd, shell=is_windows, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    
    # 实时打印输出
    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            print(f"[{' '.join(command)}] {line}", end='')
    
    if process.stderr:
        stderr = process.stderr.read()
        if stderr:
            print(f"[{' '.join(command)}] [错误]: {stderr}")


def get_ports_from_config():
    """从 P-config.toml 读取端口配置"""
    try:
        import toml
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'P-config.toml')
        if not os.path.exists(config_path):
            print(f"[警告] 配置文件 {config_path} 不存在，将使用默认端口。")
            return 7099, 7098
        
        config = toml.load(config_path)
        backend_port = config.get('webui', {}).get('backend_port', 7099)
        frontend_port = config.get('webui', {}).get('frontend_port', 7098)
        return backend_port, frontend_port
    except Exception as e:
        print(f"[错误] 读取端口配置失败: {e}，将使用默认端口。")
        return 7099, 7098

def start_backend(port):
    """启动FastAPI后端服务"""
    # 从项目根目录启动，以确保模块路径正确
    project_root = os.path.dirname(__file__)
    
    # 注意：此脚本现在假定您已在项目的主Python环境中
    # 通过 `pip install -r requirements.txt` 安装了所有依赖。
    print("准备启动后端服务...")
    print("请确保您已在当前环境中执行 'pip install -r requirements.txt'")
    
    # 指定完整的模块路径 webui.backend.main:app
    command = ["uvicorn", "webui.backend.main:app", "--host", "127.0.0.1", "--port", str(port), "--reload"]
    run_command(command, cwd=project_root)


def start_frontend(port):
    """启动Vue前端开发服务器"""
    frontend_dir = os.path.join(os.path.dirname(__file__), 'webui', 'frontend')
    
    # 每次启动都运行 npm install 以确保依赖是同步的
    # npm 会自动处理，只安装或更新必要的包
    print("正在同步前端依赖...")
    # 注意：这里需要系统已安装 Node.js 和 npm
    run_command(["npm", "install"], cwd=frontend_dir)
    print("前端依赖同步完毕。")

    # 使用指定端口启动服务
    command = ["npm", "run", "dev", "--", "--port", str(port)]
    run_command(command, cwd=frontend_dir)


if __name__ == "__main__":
    print("--- 正在启动 MaiBot Initiate WebUI ---")
    
    # 从配置文件读取端口
    backend_port, frontend_port = get_ports_from_config()

    # 在独立的线程中启动后端和前端
    backend_thread = threading.Thread(target=start_backend, args=(backend_port,))
    frontend_thread = threading.Thread(target=start_frontend, args=(frontend_port,))

    backend_thread.start()
    frontend_thread.start()

    print(f"\n后端服务 (FastAPI) 正在 http://127.0.0.1:{backend_port} 启动...")
    print(f"前端服务 (Vite) 正在 http://localhost:{frontend_port} 启动...")
    print("请稍等片刻，待服务启动完毕后，浏览器将自动打开前端页面。")
    
    # 等待几秒钟让Vite启动
    time.sleep(10)
    
    # 自动在浏览器中打开前端页面
    webbrowser.open(f"http://localhost:{frontend_port}")

    # 等待线程结束
    backend_thread.join()
    frontend_thread.join()
    print("--- WebUI 服务已关闭 ---")