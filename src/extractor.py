"""
公告字段提取器（纯正则规则）
从公告正文中提取报名时间、笔试时间、招录人数等结构化字段
"""

import re
from dataclasses import dataclass, asdict


@dataclass
class NoticeFields:
    apply_start: str | None = None
    apply_end: str | None = None
    written_exam: str | None = None
    interview_start: str | None = None
    recruit_count: int | None = None


class RuleExtractor:
    """正则规则提取器"""

    # 多模式匹配，按优先级排列
    PATTERNS = {
        # "报名时间：2026年1月18日9:00至1月25日17:00"
        # "报名时间为2026年1月6日9∶00至1月12日17∶00"  (注意∶是全角冒号)
        "apply_period": [
            # 完整日期范围（带年份）
            re.compile(
                r"报名时间[：:∶]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
                r".*?"
                r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
            ),
            # 同年省略形式："2026年1月18日至1月25日"
            re.compile(
                r"报名[：:∶].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
                r".*?(?:至|到|-|—).*?"
                r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
            ),
            # "报考申请提交时间为X月X日至X月X日"
            re.compile(
                r"(?:报考|报名).*?(\d{1,2})\s*月\s*(\d{1,2})\s*日"
                r".*?(?:至|到|-|—).*?"
                r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
            ),
        ],
        # "笔试时间：2026年3月14日"
        "exam_date": [
            re.compile(r"笔试时间[：:∶]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
            re.compile(r"(?:公共科目)?笔试[：:∶].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
            re.compile(r"笔试.*?定于.*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
        ],
        # "计划招录18500名公务员"
        # "共计划选调1268人"
        "recruit_count": [
            re.compile(r"(?:计划|拟|共|共计)\s*(?:招录|选调|录用|招考|招聘)\s*(\d[\d,]*)\s*(?:名|人|个|位)"),
            re.compile(r"招[录收聘].*?(\d[\d,]*)\s*(?:名|人)"),
            re.compile(r"全市(?:各级)?.*?(\d[\d,]*)\s*(?:名|人)"),
        ],
    }

    @classmethod
    def extract(cls, text: str) -> dict:
        """从公告正文提取字段，返回 dict

        返回的 dict 可直接 merge 到 notice 中
        """
        result: dict[str, str | None | int] = {
            "apply_start": None,
            "apply_end": None,
            "written_exam": None,
            "recruit_count": None,
        }

        # 提取报名时间
        for pat in cls.PATTERNS["apply_period"]:
            m = pat.search(text)
            if m:
                groups = m.groups()
                if len(groups) == 5 and len(groups[0]) == 4:
                    # 有年份: YYYY, M, D, M, D
                    y = int(groups[0])
                    result["apply_start"] = f"{y}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                    result["apply_end"] = f"{y}-{int(groups[3]):02d}-{int(groups[4]):02d}"
                elif len(groups) == 4:
                    # 无年份: 假设在当前公告发布的年份
                    result["apply_start"] = cls._guess_date(groups[0], groups[1])
                    result["apply_end"] = cls._guess_date(groups[2], groups[3])
                break

        # 提取笔试时间
        for pat in cls.PATTERNS["exam_date"]:
            m = pat.search(text)
            if m:
                groups = m.groups()
                if len(groups) >= 3:
                    y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
                    result["written_exam"] = f"{y}-{mo:02d}-{d:02d}"
                    break

        # 提取招录人数
        for pat in cls.PATTERNS["recruit_count"]:
            m = pat.search(text)
            if m:
                count_str = m.group(1).replace(",", "")
                result["recruit_count"] = int(count_str)
                break

        return result

    @staticmethod
    def _guess_date(month_str: str, day_str: str) -> str:
        """无年份时用当前年份补全"""
        from datetime import datetime
        year = datetime.now().year
        return f"{year}-{int(month_str):02d}-{int(day_str):02d}"


def extract_fields(text: str) -> dict:
    """便捷函数：从公告正文提取关键字段"""
    return RuleExtractor.extract(text)
