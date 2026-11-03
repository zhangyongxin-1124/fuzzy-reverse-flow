# Changelog

本项目遵循语义化版本。格式参考 Keep a Changelog。

## [1.3.0] - 2026-11-03

> 主题：**知识库版本迁移 + 只读/可写库分层 + 季度复核分级 + 统一问题编码 + 完整免责 + GitHub Release。**

### Added（P0-3 / P1-3 / P2-1 / 长期维护）
- **`rfe migrate` 结构版本迁移**：`kb_meta.json` 写入 `schema_version`（目标 v2）；`--check` 只报告，默认执行并自动备份 `*.backup-v<旧版本>-<日期>.jsonl`；补齐字段、规范化 ID、重算 fingerprint、按 fingerprint 去重，**只改结构不改语义**。
- **只读种子库 / 可写本地库显式分层**：`kb_seed/*.json` 随仓库分发且任何命令都不写入；`RFE_KB`（默认 `~/.workbuddy/reverse-engine`）是唯一写入目标。多宿主共用可写库 → 待审区机制成为必需。
- **`rfe doctor` 季度复核分级**：91–180 天未核实 → `RFE-DR-101`；>180 天或无核实日期 → `RFE-DR-102`；结构问题统一带 `RFE-DR-001/002/003` 编码。
- **统一问题编码**：`V2P-QG / V2P-OR / RFE-RL / RFE-PT / RFE-DR` 前缀表与四条硬规则，规范见 `references/issue-codes.md`；消除两套工具告警重复。
- **完整免责声明 7 条 + 知识库复核时间戳**：README「零、」章节、新增 `使用说明.txt` 与每份输出报告强制附带。
- **三档能力边界 A/B/C 与 12 项调用前自检清单**：写入 README 显著位置，明确网页聊天 / 手机只能降级到 C 档。
- **禁止公开 SaaS 条款**：允许自用与内网环回复用，禁止公开 SaaS 产品化、对外经营性 API、面向不特定公众的付费服务；P2-3 简易 MCP Server 本期不实施。
- **GitHub Release ZIP**：`fuzzy-reverse-flow-v1.3.0.zip` 带 SHA256。
- **`_check_docs.py` 发版校验**（含 `--zip` 包内文档比对）。
- **内置完整案例 `examples/`**：`娱乐小程序-逆向施工图.md`（v1.3.0 真实推演输出整理，输入「我想做一个娱乐小程序」，含 19 条合规红线、10 个死亡点、8 个里程碑与规则萃取回执）与案例索引 `README.md`；`package.py` 改为随包分发 examples/（无隐私信息），`.gitignore` 同步放开，`_check_docs.py` 新增案例一致性断言。

### Changed
- 命令表新增 `migrate`；自测新增 6 项迁移/编码断言（25 项全部通过）。
- README 新增「零、」必读章节与附录 A–D；修正「内置知识库」「被编排」历史版本标题。
- `使用说明.txt` 新建，与 README 同为发版必检文档。

## [1.2.0] - 2026-11-03

> 主题：**被编排 + 待审区 + 复核时间戳：从单机工具变成可被 v2p 调用的能力层。**

### Added
- **编排契约**（SKILL.md「编排契约」节）：本技能只工作在推演模态（少问多推）；被 `v2p plan` 经 bridge.py 单向调用时只提供数据，不反向调用 v2p、不发起追问。单独使用能力保留不变。
- **待审区**：`rfe add --pending` / `rfe pitfall add --pending` 写入 `pending.jsonl`；`pitfall pending-list / approve --id / reject --id [--reason]` 审核流转，approve 按条目 kind 自动转正到规则库或坑库，reject 归档 `rejected.jsonl`。防止错误经验污染知识库。
- **知识库元数据**：`rfe meta --set-review [--note]` 记录复核时间戳；`stats` 显示待审数与复核时间戳（超 90 天提示 ⚠）。
- **`pitfall recall --json`**：供 v2p bridge 结构化消费。
- **复核时间戳初值**：2026-11-03（本轮改造时复核结构与种子来源）。

### Fixed
- 批量导入坑卡时同批条目 ID 全部相同的 bug（`next_id` 现在累计同批已加条目）。
- `_load_payload` 兼容 `{"pitfalls": [...]}` 载荷。

### Data
- 坑库冷启动：从 vague-to-product `assets/templates/冷启动坑卡.json` 回填 18 条真实项目踩坑（坑记录 0 → 19 条）。

