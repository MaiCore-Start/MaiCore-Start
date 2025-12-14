# 多开启动功能使用指南

## 功能概述

多开启动功能允许用户同时启动多个Bot实例，系统会自动为每个实例分配不同的端口，避免端口冲突。

## 主要特性

### 1. **自动端口分配**
- 系统自动检测已使用的端口
- 为每个实例分配可用的端口
- 避免端口冲突导致的启动失败

### 2. **配置文件自动替换**
- 自动修改Bot配置文件中的端口号
- 支持TOML、JSON、YAML格式
- 支持多种端口配置字段

### 3. **实例管理**
- 注册和跟踪多个实例
- 为每个实例单独管理进程
- 支持实例状态查询

## 使用方法

### 方法一：从主菜单启动

1. 运行启动器，进入主菜单
2. 选择 `[A2]` - 多开启动
3. 从可用配置列表中选择要启动的配置（用逗号分隔）
4. 系统会显示分配的端口号
5. 确认后启动实例

### 方法二：从启动菜单启动

1. 选择 `[A]` - 运行麦麦
2. 选择一个配置
3. 在启动菜单中选择 `[M]` - 多开启动
4. 按照提示选择要启动的配置

## 配置示例

假设你有以下配置：
- 配置1: "bot_01" (端口: 8000)
- 配置2: "bot_02" (端口: 8010)
- 配置3: "bot_03" (端口: 8020)

当你选择启动配置1、2、3时：
```
[多开配置确认]
  • bot_01: 端口 8000
  • bot_02: 端口 8010
  • bot_03: 端口 8020
```

系统会自动修改每个配置的 `bot_config.toml` 文件中的端口号。

## 端口管理

### 端口范围
- 默认范围: 8000 - 9000
- 系统会跳过以下保留端口：
  - 22 (SSH)
  - 80 (HTTP)
  - 443 (HTTPS)
  - 3306 (MySQL)
  - 5432 (PostgreSQL)
  - 6379 (Redis)
  - 27017 (MongoDB)
  - 8080 (常见Web服务)

### 自定义端口

在配置文件 (`config/config.toml`) 中修改多开设置：

```toml
[multi_launch_settings]
enabled = true
base_port = 8000          # 基础端口
port_offset = 10          # 端口偏移量
auto_port_assignment = true  # 自动分配端口
```

## 支持的配置文件格式

### TOML 格式
```toml
[bot]
port = 8000
listen_port = 8001
```

### JSON 格式
```json
{
  "port": 8000,
  "listen_port": 8001
}
```

### YAML 格式
```yaml
port: 8000
listen_port: 8001
```

## 常见问题

### Q: 为什么启动失败？
A: 可能原因：
1. 选择的配置不足2个（多开需要至少2个配置）
2. 配置信息不完整（Bot路径为空）
3. 没有可用的端口（端口范围已满）

### Q: 如何停止多开的实例？
A: 
1. 在主菜单选择 `[G]` 查看运行状态
2. 使用 `stop <PID>` 命令停止指定实例
3. 使用 `stopall` 停止所有实例

### Q: 端口是否会冲突？
A: 不会。系统会：
1. 检测已使用的端口
2. 为每个实例分配不同的端口
3. 自动修改配置文件

### Q: 是否支持不同Bot类型的多开？
A: 支持。系统能够同时启动MaiBot和MoFox_bot的混合组合。

## 性能建议

- **CPU**: 建议每个实例占用10-20%的CPU，所以4-8个实例比较合理
- **内存**: 每个实例约占用300-500MB，建议总内存不低于4GB
- **磁盘**: 建议为每个实例预留1-2GB的存储空间

## 故障排查

### 查看日志
日志文件位置: `logs/` 目录

### 常见错误信息

| 错误信息 | 原因 | 解决方案 |
|--------|------|--------|
| 无法在范围中找到可用端口 | 端口已满 | 关闭一些运行中的服务或修改端口范围 |
| 配置文件不存在 | Bot路径错误 | 检查配置中的Bot路径是否正确 |
| 端口替换失败 | 配置格式错误 | 检查bot_config文件是否为有效格式 |

## 进阶用法

### 批量注册实例

在代码中使用 `multi_launch_manager`：

```python
from src.modules.multi_launch import multi_launch_manager

# 注册实例
multi_launch_manager.register_instance(
    instance_name="bot_01",
    bot_path="/path/to/bot",
    config_name="config_01",
    base_port=8000
)

# 准备实例环境
multi_launch_manager.prepare_instance_environment("bot_01")

# 获取实例信息
instance_info = multi_launch_manager.get_instance_info("bot_01")
```

### 自定义端口分配

```python
from src.modules.multi_launch import port_manager

# 获取可用端口
port = port_manager.get_available_port(
    preferred_port=8080,
    offset=0
)

# 获取多个端口
ports = port_manager.get_ports_for_instances(count=3, base_port=8000)
```

## 更新日志

### V4.1.0 (当前版本)
- ✅ 实现自动端口分配
- ✅ 支持多配置同时启动
- ✅ 自动修改配置文件端口
- ✅ 完整的端口冲突检测
- ✅ 支持多种配置文件格式

## 反馈与建议

如有问题或建议，请提交到：
- GitHub Issues: https://github.com/MaiCore-Start/MaiCore-Start/issues
- QQ群: 1025509724
