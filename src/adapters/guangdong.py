"""
广东省考适配器
数据源: 广东省人事考试网 (rsks.gd.gov.cn)
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, RawNotice


class GuangdongAdapter(BaseAdapter):
    """广东省公务员考试"""

    LIST_URL = "http://rsks.gd.gov.cn/zwgk/gwyks/index.html"

    def fetch_notice_list(self) -> list[RawNotice]:
        html = self.http.get(self.LIST_URL)
        soup = BeautifulSoup(html, "lxml")
        notices: list[RawNotice] = []

        # 广东站典型列表结构
        for item in soup.select(".news-list li, .article-list li, .list-content li, ul.list li"):
            a = item.select_one("a")
            if not a:
                continue
            url = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not url or not title:
                continue
            if url.startswith("javascript") or url == "#":
                continue

            full_url = urljoin(self.LIST_URL, url)

            # 提取日期
            date_str = None
            date_span = item.select_one(".date, span.time, [class*=date], [class*=time]")
            if date_span:
                m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", date_span.get_text())
                if m:
                    date_str = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")

            if not self.should_include(RawNotice(title=title, url=full_url, source_id=self.source_id)):
                continue

            notices.append(RawNotice(
                title=title,
                url=full_url,
                source_id=self.source_id,
                publish_date=date_str,
            ))

        # 如果上面没抓到，降级为查所有 a 标签
        if not notices:
            notices = self._fallback_parse(soup)

        return notices[:30]

    def _fallback_parse(self, soup: BeautifulSoup) -> list[RawNotice]:
        """降级解析：查找所有包含关键词的链接"""
        notices: list[RawNotice] = []
        for a in soup.select("a[href]"):
            title = a.get_text(strip=True)
            url = (a.get("href") or "").strip()
            if not title or not url or url.startswith("javascript"):
                continue
            full_url = urljoin(self.LIST_URL, url)
            if self.should_include(RawNotice(title=title, url=full_url, source_id=self.source_id)):
                notices.append(RawNotice(title=title, url=full_url, source_id=self.source_id))
        return notices

    def fetch_notice_detail(self, url: str) -> dict:
        html = self.http.get(url)
        soup = BeautifulSoup(html, "lxml")

        content_div = soup.select_one("#content, .article-content, .TRS_Editor, .content, [class*=content]")
        if not content_div:
            content_div = soup
        text = content_div.get_text(separator="\n", strip=True)

        publish_date = None
        date_el = soup.select_one(".article-info .date, .info .date, [class*=date], [class*=time], #pubtime")
        if date_el:
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", date_el.get_text())
            if m:
                publish_date = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")

        dept = None
        dept_el = soup.select_one(".article-info .source, .info .ly, [class*=source], [class*=dept]")
        if dept_el:
            dept = dept_el.get_text(strip=True).replace("来源：", "").replace("来源:", "").strip()

        return {
            "content": text[:2000],
            "publish_date": publish_date,
            "publish_dept": dept or "广东省人力资源和社会保障厅",
        }
