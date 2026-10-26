---
name: bad-reference-warn
description: 用于反向测试 sections scope：references 下单个文件超过 100 行时必须报 SECT002。
license: MIT
---

# bad-reference-warn

反向样本：SKILL.md 本身干净，缺陷只在 `references/long.md` 的体量。

## 用法

跑一次自身门禁，期望只报一条 SECT002——参考材料和流程手册各有上限，漏一个就漏一半。
