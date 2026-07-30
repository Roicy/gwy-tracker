"""
SQLite 数据库模块
- 建表 (notices, sources, crawl_logs)
- CRUD 封装
- 纯标准库 sqlite3，无额外依赖
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "gwy_tracker.db"


def get_db_path() -> str:
    return str(DB_PATH)


def get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动创建 data 目录"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url      TEXT NOT NULL,
            source_hash     TEXT NOT NULL UNIQUE,
            province        TEXT NOT NULL,
            exam_type       TEXT NOT NULL,
            title           TEXT NOT NULL,
            publish_dept    TEXT,
            publish_date    TEXT,
            content_summary TEXT,
            apply_start     TEXT,
            apply_end       TEXT,
            written_exam    TEXT,
            interview_start TEXT,
            recruit_count   INTEGER,
            raw_fields      TEXT,
            tags            TEXT,
            first_seen_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            is_active       INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_notices_province ON notices(province);
        CREATE INDEX IF NOT EXISTS idx_notices_exam_type ON notices(exam_type);
        CREATE INDEX IF NOT EXISTS idx_notices_publish_date ON notices(publish_date);
        CREATE INDEX IF NOT EXISTS idx_notices_apply_end ON notices(apply_end);

        CREATE TABLE IF NOT EXISTS sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            province        TEXT NOT NULL,
            exam_type       TEXT NOT NULL,
            name            TEXT NOT NULL,
            url             TEXT NOT NULL,
            parser_type     TEXT NOT NULL DEFAULT 'html',
            crawl_interval  INTEGER NOT NULL DEFAULT 3600,
            is_active       INTEGER DEFAULT 1,
            last_crawl_at   TEXT,
            config          TEXT,
            UNIQUE(province, exam_type, name)
        );

        CREATE TABLE IF NOT EXISTS crawl_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       INTEGER NOT NULL,
            status          TEXT NOT NULL,
            new_notices     INTEGER DEFAULT 0,
            error_msg       TEXT,
            duration_ms     INTEGER,
            crawled_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        );
    """)
    conn.commit()
    conn.close()


# ─── Notice CRUD ────────────────────────────────────────────

def insert_notice(notice: dict) -> int | None:
    """插入公告，如果 source_hash 已存在则跳过。返回 id 或 None"""
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO notices (source_url, source_hash, province, exam_type,
                title, publish_dept, publish_date, content_summary,
                apply_start, apply_end, written_exam, interview_start,
                recruit_count, raw_fields, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            notice["source_url"],
            notice["source_hash"],
            notice.get("province", ""),
            notice.get("exam_type", ""),
            notice.get("title", ""),
            notice.get("publish_dept"),
            notice.get("publish_date"),
            notice.get("content_summary"),
            notice.get("apply_start"),
            notice.get("apply_end"),
            notice.get("written_exam"),
            notice.get("interview_start"),
            notice.get("recruit_count"),
            json.dumps(notice.get("raw_fields", {}), ensure_ascii=False),
            json.dumps(notice.get("tags", []), ensure_ascii=False),
        ))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        # source_hash 冲突，已存在
        return None
    finally:
        conn.close()


def notice_exists(source_hash: str) -> bool:
    """检查公告是否已存在"""
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM notices WHERE source_hash = ?", (source_hash,)
    ).fetchone()
    conn.close()
    return row is not None


def get_existing_hashes() -> set[str]:
    """获取所有已存储的 source_hash"""
    conn = get_conn()
    rows = conn.execute("SELECT source_hash FROM notices").fetchall()
    conn.close()
    return {r[0] for r in rows}


def list_notices(
    province: str | None = None,
    exam_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """查询公告列表"""
    conn = get_conn()
    sql = "SELECT * FROM notices WHERE is_active = 1"
    params: list[Any] = []

    if province:
        sql += " AND province = ?"
        params.append(province)
    if exam_type:
        sql += " AND exam_type = ?"
        params.append(exam_type)

    sql += " ORDER BY COALESCE(publish_date, first_seen_at) DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_stats() -> dict:
    """统计信息"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM notices WHERE is_active = 1").fetchone()[0]
    by_type = conn.execute(
        "SELECT exam_type, COUNT(*) FROM notices WHERE is_active = 1 GROUP BY exam_type"
    ).fetchall()
    by_province = conn.execute(
        "SELECT province, COUNT(*) FROM notices WHERE is_active = 1 GROUP BY province ORDER BY COUNT(*) DESC"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "by_type": dict(by_type),
        "by_province": dict(by_province),
    }


# ─── Source CRUD ────────────────────────────────────────────

def upsert_source(source: dict) -> int:
    """插入或更新数据源配置"""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO sources (province, exam_type, name, url, parser_type,
            crawl_interval, is_active, config)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(province, exam_type, name) DO UPDATE SET
            url = excluded.url,
            parser_type = excluded.parser_type,
            crawl_interval = excluded.crawl_interval,
            config = excluded.config
    """, (
        source["province"],
        source["exam_type"],
        source["name"],
        source["url"],
        source.get("parser_type", "html"),
        source.get("crawl_interval", 3600),
        json.dumps(source.get("config", {}), ensure_ascii=False),
    ))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def get_active_sources() -> list[dict]:
    """获取所有活跃的数据源"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sources WHERE is_active = 1 ORDER BY province, exam_type"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_source_last_crawl(source_id: int, status: str, new_count: int = 0, error_msg: str | None = None, duration_ms: int = 0):
    """更新数据源的最后抓取时间，并记录日志"""
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE sources SET last_crawl_at = ? WHERE id = ?", (now, source_id))
    conn.execute("""
        INSERT INTO crawl_logs (source_id, status, new_notices, error_msg, duration_ms, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (source_id, status, new_count, error_msg, duration_ms, now))
    conn.commit()
    conn.close()


# ─── Helpers ────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("raw_fields", "tags", "config"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except json.JSONDecodeError:
                pass  # 保持原始字符串
    return d
