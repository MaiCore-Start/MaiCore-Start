"""
多开失败回滚和并行启动测试脚本
测试新增的并行启动和自动回滚功能
"""
import sys
import os
import shutil
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.multi_launch import MultiLaunchManager, PortManager
import structlog

logger = structlog.get_logger(__name__)

def setup_test_environment():
    """创建测试环境"""
    test_dir = Path(__file__).parent / "test_rollback_env"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    # 创建测试实例目录
    for i in range(1, 4):
        instance_dir = test_dir / f"instance_{i}"
        instance_dir.mkdir()
        
        config_dir = instance_dir / "config"
        config_dir.mkdir()
        
        config_file = config_dir / "bot_config.toml"
        config_file.write_text(f"""[bot]
port = 8000
name = "Instance {i}"

[server]
listen_port = 8000
host = "0.0.0.0"

[database]
mongo_port = 27017
""")
    
    return test_dir

def test_port_manager():
    """测试端口管理器"""
    print("\n" + "="*60)
    print("测试1: PortManager - 端口管理")
    print("="*60)
    
    pm = PortManager()
    print("✓ 已初始化 PortManager")
    
    # 刷新端口列表
    pm._refresh_used_ports()
    print(f"✓ 已刷新端口列表，当前已使用端口数: {len(pm.used_ports)}")
    
    # 分配端口
    port1 = pm.allocate_port(base_port=8000)
    print(f"✓ 分配端口 1: {port1}")
    
    port2 = pm.allocate_port(base_port=8000)
    print(f"✓ 分配端口 2: {port2}")
    
    port3 = pm.allocate_port(base_port=8000)
    print(f"✓ 分配端口 3: {port3}")
    
    # 验证端口不重复
    ports = [port1, port2, port3]
    if len(ports) == len(set(ports)):
        print(f"✅ 所有端口都是唯一的: {ports}")
    else:
        print(f"❌ 端口重复: {ports}")

def test_config_backup_restore():
    """测试配置备份和恢复"""
    print("\n" + "="*60)
    print("测试2: 配置备份和恢复")
    print("="*60)
    
    test_dir = setup_test_environment()
    mlm = MultiLaunchManager()
    
    config_file = test_dir / "instance_1" / "config" / "bot_config.toml"
    print(f"✓ 测试配置文件: {config_file}")
    
    # 读取原始内容
    original_content = config_file.read_text()
    print(f"✓ 原始配置内容:\n{original_content[:100]}...")
    
    # 备份配置
    backup_path = mlm.backup_config(str(config_file))
    if backup_path and os.path.exists(backup_path):
        print(f"✅ 配置备份成功: {backup_path}")
        backup_content = open(backup_path).read()
        if backup_content == original_content:
            print("✅ 备份内容与原文件一致")
    else:
        print(f"❌ 配置备份失败")
    
    # 修改配置
    modified_content = original_content.replace("port = 8000", "port = 9000")
    config_file.write_text(modified_content)
    print("✓ 已修改配置文件内容")
    
    # 验证修改
    current = config_file.read_text()
    if "port = 9000" in current:
        print("✅ 配置已修改")
    
    # 恢复配置
    if mlm.restore_config(str(config_file)):
        print("✅ 配置恢复成功")
        restored = config_file.read_text()
        if restored == original_content:
            print("✅ 恢复后内容与原文件一致")
        else:
            print("❌ 恢复后内容不一致")
    else:
        print("❌ 配置恢复失败")
    
    # 清理备份
    mlm.cleanup_backups()
    if not os.path.exists(backup_path):
        print("✅ 备份文件已清理")
    else:
        print("❌ 备份文件清理失败")

