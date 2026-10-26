---
name: bad-expiry-decor
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code BASE004 (an accepted whitelist with review dates but no defined expiry behavior — dates that never fail anything are decoration).
---

# Fixture: bad-expiry-decor

Single defect: the section below has counts, per-item reporting, zero-baseline, accepted whitelist, and decrease-only, but never defines what happens when a review date passes.

### 基线机制

- 零基线：首版 baseline 必须为空。
- accepted 白名单一行一条，带理由、负责人和复查日期。
- 基线与 accepted 的总条数只减不增，新增即 ERROR。
- 报告必须逐条列出当前全部违规并标「基线内 / 新欠」。
