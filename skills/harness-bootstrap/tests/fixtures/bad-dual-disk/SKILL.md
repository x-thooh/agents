---
name: bad-dual-disk
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code DUAL001：双向对账写到的磁盘侧不在布局表里，两侧各说各话。
license: MIT
---

# Fixture: bad-dual-disk

Single defect: the reconciliation names `skills/` as the disk side, but the layout
table only declares the old `playbooks/` directory.

```text
路径                                                     形态    说明
.harness/workflow/playbooks/                             按需    旧目录
```

### 能力账本

- 声明账本 `skills.declared.yaml` ↔ 磁盘 `skills/`，双向对账：多一个报错，少一个也报错。
