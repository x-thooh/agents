<!-- agents: scope=. parent= -->
# AGENTS.md

本文件是地图，不是手册。**阶段、顺序、门记录、交付物的唯一事实源是 `.harness/workflow/flow.json`**——
本文件不再抄一份阶段表，抄了就是第二个真相。流程正文（RACI/预期/执行/检查）在
`.harness/workflow/README.md`，判据在 `.harness/specs/`，状态在 `.harness/{deliverables,tasks,memory}/`。

## 命令

```bash
make init           # 装钩子（pre-commit + commit-msg），一次
make check          # 全量校验；0 ERROR 才可交付
make check-json     # 原始 JSON，便于 CI
make check-strict   # 示例数据 = ERROR；真实交付必须绿
make fix            # 自动修派生数据（目前只有 GUIDE001 索引），修完重跑
make selftest       # 每个 scope 的反向测试 + 提交消息检查的正反例
```

`--fix` 只动派生数据——重新生成一遍就能复原的东西。写证据、选版本、补理由一律不修：
脚本代劳等于伪造。前置条件是 git 工作区除目标文件外干净，否则退出码 2 且一个字都不改；
目标文件排除在外，所以「提交被拦 → `make fix` → 再提交」这条路走得通。

## 阶段路由

阶段列表、顺序、门记录文件名、每阶段交付物：读 `.harness/workflow/flow.json`。
结果状态机（哪些结果阻塞后续、每种结果必须带什么）：`.harness/workflow/transitions.json`。
门记录必填字段与账本位置：`.harness/workflow/contract.json`。

每个阶段由一个 scope 判定，scope 名写在该阶段的 `scopes` 字段里；跨阶段由 `gates` 判定。
当前 scope 清单：`scope=gates` `scope=requirements` `scope=design` `scope=dev` `scope=integration`
`scope=selftest` `scope=review` `scope=coherence` `scope=submission`；`scope=notes`；跨阶段 `scope=baseline`。

## 硬规则

每条规则要么有 scope 断言，要么标「无断言」并写强度来源。

1. 不得跳阶：前序阶段为 `reject` 或缺失时，后续阶段不得为 `pass`/`conditional`。`scope=gates`
2. 门记录字段取自 `workflow/contract.json` 的 `gate_fields`，`stage` 与 `process_version` 必须与 `flow.json` 一致。`scope=gates`
3. `pass`/`conditional` 必须有证据；`conditional` 必须有未过期例外（责任人 + 批准人 + 到期日）。`scope=gates`
4. `flow.json` 声明的每个交付物必须真实存在。`scope=gates`
5. 需求必须有唯一 ID、可测验收标准、优先级、目标版本；任务卡 1 到 `config.json.task_max_days` 人天，超限必须再拆且依赖可解析。`scope=requirements`
6. NFR 至少覆盖 performance / security / observability / compatibility，每项有指标和验证方法。`scope=requirements`
7. 方案文档至少提前 `config.json.doc_lead_business_days` 个工作日发出；评审参与方含 PO/Dev/QA/Arch；契约冻结需 FE/BE/QA 签字。`scope=design`
8. 覆盖率阈值（核心/非核心/新增代码）见 `config.json`，低于阈值即 ERROR。`scope=dev`
9. 单元测试 0 失败；CI/SAST/build 无阻断；commit 符合 `type(scope): subject` 并关联任务。`scope=dev`
10. 联调清单所有接口通过；字段/空值/枚举/边界/错误码/分页/鉴权/超时/重试/幂等/限流/降级/日志/trace 逐项验证。`scope=integration`
11. 自测清单执行率 100%、通过率达到 `config.json` 阈值、P0/P1 清零；提测准入条件在本阶段内联验证。`scope=selftest`
12. MR 行数上限与评审人数阈值见 `config.json`；超出需拆分或书面批准；作者不得自批。`scope=review`
13. E2E 链路走通；PRD 跟踪矩阵每条有证据；受影响存量回归通过；NFR 有验收报告。`scope=coherence`
14. 提测包 manifest 齐全；冒烟达到 `config.json` 阈值；版本 tag/commit/测试环境一致；QA 确认接收。`scope=submission`
15. 变更必须记录类型、影响、审批人、通知、重新基线、回滚；例外必须有责任人、理由、批准人、到期日，到期即 ERROR。`scope=gates`
16. 状态层三条：`tasks/board.json` 的 `stage` 必须在 `flow.json` 里、`status` 只能是 todo/doing/blocked/done；
    `memory/lessons.md` 每条必须有现象/根因/断言三段；`codebase-guide/index.json` 由 `scripts/gen_guide.py` 生成，
    人手改过即 ERROR。`scope=gates`
