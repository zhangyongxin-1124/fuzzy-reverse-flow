# 模糊问题逆流程推理工具 · Fuzzy Reverse Flow

> 原名 Reverse-Fuzzy Engine（内部代号 `rfe`，命令与知识库路径不变）。
> **给它一个模糊的想法，它还你一套滴水不漏的逆向施工图。**
> 目标锁定 → 逆向排雷 → 里程碑倒排 → 规则自演化（含踩坑记忆）

一个可安装的 AI 技能（Skill）＋ 一套零依赖命令行工具。
把"我想做个 XX"翻译成：**必须满足的前提**、**绝不能碰的红线**、**从今天到交付的倒排路径**，并把每次推演沉淀成可复用的领域规则，越用越准。

```bash
$ python scripts/rfe.py recall -q "我想做个类似淘宝的App" --top 3
[红线] RULE-ECOM-0001 电商平台/许可资质 (可信:high)
  如果平台含多商户入驻并提供在线交易处理（下单、撮合、结算），那么必须同时持有
  ICP 经营许可证（B25 信息服务业务）与 EDI 许可证（B21 在线数据处理与交易处理业务），
  仅有 ICP 备案不够。
  提前期 1-3 个月 | 依据 《电信业务分类目录》B21/B25
```

## 零、使用前提与能力边界（必读）

> 本项目是「本地文件 + Python CLI + 落盘知识库」，仓库内**没有任何 HTTP 服务、MCP Server 或云端 API**，不存在可供远程调用的地址。**MIT 解决的是「能不能拿去用」，不解决「别人怎么连上」。** 当前版本 **v1.5.0**，配套 vague-to-product **v2.7.0**。

### 0.1 三档能力边界（A / B / C）

| 档位 | 条件 | 能做 | 不能做 |
|---|---|---|---|
| **能力档 A（完整）** | 宿主支持「读文件 + 执行命令」（tool use）：WorkBuddy、Codex CLI、Cursor / Cline / Windsurf / Trae、Claude Code | 全套 CLI（`init` / `recall` / `infer` / `add` / `pitfall` / `meta` / `audit` / `stats` / `export` / `verify` / `doctor` / `migrate`）；拿到 103 条种子规则与 19 条冷启动坑卡，输出带真实红线的推演与体检结论 | — |
| **能力档 B（注入）** | 模型本身不能执行本地命令，但可在本地召回规则后把规则原文注入 API（DeepSeek API 等 OpenAI 兼容端点） | 拿到召回的规则原文，让模型把硬结论写成人话稿 | 模型不跑 CLI、不写知识库、不产生待审区记录、不执行迁移 |
| **能力档 C（降级）** | **网页聊天、手机 App**、纯提示词输入框 | 只拿到方法论提示词（形态判定、五信号深度、六道闸门 / 四步闭环、反模式） | 拿不到规则库、不能引用具体红线或法条、不能沉淀、不能迁移；合规结论只能写成「请人工向官方核实」 |

**网页聊天与手机只能降级到 C 档。** 这不是模型智力问题，是宿主没有「读文件 + 执行命令」能力；把开源可获取误当成服务可调用，是最常见的坑。（本文件「能力档 A/B/C」与下文「快速开始方式 A/B」含义不同，后者指安装方式：方式 A 装成技能 / 方式 B 只用命令行。）

### 0.2 12 项调用前自检清单（逐项打勾，缺一不建议开始）

