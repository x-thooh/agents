---
name: bad-baseline-warn
description: 用于反向测试 baseline scope：正文提到基线却没有基线机制小节时，必须报 BASE002。
license: MIT
---

# bad-baseline-warn

反向样本：只提了一句「基线」，不给它小节。除此之外不含任何缺陷。

现有的欠账都记在基线里，所以这次改动不需要重算。

## 用法

跑一次自身门禁：

```bash
python3 scripts/audit.py --skill-dir tests/fixtures/bad-baseline-warn
```

