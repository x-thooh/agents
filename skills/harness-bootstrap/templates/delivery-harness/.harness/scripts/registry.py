"""注册表：这一套模板有哪些 scope，按什么顺序跑。

单独一个文件，是为了让 `verify.py` 成为两套模板**逐字节相同**的那一份（`tests/template_parity.py`
的 SHARED）：调度器骨架该一致，各域的 scope 清单本来就不该一致。把清单塞回 verify.py，
两套文件就又差十几行，而「差十几行」正是上一次修 bug 只改一边的入口。
"""

from scopes import (
    coherence,
    conf,
    design,
    dev,
    gates,
    integration,
    requirements,
    review,
    selftest,
    submission,
    notes,
    worktree,
    baseline,
)

# 顺序 = 跑的顺序（输出还会按 severity/scope/line/code 再排序）
SCOPES = (
    gates,
    conf,
    requirements,
    design,
    dev,
    integration,
    selftest,
    review,
    coherence,
    submission,
    notes,
    worktree,
    baseline,
)
