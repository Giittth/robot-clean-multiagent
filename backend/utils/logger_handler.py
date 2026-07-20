"""
    日志工具
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from backend.config import settings, BASE_DIR


# 创建日志处理器
def create_log_handler():
    # 定义日志收集器
    logger = logging.getLogger("agents")
    logger.setLevel(logging.DEBUG)
    # 创建控制台处理器
    """%(asctime)s    →  时间（2025-12-29 12: 00:00）
    %(name)s       →  日志器名字
    %(levelname)s  → 日志级别（INFO / WARNING / ERROR）
    %(message)s    → 需要打印的日志内容
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(console_handler)

    # 创建保存路径
    base_path = BASE_DIR if isinstance(BASE_DIR, Path) else Path(BASE_DIR)
    log_dir = base_path / settings.log_save_file
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"

    # 创建文件处理器
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)
    return  logger

logger = create_log_handler()



if __name__ == "__main__":
    logger.error("hello world")