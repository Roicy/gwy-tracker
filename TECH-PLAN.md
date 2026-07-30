# 公务员考试公告跟踪工具 — 技术方案

> 版本: v1.1 | 日期: 2026-07-30 | 状态: 已定稿 (Phase 1 实施用)

---

## 1. 项目目标

自动监控 31 个省（自治区、直辖市）公务员考试公告，覆盖**国考、省考、普通选调、定向选调、特殊选调**五类考试，支持：

- 公告发布时即时推送通知
- 按省份、考试类型筛选
- 关键时间节点（报名、笔试、面试）的结构化提取
- 历史公告可查询

---

## 2. 核心设计约束

| 约束 | 说明 |
|------|------|
| 数据源零散 | 31 省 × 多种考试类型，分布在人事考试网、组织部网站、高校就业网三个维度 |
| 页面结构异构 | 各省网站 HTML 结构不同，没有统一模板 |
| 定向选调不公开 | 只在目标高校内网 / 就业网发布，信息不对称 |
| 反爬风险 | 部分政府网站有频率限制、验证码 |
| 时效性要求高 | 公告发布后 1 小时内通知到位 |

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────┐
│                   调度层 (Scheduler)               │
│               APScheduler / cron                  │
│         各省独立调度频率 (5min ~ 6h)              │
└──────────┬──────────────────────────┬────────────┘
           │                          │
    ┌──────▼──────┐          ┌───────▼──────┐
    │  采集适配器   │          │  RSS 适配器   │
    │  (Adapters)  │          │  (RSS Feeds) │
    └──────┬──────┘          └───────┬──────┘
           │                          │
           └──────────┬───────────────┘
                      │
           ┌──────────▼──────────┐
           │    数据管道 (Pipeline) │
           │  ┌─ 去重             │
           │  ├─ 结构化提取 (LLM)  │
           │  ├─ 字段验证          │
           │  └─ 持久化           │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │      存储层          │
           │  SQLite (MVP)       │
           │  PostgreSQL (扩展)   │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │      通知层          │
           │  ┌─ 企业微信机器人   │
           │  ├─ Server酱/微信    │
           │  └─ 邮件 (备选)     │
           └─────────────────────┘
```

---

## 4. 技术选型

### 4.1 核心栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 爬虫引擎 | Python 3.12+ | `httpx` + `BeautifulSoup`，生态成熟 |
| 任务调度 | **GitHub Actions cron** | 免费、免运维，直接替代 APScheduler |
| 数据存储 | **SQLite** | 零配置、零费用，单文件即数据库 |
| 结构化提取 | **纯规则匹配** (正则) | 零依赖、零成本，覆盖 80% 公告格式 |
| Web 前端 | **纯静态 HTML** (GitHub Pages) | 免费托管，从 JSON 渲染公告列表 |
| 通知推送 | 企业微信机器人 / Server酱 | 免费、微信直达 |

### 4.2 依赖库 (Phase 1)

```
httpx               # 异步 HTTP 客户端
beautifulsoup4      # HTML 解析
lxml                # 快速 HTML 解析器
jinja2              # 静态 HTML 模板渲染
python-dotenv       # 环境变量管理
rich                # 终端日志美化
```

> Phase 1 **不引入**：数据库 ORM（直接用 sqlite3 标准库）、APScheduler（用 GitHub cron 替代）、Web 框架（纯静态页面）。

### 4.3 为什么不用服务器

```
┌─ GitHub Actions (免费) ─────────────────┐
│  cron 触发 → 跑爬虫 → 更新 SQLite       │
│  → 导出 JSON → 渲染 HTML                │
│  → 提交回 repo → 触发 Pages 部署        │
└─────────────────────────────────────────┘
┌─ GitHub Pages (免费) ───────────────────┐
│  纯静态站点: index.html + data.json      │
│  用户浏览器直接渲染公告列表               │
└─────────────────────────────────────────┘
```

- **计算**：GitHub Actions 公开仓库**无限免费**分钟，每 30 分钟跑一次也完全够
- **存储**：SQLite 文件 < 10MB，随代码一起放仓库
- **前端**：GitHub Pages 免费托管静态站点，HTTPS 自带
- **总费用**：$0/月

---

## 5. 数据模型

### 5.1 公告表 (notices)

```sql
CREATE TABLE notices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 来源标识
    source_url      TEXT NOT NULL,              -- 公告原始 URL
    source_hash     TEXT NOT NULL UNIQUE,       -- URL + 标题的 SHA256，用于去重
    
    -- 分类维度
    province        TEXT NOT NULL,              -- 省份，如 '广东'
    exam_type       TEXT NOT NULL,              -- 国考 | 省考 | 选调 | 定向选调 | 特殊选调
    
    -- 公告信息
    title           TEXT NOT NULL,              -- 公告标题
    publish_dept    TEXT,                       -- 发布单位
    publish_date    TEXT,                       -- 发布日期 (YYYY-MM-DD)
    content_summary TEXT,                       -- 公告摘要 (由 LLM 生成，可选)
    
    -- 关键时间节点
    apply_start     TEXT,                       -- 报名开始 (YYYY-MM-DD)
    apply_end       TEXT,                       -- 报名截止 (YYYY-MM-DD)
    written_exam    TEXT,                       -- 笔试时间 (YYYY-MM-DD)
    interview_start TEXT,                       -- 面试开始 (YYYY-MM-DD)
    
    -- 结构化数据
    recruit_count   INTEGER,                    -- 招录人数
    raw_fields      TEXT,                       -- JSON: LLM 提取的原始结构化字段
    
    -- 标签
    tags            TEXT,                       -- JSON: ['联考', '应届', '基层经验']
    
    -- 元数据
    first_seen_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    is_active       INTEGER DEFAULT 1           -- 是否仍有效
);

