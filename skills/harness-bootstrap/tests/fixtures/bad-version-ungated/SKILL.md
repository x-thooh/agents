---
name: bad-version-ungated
description: 用于反向测试：声明了 rules_version 却只盖章不谈到期，该被 VER001 抓住。
license: MIT
---

# bad-version-ungated

反向样本。规则集版本写成了日期，但没有任何到期行为——日期只在展示，不产生任何约束。

## 版本

rules_version: 2024-01-01

日期版本，不承诺向后兼容。

## 基线机制

- 基线按条数记，逐条输出，不许只报「基线内 N 条」。
- 零基线：首版 baseline 必须为空，存量问题要么修，要么进 accepted 白名单。
- accepted 每条带理由 + 负责人 + 复查日期；accepted 与基线总数只减不增，新增即 ERROR。
- 保质期：复查日期过期未续或未移除条目的，verify 报 ERROR。
