---
name: bad-template-phantom-path
description: 用于反向测试 tplpath scope：模板文档里点名的路径在模板里不存在时必须报 TP001，否则目标仓库照文档走会扑空。
license: MIT
---

# bad-template-phantom-path

反向样本：`templates/demo/AGENTS.md` 里写着 `.harness/scripts/retro.py`，模板里并没有这个文件。
它模拟的正是 v1 P0-1 那个形态——文档承诺在、交付物缺席。

同一份文档里还写了真实存在的 `.harness/workflow/contract.json`：能解析的路径必须放过，
否则这条规则就退化成「见到反引号就报」。

本样本只跑 `tplpath`（`--only`）：`templates/` 一出现，布局对账会按自己的规矩报 LP003，
那是另一条规则的事，混进来就证明不了「恰好是 TP001 报的」。
