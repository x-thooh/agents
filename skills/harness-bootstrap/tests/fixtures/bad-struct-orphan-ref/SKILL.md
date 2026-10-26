---
name: bad-struct-orphan-ref
description: 用于反向测试 struct scope：references 下有文件却没有任何入口链到它时，必须报 STRUCT003。
license: MIT
---

# Fixture: bad-struct-orphan-ref

Single defect: `references/` 下有一份文档谁都没链——外置了却没人读得到。
Expects exactly one ERROR with code STRUCT003。

注意样本自己不点名那份文件：判据是「有没有人提到它」，把它写进这里就等于自己链了自己。

正文一行。
