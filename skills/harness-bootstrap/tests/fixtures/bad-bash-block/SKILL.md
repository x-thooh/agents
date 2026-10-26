---
name: bad-bash-block
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code BASH001 (bash fence contains a non-runnable placeholder).
---

# Fixture: bad-bash-block

Single defect: the bash fence below contains a U+2026 placeholder and cannot be run as written.

```bash
find . -type f \( -name "*.md" -o … \) | wc -l
```
