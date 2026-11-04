# 规则卡 / 坑卡字段定义

> 两份 JSON 是工具的持久化契约。字段改动需同步 `references/rule.schema.json` 与 `scripts/rfe.py`。

---

## 1. 规则卡（rule）

```json
{
  "id": "RULE-ECOM-0001",
  "domain": "电商平台",
  "subdomain": "许可资质",
  "rule": "如果平台含多商户入驻并提供在线交易处理，那么必须同时持有 ICP 经营许可证（B25）与 EDI 许可证（B21），否则属无证经营。",
  "type": "compliance",
  "severity": "redline",
  "trigger": ["电商", "多商户", "入驻", "在线交易"],
  "probe": ["ICP", "EDI", "经营许可"],
  "lead_time": "1-3 个月",
  "basis": "《电信业务分类目录》B21/B25",
  "basis_level": "rule",
  "verify_url": "https://www.miit.gov.cn/",
  "confidence": "high",
  "note": "单商户自营通常无需 EDI",
  "status": "active",
  "verified_at": null,
  "hit_count": 0,
  "source": "seed",
  "created_at": "2026-11-02T22:30:00"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 自动 | 形如 `RULE-<领域码>-####`；`add` 时自动生成 |
| `domain` / `subdomain` | 是 | 领域名须与 `kb_seed/00_taxonomy.json` 对齐，否则领域加权失效 |
| `rule` | **是** | 必须是一个"如果…那么必须…"的完整句，含后果更佳 |
| `type` | 是 | `compliance` 合规 / `resource` 资源 / `risk` 风险 / `path` 路径 / `misconception` 误传 |
| `severity` | 是 | `redline` 红线 / `blocker` 阻断 / `advisory` 提示 |
| `trigger` | 是 | 口语化关键词，用于召回与场景适用性判断 |
| `probe` | 建议 | 一份合规方案里"应当出现"的短词，用于 `audit` 覆盖率检查；**越短越好**（如 `"EDI"` 而非 `"EDI许可证"`） |
| `lead_time` | 建议 | 审批/准备周期，倒排期的核心输入 |
| `basis` / `basis_level` | 建议 | 依据名称与效力层级；`basis_level` ∈ law/regulation/rule/policy/standard/license/platform/judicial/practice |
| `verify_url` | 建议 | 官方核实入口（.gov.cn 或平台规则页） |
| `confidence` | 是 | high / medium / low |
| `note` | 可选 | 边界条件、例外、常见误读 |
| `status` | 自动 | `active` / `deprecated`（已废止，召回时提示勿引用） |
| `verified_at` | 可选 | 人工核实日期；`verify` 命令写入，超 180 天由 `doctor` 标 stale |
| `hit_count` | 自动 | 召回命中次数，影响下次排序 |
| `source` | 自动 | 写入渠道：`seed` 种子库 / `agent` 推演产出 / `user` 人工录入 |
| `provenance` | 自动 | 内容来源性质：`rfe-original` 原创归纳 / `user-input` 推演得出 / `third-party` 外部引入 |
| `upstream` | 视情况 | 仅当 `provenance=third-party` 时必填来源名称与 URL；引入前须确认其许可证允许再分发，否则不得并入 |

> **溯源纪律**：`basis` 只写法规名称、条款序号与官方入口，属公有领域引用；**不得整段摘录他人整理好的资质清单、代办宣传稿或付费课程讲义**。若确需引入外部规则，必须置 `provenance=third-party` 并填 `upstream`，否则视为来源不明。

### 领域码对照

`通用 COM`｜`电商平台 ECOM`｜`招聘与人力 HR`｜`内容与短剧 MEDIA`｜`教育培训 EDU`｜`医疗健康 MED`｜`餐饮食品 FOOD`｜`线下活动 EVENT`｜`软件与小程序 SASS`｜`硬件制造 HW`｜`金融与投资 FIN`｜`AI生成服务 AIGC`｜`本地生活 LOCAL`｜其他 `GEN`

---

## 2. 坑卡（pitfall）

```json
{
  "id": "PIT-0001",
  "domain": "软件与小程序",
  "trap": "先上线后补备案，小程序被限制访问",
  "trigger": ["上线", "备案", "抢时间"],
  "symptom": "用户反馈打不开，后台提示未备案",
  "guard": "备案与开发并行启动，材料在开发第一周就提交",
  "fallback": "立即提交备案并公告；用 H5 过渡承接流量",
  "severity": "blocker",
  "seen_count": 1,
  "created_at": "2026-11-02T22:30:00"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `trap` | **是** | 一句话说清"死在哪"，动词开头 |
| `domain` | 是 | 同规则卡 |
| `trigger` | 建议 | 用于 `pitfall recall` 匹配 |
| `symptom` | 建议 | 发生时的可观察现象 |
| `guard` | 建议 | 事前预防动作（写成一个具体动作，不是"要注意"） |
| `fallback` | 建议 | 已发生时的止血动作 |
| `severity` | 自动 | 默认 `blocker` |
| `seen_count` | 自动 | 复现次数；达 3 次应升格为规则卡 |

---

## 3. 写入前自检

- [ ] `rule` / `trap` 是完整句，不是短语
- [ ] `trigger` 至少 2 个，且是用户会说的口语词
- [ ] `severity` 没有被滥用成全是 redline
- [ ] `confidence: low` 的条目带了 `verify_url`
- [ ] 没有写入人名、报价、内部排期等不可迁移信息

---

## 4. 校验命令

```bash
python scripts/rfe.py add --file card.json     # 结构不合规会提示跳过
python scripts/rfe.py doctor                   # 检查缺字段、重复 ID、超期未核实
python scripts/rfe.py export -F json -o all.json  # 导出后可用 JSON Schema 校验
```
