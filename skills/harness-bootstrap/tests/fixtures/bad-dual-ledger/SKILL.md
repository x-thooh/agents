---
name: bad-dual-ledger
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code DUAL001 (the two-sided ledger names neither an intent file nor an authoring side, so it compares a generated view with itself).
---

# Fixture: bad-dual-ledger

Single defect: the reconciliation below compares the generated capability block with the on-disk directory, and both sides come from the same generator.

### 能力账本

- 能力块的技能清单 ↔ `skills/` 实际目录，双向对账：多一个报错，少一个也报错。
