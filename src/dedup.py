"""
去重模块
- 使用 URL + 标题的 SHA256 作为唯一标识
"""

import hashlib


def compute_dedup_key(url: str, title: str) -> str:
    """计算公告的去重哈希"""
    raw = f"{url.strip()}|{title.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
