# 验收清单与规则↔断言对照

> 本文件从 `../SKILL.md` 拆出（§二.5：参考材料超过 100 行或反复查表用的，外置）。
> 正文中的 `§X` 指 `../SKILL.md` 的章节；需要精确跳转时读该文件的对应标题。

```bash
make init                # 目录/文件齐全、钩子已装
make check               # 全库回归，非零退出即有 ERROR
make check-json          # 原始计数，不看降级后的
```

**本 skill 自身的门禁**（改 SKILL.md 前后都要跑，0 ERROR 才算改完）：

```bash
python3 scripts/audit.py                  # 审本 SKILL.md
python3 tests/fixtures.py                 # 全部反向断言：每个 fixture 一件缺陷，code 精确对上
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal   # 正对照：0 ERROR 0 WARN
```

**期望清单只有一处**：`tests/fixtures.py` 的 `CASES` 表。它逐条写明每个 fixture 该报哪个 code，
跑 `make check` 时一起执行。这里不再抄一份——抄出来的第二份表迟早和第一份不一致，
而「表说某条规则有人守」这句话的信用就建立在这上面。新增 scope 时改那张表，不是改这里。

反向测试的断言集合：每个 fixture 只含一个缺陷，audit.py 对它各报且仅报一个 ERROR、code 精确对上——不是「某条规则报了」，是「这条规则报的」（§六 verify 规范：每个 scope 上线前跑一次反向测试）。audit.py 不审语义一致性（机器判不了），语义项由上表「判据」列标注为人判，按 §二.2 计入「无断言」并写明强度来源。

三项全过之外，人工核对两件事：

- 入口地图上的每个入口文件真实存在（覆盖断言是弱断言）
- 每条硬规则在断言表里有对应行，没有的在「只有流程、无断言」清单里

### 规则 ↔ 断言载体对照（**目标仓库侧**）

右栏是**目标仓库自己实现**的载体，不是本 skill 自带的：默认按「服务名 + `pkg` 等共有目录」划分 scope，
目标仓库可自行指定命名与划分。所以这张表是**给目标仓库抄的骨架**，不是本 skill 的验收清单——
把它当成本 skill 的自查表，会把「目标仓库还没建这个 scope」读成「本 skill 有人守」。

按 §二.2 自查：每条规则要么在这里有一行，要么在台面上写明「无断言」及强度来源。