CREATE INDEX idx_notices_province ON notices(province);
CREATE INDEX idx_notices_exam_type ON notices(exam_type);
CREATE INDEX idx_notices_publish_date ON notices(publish_date);
CREATE INDEX idx_notices_apply_end ON notices(apply_end);
```

### 5.2 数据源配置表 (sources)

```sql
CREATE TABLE sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    province        TEXT NOT NULL,
    exam_type       TEXT NOT NULL,              -- 该源主要发布的考试类型
    name            TEXT NOT NULL,              -- 来源名称，如 '广东省人事考试网'
    url             TEXT NOT NULL,              -- 公告列表页 URL
    parser_type     TEXT NOT NULL DEFAULT 'html', -- html | rss | api
    crawl_interval  INTEGER NOT NULL DEFAULT 3600, -- 抓取间隔 (秒)
    is_active       INTEGER DEFAULT 1,
    last_crawl_at   TEXT,
    config          TEXT,                       -- JSON: 针对该源的解析规则
    UNIQUE(province, exam_type, name)
);
```

### 5.3 抓取日志表 (crawl_logs)

```sql
CREATE TABLE crawl_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL,
    status          TEXT NOT NULL,              -- success | failed | partial
    new_notices     INTEGER DEFAULT 0,
    error_msg       TEXT,
    duration_ms     INTEGER,
    crawled_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);
```

---

## 6. 核心模块设计

### 6.1 适配器模式（Adapter Pattern）

这是整个架构最关键的设计。每个省/来源实现统一接口：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class RawNotice:
    """从网页提取的原始公告字段"""
    title: str
    url: str
    publish_date: str | None
    source_id: int

class BaseAdapter(ABC):
    """公告采集适配器基类"""
    
    def __init__(self, source_config: dict):
        self.config = source_config
        self.source_id = source_config['id']
    
    @abstractmethod
    async def fetch_notice_list(self) -> List[RawNotice]:
        """从列表页获取最新的公告链接列表"""
        ...
    
    @abstractmethod
    async def fetch_notice_detail(self, url: str) -> dict:
        """进入公告详情页，提取完整字段"""
        ...
    
    async def run(self) -> List[dict]:
        """完整采集流程：列表 → 去重 → 详情 → 结构化"""
        raw_list = await self.fetch_notice_list()
        new_notices = self.dedup(raw_list)
        details = []
        for raw in new_notices:
            detail = await self.fetch_notice_detail(raw.url)
            detail.update(raw.__dict__)
            details.append(detail)
        return details
```

