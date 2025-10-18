import toml
import os
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter()

# 配置文件路径
CONFIG_FILE_PATH = "config/config.toml"

class InstanceConfig(BaseModel):
    serial_number: str
    absolute_serial_number: int
    version_path: str
    nickname_path: str
    bot_type: str
    qq_account: str
    mai_path: Optional[str] = None
    mofox_path: Optional[str] = None
    adapter_path: Optional[str] = None
    napcat_path: Optional[str] = None
    venv_path: Optional[str] = None
    mongodb_path: Optional[str] = None
    webui_path: Optional[str] = None
    install_options: Optional[Dict[str, bool]] = None

class CreateInstancePayload(BaseModel):
    name: str
    config: Dict[str, Any]


def load_instance_config():
    """加载实例配置文件"""
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            return toml.load(f)
    except FileNotFoundError:
        # 如果文件不存在，创建一个空的结构
        return {"configurations": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载实例配置文件失败: {e}")

def save_instance_config(config_data: Dict[str, Any]):
    """保存实例配置文件"""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            toml.dump(config_data, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存实例配置文件失败: {e}")


@router.get("/instances", summary="获取所有实例配置")
def get_all_instances():
    """获取 config.toml 中定义的所有实例配置。"""
    config = load_instance_config()
    return config.get("configurations", {})

@router.post("/instances", summary="创建一个新的实例配置")
def create_instance(payload: CreateInstancePayload):
    """创建一个新的实例配置集。"""
    config = load_instance_config()
    instances = config.setdefault("configurations", {})
    
    name = payload.name
    new_config_data = payload.config

    # 校验：名称是否已存在
    if name in instances:
        raise HTTPException(status_code=400, detail=f"配置集名称 '{name}' 已存在。")

    # 校验：序列号是否唯一
    if 'serial_number' in new_config_data:
        new_serial = new_config_data['serial_number']
        for inst_name, inst_data in instances.items():
            if inst_data.get('serial_number') == new_serial:
                raise HTTPException(status_code=400, detail=f"用户序列号 '{new_serial}' 已被配置集 '{inst_name}' 使用。")

    # 分配绝对序列号
    used_abs_serials = {inst.get("absolute_serial_number", 0) for inst in instances.values()}
    new_abs_serial = 1
    while new_abs_serial in used_abs_serials:
        new_abs_serial += 1
    new_config_data["absolute_serial_number"] = new_abs_serial

    instances[name] = new_config_data
    save_instance_config(config)
    
    return {"status": "success", "message": f"实例 '{name}' 创建成功。", "name": name, "config": new_config_data}

@router.post("/instances/{name}", summary="更新指定实例的配置")
def update_instance(name: str, instance_update: Dict[str, Any]):
    """更新一个已存在的实例配置。"""
    config = load_instance_config()
    instances = config.get("configurations", {})

    if name not in instances:
        raise HTTPException(status_code=404, detail=f"配置集 '{name}' 未找到。")
    
    # 更新数据
    instances[name].update(instance_update)
    save_instance_config(config)

    return {"status": "success", "message": f"实例 '{name}' 更新成功。", "config": instances[name]}

@router.delete("/instances/{name}", summary="删除一个实例配置")
def delete_instance(name: str):
    """根据名称删除一个实例配置集。"""
    config = load_instance_config()
    instances = config.get("configurations", {})

    if name not in instances:
        raise HTTPException(status_code=404, detail=f"配置集 '{name}' 未找到。")
    
    deleted_config = instances.pop(name)
    save_instance_config(config)

    return {"status": "success", "message": f"实例 '{name}' 已被删除。", "deleted_config": deleted_config}