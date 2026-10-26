---
name: bad-loop-hook
description: 用于反向测试 loop scope 的钩子对账：scope 有 code 但 REFLECT 为空时必须报 LOOP004。
license: MIT
---

# bad-loop-hook

反向样本：`scripts/scopes/demo.py` 会报 `DEMO001`，但 `scripts/hooks.py` 把它登记成空的
REFLECT——「有可报的 code，却没有声明可反向验证的面」。空不等于通过。

参考：[`references/acceptance.md`](references/acceptance.md)、
[`references/code-index.md`](references/code-index.md)。
