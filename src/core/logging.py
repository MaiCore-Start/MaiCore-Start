"""
日志配置模块
使用 structlog 提供结构化日志，支持控制台和JSONL文件输出。
"""
import sys
import os
import glob
import logging
import json
from functools import partial
from datetime import datetime, timedelta
import structlog
from rich.logging import RichHandler

# 从程序配置模块导入 p_config_manager
from .p_config import p_config_manager

LOG_DIR = "log"

# 创建一个模块级别的logger实例，供本模块内部函数使用
# 注意：在setup_logging完成前，它可能不会按预期工作
logger = structlog.get_logger(__name__)

# --- 动态级别控制 ---
_default_console_level = logging.WARNING

def set_console_log_level(level: str):
    """动态设置控制台日志级别"""
    try:
        level_val = getattr(logging, level.upper())
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(level_val)
                logger.debug(f"控制台日志级别已临时设置为 {level}")
                break
    except Exception as e:
        logger.error("设置控制台日志级别失败", error=str(e))

def reset_console_log_level():
    """将控制台日志级别恢复为默认值"""
    try:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(_default_console_level)
                logger.debug("控制台日志级别已恢复为默认")
                break
    except Exception as e:
        logger.error("恢复控制台日志级别失败", error=str(e))


def rotate_logs():
    """
    扫描日志目录并删除超过指定保留天数的旧日志文件。
    """
    try:
        # 从配置中获取日志保留天数，如果获取失败则默认为30天
        retention_days = p_config_manager.get("logging.log_rotation_days", 30)
        
        # 确保保留天数是有效的正整数
        if not isinstance(retention_days, int) or retention_days <= 0:
            retention_days = 30
            logger.warning(
                "无效的日志保留天数配置，将使用默认值30天",
                config_value=p_config_manager.get("logging.log_rotation_days")
            )

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # 检查日志目录是否存在
        if not os.path.isdir(LOG_DIR):
            return

        # 遍历目录中的所有 .jsonl 文件
        for log_file in glob.glob(os.path.join(LOG_DIR, "*.jsonl")):
            try:
                # 从文件名中提取日期部分 (e.g., "2025-10-07_14-24-31.jsonl")
                filename = os.path.basename(log_file)
                timestamp_str = filename.split('.')[0]
                log_date = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                
                # 如果日志文件早于截止日期，则删除它
                if log_date < cutoff_date:
                    os.remove(log_file)
                    logger.info("已删除旧日志文件", file=log_file)
            except (ValueError, IndexError) as e:
                # 如果文件名格式不正确，记录警告并跳过
                logger.warning(
                    "无法解析日志文件名，跳过轮转检查",
                    file=log_file,
                    error=str(e)
                )
            except Exception as e:
                # 捕获其他删除文件时可能发生的异常
                logger.error(
                    "删除旧日志文件失败",
                    file=log_file,
                    error=str(e)
                )
    except Exception as e:
        # 捕获在读取配置或执行轮转时发生的任何顶层异常
        logger.error("日志轮转失败", error=str(e))


def setup_logging(level: str = "INFO"):
    """
    设置结构化日志，支持同时输出到控制台和JSONL文件。
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    # 1. 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 2. 在配置日志系统前执行日志轮转
    # (此时日志系统尚未完全配置，因此轮转本身的日志可能不会被记录到文件中)
    rotate_logs()
    
    # 3. 创建本次运行的日志文件名
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = os.path.join(LOG_DIR, f"{timestamp}.jsonl")

    # 4. 配置structlog
    # structlog的处理器是按顺序执行的，最终结果交给logger处理
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"), # 使用ISO 8601格式时间戳
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # 这个处理器会把日志事件渲染成JSON字符串，用于文件输出
            # 使用 functools.partial 来确保中文字符被正确编码
            structlog.processors.JSONRenderer(serializer=partial(json.dumps, ensure_ascii=False)),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 5. 配置Python标准logging，作为structlog的输出端
    # 我们配置两个handler：一个用于控制台，一个用于文件
    
    # 控制台handler，使用RichHandler美化输出
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False
    )
    # 为控制台handler单独设置一个更易读的格式化器
    # rich会自动处理日志级别和时间，这里我们只需要消息本身
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    # 设置控制台只显示WARNING及以上级别的日志
    console_handler.setLevel(_default_console_level)

    # 文件handler，写入JSONL文件
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    # 文件handler的格式化器很简单，因为它接收的已经是JSON字符串了
    file_formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(file_formatter)

    # 获取根logger并配置
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers = [console_handler, file_handler]


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    获取一个已配置的结构化日志器实例。
    
    Args:
        name: 日志器名称 (通常是 __name__)
        
    Returns:
        一个绑定的structlog日志器实例
    """
    return structlog.get_logger(name)

# 在模块加载时自动初始化日志系统
setup_logging()
