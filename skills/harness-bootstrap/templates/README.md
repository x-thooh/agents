# templates/

两套可拷贝的 harness 模板，布局统一为 `.harness/` 十件套。模板是「某个业务域的答案」，
不是通用解：拷进目标仓库后，把 `example: true` 的示例数据换成真实证据，把阈值改成团队实际值。

## 两套的区别

| 维度 | `delivery-harness/` | `go-dev-harness/` |
| --- | --- | --- |
| 管什么 | 一次需求的**交付流程**（跨角色） | 一个 Go 研发的**日常改动**（单角色） |
| 阶段 | 8：需求 → 方案 → 开发 → 联调 → 自测 → CR → 自洽 → 提测 | 6：契约 → 设计 → 编码 → 测试 → 评审 → 发布观察 |
| 判据对象 | 文档与证据齐不齐（PRD、任务卡、跟踪矩阵、联调清单、提测包） | 代码形状对不对（包布局、错误链、context、导出面、源码卫生） |
| scope 读什么 | 9 个全部读 `.harness/deliverables/` 的 JSON 证据 | 7 个读证据；`layout`、`runtime` 直接扫 `.go` 源码，`impl`/`test` 两边都看 |
| 谁签字 | PO / Dev / QA / Arch（RACI 分工） | 研发本人 + 评审人 |
| 出口 | 提测包 manifest + 冒烟报告，交给 QA | tag + 灰度比例 + 回滚预案 + 观察窗，直接对生产 |
| 典型阈值 | 任务 ≤3 人天、核心覆盖 60%、自测通过率 95% | main ≤80 行、覆盖 75/80、MR ≤400 行、观察窗 ≥30min |

**怎么选**：需求要经 QA、联调、提测 → `delivery-harness`；后端服务/库，自己写自己发 →
`go-dev-harness`。两套**不能直接叠加**——它们抢同一批路径（`AGENTS.md`、`.harness/workflow/`、
`.harness/scripts/`）。要合，只能选一套当骨架，把另一套的阶段写成 `workflow/flow.json` 里的附加阶段。

## 共同骨架（`.harness/` 十件套）

```text
AGENTS.md                       地图：命令 + 硬规则（每条带 scope 或「无断言」）+ 人判项 + 目录地图
.harness/workflow/              flow.json（阶段唯一事实源）+ transitions.json + contract.json + 正文
.harness/specs/                 业务域规格、规范与断言对照
.harness/deliverables/          gates/ 门记录、artifacts/ 证据、ledgers/ 账本、reports/ 报告
.harness/tasks/board.json       任务看板（还没做什么）
.harness/memory/                lessons.md（现象/根因/断言）+ decisions.md
.harness/codebase-guide/        index.json，由 scripts/gen_guide.py 生成，禁手改
.harness/scripts/               verify.py 调度器 + 一个 scope 一个文件 + gen_guide.py
.harness/git-hooks/             pre-commit：提交前跑 make check
.harness/stack-templates/       门记录与产物骨架
.harness/config.json            单一根配置（阈值、模块根）
tests/reverse.py                每个 scope 一条违规样本 + --fix 的四条边界样本
Makefile                        init / check / check-json / check-strict / fix / selftest
```

五条一致的约定：`example: true` 的示例数据在 `--strict` 下判 ERROR；退出码 0 = 无 ERROR；
反向测试与 scope 一一对应，新增 scope 必须同批加一条；**阶段只写在 `flow.json`，脚本与散文都不许再抄一份**；
**`--fix` 只修派生数据**（可修清单与断言同住 `FIXERS`），且前置条件按目标文件排除——
否则「提交被拦 → fix → 再提交」会被自己的前置条件卡死。

## 加第三套模板

1. 复制任一套做骨架，保留上面十件套的形状。
2. 换 `.harness/config.json` 的阈值，换 `workflow/flow.json` 的阶段与 `version`。
3. 重写 `scopes/`：**只写能机器判的**，判不了的进 `AGENTS.md` 的「人判项」。
4. 每个 scope 配一条 `tests/reverse.py` 样本，跑 `make selftest` 全绿再交付。
5. 在本文件的「两套的区别」表里加一列——这张表是选型入口，不加等于没人知道它存在。
