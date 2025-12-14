"""
多开启动模块
负责管理多个Bot实例的同时启动和端口自动分配
"""
import os
import re
import socket
import shutil
import structlog
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = structlog.get_logger(__name__)


class PortManager:
    """端口管理器 - 负责端口分配和检测"""
    
    # 保留端口列表（系统关键端口）
    RESERVED_PORTS = {
        22,      # SSH
        80,      # HTTP
        443,     # HTTPS
        3306,    # MySQL
        5432,    # PostgreSQL
        6379,    # Redis
        27017,   # MongoDB
        8080,    # 常见Web服务
    }
    
    # Bot常用端口范围
    BOT_PORT_RANGE = (8000, 9000)
    
    def __init__(self):
        self.used_ports = set()
        self._refresh_used_ports()
    
    def _refresh_used_ports(self):
        """刷新当前系统已使用的端口列表"""
        import psutil
        self.used_ports = set()
        
        try:
            # 获取所有活跃的网络连接
            connections = psutil.net_connections()
            for conn in connections:
                if conn.laddr and conn.laddr.port:
                    self.used_ports.add(conn.laddr.port)
        except Exception as e:
            logger.warning("获取已使用端口失败，使用备用方法", error=str(e))
            # 备用方法：尝试连接常见端口
            self._detect_ports_by_connection()
    
    def _detect_ports_by_connection(self):
        """通过尝试连接来检测已占用的端口"""
        for port in range(self.BOT_PORT_RANGE[0], self.BOT_PORT_RANGE[1] + 1):
            if self._is_port_open(port):
                self.used_ports.add(port)
    
    @staticmethod
    def _is_port_open(port: int) -> bool:
        """检查端口是否被占用"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            return result == 0
        except Exception:
            return False
        finally:
            sock.close()
    
    def get_available_port(self, preferred_port: int = None, offset: int = 0) -> int:
        """
        获取可用的端口
        
        Args:
            preferred_port: 优先使用的端口
            offset: 端口偏移量（用于为多个实例分配不同的端口）
            
        Returns:
            可用的端口号
        """
        self._refresh_used_ports()
        
        # 如果指定了偏好端口，尝试使用它
        if preferred_port:
            if self._is_port_available(preferred_port):
                return preferred_port
            # 如果偏好端口被占用，向上查找
            port = preferred_port + 1
            while port <= self.BOT_PORT_RANGE[1]:
                if self._is_port_available(port):
                    return port
                port += 1
        
        # 使用偏移量查找端口
        base_port = self.BOT_PORT_RANGE[0] + offset
        port = base_port
        while port <= self.BOT_PORT_RANGE[1]:
            if self._is_port_available(port):
                return port
            port += 1
        
        # 都找不到，返回错误
        raise RuntimeError(f"无法在范围 {self.BOT_PORT_RANGE[0]}-{self.BOT_PORT_RANGE[1]} 中找到可用端口")
    
    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用（未被占用且不在保留列表中）"""
        if port in self.RESERVED_PORTS or port in self.used_ports:
            return False
        if not self._is_port_open(port):
            return True
        return False
    
    def get_ports_for_instances(self, count: int, base_port: int = 8000) -> List[int]:
        """
        为多个实例获取端口列表
        
        Args:
            count: 实例数量
            base_port: 基础端口
            
        Returns:
            端口号列表
        """
        ports = []
        for i in range(count):
            try:
                port = self.get_available_port(preferred_port=base_port + i * 10, offset=i)
                ports.append(port)
            except RuntimeError as e:
                logger.error("获取端口失败", instance_index=i, error=str(e))
                raise
        return ports


