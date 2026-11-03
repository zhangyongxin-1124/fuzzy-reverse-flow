# 内置完整案例（examples/）

> 这里放**随包分发的公开推演案例**：由 fuzzy-reverse-flow 真实运行输出整理而成，
> 用来在动手之前先看懂"本工具到底输出什么、输出到什么深度"。
> 私有推演案例（含真实项目与商业信息的）仍在仓库外，不进本目录、不随包发布。

## 当前收录

| 案例 | 输入原话 | 结论档位 | 一句话看点 |
|---|---|---|---|
| [娱乐小程序-逆向施工图.md](娱乐小程序-逆向施工图.md) | 「我想做一个娱乐小程序」 | 黄灯 | "娱乐"两个字下面藏着三条红线条数差 5 倍的路线；最硬的门槛不是技术，是**主体类型注册后不可变更** |

## 怎么读这份案例（对照工具的四阶段）

| 案例章节 | 对应阶段 | 对应方法论文档 | 典型命令 |
|---|---|---|---|
| 1. 阶段一 · 目标锁定 | 八维锁定表 + 伪需求四问 + 待拍板变量 | `references/stage1-target-locking.md` | `rfe infer` / `rfe recall` |
| 2. 阶段二 · 逆向硬性条件反推 | 路线对照 + 合规红线表（R1-R19）+ 资源底线 + 死亡点清单 | `references/stage2-requisites.md` | `rfe recall --severity redline` |
| 3. 阶段三 · 倒排期任务书 | 里程碑 M0-M7 + 关键路径 + 今天 24 小时清单 + 降级路线 | `references/stage3-milestones.md` | （由模型按模板产出） |
| 4. 阶段四 · 规则萃取 | RULE-* / PIT-* 入库 + 待审区转正回执 | `references/stage4-evolution.md` | `rfe add --pending` / `rfe pitfall approve --id` |
| 5. 免责与核实清单 | 官方核实入口 + 7 条免责声明（输出强制附带） | README「零、」0.3 节 | — |

## 复现这份案例

```bash
# 1) 初始化知识库（103 条种子规则 / 13 领域）
python scripts/rfe.py init

# 2) 召回娱乐 / 小程序 / UGC 相关红线
python scripts/rfe.py recall --query "我想做一个娱乐小程序" --top 5

# 3) 用你的 AI 宿主（能力档 A）按 SKILL.md 四阶段输出施工图，
#    并把 4.1 节的 3 条规则 + 1 条坑卡沉淀进待审区：
python scripts/rfe.py add --file rule-SASS-0001.json --pending
python scripts/rfe.py pitfall add --pending
python scripts/rfe.py pitfall pending-list
python scripts/rfe.py pitfall approve --id RULE-SASS-0001
```

> 提示：案例中的法规、平台规则与金额均为 2026-11-03 时点的经验值，
> 引用前请按案例第 5 节的官方入口逐条人工核实。
