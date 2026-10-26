---
name: bad-doc-phantom-code
description: 用于反向测试 docphantom scope：文档把某个 code 归给 audit.py 而源码里已没有它时，必须报 DOC002。
license: MIT
---

# bad-doc-phantom-code

反向样本：`references/acceptance.md` 里有一行把某个不存在的 code 归给 `audit.py`，
而 `scripts/scopes/demo.py` 只会报 `DEMO001`。DOC001（源码 → 文档）在这份样本里是满足的，
所以唯一缺陷是反方向的「幻影 code」。除此之外不含缺陷。

参考：`references/acceptance.md`、`references/code-index.md`。
