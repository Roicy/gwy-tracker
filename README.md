# 公务员考试公告跟踪工具

自动监控各省公务员考试公告（国考、省考、选调、特殊选调），支持网页浏览和微信通知推送。

## 功能

- 🕵️ **自动抓取**：定时扫描各省人事考试网/组织部/国考专题站
- 📊 **网页浏览**：GitHub Pages 托管，按省份/类型/关键词筛选
- 🔔 **微信通知**：新公告通过企业微信机器人即时推送
- 💰 **零成本**：GitHub Actions + Pages 全免费方案

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置通知（可选）
cp .env.example .env
# 编辑 .env 填入企业微信 Webhook URL

# 3. 手动运行
python -m src.main

# 4. 查看结果
# 打开 web/index.html 或 data.json
```

## 项目结构

```
gwy-tracker/
├── config/sources.yaml       # 数据源配置
├── src/
│   ├── main.py               # 入口
│   ├── database.py           # SQLite 存储
│   ├── extractor.py          # 正则字段提取
│   ├── notifier.py           # 通知推送
│   ├── render.py             # 静态站点生成
│   └── adapters/             # 各省适配器
├── web/                      # 前端 (GitHub Pages)
├── data/                     # SQLite 数据库
└── .github/workflows/        # CI/CD
```

## 部署

1. Fork 本仓库
2. 在 Settings → Secrets 中配置 `WECOM_BOT_WEBHOOK`（可选）
3. 启用 Settings → Pages → Source: GitHub Actions
4. GitHub Actions 自动定时运行，站点自动部署

## 适配器

目前已覆盖：
- [x] 国考（国家公务员局）
- [x] 广东省考（广东人事考试网）
- [x] 河南省考（河南人事考试中心）
- [x] 湖南省考（湖南人事考试网）
- [ ] 其余 27 省（持续添加中）