**具体适配器示例**：

```python
class GuangdongRSKSAdapter(BaseAdapter):
    """广东省人事考试网适配器"""
    
    LIST_URL = "http://rsks.gd.gov.cn/zwgk/gwyks/index.html"
    
    async def fetch_notice_list(self):
        html = await self._get(self.LIST_URL)
        soup = BeautifulSoup(html, 'lxml')
        # 定位公告列表区域
        items = soup.select('.news-list li a')
        return [
            RawNotice(
                title=a.get_text(strip=True),
                url=urljoin(self.LIST_URL, a['href']),
                publish_date=self._extract_date(a),
                source_id=self.source_id
            )
            for a in items[:20]  # 只取最近 20 条
        ]

class GuoKaoAdapter(BaseAdapter):
    """国考专题站适配器"""
    
    LIST_URL = "http://bm.scs.gov.cn/kl{year}"  # year 动态替换
    # 国考的页面结构相对稳定
```

**需要的适配器数量**（Phase 1 覆盖）：

| 优先级 | 范围 | 适配器数量 | 备注 |
|--------|------|-----------|------|
| P0 | 国考 | 1 | 结构最稳定 |
| P1 | 联考大省 (广东、河南、河北、湖南等 8 省) | 8 | 覆盖主要招考量 |
| P2 | 选调生主流渠道 (高校就业网) | 3-5 | 定向选调抓取 |
| P3 | 其余 23 省 | 23 | 逐步扩展 |

### 6.2 去重策略

使用 **URL + 标题的 SHA256 哈希** 作为唯一标识：

```python
import hashlib

def compute_dedup_key(url: str, title: str) -> str:
    raw = f"{url.strip()}|{title.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def dedup(notices: List[RawNotice], db: Session) -> List[RawNotice]:
    existing = {n.source_hash for n in db.query(Notice.source_hash).all()}
    new = []
    for n in notices:
        key = compute_dedup_key(n.url, n.title)
        if key not in existing:
            n.source_hash = key
            new.append(n)
    return new
```

### 6.3 结构化提取（纯规则匹配）

Phase 1 只用正则，不引入 LLM。后续如果需要，再加 LLM 兜底。

```python
import re
from dataclasses import dataclass

@dataclass
class NoticeFields:
    apply_start: str | None = None
    apply_end: str | None = None
    written_exam: str | None = None
    recruit_count: int | None = None

class RuleExtractor:
    """基于正则规则提取公告关键字段"""

    # 中文日期表达式的各种变体
    PATTERNS = {
        # "报名时间：2026年1月18日至1月25日"
        'apply_period': [
            r'报名时间[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?(\d{1,2})\s*月\s*(\d{1,2})\s*日',
            r'报名[：:].*?(\d{4})[年.](\d{1,2})[月.](\d{1,2})[日].*?(\d{1,2})[月.](\d{1,2})[日]',
        ],
        # "笔试时间：2026年3月14日"
        'exam_date': [
            r'笔试时间[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
            r'(?:公共科目)?笔试[：:].*?(\d{4})[年.](\d{1,2})[月.](\d{1,2})[日]',
        ],
        # "计划招录18500名公务员" / "共选调1268人"
        'recruit_count': [
            r'(?:计划|拟|共|共计).*?(?:招录|选调|录用|招考).*?(\d{1,6})\s*(?:名|人|个)',
            r'招[录收].*?(\d{1,6})\s*(?:名|人)',
        ],
    }

    @classmethod
    def extract(cls, text: str) -> NoticeFields:
        result = NoticeFields()
        for field, patterns in cls.PATTERNS.items():
            for pat in patterns:
                match = re.search(pat, text)
                if match:
                    setattr(result, field, cls._normalize(field, match))
                    break  # 一个字段匹配成功即停止
        return result

    @classmethod
    def _normalize(cls, field: str, match: re.Match):
        """将正则捕获组归一化为标准格式"""
        if field == 'apply_period':
            y, m1, d1, m2, d2 = match.groups()
            return {
                'start': f'{y}-{int(m1):02d}-{int(d1):02d}',
                'end':   f'{y}-{int(m2):02d}-{int(d2):02d}',
            }
        if field == 'exam_date':
            y, m, d = match.groups()
            return f'{y}-{int(m):02d}-{int(d):02d}'
        if field == 'recruit_count':
            return int(match.group(1))
```

