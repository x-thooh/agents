# Go 工程规范（可机检部分）

每条规范对应一个 scope 代码；改规范必须同批改断言，否则这条规范会静默失效。
「来源」列写的是这条规范的权威出处——**没有出处的规范就是个人偏好，得标「本项目」并给理由**。

| 标记 | 出处 |
| --- | --- |
| `EG` | [Effective Go](https://go.dev/doc/effective_go) |
| `CR` | [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) |
| `UB` | [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md) |
| `PL` | [golang-standards/project-layout](https://github.com/golang-standards/project-layout) |
| `CC` | [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) |
| `GL` | [golangci-lint 配置](https://golangci-lint.run/docs/configuration/file/) |
| `LH` | [lefthook 配置](https://lefthook.dev/configuration/) |

## 模块与包边界

| 规范 | 判据 | 代码 | 来源 |
| --- | --- | --- | --- |
| 模块根有 `go.mod`，`go` 版本不低于阈值 | `go_version_min` | `LAY001` `LAY002` | `PL` + 本项目阈值 |
| 不许 `replace` 指向本地路径 | `=> ./`、`=> ../` | `LAY003` | 本项目：本地路径让构建不可复现 |
| 入口只在 `cmd/<服务>/main.go`，只做装配 | 行数 ≤ `main_max_lines` | `LAY004` | `PL`（cmd）+ 本项目阈值 |
| 业务代码不进 `cmd/` | `cmd/` 下必须 `package main` | `LAY005` | `PL` |
| 导出符号有 doc 注释，首行以符号名开头 | 紧邻 `// Name ...` | `LAY006` | `CR` Doc Comments / `EG` |
| doc 注释以句号结尾 | 末行 `.` 或 `。` | `LAY012`（WARN） | `CR` Comment Sentences |
| 接口小 | 方法数 ≤ `max_interface_methods` | `LAY007`（WARN） | `CR` Interfaces + 本项目阈值 |
| receiver 不用 `this`/`self`/`me`，同类型一个名字 | `func (c *T)` 聚合后判 | `LAY008` | `CR` Receiver Names |
| 同一类型不混用指针/值 receiver | 按类型聚合 | `LAY009` | `CR` Receiver Type |
| 包注释紧贴 `package` 子句 | 中间无空行 | `LAY010` | `CR` Package Comments |
| 不要 `src/` 目录 | 存在即报 | `LAY011` | `PL` Directories You Shouldn't Have |

包边界怎么定：**按变化原因分，不按技术层分**。`internal/order` 变是因为业务规则变；
`internal/httpapi` 变是因为协议变。两者混在一起时，协议改动会牵动业务测试。

## 错误处理

| 规范 | 判据 | 代码 | 来源 |
| --- | --- | --- | --- |
| 库代码不 `panic` | 非 main 包出现 `panic(` | `RUNT001` | `UB` Don't Panic |
| 库代码不退出进程 | `log.Fatal(`、`os.Exit(` | `RUNT002` | `UB` Exit in Main |
| 包装保留错误链 | `fmt.Errorf` 带 err 必须带 `%w` | `RUNT003` | `UB` Errors |
| 不吞错 | `if err != nil { return nil }` | `RUNT004` | 本项目：`CR` Indent Error Flow 只管缩进，不管吞 |
| 错误串不大写开头、不带结尾标点 | 首词全大写（HTTP/URL）放行 | `RUNT008` | `CR` Error Strings |
| 包级错误变量用 `Err`/`err` 前缀 | `var ErrFoo = errors.New` | `RUNT009` | `UB` Error Naming |
| 自定义错误类型以 `Error` 结尾 | `func (e *X) Error() string` | `RUNT009` | `UB` Error Naming |
| 库代码不写 `func init()` | 非 main 包 | `RUNT010` | `UB` Avoid `init()` |
| 可判定的错误用 sentinel | `errors.New` + `errors.Is` | 人判 | `UB` Error Naming |

判定链：**能 `errors.Is` 判的才是契约，字符串匹配不是**。对外错误码在 `httpapi` 层映射，
不要让 HTTP 状态码渗进 `internal/order`。

`RUNT008` 的理由是错误串会被拼进别的消息：`log.Printf("Reading %s: %v", name, err)`
不该在句中冒出大写。`RUNT010` 的理由是 `init()` 的执行顺序由包依赖图决定，
测试没法重排它——显式构造函数可以。

## 并发与 context

| 规范 | 判据 | 代码 | 来源 |
| --- | --- | --- | --- |
| 库代码不自造 context | `context.Background()` / `TODO()` | `RUNT005` | `CR` Contexts |
| goroutine 有收敛路径 | 同文件有 WaitGroup/errgroup/channel | `RUNT007`（WARN） | 本项目 |
| 不用 Sleep 当同步 | `time.Sleep(` | `RUNT006`（WARN） | 本项目 |
| `ctx` 作首参并透传 | 人工核对 | 人判 | `CR` Contexts |

`context.Background()` 只允许出现在 `main` 和测试里。库函数拿到 ctx 就往下传，
不要在中途换成 Background——那会让超时和取消在最需要的地方失效。

判定口径：`RUNT001`/`RUNT002`/`RUNT005`/`RUNT006`/`IMP004` 比对的是**剥掉注释、
又把字面量内容抹掉**之后的那一行——`var _ = "库代码不许 panic(见规范"` 是文案，不是调用。
`RUNT008` 反过来要读字面量原文，它判的正是文案本身。两种口径不能混用：混用的后果是
合规代码被判红，而正对照（合规样本）照样绿。守这条的是 `tests/reverse.py` 的 `clean_case`。

## 测试

| 规范 | 判据 | 代码 | 来源 |
| --- | --- | --- | --- |
| 每个非 main 包有测试 | 目录内有 `_test.go` | `TST001` | 本项目 |
| 覆盖率达标 | `coverage.total_min` / `core_min` | `TST002` | 本项目阈值 |
| 并发安全 | `go test -race` = pass | `TST004` | `EG`（`-race` 是标准做法） |
| 性能不退化 | benchmark 超基线 20% | `TST003` | 本项目阈值 |
| 不静默跳过 | `t.Skip` 同行写理由 | `TST005`（WARN） | 本项目 |
| 测试不用 Sleep | `time.Sleep(` | `TST006`（WARN） | 本项目 |
| 证据对应当前提交 | `test.json` 的 `commit` = 当前 HEAD | `TST007` | 本项目 |

覆盖率统计范围由 `config.json` 的 `coverage.include` 决定（本例 `["internal"]`）；`cmd/` 只做装配，
计入总数会把「入口薄」这条规则变成惩罚。`coverage.core_packages` 指定承载业务规则的包
（本例 `["internal/order"]`），`core` 是这些包的加权平均，不是全仓平均。

表驱动测试的判据是「失败时能一眼看出是哪个 case」：`t.Run(tc.name, ...)` + `t.Fatalf` 带输入与期望。

## 源码卫生

| 规范 | 判据 | 代码 | 来源 |
| --- | --- | --- | --- |
| 构建/静态检查通过 | `build`/`vet`/`lint` = pass | `IMP001` | 本项目 + `GL` |
| 缩进用 tab、行尾无空白、LF | 逐行扫描 | `IMP002` | `EG` Formatting（gofmt） |
| import 分组：标准库单独第一组 | 首段带点即第三方 | `IMP005` | `CR` Imports |
| 单文件不过长 | `max_file_lines` | `IMP003`（WARN） | 本项目 |
| TODO 有主 | `TODO(name):` | `IMP004`（WARN） | 本项目 |
| 证据对应当前提交 | `impl.json` 的 `commit` = 当前 HEAD | `IMP006` | 本项目 |

`IMP005` 只判路径形状：`github.com/x/y` 首段带点 ⇒ 第三方，`net/http` 不带点 ⇒ 标准库。
`goimports` 会替你排，但它没被跑过的时候总得有人看出来。

## 提交消息（Conventional Commits 1.0.0）

由 `.harness/scripts/check_commit.py` 判，挂在 `commit-msg` 钩子上；条文号对应 `CC` 原文。

| 规范 | 条文 | 代码 |
| --- | --- | --- |
| `type[(scope)][!]: 描述` | #1 | `CM001` |
| type 必须是已知 noun（allowlist） | #2 #14 | `CM002` |
| description 与 body 之间空一行 | #6 | `CM003` |
| `BREAKING CHANGE` 全大写 | #12 #16 | `CM004` |
| 首行 ≤ 72 字 | 本项目（git 惯例） | `CM005` |

不判的：描述写得好不好、body 讲清没讲清——那是人的事，机器判不了就别假装判。

## 工具层：各管一件事

**重叠是故意的，代替是不允许的。** 同一件事在两层各判一次，比「以为有人在判」安全。

| 层 | 入口 | 依赖 | 判什么 |
| --- | --- | --- | --- |
| 词法层 | `make check` → `verify.py` | 只要 `python3` | 文件形状、JSON 契约、正则可见的调用与字面量 |
| 构建与测试层 | `make evidence` → `build/vet/test -race/cover/bench` + `golangci-lint` | Go 工具链 + golangci-lint | 编译、静态检查、并发安全、覆盖率、benchmark；全部 exit 0 才写 `impl.json` / `test.json` |
| 类型层 | `make lint` → `golangci-lint` | Go 工具链 + golangci-lint | 需要类型信息的：`errcheck` `unused` `unparam` `errorlint` `revive` |
| 钩子层 | `make init` / `make init-lefthook` | git；lefthook 可选 | 什么时候跑 |
| 消息层 | `commit-msg` → `check_commit.py` | 只要 `python3` | `CC` 的条文 |

分工的关键一条：`IMP001` / `TST002` / `TST004` 要求证据里写 `pass`——**verify.py 只判「写了 pass」，
`make evidence` 跑真实命令产证据**。前者零依赖，任何机器（含 CI 的 gate job，不装 Go）都能跑；
后者要工具链，跑在 sample job 里。证据带 `commit`，`IMP006` / `TST007` 在 verify 侧校验它等于
当前 HEAD：改了代码不重跑，证据就过期。

改 `.golangci.yml` 的启用项或阈值，同批改这一节——否则这张表就是过期的说明书。

钩子只有一份实现（`.harness/git-hooks/`）。`lefthook.yml` 是可选的调度层，每条 job 都只是
`sh .harness/git-hooks/<hook>`，不内联任何检查：在 YAML 里再抄一遍命令，等于给门禁开第二份定义，
改一处就漂一处。两套只装一套——`core.hooksPath` 一旦设置，git 就只看那个目录，lefthook 写进
`.git/hooks/` 的转发脚本永远不会被调用（`GATE008` 守这一条，也守钩子文件的执行位：
没有执行位 git 会静默跳过，装了但没跑比没装更危险）。

## 读过但没采纳的

有出处的规范不等于都该抄。以下是读过之后决定不采纳的，理由写在这儿，免得下次重新讨论：

| 出处 | 内容 | 为什么不采纳 |
| --- | --- | --- |
| `universal-dev-standards` | 每份标准配一套 `.ai.yaml` 机器可读版（141 份） | 两套格式要靠 hash 同步，同步本身就是新的漂移源。本模板用「一份规范 + 一条断言」，断言跑起来就是机器可读版 |
| `universal-dev-standards` | 「注册式偏离」：未登记的偏离报错，登记过的带理由与跟踪号告警，**条目开始一致也是错** | 前两条已实现（`exceptions.json` + `oversize_approved`）。第三条暂不实现：现在没有会「自动一致」的例外，加了就是空断言 |
| `lefthook` | `remotes` / `extends`：从远端拉共享钩子配置 | 钩子实现只在 `git-hooks/` 一处。从远端拉配置 = 引入第二个事实源 |
| `golangci-lint` | 自定义 linter 插件 | 要编译插件，`verify.py` 保持零依赖这条就破了 |

## 为什么这些能机检、那些不能

机检只认**词法可见的形状**：调用了什么、返回了什么、文件里有没有某行。判不了的是
「这个抽象是否合理」「这个错误码语义对不对」——所以后者进 `AGENTS.md` 的「人判项」，
由门记录签字，而不是假装有断言。
