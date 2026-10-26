---
name: bad-struct-extra
description: 用于反向测试 struct scope：根下多出一个未声明的目录，该被 STRUCT001 抓住。
license: MIT
---

# bad-struct-extra

单一缺陷：根下有个 `docs/`，既不在标准四件里，也没在 EXTRAS 里声明理由。
