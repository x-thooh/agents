---
name: bad-layout-parity
description: 用于反向测试 layout_parity scope：布局表要求了模板没建的东西时必须报 LP001，否则「表是根」只是口号。
license: MIT
---

# bad-layout-parity

反向样本：布局表要求 `AGENTS.md` 与 `.harness/config.json`，模板只建了前者。
除此之外不含任何缺陷。

## 布局

生成物的标准布局（清单只此一处）：

```text
路径                   形态    说明
AGENTS.md              必建    入口（地图，不是手册）
.harness/config.json   必建    执行：阈值与模块根（单一根配置）
```