1. □ 已取得技能文件副本（git clone 或 GitHub Release ZIP），并校验 **SHA256** 与发布页一致
2. □ 已安装 **Python 3.8+**，`python -V` 可执行（零第三方依赖）
3. □ 用户目录可写（`~/.workbuddy/` 或 `RFE_KB` 指向的目录可创建文件）
4. □ 调用宿主支持「读文件 + 执行命令」；纯网页 / 手机 App 不满足（**决定性**）
5. □ 已初始化知识库：`rfe init`，且 `rfe stats` 显示规则总数大于 0
6. □ 已完成结构迁移：`rfe migrate --check` 显示 v2，必要时执行 `rfe migrate`
7. □ 模型上下文窗口 ≥ 8K（注入规则后实测约 7418 字）
8. □ 知识库复核时间戳在 90 天内（`rfe meta` / `rfe doctor` 查看）
9. □ 已确认本次属于 A / B / C 哪一档，并接受该档能力上限
10. □ 已阅读并接受 0.3 节完整免责声明 7 条（报告尾部强制附带）
11. □ 用途为自用或内网团队复用，**不是**公开 SaaS / 对外经营性 API
12. □ 多宿主并行时，新沉淀走 `rfe add --pending` / `rfe pitfall add --pending` → 待审区 → `rfe pitfall approve/reject`，不直接写正式库

> 完整逐条版见同目录 [`使用说明.txt`](使用说明.txt)（与 README 同为发版必检文档，由 `_check_docs.py` 强制比对一致性）。

### 0.3 使用前提与完整免责声明（7 条，报告尾部强制附带）

1. **内容性质**：全部规则、红线、坑卡与检查项为作者及贡献者的经验性总结，非法律意见、非监管口径、非投资建议。
2. **时效风险**：法律法规、平台审核规则、资质要求会变动；报告所附「知识库复核时间戳」只表示上次人工复核日期，不保证当下仍有效。
3. **强制人工核验**：任何「通过 / 阻断」结论都是自动化的必要条件判断，上线、签约、投放、发布前必须由具备资质的人员向官方渠道逐条核实。
4. **不替代测试**：静态扫描与手测清单不能替代真实环境测试、灰度验证与人工验收；交付必须保留人工核验环节。
5. **责任边界**：使用者对基于本报告作出的决策独立承担责任；作者不对任何直接或间接损失负责。
6. **使用边界**：本项目仅授权自用与内网团队复用；禁止封装为公开 SaaS、对外经营性 API 或任何面向不特定公众的付费服务。
7. **署名保留**：依据 MIT License，转载、修改与再分发必须保留「Copyright (c) 2026 张勇鑫 (Zhang Yongxin)」及许可声明。

> 每份 `v2p plan` 输出报告强制附带本节 7 条免责声明与**知识库复核时间戳**；只写一行简版免责视为不合格。

### 0.4 边界与禁止条款（硬约束）

- **允许**：个人自用；内网团队多个 Agent 复用（如需服务化，仅允许绑定 `127.0.0.1` 环回地址，不得对外暴露）；GitHub 开源与 Release 分发。
- **禁止**：公开 SaaS 产品化；对外经营性 API；面向不特定公众的付费服务；把规则库当作商业合规数据服务售卖；删除或改写 MIT 署名。
- **理由**：规则是经验总结而非合规意见，公开对外提供会构成事实上的「合规意见服务」，带来法律风险。本项目不做、不建议、不授权。
- **P2-3 已实施为仅本地形态（vague-to-product v2.6.0）**：配套技能的本地 stdio MCP Server 只读、无网络监听；本仓库自身仍无任何 MCP/HTTP 服务，禁止公开 SaaS 边界不变。

### 0.5 章节指引

- 知识库分层与版本迁移 → 附录 A；统一问题编码 → 附录 B；季度复核 → 附录 C；Release 部署与发版校验 → 附录 D。
- 内置完整案例（真实推演输出，先看输出再动手）→ `examples/娱乐小程序-逆向施工图.md` 与 `examples/README.md`。
- 环境变量与路径、完整命令清单 → [`使用说明.txt`](使用说明.txt) 第 2、3 节。

---

## 为什么需要"逆向"而不是"正向"

正向规划会漏前提，逆向逼问才会暴露门槛。同一个想法，两种问法：

| 正向（计划书思维） | 逆向（本引擎） |
|---|---|
| 1 注册公司 → 2 开发 → 3 上线 → 4 推广 | 上线的前一刻必须已过审 → 过审前必须双证齐全 → 双证要 1–3 个月 → **今天必须先交材料** |
| 结论：要做 9 个月，做到哪算哪 | 结论：项目下限由资质周期决定，开发可并行，钱必须撑到证下来 |

