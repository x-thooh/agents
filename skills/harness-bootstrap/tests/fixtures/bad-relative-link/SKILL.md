---
name: bad-relative-link
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。Expects exactly one ERROR with code LINK004.
---

# Fixture: bad-relative-link

Single defect: the link below points at a file that does not exist.
Expects exactly one ERROR with code LINK004 (relative link target missing).

拆出去的材料在这里：[`references/does-not-exist.md`](references/does-not-exist.md)。
