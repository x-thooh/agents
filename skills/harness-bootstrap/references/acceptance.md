# 验收清单与规则 ↔ 断言载体对照（目标仓库侧）

> 本文件只管一件事：**目标仓库该把每条规则挂到哪个断言载体上**。本 skill 自己怎么验自己，
> 在 [`self-gates.md`](./self-gates.md)——两张表读者不同、用途不同，放一个文件里读者每次都要先
> 分辨自己在看哪一张。正文中的 `§X` 指 `../SKILL.md` 的章节。

## 规则 ↔ 断言载体对照

右栏是**目标仓库自己实现**的载体，不是本 skill 自带的：默认按「服务名 + `pkg` 等共有目录」划分 scope，
目标仓库可自行指定命名与划分。所以这张表是**给目标仓库抄的骨架**，不是本 skill 的验收清单——
把它当成本 skill 的自查表，会把「目标仓库还没建这个 scope」读成「本 skill 有人守」。

按 §二.2 自查：每条规则要么在这里有一行，要么在台面上写明「无断言」及强度来源。

**要核「每条硬规则都有一行」先得有完整 code 清单**：本 skill 实现里的全部 code（含 scope 与级别）在 [`code-index.md`](./code-index.md)。它由 `python3 scripts/gen_code_index.py` 生成，`codeindex` scope 会重新生成一遍做逐字节比对——手改即 ERROR。所以清单不会漂；漂了就会被拦。