差别不在勤奋，在于**先证伪再证成**。

---

## 四阶段闭环

| 阶段 | 做什么 | 硬产出 |
|---|---|---|
| **1 目标锁定** | 八维逼问（目标/对象/受众/范围/约束/标准/优先级/输出形式）+ 伪需求四问 | 一句可验收的真目标 + 默认假设清单 |
| **2 逆向反推** | 假设目标已达成，反推六层合规（主体→备案→许可→专项→内容→数据）+ 资源底线 + 死亡点 | 合规红线表 / 资源底线表 / 死亡点清单 |
| **3 里程碑倒排** | 从 T0 往回问"上一刻必须完成什么"，直到今天 | 关键路径 + 今天 3 件事 + 降级路线 |
| **4 自我演化** | 萃取 1–3 条领域规则，写入知识库；踩过的坑另存为坑卡 | 规则卡入库 + 下次自动前置提示 |

**闭环的关键是第 4 步**：不落库的推演只聪明一次。规则累积后，同一领域第二次推演直接跳过"从零想"，从已有红线上开始。

---

## 特性

- **零依赖**：纯 Python 标准库，Python 3.8+ 跑得动，没有 pip install。
- **可解释的召回**：字符二元组 + 触发器命中 + 领域亲和 + 历史命中数，命中理由可逐条打印。
- **可进 CI 的方案体检**：`audit` 检查四阶段完整性、红线覆盖率、危险话术（承诺过审/包过/个人账户收款/规避审核），有红项返回非 0。
- **场景感知**：方案没触及的场景（比如没做劳务派遣）不会被强行要求，但可用 `--strict` 全量校验。
- **否定语境识别**：写"严禁个人账户收款"不会被误判为风险表述。
- **带时效的规则**：每条有 `confidence` 与 `verified_at`，法规类规则超 90 天由 `doctor` 触发短周期快更提醒（RFE-DR-103，信息源与流程见 [`references/regulation-watch.md`](references/regulation-watch.md)），普通规则超 180 天标记待复核；废止条目保留为 `deprecated`，召回时提示"勿再引用"。
- **专收"常见误传"**：例如"《互联网医疗保健信息服务审核同意书》"这类已取消的旧审批，会主动纠偏，避免整份方案方向错误。

---

## v1.5.0 新增：超期降权机防化、红线错误保险、众筹与出海图层

1. **规则库超期降权（P1）**：`rfe recall` 对法规类规则超 90 天未核实者自动降匹配权重 20% 并标注"可能过时"——静态库不会再无声过期（与 doctor RFE-DR-103 同一判定）。
2. **红线错误保险（7.5 风险层）**：所有红线级召回自动附"请以主管部门现行有效文本为准，重大决策请咨询执业律师"。
3. **对话模式引导（P1）**：`docs/对话模式推演引导.md`——不用命令行、纯聊天完成一次完整推演。
4. **规则库众筹（P2）**：`docs/规则库众筹指南.md` + Issue 模板「踩坑规则提交」，让 103 条滚雪球。
5. **海外合规图层（P2，实验性）**：`references/regulation-global.md`——GDPR/CCPA 方向性条目，出海场景叠加使用。

## 快速开始

### 方式 A：作为 WorkBuddy 技能（对话中使用）

```bash
# 一键安装（自动识别系统，装到 ~/.workbuddy/skills/，并跑一遍校验）
python scripts/install.py

# 只看会做什么、不动文件
python scripts/install.py --dry-run
```

手动安装（等价）：

```bash
cp -r fuzzy-reverse-flow ~/.workbuddy/skills/
# Windows PowerShell:
# New-Item -ItemType Junction -Path "$env:USERPROFILE\.workbuddy\skills\fuzzy-reverse-flow" -Target "F:\你的路径\fuzzy-reverse-flow"
```

安装后**新开一个会话**，说"我想做个 XX，帮我倒推需要什么条件"，技能就会按四阶段输出，并在结尾自动萃取规则。