### 6.4 通知推送

```python
class NotificationService:
    """多渠道通知推送"""
    
    def __init__(self):
        self.channels = []
    
    def register(self, channel: 'BaseChannel'):
        self.channels.append(channel)
    
    async def notify(self, notice: Notice):
        """新公告通知"""
        for ch in self.channels:
            if ch.should_notify(notice):  # 按用户订阅规则过滤
                await ch.send(self._format(notice))

class WeComBotChannel(BaseChannel):
    """企业微信机器人 — 免费、稳定、富文本"""
    
    async def send(self, message: str):
        await httpx.post(self.webhook_url, json={
            "msgtype": "markdown",
            "markdown": {"content": message}
        })
```

**通知模板示例**：

```markdown
## 🆕 新公告 [广东·省考]
**广东省2026年考试录用公务员公告**
- 📅 报名：2026-01-20 ~ 2026-01-25
- ✏️ 笔试：2026-03-14
- 📊 招录：**18,500 人**
- 📍 发布单位：广东省委组织部
- 🔗 [查看原文](http://rsks.gd.gov.cn/...)
```

---

## 7. 部署 & 调度（GitHub Actions）

### 7.1 调度策略

用 GitHub Actions 的 cron 实现定时任务，**不需要 APScheduler**。

```yaml
# .github/workflows/scrape.yml
name: 抓取公务员考试公告

on:
  schedule:
    # 公告季 (10-2月): 每 30 分钟
    - cron: '*/30 * * 10-2 *'
    # 淡季 (3-9月): 每 6 小时
    - cron: '0 */6 * 3-9 *'
  workflow_dispatch:  # 支持手动触发

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python src/main.py
      - name: 提交更新 (如果有新公告)
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ web/
          git diff --staged --quiet || git commit -m "📋 $(date +%Y-%m-%d) 公告更新"
          git push
```

> **费用说明**：公开仓库 GitHub Actions **无限免费**。私有仓库每月 2000 分钟免费，按每 30 分钟跑一次每次 2 分钟算，约 2880 分钟/月——如果是私有仓库会超。**建议用公开仓库**。

### 7.2 调度频率策略

不同考试类型用不同频率标签（在 cron 层面统一调度，在代码层面按类型判断是否该跑）：

```python
# 公告季判断
def is_peak_season() -> bool:
    month = datetime.now().month
    return month in [10, 11, 1, 2]

# 各来源适配器上的频率标记
SOURCE_INTERVALS = {
    '国考':     3600,    # 1h (发布极少)
    '省考':     7200,    # 2h
    '选调':     3600,    # 1h (窗口期短)
    '特殊选调': 1800,    # 30min (定向，窗口极短)
}
```

### 7.3 数据持久化流程

```
GitHub Actions 每次执行:
  checkout repo (获取上次的 SQLite + JSON)
    → 运行爬虫 (更新 SQLite)
    → 从 SQLite 导出 data.json
    → 用 Jinja2 渲染 index.html
    → git commit + push (把更新写回 repo)
    → GitHub Pages 自动部署
```

SQLite 文件直接放在仓库 `data/` 目录中，随每次抓取提交更新。

---

## 8. 项目目录结构

