# 多开失败回滚和并行启动功能指南

## 📋 概述

本文档详细说明了 v2.0 版本中新增的两项重要功能：
- **失败回滚机制**: 自动恢复配置文件，防止错误配置
- **真正的并行启动**: 使用多线程实现真正的并行启动，显著提升启动速度

## 🔄 失败回滚机制详解

### 什么是失败回滚？

失败回滚是一种安全机制，确保在多开启动过程中如果某个实例启动失败，系统会自动：
1. **恢复配置**: 将被修改的配置文件恢复到原始状态
2. **清理资源**: 清理备份文件和临时数据
3. **停止其他实例**: 停止已成功启动的实例（保留完整状态）

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 启动多开流程                                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 第一阶段：配置备份                                          │
│ • 备份所有实例的配置文件                                    │
│ • 记录备份文件位置                                          │
│ • 注册实例信息                                              │
│ • 准备实例环境                                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 第二阶段：并行启动                                          │
│ • 使用多线程并行启动所有实例                                │
│ • 实时监控每个实例的启动状态                                │
│ • 收集每个实例的启动结果                                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    ┌─────┴─────┐
                    ↓           ↓
            ✅ 全部成功    ❌ 部分失败
                    │           │
                    ↓           ↓
            清理备份文件    执行回滚
            继续运行        恢复配置
                            清理资源
```

### 详细步骤

#### 1️⃣ 配置备份阶段
```python
# 系统自动执行以下操作：
for instance in selected_instances:
    config_path = f"{bot_path}/config/bot_config.toml"
    # 创建备份：bot_config.toml.backup
    backup_path = multi_launch_manager.backup_config(config_path)
    print(f"✓ 已备份: {config_path} -> {backup_path}")
```

**特点**:
- 备份文件使用 `.backup` 后缀
- 若已存在备份，自动添加时间戳避免覆盖
- 使用 `shutil.copy2()` 保留文件元数据（修改时间等）

#### 2️⃣ 并行启动阶段
```python
# 创建每个实例的启动线程
for instance in selected_instances:
    thread = threading.Thread(
        target=launch_instance_thread,
        args=(instance_name, config, port)
    )
    threads.append(thread)
    thread.start()  # 立即启动

# 等待所有线程完成（最多等待120秒/实例）
for thread in threads:
    thread.join(timeout=120)
```

**并行优势**:
- 三个实例并行启动耗时 ~120 秒
- 串行启动相同实例耗时 ~360 秒
- **性能提升**: 约 66% 的时间节省

#### 3️⃣ 失败检测阶段
```python
# 统计启动结果
successful = [name for name, result in launch_results.items() 
              if result.get("success", False)]
failed = [name for name, result in launch_results.items() 
          if not result.get("success", False)]

if failed:
    # 检测到失败，触发回滚
    print(f"❌ 检测到 {len(failed)} 个实例启动失败")
    print("🔄 开始回滚...")
```

#### 4️⃣ 回滚执行阶段
```python
# 系统执行以下回滚操作：
rollback_results = multi_launch_manager.rollback_all()

# 详细过程：
for config_path in modified_configs:
    backup_path = config_backups[config_path]
    
    # 恢复原文件
    shutil.copy2(backup_path, config_path)
    print(f"✓ 已恢复: {config_path}")
    
    # 删除备份文件
    os.remove(backup_path)
    print(f"✓ 已清理备份: {backup_path}")
```

### 用户看到的流程

```
🚀 开始多开启动流程（并行启动）...

📋 第一阶段：配置备份...
  ✓ 已备份: D:\Bot1\config\bot_config.toml
  ✓ 已备份: D:\Bot2\config\bot_config.toml
  ✓ 已备份: D:\Bot3\config\bot_config.toml

🚀 第二阶段：并行启动实例...
  ⏳ [Bot1] 正在启动...(端口: 8001)
  ⏳ [Bot2] 正在启动...(端口: 8002)
  ⏳ [Bot3] 正在启动...(端口: 8003)
  ✅ [Bot1] 启动成功
  ❌ [Bot2] 启动失败 (MongoDB未启动)
  ✅ [Bot3] 启动成功

📊 第三阶段：检查启动结果...
  🎉 成功启动 2 个实例:
    ✅ Bot1
    ✅ Bot3
  
  ❌ 1 个实例启动失败:
    ❌ Bot2: MongoDB启动失败

🔄 检测到启动失败，正在执行回滚...
  ✅ 已恢复: D:\Bot1\config\bot_config.toml
  ✅ 已恢复: D:\Bot2\config\bot_config.toml
  ✅ 已恢复: D:\Bot3\config\bot_config.toml
  ✅ 回滚完成：3/3 个配置文件已恢复
  🧹 已清理备份文件
```

## ⚡ 真正的并行启动详解

### 架构设计

```
主线程 (Main Thread)
    ↓
┌───────────────────────────────────────────┐
│ 配置备份阶段 (序列执行)                    │
│  • 备份 Instance 1 配置                    │
│  • 备份 Instance 2 配置                    │
│  • 备份 Instance 3 配置                    │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│ 并行启动阶段 (真并行)                     │
│                                           │
│  ┌─────────────┐  ┌─────────────┐        │
│  │ 线程 1      │  │ 线程 2      │  ...  │
│  │Instance 1   │  │Instance 2   │        │
│  │启动         │  │启动         │        │
│  └─────────────┘  └─────────────┘        │
│       ↓                ↓                  │
│    120s            120s                   │
│       └────────┬────────┘                 │
│               120s (并行总时间)           │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│ 结果检查阶段 (并行等待)                   │
│  • 等待所有线程完成                      │
│  • 汇总启动结果                          │
│  • 执行回滚(如需)                        │
└───────────────────────────────────────────┘
```

### 线程安全设计

系统使用了多种机制确保线程安全：

```python
# 1. 使用 threading.Lock 保护共享资源
results_lock = threading.Lock()