### 方式 B：只用命令行

```bash
python scripts/rfe.py init                       # 初始化并导入 100+ 条种子规则
python scripts/rfe.py infer -t "做个小程序卖菜"   # 猜领域
python scripts/rfe.py recall -q "做个小程序卖菜"  # 召回红线
python scripts/rfe.py audit --plan my-plan.md --domain "电商平台"
python scripts/rfe.py pitfall recall -q "上线 备案"
```

知识库默认在 `~/.workbuddy/reverse-engine/`，可用 `RFE_KB` 环境变量改到任意位置（例如放进项目仓库做团队共享）。

---

## 内置完整案例（先看输出，再动手）

不想先啃方法论？直接看一份**真实推演输出**：输入只有一句「我想做一个娱乐小程序」，输出是一张含 **19 条合规红线、10 个死亡点、8 个里程碑**的逆向施工图，并把 3 条规则＋1 条坑卡沉淀进知识库待审区。

- 完整案例：[`examples/娱乐小程序-逆向施工图.md`](examples/娱乐小程序-逆向施工图.md)
- 案例索引（怎么读、对应哪些阶段与命令、怎么复现）：[`examples/README.md`](examples/README.md)

> 案例由 fuzzy-reverse-flow v1.3.0 真实运行输出整理而成，随包分发；文末附官方核实入口与 7 条免责声明。引用其中法规与金额前请按案例第 5 节逐条人工核实。

---

## 检测：四层验证，逐层有命令

装完不等于能用。按下面四层验，出问题能定位到具体一层。

### 第 1 层 · 结构（能不能被识别为技能）

```bash
python scripts/install.py --verify
```

检查项：`SKILL.md` 存在且 frontmatter 合法（`name` 必须与目录名一致）、`name` 只含小写字母与连字符、`description` 非空且含触发词、必备文件齐全（`LICENSE` / `PROVENANCE.md` / `kb_seed` / `scripts`）。

> 常见失败：`name: 模糊问题逆流程推理工具` —— **中文不能作为技能标识**，只能是描述文字。标识统一用 `fuzzy-reverse-flow`。

### 第 2 层 · 功能（逻辑对不对）

```bash
python scripts/selftest.py            # 19 项端到端断言，全程在临时库运行，不污染真实知识库
python scripts/selftest.py --verbose  # 失败时打印完整输出
```

覆盖：初始化、领域推断、召回排序、规则去重、第三方规则拒收、记坑与升级、好方案通过体检、坏方案被拦截（缺阶段/危险话术/红线未覆盖）、导出、统计。

### 第 3 层 · 原创性（能不能合法开源）

```bash
python scripts/provenance_check.py          # 8 项痕迹筛查
python scripts/provenance_check.py --strict # 提醒也算失败，发布前建议用这个
```

覆盖：非标准库依赖、第三方版权头 / SPDX、外链白名单、英文长句残留、HTML 复制痕迹、不可见字符、规则来源标注、必备声明文件。有异常返回退出码 1，可直接接 CI。

### 第 4 层 · 加载（WorkBuddy 是否真的认）

装好后**新开一个会话**，输入：

```
我想做一个面向 40 岁以上人群的零工招聘小程序，帮我倒推需要什么条件
```

预期表现：技能被自动唤起，输出包含"阶段一 目标锁定 / 阶段二 逆向硬性条件 / 阶段三 倒排期 / 阶段四 规则萃取"，且第二条红线涉及《人力资源服务许可证》。

没被唤起 → 检查技能名是否与目录名一致、`description` 里的触发词是否被你改短了、以及会话是否在安装**之前**就开着（技能列表在会话启动时加载）。

---

## 发布：打包成可分发件

```bash
python scripts/package.py                  # 生成 dist/<name>-v<version>.zip
python scripts/package.py --list           # 只列清单，不打包
python scripts/package.py --no-check       # 跳过前置检测（不推荐）
```

打包时自动：

