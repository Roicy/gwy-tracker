"""
河南省考适配器
数据源: 河南省人事考试中心 (hnrsks.com)
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, RawNotice


class HenanAdapter(BaseAdapter):
    """河南省公务员考试"""

    LIST_URL = "https://www.hnrsks.com/"

    def fetch_notice_list(self) -> list[RawNotice]:
        html = self.http.get(self.LIST_URL)
        soup = BeautifulSoup(html, "lxml")
        notices: list[RawNotice] = []

        # 河南站典型结构：a[href*='content'] 或新闻列表
        for a in soup.select("a[href]"):
            url = (a.get("href") or "").strip()
            title = a.get_text(strip=True)
            if not url or not title or len(title) < 6:
                continue
            if url.startswith("javascript") or url == "#":
                continue

            full_url = urljoin(self.LIST_URL, url)

            # 河南站的公告链接通常包含 /content 或 /article
            if not any(kw in full_url.lower() for kw in ["/content", "/article", "detail", "info"]):
                continue

            if not self.should_include(RawNotice(title=title, url=full_url, source_id=self.source_id)):
                continue

            notices.append(RawNotice(
                title=title,
                url=full_url,
                source_id=self.source_id,
            ))

        return notices[:30]

    def fetch_notice_detail(self, url: str) -> dict:
        html = self.http.get(url)
        soup = BeautifulSoup(html, "lxml")

        content_div = soup.select_one(".article-con, .content, #content, .TRS_Editor, [class*=article]")
        if not content_div:
            content_div = soup
        text = content_div.get_text(separator="\n", strip=True)

        publish_date = None
        date_el = soup.select_one(".info-date, .info-time, .time, [class*=date], [class*=time]")
        if date_el:
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", date_el.get_text())
            if m:
                publish_date = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")

        dept = None
        dept_el = soup.select_one(".info-source, .source, [class*=source], [class*=laizi]")
        if dept_el:
            dept = dept_el.get_text(strip=True).replace("来源：", "").replace("来源:", "").replace("文章来源：", "").strip()

        return {
            "content": text[:2000],
            "publish_date": publish_date,
            "publish_dept": dept or "河南省人事考试中心",
        }
