#!/usr/bin/env python3
"""
公务员考试公告跟踪工具 — 主入口
- 由 GitHub Actions 定时触发
- 也支持本地手动运行: python -m src.main
"""

import sys
import time
import yaml
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.database import (
    init_db, upsert_source, get_active_sources, get_existing_hashes,
    insert_notice, insert_positions, update_source_last_crawl, notice_exists,
)
from src.dedup import compute_dedup_key
from src.extractor import extract_fields, extract_positions, extract_attachments
from src.notifier import notify_new_notice
from src.render import export_json
from src.utils.logger import info, warn, error
from src.utils.http import HttpClient

# ─── 适配器注册表 ───
from src.adapters.base import GenericAdapter
from src.adapters.guokao import GuoKaoAdapter
from src.adapters.fenbi import FenbiAdapter

ADAPTER_MAP: dict[str, Any] = {
    "generic": GenericAdapter,
    "guokao": GuoKaoAdapter,
    "fenbi": FenbiAdapter,
}


def load_sources() -> list[dict]:
    """从 YAML 配置文件加载数据源"""
    config_path = ROOT_DIR / "config" / "sources.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def init_sources_in_db(sources: list[dict]):
    """将 YAML 中的源同步到 SQLite"""
    for src in sources:
        upsert_source({
            "province": src["province"],
            "exam_type": src["exam_type"],
            "name": src["name"],
            "url": src["url"],
            "parser_type": src.get("parser_type", "html"),
            "crawl_interval": src.get("crawl_interval", 3600),
            "config": src.get("config", {}),
        })


def get_adapter(source: dict):
    """根据 source 的 adapter 配置获取适配器实例"""
    adapter_name = source.get("config", {}).get("adapter", "")
    adapter_cls = ADAPTER_MAP.get(adapter_name)
    if adapter_cls is None:
        error(f"未知适配器: {adapter_name}，来源: {source['name']}")
        return None
    return adapter_cls(source)


def crawl_one_source(source: dict) -> dict:
    """抓取单个数据源，返回结果统计"""
    adapter = get_adapter(source)
    if adapter is None:
        return {"source_id": source["id"], "new": 0, "errors": ["无适配器"]}

    t0 = time.time()
    existing_hashes = get_existing_hashes()
    new_count = 0
    errors: list[str] = []

    try:
        raw_list = adapter.fetch_notice_list()
        info(f"[{source['province']}] {source['name']} — 列表 {len(raw_list)} 条")
    except Exception as e:
        error(f"[{source['province']}] {source['name']} 列表抓取失败: {e}")
        duration_ms = int((time.time() - t0) * 1000)
        update_source_last_crawl(source["id"], "failed", 0, str(e), duration_ms)
        return {"source_id": source["id"], "new": 0, "errors": [str(e)]}

    for raw in raw_list:
        dedup_key = compute_dedup_key(raw.url, raw.title)
        if dedup_key in existing_hashes:
            continue

        # 去重检查
        if notice_exists(dedup_key):
            existing_hashes.add(dedup_key)
            continue

        # 抓取详情
        try:
            detail = adapter.fetch_notice_detail(raw.url)
        except Exception as e:
            warn(f"[{source['province']}] 详情抓取失败: {raw.url} — {e}")
            errors.append(f"详情失败: {raw.url}")
            continue

        # 字段提取（传入发布日期用于年份推断）
        content = detail.get("content", "")
        detail_html = detail.get("html", "")  # 适配器可返回原始 HTML
        pub_date = detail.get("publish_date") or raw.publish_date
        extracted = extract_fields(content, pub_date)

        # 附件和职位表
        attachments = detail.get("attachment_urls", [])
        positions = []
        if detail_html:
            attachments = extract_attachments(detail_html, raw.url)
            positions = extract_positions(detail_html)

        # 组装通知记录
        notice = {
            "source_url": raw.url,
            "source_hash": dedup_key,
            "province": source["province"],
            "exam_type": source["exam_type"],
            "title": raw.title,
            "publish_dept": detail.get("publish_dept"),
            "publish_date": detail.get("publish_date") or raw.publish_date,
            "content_summary": content[:500] if content else None,
            "apply_start": extracted.get("apply_start"),
            "apply_end": extracted.get("apply_end"),
            "written_exam": extracted.get("written_exam"),
            "interview_start": extracted.get("interview_start"),
            "recruit_count": extracted.get("recruit_count"),
            "raw_fields": extracted,
            "tags": [],
            "attachment_urls": attachments,
            "position_count": len(positions),
        }

        notice_id = insert_notice(notice)
        if notice_id:
            new_count += 1
            existing_hashes.add(dedup_key)

            # 存储职位表
            if positions:
                insert_positions(notice_id, positions)

            # 推送通知
            channels = notify_new_notice(notice)
            if channels:
                info(f"  ✅ 新公告 + 已推送 {channels}: {raw.title[:50]}...")
            else:
                info(f"  ✅ 新公告 ({len(positions)}岗位): {raw.title[:50]}...")

    duration_ms = int((time.time() - t0) * 1000)
    status = "success" if not errors else "partial"
    update_source_last_crawl(source["id"], status, new_count, "; ".join(errors[:3]), duration_ms)

    return {"source_id": source["id"], "new": new_count, "errors": errors}


def main():
    """主流程"""
    info("=" * 50)
    info("公务员考试公告跟踪 — 开始抓取")

    # 初始化
    init_db()
    sources_config = load_sources()
    init_sources_in_db(sources_config)

    # 获取数据库中的活跃源（此时已有 id）
    active_sources = get_active_sources()
    info(f"数据源: {len(active_sources)} 个")

    # 逐个抓取
    total_new = 0
    for src in active_sources:
        result = crawl_one_source(src)
        total_new += result["new"]

    # 导出静态站点
    num_notices = export_json()
    info(f"JSON 导出: {num_notices} 条公告")
    # render_html()  # HTML 为纯静态，不需渲染

    info(f"完成! 本次新增 {total_new} 条公告，数据库共 {num_notices} 条")
    info("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