| 规则组 | 断言载体 | 强度 |
| --- | --- | --- |
| skill 目录形状（`SKILL.md` + `references/` + `scripts/` + `agents/`；根下每个条目要么是标准四件，要么在 `EXTRAS` 里写明理由） | audit.py STRUCT001（近似拼写 `reference`/`script`/`agent` 与未声明条目）/ STRUCT002（`references/` 只放 `.md`，不建子目录）+ `tests/fixtures.py` 三例 | 强 |
| 基线记账与收敛（条数制 / 零基线 / accepted 只减不增 + 保质期） | audit.py BASE001/BASE003/BASE004 + verify `scope=baseline` | 强 |
| 规则集版本保质期（`rules_version` 90 天未重新确认即 ERROR；基线不设刷新日期字段） | audit.py VER001（提到它的那一行必须同时写明天数与到期行为） | 强 |
| references/*.md 里的跨文件 §X.Y 引用指向存在的章节/条目（断言坑 #12 的存在性半边） | audit.py XREFDOC001/XREFDOC002（改号/删节/外置后没跟着改；重排同号仍属人判） | 强（存在性半边）+ 人判（重排同号） |
| 入口覆盖链、指针存在性 | verify `scope=folders` | 强 |
| `description` 无流程摘要、有触发条件 | audit.py FM008/FM009（启发式：抓箭号与序号词，纯主题清单靠人判） | 机器+人判 |
| 决策 `scope` 值 ⊆ 已批准的模块清单（锚点可定位；proposed 严格、implemented 降级） | verify 发现器 + `modules-confirmed` + `scope=notes` | 强（必做反向测试） |
| 模块清单带 `modules-confirmed: <sha>`，且每条锚点全部命中 | verify 发现器（无指纹即 ERROR，防 AI 自悟入册） | 强 |
| 头五行齐全、`summary` ≤ 120 字、无多余字段 | verify `scope=notes` | 强 |
| `## 不显然之处` 段存在且非空 | verify `scope=notes`（空段机检，内容人判） | 机器+人判 |
| 规则编号 ↔ 断言表行 | verify `scope=harness` | 强 |
| verify 脚本规范（一 scope 一文件 / 首版只上有断言的 scope / 声明即承诺） | audit.py LAYOUT001（调度器体征：scope 专属正则常量 / `Finding` 构造 / 体量上限）+ 正对照 `fixtures/ok-minimal` | 机器+人判（适用面：只在 `<skill_dir>/scripts/audit.py` 存在时检查，不存在记 not_applicable，不冒充通过） |
| 交付前不自选加戏、预算留给收尾 | 人判（看 diff：多出来的阶段/交付物是不是需求里没有的） | **无断言**（人审 diff；曾在评测用例里守，该套件已删——§二.5 的额度规则不接受「跑不起来的断言」冒充断言） |
| 链接/锚点、裸路径 | verify `scope=links` | 强 |
| 枚举闭集（分类/状态/kind） | verify 常量表 | 强 |
| 语料位置 ↔ `Status:` 互校 | verify `scope=notes` | 强（必做反向测试） |
| 索引派生一致性 | verify 重新生成比对 | 强 |
| 额度（行数/篇数） | verify 常量 | 中 |
| discovery 双向对账 | verify `scope=skills` | 强 |
| 归档笔记的 `Archived:` 日期 = 该笔记移动当次提交的日期（归档是事件驱动，不设时间阈值） | 目标仓库 verify `scope=archive`（读 `git log`；本仓库 audit.py 明说不依赖 git，故不在此处实现） | 强（有版本控制时）；无 git 的仓库降级为人判并显式标注 |
| 决策理由是否仍成立 | 人判 | **无断言**（人审 diff） |
| 教训是否真能改变下次做法 | 人判 | **无断言**（人审） |

标「无断言」的行是本 skill 的待补项：要么补断言，要么在目标仓库的断言表里显式标「无断言」——不许既不补也不标。（不写行数：数出来的值和表必然一致，写死的数字迟早不一致——§二.8 禁人手索引。）

### 本 skill 自身守什么（`make check` 的全部内容）

上表右栏一个 scope 都不在本仓库里——本 skill 没有「自己的 verify」。它只有 `audit.py`：守
frontmatter 合规、目录形状、章节与条目引用存在性、相对链接存在性、调度器体征、基线/版本/账本
这几段**文本是否写全**，外加 §二.5 的两个 100 行上限（`SECT001` 单节 / `SECT002` 参考材料）。
一句话：**只判「规范写没写清」，不判「规范对不对」**。

后者没有断言：规则是否成立、模板是否兑现、目标仓库是否照做，全部是 §十 的人判项。
这是本 skill 的已知空洞，不是遗漏——写在这里，免得下次又有人从 `make check` 全绿推出「这套东西是对的」。

`.harness/INDEX.md` 顶部再放一块 discovery，等价于 UHP 的 `GET /v1/uhp`——接续旧任务的 agent 先读它，就知道这层哪些断言域已上线、哪些规则没人守、哪个技能声明了没装机。**这份文件由脚本生成**（手改即漂移，生成后比对不一致即 ERROR）：

```yaml
# 不声明 conformance 级别：只弱借用「声明即承诺」，不取 UHP 的累计分级
rules_version: YYYY-MM-DD     # 日期版本，不是 semver；90 天保质期
scopes_live: [harness, folders, schema, links]   # 已上线断言域，与 verify 的 scope 一一对应
scopes_todo: [notes]          # 未上线：声明即承诺，上线前不进 scopes_live
skills_declared: [flow-a, flow-b]   # 声明侧（人手维护），与 .harness/workflow/playbooks/ 双向对账
unanchored_rules: <脚本数出来的整数>   # 派生：脚本数断言表里「无断言」的行；写一个数字就是第二处真相
```

版本用日期，不承诺向后兼容（UHP 版本就是发布日期）：改一条约束就是新日期，存量内容不必回填。**到期行为**：`rules_version` 超过 90 天未重新确认（新日期 + 确认人）时 verify 报 ERROR——旧不等于错，但「没人再看它」必须报出来。这里**不放 `baseline` 日期**：零基线之后基线是空集，给空集盖刷新日期是自指矛盾（旧机制遗留字段，已删）。

块内字段分两类，维护方式不同：**派生**（脚本现场数，手写即漂移，整块走「重新生成后逐字节比对」）——`scopes_live`/`scopes_todo`（来自 verify 注册表）、`unanchored_rules`（数断言表里「无断言」的行）；**人手维护**（意图账本）——`skills_declared`（与 `.harness/workflow/playbooks/` 双向对账）。派生字段不准人填数：数出来的值和表必然一致，写死的数字和表迟早不一致，而后者就是「INDEX 说哪条规则没人守」这句话失去信用的地方。
