# 本地多开检测报告

生成时间：2025-12-14
适用版本：V4.1 系列

## 功能概述
- 进程扫描：基于签名匹配识别可能的 Bot 相关进程。
- 端口扫描：收集可能相关的监听/连接端口并关联到进程。
- 疑似实例：将进程与其占用端口关联，生成疑似多开实例列表。

入口位置：主菜单 [A3] 检测本地多开（进程/端口），或多开菜单输入 `D`。

## 使用方法
- 交互方式：运行主程序，选择 A3 → 查看检测输出 → 按任意键返回主菜单。
- 命令方式：在项目虚拟环境中运行：
  ```powershell
  Push-Location " "
  .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0, r' '); from src.modules.launcher import launcher; launcher._detect_multi_open()"
  Pop-Location
  ```

## 示例输出（本机一次检测快照）
- 进程匹配（可能的Bot相关进程）
  - 无匹配进程
- 端口占用（可能相关）（节选）
  - 端口 1042 ← PID 23056 (ESTABLISHED)
  - 端口 1042 ← PID 23056 (LISTEN)
  - 端口 3702 ← PID 8332 (NONE)
  - 端口 3917 ← PID 3756 (LISTEN)
  - 端口 5040 ← PID 13332 (LISTEN)
- 疑似多开实例（进程关联端口）
  - 未发现疑似实例

注：上述为示例快照，不同机器与时刻会有差异。

## 导出报告
- 如需导出 JSON 报告，可运行演示脚本：
  ```powershell
  Push-Location " "
  .venv\\Scripts\\python.exe scripts\\detect_multi_open_demo.py > Temporary\\detect_multi_open_report.json
  Pop-Location
  ```
- 也可在代码中直接调用 `multi_launch_manager.detect_local_instances()` 获取结构化数据：
  - 返回键：`processes`（进程匹配列表）、`ports`（端口占用列表）、`suspected_instances`（疑似实例）。

## 进一步优化建议
- 表格化输出：使用 `rich.Table` 展示进程与端口，提升可读性。
- 增强匹配：扩充 `process_signatures` 与 `port_hints`，提高识别准确度。
- 历史留存：将每次检测结果保存到 `Temporary/`，便于趋势分析。
