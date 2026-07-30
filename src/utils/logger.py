"""
结构化日志模块
- 带时间戳的格式化输出
- GitHub Actions 友好 (::notice / ::warning / ::error 命令)
"""

import sys
import time
from typing import Literal

Level = Literal["debug", "info", "warn", "error"]


def log(level: Level, message: str, **kwargs):
    """打印结构化日志"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    level_upper = level.upper()
    extra = f" {kwargs}" if kwargs else ""

    # GitHub Actions 工作流命令
    if level == "error":
        print(f"::error::{message}{extra}", file=sys.stderr)
    elif level == "warn":
        print(f"::warning::{message}{extra}")

    print(f"[{ts}] [{level_upper}] {message}{extra}", file=sys.stderr)
    sys.stderr.flush()


def info(msg: str, **kwargs):
    log("info", msg, **kwargs)


def warn(msg: str, **kwargs):
    log("warn", msg, **kwargs)


def error(msg: str, **kwargs):
    log("error", msg, **kwargs)


def debug(msg: str, **kwargs):
    log("debug", msg, **kwargs)
