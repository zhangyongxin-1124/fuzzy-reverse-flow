#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py — 把本工具装成 WorkBuddy 技能，并做结构校验（零依赖）

用法：
    python scripts/install.py                 # 复制安装到 ~/.workbuddy/skills/<name>
    python scripts/install.py --dry-run       # 只打印计划，不动文件
    python scripts/install.py --link          # 建目录联接（改源码即时生效，Windows/macOS/Linux）
    python scripts/install.py --force         # 目标已存在时覆盖
    python scripts/install.py --verify        # 只校验，不安装
    python scripts/install.py --uninstall     # 移除已安装的技能

为什么默认「复制」而不是「链接」：复制在任何系统、任何权限下都能用；
链接适合自己改代码时用，但 Windows 上若目标不是链接会误删真实文件，故不设为默认。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_BASE = Path(os.environ.get("WORKBUDDY_SKILLS", "")) or (Path.home() / ".workbuddy" / "skills")

# 安装/打包时不应带上的内容
EXCLUDE_DIRS = {"__pycache__", ".git", ".kbtest", "dist", "node_modules"}
EXCLUDE_GLOBS = (".kb", ".kb*", "*.pyc", "*.tmp")

REQUIRED = ["SKILL.md", "LICENSE", "PROVENANCE.md", "scripts/rfe.py", "kb_seed"]


def log(msg: str) -> None:
    print(msg)


def parse_frontmatter(text: str) -> dict:
    """轻量解析 YAML frontmatter，只取顶层 key: value（不引入 PyYAML）。"""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    meta = {}
    key = None
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][\w-]*\s*:", line):
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip().strip("\"'")
            meta[key] = val
        elif key and line.startswith((" ", "\t")):
            meta[key] = (str(meta.get(key, "")) + " " + line.strip()).strip()
    return meta


