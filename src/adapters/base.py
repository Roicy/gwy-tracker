"""
公告采集适配器基类
每个省/来源实现自己的 Adapter 子类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urljoin

from src.utils.http import HttpClient


@dataclass
class RawNotice:
    """从列表页提取的原始公告信息"""
    title: str
    url: str
    source_id: int
    publish_date: str | None = None
    raw_html: str | None = None  # 详情页 HTML（延迟加载）


@dataclass
class CrawlResult:
    """一次抓取的结果"""
    source_id: int
    new_notices: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


class BaseAdapter(ABC):
    """公告采集适配器基类

    子类只需实现：
    - fetch_notice_list(): 从列表页获取公告链接
    - fetch_notice_detail(): 从详情页提取字段
    """

    def __init__(self, source_config: dict):
        self.config = source_config
        self.source_id: int = source_config.get("id", 0)
        self.province: str = source_config.get("province", "")
        self.exam_type: str = source_config.get("exam_type", "")
        self.base_url: str = source_config.get("url", "")
        self.parser_config: dict = source_config.get("config", {})
        self.http = HttpClient()

    @abstractmethod
    def fetch_notice_list(self) -> list[RawNotice]:
        """从列表页抓取公告链接列表"""
        ...

    @abstractmethod
    def fetch_notice_detail(self, url: str) -> dict:
        """进入公告详情页，提取字段。返回 dict 包含 content 等"""
        ...

    def should_include(self, notice: RawNotice) -> bool:
        """子类可覆写：过滤无关页面（如非招考公告）"""
        title = notice.title.lower()
        keywords = ["公务员", "选调", "招录", "招考", "录用", "考试", "公告"]
        return any(kw in title for kw in keywords)

    def urljoin(self, url: str) -> str:
        """拼接相对 URL 为绝对 URL"""
        return urljoin(self.base_url, url)