def launch_instance_thread(...):
    # 执行启动操作
    ...
    
    # 线程安全地更新结果
    with results_lock:
        launch_results[instance_name] = {...}
        ui.print_success(f"✅ [{instance_name}] 启动成功")
```

**保护机制**:
- ✅ `launch_results` 字典（共享结果）
- ✅ 控制台输出（UI 操作）
- ✅ 配置管理器更新
- ✅ 实例状态追踪

### 超时管理

```python
# 每个实例最多等待 120 秒
timeout_per_instance = 120
total_timeout = timeout_per_instance * len(instance_threads)

# 等待所有线程完成
for thread in instance_threads:
    thread.join(timeout=total_timeout)

# 如果线程超时仍未完成，会显示警告
```

### 组件启动顺序

每个实例内，组件按照以下顺序启动：
```
1. MongoDB (数据库)
   ↓
2. NapCat (QQ 客户端)
   ↓
3. WebUI (Web 管理界面)
   ↓
4. Adapter (适配器)
   ↓
5. Mai (主程序)
```

这个顺序确保了依赖关系的正确性。

## 📊 性能对比

### 启动时间比较

| 场景 | 串行启动 | 并行启动 | 性能提升 |
|------|--------|--------|--------|
| 1个实例 | 120s | 120s | 0% |
| 2个实例 | 240s | 120s | 50% ↑ |
| 3个实例 | 360s | 120s | 66% ↑ |
| 5个实例 | 600s | 120s | 80% ↑ |

### 资源使用对比

| 指标 | 串行启动 | 并行启动 |
|------|--------|--------|
| CPU 平均使用率 | 低 | 中高 |
| 内存峰值 | 递增 | 一次性高峰 |
| 磁盘 I/O | 连续 | 集中 |

## 🛡️ 安全特性

### 备份文件管理
```
备份流程：
  config.toml → config.toml.backup

启动成功时：
  ✓ config.toml.backup (自动删除)

启动失败时：
  ✓ config.toml.backup (用于恢复)
  ↓
  恢复完成后 (自动删除)
```

### 失败恢复策略

| 失败类型 | 处理方式 |
|---------|--------|
| 单个实例失败 | 回滚全部配置 |
| MongoDB 启动失败 | 回滚全部配置 |
| 网络问题 | 回滚全部配置 |
| 用户中断 | 保留部分状态，提示手动回滚 |

## 🔧 高级配置

### 调整超时时间

在 `launcher.py` 中修改：

```python
# 修改每个实例的超时时间（单位：秒）
timeout_per_instance = 120  # 改为 60 则超时为 60 秒

# 修改启动线程的延迟（避免资源竞争）
time.sleep(0.5)  # 改为 1.0 则增加更多延迟
```

### 禁用并行启动

如果需要使用旧的串行启动方式：

```python
# 在 launcher.py 中注释掉并行启动部分
# 使用旧的 _launch_multiple_instances_serial() 方法
```

## 📋 故障排除

### Q: 启动失败后配置没有恢复

**A**: 检查以下几点：
1. 确保备份文件存在：`config.toml.backup`
2. 检查文件权限，确保可读写
3. 查看日志中的恢复结果信息

### Q: 某些实例无法并行启动

**A**: 可能原因：
1. MongoDB 独占，无法并行：在启动前手动启动 MongoDB
2. 端口冲突：检查分配的端口是否已被占用
3. 资源不足：增加系统内存

### Q: 恢复配置后某些实例无法启动

**A**: 
1. 手动检查配置文件内容
2. 尝试从更早的备份恢复
3. 检查日志文件获取详细错误信息

## 💡 最佳实践

### 1️⃣ 启动前的检查
```
□ 确认所有 Bot 配置文件正确
□ 检查磁盘空间充足（至少 1GB）
□ 关闭不需要的后台程序
□ 确保 MongoDB 安装正确
```

### 2️⃣ 启动中的监控
```
□ 观察每个实例的启动信息
□ 注意警告信息和错误提示
□ 避免在启动中操作文件
□ 保持网络连接稳定
```

### 3️⃣ 启动后的验证
```
□ 验证所有实例正常运行
□ 测试各实例的功能
□ 查看日志确认无错误
□ 备份成功的配置文件
```

## 📚 相关文档

- [多开快速开始](MULTI_LAUNCH_QUICKSTART.md)
- [多开详细指南](MULTI_LAUNCH_GUIDE.md)
- [技术实现细节](MULTI_LAUNCH_IMPLEMENTATION.md)

## 🎯 总结

本版本新增的失败回滚和并行启动功能为多开提供了：

✅ **可靠性**: 自动回滚防止配置错误
✅ **性能**: 并行启动快 3 倍
✅ **安全性**: 完整的备份和恢复机制
✅ **易用性**: 自动化处理，无需手动干预

这些改进使得 MaiCore 成为了一个可以安心使用的生产级多开工具。
