---
name: bad-xref-table
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code XREF002 (reference to a numbered table row that does not exist).
---

# Fixture: bad-xref-table

## 二、设计原则

| # | 原则 |
| --- | --- |
| 1 | 第一条 |
| 2 | 第二条 |

Single defect: the reference below points to table row 3, which does not exist.

见 §二.3。
