# go-dev-harness

> 本文件是**模板说明**，不是目标仓库的 README。拷进仓库时它叫 `TEMPLATE.md`，
> 就是为了不覆盖你原来的 `README.md`（早期版本叫 `README.md`，拷一次就把人家的覆盖了）。

Golang 软件开发工程师的业务 harness：把「接需求 → 定接口 → 设计 → 编码 → 测试 → 评审 → 发布」这条业务流
写成可执行的断言。与 `delivery-harness` 的区别：那套管**交付流程**（PRD、联调、提测），这套管
**一个 Go 研发每天在仓库里做的事**——代码形状、错误与并发纪律、测试与覆盖率、MR 与发布边界。
两套布局一致：`.harness/` 十件套。

## 内容

- `AGENTS.md`：入口、命令、16 条硬规则（每条带 scope 或「无断言」）、目录地图。
- `.harness/workflow/`：`flow.json`（阶段唯一事实源）、`transitions.json`（结果状态机）、
  `contract.json`（门记录字段与账本位置）、`README.md`（6 阶段流程正文，在 `workflow/` 下）。
- `.harness/config.json`：阈值（覆盖率、main 行数、MR、发布观察窗）+ `go_src`。
- `.harness/specs/standards.md`：Go 规范与断言对照表。
- `.harness/deliverables/`：`gates/` 门记录、`artifacts/` 证据、`ledgers/` 变更与例外。
- `.harness/tasks/board.json`、`.harness/memory/`、`.harness/codebase-guide/index.json`。
- `.harness/scripts/`：`verify.py` 调度器 + 一组 scope（一个 scope 一个文件，见 `scopes/`）+ `gen_guide.py`。
- `sample/`：能过全部断言的示例 Go 模块（`go_src` 指向它）。
- `tests/reverse.py`：每个 scope 一条违规样本，验证真的会报 ERROR。

## 使用

把本目录内容复制到目标 Go 仓库根目录（或只合并 `.harness/`、`AGENTS.md`、`Makefile`），然后：

1. 把 `.harness/config.json` 的 `go_src` 从 `"sample"` 改成 `"."`（你的模块根），删掉 `sample/`。
2. 按团队实际改阈值：覆盖率、`main_max_lines`、MR 行数、评审人数、发布观察窗。
3. 逐项替换 `example: true` 的证据为真实证据，最后跑 `python3 .harness/scripts/gen_guide.py` 刷新索引。

```bash
make init           # 装 pre-commit 钩子：提交前自动跑 check
make check          # 示例数据只产生 WARN；0 ERROR 即通过
make check-strict   # 示例数据按 ERROR 处理；替换真实证据后应变绿
make selftest       # 正对照 + 11 个反向测试
```

## scope 一览（一个 scope 一个文件）

| scope | 判什么 | 主要代码 |
| --- | --- | --- |
| `gates` | 流程契约（flow/transitions/contract）、门记录、交付物存在、账本、任务/记忆/索引 | GATE001–007、GUIDE001 |
| `conf` | `config.json` 自身的诚实性：键名拼错、示例标记、`go_src` 是否还指着模板自带的 `sample/` | CONF001、CONF002、EXAMPLE001 |
| `contract` | 接口六要素（方法/路径/请求/响应/错误码/幂等）、验收可测、NFR | CTR001–004 |
| `design` | 包职责、依赖无环、被否方案、失败模式 | DES001–004 |
| `layout` | `go.mod`、`cmd` 薄、包边界、导出符号 doc、接口大小 | LAY001–007 |
| `runtime` | panic/退出/丢链/吞错/自造 context/goroutine 收敛 | RUNT001–007 |
| `impl` | build/vet/lint 证据 + 源码卫生（CRLF、行尾空白、tab） | IMP001–004 |
| `test` | 每包有测试、覆盖率、race、benchmark 退化、跳过理由 | TST001–006 |
| `review` | MR 体量、评审人数、自批、意见闭环 | REV001–004 |
| `release` | 版本/tag 一致、回滚预案、冒烟全绿、观察窗 | REL001–005 |

## 设计边界

- 机器判：文件形状、字段、阈值、状态、依赖、词法可见的调用模式、索引与磁盘一致。
- 人判：需求价值、方案取舍、可读性、错误码语义、灰度风险；见 `AGENTS.md`「人判项（无断言）」。
- 不依赖 Go 工具链：verify 是纯 Python，`build/vet/lint/覆盖率/benchmark` 以证据文件记录。
- 反向测试与 scope 一一对应：新增 scope 必须同批加一条反向样本，否则该 scope 可能从上线起就没执行过。
