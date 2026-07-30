"""
湖南省考适配器
数据源: 湖南人事考试网 (hunanpea.com)
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, RawNotice


class HunanAdapter(BaseAdapter):
    """湖南省公务员考试"""

    LIST_URL = "http://www.hunanpea.com/"

    def fetch_notice_list(self) -> list[RawNotice]:
        html = self.http.get(self.LIST_URL)
        soup = BeautifulSoup(html, "lxml")
        notices: list[RawNotice] = []

        for a in soup.select("a[href]"):
            url = (a.get("href") or "").strip()
            title = a.get_text(strip=True)
            if not url or not title or len(title) < 6:
                continue
            if url.startswith("javascript") or url == "#":
                continue

            full_url = urljoin(self.LIST_URL, url)

            if not any(kw in full_url.lower() for kw in ["article", "detail", "info", "content", "news"]):
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

        content_div = soup.select_one("#content, .article-content, .content, .TRS_Editor, [class*=content]")
        if not content_div:
            content_div = soup
        text = content_div.get_text(separator="\n", strip=True)

        publish_date = None
        for el in soup.select("[class*=date], [class*=time], .info span, .article-info span"):
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", el.get_text())
            if m:
                publish_date = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                break

        dept = None
        dept_el = soup.select_one("[class*=source], [class*=laizi], .info-source")
        if dept_el:
            dept = dept_el.get_text(strip=True).replace("来源：", "").replace("来源:", "").strip()

        return {
            "content": text[:2000],
            "publish_date": publish_date,
            "publish_dept": dept or "湖南省人事考试院",
        }
