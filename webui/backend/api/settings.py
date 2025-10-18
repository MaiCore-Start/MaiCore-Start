import toml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

# 相对路径是相对于项目根目录
CONFIG_FILE_PATH = "config/P-config.toml"
DEFAULT_CONFIG = {
    "theme": {
        "primary": "#BADFFA",
        "success": "#4AF933",
        "warning": "#F2FF5D",
        "error": "#FF6B6B",
        "info": "#6DA0FD",
        "secondary": "#00FFBB",
    },
    "logging": {
        "log_rotation_days": 30
    },
    "display": {
        "max_versions_display": 20
    },
    "on_exit": {
        "process_action": "ask"
    },
    "webui": {
        "backend_port": 7099,
        "frontend_port": 7098
    }
}

# 列表来源: https://chromium.googlesource.com/chromium/src/+/main/net/base/port_util.cc
UNSAFE_PORTS = [
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53,
    69, 77, 79, 87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115,
    117, 119, 123, 135, 137, 139, 143, 161, 162, 179, 389, 427, 465,
    512, 513, 514, 515, 526, 530, 531, 532, 540, 548, 554, 556, 563,
    587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049, 3659,
    4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697,
    10080,
]

class WebUISettings(BaseModel):
    backend_port: int = 7099
    frontend_port: int = 7098

class ProgramSettings(BaseModel):
    theme: Dict[str, str]
    logging: Dict[str, Any]
    display: Dict[str, Any]
    on_exit: Dict[str, str]
    webui: WebUISettings

def load_p_config():
    """加载主程序配置文件"""
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            return toml.load(f)
    except FileNotFoundError:
        return DEFAULT_CONFIG
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载配置文件失败: {e}")

def save_p_config(config_data: Dict[str, Any]):
    """保存主程序配置文件"""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            toml.dump(config_data, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {e}")


@router.get("/settings/program", response_model=ProgramSettings, summary="获取程序设置")
def get_program_settings():
    """
    提供用于可视化设置程序的配置信息。
    """
    return load_p_config()

@router.post("/settings/program", summary="更新程序设置")
def update_program_settings(settings: ProgramSettings):
    """
    接收前端传来的新设置并保存到 P-config.toml。
    """
    # 校验端口
    backend_port = settings.webui.backend_port
    frontend_port = settings.webui.frontend_port

    if backend_port in UNSAFE_PORTS:
        raise HTTPException(status_code=400, detail=f"后端端口 {backend_port} 是浏览器限制的端口，请更换。")
    if frontend_port in UNSAFE_PORTS:
        raise HTTPException(status_code=400, detail=f"前端端口 {frontend_port} 是浏览器限制的端口，请更换。")
    if backend_port == frontend_port:
        raise HTTPException(status_code=400, detail="后端和前端端口不能相同。")

    config_data = settings.dict()
    save_p_config(config_data)
    return {"status": "success", "message": "程序设置已成功更新。"}