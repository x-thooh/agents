# Go 工程规范（可机检部分）

每条规范对应一个 scope 代码；改规范必须同批改断言，否则这条规范会静默失效。

## 模块与包边界

| 规范 | 判据 | scope |
| --- | --- | --- |
| 模块根有 `go.mod`，`go` 版本不低于阈值 | `go_version_min` | `layout` |
| 不许 `replace` 指向本地路径 | `=> ./`、`=> ../` | `layout` |
| 入口只在 `cmd/<服务>/main.go`，只做装配 | 行数 ≤ `main_max_lines` | `layout` |
| 业务代码不进 `cmd/` | `cmd/` 下必须 `package main` | `layout` |
| 导出符号有 doc 注释 | 上一行 `// Name ...` | `layout` |
| 接口小 | 方法数 ≤ `max_interface_methods` | `layout` |

包边界怎么定：**按变化原因分，不按技术层分**。`internal/order` 变是因为业务规则变；
`internal/httpapi` 变是因为协议变。两者混在一起时，协议改动会牵动业务测试。

## 错误处理

| 规范 | 判据 | scope |
| --- | --- | --- |
| 库代码不 `panic` | 非 main 包出现 `panic(` | `runtime` |
| 库代码不退出进程 | `log.Fatal(`、`os.Exit(` | `runtime` |
| 包装保留错误链 | `fmt.Errorf` 带 err 必须带 `%w` | `runtime` |
| 不吞错 | `if err != nil { return nil }` | `runtime` |
| 可判定的错误用 sentinel | `var ErrX = errors.New(...)` + `errors.Is` | 人判 |

判定链：**能 `errors.Is` 判的才是契约，字符串匹配不是**。对外错误码在 `httpapi` 层映射，
不要让 HTTP 状态码渗进 `internal/order`。

## 并发与 context

| 规范 | 判据 | scope |
| --- | --- | --- |
| 库代码不自造 context | `context.Background()` / `TODO()` | `runtime` |
| goroutine 有收敛路径 | 同文件有 WaitGroup/errgroup/channel | `runtime`（WARN） |
| 不用 Sleep 当同步 | `time.Sleep(` | `runtime`（WARN） |
| `ctx` 作首参并透传 | 人工核对 | 人判 |

`context.Background()` 只允许出现在 `main` 和测试里。库函数拿到 ctx 就往下传，
不要在中途换成 Background——那会让超时和取消在最需要的地方失效。

## 测试

| 规范 | 判据 | scope |
| --- | --- | --- |
| 每个非 main 包有测试 | 目录内有 `_test.go` | `test` |
| 覆盖率达标 | `coverage.total_min` / `core_min` | `test` |
| 并发安全 | `go test -race` = pass | `test` |
| 性能不退化 | benchmark 超基线 20% | `test` |
| 不静默跳过 | `t.Skip` 同行写理由 | `test`（WARN） |
| 测试不用 Sleep | `time.Sleep(` | `test`（WARN） |

覆盖率统计范围约定为 `./internal/...`：`cmd/` 只做装配，计入总数会把「入口薄」这条规则变成惩罚。
`core` 取承载业务规则的那个包（本例 `internal/order`），不是全仓平均。

表驱动测试的判据是「失败时能一眼看出是哪个 case」：`t.Run(tc.name, ...)` + `t.Fatalf` 带输入与期望。

## 源码卫生

| 规范 | 判据 | scope |
| --- | --- | --- |
| 构建/静态检查通过 | `build`/`vet`/`lint` = pass | `impl` |
| 缩进用 tab、行尾无空白、LF | 逐行扫描 | `impl` |
| 单文件不过长 | `max_file_lines` | `impl`（WARN） |
| TODO 有主 | `TODO(name):` | `impl`（WARN） |

## 为什么这些能机检、那些不能

机检只认**词法可见的形状**：调用了什么、返回了什么、文件里有没有某行。判不了的是
「这个抽象是否合理」「这个错误码语义对不对」——所以后者进 `AGENTS.md` 的「人判项」，
由门记录签字，而不是假装有断言。
