"""
静态站点生成器
- 从 SQLite 导出 data.json（含职位表）
- 可选：Jinja2 渲染 HTML
"""

import json
from pathlib import Path
from datetime import datetime

from src.database import list_notices, get_stats, get_positions

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


def export_json(output_path: Path | None = None):
    """将公告数据 + 职位表导出为 JSON"""
    notices = list_notices(limit=500)

    # 为每条公告加载职位信息
    enriched = []
    for n in notices:
        item = dict(n)
        if item.get("position_count", 0) > 0:
            item["positions"] = get_positions(item["id"])
        else:
            item["positions"] = []
        enriched.append(item)

    stats = get_stats()

    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "notices": enriched,
    }

    output_path = output_path or (WEB_DIR / "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(notices)
