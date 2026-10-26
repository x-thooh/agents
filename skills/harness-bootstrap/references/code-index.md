# 全部 code 清单（脚本生成，禁手改）

> 由 `python3 scripts/gen_code_index.py` 生成；`codeindex` scope 会重新生成一遍做逐字节比对，
> 不一致即 ERROR。手改这个文件一定被拦——要改就改 `scripts/scopes/*.py`，然后 `make code-index`。
>
> 级别取自源码里同一个 `Finding(...)` 调用中紧挨在该 code 前的 `"ERROR"` / `"WARN"` 字面量。
> 这个解析依赖构造形态 `Finding("级别", NAME, 行, "code", ...)`；形态变了这里会取错，
> 所以生成后要人眼看一遍，别把它当成定义——定义在代码里。
> 箭头表示同一 code 有多档：`WARN → ERROR` 即「轻了报 WARN、重了报 ERROR」。

共 41 个 code：33 个只报 ERROR、4 个只报 WARN、4 个分两档。

| code | scope | 级别 |
| --- | --- | --- |
| `BASE001` | baseline | ERROR |
| `BASE002` | baseline | WARN |
| `BASE003` | baseline | ERROR |
| `BASE004` | baseline | ERROR |
| `BASH001` | bash | ERROR |
| `BASH002` | bash | ERROR |
| `BUDGET001` | budget | WARN → ERROR |
| `BUDGET002` | budget | WARN → ERROR |
| `CODEINDEX001` | codeindex | ERROR |
| `DOC001` | docclaim | ERROR |
| `DOC002` | docphantom | ERROR |
| `FM001` | frontmatter | ERROR |
| `FM002` | frontmatter | ERROR |
| `FM003` | frontmatter | ERROR |
| `FM004` | frontmatter | ERROR |
| `FM005` | frontmatter | ERROR |
| `FM006` | frontmatter | ERROR |
| `FM007` | frontmatter | ERROR |
| `FM008` | frontmatter | ERROR |
| `FM009` | frontmatter | ERROR |
| `HOST001` | host | ERROR |
| `HOST002` | host | ERROR |
| `LAYOUT001` | layout | ERROR |
| `LP001` | layout_parity | ERROR |
| `LP002` | layout_parity | WARN |
| `LP003` | layout_parity | ERROR |
| `DUAL001` | ledger | ERROR |
| `LINK001` | links | WARN |
| `LINK002` | links | ERROR |
| `LINK003` | links | WARN |
| `LINK004` | links | ERROR |
| `SECT001` | sections | WARN → ERROR |
| `SECT002` | sections | WARN → ERROR |
| `STRUCT001` | struct | ERROR |
| `STRUCT002` | struct | ERROR |
| `SCOPE001` | terms | ERROR |
| `VER001` | version | ERROR |
| `XREF001` | xref | ERROR |
| `XREF002` | xref | ERROR |
| `XREFDOC001` | xrefdoc | ERROR |
| `XREFDOC002` | xrefdoc | ERROR |
