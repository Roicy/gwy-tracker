"""
通知推送模块
- 企业微信机器人（主力）
- Server 酱（备用）
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

WECOM_WEBHOOK = os.getenv("WECOM_BOT_WEBHOOK", "")
SERVER_CHAN_KEY = os.getenv("SERVER_CHAN_KEY", "")


def _format_markdown(notice: dict) -> str:
    """格式化公告为 Markdown 消息"""
    exam_label = f"{notice.get('province', '')}·{notice.get('exam_type', '')}"
    title = notice.get("title", "未知标题")

    lines = [
        f"## 🆕 新公告 [{exam_label}]",
        f"**{title}**",
        "",
    ]
    if notice.get("apply_start") and notice.get("apply_end"):
        lines.append(f"- 📅 报名：{notice['apply_start']} ~ {notice['apply_end']}")
    if notice.get("written_exam"):
        lines.append(f"- ✏️ 笔试：{notice['written_exam']}")
    if notice.get("recruit_count"):
        lines.append(f"- 📊 招录：**{notice['recruit_count']:,} 人**")
    if notice.get("publish_dept"):
        lines.append(f"- 📍 发布：{notice['publish_dept']}")
    if notice.get("source_url"):
        lines.append(f"- 🔗 [查看原文]({notice['source_url']})")

    return "\n".join(lines)


def send_wecom(notice: dict) -> bool:
    """通过企业微信机器人推送"""
    if not WECOM_WEBHOOK:
        return False

    content = _format_markdown(notice)
    try:
        resp = httpx.post(
            WECOM_WEBHOOK,
            json={"msgtype": "markdown", "markdown": {"content": content}},
            timeout=10,
        )
        data = resp.json()
        return data.get("errcode") == 0
    except Exception:
        return False


def send_server_chan(title: str, desp: str = "") -> bool:
    """通过 Server 酱推送（备用）"""
    if not SERVER_CHAN_KEY:
        return False

    try:
        resp = httpx.post(
            f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send",
            data={"title": title, "desp": desp},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def notify_new_notice(notice: dict) -> list[str]:
    """推送新公告通知，返回成功的渠道列表"""
    channels = []
    if send_wecom(notice):
        channels.append("wecom")
    if send_server_chan(notice["title"], notice.get("source_url", "")):
        channels.append("server_chan")
    return channels
