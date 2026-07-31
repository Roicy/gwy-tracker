"""
公告字段提取器（纯正则规则）
精准匹配报名时间、笔试时间、招录人数
"""

import re
from datetime import datetime


def extract_fields(text: str, publish_date: str | None = None) -> dict:
    """从公告正文提取关键字段

    publish_date 用于推断缺失年份的日期
    """
    # 推断年份
    year = None
    if publish_date:
        m = re.search(r"(\d{4})", publish_date)
        if m:
            year = int(m.group(1))
    if year is None:
        year = datetime.now().year

    return {
        **_extract_apply(text, year),
        **_extract_exam(text, year),
        **_extract_count(text),
        "interview_start": _extract_interview(text, year),
    }


def _extract_apply(text: str, year: int) -> dict:
    """提取报名时间"""
    # ── 完整格式："2026年1月18日9:00至1月25日17:00" ──
    m = re.search(
        r"报名时间[：:∶]\s*"
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?"
        r"(?:至|到|-|—|~)\s*.*?"
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        text
    )
    if m:
        return {
            "apply_start": f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
            "apply_end": f"{int(m.group(1))}-{int(m.group(4)):02d}-{int(m.group(5)):02d}",
        }

    # ── 省略年份："1月18日9∶00至1月25日17∶00" ──
    m = re.search(
        r"(?:报名|报考).*?时间[：:∶]\s*"
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?"
        r"(?:至|到|-|—|~)\s*.*?"
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        text
    )
    if m:
        m1, d1, m2, d2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if m1 <= m2:  # 同一年内
            return {
                "apply_start": f"{year}-{m1:02d}-{d1:02d}",
                "apply_end": f"{year}-{m2:02d}-{d2:02d}",
            }

    # ── 分开表述："报名时间：2026年1月18日。报名截止时间：2026年1月25日" ──
    start_m = re.search(r"(?:报名|报考).*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    end_m = re.search(r"(?:截止|结束|至).*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if start_m:
        s = f"{int(start_m.group(1))}-{int(start_m.group(2)):02d}-{int(start_m.group(3)):02d}"
        e = None
        if end_m:
            e = f"{int(end_m.group(1))}-{int(end_m.group(2)):02d}-{int(end_m.group(3)):02d}"
        return {"apply_start": s, "apply_end": e}

    return {"apply_start": None, "apply_end": None}


def _extract_exam(text: str, year: int) -> dict:
    """提取笔试时间"""
    # "笔试时间：2026年3月14日"
    m = re.search(r"笔试时间[：:∶]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return {"written_exam": f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    # "公共科目笔试时间为2026年3月14日"
    m = re.search(r"(?:公共科目)?笔试[：:∶].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return {"written_exam": f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    # "行政职业能力测验：2026年3月14日 9:00-11:00"
    m = re.search(r"(?:行政职业能力测验|申论|行测).*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return {"written_exam": f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    # "定于2026年3月14日进行笔试"
    m = re.search(r"(?:定于|于|拟定于|拟于)\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?笔试", text)
    if m:
        return {"written_exam": f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    return {"written_exam": None}


def _extract_interview(text: str, year: int) -> str | None:
    """提取面试时间"""
    m = re.search(r"面试时间[：:∶]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _extract_count(text: str) -> dict:
    """提取招录人数——只匹配明确在描述「招录人数」的上下文"""
    patterns = [
        # "全省计划招录公务员10198名"  (最精准)
        r"(?:全省|全市|全区|共|共计|计划|拟|此次)\s*(?:招录|选调|录用|招考|招聘)\s*(?:公务员|工作人员|.*?)\s*(\d[\d,]{2,6})\s*(?:名|人|个|位)",
        # "计划招录18500名公务员"
        r"(?:计划|拟|共|共计)\s*(?:招录|选调|录用|招考)\s*(\d[\d,]{2,6})\s*(?:名|人)",
        # "招录11779人"
        r"(?:招录|选调|录用|招考)\s*(\d[\d,]{2,6})\s*(?:名|人|个)",
        # "全省共计划招录10198名"
        r"(?:全省|全市|全区).*?(\d[\d,]{2,6})\s*(?:名|人)",
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            count_str = m.group(1).replace(",", "").replace("，", "")
            n = int(count_str)
            # 合理性检查：招录人数通常在 10-500000 之间
            if 10 <= n <= 500000:
                return {"recruit_count": n}

    return {"recruit_count": None}


# ─── 职位表解析 ──────────────────────────────────────────────

# 常见的职位表表头关键词映射
HEADER_MAP = {
    "职位代码": "position_code",
    "职位编码": "position_code",
    "岗位代码": "position_code",
    "招录单位": "dept_name",
    "用人单位": "dept_name",
    "招考单位": "dept_name",
    "单位名称": "dept_name",
    "职位名称": "position_name",
    "岗位名称": "position_name",
    "招录职位": "position_name",
    "招录人数": "recruit_num",
    "招考人数": "recruit_num",
    "计划人数": "recruit_num",
    "录用人数": "recruit_num",
    "学历要求": "education",
    "学历": "education",
    "学位要求": "education",
    "专业要求": "major",
    "专业": "major",
    "专业类别": "major",
    "基层工作最低年限": "experience",
    "基层工作年限": "experience",
    "基层经验": "experience",
    "政治面貌": "political_status",
    "其他条件": "other_requirements",
    "备注": "other_requirements",
    "其他要求": "other_requirements",
}


def extract_positions(html: str) -> list[dict]:
    """从 HTML 中解析职位表"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    tables = soup.select("table")

    best_positions: list[dict] = []
    for table in tables:
        positions = _parse_table(table)
        if len(positions) > len(best_positions):
            best_positions = positions

    return best_positions[:500]  # 最多 500 个岗位


def _parse_table(table) -> list[dict]:
    """解析单个 table 为职位列表"""
    rows = table.select("tr")
    if len(rows) < 2:
        return []

    # 解析表头
    header_row = rows[0]
    headers = []
    for th in header_row.select("th, td"):
        text = th.get_text(strip=True).replace("\n", "").replace("\r", "")
        # 匹配表头关键词
        matched = None
        for keyword, field_name in HEADER_MAP.items():
            if keyword in text:
                matched = field_name
                break
        headers.append(matched or text)

    # 如果没匹配到职位表特征列（至少要有单位名称或职位代码），跳过
    has_key_cols = any(h in HEADER_MAP.values() for h in headers)
    if not has_key_cols:
        return []

    # 解析数据行
    positions = []
    for row in rows[1:]:
        cells = row.select("td, th")
        if len(cells) < 2:
            continue

        pos = {}
        for i, cell in enumerate(cells):
            if i >= len(headers):
                break
            field = headers[i]
            if field in HEADER_MAP.values():
                pos[field] = cell.get_text(strip=True).replace("\n", " ").replace("\r", "")

        if pos:  # 至少有一个匹配字段
            # 尝试从文本中提取人数
            if "recruit_num" in pos:
                m = re.search(r"(\d+)", str(pos["recruit_num"]))
                if m:
                    pos["recruit_num"] = int(m.group(1))
            positions.append(pos)

    return positions


def extract_attachments(html: str, base_url: str = "") -> list[str]:
    """从 HTML 中提取附件链接（XLS、PDF、DOC 等）"""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip().lower()
        if any(href.endswith(ext) for ext in [".xls", ".xlsx", ".pdf", ".doc", ".docx", ".zip"]):
            full = urljoin(base_url, a.get("href", ""))
            if full not in urls:
                urls.append(full)
    return urls[:10]  # 最多 10 个附件
