<!-- agents: scope=. parent= -->
# AGENTS.md

本文件是地图，不是手册。**阶段、顺序、门记录、交付物的唯一事实源是 `.harness/workflow/flow.json`**——
本文件不抄阶段表。流程正文在 `.harness/workflow/README.md`，Go 规范与断言对照在
`.harness/specs/standards.md`，状态在 `.harness/{deliverables,tasks,memory}/`。

## 命令

```bash
make init           # 装钩子（core.hooksPath → .harness/git-hooks），一次
make init-lefthook  # 或用 lefthook 装同一批钩子；两套只装一套
make check          # 全量校验；0 ERROR 才可交付
make check-json     # 原始 JSON，便于 CI
make check-strict   # 示例数据 = ERROR；真实交付必须绿
make fix            # 自动修派生数据（目前只有 GUIDE001 索引），修完重跑
make lint           # 工具层：golangci-lint（需要 Go 工具链，可选）
make selftest       # 反向测试：每个 scope 至少一条违规样本 + 提交消息检查
```

提交消息按 Conventional Commits 1.0.0：`<type>[(scope)][!]: <描述>`，type ∈ feat/fix/docs/
style/refactor/perf/test/build/ci/chore/revert。由 `commit-msg` 钩子判，细则见
`.harness/specs/standards.md`「提交消息」一节。

`--fix` 只动派生数据——重新生成一遍就能复原的东西。写证据、选版本、补理由一律不修：
脚本代劳等于伪造。前置条件是 git 工作区除目标文件外干净，否则退出码 2 且一个字都不改；
目标文件排除在外，所以「提交被拦 → `make fix` → 再提交」这条路走得通。

## 阶段路由

阶段列表、顺序、门记录文件名、每阶段交付物：读 `.harness/workflow/flow.json`。
结果状态机：`.harness/workflow/transitions.json`；门记录必填字段与账本位置：`.harness/workflow/contract.json`。

每个阶段由一个或多个 scope 判定（写在 flow.json 的 `scopes` 字段），跨阶段由 `gates` 判定。
当前 scope 清单：`scope=gates` `scope=contract` `scope=design` `scope=layout` `scope=runtime`
`scope=impl` `scope=test` `scope=review` `scope=release`。

## 硬规则

每条规则要么有 scope 断言，要么标「无断言」并写强度来源。

1. 不得跳阶：前序阶段为 `reject` 或缺失时，后续阶段不得为 `pass`/`conditional`。`scope=gates`
2. 门记录字段取自 `workflow/contract.json` 的 `gate_fields`，`stage` 与 `process_version` 必须与 `flow.json` 一致。`scope=gates`
3. `pass`/`conditional` 必须有证据；`conditional` 必须有未过期例外。`scope=gates`
4. `flow.json` 声明的每个交付物必须真实存在。`scope=gates`
5. 接口必须声明方法、路径、请求、响应、错误码、幂等性；验收标准必须可测（given_when_then 或 measure）。`scope=contract`
6. NFR 至少覆盖 performance / observability / compatibility，每项有指标或验证方法。`scope=contract`
7. 方案必须写清包职责、依赖无环、每个决策的被否方案、失败模式（检测 + 缓解）。`scope=design`
8. 模块根有 `go.mod`；`go` 版本不低于 `config.json.go_version_min`；不许 `replace` 指向本地路径；`cmd/<服务>/main.go` 只装配且不超 `main_max_lines`。`scope=layout`
9. 导出符号必须有 doc 注释；接口方法数不超过 `max_interface_methods`。`scope=layout`
10. 库代码（非 `package main`）不许 `panic`、`log.Fatal`、`os.Exit`，不许自造 `context.Background()`/`TODO()`。`scope=runtime`
11. 包装错误必须用 `%w`；`if err != nil` 后直接 `return nil` 视为吞错。`scope=runtime`
12. `build`/`vet`/`lint` 必须 `pass`；源码不许 CRLF、行尾空白、空格缩进。`scope=impl`
13. 每个非 main 包必须有 `_test.go`；覆盖率与 `-race` 按 `config.json` 判定；benchmark 退化超 20% 即 ERROR。`scope=test`
14. MR 行数、评审人数按 `config.json`；超出需 `oversize_approved`；作者不得自批；意见必须全部 `closed`。`scope=review`
15. 发布：`tag` 必须是 `v<version>`；`env` ∈ {dev, gray, prod}；回滚三要素齐全；冒烟全绿；观察窗与错误率/p99 在阈值内。`scope=release`
16. 状态层三条：`tasks/board.json` 的 `stage` 必须在 `flow.json` 里、`status` 只能是 todo/doing/blocked/done；
    `memory/lessons.md` 每条必须有现象/根因/断言三段；`codebase-guide/index.json` 由 `scripts/gen_guide.py` 生成，
    人手改过即 ERROR。`scope=gates`
