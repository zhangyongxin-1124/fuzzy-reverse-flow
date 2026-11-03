#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 端到端自测（不依赖 pytest，直接 python scripts/selftest.py）

覆盖链路：init → infer → recall → add(去重) → pitfall → audit(通过/不通过) → doctor → export
全部在临时知识库中运行，不污染用户的真实规则库。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RFE = ROOT / "scripts" / "rfe.py"
PASS, FAIL = [], []


def build_covered_plan(domain: str, out: Path) -> Path:
    """从种子规则库生成"满覆盖"测试夹具。

    为什么不用 examples/：私有推演案例不随包发布，若自测依赖它，
    别人 clone 下来第一次跑就失败。夹具按规则库现算，规则增删后自动跟随。
    """
    triggers, probes = [], []
    for f in sorted((ROOT / "kb_seed").glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            continue
        for r in data.get("rules", []):
            if r.get("domain") != domain or r.get("severity") != "redline":
                continue
            triggers += [t for t in (r.get("trigger") or []) if t]
            probes += [p for p in (r.get("probe") or []) if p]

    t_list = list(dict.fromkeys(triggers))
    p_list = list(dict.fromkeys(probes))
    body = [
        "# 自测夹具：满覆盖方案（由规则库自动生成，请勿手改）",
        "",
        "## 0. 结论摘要",
        "判定：黄灯。最硬门槛见阶段二。",
        "",
        "## 1. 阶段一 · 目标锁定",
        "真目标：用于自测的方案骨架，覆盖本领域全部红线。",
        "",
        "## 2. 阶段二 · 逆向硬性条件（合规红线）",
    ]
    for i in range(0, max(6, min(len(t_list), 10))):
        body.append(f"- 如果条件 {i + 1} 成立，那么必须满足对应硬性条件，否则不得上线。")
    body += [
        "",
        "## 3. 阶段三 · 倒排期里程碑",
        "如果资质未提前提交，那么必须顺延上线时间。",
        "",
        "## 4. 阶段四 · 规则萃取",
        "本次沉淀 1 条规则，已入库。",
        "",
        "## 5. 免责与核实",
        "以上结论以官方口径为准，待核实；不构成法律意见。",
        "",
        "## 6. 场景要素（供覆盖率检查识别）",
        "涉及场景：" + "、".join(t_list),
        "硬性条件要素：" + "、".join(p_list),
    ]
    out.write_text("\n".join(body), encoding="utf-8")
    return out


def run(*args: str, stdin: str | None = None, kb: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, RFE_KB=kb, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, str(RFE), *args],
        input=stdin, text=True, encoding="utf-8", capture_output=True, env=env, cwd=str(ROOT),
    )


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} {detail}")
        print(f"  [FAIL] {name} {('-> ' + detail) if detail else ''}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rfe-selftest-")
    print(f"临时知识库: {tmp}\n")

    print("[1] init")
    r = run("init", kb=tmp)
    check("init 成功", r.returncode == 0, r.stderr[-300:])
    rules_file = Path(tmp) / "rules.jsonl"
    n_rules = sum(1 for _ in rules_file.open(encoding="utf-8")) if rules_file.exists() else 0
    check("种子规则已导入(>=60)", n_rules >= 60, f"实际 {n_rules}")

    print("[2] infer")
    r = run("infer", "-t", "我想做一个类似淘宝的电商App，多商户入驻", kb=tmp)
    check("识别为电商平台", "电商平台" in r.stdout, r.stdout[-200:])

    print("[3] recall")
    r = run("recall", "-q", "我想做一个类似淘宝的App，多商户入驻、在线下单", "--top", "6", kb=tmp)
    check("召回命中规则", "RULE-" in r.stdout, r.stdout[:200])
    check("命中双证红线", "EDI" in r.stdout or "ICP" in r.stdout, r.stdout[:200])

    print("[4] add + 去重")
    card = json.dumps({
        "domain": "电商平台", "subdomain": "许可资质",
        "rule": "自测规则：如果平台做在线交易，那么必须持有 EDI 许可证。",
        "type": "compliance", "severity": "redline",
        "trigger": ["自测关键字"], "probe": ["EDI"],
        "confidence": "high",
    }, ensure_ascii=False)
    r1 = run("add", stdin=card, kb=tmp)
    check("新增规则成功", "新增 RULE-" in r1.stdout, r1.stdout)
    r2 = run("add", stdin=card, kb=tmp)
    check("重复规则被去重", "已存在" in r2.stdout, r2.stdout)

    # 溯源纪律：声明 third-party 却没有 upstream，必须拒收
    ext = json.dumps({
        "domain": "通用", "subdomain": "外部引入",
        "rule": "自测规则：如果引入外部规则，那么必须写明来源与许可证。",
        "type": "compliance", "severity": "advisory",
        "trigger": ["自测外部"], "provenance": "third-party",
    }, ensure_ascii=False)
    r3 = run("add", stdin=ext, kb=tmp)
    check("拒收无来源的第三方规则", "缺 upstream" in r3.stdout, r3.stdout)

    print("[5] pitfall")
    pit = json.dumps({"domain": "电商平台", "trap": "自测坑：只办 ICP 备案就上线交易，被责令整改",
                      "symptom": "支付通道被关停", "trigger": ["自测坑"]}, ensure_ascii=False)
    r = run("pitfall", "add", stdin=pit, kb=tmp)
    check("记坑成功", "记坑 PIT-" in r.stdout, r.stdout)
    r = run("pitfall", "recall", "-q", "自测坑", kb=tmp)
    check("坑召回成功", "自测坑" in r.stdout, r.stdout)

    print("[6] audit 好方案")
    good = build_covered_plan("电商平台", Path(tmp) / "good-plan.md")
    r = run("audit", "--plan", str(good), "--domain", "电商平台", kb=tmp)
    check("合规方案通过体检", r.returncode == 0, r.stdout[-400:])

    print("[7] audit 坏方案")
    bad = Path(tmp) / "bad-plan.md"
    bad.write_text("我想做个电商App，先找外包开发，上线后再补资质。保证能过审，稳赚不赔。",
                   encoding="utf-8")
    r = run("audit", "--plan", str(bad), "--domain", "电商平台", kb=tmp)
    check("缺阶段被判不通过", r.returncode == 1, r.stdout[-300:])
    check("检出危险话术", "PHRASE" in r.stdout, r.stdout[-300:])
    check("检出红线未覆盖", "COVERAGE" in r.stdout, r.stdout[-300:])

    print("[8] doctor / export / stats")
    r = run("doctor", kb=tmp)
    check("doctor 可运行", r.returncode == 0 and "规则" in r.stdout, r.stdout[-200:])
    out_md = Path(tmp) / "export.md"
    r = run("export", "-F", "md", "-o", str(out_md), kb=tmp)
    check("导出 Markdown", out_md.exists() and "领域规则库导出" in out_md.read_text(encoding="utf-8"),
          r.stdout[-200:])
    r = run("stats", kb=tmp)
    check("stats 可运行", "规则总数" in r.stdout, r.stdout[-200:])

    # [8+] RFE-DR-103：法规类规则超 90 天触发短周期提醒
    from datetime import date, timedelta
    reg = {"id": "R-REG-SELFTEST", "rule": "测试法规规则：平台需办理某备案",
           "tags": ["法规"], "domain": "测试",
           "verified_at": (date.today() - timedelta(days=100)).isoformat(),
           "fingerprint": "fp-reg-selftest", "source": "selftest", "confidence": "medium"}
    with open(Path(tmp) / "rules.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    r = run("doctor", kb=tmp)
    check("doctor 对法规类超 90 天输出 RFE-DR-103",
          r.returncode == 0 and "RFE-DR-103" in r.stdout and "regulation-watch.md" in r.stdout,
          r.stdout[-300:])
    # 普通规则同天数不应触发 DR-103（对照）
    plain = dict(reg, id="R-PLAIN-SELFTEST", tags=["通用"], fingerprint="fp-plain-selftest")
    with open(Path(tmp) / "rules.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(plain, ensure_ascii=False) + "\n")
    r = run("doctor", kb=tmp)
    check("普通规则超 90 天走 RFE-DR-101 而非 DR-103",
          r.returncode == 0 and "R-PLAIN-SELFTEST" not in (r.stdout.split("RFE-DR-103")[1].split("RFE-DR-")[0] if "RFE-DR-103" in r.stdout else ""),
          r.stdout[-300:])

    # [9] 开源合规：原创性自查必须通过（防止后续提交夹带第三方代码/文本）
    print()
    print("[8b] migrate：结构版本迁移与只读种子库分层")
    r = run("migrate", "--check", kb=tmp)
    check("migrate --check 只报告不写入", r.returncode == 0
          and "--check" in r.stdout and "只读种子库" in r.stdout, r.stdout[-300:])
    r = run("migrate", kb=tmp)
    check("migrate 执行成功", r.returncode == 0
          and "schema_version=2" in r.stdout, r.stdout[-300:])
    meta_p = Path(tmp) / "kb_meta.json"
    check("kb_meta 写入 schema_version=2", meta_p.exists()
          and json.loads(meta_p.read_text(encoding="utf-8")).get("schema_version") == 2)
    check("迁移生成备份文件", len(list(Path(tmp).glob("*.backup-v0-*.jsonl"))) >= 1)
    r = run("doctor", kb=tmp)
    check("doctor 输出统一问题编码 RFE-DR-*", "RFE-DR-" in r.stdout, r.stdout[-300:])
    check("只读种子库未被写入", not list((ROOT / "kb_seed").glob("*.backup*")))

    print("\n[9] provenance_check 原创性自查")
    checker = Path(__file__).resolve().parent / "provenance_check.py"
    r = subprocess.run([sys.executable, str(checker)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    check("自查脚本通过（无第三方痕迹）", r.returncode == 0, (r.stdout or r.stderr)[-400:])
    check("自查覆盖规则来源标注", "全部标注 source" in r.stdout, r.stdout[-300:])

    print(f"\n结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for f in FAIL:
            print("  - " + f)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