def verify(root: Path = SKILL_ROOT) -> list:
    """结构校验。返回 (errors, warns, info)。"""
    errors, warns, info = [], [], []
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        return [f"缺少 SKILL.md：{root}"], [], []

    meta = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
    name = str(meta.get("name", "")).strip()
    desc = str(meta.get("description", "")).strip()

    if not name:
        errors.append("SKILL.md 缺少 name 字段（技能标识，必填）")
    else:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", name):
            errors.append(f"name「{name}」不合规：只能用小写字母、数字、连字符，2–63 位")
        if re.search(r"[^\x00-\x7f]", name):
            errors.append("name 含中文或全角字符——技能标识必须是英文 slug，中文名请写进 description")
        if name != root.name:
            warns.append(f"name「{name}」与目录名「{root.name}」不一致，部分客户端会按目录名加载")
        info.append(f"技能标识: {name}")

    if not desc:
        errors.append("description 为空——模型靠它判断何时唤起技能")
    elif len(desc) < 30:
        warns.append(f"description 偏短（{len(desc)} 字），触发词可能覆盖不足")
    else:
        hits = [w for w in ("我想", "倒推", "需要什么", "能不能", "条件", "合规", "路径") if w in desc]
        info.append(f"description {len(desc)} 字，含 {len(hits)} 个触发词")
        if len(hits) < 2:
            warns.append("description 里触发词偏少，建议补「我想做XX/帮我倒推/要什么条件」等口语表述")

    ver = str(meta.get("version", "")).strip()
    if ver and not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        warns.append(f"version「{ver}」不符合 semver（形如 1.1.0）")
    elif ver:
        info.append(f"版本: {ver}")

    for rel in REQUIRED:
        if not (root / rel).exists():
            errors.append(f"缺少必备文件/目录：{rel}")

    seed = root / "kb_seed"
    if seed.is_dir():
        n = 0
        for f in seed.glob("*.json"):
            try:
                n += len(json.loads(f.read_text(encoding="utf-8-sig")).get("rules", []))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{f.name} 解析失败：{exc}")
        info.append(f"种子规则 {n} 条")
        if n < 50:
            warns.append(f"种子规则仅 {n} 条，召回覆盖面可能不足")

    rfe = root / "scripts" / "rfe.py"
    if rfe.exists():
        r = subprocess.run([sys.executable, str(rfe), "--help"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            errors.append(f"rfe.py 无法运行：{(r.stderr or '').strip()[:200]}")
        else:
            info.append("CLI 可正常运行")

    if sys.version_info < (3, 8):
        errors.append(f"Python {sys.version.split()[0]} 过低，需要 3.8+")
    return errors, warns, info


def _ignore(_dir, names):
    skip = set()
    for n in names:
        if n in EXCLUDE_DIRS:
            skip.add(n)
        elif any(Path(n).match(g) for g in EXCLUDE_GLOBS):
            skip.add(n)
    return skip


def _is_link(target: Path) -> bool:
    """判断是否为链接/联接（junction）。Windows 上 junction 不算 symlink。"""
    if target.is_symlink():
        return True
    if hasattr(os.path, "isjunction"):
        try:
            return os.path.isjunction(target)
        except OSError:
            return False
    if os.name == "nt":
        try:
            import stat as _stat
            attrs = getattr(target.lstat(), "st_file_attributes", 0)
            return bool(attrs & _stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except OSError:
            return False
    return False


def _remove_target(target: Path) -> None:
    """安全移除目标：链接只删链接本身，绝不递归删除它指向的真实目录。

    踩坑记录：早期版本对 junction 直接 shutil.rmtree，会把 F 盘源码一起删掉。
    Windows 上 os.rmdir 对 junction 是「摘链」语义，安全；对非空真目录才报错。
    """
    if _is_link(target):
        if target.is_symlink():
            target.unlink()
            return
        if os.name == "nt":
            os.rmdir(target)        # junction：只摘除链接
            return
    if target.is_dir():
        shutil.rmtree(target)       # 真目录（安装时复制的副本），可安全递归删
    else:
        target.unlink()


def do_install(link: bool, force: bool, dry: bool) -> int:
    meta = parse_frontmatter((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    name = meta.get("name", "").strip() or SKILL_ROOT.name
    target = SKILLS_BASE / name

    log(f"源目录  : {SKILL_ROOT}")
    log(f"目标位置: {target}")
    log(f"方式    : {'目录联接（改源码即时生效）' if link else '复制'}")

    if target.exists() or _is_link(target):
        kind = "链接" if _is_link(target) else "目录"
        if not force:
            log(f"\n目标已存在（{kind}）。确认覆盖请加 --force；不会删除源目录。")
            return 1
        if dry:
            log(f"[dry-run] 将移除已存在的{kind}")
        else:
            _remove_target(target)

    if dry:
        log("[dry-run] 将创建目标目录并写入技能文件（不执行）")
        return 0

    SKILLS_BASE.mkdir(parents=True, exist_ok=True)
    if link:
        if os.name == "nt":
            ps = ("New-Item -ItemType Junction -Path "
                  f"'{target}' -Target '{SKILL_ROOT}' | Out-Null")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True)
            if r.returncode != 0:
                log(f"联接创建失败，退回复制：{(r.stderr or '').strip()[:120]}")
                link = False
        else:
            try:
                target.symlink_to(SKILL_ROOT, target_is_directory=True)
            except OSError as exc:
                log(f"软链创建失败（{exc}），退回复制")
                link = False
    if not link:
        shutil.copytree(SKILL_ROOT, target, ignore=_ignore, dirs_exist_ok=True)

    log(f"\n已安装到 {target}")
    errs, warns, infos = verify(target)
    log("\n[结构校验]")
    for i in infos:
        log(f"  ✓ {i}")
    for w in warns:
        log(f"  ! {w}")
    for e in errs:
        log(f"  ✗ {e}")
    if errs:
        log("\n安装后校验未通过，请按上面错误修正。")
        return 1
    log("\n下一步：新开一个会话，说「我想做个 XX，帮我倒推需要什么条件」。")
    log("（技能列表在会话启动时加载，当前会话不会热更新。）")
    return 0


def do_uninstall() -> int:
    meta = parse_frontmatter((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    name = meta.get("name", "").strip() or SKILL_ROOT.name
    target = SKILLS_BASE / name
    if not (target.exists() or _is_link(target)):
        log(f"未安装：{target}")
        return 0
    if _is_link(target) and target.resolve() == SKILL_ROOT.resolve():
        log(f"目标是指向源目录的链接，仅摘除链接，不删除源码：{target}")
    _remove_target(target)
    log(f"已移除 {target}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="安装本工具为 WorkBuddy 技能")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    ap.add_argument("--link", action="store_true", help="建目录联接而非复制")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的目标")
    ap.add_argument("--verify", action="store_true", help="只做结构校验")
    ap.add_argument("--uninstall", action="store_true", help="移除已安装技能")
    args = ap.parse_args()

    if args.verify:
        errs, warns, infos = verify()
        log("[结构校验]")
        for i in infos:
            log(f"  ✓ {i}")
        for w in warns:
            log(f"  ! {w}")
        for e in errs:
            log(f"  ✗ {e}")
        log(f"\n结论：{'未通过（%d 项错误）' % len(errs) if errs else '通过（%d 项提醒）' % len(warns)}")
        return 1 if errs else 0

    if args.uninstall:
        return do_uninstall()
    return do_install(args.link, args.force, args.dry_run)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