17. 钩子只有一份实现：`.harness/git-hooks/` 下的脚本必须有执行位（没执行位 git 静默跳过），
    `lefthook.yml` 只做调度、每条 job 委托给这些脚本，两边的 hook 集合必须一致。`scope=gates`
18. 提交消息符合 Conventional Commits 1.0.0；`specs/standards.md` 引用的断言代码必须真的存在。`scope=gates`

## 人判项（无断言）

以下是机器判不了的，必须在门记录里由 owner 签字，强度来源是人工评审：

- 需求是否真实解决用户问题、优先级是否合理。
- 方案取舍是否站得住（被否方案的理由是否成立）。
- 代码可读性与设计质量。
- 错误码语义是否与调用方约定一致。
- 灰度比例、观察窗与回滚触发条件是否匹配风险。

## 目录地图

```text
AGENTS.md                        本文件（地图）
Makefile                         make init / init-lefthook / check / fix / lint / selftest
.golangci.yml                    工具层配置（需 Go 工具链；与 specs/standards.md「工具层」同批改）
lefthook.yml                     可选钩子调度层，只委托 .harness/git-hooks/，不内联检查
.harness/config.json             阈值（覆盖率、main 行数、MR、发布观察窗）+ go_src
.harness/workflow/flow.json      阶段唯一事实源（顺序/门记录/交付物/scope）
.harness/workflow/transitions.json  结果状态机
.harness/workflow/contract.json  门记录必填字段、账本位置
.harness/workflow/README.md      流程正文（6 阶段：目的/输入/产物/检查）
.harness/specs/standards.md      Go 规范与断言对照表（含来源、工具层分工、未采纳项）
.harness/deliverables/gates/     6 个阶段门记录
.harness/deliverables/artifacts/ 6 个阶段的机器可读证据
.harness/deliverables/ledgers/   变更账本、例外账本
.harness/tasks/board.json        任务看板（还没做什么）
.harness/memory/lessons.md       踩坑记忆（现象/根因/断言）
.harness/memory/decisions.md     全仓级决策
.harness/codebase-guide/index.json  代码库索引（脚本生成，禁手改）
.harness/scripts/verify.py       调度器（注册表 / 排序 / 退出码 / --fix 编排）
.harness/scripts/scopes/         一个 scope 一个文件
.harness/scripts/gen_guide.py    生成 codebase-guide/index.json
.harness/scripts/check_commit.py 提交消息检查（Conventional Commits 1.0.0）
.harness/git-hooks/pre-commit    提交前跑 check（make init 安装）
.harness/git-hooks/commit-msg    提交消息门（同上；必须可执行）
.harness/stack-templates/        门记录模板
sample/                          示例 Go 模块（go_src；真实仓库改成 "."）
tests/reverse.py                 反向测试：每个 scope 至少一条违规样本
tests/commit_msg.py              提交消息检查器的正/反例
```

## 维护本文件

- 新增硬规则：同批在 `scopes/` 加断言，或在上面「人判项」写明强度来源；不许只写规则。
- 改阈值：先改 `.harness/config.json`，再改本文件与 `.harness/specs/standards.md`，最后跑 `make check`。
- 改阶段/产物：先改 `.harness/workflow/flow.json`，再改门记录与对应 scope；不要反过来。
- 改索引：跑 `python3 .harness/scripts/gen_guide.py`，不要手改 `index.json`（或直接 `make fix`）。
- 加钩子：脚本放 `.harness/git-hooks/`（记得 `chmod +x`），并在 `lefthook.yml` 加同名 job 委托它。
- 本文件行数硬上限 150，由 `gates` scope 断言。
