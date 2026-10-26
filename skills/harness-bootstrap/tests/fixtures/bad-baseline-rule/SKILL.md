---
name: bad-baseline-rule
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code BASE001 (baseline section states no per-key count and no per-item output).
---

# Fixture: bad-baseline-rule

Single defect: the baseline section below keeps only (scope, path, fingerprint) and reports an aggregate number, so the second violation on the same key disappears.

### 基线机制

- 零基线：首版 baseline 必须为空，当天 ERROR 不许整表灌进去当见面礼。
- accepted 白名单一行一条带理由与复查日期，只减不增。
- 复查日期到期未续或未删的条目，verify 报 ERROR。
- 基线用三列「域 + 路径 + 消息指纹（数字抹成 #）」，报告只给「0 ERROR（基线内 N 条）」总数。
