"""
国考适配器 (特殊处理)
数据源: 国家公务员局 bm.scs.gov.cn
该站大量使用 JS 渲染，这里尝试抓取静态文章列表页
"""

from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, RawNotice


class GuoKaoAdapter(BaseAdapter):
    """国家公务员考试（国考）"""

    def fetch_notice_list(self) -> list[RawNotice]:
        notices: list[RawNotice] = []
        seen: set[str] = set()

        # 国考文章列表页（静态 HTML）
        for list_url in self.config.get("config", {}).get("list_urls", [self.list_url]):
            try:
                html = self.http.get(list_url)
                soup = BeautifulSoup(html, "lxml")
                for a in soup.select("a[href]"):
                    url = (a.get("href") or "").strip()
                    title = a.get_text(strip=True)
                    if not url or not title:
                        continue
                    if url.startswith("javascript") or url == "#":
                        continue

                    full_url = self.urljoin(url)

                    # 只保留 article 相关链接
                    if "article" not in full_url.lower():
                        continue
                    if full_url in seen:
                        continue
                    seen.add(full_url)

                    if not self.should_include(title):
                        continue

                    notices.append(RawNotice(
                        title=title,
                        url=full_url,
                        source_id=self.source_id,
                    ))
            except Exception:
                continue

        return notices[:30]

    def should_include(self, title: str) -> bool:
        kw = ["公务员", "录用", "招录", "招考", "公告", "职位", "报名", "笔试", "面试", "调剂", "补录"]
        return any(k in title for k in kw)
