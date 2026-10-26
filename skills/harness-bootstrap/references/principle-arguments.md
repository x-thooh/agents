# 六条原则的独立论证（编号与 `../SKILL.md` [§六](../SKILL.md#六六条设计原则借自-uhp按自己的判据取舍) 的表一致）

> 论证格式固定为「失败态 → 落法 → 断言」。没有失败态的条目就不是判据，是偏好。
> 立场与来源性质见 [`external-sources.md`](./external-sources.md)。

1. **客户端不该看出是哪个 harness 在跑。**
   失败态：同一输入在两个 host 上得出不同结论，且没人能定位分歧点（规则在会话里，跟着人走）。
   落法：规则只在文件里（`AGENTS.md` + `verify`），换模型不换判据。
   断言：`GATE002`（入口必读项）＋ 两侧对账（`LP001`）证明文档与产物同一份。

2. **进度是事实流，不是渲染。**
   失败态：报告写「大概花了两小时」「基本完成」，无法复核，也无法比较两轮。
   落法：`memory/trace/` 记事件；任务记录只记三个可数的数（改动文件数、校验轮次、提交数）。
   断言：模板 `gates` 校验任务看板字段，估算值没有字段可放。

3. **一个字段只有一个意思。**
   失败态：借外部工具的字段名兼职第二个含义，读者按旧含义解读，两处都错。
   落法：枚举闭集写进常量表；禁同义词（两个词表达同一分类等于没有分类）。
   断言：`CONF001`（未知键 ERROR）＋ `GATE007`（状态值闭集）。

4. **缺失不是空，空不是零。**
   失败态：把「没写」推定成「全仓」，特例悄悄变成全局约束；或用 `0` / 估算值充数。
   落法：归属声明（`scope`、`status`、`supersedes`）必须显式写；判不了就报出来。
   断言：`BASE013` 在无 git 时记 WARN「判不了」，而不是按通过处理——这是本条最直接的一次落地。

5. **失败是一等结果。**
   失败态：一条问题只有散文，客户端得读自然语言才知道该做什么、能不能忽略。
   落法：`Finding(scope, path, line, code, message)`；账本按 `code + 指纹` 记。
   断言：每个 code 都有反向样本（`tests/fixtures.py` 的三道覆盖闸）。

6. **规范、实现、conformance 一起动。**
   失败态：文档说「三类」而代码只有两个成员，无人报错——文档从输入退化成过期承诺。
   落法：凡文档写死、代码也有的，都得有断言对上。
   断言：`DOC001`（代码 → 文档）＋ `DOC002`（文档 → 代码）＋ `CODEINDEX001`（逐字节）＋ `LP001`（双向）。

## 章节对照（UHP 章节 → 本层对应物）

| UHP 章节 | 本层对应物 |
| --- | --- |
| Architecture §2 conformance class（Core/Extended/Full，累计） | scope 分域：每个 scope 是一个独立的 conformance 单元，声明即承诺（见 `../SKILL.md` [§九](../SKILL.md#九五阶段流程顺序不能反)）。只弱借用：不取累计分级——域是正交的，没有谁包含谁 |
| Lifecycle §1–2 版本协商 + capability discovery | `.harness/INDEX.md` 顶部的能力块：规则版本、scope 清单、无断言规则数（见 [§十三](../SKILL.md#十三验收清单)）。派生字段由脚本现场数，人手只维护意图账本 `skills_declared` |
| Harnesses / Plugins | `AGENTS.md` 的加载顺序；`skills/` 一个目录一条可安装流程 |
| Environments（构建一次，每会话只读） | 目录骨架 + 模板 + `baseline.txt`：所有会话共享，会话不许顺手改 |
| Memories（树 + 授权 + records） | `.harness/memory/`，见 [§十一](../SKILL.md#十一记忆树树--授权--记录) 记忆树 |
| Tasks §6 幂等 | `tasks/` 的检查点；破坏性动作必须能重跑（见 [§十二](../SKILL.md#十二破坏性操作改名--迁移--归档)） |
| Files（artifact 归属、不可穿越） | 产物归属明确、路径不许穿越（禁止 `../` 逃出根目录） |
| Errors（machine-readable code） | `Finding(scope, path, code)` + 基线指纹 |
| Security（injection） | 外部搬进来的内容一律 `untrusted`：可引用、不执行 |