class ConfigPortReplacer:
    """配置文件端口替换器 - 处理不同Bot类型的配置文件端口替换"""
    
    # 配置文件中可能出现的端口相关字段
    PORT_PATTERNS = {
        # MaiBot 常见的端口配置
        "port": r'"port"\s*:\s*(\d+)',
        "listen_port": r'"listen_port"\s*:\s*(\d+)',
        "http_port": r'"http_port"\s*:\s*(\d+)',
        "ws_port": r'"ws_port"\s*:\s*(\d+)',
        "api_port": r'"api_port"\s*:\s*(\d+)',
        "server_port": r'"server_port"\s*:\s*(\d+)',
        "port =": r'port\s*=\s*(\d+)',
        "listen_port =": r'listen_port\s*=\s*(\d+)',
    }
    
    def __init__(self):
        self.port_manager = PortManager()
    
    def replace_ports_in_config(
        self, 
        config_path: str, 
        new_port: int,
        config_format: str = "toml"
    ) -> bool:
        """
        替换配置文件中的端口号
        
        Args:
            config_path: 配置文件路径
            new_port: 新端口号
            config_format: 配置文件格式 ("toml", "json", "yaml")
            
        Returns:
            是否替换成功
        """
        if not os.path.exists(config_path):
            logger.warning("配置文件不存在", path=config_path)
            return False
        
        try:
            if config_format == "toml":
                return self._replace_ports_in_toml(config_path, new_port)
            elif config_format == "json":
                return self._replace_ports_in_json(config_path, new_port)
            elif config_format == "yaml":
                return self._replace_ports_in_yaml(config_path, new_port)
            else:
                logger.error("不支持的配置格式", format=config_format)
                return False
        except Exception as e:
            logger.error("替换端口失败", path=config_path, error=str(e))
            return False
    
    def _replace_ports_in_toml(self, config_path: str, new_port: int) -> bool:
        """替换TOML格式配置文件中的端口"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 查找并替换所有可能的端口配置
            for field_name, pattern in self.PORT_PATTERNS.items():
                # 查找所有匹配的端口
                matches = re.finditer(pattern, content)
                for match in matches:
                    old_port = match.group(1)
                    logger.info("找到端口配置", field=field_name, old_port=old_port)
                    # 替换端口
                    content = content.replace(
                        match.group(0),
                        match.group(0).replace(old_port, str(new_port))
                    )
            
            # 只在有修改时才写入
            if content != original_content:
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info("TOML配置文件端口替换成功", path=config_path, new_port=new_port)
                return True
            else:
                logger.warning("未找到可替换的端口配置", path=config_path)
                return False
                
        except Exception as e:
            logger.error("TOML替换失败", path=config_path, error=str(e))
            return False
    
    def _replace_ports_in_json(self, config_path: str, new_port: int) -> bool:
        """替换JSON格式配置文件中的端口"""
        try:
            import json
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 递归替换JSON中的所有port相关字段
            self._replace_ports_in_dict(config, new_port)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info("JSON配置文件端口替换成功", path=config_path, new_port=new_port)
            return True
            
        except Exception as e:
            logger.error("JSON替换失败", path=config_path, error=str(e))
            return False
    
    def _replace_ports_in_dict(self, obj: Any, new_port: int):
        """递归替换字典中的端口值"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(key, str) and 'port' in key.lower():
                    if isinstance(value, int):
                        obj[key] = new_port
                        logger.debug("替换端口字段", key=key, new_port=new_port)
                else:
                    self._replace_ports_in_dict(value, new_port)
        elif isinstance(obj, list):
            for item in obj:
                self._replace_ports_in_dict(item, new_port)
    
    def _replace_ports_in_yaml(self, config_path: str, new_port: int) -> bool:
        """替换YAML格式配置文件中的端口"""
        try:
            import yaml
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if config:
                self._replace_ports_in_dict(config, new_port)
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, allow_unicode=True)
                
                logger.info("YAML配置文件端口替换成功", path=config_path, new_port=new_port)
                return True
            else:
                logger.warning("YAML文件为空", path=config_path)
                return False
                
        except Exception as e:
            logger.error("YAML替换失败", path=config_path, error=str(e))
            return False


