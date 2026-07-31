"""
公告采集适配器
- BaseAdapter: 抽象基类
- GenericAdapter: 通用适配器（大多数省份用这个，选择器从 YAML 读取）
- 特殊站点写专用子类
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.utils.http import HttpClient


@dataclass
class RawNotice:
    """从列表页提取的原始公告信息"""
    title: str
    url: str
    source_id: int
    publish_date: str | None = None


class BaseAdapter(ABC):
    """公告采集适配器基类"""

    def __init__(self, source_config: dict):
        self.config = source_config
        self.source_id = source_config.get("id", 0)
        self.province = source_config.get("province", "")
        self.exam_type = source_config.get("exam_type", "")
        self.base_url = source_config.get("url", "")
        cfg = source_config.get("config", {})
        self.list_url = cfg.get("list_url", self.base_url)
        self.verify_ssl = cfg.get("verify_ssl", True)
        self.http = HttpClient(verify_ssl=self.verify_ssl)

    @abstractmethod
    def fetch_notice_list(self) -> list[RawNotice]:
        ...

    def fetch_notice_detail(self, url: str) -> dict:
        """默认详情页抓取：提取正文、日期、发布单位"""
        html = self.http.get(url)
        soup = BeautifulSoup(html, "lxml")

        # 正文
        for sel in ["#content", ".article-content", ".article-con", ".TRS_Editor",
                     ".content", "[class*=article]", "[class*=content]", "article"]:
            div = soup.select_one(sel)
            if div:
                text = div.get_text(separator="\n", strip=True)
                break
        else:
            text = soup.get_text(separator="\n", strip=True)

        # 日期
        publish_date = None
        for el in soup.select("[class*=date], [class*=time], .info span, .article-info span, .info-time, .info-date, #pubtime"):
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", el.get_text())
            if m:
                publish_date = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                break

        # 发布单位
        dept = None
        for el in soup.select("[class*=source], [class*=dept], [class*=laizi], .info-source, .article-source"):
            dept = el.get_text(strip=True)
            dept = dept.replace("来源：", "").replace("来源:", "").replace("文章来源：", "").strip()
            if dept and len(dept) < 50:
                break

        return {
            "content": text[:2000],
            "publish_date": publish_date,
            "publish_dept": dept,
            "html": html,  # 原始 HTML，用于职位表解析和附件提取
        }

    def should_include(self, title: str) -> bool:
        """判断标题是否与招考相关"""
        kw = ["公务员", "选调", "招录", "招考", "录用", "考试录用", "遴选", "公告"]
        return any(k in title for k in kw)

    def urljoin(self, url: str) -> str:
        return urljoin(self.list_url, url)


class GenericAdapter(BaseAdapter):
    """
    通用适配器 — 适用于大多数省人事考试网
    选择器和过滤规则从 YAML config 中读取
    """

    def fetch_notice_list(self) -> list[RawNotice]:
        html = self.http.get(self.list_url)
        soup = BeautifulSoup(html, "lxml")
        notices: list[RawNotice] = []
        seen: set[str] = set()

        cfg = self.config.get("config", {})
        selectors = cfg.get("list_selectors", [
            "ul.list li a",
            ".news-list li a",
            ".article-list a",
            "a[href*='article']",
            "a[href*='content']",
            "a[href*='detail']",
            "a[href*='info']",
            "a[href*='news']",
        ])

        for sel in selectors:
            for a in soup.select(sel):
                url = (a.get("href") or "").strip()
                title = a.get_text(strip=True)
                if not url or not title or len(title) < 6:
                    continue
                if url.startswith("javascript") or url == "#":
                    continue

                full_url = urljoin(self.list_url, url)
                if full_url in seen:
                    continue
                seen.add(full_url)

                if not self.should_include(title):
                    continue

                # 尝试在同级元素中找日期
                date_str = None
                parent = a.parent
                if parent:
                    for ds in [".date", ".time", "span.time", "[class*=date]", "[class*=time]"]:
                        date_el = parent.select_one(ds)
                        if date_el:
                            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", date_el.get_text())
                            if m:
                                date_str = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                                break

                notices.append(RawNotice(
                    title=title,
                    url=full_url,
                    source_id=self.source_id,
                    publish_date=date_str,
                ))

        return notices[:30]
