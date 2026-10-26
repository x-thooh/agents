---
name: bad-phantom-scope
description: 用于反向测试 docphantom scope 的第三个方向：正文点名的 scope 模块不存在时必须报 DOC002。
license: MIT
---

# bad-phantom-scope

反向样本：正文说「`ghostscope` 的 `DEMO001` 守这条规则」，但 `scripts/scopes/` 下
只有 `demo.py`，没有 `ghostscope.py`。`DEMO001` 真实存在，所以 code 方向（DOC001/DOC002）
都满足——唯一缺陷是**scope 名指向不存在的模块**。

这一段同时是它的归属条件：同一句里点了本仓库的真实 code，才说明它在讲本仓库的载体。

参考：[`references/acceptance.md`](references/acceptance.md)、
[`references/code-index.md`](references/code-index.md)。