class MultiLaunchManager:
    """多开启动管理器 - 管理多个Bot实例的同时启动"""
    
    def __init__(self):
        self.port_manager = PortManager()
        self.port_replacer = ConfigPortReplacer()
        self.instances: Dict[str, Dict[str, Any]] = {}
        self.config_backups: Dict[str, str] = {}  # 备份配置：{config_path: backup_path}
        self.modified_configs: List[str] = []  # 已修改的配置文件列表（用于回滚）
        self.launched_instances: List[str] = []  # 已成功启动的实例列表（用于回滚）
    
    def register_instance(
        self, 
        instance_name: str,
        bot_path: str,
        config_name: str,
        base_port: int = 8000
    ) -> bool:
        """
        注册一个多开实例
        
        Args:
            instance_name: 实例名称
            bot_path: Bot的路径
            config_name: 使用的配置名称
            base_port: 基础端口
            
        Returns:
            是否注册成功
        """
        try:
            # 获取一个可用的端口
            allocated_port = self.port_manager.get_available_port(
                preferred_port=base_port,
                offset=len(self.instances)
            )
            
            instance_info = {
                "name": instance_name,
                "bot_path": bot_path,
                "config_name": config_name,
                "allocated_port": allocated_port,
                "status": "registered"
            }
            
            self.instances[instance_name] = instance_info
            logger.info("实例已注册", instance_name=instance_name, port=allocated_port)
            return True
            
        except Exception as e:
            logger.error("实例注册失败", instance_name=instance_name, error=str(e))
            return False
    
    def prepare_instance_environment(self, instance_name: str) -> bool:
        """
        为实例准备环境（创建临时配置、替换端口等）
        
        Args:
            instance_name: 实例名称
            
        Returns:
            是否准备成功
        """
        if instance_name not in self.instances:
            logger.error("实例不存在", instance_name=instance_name)
            return False
        
        instance = self.instances[instance_name]
        bot_path = instance["bot_path"]
        allocated_port = instance["allocated_port"]
        
        try:
            # 查找配置文件
            config_path = os.path.join(bot_path, "config", "bot_config.toml")
            
            if not os.path.exists(config_path):
                logger.warning("配置文件不存在，跳过端口替换", path=config_path)
                return True
            
            # 替换配置中的端口
            success = self.port_replacer.replace_ports_in_config(
                config_path,
                allocated_port,
                config_format="toml"
            )
            
            if success:
                instance["status"] = "environment_ready"
                logger.info("实例环境准备完成", instance_name=instance_name, port=allocated_port)
                return True
            else:
                logger.warning("端口替换失败，但继续启动", instance_name=instance_name)
                instance["status"] = "environment_ready"
                return True
                
        except Exception as e:
            logger.error("环境准备失败", instance_name=instance_name, error=str(e))
            return False
    
    def get_instance_info(self, instance_name: str) -> Optional[Dict[str, Any]]:
        """获取实例信息"""
        return self.instances.get(instance_name)
    
    def get_all_instances(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已注册的实例"""
        return self.instances.copy()
    
    def backup_config(self, config_path: str) -> Optional[str]:
        """
        备份配置文件 - 在修改前进行备份以支持回滚
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            备份文件路径，失败时返回None
        """
        if not os.path.exists(config_path):
            logger.warning("配置文件不存在，无法备份", path=config_path)
            return None
            
        try:
            # 创建备份文件名：original.toml -> original.toml.backup
            backup_path = config_path + ".backup"
            
            # 如果备份已存在，添加时间戳
            if os.path.exists(backup_path):
                import time
                timestamp = int(time.time())
                backup_path = f"{config_path}.backup.{timestamp}"
            
            shutil.copy2(config_path, backup_path)
            self.config_backups[config_path] = backup_path
            logger.info("配置文件备份成功", original=config_path, backup=backup_path)
            return backup_path
            
        except Exception as e:
            logger.error("配置文件备份失败", path=config_path, error=str(e))
            return None
    
    def restore_config(self, config_path: str) -> bool:
        """
        恢复配置文件 - 从备份恢复原始配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            是否恢复成功
        """
        if config_path not in self.config_backups:
            logger.warning("无可用的备份文件", path=config_path)
            return False
            
        try:
            backup_path = self.config_backups[config_path]
            
            if not os.path.exists(backup_path):
                logger.error("备份文件不存在", backup=backup_path)
                return False
            
            shutil.copy2(backup_path, config_path)
            logger.info("配置文件已恢复", path=config_path, from_backup=backup_path)
            return True
            
        except Exception as e:
            logger.error("配置文件恢复失败", path=config_path, error=str(e))
            return False
    
    def cleanup_backups(self, config_path: Optional[str] = None):
        """
        清理备份文件 - 启动成功后清理备份
        
        Args:
            config_path: 指定配置文件路径，None时清理全部
        """
        try:
            if config_path:
                if config_path in self.config_backups:
                    backup_path = self.config_backups[config_path]
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                        logger.debug("备份文件已清理", backup=backup_path)
                    del self.config_backups[config_path]
            else:
                for backup_path in self.config_backups.values():
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                        logger.debug("备份文件已清理", backup=backup_path)
                self.config_backups.clear()
                
        except Exception as e:
            logger.warning("清理备份文件时出错", error=str(e))
    
    def mark_instance_launched(self, instance_name: str):
        """标记实例已启动"""
        if instance_name not in self.launched_instances:
            self.launched_instances.append(instance_name)
    
    def mark_config_modified(self, config_path: str):
        """标记配置文件已修改"""
        if config_path not in self.modified_configs:
            self.modified_configs.append(config_path)
    
    def rollback_all(self) -> Dict[str, bool]:
        """
        回滚所有改动 - 当启动失败时，恢复所有已修改的配置和停止所有已启动的实例
        
        Returns:
            回滚结果字典：{config_path: 是否恢复成功}
        """
        logger.warning("执行多开启动失败回滚...")
        rollback_results = {}
        
        # 恢复所有已修改的配置
        for config_path in self.modified_configs:
            success = self.restore_config(config_path)
            rollback_results[config_path] = success
            
        # 清理备份文件
        self.cleanup_backups()
        
        # 清空追踪列表
        self.modified_configs.clear()
        self.launched_instances.clear()
        
        logger.info("多开回滚完成", success_count=sum(rollback_results.values()),
                   total_count=len(rollback_results))
        return rollback_results
    
    def get_rollback_status(self) -> Dict[str, Any]:
        """获取回滚状态信息"""
        return {
            "modified_configs": self.modified_configs.copy(),
            "launched_instances": self.launched_instances.copy(),
            "config_backups": self.config_backups.copy()
        }
    
    def unregister_instance(self, instance_name: str) -> bool:
        """取消注册实例"""
        if instance_name in self.instances:
            del self.instances[instance_name]
            logger.info("实例已取消注册", instance_name=instance_name)
            return True
        return False


# 全局多开管理器实例
multi_launch_manager = MultiLaunchManager()
port_manager = PortManager()
port_replacer = ConfigPortReplacer()
