# 本 skill 自身守什么（`make check` 的全部内容）

> 本文件只管一件事：**这个仓库自己怎么验自己**。目标仓库该把规则挂到哪个载体上，在
> [`acceptance.md`](./acceptance.md)。正文中的 `§X` 指 `../SKILL.md` 的章节。


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

### 本 skill 自身守什么（`make check` 的全部内容）

上表右栏一个 scope 都不在本仓库里——本 skill 没有「自己的 verify」。它只有 `audit.py`：守
frontmatter 合规、目录形状、章节与条目引用存在性、相对链接存在性、调度器体征、基线/版本/账本
这几段**文本是否写全**，外加 §二.5 的两个 100 行上限（`SECT001` 单节 / `SECT002` 参考材料）。
一句话：**只判「规范写没写清」，不判「规范对不对」**。

后者没有断言：规则是否成立、模板是否兑现、目标仓库是否照做，全部是 §十 的人判项。
这是本 skill 的已知空洞，不是遗漏——写在这里，免得下次又有人从 `make check` 全绿推出「这套东西是对的」。

`.harness/INDEX.md` 顶部再放一块 discovery，等价于 UHP 的 `GET /v1/uhp`——接续旧任务的 agent 先读它，就知道这层哪些断言域已上线、哪些规则没人守、哪个技能声明了没装机。**这份文件由脚本生成**（手改即漂移，生成后比对不一致即 ERROR）：

```yaml