def test_instance_registration():
    """测试实例注册"""
    print("\n" + "="*60)
    print("测试3: 实例注册和管理")
    print("="*60)
    
    test_dir = setup_test_environment()
    mlm = MultiLaunchManager()
    
    # 注册多个实例
    instance_names = []
    for i in range(1, 4):
        instance_name = f"test_instance_{i}"
        bot_path = str(test_dir / f"instance_{i}")
        
        success = mlm.register_instance(
            instance_name,
            bot_path,
            f"config_{i}",
            base_port=8000,
            offset=i
        )
        
        if success:
            print(f"✅ 实例 '{instance_name}' 注册成功")
            instance_names.append(instance_name)
        else:
            print(f"❌ 实例 '{instance_name}' 注册失败")
    
    # 验证所有实例已注册
    all_instances = mlm.get_all_instances()
    if len(all_instances) == 3:
        print(f"✅ 所有实例已注册，总数: {len(all_instances)}")
    
    # 显示实例信息
    for name, info in all_instances.items():
        print(f"  • {name}: 端口={info['allocated_port']}, 路径={info['bot_path']}")

def test_rollback_mechanism():
    """测试回滚机制"""
    print("\n" + "="*60)
    print("测试4: 回滚机制")
    print("="*60)
    
    test_dir = setup_test_environment()
    mlm = MultiLaunchManager()
    
    # 创建多个配置文件的修改情景
    config_files = []
    for i in range(1, 4):
        config_file = test_dir / f"instance_{i}" / "config" / "bot_config.toml"
        config_files.append(str(config_file))
        
        # 备份配置
        backup = mlm.backup_config(str(config_file))
        if backup:
            print(f"✓ 配置 {i} 已备份")
        
        # 标记为已修改
        mlm.mark_config_modified(str(config_file))
        
        # 模拟修改
        original = config_file.read_text()
        modified = original.replace("port = 8000", f"port = {8000+i*1000}")
        config_file.write_text(modified)
        print(f"✓ 配置 {i} 已修改 (端口变更)")
    
    # 检查回滚状态
    status = mlm.get_rollback_status()
    print(f"\n回滚状态:")
    print(f"  • 已修改配置数: {len(status['modified_configs'])}")
    print(f"  • 已备份配置数: {len(status['config_backups'])}")
    
    # 执行回滚
    print("\n执行回滚...")
    rollback_results = mlm.rollback_all()
    
    if rollback_results:
        success_count = sum(1 for v in rollback_results.values() if v)
        print(f"✅ 回滚完成: {success_count}/{len(rollback_results)} 个配置已恢复")
        
        # 验证恢复
        for i, config_file in enumerate(config_files, 1):
            content = open(config_file).read()
            if "port = 8000" in content:
                print(f"✅ 配置 {i} 已正确恢复")
            else:
                print(f"❌ 配置 {i} 恢复失败")

def test_parallel_launch_simulation():
    """模拟并行启动情景"""
    print("\n" + "="*60)
    print("测试5: 并行启动模拟")
    print("="*60)
    
    import threading
    
    results = {}
    lock = threading.Lock()
    
    def simulate_component_startup(instance_name: str, delay: float = 0.5):
        """模拟组件启动"""
        import time
        print(f"  [{instance_name}] 开始启动...")
        time.sleep(delay)
        
        success = instance_name != "instance_fail"  # 模拟其中一个失败
        
        with lock:
            results[instance_name] = success
        
        if success:
            print(f"  ✅ [{instance_name}] 启动成功")
        else:
            print(f"  ❌ [{instance_name}] 启动失败")
    
    print("🚀 开始并行启动模拟...")
    
    # 创建并启动线程
    threads = []
    for i in range(1, 4):
        name = f"instance_{i}" if i != 2 else "instance_fail"
        thread = threading.Thread(
            target=simulate_component_startup,
            args=(name, 0.3)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    print("\n启动结果汇总:")
    successful = [k for k, v in results.items() if v]
    failed = [k for k, v in results.items() if not v]
    
    print(f"✅ 成功: {len(successful)} 个")
    for name in successful:
        print(f"  • {name}")
    
    if failed:
        print(f"❌ 失败: {len(failed)} 个")
        for name in failed:
            print(f"  • {name}")

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("多开回滚和并行启动功能测试")
    print("="*60)
    
    try:
        test_port_manager()
        test_config_backup_restore()
        test_instance_registration()
        test_rollback_mechanism()
        test_parallel_launch_simulation()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
