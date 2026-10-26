# 踩坑记忆

一条一个坑，三段缺一不可：现象 / 根因 / 落成的断言。**没有第三条的条目不算记忆**——
那只是抱怨。落成的断言要么指向 `scripts/scopes/` 里的一个 code，要么在 `AGENTS.md`
的「人判项」里写明强度来源。

## L-1 错误链在中间层断掉

- 现象：HTTP 层拿不到 `order.ErrNotFound`，只能靠字符串匹配，改文案就崩。
- 根因：中间层 `fmt.Errorf("get order %q: %v", id, err)` 用了 `%v`，错误链断了。
- 断言：`RUNT003`——`fmt.Errorf` 带 err 却没 `%w` 判 ERROR。

## L-2 入口膨胀成第二个业务层

- 现象：`cmd/ordersvc/main.go` 长到 300 行，里面写了下单校验和重试。
- 根因：装配与业务混在一起，main 没有行数约束。
- 断言：`LAY004`——`main.go` 超过 `main_max_lines` 判 ERROR，业务必须下沉到 `internal/`。
