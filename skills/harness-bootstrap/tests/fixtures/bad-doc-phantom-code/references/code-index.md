# 全部 code 清单（脚本生成，禁手改）

> 由 `python3 scripts/gen_code_index.py` 生成；`codeindex` scope 会重新生成一遍做逐字节比对，
> 不一致即 ERROR。手改这个文件一定被拦——要改就改 `scripts/scopes/*.py`，然后 `make code-index`。
>
> 级别取自源码里同一个 `Finding(...)` 调用中紧挨在该 code 前的 `"ERROR"` / `"WARN"` 字面量。
> 这个解析依赖构造形态 `Finding("级别", NAME, 行, "code", ...)`；形态变了这里会取错，
> 所以生成后要人眼看一遍，别把它当成定义——定义在代码里。
> 箭头表示同一 code 有多档：`WARN → ERROR` 即「轻了报 WARN、重了报 ERROR」。

共 1 个 code：1 个只报 ERROR、0 个只报 WARN、0 个分两档。

| code | scope | 级别 |
| --- | --- | --- |
| `DEMO001` | demo | ERROR |
