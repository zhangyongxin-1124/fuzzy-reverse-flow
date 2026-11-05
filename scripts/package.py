#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package.py — 生成可分发的技能包（零依赖）

用法：
    python scripts/package.py            # 检查 → 打包到 dist/<name>-v<version>.zip
    python scripts/package.py --list     # 只列会打包哪些文件
    python scripts/package.py --no-check # 跳过前置检测（不建议）

v1.3.0 起内置公开案例：examples/（真实推演输出整理，无隐私信息）随包分发，
    便于使用者先看懂输出形态。含真实项目信息的私有案例仍存仓库外，不进 examples/。
打包时强制排除：
    .kb* / kb_local/ 本地知识库（个人规则、踩坑记录）
    __pycache__ / *.pyc / dist/
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from install import SKILL_ROOT, parse_frontmatter, verify  # noqa: E402

EXCLUDE_DIRS = {"__pycache__", ".git", ".kbtest", "dist", "node_modules",
                "kb_local", ".vscode", ".idea"}
EXCLUDE_GLOBS = (".kb", ".kb*", "*.pyc", "*.pyo", "*.tmp", ".DS_Store", "Thumbs.db")

# 固定时间戳（zip 最小可表示时间），用于可复现构建：同内容必得同 SHA256
FIXED_TS = (1980, 1, 1, 0, 0, 0)


def collect() -> list:
    out = []
    for p in sorted(SKILL_ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(SKILL_ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if any(Path(part).match(g) for part in rel.parts for g in EXCLUDE_GLOBS):
            continue
        out.append(rel)
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_check(script: str) -> bool:
    r = subprocess.run([sys.executable, str(SKILL_ROOT / "scripts" / script)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
    print(f"  {'✓' if ok else '✗'} {script}: {tail[0]}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="打包本工具为可分发 zip")
    ap.add_argument("--list", action="store_true", help="只列文件清单")
    ap.add_argument("--no-check", action="store_true", help="跳过前置检测")
    ap.add_argument("--out", default="", help="输出路径（默认 dist/<name>-v<version>.zip）")
    args = ap.parse_args()

    meta = parse_frontmatter((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    name = meta.get("name", "").strip() or SKILL_ROOT.name
    version = meta.get("version", "0.0.0").strip() or "0.0.0"

    files = collect()
    total = sum((SKILL_ROOT / f).stat().st_size for f in files)
    print(f"技能: {name}  v{version}")
    print(f"文件: {len(files)} 个，{total / 1024:.1f} KB")
    print("包含: examples/（内置公开案例）; 排除: .kb*（本地知识库）, __pycache__, dist/")

    if args.list:
        print("\n[清单]")
        for f in files:
            print(f"  {f.as_posix()}")
        return 0

    if not args.no_check:
        print("\n[前置检测]")
        required_docs = ["README.md", "使用说明.txt", "CHANGELOG.md", "PROVENANCE.md",
                         "LICENSE", "SKILL.md", "_check_docs.py", "references/issue-codes.md",
                         "references/regulation-watch.md", "references/regulation-global.md",
                         "docs/对话模式推演引导.md", "docs/规则库众筹指南.md",
                         ".github/ISSUE_TEMPLATE/踩坑规则提交.md"]
        missing = [f for f in required_docs if not (SKILL_ROOT / f).is_file()]
        if missing:
            print("  ✗ 发版必备文档缺失：" + "、".join(missing))
            return 1
        print("  ✓ 发版必备文档齐备（README / 使用说明.txt / 校验脚本 / 编码规范）")
        errs, warns, _ = verify(SKILL_ROOT)
        for w in warns:
            print(f"  ! {w}")
        if errs:
            for e in errs:
                print(f"  ✗ {e}")
            print("\n结构校验未通过，拒绝打包。")
            return 1
        ok = run_check("selftest.py") and run_check("provenance_check.py")
        if not ok:
            print("\n检测未通过，拒绝打包（确认无误可加 --no-check）。")
            return 1

    out = Path(args.out) if args.out else SKILL_ROOT / "dist" / f"{name}-v{version}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    checks = []
    def put(z: zipfile.ZipFile, arc: str, data: bytes, mode: int = 0o644) -> None:
        """以固定时间戳写入，保证同内容 → 同 SHA256（可复现构建）。

        若用 z.write() / z.writestr(裸调用)，zip 会写入当前时间，
        导致每次打包校验值都变，校验值就失去意义。
        """
        info = zipfile.ZipInfo(arc, date_time=FIXED_TS)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o100000 | mode) << 16
        z.writestr(info, data)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            arc = f"{name}/{rel.as_posix()}"
            src = SKILL_ROOT / rel
            put(z, arc, src.read_bytes())
            checks.append((sha256(src), arc, rel.as_posix()))
        manifest = "\n".join([
            f"# {name} v{version}",
            f"# files: {len(checks)}",
            f"# excluded: .kb*, __pycache__, dist/",
            "",
        ] + [f"{h}  {p}" for h, p, _ in checks])
        put(z, f"{name}/MANIFEST.txt", manifest.encode("utf-8"))
        # SHA256SUMS 用技能根相对路径，解压后在该目录内 `sha256sum -c SHA256SUMS.txt` 可直接校验
        put(z, f"{name}/SHA256SUMS.txt",
            ("\n".join(f"{h}  {r}" for h, _, r in checks) + "\n").encode("utf-8"))

    size = out.stat().st_size
    print(f"\n已生成: {out}  ({size / 1024:.1f} KB)")
    print(f"校验值: {sha256(out)}")
    print("\n接收方安装：")
    print(f"  1) 解压得到 {name}/ 目录")
    print(f"  2) 放到 ~/.workbuddy/skills/ 下")
    print(f"  3) cd {name} && python scripts/install.py --verify")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
