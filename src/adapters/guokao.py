"""
国考适配器
数据源: 国家公务员局 (bm.scs.gov.cn)
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

from src.adapters.base import BaseAdapter, RawNotice


class GuoKaoAdapter(BaseAdapter):
    """国家公务员考试（国考）"""

    BASE = "http://bm.scs.gov.cn"

    # 几个关键的列表页
    LIST_PAGES = [
        "http://bm.scs.gov.cn/pp/gkweb/core/web/ui/business/article/articelist.html?ColumnId=7",
        "http://bm.scs.gov.cn/pp/gkweb/core/web/ui/business/home/gkhome.html",
    ]

    def fetch_notice_list(self) -> list[RawNotice]:
        notices: list[RawNotice] = []
        seen_urls: set[str] = set()

        for list_url in self.LIST_PAGES:
            try:
                html = self.http.get(list_url)
                soup = BeautifulSoup(html, "lxml")
                for a in soup.select("a[href]"):
                    url = a.get("href", "").strip()
                    title = a.get_text(strip=True)

                    if not url or not title:
                        continue

                    # 过滤 JS 和空链接
                    if url.startswith("javascript") or url == "#":
                        continue

                    full_url = urljoin(list_url, url)

                    # 只保留指向 article 的链接
                    if "article" not in full_url.lower():
                        continue

                    # 去重
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    if not self.should_include(RawNotice(title=title, url=full_url, source_id=self.source_id)):
                        continue

                    notices.append(RawNotice(
                        title=title,
                        url=full_url,
                        source_id=self.source_id,
                    ))
            except Exception:
                # 单个列表页失败不影响其他
                continue

        return notices[:30]  # 最多 30 条

    def fetch_notice_detail(self, url: str) -> dict:
        html = self.http.get(url)
        soup = BeautifulSoup(html, "lxml")

        # 提取正文
        content_div = soup.select_one(".article-con, #content, .content, article, .main-content, [class*=content]")
        if not content_div:
            content_div = soup

        text = content_div.get_text(separator="\n", strip=True)

        # 提取发布日期
        publish_date = None
        date_spans = soup.select(".date, .time, .article-info span, [class*=date], [class*=time]")
        for span in date_spans:
            match = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", span.get_text())
            if match:
                raw = match.group(1)
                publish_date = raw.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                break

        # 提取发布单位
        dept = None
        dept_spans = soup.select(".source, .dept, [class*=source], [class*=dept]")
        if dept_spans:
            dept = dept_spans[0].get_text(strip=True).replace("来源：", "").replace("来源:", "").strip()

        return {
            "content": text[:2000],
            "publish_date": publish_date,
            "publish_dept": dept or "国家公务员局",
        }
