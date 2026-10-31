#!/usr/bin/env python3
"""check_commit.py 的反向测试：一条消息一个缺陷，期望的 code 精确对上。

和 tests/reverse.py 分开，因为被测对象不同：那边测 verify 的 scope，
这边测提交消息校验器。两者都是「声明即承诺」的一部分——钩子装了却没测过，
等于没有钩子。

用法: python3 tests/commit_msg.py
退出码: 0 = 全部符合期望；1 = 有偏差
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".harness/scripts/check_commit.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_commit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# (说明, 消息, 期望的 code 集合)
CASES = (
    ("正对照：最小合规", "feat: add order lookup", set()),
    ("正对照：带 scope", "fix(order): reject negative amount", set()),
    ("正对照：破坏性变更用 !", "feat(api)!: drop v1 endpoint", set()),
    ("正对照：footer 用大写 BREAKING CHANGE",
     "feat: drop v1\n\nBREAKING CHANGE: use v2 instead", set()),
    ("正对照：body 与 footer",
     "fix: prevent double submit\n\nIgnore duplicate ids.\n\nRefs: #12", set()),
    ("缺 type", "add order lookup", {"CM001"}),
    ("缺冒号空格", "feat add order lookup", {"CM001"}),
    ("未知 type", "feet: add order lookup", {"CM002"}),
    ("body 没空行", "feat: add lookup\nbody on the next line", {"CM003"}),
    ("BREAKING CHANGE 小写", "feat: drop v1\n\nbreaking change: use v2", {"CM004"}),
    ("首行过长",
     "feat: " + "很长的描述" * 20, {"CM005"}),
    # 一个提交只做一件事：判据刻意收窄（行首并列连接词 + 标点），所以两条都验——
    # 只验「会报」会让人以为句中出现也算，只验「不报」则等于没验。
    ("正文行首并列另一件事", "feat: add lookup\n\n顺带：修掉一个拼写", {"CM006"}),
    # 自然写法是「顺带」+ 动作 + 冒号，不是「顺带：」。只验前者等于这条规则只在
    # 刻意造句时生效——实测写提交时正是这个形态，绿灯漏过。
    ("正文行首「顺带」后接动作词", "feat: add lookup\n\n顺带修了两处：拼写与缩进", {"CM006"}),
    ("正对照：句中「同时」不算合并",
     "feat: add lookup\n\n读取的同时更新缓存。", set()),
)


def main():
    checker = load_checker()
    failures = []
    for name, message, expected in CASES:
        actual = {code for code, _ in checker.check(message)}
        if actual != expected:
            failures.append(f"{name}: 期望 {sorted(expected) or '无'}，实际 {sorted(actual) or '无'}")
            continue
        print(f"PASS {name}: {sorted(expected) or '0 条发现'}")

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"ALL {len(CASES)} COMMIT MESSAGES MATCHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
