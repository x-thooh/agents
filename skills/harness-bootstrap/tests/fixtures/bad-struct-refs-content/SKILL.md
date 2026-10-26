---
name: bad-struct-refs-content
description: 用于反向测试 struct scope：references/ 里放了可执行代码，该被 STRUCT002 抓住。
license: MIT
---

# bad-struct-refs-content

单一缺陷：`references/` 只该放按需读取的文档，这里塞了个脚本。
