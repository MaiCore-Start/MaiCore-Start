"""
简单脚本：调用 MultiLaunchManager 的本地多开检测并打印结果
"""
import json
from src.modules.multi_launch import multi_launch_manager

if __name__ == "__main__":
    report = multi_launch_manager.detect_local_instances()
    print("=== 本地多开检测报告 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
