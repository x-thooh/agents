---
name: ok-minimal
description: 用于正向对照：这是能过全部 scope 的最小合规样本，没有缺陷，audit 必须报 0 ERROR 0 WARN。
license: MIT
---

# ok-minimal

正向对照样本。它存在的唯一理由：证明「0 条发现」和「检查器根本没跑」不是一回事。
没有一份全绿样本时，反向测试只能证明规则会报错，不能证明规则会放过。

## 用法

跑一次自身门禁：

```bash
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal
```

判据是 0 ERROR 且 0 WARN。任何一条 WARN 都说明这份样本被污染了，正对照随之失效。

## 基线机制

- 基线按条数记，逐条输出，不许只报「基线内 N 条」。
- 零基线：首版 baseline 必须为空，存量问题要么修，要么进 accepted 白名单。
- accepted 每条带理由 + 负责人 + 复查日期；accepted 与基线总数只减不增，新增即 ERROR。
- 保质期：复查日期过期未续或未移除条目的，verify 报 ERROR。
