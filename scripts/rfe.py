#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rfe.py — 模糊问题逆流程推理工具（Fuzzy Reverse Flow）知识库 CLI（零依赖，仅 Python 标准库）

设计目标
  1. 规则与踩坑记忆可持久化、可 diff、可开源共享（JSONL，逐行一条，便于 git 合并）
  2. 召回想得快且可解释（字符二元组 + 触发器命中 + 领域加权 + 历史命中数）
  3. 方案体检可进 CI（有红项返回非 0）

子命令
  init      初始化知识库并导入种子规则
  recall    召回相关规则（推演前必做）
  infer     猜测领域（阶段一用）
  add       追加规则（文件或 stdin）
  pitfall   踩坑记忆：add / recall / list
  audit     方案体检：四阶段完整性 + 红线覆盖 + 危险话术
  stats     知识库统计
  export    导出 Markdown / JSON
  verify    更新规则核实状态
  doctor    知识库自检
  migrate   知识库结构版本迁移（只写可写本地库，绝不写只读种子库）

知识库分两层（v1.3.0 起显式声明）
  只读种子库：SKILL_ROOT/kb_seed/*.json —— 随仓库分发，永不写入、永不修改
  可写本地库：RFE_KB（默认 ~/.workbuddy/reverse-engine）—— init / add / pitfall /
              settle / approve / verify / doctor --fix / migrate 只写这一层
  多宿主（WorkBuddy、Codex 等）共用同一份可写本地库，故新沉淀一律先进待审区。

环境变量
  RFE_KB    可写本地知识库目录，默认 ~/.workbuddy/reverse-engine
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    """从 SKILL.md frontmatter 读版本号，避免此处与技能版本各写一份而漂移。"""
    try:
        for line in (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("version:"):
                return line.split(":", 1)[1].strip() or "0.0.0"
    except OSError:
        pass
    return "0.0.0"


VERSION = _read_version()
SEED_DIR = SKILL_ROOT / "kb_seed"

DEFAULT_KB = Path(os.environ.get("RFE_KB", "")) if os.environ.get("RFE_KB") else (
    Path.home() / ".workbuddy" / "reverse-engine"
)

RULES = "rules.jsonl"
PITFALLS = "pitfalls.jsonl"
PENDING = "pending.jsonl"   # 待审区：新沉淀的规则/坑卡先入此，人工确认后转正
META = "kb_meta.json"       # 知识库元数据（复核时间戳、结构版本等）

SCHEMA_VERSION = 2          # 可写本地库的结构版本（migrate 的目标版本）
SCHEMA_HISTORY = {
    0: "v1.1.x 及更早：无 kb_meta.json，字段不统一",
    1: "v1.2.0：rules / pitfalls / pending 三件套 + 复核时间戳",
    2: "v1.3.0：字段规范化、fingerprint 去重、季度复核分级、只读/可写库显式分层",
}

SEVERITY_ORDER = {"redline": 0, "blocker": 1, "advisory": 2}
SEVERITY_LABEL = {"redline": "[红线]", "blocker": "[阻断]", "advisory": "[提示]"}
TYPE_LABEL = {
    "compliance": "合规资质",
    "resource": "资源前提",
    "risk": "致命风险",
    "path": "路径依赖",
    "misconception": "常见误传",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_RE = re.compile(r"[a-z0-9]{2,}")

# 危险话术：出现即提示（不阻断，但必须人工确认）
RISKY_PHRASES = [
    ("保证过审", "error", "承诺审核结果：广告法/平台规则均禁止，且属不可控承诺"),
    ("包过", "error", "承诺审核结果，属不可控承诺"),
    ("百分百", "error", "绝对化承诺，涉广告法风险"),
    ("稳赚", "error", "收益承诺，涉广告法/金融合规风险"),
    ("保证收益", "error", "收益承诺"),
    ("无需资质", "error", "暗示规避许可，属红线表述"),
    ("无需备案", "error", "境内提供互联网信息服务必须备案"),
    ("绕开审核", "error", "规避监管表述，禁止输出"),
    ("规避审核", "error", "规避监管表述，禁止输出"),
    ("个人账户收款", "error", "资金流水走个人账户，涉税务与支付合规风险"),
    ("个人收款码", "error", "经营收款应使用商户号"),
    ("刷单", "error", "虚假交易，涉反不正当竞争与平台处罚"),
    ("爬取用户", "warn", "数据抓取需评估合法性（个人信息/不正当竞争）"),
    ("内部渠道拿证", "warn", "资质须经法定程序，警惕代办风险"),
    ("代办包下证", "warn", "代办承诺不可信，且可能涉伪造材料"),
]


# ---------------------------------------------------------------- 基础工具

def _u(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def tokens(text: str) -> set:
    raw = _u(text)
    out = set(ASCII_RE.findall(raw))
    cjk = "".join(CJK_RE.findall(raw))
    for i in range(len(cjk) - 1):
        out.add(cjk[i:i + 2])
    return out


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today() -> str:
    return date.today().isoformat()


def kb_path(name: str) -> Path:
    return DEFAULT_KB / name


def ensure_kb() -> None:
    DEFAULT_KB.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def write_jsonl(path: Path, items: list) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    tmp.replace(path)


def append_jsonl(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def fingerprint(obj: dict) -> str:
    base = "|".join([
        _u(obj.get("domain", "")),
        _u(obj.get("rule", "") or obj.get("trap", "")),
    ])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def next_id(prefix: str, items: list) -> str:
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    mx = 0
    for it in items:
        m = pat.match(str(it.get("id", "")))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}-{mx + 1:04d}"


# ---------------------------------------------------------------- 初始化

def cmd_init(args) -> int:
    ensure_kb()
    rf, pf = kb_path(RULES), kb_path(PITFALLS)
    rf.touch(exist_ok=True)
    pf.touch(exist_ok=True)
    existing = {x.get("fingerprint") for x in read_jsonl(rf)}
    added, skipped = 0, 0
    if not args.no_seed and SEED_DIR.exists():
        for path in sorted(SEED_DIR.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001
                print(f"  ! 跳过 {path.name}: {exc}")
                continue
            rules = payload.get("rules", []) if isinstance(payload, dict) else payload
            if not isinstance(rules, list):
                continue
            for rule in rules:
                if not isinstance(rule, dict) or not rule.get("rule"):
                    continue
                fp = fingerprint(rule)
                if fp in existing:
                    skipped += 1
                    continue
                rule.setdefault("id", next_id("RULE-" + _domain_code(rule.get("domain", "")),
                                              read_jsonl(rf)))
                rule.setdefault("created_at", now_iso())
                rule.setdefault("source", "seed")
                rule.setdefault("status", "active")
                rule.setdefault("hit_count", 0)
                rule.setdefault("severity", "advisory")
                rule.setdefault("type", "compliance")
                rule["fingerprint"] = fp
                append_jsonl(rf, rule)
                existing.add(fp)
                added += 1
    print(f"知识库: {DEFAULT_KB}")
    print(f"  导入种子规则 {added} 条，跳过重复 {skipped} 条")
    print(f"  当前规则总数 {len(read_jsonl(rf))} 条")
    return 0


def _domain_code(domain: str) -> str:
    table = {
        "通用": "COM", "电商平台": "ECOM", "内容与短剧": "MEDIA", "自媒体": "MEDIA",
        "招聘与人力": "HR", "教育培训": "EDU", "医疗健康": "MED", "餐饮食品": "FOOD",
        "线下活动": "EVENT", "软件与小程序": "SASS", "硬件制造": "HW",
        "金融与投资": "FIN", "AI生成服务": "AIGC", "本地生活": "LOCAL",
    }
    return table.get(domain, "GEN")


# ---------------------------------------------------------------- 领域推断

def load_taxonomy() -> list:
    path = SEED_DIR / "00_taxonomy.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("domains", [])
    except Exception:  # noqa: BLE001
        return []


def infer_domain_names(text: str, top: int = 2) -> list:
    """按 taxonomy 触发器命中数推断领域，返回前 top 个领域名。"""
    t = _u(text)
    scores = []
    for dom in load_taxonomy():
        hit = [x for x in dom.get("triggers", []) if x and _u(x) in t]
        if hit:
            scores.append((len(hit), dom["domain"]))
    scores.sort(reverse=True)
    return [d for _, d in scores[:top]]


def cmd_infer(args) -> int:
    text = _u(args.text)
    scores = []
    for dom in load_taxonomy():
        hit = [x for x in dom.get("triggers", []) if x and _u(x) in text]
        if hit:
            scores.append((len(hit), dom["domain"], hit, dom.get("note", "")))
    scores.sort(reverse=True)
    if not scores:
        print("未能识别领域，建议按【通用】层推演（主体/备案/许可/内容/数据）。")
        return 0
    print("领域推断（按命中触发器数排序）：")
    for n, name, hit, note in scores[:4]:
        print(f"  {name}  命中{n}项: {'、'.join(hit[:8])}")
        if note:
            print(f"    说明: {note}")
    if args.json:
        print(json.dumps([{"domain": s[1], "hits": s[2]} for s in scores], ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- 召回

def _rule_text(rule: dict) -> str:
    parts = [
        rule.get("domain", ""), rule.get("subdomain", ""), rule.get("rule", ""),
        rule.get("note", ""), rule.get("basis", ""),
    ]
    parts += list(rule.get("trigger", []) or [])
    parts += list(rule.get("probe", []) or [])
    parts += list(rule.get("tags", []) or [])
    return " ".join(str(p) for p in parts if p)


def score_rule(query: str, q_tokens: set, rule: dict) -> float:
    score = 0.0
    rt = tokens(_rule_text(rule))
    score += len(q_tokens & rt) * 1.0
    qraw = _u(query)
    for trig in rule.get("trigger", []) or []:
        t = _u(trig)
        if t and t in qraw:
            score += 3.0
    dom = _u(rule.get("domain", ""))
    if dom and dom in qraw:
        score += 2.0
    score += SEVERITY_ORDER.get(rule.get("severity", "advisory"), 2) * -0.6 + 1.0
    score += min(rule.get("hit_count", 0), 10) * 0.25
    if rule.get("status") == "deprecated":
        score -= 1.0
    return score


def cmd_recall(args) -> int:
    rules = read_jsonl(kb_path(RULES))
    if not rules:
        print("知识库为空，先运行: rfe.py init")
        return 0
    pool = rules
    if args.domain:
        dom = _u(args.domain)
        pool = [r for r in rules if _u(r.get("domain", "")) == dom] or rules
    if args.severity:
        pool = [r for r in pool if r.get("severity") == args.severity] or pool
    q_tokens = tokens(args.query)
    top_domains = set(infer_domain_names(args.query))
    scored = []
    for r in pool:
        s = score_rule(args.query, q_tokens, r)
        rdom = r.get("domain", "通用")
        if top_domains and rdom not in top_domains and rdom != "通用":
            s *= 0.55  # 领域不匹配降权，减少跨领域噪声
        scored.append((s, r))
    scored = [x for x in scored if x[0] > 0.4]
    scored.sort(key=lambda x: (-x[0], SEVERITY_ORDER.get(x[1].get("severity", "advisory"), 2)))
    top = scored[: args.top]

    if args.json:
        print(json.dumps([dict(rule=r, score=round(s, 2)) for s, r in top],
                         ensure_ascii=False, indent=2))
        return 0

    if not top:
        print("无命中规则。建议：rfe.py infer --text \"...\" 先判领域，再按通用层推演。")
        return 0

    print(f"召回 {len(top)} 条（query={args.query}）：\n")
    for s, r in top:
        sev = r.get("severity", "advisory")
        print(f"{SEVERITY_LABEL.get(sev, '[提示]')} {r.get('id','?')} "
              f"{r.get('domain','')}/{r.get('subdomain','')}  "
              f"(可信:{r.get('confidence','?')} 核实:{_verified_label(r)} 命中:{r.get('hit_count',0)} 分:{s:.1f})")
        print(f"  {r.get('rule','')}")
        extra = []
        if r.get("lead_time"):
            extra.append(f"提前期 {r['lead_time']}")
        if r.get("basis"):
            extra.append(f"依据 {r['basis']}")
        if r.get("verify_url"):
            extra.append(f"核实 {r['verify_url']}")
        if extra:
            print("  " + " | ".join(extra))
        if r.get("status") == "deprecated":
            print("  ! 该规则已标注废止/不适用，请勿再作为要求引用")
        print()
    _touch_hits([r.get("id") for _, r in top])
    return 0


def _verified_label(rule: dict) -> str:
    v = rule.get("verified_at")
    if not v:
        return "未核实"
    try:
        d = date.fromisoformat(str(v)[:10])
    except ValueError:
        return str(v)
    days = (date.today() - d).days
    return f"{v}（{days}天前）" + (" 需复核" if days > 180 else "")


def _touch_hits(ids: list) -> None:
    if not ids:
        return
    path = kb_path(RULES)
    items = read_jsonl(path)
    idset = {i for i in ids if i}
    changed = False
    for it in items:
        if it.get("id") in idset:
            it["hit_count"] = int(it.get("hit_count", 0)) + 1
            changed = True
    if changed:
        write_jsonl(path, items)


# ---------------------------------------------------------------- 写入规则

def _load_payload(path_arg: str | None) -> list:
    if path_arg:
        raw = Path(path_arg).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    raw = raw.strip()
    data = json.loads(raw)
    if isinstance(data, dict) and "rules" in data:
        return data["rules"]
    if isinstance(data, dict) and "pitfalls" in data:
        return data["pitfalls"]
    if isinstance(data, list):
        return data
    return [data]


def cmd_add(args) -> int:
    ensure_kb()
    pending = getattr(args, "pending", False)
    path = kb_path(PENDING if pending else RULES)
    items = read_jsonl(path)
    existing = {x.get("fingerprint"): x for x in items}
    added = []
    for rule in _load_payload(args.file):
        if not isinstance(rule, dict) or not (rule.get("rule") or "").strip():
            print("  ! 跳过一条：缺少 rule 字段")
            continue
        fp = fingerprint(rule)
        if fp in existing:
            existing[fp]["hit_count"] = int(existing[fp].get("hit_count", 0)) + 1
            print(f"  = 已存在相同规则，命中数 +1：{existing[fp].get('id')}")
            continue
        rule.setdefault("domain", "通用")
        rule.setdefault("id", next_id("RULE-" + _domain_code(rule["domain"]), items + added))
        rule.setdefault("severity", "advisory")
        rule.setdefault("type", "compliance")
        rule.setdefault("confidence", "medium")
        rule.setdefault("status", "active")
        rule.setdefault("hit_count", 0)
        rule.setdefault("created_at", now_iso())
        rule.setdefault("source", "agent")
        rule.setdefault("provenance", "user-input")
        rule.setdefault("upstream", None)
        # 溯源纪律：声明为 third-party 却没写来源，拒绝入库（避免来源不明的内容污染知识库）
        if _u(rule.get("provenance")) == "third-party" and not _u(rule.get("upstream") or ""):
            print(f"  ! 拒收一条：provenance=third-party 但缺 upstream（来源名称+URL）。"
                  f"引入外部规则须先确认其许可证允许再分发。")
            continue
        rule["fingerprint"] = fp
        if pending:
            rule["kind"] = "rule"
            rule["review"] = "pending"
            rule["pending_at"] = now_iso()
        items.append(rule)          # 与已有条目一起原子写回
        added.append(rule)
        where = "待审" if pending else "新增"
        print(f"  + {where} {rule['id']}  {rule['rule'][:48]}")
    write_jsonl(path, items)
    if pending:
        print(f"共 {len(added)} 条进入待审区，人工确认后用 pitfall approve --id <ID> 转正。")
    else:
        print(f"共新增 {len(added)} 条，知识库现 {len(items)} 条。")
    return 0


# ---------------------------------------------------------------- 知识库元数据

def _meta_path() -> Path:
    return kb_path(META)


def load_meta() -> dict:
    p = _meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def cmd_meta(args) -> int:
    meta = load_meta()
    if args.set_reviewed:
        meta["last_reviewed"] = today()
        meta["review_note"] = args.note or meta.get("review_note", "")
        _meta_path().write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        meta = load_meta()
    last = meta.get("last_reviewed")
    if not last:
        print("复核时间戳：从未设置（建议每季度复核一次规则库后执行 meta --set-review）")
        return 0
    try:
        days = (date.today() - date.fromisoformat(str(last)[:10])).days
    except ValueError:
        days = -1
    flag = "  ⚠ 超过 90 天，建议安排复核" if days > 90 else ""
    print(f"复核时间戳：{last}（{days} 天前）{flag}")
    if meta.get("review_note"):
        print(f"备注：{meta['review_note']}")
    return 0


# ---------------------------------------------------------------- 踩坑记忆

def cmd_pitfall(args) -> int:
    ensure_kb()
    path = kb_path(PITFALLS)
    if args.action == "add":
        target = kb_path(PENDING) if getattr(args, "pending", False) else path
        items = read_jsonl(target)
        existing = {x.get("fingerprint") for x in items}
        acc = list(items)   # 批量导入时序号要累计，否则同批全拿同一个 ID
        added = 0
        for pit in _load_payload(args.file):
            if not (pit.get("trap") or "").strip():
                print("  ! 跳过：缺少 trap 字段")
                continue
            fp = fingerprint(pit)
            if fp in existing:
                print(f"  = 已存在相同坑，跳过：{pit.get('trap')[:40]}")
                continue
            pit.setdefault("id", next_id("PIT", acc))
            pit.setdefault("domain", "通用")
            pit.setdefault("severity", "blocker")
            pit.setdefault("seen_count", 0)
            pit.setdefault("created_at", now_iso())
            pit.setdefault("kind", "pitfall")
            pit["fingerprint"] = fp
            if getattr(args, "pending", False):
                pit["review"] = "pending"
                pit["pending_at"] = now_iso()
            append_jsonl(target, pit)
            acc.append(pit)
            existing.add(fp)
            added += 1
            where = "待审" if getattr(args, "pending", False) else "记坑"
            print(f"  + {where} {pit['id']}  {pit['trap'][:48]}")
        if getattr(args, "pending", False):
            print(f"共 {added} 条进入待审区（{target}），人工确认后用 pitfall approve 转正。")
        else:
            print(f"共记坑 {added} 条。")
        return 0

    if args.action == "pending-list":
        items = read_jsonl(kb_path(PENDING))
        if not items:
            print("待审区为空。")
            return 0
        for p in items:
            print(f"{p.get('id')} [{p.get('kind','pitfall')}/{p.get('severity','?')}] "
                  f"[{p.get('domain')}] {p.get('trap') or p.get('rule','')}")
        print(f"共 {len(items)} 条待审。确认: pitfall approve --id <ID>；"
              f"退回: pitfall reject --id <ID> [--reason]")
        return 0

    if args.action in ("approve", "reject"):
        pend_path = kb_path(PENDING)
        items = read_jsonl(pend_path)
        hit = [x for x in items if x.get("id") == args.id]
        if not hit:
            print(f"待审区中未找到 {args.id}")
            return 2
        item = hit[0]
        items = [x for x in items if x.get("id") != args.id]
        write_jsonl(pend_path, items)
        if args.action == "approve":
            dest = kb_path(RULES if item.get("kind") == "rule" else PITFALLS)
            item["review"] = "approved"
            item["approved_at"] = now_iso()
            dest_items = read_jsonl(dest)
            item["id"] = next_id("RULE-" + _domain_code(item.get("domain", "通用"))
                                 if item.get("kind") == "rule" else "PIT", dest_items)
            dest_items.append(item)
            write_jsonl(dest, dest_items)
            print(f"✓ {args.id} 已转正为 {item['id']}（{dest.name}）")
        else:
            item["review"] = "rejected"
            item["rejected_at"] = now_iso()
            if args.reason:
                item["reject_reason"] = args.reason
            rej = kb_path("rejected.jsonl")
            rej_items = read_jsonl(rej)
            rej_items.append(item)
            write_jsonl(rej, rej_items)
            print(f"✗ {args.id} 已退回并归档（rejected.jsonl）"
                  + (f"：{args.reason}" if args.reason else ""))
        return 0

    items = read_jsonl(path)
    if args.action == "list":
        for p in items:
            print(f"{p.get('id')} [{p.get('domain')}] {p.get('trap')}")
        print(f"共 {len(items)} 条")
        return 0

    # recall
    q_tokens = tokens(args.query or "")
    qraw = _u(args.query or "")
    scored = []
    for p in items:
        text = " ".join(str(x) for x in [
            p.get("domain", ""), p.get("trap", ""), p.get("symptom", ""),
            p.get("guard", ""), " ".join(p.get("trigger", []) or []),
        ])
        s = len(q_tokens & tokens(text)) + sum(
            2.0 for t in (p.get("trigger") or []) if t and _u(t) in qraw)
        s += min(p.get("seen_count", 0), 5) * 0.3
        if s > 0.4:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    if getattr(args, "json", False):
        print(json.dumps([dict(pitfall=p, score=round(s, 2)) for s, p in scored[: args.top]],
                         ensure_ascii=False, indent=2))
        return 0
    if not scored:
        print("无历史坑记录。本次若踩到新坑，用 pitfall add 记下来。")
        return 0
    print("历史踩坑（同类场景已知雷区）：\n")
    for s, p in scored[: args.top]:
        print(f"{SEVERITY_LABEL.get(p.get('severity','blocker'), '[阻断]')} {p.get('id')} [{p.get('domain')}] {p.get('trap')}")
        for k, label in (("symptom", "症状"), ("guard", "预防"), ("fallback", "兜底")):
            if p.get(k):
                print(f"  {label}: {p[k]}")
        print()
    return 0


# ---------------------------------------------------------------- 方案体检

STAGE_KEYS = {
    "阶段一": ["阶段一", "阶段1", "目标锁定", "target locking"],
    "阶段二": ["阶段二", "阶段2", "硬性条件", "前置条件", "红线", "pre-requisite"],
    "阶段三": ["阶段三", "阶段3", "倒排", "里程碑", "milestone"],
    "阶段四": ["阶段四", "阶段4", "规则萃取", "沉淀", "evolution"],
}


def _negation_context(low: str, idx: int, plen: int, window: int = 16) -> bool:
    """判断某处出现是否处于「禁止/否定」语境，避免把“严禁个人账户收款”误判为风险。"""
    left = low[max(0, idx - window):idx]
    right = low[idx + plen: idx + plen + window]
    markers = ("禁止", "严禁", "不得", "不能", "不要", "不可", "避免", "杜绝", "勿",
               "拒绝", "切忌", "绝不", "别用", "不用", "不采用")
    consequences = ("红线", "违规", "违法", "高风险", "不合法", "属风险", "会出事", "禁止")
    return any(m in left for m in markers) or any(c in right for c in consequences)


def scan_risky_phrases(raw: str) -> list:
    low = _u(raw)
    hits = []
    for phrase, level, why in RISKY_PHRASES:
        p = _u(phrase)
        start = 0
        flagged = False
        while True:
            i = low.find(p, start)
            if i < 0:
                break
            if not _negation_context(low, i, len(p)):
                flagged = True
                break
            start = i + len(p)
        if flagged:
            hits.append((level, phrase, why))
    return hits


def cmd_audit(args) -> int:
    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"找不到文件: {plan_path}")
        return 2
    raw = plan_path.read_text(encoding="utf-8", errors="replace")
    low = _u(raw)
    nospace = re.sub(r"\s+", "", low)
    problems = []   # (level, code, message)

    # 1. 四阶段完整性
    for stage, keys in STAGE_KEYS.items():
        if not any(_u(k) in low for k in keys):
            problems.append(("error", "STAGE", f"缺少 {stage}（报告结构不完整）"))

    # 2. 推导句式数量
    n_if = raw.count("如果")
    n_then = raw.count("那么必须") + raw.count("那么需") + raw.count("必须")
    if n_if < 3:
        problems.append(("warn", "PATTERN", f"“如果”句式仅 {n_if} 处，推导链偏弱（建议 ≥5）"))
    if n_then < 3:
        problems.append(("warn", "PATTERN", "硬性条件表述不足，可能退化为建议清单"))

    # 3. 红线覆盖
    rules = read_jsonl(kb_path(RULES))
    domain = args.domain
    pool = [r for r in rules if r.get("severity") == "redline"
            and r.get("status") != "deprecated"]
    if domain:
        pool = [r for r in pool if _u(r.get("domain", "")) == _u(domain)] or pool
    else:
        q_tokens = tokens(raw[:4000])
        pool = sorted(pool, key=lambda r: -score_rule(raw[:4000], q_tokens, r))[:12]
    missing = []
    skipped = []
    for r in pool:
        trig = [t for t in (r.get("trigger") or []) if t]
        if not args.strict and trig and not any(_u(t) in low for t in trig):
            skipped.append(r)   # 方案未触及该场景，视为不适用
            continue
        probes = [p for p in (r.get("probe") or []) if p]
        if not probes:
            probes = trig
        if probes and not any(re.sub(r"\s+", "", _u(p)) in nospace for p in probes):
            missing.append(r)
    for r in missing:
        problems.append(("error", "COVERAGE",
                         f"未覆盖红线 {r.get('id')}: {r.get('rule')[:52]}…（触发词: {'/'.join((r.get('probe') or r.get('trigger') or [])[:3])}）"))

    # 4. 危险话术（否定语境不计）
    for level, phrase, why in scan_risky_phrases(raw):
        problems.append((level, "PHRASE", f"出现危险表述「{phrase}」：{why}"))

    # 5. 免责与核实
    if not any(k in low for k in ["以官方", "待核实", "核实", "不构成法律意见", "咨询律师"]):
        problems.append(("warn", "DISCLAIM", "缺少“核实/免责”提示，法规类结论必须标注确认入口"))

    errors = [p for p in problems if p[0] == "error"]
    warns = [p for p in problems if p[0] != "error"]

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warns,
                          "skipped_rules": [r.get("id") for r in skipped]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"体检对象: {plan_path}  （{len(raw)} 字符）")
        if not problems:
            print("  通过：四阶段齐全、红线覆盖完整、无危险话术。")
        for lvl, code, msg in errors:
            print(f"  [错误/{code}] {msg}")
        for lvl, code, msg in warns:
            print(f"  [提醒/{code}] {msg}")
        if skipped:
            print(f"\n  (另有 {len(skipped)} 条红线因方案未涉及该场景而判定不适用；"
                  f"如已纳入范围请补写或加 --strict)")
        print(f"\n结论: {'未通过（%d 项错误）' % len(errors) if errors else '通过（%d 项提醒）' % len(warns)}")
    return 1 if errors else 0


# ---------------------------------------------------------------- 统计 / 导出 / 核实 / 自检

def cmd_stats(args) -> int:
    rules = read_jsonl(kb_path(RULES))
    pits = read_jsonl(kb_path(PITFALLS))
    pends = read_jsonl(kb_path(PENDING))
    if not rules:
        print("知识库为空。")
        return 0
    by_dom, by_sev, by_src = {}, {}, {}
    for r in rules:
        by_dom[r.get("domain", "?")] = by_dom.get(r.get("domain", "?"), 0) + 1
        by_sev[r.get("severity", "?")] = by_sev.get(r.get("severity", "?"), 0) + 1
        by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
    print(f"规则总数 {len(rules)} | 坑记录 {len(pits)} | 待审 {len(pends)}")
    print("按等级: " + ", ".join(f"{k}={v}" for k, v in sorted(by_sev.items())))
    print("按来源: " + ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())))
    print("按领域:")
    for k, v in sorted(by_dom.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    hot = sorted(rules, key=lambda r: -int(r.get("hit_count", 0)))[:5]
    if hot and hot[0].get("hit_count"):
        print("最常命中:")
        for r in hot:
            if int(r.get("hit_count", 0)) <= 0:
                break
            print(f"  {r.get('id')} x{r['hit_count']} {r.get('rule','')[:40]}")
    meta = load_meta()
    last = meta.get("last_reviewed")
    if last:
        try:
            days = (date.today() - date.fromisoformat(str(last)[:10])).days
        except ValueError:
            days = -1
        mark = " ⚠ 建议复核" if days > 90 else ""
        print(f"复核时间戳：{last}（{days} 天前）{mark}")
    else:
        print("复核时间戳：未设置（rfe meta --set-review）")
    return 0


def cmd_export(args) -> int:
    rules = read_jsonl(kb_path(RULES))
    if args.format == "json":
        text = json.dumps(rules, ensure_ascii=False, indent=2)
    else:
        lines = ["# 领域规则库导出", "", f"> 生成时间 {now_iso()} · 共 {len(rules)} 条", ""]
        doms = sorted({r.get("domain", "通用") for r in rules})
        for dom in doms:
            lines.append(f"## {dom}")
            lines.append("")
            subset = [r for r in rules if r.get("domain", "通用") == dom]
            subset.sort(key=lambda r: SEVERITY_ORDER.get(r.get("severity", "advisory"), 2))
            for r in subset:
                lines.append(f"- **{SEVERITY_LABEL.get(r.get('severity'), '[提示]')} {r.get('id')}** "
                             f"{r.get('rule')}")
                meta = []
                if r.get("lead_time"):
                    meta.append(f"提前期 {r['lead_time']}")
                if r.get("basis"):
                    meta.append(f"依据 {r['basis']}")
                meta.append(f"可信度 {r.get('confidence','?')}")
                meta.append(f"核实 {_verified_label(r)}")
                lines.append(f"  - {' · '.join(meta)}")
            lines.append("")
        text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已导出到 {args.out}")
    else:
        print(text)
    return 0


def cmd_verify(args) -> int:
    path = kb_path(RULES)
    items = read_jsonl(path)
    hit = 0
    for it in items:
        if it.get("id") == args.id:
            it["verified_at"] = args.date or today()
            if args.confidence:
                it["confidence"] = args.confidence
            if args.note:
                it["verify_note"] = args.note
            it["status"] = "active"
            hit += 1
    if not hit:
        print(f"未找到规则 {args.id}")
        return 2
    write_jsonl(path, items)
    print(f"{args.id} 已更新：核实日期 {args.date or today()}，可信度 {args.confidence or '不变'}")
    return 0


def _migrate_items(items: list, kind: str) -> tuple:
    """字段规范化 + fingerprint 去重。返回 (新列表, 规范化条数, 去重条数)。"""
    out, changed, removed, seen = [], 0, 0, set()
    for it in items:
        if not isinstance(it, dict):
            removed += 1
            continue
        before = json.dumps(it, ensure_ascii=False, sort_keys=True)
        it.setdefault("created_at", now_iso())
        it.setdefault("source", "unknown")
        it.setdefault("status", "active")
        it.setdefault("review", "approved")
        it.setdefault("schema", SCHEMA_VERSION)
        if kind == "rule":
            it.setdefault("severity", "advisory")
            it.setdefault("type", "compliance")
            it.setdefault("hit_count", 0)
            it.setdefault("verified_at", "")
            if not it.get("id"):
                it["id"] = next_id("RULE-" + _domain_code(it.get("domain", "")), out)
        else:
            if not it.get("id"):
                it["id"] = next_id("PIT-" + _domain_code(it.get("domain", "")), out)
        fp = it.get("fingerprint") or fingerprint(it)
        if fp in seen:
            removed += 1
            continue
        seen.add(fp)
        it["fingerprint"] = fp
        if json.dumps(it, ensure_ascii=False, sort_keys=True) != before:
            changed += 1
        out.append(it)
    return out, changed, removed


def cmd_migrate(args) -> int:
    """结构版本迁移：只读种子库 kb_seed/ 永不写入，唯一写入目标是可写本地库。"""
    ensure_kb()
    meta = load_meta()
    cur = int(meta.get("schema_version", 0) or 0)
    print(f"只读种子库（永不写入）：{SEED_DIR}")
    print(f"可写本地库（唯一写入目标）：{DEFAULT_KB}")
    print(f"结构版本：v{cur} → v{SCHEMA_VERSION}｜{SCHEMA_HISTORY.get(SCHEMA_VERSION, '')}")
    if cur >= SCHEMA_VERSION:
        print("已是最新结构，无需迁移。")
        return 0
    rp, pp = kb_path(RULES), kb_path(PITFALLS)
    rules, pits = read_jsonl(rp), read_jsonl(pp)
    nr, cr, dr = _migrate_items(rules, "rule")
    np_, cp, dp = _migrate_items(pits, "pitfall")
    print(f"规则 {len(rules)} → {len(nr)}（规范化 {cr} 条 / 去重 {dr} 条）")
    print(f"坑卡 {len(pits)} → {len(np_)}（规范化 {cp} 条 / 去重 {dp} 条）")
    if args.check:
        print("--check：仅报告，未写入任何文件。")
        return 0
    stamp = today()
    for src, items in ((rp, rules), (pp, pits)):
        if src.exists():
            bak = src.with_name(f"{src.stem}.backup-v{cur}-{stamp}{src.suffix}")
            if not bak.exists():
                bak.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"已备份：{bak.name}")
    write_jsonl(rp, nr)
    write_jsonl(pp, np_)
    meta["schema_version"] = SCHEMA_VERSION
    meta["migrated_from"] = cur
    meta["migrated_at"] = now_iso()
    _meta_path().write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(f"迁移完成：kb_meta.json → schema_version={SCHEMA_VERSION}")
    print("迁移只改结构不改语义；请接着执行 rfe doctor 与 rfe stats 复核。")
    return 0


def cmd_doctor(args) -> int:
    rules = read_jsonl(kb_path(RULES))
    pits = read_jsonl(kb_path(PITFALLS))
    issues = 0
    ids = [r.get("id") for r in rules]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        issues += 1
        print(f"[RFE-DR-001] 重复 ID: {', '.join(sorted(map(str, dup)))}")
    quarterly, stale = [], []
    for r in rules:
        if not r.get("rule"):
            issues += 1
            print(f"[RFE-DR-002] {r.get('id')} 缺少 rule 字段")
        v = r.get("verified_at")
        if not v:
            stale.append(r.get("id"))
        else:
            try:
                days = (date.today() - date.fromisoformat(str(v)[:10])).days
                if days > 180:
                    stale.append(r.get("id"))
                elif days > 90:
                    quarterly.append(r.get("id"))
            except ValueError:
                stale.append(r.get("id"))
        if not r.get("fingerprint"):
            issues += 1
            print(f"[RFE-DR-003] {r.get('id')} 缺少 fingerprint（可能导致去重失效）")
    print(f"规则 {len(rules)} 条 / 坑 {len(pits)} 条 / 结构问题 {issues} 项")
    if quarterly:
        print(f"[RFE-DR-101] 季度复核到期（91-180 天未核实）{len(quarterly)} 条："
              f"{', '.join(map(str, quarterly[:10]))}" + (" ..." if len(quarterly) > 10 else ""))
        print("    建议安排本季度人工复核，完成后执行 meta --set-review。")
    if stale:
        print(f"[RFE-DR-102] 过期规则（无核实日期或超 180 天）{len(stale)} 条："
              f"{', '.join(map(str, stale[:10]))}" + (" ..." if len(stale) > 10 else ""))
        print("    建议逐条核对官方入口后执行 verify --id <ID> --confidence high")
    if not args.fix and not issues and not stale and not quarterly:
        print("健康：无需处理。")
    return 0


# ---------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rfe", description="模糊问题逆流程推理工具（Fuzzy Reverse Flow）CLI v" + VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="初始化知识库并导入种子规则")
    s.add_argument("--no-seed", action="store_true", help="不导入种子规则")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("recall", help="召回相关规则")
    s.add_argument("--query", "-q", required=True)
    s.add_argument("--domain", "-d", default="")
    s.add_argument("--severity", default="", choices=["", "redline", "blocker", "advisory"])
    s.add_argument("--top", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_recall)

    s = sub.add_parser("infer", help="推断领域")
    s.add_argument("--text", "-t", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_infer)

    s = sub.add_parser("add", help="新增规则（JSON 文件或 stdin）")
    s.add_argument("--file", "-f", default=None)
    s.add_argument("--pending", action="store_true",
                   help="先入待审区，人工确认后再转正入库")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("pitfall", help="踩坑记忆")
    s.add_argument("action", choices=["add", "recall", "list",
                                      "pending-list", "approve", "reject"])
    s.add_argument("--file", "-f", default=None)
    s.add_argument("--query", "-q", default="")
    s.add_argument("--top", type=int, default=5)
    s.add_argument("--id", default="", help="approve/reject 的待审条目 ID")
    s.add_argument("--reason", default="", help="reject 时的退回原因")
    s.add_argument("--pending", action="store_true", help="add 时先入待审区")
    s.add_argument("--json", action="store_true", help="recall 时输出 JSON")
    s.set_defaults(func=cmd_pitfall)

    s = sub.add_parser("meta", help="知识库元数据（复核时间戳）")
    s.add_argument("--set-review", action="store_true", dest="set_reviewed",
                   help="把复核时间戳置为今天")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_meta)

    s = sub.add_parser("audit", help="方案体检")
    s.add_argument("--plan", "-p", required=True)
    s.add_argument("--domain", "-d", default="")
    s.add_argument("--strict", action="store_true", help="不做场景适用性判断，要求覆盖该领域全部红线")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("stats", help="统计")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("export", help="导出")
    s.add_argument("--format", "-F", default="md", choices=["md", "json"])
    s.add_argument("--out", "-o", default=None)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("verify", help="更新核实状态")
    s.add_argument("--id", required=True)
    s.add_argument("--confidence", default="", choices=["", "high", "medium", "low"])
    s.add_argument("--note", default="")
    s.add_argument("--date", default="")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("doctor", help="知识库自检（季度复核 / 过期规则分级标记）")
    s.add_argument("--fix", action="store_true")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("migrate", help="知识库结构版本迁移（只读种子库永不写入）")
    s.add_argument("--check", action="store_true", help="只报告不写入")
    s.set_defaults(func=cmd_migrate)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
