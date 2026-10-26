---
name: bad-skill-phantom-code
description: 用于反向测试 docphantom scope：SKILL.md 正文点到不存在的 code（ZZ001）时必须报 DOC002。
license: MIT
---

# bad-skill-phantom-code

反向样本：正文说「`scripts/scopes/demo.py` 的 `DEMO001` 与 `ZZ001` 一起守这条规则」，
但 `ZZ001` 在本仓库任何 `.py` 里都不存在。`references/acceptance.md` 已经把
`DEMO001` 点了名，所以 DOC001 满足——唯一缺陷是文档 → 源码方向的幻影。除此之外不含缺陷。

参考：`references/acceptance.md`、`references/code-index.md`。

反向样本的脚本在 `scripts/scopes/demo.py`。本句只为让 DLV001 不误报：一个样本只该含一件缺陷。
