# 验收清单与规则↔断言对照

> 本文件从 `../SKILL.md` 拆出（§二.5：参考材料超过 100 行或反复查表用的，外置）。
> 正文中的 `§X` 指 `../SKILL.md` 的章节；需要精确跳转时读该文件的对应标题。

```bash
make init                # 目录/文件齐全、钩子已装
make check               # 全库回归，非零退出即有 ERROR
make check -- --json     # 原始计数，不看降级后的
```

**本 skill 自身的门禁**（改 SKILL.md 前后都要跑，0 ERROR 才算改完）：

```bash
python3 scripts/audit.py                                              # 审本 SKILL.md
python3 scripts/audit.py --skill-dir tests/fixtures/bad-frontmatter   # 反向测试，期待且仅期待 FM004
python3 scripts/audit.py --skill-dir tests/fixtures/bad-bash-block    # 期待且仅期待 BASH001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref          # 期待且仅期待 XREF001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref-table    # 期待且仅期待 XREF002（表格行也算条目）
python3 scripts/audit.py --skill-dir tests/fixtures/bad-description      # 期待且仅期待 FM008
python3 scripts/audit.py --skill-dir tests/fixtures/bad-description-trigger  # 期待且仅期待 FM009
python3 scripts/audit.py --skill-dir tests/fixtures/bad-relative-link  # 期待且仅期待 LINK004
python3 scripts/audit.py --skill-dir tests/fixtures/bad-baseline-rule  # 期待且仅期待 BASE001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-host-loading  # 期待且仅期待 HOST001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-dual-ledger  # 期待且仅期待 DUAL001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-scope-grading  # 期待且仅期待 SCOPE001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-zero-baseline  # 期待且仅期待 BASE003（零基线 / accepted / 只减不增）
python3 scripts/audit.py --skill-dir tests/fixtures/bad-expiry-decor  # 期待且仅期待 BASE004（豁免无保质期）
python3 scripts/audit.py --skill-dir tests/fixtures/bad-version-ungated  # 期待且仅期待 VER001（rules_version 无到期行为）
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref-ext  # 期待且仅期待 XREFDOC002（跨文件引用指向不存在的条目）
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal --dispatch tests/fixtures/bad-inline-scope/scripts/audit.py  # 期待且仅期待 LAYOUT001（实现塞回调度器）
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal   # 正对照：0 ERROR 0 WARN（没它就跟不上「检查器没跑」区分）
```

反向测试的断言集合：每个 fixture 只含一个缺陷，audit.py 对它各报且仅报一个 ERROR、code 精确对上——不是「某条规则报了」，是「这条规则报的」（§六 verify 规范：每个 scope 上线前跑一次反向测试）。audit.py 不审语义一致性（机器判不了），语义项由上表「判据」列标注为人判，按 §二.2 计入「无断言」并写明强度来源。

三项全过之外，人工核对两件事：

- 入口地图上的每个入口文件真实存在（覆盖断言是弱断言）
- 每条硬规则在断言表里有对应行，没有的在「只有流程、无断言」清单里

### 规则 ↔ 断言对照（一页纸）

按 §二.2 自查：每条规则要么在这里有一行，要么在台面上写明「无断言」及强度来源。

