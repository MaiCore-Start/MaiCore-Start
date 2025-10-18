import os
import json
import toml
from fastapi import APIRouter, HTTPException
from bs4 import BeautifulSoup
import re

router = APIRouter()

CONFIG_FILE_PATH = "config/config.toml"

def get_instance_root_path(instance_name: str) -> str:
    """根据实例名称从主配置文件中获取其根目录路径。"""
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = toml.load(f)
        
        instance_data = config.get("configurations", {}).get(instance_name)
        if not instance_data:
            raise HTTPException(status_code=404, detail=f"实例 '{instance_name}' 在配置文件中未找到。")
        
        # 优先使用 mofox_path 或 mai_path 作为根目录
        bot_path = instance_data.get("mofox_path") or instance_data.get("mai_path") or instance_data.get("maibot_path")
        
        if not bot_path or not os.path.isdir(bot_path):
            raise HTTPException(status_code=404, detail=f"实例 '{instance_name}' 的根目录路径无效或不存在: {bot_path}")
            
        return bot_path
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="主配置文件 'config/config.toml' 未找到。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理配置文件时出错: {e}")

def parse_stats_html(html_path: str) -> dict:
    """解析 maibot_statistics.html 文件，提取图表数据。"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')
        
        script_tag = soup.find('script', string=re.compile(r'const allChartData ='))
        if not script_tag:
            raise HTTPException(status_code=404, detail="在HTML文件中未找到 'allChartData' 脚本。")
            
        script_content = script_tag.string
        # 使用正则表达式提取 JSON 对象字符串
        match = re.search(r'const allChartData = (.*?);', script_content, re.DOTALL)
        if not match:
             raise HTTPException(status_code=500, detail="无法从脚本中提取JSON数据。")

        json_str = match.group(1).strip()
        chart_data = json.loads(json_str)
        return chart_data

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"统计文件不存在: {html_path}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析HTML文件中的JSON数据失败。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析HTML文件时发生未知错误: {e}")


@router.get("/statistics/{instance_name}", summary="获取单个实例的统计数据")
def get_instance_statistics(instance_name: str):
    """
    根据实例名称，找到对应的 maibot_statistics.html 文件，并解析其中的数据返回。
    """
    # 1. 定位实例根目录
    root_path = get_instance_root_path(instance_name)
    
    # 2. 构建统计文件路径
    stats_file_path = os.path.join(root_path, "maibot_statistics.html")
    
    # 3. 解析并返回数据
    return parse_stats_html(stats_file_path)

# 聚合所有实例数据的逻辑可以在这里进一步实现
@router.get("/statistics/summary", summary="获取所有实例的统计数据摘要（待实现）")
def get_statistics_summary():
    """
    （待实现）聚合所有可用的实例统计数据，为全局仪表盘提供数据。
    """
    # 示例逻辑：
    # 1. 加载 config.toml 获取所有实例名称
    # 2. 遍历每个实例，调用 get_instance_statistics
    # 3. 将数据进行聚合（例如，加总所有实例的总花费）
    # 4. 返回聚合后的数据
    raise HTTPException(status_code=501, detail="此功能正在开发中。")
