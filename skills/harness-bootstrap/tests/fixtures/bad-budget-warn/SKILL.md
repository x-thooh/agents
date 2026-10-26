---
name: bad-budget-warn
description: 用于反向测试 budget scope：单脚本超过 150 行时必须报 BUDGET001 的 WARN 档（准备拆）。
license: MIT
---

# bad-budget-warn

反向样本：`scripts/huge.py` 故意写到 160 行。除此之外不含缺陷。

反向样本的脚本在 `scripts/huge.py`。本句只为让 DLV001 不误报：一个样本只该含一件缺陷。