- **包含** `examples/`（内置公开案例，真实推演输出整理，随包分发便于理解输出形态）；**排除** `.kb*`（本地知识库，含个人项目与踩坑记录）、`__pycache__`、`dist/`；
- 生成 `MANIFEST.txt`（逐文件 SHA256）与 `SHA256SUMS.txt`，便于接收方校验；
- 打包前自动跑第 1、2、3 层检测，不通过则拒绝出包；
- **可复现构建**：包内所有条目使用固定时间戳（1980-01-01），因此**内容相同必然得到相同的 SHA256**。同样的代码在任何人机器上打包都得到同一个校验值，校验值才有意义。

接收方验证：

```bash
sha256sum -c SHA256SUMS.txt      # macOS/Linux，解压后在技能根目录执行
certutil -hashfile <file> SHA256 # Windows 校验整包
```

> ⚠️ **Windows 解压注意**：包内 `templates/倒排期任务书.md`、`推演报告骨架.md` 为中文文件名（zip 已正确设置 UTF-8 标志位）。
> 请用**资源管理器双击**或 `Expand-Archive` 解压；**不要用 Git Bash（MSYS）自带的 `unzip`**——它按系统 GBK 解码，会把中文文件名变成乱码，导致 `sha256sum -c` 报 `No such file or directory`。这不是包坏了，是解压工具的问题。

---

## 命令表

| 命令 | 作用 | 典型用法 |
|---|---|---|
| `init` | 初始化知识库 + 导入种子 | `rfe.py init` |
| `infer` | 推断领域 | `rfe.py infer -t "开个奶茶店"` |
| `recall` | 召回规则（推演前必做） | `rfe.py recall -q "..." --top 8 --json` |
| `add` | 新增规则（文件或 stdin） | `rfe.py add --file card.json` |
| `pitfall add/recall/list` | 踩坑记忆 | `rfe.py pitfall recall -q "备案 上线"` |
| `audit` | 方案体检（可进 CI） | `rfe.py audit -p plan.md -d "招聘与人力"` |
| `stats` | 统计与最常命中 | `rfe.py stats` |
| `export` | 导出 md / json 共享 | `rfe.py export -F md -o rules.md` |
| `verify` | 更新核实状态 | `rfe.py verify --id RULE-ECOM-0001 --confidence high` |
| `doctor` | 知识库自检（重复 ID / 缺字段 / 超期） | `rfe.py doctor` |
| `migrate` | 知识库结构版本迁移（`--check` 只报告；默认执行并自动备份，只读种子库永不写入） | `rfe migrate --check` / `rfe migrate` |

---

## 内置知识库（种子库 103 条规则 / 13 个领域）

| 文件 | 领域 | 覆盖重点 |
|---|---|---|
| `kb_seed/10_common.json` | 通用 | 主体、ICP/公安/App 备案、PIPL、等保、算法备案、商标、支付、广告 |
| `20_ecommerce.json` | 电商平台 | ICP+EDI 双证、平台审核义务、二清、7 日无理由、价格欺诈、类目准入 |
| `30_media.json` | 内容与短剧 | 微短剧三档备案、片头备案号、AI 标识、改编权/音乐/字体、人格权 |
| `40_hr.json` | 招聘与人力 | 人力资源服务许可、网络招聘双证、账号核验、禁止向劳动者收费、就业歧视 |
| `50_edu.json` | 教育培训 | 学科/非学科分类、办学许可、教育广告、预付费监管、未成年人 |
| `60_health.json` | 医疗健康 | 互联网医院、首诊限制、药品信息服务、医疗广告、健康数据 |
| `70_food.json` | 餐饮食品 | 食品经营许可（含网络经营）、健康证、油烟消防、功效宣传 |
| `80_event.json` | 线下活动 | 1000 人安全许可、营业性演出、消防、票务、公众责任险 |
| `85_aigc.json` | AI 生成服务 | 算法备案/安全评估、显式+隐式标识、语料、声音肖像、推理成本 |
| `90_saas.json` | 软件与小程序 | 软著、开源许可证审计、上架隐私检测、SDK 披露、经营性判定 |
| `92_hardware.json` | 硬件制造 | CCC、SRRC、UN38.3、CE/FCC、FTO、产品责任 |
| `94_local.json` | 本地生活 | 上门服务核验、养老托育资质、预付卡 |
| `95_finance.json` | 金融与投资 | 投顾牌照、非法集资、LPR 4 倍、支付牌照、虚拟货币 |
| `99_misconceptions.json` | 全领域 | 12 条"常见误传"，专治用过时口径做规划 |

