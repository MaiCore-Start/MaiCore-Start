# 部署系统模块化重构说明

## 概述
本次重构将原有的单一臃肿的 `deployment.py` 文件拆分为模块化的部署核心系统，使代码结构更清晰、更易维护和扩展。

## 新的文件结构

```
src/modules/
├── deployment.py                    # 主部署管理器（重构后）
├── deployment_old.py                # 原始部署文件（备份）
└── deployment_core/                 # 新增：部署核心模块
    ├── __init__.py                  # 模块导出
    ├── base_deployer.py             # 基础部署器类
    ├── version_manager.py           # 版本管理器
    ├── maibot_deployer.py           # MaiBot部署器
    ├── mofox_deployer.py            # MoFox_bot部署器
    └── napcat_deployer.py           # NapCat部署器
```

## 各模块职责

### 1. `base_deployer.py` - 基础部署器
提供所有部署器共用的基础功能：
- ✅ 虚拟环境创建 (`create_virtual_environment`)
- ✅ 依赖安装 (`install_dependencies_in_venv`)
- ✅ 网络连接检查 (`check_network_connection`)
- ✅ 文件下载 (`download_file`)
- ✅ 归档文件解压 (`extract_archive`)
- ✅ 虚拟环境Python路径获取 (`get_venv_python_path`)

### 2. `version_manager.py` - 版本管理器
负责从GitHub获取和管理版本信息：
- ✅ GitHub releases获取 (`get_github_releases`)
- ✅ GitHub分支获取 (`get_github_branches`)
- ✅ 版本列表获取和缓存 (`get_versions`)
- ✅ 版本选择菜单 (`show_version_menu`)
- ✅ 更新日志显示 (`show_changelog_menu`, `show_version_changelog`)
- ✅ 离线模式支持 (`set_offline_mode`)

**特性：**
- 5分钟缓存机制，减少API调用
- 支持离线模式，使用默认版本列表
- 支持releases和branches的统一管理

### 3. `maibot_deployer.py` - MaiBot部署器
处理MaiBot特定的部署逻辑：
- ✅ MaiBot安装 (`install_bot`)
- ✅ 适配器安装和版本检测 (`install_adapter`)
- ✅ 配置文件设置 (`setup_config_files`)
  - 支持 >= 0.10.0 版本的新配置结构
  - 支持旧版本的配置结构
  - 自动识别需要的配置文件模板

**版本兼容性：**
- ✅ 0.5.x及以下：无需适配器
- ✅ 0.6.x：使用0.2.3版本适配器
- ✅ 0.7.x-0.8.x：使用0.4.2版本适配器
- ✅ 0.10.0+：新配置文件结构（bot_config.toml + model_config.toml + plugin_config.toml）
- ✅ main/dev分支：使用对应分支的适配器

### 4. `mofox_deployer.py` - MoFox_bot部署器
处理MoFox_bot特定的部署逻辑：
- ✅ MoFox_bot安装 (`install_bot`)
- ✅ 配置文件设置 (`setup_config_files`)
  - 支持内置适配器
  - 支持外置适配器（可选）
  - 自动配置model_config.toml

**特性：**
- 默认使用内置适配器
- 支持可选的外置适配器安装
- 提供MoFox_bot专用配置提示

### 5. `napcat_deployer.py` - NapCat部署器
处理NapCat的下载、安装和配置：
- ✅ 版本列表获取 (`get_napcat_versions`)
- ✅ 版本选择 (`select_napcat_version`)
- ✅ NapCat下载和解压 (`download_napcat`)
- ✅ 安装程序运行 (`run_napcat_installer`)
- ✅ 已安装NapCat检测 (`find_installed_napcat`)
- ✅ 安装完成等待和检测 (`_wait_for_napcat_installation`)

**特性：**
- 支持Shell基础版、Framework一键包、Shell一键包
- 自动检测NapCat.Shell和NapCat.Framework版本
- 3次路径检测机制，确保安装成功
- 支持默认版本回退

