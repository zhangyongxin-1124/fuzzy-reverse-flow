#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建可上传 WorkBuddy 开放平台的技能包（UTF-8 文件名）。

为什么需要这个脚本：
  Windows 自带"发送到压缩文件夹"用 GBK 写 zip 内的中文文件名，
  跨平台解压会变成乱码，开放平台解析会失败。
  本脚本用 zipfile 显式写入，非 ASCII 文件名会自动带上 UTF-8 标志位（bit 0x800）。

用法：
  python scripts/build_market_zip.py                 # 打包到 dist/
  python scripts/build_market_zip.py --out <路径>     # 指定输出路径
  python scripts/build_market_zip.py --verify-only <zip>  # 只校验已有包
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = SKILL_ROOT.name

# 不进入市场包的内容
EXCLUDE_DIRS = {"dist", "__pycache__", ".git", ".idea", ".vscode", ".pytest_cache"}
EXCLUDE_FILES = {".gitignore", ".DS_Store", "Thumbs.db"}
EXCLUDE_PATTERNS = [re.compile(r".*\.bak(-\d{8}-\d{6})?$"), re.compile(r".*\.pyc$")]

# 开放平台 SKILL.md frontmatter 必填字段
REQUIRED_FIELDS = [
    "name",
    "display_name",
    "display_name_en",
    "description",
    "description_zh",
    "description_en",
    "version",
    "author",
]


def parse_frontmatter(skill_md: Path) -> dict:
    """粗解析 YAML frontmatter 的顶层标量字段（够用即可，不引入 PyYAML）。"""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if not line or line.startswith((" ", "\t", "#", "-")):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val:
                fields[key.strip()] = val
    return fields


def yaml_strict_check(skill_md: Path) -> list:
    """用真正的 YAML 解析器验证 frontmatter（平台用严格解析，含 ': ' 的裸值会炸）。
    yaml 为可选增强，动态导入以保持零依赖承诺；缺失时跳过校验。"""
    try:
        yaml = __import__("yaml")
    except ImportError:
        return []
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return ["frontmatter 缺失"]
    try:
        data = yaml.safe_load(m.group(1))
        if not isinstance(data, dict):
            return ["frontmatter 未解析为键值映射"]
        return []
    except yaml.YAMLError as e:
        return [f"YAML 语法错误: {e}"]


def check_skill_md(fields: dict) -> list:
    problems = []
    for f in REQUIRED_FIELDS:
        if not fields.get(f):
            problems.append(f"缺少必填字段: {f}")
    # description 里应有触发词，便于模型判断何时调用
    desc = fields.get("description", "")
    if desc and len(desc) < 30:
        problems.append("description 过短，建议写清用途与触发词")
    if desc and len(desc) > 1200:
        problems.append(f"description 过长（{len(desc)} 字），市场展示可能被截断")
    return problems


def iter_files():
    for path in sorted(SKILL_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SKILL_ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if any(p.match(path.name) for p in EXCLUDE_PATTERNS):
            continue
        yield path, rel


def build(out_path: Path) -> None:
    skill_md = SKILL_ROOT / "SKILL.md"
    if not skill_md.exists():
        sys.exit("错误: 缺少 SKILL.md")

    fields = parse_frontmatter(skill_md)
    problems = check_skill_md(fields)
    problems += yaml_strict_check(skill_md)
    if problems:
        print("SKILL.md 校验未通过:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, rel in iter_files():
            # 顶层必须带技能名目录
            arcname = f"{SKILL_NAME}/{rel.as_posix()}"
            zf.write(path, arcname)
            count += 1

    size_kb = out_path.stat().st_size / 1024
    print(f"已生成: {out_path}")
    print(f"文件数: {count} | 大小: {size_kb:.1f} KB")
    print(f"版本: {fields.get('version')} | 作者: {fields.get('author')}")
    print(f"展示名: {fields.get('display_name')} / {fields.get('display_name_en')}")
    verify(out_path)


def verify(zip_path: Path) -> None:
    print("\n--- 校验包内容 ---")
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]

        # 1. 顶层目录唯一且为技能名
        tops = {n.split("/")[0] for n in names}
        if len(tops) != 1:
            problems.append(f"顶层目录不唯一: {tops}")
        elif SKILL_NAME not in tops:
            problems.append(f"顶层目录应为 {SKILL_NAME}，实际 {tops}")

        # 2. SKILL.md 在顶层目录下
        if f"{SKILL_NAME}/SKILL.md" not in names:
            problems.append("SKILL.md 不在技能根目录下")

        # 3. UTF-8 标志位 + 乱码检测
        #    zipfile 读取规则：flag 0x800 存在按 UTF-8 解码，否则按 cp437 解码。
        #    - 有 flag 且有非 ASCII  → 正确（文件名是干净中文）
        #    - 无 flag 且有非 ASCII  → 可疑，原始编码未知
        #    - 文件名含非 ASCII 但每个字符都 < U+0100 → 是 cp437 解出来的乱码
        non_utf8 = []
        mojibake = []
        for i in infos:
            has_non_ascii = any(ord(c) > 127 for c in i.filename)
            if not has_non_ascii:
                continue
            if not (i.flag_bits & 0x800):
                non_utf8.append(i.filename)
            elif all(ord(c) < 256 for c in i.filename):
                mojibake.append(i.filename)

        if non_utf8:
            problems.append(f"{len(non_utf8)} 个文件名缺少 UTF-8 标志位，示例: {non_utf8[0]}")
        if mojibake:
            problems.append(f"{len(mojibake)} 个文件名疑似编码错位，示例: {mojibake[0]}")

        # 4. 关键文件齐全
        for must in ["SKILL.md"]:
            if f"{SKILL_NAME}/{must}" not in names:
                problems.append(f"缺少关键文件: {must}")

        zh_files = [n for n in names if any("\u4e00" <= c <= "\u9fff" for c in n)]
        print(f"总条目: {len(infos)} | 含中文名的文件: {len(zh_files)}")
        if zh_files:
            print("中文文件名抽样:")
            for n in zh_files[:4]:
                print("  ✓ " + n.split("/", 1)[-1])

    if problems:
        print("\n校验失败:")
        for p in problems:
            print("  ✗ " + p)
        sys.exit(1)
    print("\n校验全部通过 ✓  可上传至 WorkBuddy 开放平台")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="输出 zip 路径")
    ap.add_argument("--verify-only", metavar="ZIP", help="只校验已有 zip")
    args = ap.parse_args()

    if args.verify_only:
        verify(Path(args.verify_only))
        return

    if args.out:
        out = Path(args.out)
    else:
        version = parse_frontmatter(SKILL_ROOT / "SKILL.md").get("version", "0.0.0")
        out = SKILL_ROOT / "dist" / f"{SKILL_NAME}-v{version}-market.zip"
    build(out)


if __name__ == "__main__":
    main()