```
gwy-tracker/
├── TECH-PLAN.md              # 本文件
├── README.md                 # 项目说明
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量模板
├── .github/
│   └── workflows/
│       └── scrape.yml        # GitHub Actions: 定时抓取 + 自动部署
├── config/
│   └── sources.yaml          # 数据源配置 (所有省份 URL + 解析规则)
├── src/
│   ├── __init__.py
│   ├── main.py               # 入口 (一跑到底)
│   ├── models.py             # 数据模型 (dataclasses)
│   ├── database.py           # SQLite crud 封装
│   ├── dedup.py              # 去重逻辑 (SHA256)
│   ├── extractor.py          # 正则字段提取 (纯规则)
│   ├── notifier.py           # 通知推送 (企业微信/Server酱)
│   ├── render.py             # 生成静态 HTML + JSON
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py           # BaseAdapter 基类
│   │   ├── guokao.py         # 国考适配器
│   │   ├── guangdong.py      # 广东省人事考试网
│   │   ├── henan.py          # 河南省人事考试网
│   │   ├── hunan.py          # 湖南红星网
│   │   ├── shandong.py       # 山东灯塔党建
│   │   ├── ...               # 其他省份逐省添加
│   │   └── university.py     # 高校就业网通用适配器
│   └── utils/
│       ├── __init__.py
│       ├── http.py           # HTTP 客户端 (UA轮换/重试/超时)
│       └── logger.py         # 结构化日志
├── tests/
│   ├── test_extractor.py
│   └── test_dedup.py
├── web/                      # 静态站点 (GitHub Pages 部署目录)
│   ├── index.html            # 公告列表页 (Jinja2 渲染)
│   ├── data.json             # 公告 JSON (从 SQLite 导出)
│   └── style.css             # 简单样式
└── data/
    └── gwy_tracker.db        # SQLite 数据库 (Git 跟踪，随 Actions 更新)
```

---

## 9. 实施计划

### Phase 1 — MVP（现在）

**目标**：国考 + 3 个省考，完整闭环（采集 → 存储 → 通知 → 网页）

- [ ] 项目骨架搭建（目录、依赖）
- [ ] SQLite 数据模型 + crud 封装
- [ ] `BaseAdapter` + 国考适配器
- [ ] 广东、河南、湖南三省适配器
- [ ] 正则字段提取器 + 去重
- [ ] 企业微信机器人通知
- [ ] Jinja2 渲染静态 HTML + JSON export
- [ ] GitHub Actions workflow (cron + deploy)
- [ ] GitHub Pages 自动部署
- [ ] 手动运行验证全流程

### Phase 2 — 覆盖扩展

**目标**：31 省省考 + 主要选调

- [ ] 补齐全部省考适配器
- [ ] 选调生高校就业网适配器（3-5 个高校）
- [ ] 公告季自适应调频优化
- [ ] 通知渠道扩展（Server酱/邮件）
- [ ] LLM 结构化字段提取（作为规则失败时的兜底，可选）

### Phase 3 — 打磨

**目标**：稳定性 + 数据质量

- [ ] 爬虫健康监控（每个源的抓取成功率）
- [ ] 反爬策略（参数化延时、UA 轮换）
- [ ] 数据质量检查（缺失字段检测）
- [ ] 抓取成功率统计面板
- [ ] 适配器配置化（页面选择器进 YAML，降低维护成本）

---

## 10. 风险 & 缓解

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| 政府网站改版导致解析器失效 | 高 | 适配器单元测试 + 抓取失败告警 + 健康检查 |
| IP 被封 | 中 | 降低频率、User-Agent 轮换、代理池备用 |
| 结构化提取不准确 | 中 | 规则优先 + LLM 兜底 + 人工标注反馈闭环 |
| 定向选调源覆盖不全 | 高 | 明确标注覆盖率，用户可手动补充 |
| 维护成本随省份数线性增长 | 中 | 适配器配置化，将页面选择器写入 YAML 减少硬编码 |

---

## 11. 已确定的设计决策

| 决策 | 结论 | 理由 |
|------|------|------|
| **存储** | SQLite | Phase 1 数据量 < 1 万条，SQLite 完全够；零配置 |
| **结构化提取** | 纯正则规则 | 覆盖 80% 公告格式，零成本；LLM 留到 Phase 2 作为兜底 |
| **部署** | GitHub Actions + Pages | 公开仓库全免费，免运维 |
| **Web 前端** | Jinja2 渲染纯静态 HTML | 不引入前后端框架，浏览器直接渲染 |
| **调度** | GitHub cron 替代 APScheduler | 省去进程守护，Actions 自带定时 |
| **通知** | 企业微信机器人 | 免费、Markdown 支持、微信直达 |