| 规则组 | 断言载体 | 强度 |
| --- | --- | --- |
| skill 目录形状（`SKILL.md` + `references/` + `scripts/` + `agents/`；根下每个条目要么是标准四件，要么在 `EXTRAS` 里写明理由） | audit.py STRUCT001（近似拼写 `reference`/`script`/`agent` 与未声明条目）/ STRUCT002（`references/` 只放 `.md`，不建子目录）+ `tests/fixtures.py` 三例 | 强 |
| 基线机制写全了（条数制 / 逐条 / 零基线 / accepted / 只减不增 / 保质期 / 到期行为） | audit.py BASE001/BASE003/BASE004（只判正文有没有写全） | 强（文本） |
| 基线机制真的在跑（账本格式 / 豁免过期 / 总数上升 / 可刷新；账本内降 WARN、账本外仍 ERROR） | 模板 verify 的 `scope=baseline`：BASE011 / BASE012 / BASE013 / BASE014 | 强（执行）+ 人判（指纹是否抹对了） |
| 规则集版本保质期（`rules_version` 90 天未重新确认即 ERROR；基线不设刷新日期字段） | audit.py VER001（提到它的那一行必须同时写明天数与到期行为） | 强 |
| references/*.md 里的跨文件 §X.Y 引用指向存在的章节/条目（断言坑 #12 的存在性半边） | audit.py XREFDOC001/XREFDOC002（改号/删节/外置后没跟着改；重排同号仍属人判） | 强（存在性半边）+ 人判（重排同号） |
| 「每条硬规则在断言表里有对应行」有人核得动 | audit.py CODEINDEX001（`references/code-index.md` 与源码逐字节一致；`make code-index` 重生成） | 强（清单本身）+ 人判（行到底对应得对不对） |
| 模板装到真仓库后仍然诚实（示例会被拦、`go_src` 还在扫 sample 会被点名） | `make check-boot`（`tests/template_boot.py`：拷进临时空仓库 → 验退出码与正文，含一次假绿灯的回归） | 强 |
| `config.json` 的键名拼错不会被静默忽略 | 模板 `conf` scope CONF001（未知键 ERROR，键名闭集在 `conf.py` 的 `ALLOWED`） | 强 |
| 入口覆盖链、指针存在性 | verify `scope=folders` | 强 |
| `description` 无流程摘要、有触发条件 | audit.py FM008/FM009（启发式：抓箭号、序号词与交付物清单；纯主题清单靠人判） | 机器+人判 |
| 决策 `scope` 值 ⊆ 已批准的模块清单（锚点可定位；proposed 严格、implemented 降级） | verify 发现器 + `modules-confirmed` + `scope=notes` | 强（必做反向测试） |
| 模块清单带 `modules-confirmed: <sha>`，且每条锚点全部命中 | verify 发现器（无指纹即 ERROR，防 AI 自悟入册） | 强 |
| 头五行齐全、`summary` ≤ 120 字、无多余字段 | verify `scope=notes` | 强 |
| `## 不显然之处` 段存在且非空 | verify `scope=notes`（空段机检，内容人判） | 机器+人判 |
| 规则编号 ↔ 断言表行 | verify `scope=harness` | 强 |
| verify 脚本规范（一 scope 一文件 / 首版只上有断言的 scope / 声明即承诺） | audit.py LAYOUT001（调度器体征：scope 专属正则常量 / `Finding` 构造；体量归 BUDGET001）+ 正对照 `fixtures/ok-minimal` | 机器+人判（适用面：只在 `<skill_dir>/scripts/audit.py` 存在时检查，不存在记 not_applicable，不冒充通过） |
| 交付前不自选加戏、预算留给收尾 | 人判（看 diff：多出来的阶段/交付物是不是需求里没有的） | **无断言**（人审 diff；曾在评测用例里守，该套件已删——§二.5 的额度规则不接受「跑不起来的断言」冒充断言） |
| 链接/锚点、裸路径 | verify `scope=links` | 强 |
| 枚举闭集（分类/状态/kind） | verify 常量表 | 强 |
| 语料位置 ↔ `Status:` 互校 | verify `scope=notes` | 强（必做反向测试） |
| 索引派生一致性 | verify 重新生成比对 | 强 |
| 额度（行数/篇数） | 常量住在 `scripts/scopes/common.py`；本仓库由 audit.py SECT001/SECT002（单节与单文件 80/100）、BUDGET001（代码 150/200，含调度器；**只覆盖 `scripts/`**，`templates/` 与 `tests/` 不在内——见 `doc-budgets.md`，该部分**无断言**）、BUDGET002（SKILL.md 总量 400/500）守 | 中（覆盖范围内强 / 范围外无断言） |
| discovery 双向对账 | verify `scope=skills` | 强 |
| 归档笔记的 `Archived:` 日期 = 该笔记移动当次提交的日期（归档是事件驱动，不设时间阈值） | 目标仓库 verify `scope=archive`（读 `git log`；本仓库 audit.py 明说不依赖 git，故不在此处实现） | 强（有版本控制时）；无 git 的仓库降级为人判并显式标注 |
| 围栏代码可执行（无占位符 U+2026、`bash -n` 通过） | audit.py BASH001 / BASH002 | 强 |
| 提了基线就要有基线小节 | audit.py BASE002 | 中 |
| 宿主加载实测（承诺分层入口前必须先实测宿主真读子目录） | audit.py HOST001 / HOST002 | 强 |
| 双向对账的两侧各点名一个载体（否则是派生品自比较） | audit.py DUAL001 | 强 |
| frontmatter 齐全且合法（有 frontmatter / name / name 形状 / 有 description / 非空 / 长度 ≤ 1024 / 字段表外） | audit.py FM001 / FM002 / FM003 / FM004 / FM005 / FM006 / FM007（FM008/FM009 见上） | 强 |
| 文件内 `§X` / `§X.Y` 引用指向存在的章节/条目 | audit.py XREF001 / XREF002 | 强 |
| 外部链接：内联=承诺可查，脚注=引用不查 | audit.py LINK001（未检查）/ LINK002（4xx）/ LINK003（不可达降级）/ LINK004（相对链接必须存在）；外部三条需 `--check-links` 才真跑，相对链接离线强断言 | 强（相对）+ 中（外部） |
| 布局表 ↔ 模板双向对账（表为根，产物不得反向定义规范） | audit.py LP001 / LP002 / LP003 | 强 |
| 规范用语：`scope 分域` 不是分级 | audit.py SCOPE001 | 强 |
| **文档描述必须与代码一致**，两个方向 | audit.py DOC001（代码里的每个 code 本文档都要有行）+ DOC002（本文档与 SKILL.md 点名的 code 必须真存在，幻影即 ERROR；行写得对不对仍人判） | 强（覆盖 + 幻影）+ 人判（对应） |
| **提交是最小不可分割单位**（一个提交一件事，不合并多功能） | 两套模板的 `check_commit.py` CM006（行首并列连接词启发式；句中不算），由 `.harness/git-hooks/commit-msg` 强制、`tests/commit_msg.py` 正反例守；钩子丢执行位即 GATE008 | 机器（启发式 + 钩子）+ 人判（两处改动算不算一件事）；`git commit --no-verify` 可绕过，绕过口是明的 |
| 决策理由是否仍成立 | 人判 | **无断言**（人审 diff） |
| 教训是否真能改变下次做法 | 人判 | **无断言**（人审） |

标「无断言」的行是本 skill 的待补项：要么补断言，要么在目标仓库的断言表里显式标「无断言」——不许既不补也不标。（不写行数：数出来的值和表必然一致，写死的数字迟早不一致——§二.8 禁人手索引。）


### 目标仓库的 discovery 块（`.harness/INDEX.md` 顶部）

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