| 规则组 | 断言载体 | 强度 |
| --- | --- | --- |
| 基线记账与收敛（条数制 / 零基线 / accepted 只减不增 + 保质期） | audit.py BASE001/BASE003/BASE004 + verify `scope=baseline` | 强 |
| 规则集版本保质期（`rules_version` 90 天未重新确认即 ERROR；基线不设刷新日期字段） | audit.py VER001（提到它的那一行必须同时写明天数与到期行为） | 强 |
| reference/*.md 里的跨文件 §X.Y 引用指向存在的章节/条目（断言坑 #12 的存在性半边） | audit.py XREFDOC001/XREFDOC002（改号/删节/外置后没跟着改；重排同号仍属人判） | 强（存在性半边）+ 人判（重排同号） |
| 入口覆盖链、指针存在性 | verify `scope=folders` | 强 |
| `description` 无流程摘要、有触发条件 | audit.py FM008/FM009（启发式：抓箭号与序号词，纯主题清单靠人判） | 机器+人判 |
| 决策 `scope` 值 ⊆ 已批准的模块清单（锚点可定位；proposed 严格、implemented 降级） | verify 发现器 + `modules-confirmed` + `scope=notes` | 强（必做反向测试） |
| 模块清单带 `modules-confirmed: <sha>`，且每条锚点全部命中 | verify 发现器（无指纹即 ERROR，防 AI 自悟入册） | 强 |
| 头五行齐全、`summary` ≤ 120 字、无多余字段 | verify `scope=notes` | 强 |
| `## 不显然之处` 段存在且非空 | verify `scope=notes`（空段机检，内容人判） | 机器+人判 |
| 规则编号 ↔ 断言表行 | verify `scope=harness` | 强 |
| verify 脚本规范（一 scope 一文件 / 首版只上有断言的 scope / 声明即承诺） | audit.py LAYOUT001（调度器体征：scope 专属正则常量 / `Finding` 构造 / 体量上限）+ 正对照 `fixtures/ok-minimal` | 机器+人判（适用面：只在 `<skill_dir>/scripts/audit.py` 存在时检查，不存在记 not_applicable，不冒充通过） |
| 交付前不自选加戏、预算留给收尾 | 评测用例 `empty-bootstrap`（预算内产出可判分） | 机器（评测） |
| 链接/锚点、裸路径 | verify `scope=links` | 强 |
| 枚举闭集（分类/状态/kind） | verify 常量表 | 强 |
| 语料位置 ↔ `Status:` 互校 | verify `scope=notes` | 强（必做反向测试） |
| 索引派生一致性 | verify 重新生成比对 | 强 |
| 额度（行数/篇数） | verify 常量 | 中 |
| discovery 双向对账 | verify `scope=skills` | 强 |
| 归档笔记的 `Archived:` 日期 = 该笔记移动当次提交的日期（归档是事件驱动，不设时间阈值） | 目标仓库 verify `scope=archive`（读 `git log`；本仓库 audit.py 明说不依赖 git，故不在此处实现） | 强（有版本控制时）；无 git 的仓库降级为人判并显式标注 |
| 决策理由是否仍成立 | 人判 | **无断言**（人审 diff） |
| 教训是否真能改变下次做法 | 人判 | **无断言**（人审） |

标「无断言」的行是本 skill 的待补项：要么补断言，要么在目标仓库的断言表里显式标「无断言」——不许既不补也不标。（不写行数：数出来的值和表必然一致，写死的数字迟早不一致——§天 禁人手索引。）

`harness/INDEX.md` 顶部再放一块 discovery，等价于 UHP 的 `GET /v1/uhp`——接续旧任务的 agent 先读它，就知道这层哪些断言域已上线、哪些规则没人守、哪个技能声明了没装机。**这份文件由脚本生成**（手改即漂移，生成后比对不一致即 ERROR）：

```yaml
# 不声明 conformance 级别：只弱借用「声明即承诺」，不取 UHP 的累计分级
rules_version: YYYY-MM-DD     # 日期版本，不是 semver；90 天保质期
scopes_live: [harness, folders, schema, links]   # 已上线断言域，与 verify 的 scope 一一对应
scopes_todo: [notes]          # 未上线：声明即承诺，上线前不进 scopes_live
skills_declared: [flow-a, flow-b]   # 声明侧（人手维护），与 .harness/workflow/playbooks/ 双向对账
unanchored_rules: 3           # 派生：脚本数断言表里「无断言」的行，手写即漂移
```

版本用日期，不承诺向后兼容（UHP 版本就是发布日期）：改一条约束就是新日期，存量内容不必回填。**到期行为**：`rules_version` 超过 90 天未重新确认（新日期 + 确认人）时 verify 报 ERROR——旧不等于错，但「没人再看它」必须报出来。这里**不放 `baseline` 日期**：零基线之后基线是空集，给空集盖刷新日期是自指矛盾（旧机制遗留字段，已删）。

块内字段分两类，维护方式不同：**派生**（脚本现场数，手写即漂移，整块走「重新生成后逐字节比对」）——`scopes_live`/`scopes_todo`（来自 verify 注册表）、`unanchored_rules`（数断言表里「无断言」的行）；**人手维护**（意图账本）——`skills_declared`（与 `.harness/workflow/playbooks/` 双向对账）。派生字段不准人填数：数出来的值和表必然一致，写死的数字和表迟早不一致，而后者就是「INDEX 说哪条规则没人守」这句话失去信用的地方。