> 知识库是**通用认知 + 官方入口索引**，不是法律意见。每条都可被你自己的实践推翻：`verify` 更新、`status: deprecated` 保留历史。

---

## 设计原则

1. **不编造**：写不出准确许可名称，就写"名称待属地确认"并给官方入口，绝不虚构文号条款。
2. **可证伪**：每条规则带 `confidence` + `verified_at`，允许被更新、被废止。
3. **可执行**：只收"如果…那么必须…"，拒收"要注意合规"这类不可执行句。
4. **有主体**：每条都说明对个人 / 个体户 / 企业 / 平台中的谁成立。
5. **先商业后合规**：死亡点清单里至少两条必须是商业侧（没人用、没供给、没现金流）。
6. **零依赖可移植**：JSONL 存储，git 友好，团队可共享一份 `RFE_KB`。

---

## 开源与合规声明

- **许可证**：MIT。可商用、可修改、可再分发，保留版权声明即可。
- **零第三方代码**：仅使用 Python 标准库（12 个模块），无任何 pip 依赖，因此不牵涉 GPL/AGPL 传染或第三方署名义务。
- **原创边界（如实披露）**：代码、规则条目、模板、示例为独立撰写；**四阶段框架源自委托方提供的原始提示词**，由本项目扩写实现。完整溯源见 [`PROVENANCE.md`](PROVENANCE.md)。
- **法规引用**：仅引用法律法规、部门规章、国家标准的**名称与官方公开链接**。法规文本属《著作权法》第五条排除对象，引用不构成侵权；不摘录条文全文，不搬运第三方汇编的资质清单。
- **可验证**：运行 `python scripts/provenance_check.py` 自动核查依赖、版权痕迹、外链白名单、复制残留与规则来源标注；有异常返回退出码 1。
- **商标**：文中出现的"淘宝""微信""支付宝""抖音"等仅为**指示性举例**（说明业务形态），与相应权利人无任何关联、赞助或背书关系。
- **不构成法律意见**：本项目提供的是合规认知框架与核实路径，不能替代执业律师意见。涉及交易结构、股权、刑事风险，请咨询专业人士。
- **时效性**：监管口径变化频繁且各地执行有差异。所有 `confidence: medium/low` 条目及标记"待核实"的结论，落地前必须通过 `verify_url` 指向的官方渠道确认。

---

## 贡献

欢迎补充新领域与踩坑记录，格式见 `references/rule-schema.md`：

```bash
# 1. 新增领域：在 kb_seed/00_taxonomy.json 加 triggers
# 2. 新增规则：kb_seed/NN_<domain>.json，注意 severity 不要滥用 redline
# 3. 自测：python scripts/selftest.py
# 4. 体检示例：python scripts/rfe.py audit -p examples/娱乐小程序-逆向施工图.md -d "小程序"
```

取舍标准只有一条：**这条规则能让下一个人的方案少踩一个具体的坑吗？** 不能就不收。

---

## Roadmap

- [ ] `audit` 支持跨领域规则组合（如"电商 + AI 生成"叠加校验）
- [ ] 规则间冲突检测（同一场景两条规则结论相反时提示）
- [ ] 导出为 Markdown 知识库页面（供团队 wiki 使用）
- [ ] 时间线可视化（关键路径甘特图，输出 SVG）
- [ ] 多语言规则库（面向出海场景的 GDPR / CCPA 图层）

---

## 目录结构

