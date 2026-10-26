---
name: bad-zero-baseline
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code BASE003 (a baseline section that allows stuffing existing errors into the first baseline — no zero-baseline rule, no accepted whitelist, no decrease-only bound).
---

# Fixture: bad-zero-baseline

Single defect: the section below declares count + per-item reporting but permits a non-empty first baseline with no accepted whitelist and no decrease-only bound.

### 基线机制

- 四列「域 + 路径 + 消息指纹（数字抹成 #） + 条数」：条数用来判断同一格是不是又犯了。
- 报告必须逐条列出当前全部违规并标「基线内 / 新欠」。
- 复查日期到期未续或未删的条目，verify 报 ERROR。
- 首版把现有 ERROR 整表写进基线即可报绿。