### 6. `deployment.py` - 主部署管理器（重构后）
协调各个部署器完成部署任务：
- ✅ 网络检查
- ✅ 配置获取（Bot类型、版本、组件选择等）
- ✅ 部署确认
- ✅ 部署步骤协调：
  1. Bot主体安装
  2. 适配器安装（如需要）
  3. NapCat安装（如需要）
  4. WebUI安装（如需要）
  5. Python环境设置
  6. 配置文件设置
  7. 实例配置保存
- ✅ 部署后信息显示

## 引用关系

```
deployment.py
├── MaiBotDeployer (from deployment_core)
│   ├── BaseDeployer
│   └── VersionManager
├── MoFoxBotDeployer (from deployment_core)
│   ├── BaseDeployer
│   └── VersionManager
├── NapCatDeployer (from deployment_core)
│   └── BaseDeployer
├── mongodb_downloader (from component_download)
└── webui_installer
```

## 重要改进

### 1. 模块化设计
- 每个Bot类型有独立的部署器
- 共用功能抽取到基础类
- 版本管理独立模块化

### 2. 代码复用
- 基础部署器提供通用方法
- 避免重复代码
- 易于维护和扩展

### 3. 扩展性
- 新增Bot类型只需：
  1. 创建新的部署器类继承BaseDeployer
  2. 实现`install_bot`和`setup_config_files`方法
  3. 在deployment.py中添加调用逻辑

### 4. 易维护性
- 单一职责原则
- 清晰的文件组织
- 完整的文档注释

### 5. 引用已有模块
- MongoDB部署引用 `component_download/mongodb_downloader.py`
- NapCat可以独立实现，也可引用 `component_download/napcat_downloader.py`
- 保持了与现有模块的兼容性

## 使用示例

```python
# 导入部署管理器
from src.modules.deployment import deployment_manager

# 部署新实例
deployment_manager.deploy_instance()

# 各个部署器也可以独立使用
from src.modules.deployment_core import MaiBotDeployer, NapCatDeployer

maibot_deployer = MaiBotDeployer()
napcat_deployer = NapCatDeployer()

# 获取MaiBot版本列表
versions = maibot_deployer.version_manager.get_versions()

# 获取NapCat版本列表
napcat_versions = napcat_deployer.get_napcat_versions()
```

## 测试建议

### 1. 功能测试
- [ ] MaiBot部署（各个版本）
- [ ] MoFox_bot部署
- [ ] NapCat安装和检测
- [ ] 适配器版本匹配
- [ ] 配置文件生成

### 2. 边界测试
- [ ] 离线模式
- [ ] 网络失败重试
- [ ] 版本缓存
- [ ] 路径验证

### 3. 兼容性测试
- [ ] 旧版本MaiBot (< 0.6.0)
- [ ] 新版本MaiBot (>= 0.10.0)
- [ ] MoFox_bot各版本
- [ ] 不同分支部署

## 注意事项

1. **原始文件备份**：原 `deployment.py` 已备份为 `deployment_old.py`
2. **向后兼容**：新的deployment_manager保持了与原有代码相同的接口
3. **MongoDB安装**：使用 `component_download/mongodb_downloader.py`
4. **配置文件**：严格遵循版本检测逻辑，确保配置文件正确生成
5. **用户变量**：所有用户提供的变量（QQ、路径等）都正确传递和使用

## 未来扩展方向

1. **更多Bot类型**：轻松添加新的Bot部署器
2. **更新和删除功能**：完善实例管理功能
3. **插件系统**：支持部署器插件化
4. **配置迁移**：支持配置自动迁移和升级
5. **批量部署**：支持一次部署多个实例

## 总结

本次重构显著提升了代码质量和可维护性，为未来功能扩展奠定了良好基础。模块化的设计使得每个部分职责清晰，易于测试和调试。