```
fuzzy-reverse-flow/
├── SKILL.md                  # 技能主入口：四阶段铁律 + 输出模板
├── README.md
├── PROVENANCE.md             # 溯源与原创性声明（发布前必读）
├── LICENSE
├── CHANGELOG.md
├── references/               # 方法论文档
│   ├── stage1-target-locking.md
│   ├── stage2-requisites.md
│   ├── stage3-milestones.md
│   ├── stage4-evolution.md
│   ├── rule-schema.md
│   └── anti-patterns.md
├── kb_seed/                  # 种子规则库（JSON，每条带 source/provenance）
├── examples/                 # 内置公开案例（真实推演输出整理，随包分发）
│   ├── README.md             # 案例索引：怎么读、怎么复现
│   └── 娱乐小程序-逆向施工图.md
├── scripts/
│   ├── rfe.py                # 知识库 CLI（零依赖）
│   ├── install.py            # 一键安装 + 四层检测
│   ├── package.py            # 打包发布（自动排除私有内容）
│   ├── provenance_check.py   # 原创性自查
│   └── selftest.py           # 端到端自测（含原创性自查）
├── references/
│   └── rule.schema.json      # 规则/坑卡字段契约（JSON Schema）
└── templates/                # 报告骨架 / 倒排期 / 规则卡 / 坑卡
```

> **内置公开案例**（`examples/`，如娱乐小程序逆向施工图）为真实推演输出整理，无隐私信息，随仓库提交并随包分发。含真实项目与商业信息的**私有推演案例**（电商 App、招聘小程序）仍不随包发布，存放于仓库外的 `../fuzzy-reverse-flow-私有案例/`；自测不依赖任何案例文件。

---

MIT © 2026 张勇鑫 (Zhang Yongxin)

## 被编排（v1.2.0 起，v1.3.0 增强）

本技能可被 vague-to-product 的 `v2p plan` 经 `bridge.py` **单向调用**：v2p 负责追问与需求规格，本技能只提供合规红线、资源底线、风险与坑卡数据，不反向调用、不发起追问。两套工具仍可各自独立使用。

新增能力：`rfe add --pending` / `rfe pitfall add --pending`（沉淀先进待审区）→ `rfe pitfall pending-list / approve --id / reject --id` 人工审核转正；`rfe meta --set-review` 记录规则库季度复核时间戳（超 90 天 `stats` 会提示）。


---

## 附录 A · 知识库分层、待审区与版本迁移（v1.3.0 机制）

| 层 | 路径 | 权限 |
|---|---|---|
| **只读种子库** | `<技能目录>/kb_seed/*.json`（103 条规则 / 13 领域） | 随仓库分发，**任何命令都不写入** |
| **可写本地库** | `RFE_KB`，默认 `~/.workbuddy/reverse-engine` | `rules.jsonl` / `pitfalls.jsonl` / `pending.jsonl` / `rejected.jsonl` / `kb_meta.json` |

- WorkBuddy 与 Codex 等**多宿主共用同一份可写本地库**，故新沉淀一律先进 `pending.jsonl` 待审区，人工 `rfe pitfall approve --id` / `reject --id` 后才转正，防止多宿主并行写入污染知识库。
- 结构版本写入 `kb_meta.json` 的 `schema_version=2`（当前目标 **v2**）：v0 = v1.1.x 及更早（无元数据）；v1 = v1.2.0（三件套 + 复核时间戳）；v2 = v1.3.0（字段规范化、fingerprint 去重、季度复核分级、只读/可写库显式分层）。
- `rfe migrate --check` 只报告不写入；`rfe migrate` 执行迁移并自动备份为 `*.backup-v<旧版本>-<日期>.jsonl`，**只改结构不改语义**（补 `created_at` / `source` / `status` / `review` / `schema` / `severity` / `type` / `hit_count` / `verified_at`、规范化 ID、重算 fingerprint、按 fingerprint 去重）。
- 标准顺序：`rfe init` → `rfe migrate --check` → `rfe migrate` → `rfe doctor` → `rfe stats`。
- **环境变量与默认参数**（写代码 / 改配置以此为准）：`RFE_KB`（可写本地库，默认 `~/.workbuddy/reverse-engine`）、`RFE_SCRIPT`（v2p bridge 显式指定 rfe.py）、`V2P_HOME`（口味档案与 plans/ 报告，默认 `~/.workbuddy/v2p`）、`V2P_PROJECT`（多项目口味隔离）。完整清单见 `使用说明.txt` 第 2 节。

