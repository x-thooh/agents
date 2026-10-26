---
name: bad-bash-syntax
description: 用于反向测试 bash scope：围栏代码 bash -n 失败时必须报 BASH002，否则「可执行」只是排版。
license: MIT
---

# bad-bash-syntax

反向样本：第二段围栏的算术表达式少一个右括号，bash -n 会失败。除此之外不含缺陷。

```bash
python3 scripts/audit.py --skill-dir .
```

```bash
if [ -z "$x" ]; then
  echo hi
fi
echo $(( 1 + )
```