17. 提交消息符合 Conventional Commits 1.0.0，且**一个提交只做一件事**（正文行首以「顺带/另外/同时/此外」另起一件即为信号）。断言来源：`.harness/git-hooks/commit-msg`（`make init` 安装后强制）+ `tests/commit_msg.py` 正反例；它不在 verify 的 scope 里，且可被 `git commit --no-verify` 绕过——绕过口是明的，没装钩子时这条规则退化为人工纪律。钩子丢了执行位即 GATE008 ERROR（git 会静默跳过）。

18. 基线：老账记在 `.harness/baseline.txt`（四列，TAB 分隔），显式豁免记在
    `.harness/accepted.json`（理由 + 负责人 + 复查日期）。账本内降 WARN、账本外仍
    ERROR 且前缀「新欠」；豁免过期、账本格式坏、总数上升都是 ERROR。
    `scope=baseline`（跨阶段，最后跑）
20. 决策笔记：`.harness/specs/notes/{proposed,implemented,rejected}/` 下每篇必须被文档引用
    （孤儿笔记 = 写了没人读得到），且 `status:` 与所在目录一致（换状态用 `git mv`，
    只改字段会留下没有版本记录的错位）。`scope=notes`

## 人判项（无断言）

以下是机器判不了的，必须在门记录里由 A 角色签字，强度来源是人工评审：

- 需求是否真实解决用户问题、优先级是否合理。
- 技术方案是否合理、可维护、可演进。
- 代码可读性与设计质量。
- 业务链路是否真正自洽、PRD 是否被满足。
- 风险接受与例外理由是否成立。

## 目录地图

```text
AGENTS.md                        本文件（地图）
Makefile                         make init / check / check-json / check-strict / fix / selftest
.harness/baseline.txt           老账账本（四列；首版为空）
.harness/accepted.json          显式豁免（理由/负责人/复查日期，只减不增）
.harness/config.json             阈值（覆盖率、任务人天、MR 行数、冒烟通过率）
.harness/workflow/flow.json      阶段唯一事实源（顺序/门记录/交付物/scope）
.harness/workflow/transitions.json  结果状态机
.harness/workflow/contract.json  门记录必填字段、账本位置
.harness/workflow/README.md      流程正文（RACI / 预期 / 执行 / 检查）
.harness/specs/                  业务域规格（design.md 等）
.harness/deliverables/gates/     8 个阶段门记录
.harness/deliverables/artifacts/ 8 个阶段的机器可读证据
.harness/deliverables/ledgers/   变更账本、例外账本
.harness/deliverables/reports/   自测报告等产物
.harness/tasks/board.json        任务看板（还没做什么）
.harness/memory/lessons.md       踩坑记忆（现象/根因/断言）
.harness/memory/decisions.md     全仓级决策
.harness/codebase-guide/index.json  代码库索引（脚本生成，禁手改）
.harness/scripts/verify.py       调度器（注册表 / 排序 / 退出码 / --fix 编排）
.harness/scripts/scopes/         一个 scope 一个文件
.harness/scripts/gen_guide.py    生成 codebase-guide/index.json
.harness/scripts/check_commit.py 提交消息检查（Conventional Commits 1.0.0 + 一个提交一件事）
.harness/git-hooks/pre-commit    提交前跑 check（make init 安装）
.harness/git-hooks/commit-msg    提交消息门（同上；必须可执行）
.harness/stack-templates/        门记录与提测包模板
tests/reverse.py                 反向测试：每个 scope 至少一条违规样本
tests/commit_msg.py              提交消息检查器的正/反例
```

## 维护本文件

- 新增硬规则：同批在 `scopes/` 加断言，或在上面「人判项」写明强度来源；不许只写规则。
- 改阈值：先改 `.harness/config.json`，再改本文件与 `.harness/workflow/README.md`，最后跑 `make check`。
- 改阶段/产物：先改 `.harness/workflow/flow.json`，再改门记录与对应 scope；不要反过来。
- 改索引：跑 `python3 .harness/scripts/gen_guide.py`，不要手改 `index.json`。
- 本文件行数硬上限 150，由 `gates` scope 断言。
