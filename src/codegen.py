#!/usr/bin/env python3
"""
兑换码生成器
- 生成 N 个兑换码，输出哈希列表（codes.json）+ 明文列表（codes-plain.txt）
- 用法：python src/codegen.py [数量] [前缀]
  示例：python src/codegen.py 50 GWY-
"""

import sys
import hashlib
import secrets
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


def generate(count: int = 50, prefix: str = "GWY-") -> tuple[list[dict], list[str]]:
    """生成兑换码，返回 (hashes, plain_codes)"""
    hashes = []
    plain = []

    for _ in range(count):
        # 格式: GWY-A3F8B9C2
        raw = f"{prefix}{secrets.token_hex(4).upper()}"
        h = hashlib.sha256(raw.encode()).hexdigest()
        hashes.append({"hash": h, "created": datetime.now().strftime("%Y-%m-%d")})
        plain.append(raw)

    return hashes, plain


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    prefix = sys.argv[2] if len(sys.argv) > 2 else "GWY-"

    hashes, plain = generate(count, prefix)

    # 写入 codes.json（公开，只有哈希值）
    codes_path = WEB_DIR / "codes.json"
    # 如果已有，合并
    existing = {}
    if codes_path.exists():
        with open(codes_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        for c in existing_data.get("codes", []):
            existing[c["hash"]] = c

    for h in hashes:
        existing[h["hash"]] = h

    output = {
        "version": 1,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "codes": list(existing.values()),
    }
    with open(codes_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 写入 codes-plain.txt（私密！不要提交到 Git）
    plain_path = ROOT / "codes-plain.txt"
    with open(plain_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (count={count})\n")
        for p in plain:
            f.write(p + "\n")

    print(f"✅ 生成 {count} 个兑换码")
    print(f"   哈希列表: {codes_path}")
    print(f"   明文列表: {plain_path} (⚠️ 不要提交到 Git！)")

    # 打印前 5 个码供预览
    print(f"\n前 5 个码（预览）:")
    for p in plain[:5]:
        print(f"   {p}")


if __name__ == "__main__":
    main()
