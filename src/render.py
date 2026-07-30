"""
静态站点生成器
- 从 SQLite 导出 data.json
- 用 Jinja2 渲染 index.html
- 输出到 web/ 目录（GitHub Pages 部署目录）
"""

import json
from pathlib import Path
from datetime import datetime

from jinja2 import Template

from src.database import list_notices, get_stats

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
TEMPLATE_PATH = WEB_DIR / "index.html"


def export_json(output_path: Path | None = None):
    """将公告数据导出为 JSON"""
    notices = list_notices(limit=500)
    stats = get_stats()

    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "notices": notices,
    }

    output_path = output_path or (WEB_DIR / "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(notices)


def render_html():
    """用 Jinja2 渲染 index.html"""
    # 读模板
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_source = f.read()

    # 如果模板还没有 Jinja2 标记，说明是纯 HTML + JS 加载 data.json
    # 这种情况下不需要渲染
    if "{{" not in template_source and "{%" not in template_source:
        return

    # 如果模板含 Jinja2 变量，进行服务端渲染
    notices = list_notices(limit=200)
    # 按省份分组
    by_province: dict[str, list] = {}
    for n in notices:
        p = n.get("province", "未知")
        by_province.setdefault(p, []).append(n)

    template = Template(template_source)
    html = template.render(notices=notices, by_province=by_province, updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    with open(WEB_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)
