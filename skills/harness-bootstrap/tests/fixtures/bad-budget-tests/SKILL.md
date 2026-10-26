---
name: bad-budget-tests
description: 用于反向测试 budget scope 的扫描面：tests/ 下的脚本超过 200 行时也必须报 BUDGET001。
license: MIT
---

# bad-budget-tests

反向样本：`tests/huge.py` 故意写到 210 行，`scripts/` 下一个 .py 都没有。
只扫 `scripts/` 的实现（v2 评审前的形态）对这个样本报 0 条——那正是它存在的理由。

参考：`references/acceptance.md`。