## [1.1.1] - 2026-11-02

### Changed
- **著作权人明确化**：`LICENSE` 由占位写法 `Fuzzy Reverse Flow contributors` 改为真实权利人 **张勇鑫**（`Copyright (c) 2026 张勇鑫 (Zhang Yongxin)`）。同步更新 `README.md` 文末署名与 `PROVENANCE.md` 第 1 节说明。自此权属主体可直接用于维权举证。
- 仅署名变更，代码、规则库、命令与知识库路径**零改动**，已安装环境无需重装（目录联接方式改一处即生效；复制方式需重装以同步 LICENSE）。

### Fixed
- **打包结果不可复现**：`package.py` 原用 `z.write()` / `z.writestr()`，zip 会写入当前时间，同一份内容连续打包两次得到不同 SHA256，校验值形同虚设。改为固定时间戳（1980-01-01）写入，已验证两次打包校验值完全一致。
- **自查脚本误报自家署名**：`provenance_check.py` 把 CHANGELOG 中新增的 `Copyright (c) 2026 张勇鑫` 判为"第三方版权痕迹"并拒绝打包。新增 `SELF_HOLDERS` 白名单，只放行带本项目权利人的行（而非整文件豁免），并用 `Copyright (c) 2020 John Doe` 做负向验证，确认第三方版权仍能被拦截。
- README 发布章节补充：可复现构建说明、Windows 解压注意事项（MSYS `unzip` 会按 GBK 解码导致中文文件名乱码，应用资源管理器或 `Expand-Archive`）。
- **CLI 版本号漂移**：`rfe.py` 中 `VERSION = "1.0.0"` 硬编码，与 `SKILL.md` 的 1.1.1 不一致，`--help` 会显示旧版本。改为从 `SKILL.md` frontmatter 读取，此后只需改一处。
- **进入 PATH 的命令行入口**：新增 `~/bin/rfe`（bash/sh）与 `~/bin/rfe.cmd`（Windows）。`.cmd` 必须纯 ASCII——cmd.exe 按 GBK 解码批处理，中文注释会直接变成乱码命令；脚本内临时 `chcp 65001` 输出中文后再恢复原代码页。

## [1.1.0] - 2026-11-02

### 更名
- 技能更名为**模糊问题逆流程推理工具**（Fuzzy Reverse Flow），标识 `fuzzy-reverse-flow`。
  原 `reverse-fuzzy-engine` 的目录链接已摘除。内部代号 `rfe`、命令、知识库路径 `~/.workbuddy/reverse-engine` 全部保持不变，已有规则库无需迁移。
- 新目录名即新技能名，因此**必须重新安装**：`python scripts/install.py --force`。

### Added
- **`scripts/install.py`**：一键安装（复制 / 目录联接 / dry-run / 卸载）+ 四层检测的第 1 层结构校验。校验项含 frontmatter 合法性、`name` 必须为英文 slug 且与目录名一致、description 触发词数量、必备文件、CLI 可运行、种子规则条数。
- **`scripts/package.py`**：生成可分发 zip，自动排除 `examples/`、`.kb*`、`__pycache__`、`dist/`，并附 `MANIFEST.txt` 与 `SHA256SUMS.txt`；打包前强制跑结构校验 + 自测 + 原创性自查，任一失败即拒绝出包。
- README 新增「检测：四层验证」与「发布：打包成可分发件」两节，逐层给出命令、检查项与常见失败原因。

### Changed
- **私有案例隔离**：`examples/` 两个推演案例（含真实项目信息）移出技能目录至 `../fuzzy-reverse-flow-私有案例/`，`.gitignore` 与打包脚本双重排除。
- **自测不再依赖私有案例**：改为按种子规则库动态生成"满覆盖"夹具，规则增删后夹具自动跟随。这修掉一个致命问题——原来自测读 `examples/01`，别人 clone 后第一次跑必然失败。
- 依赖自查白名单补全标准库（`zipfile` 等），并区分"本地模块"与"第三方包"。

### Fixed
- **危险删除逻辑**：`install.py` 早期版本对 Windows junction 直接用 `shutil.rmtree`，卸载/覆盖安装会连带删掉源码目录。改为对 junction 用 `os.rmdir` 摘链，仅对真副本递归删除；卸载时额外检测目标是否指向源码并给出提示。
- `package.py` 的 `SHA256SUMS.txt` 原用 `name/rel` 全路径，接收方解压后无法直接 `-c` 校验，改为技能根相对路径。

