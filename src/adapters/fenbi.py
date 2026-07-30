"""
粉笔网聚合适配器
数据源: fenbi.com 考试信息列表
作为主数据源的补充——粉笔网聚合了各省公告，页面结构相对稳定
"""

import json
import re
from bs4 import BeautifulSoup

from src.adapters.base import BaseAdapter, RawNotice


class FenbiAdapter(BaseAdapter):
    """粉笔网考试日历——聚合各省公告"""

    def fetch_notice_list(self) -> list[RawNotice]:
        notices: list[RawNotice] = []
        seen: set[str] = set()

        # 粉笔网各省考试信息列表页
        urls = self.config.get("config", {}).get("list_urls", [self.list_url])

        for list_url in urls:
            try:
                html = self.http.get(list_url)
                soup = BeautifulSoup(html, "lxml")

                # 粉笔网的考试信息卡片/列表项
                for a in soup.select("a[href]"):
                    url = (a.get("href") or "").strip()
                    title = a.get_text(strip=True)
                    if not url or not title or len(title) < 6:
                        continue
                    if url.startswith("javascript") or url == "#":
                        continue

                    full_url = self.urljoin(url)
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

                # 也检查页面中嵌入的 JSON 数据
                for script in soup.select("script"):
                    text = script.get_text(strip=True) if script.string else ""
                    if not text or "window.__INITIAL_STATE__" not in text:
                        continue
                    # 尝试从 JSON 中提取考试信息
                    try:
                        # 找 JSON 对象
                        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', text, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            self._extract_from_json(data, notices, list_url, seen)
                    except (json.JSONDecodeError, KeyError):
                        pass

            except Exception:
                continue

        return notices[:40]

    def _extract_from_json(self, data: dict, notices: list, base_url: str, seen: set):
        """递归从 JSON 中提取考试信息"""
        if isinstance(data, dict):
            for key in ("exams", "examList", "noticeList", "items", "list", "data"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("name") or ""
                            url = item.get("url") or item.get("link") or item.get("detailUrl") or ""
                            if title and url and "考试" in title:
                                full_url = self.urljoin(url)
                                if full_url not in seen:
                                    seen.add(full_url)
                                    notices.append(RawNotice(
                                        title=title,
                                        url=full_url,
                                        source_id=self.source_id,
                                    ))
            for v in data.values():
                self._extract_from_json(v, notices, base_url, seen)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._extract_from_json(item, notices, base_url, seen)

    def should_include(self, title: str) -> bool:
        kw = ["公务员", "选调", "招录", "招考", "录用", "省考", "国考", "公告", "考试"]
        return any(k in title for k in kw)
