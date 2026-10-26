---
name: bad-stale-code-index
description: 用于反向测试 codeindex scope：references/code-index.md 与源码不一致时必须报 CODEINDEX001。
license: MIT
---

# bad-stale-code-index

反向样本：源码里有一个 `DEMO001`，而 `references/code-index.md` 里没有它。
除此之外不含缺陷。

参考：`references/acceptance.md`、`references/code-index.md`。

反向样本的脚本在 `scripts/scopes/demo.py`。本句只为让 DLV001 不误报：一个样本只该含一件缺陷。