## [1.0.1] - 2026-11-02

### 开源合规核查（无功能性变更）

应委托方要求，对 v1.0.0 全量核查"是否夹带他人开源内容"，结论：**未发现第三方代码或受版权文本**。同时补上"能自证"的机制。

### Added
- **`PROVENANCE.md`**：逐类声明内容归属——代码/文本/规则/模板/示例各自来源；如实披露四阶段框架源自委托方提供的原始提示词；说明法规名称引用为何不构成侵权（《著作权法》第五条）；附人工比对记录（与 `coopersimson96/reverse-engineer`、`zhaoxuya520/reverse-skill` 的关系判定）。
- **`scripts/provenance_check.py`**：可复跑的原创性自查器，8 项检查——非标准库依赖、第三方版权头/SPDX、外链白名单、≥60 字符英文散文残留、HTML/富文本残留、不可见字符、规则来源标注完整性、必备声明文件；`--json` 供 CI，`--strict` 把提醒也算失败。
- **规则来源字段**：103 条种子规则全部补 `source` / `provenance` / `upstream`，使"引用公有领域法规"与"复制他人汇编"可机器区分；schema 同步扩展。

### Changed
- README「原创性」表述从"全部原创"改为**如实分述**（原创范围 + 框架来源 + 可验证命令），避免过度声明。
- `LICENSE` 著作权人保留 `contributors` 写法；发布前如需署名主体，按 `PROVENANCE.md` 第 1 节提示替换。（已于 1.1.1 落实为「张勇鑫」）

### Fixed
- **隐私风险**：`.gitignore` 原未排除仓库内知识库目录，若把 `RFE_KB` 指向仓库，会把含个人项目规则与踩坑记录的库误提交。已补 `.kb/` `.kb*/` `kb_local/`。
- `provenance_check.py` 自检误报：扫描器把自身的检测正则判为"第三方版权痕迹"，已将自身与 `LICENSE`/`PROVENANCE.md` 列入豁免，并把中国版权保护中心域名加入白名单。

## [1.0.0] - 2026-11-02

### Added
- **四阶段引擎**：目标锁定（八维 + 伪需求四问）→ 逆向硬性条件（六层合规扫描 + 资源底线 + 死亡点）→ 里程碑倒排（关键路径 / 缓冲 / 降级路线）→ 自我演化（规则萃取 + 踩坑记忆）。
- **零依赖 CLI `rfe.py`**：`init / infer / recall / add / pitfall / audit / stats / export / verify / doctor` 十个子命令。
- **种子规则库 103 条 / 13 个领域**：通用、电商、内容与短剧、招聘与人力、教育培训、医疗健康、餐饮食品、线下活动、AI 生成服务、软件与小程序、硬件制造、本地生活、金融与投资。
- **常见误传专区**：12 条已被取消或从未成立的"行业常识"，用于纠偏（如已取消的互联网医疗保健信息服务审核、ICP 备案≠经营许可、开源可随意商用等）。
- **方案体检 `audit`**：四阶段完整性、推导句式数量、红线覆盖率（带场景适用性判断 + `--strict` 全量模式）、危险话术扫描（含否定语境识别）、免责提示检查；有红项返回退出码 1，可接入 CI。
- **可解释召回**：字符二元组 + 触发器 ×3 + 领域命中 ×2 + 历史命中数加权 + 跨领域降权 0.55，输出命中理由与核实状态。
- **规则时效管理**：`confidence` / `verified_at` / `status`，超 180 天由 `doctor` 标记待复核；废止规则召回时提示勿引用。
- **文档与模板**：`references/` 六份方法论、报告骨架、倒排期任务书、规则卡、坑卡、两个端到端示例（电商 App / 招聘小程序）。
- **端到端自测**：`scripts/selftest.py` 覆盖 16 项断言，全程在临时知识库运行。

### Design notes
- 知识库用 JSONL（一行一条），便于 git diff 与团队合并。
- 指纹去重（domain + rule 的 SHA1 前 16 位），重复写入自动累加 `hit_count` 而非产生副本。
- 规则 ID 形如 `RULE-ECOM-0001`，按领域分段编号，新增领域自动生成，不冲突。
- 所有法规引用只写名称 + 官方链接，不摘录条文；不构成法律意见。