---

## 附录 B · 统一问题编码（消除两套工具告警重复）

| 前缀 | 所属 | 含义 | 全局编码示例 |
|---|---|---|---|
| `V2P-QG-*` | v2p | 交付质量闸门检查项（原短码 `QG-xxx`，等价全称 `V2P-QG-xxx`） | `V2P-QG-101` |
| `V2P-OR-*` | v2p | 编排层冲突 / 状态告警 | `V2P-OR-001` |
| `RFE-RL-*` | rfe | 规则库红线与阻断规则 | `RFE-RL-RULE-ECOM-0001` |
| `RFE-PT-*` | rfe | 踩坑记忆（坑卡） | `RFE-PT-PIT-0001` |
| `RFE-DR-*` | rfe | 知识库自检诊断 | `RFE-DR-001` |

四条硬规则：① 前缀全局唯一；② 编码幂等（已带前缀不再叠加）；③ 同一编码可跨节引用，但按报告末尾「问题编码索引（去重）」计数，红线节与资源底线节按编码集合去重过滤；④ `v2p gate` 仍输出短码 `QG-xxx`（自测依赖），报告引用时用全称。完整规范见 [`references/issue-codes.md`](references/issue-codes.md)。

固定诊断码：`RFE-DR-001` 重复 ID、`RFE-DR-002` 缺 `rule` 字段、`RFE-DR-003` 缺 fingerprint、`RFE-DR-101` 季度复核到期（91-180 天）、`RFE-DR-102` 过期规则（>180 天或无核实日期）、`RFE-DR-103` 法规类规则超 90 天未核实（短周期快更提醒）。

---

## 附录 C · 长期维护：季度复核机制

1. 每季度人工核对官方入口后执行 `rfe meta --set-review --note "..."` 记录复核日期。
2. `rfe doctor` 分级标记：法规类规则超 90 天 → `RFE-DR-103`（快更流程见 references/regulation-watch.md）；普通规则 91-180 天未核实 → `RFE-DR-101`；超过 180 天或无核实日期 → `RFE-DR-102`。
3. 逐条核实后执行 `rfe verify --id <ID> --confidence high`。
4. 每份输出报告强制附带知识库复核时间戳与 0.3 节完整免责声明。
5. 推广路径固定为：**自用提效 → GitHub 开源 Release**；拦截公开 SaaS，明确禁止公开 SaaS 产品化。

---

## 附录 D · GitHub Release 部署与发版校验

1. 从 GitHub Release 下载 `fuzzy-reverse-flow-v1.5.0.zip`，核对页面给出的 **SHA256**。
2. 解压到 `~/.workbuddy/skills/<技能名>/`（WorkBuddy）或 `~/.codex/skills/<技能名>/`（Codex CLI）；vague-to-product-v2.6.0.zip 需同级放置（或用 `RFE_SCRIPT` 指定）。
3. 执行 `python scripts/selftest.py`，应输出「全部通过」；再跑 `rfe init` → `rfe migrate --check`，完成 0.2 节 12 项自检。
4. 维护者发版固定顺序：**改代码 → 更新 README.md 与 使用说明.txt → `python _check_docs.py` → 组装发布包 → `python _check_docs.py --zip dist/<包名>.zip` → 提交推送 → 上传 / 替换 Release 附件**。两轮校验全部 PASS 才允许发版。

---

## 许可证 | License

本项目以 [MIT License](LICENSE) 开源。

> Copyright (c) 2026 张勇鑫 (Zhang Yongxin)
>
> 任何人可免费使用、修改、再分发（含商用），唯须保留上述版权与许可声明。
> 作者姓名「张勇鑫 (Zhang Yongxin)」为唯一署名，转载请勿删改。
