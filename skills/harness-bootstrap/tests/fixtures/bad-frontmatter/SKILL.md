---
name: not-matching
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code FM004 (name does not match the parent directory name).
---

# Fixture: bad-frontmatter

Single defect: the `name` field does not match the parent directory name.
Do not fix this file; the reverse test asserts the exact code.
