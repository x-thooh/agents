#!/usr/bin/env python3
"""复盘校验器的反向测试：先造出不合规，再看它是否真被拦住。

为什么需要它：`make retro-check` 只证明**当前那几篇复盘**合规，不证明校验器会拦——
把某条判定整段删掉，只要现存复盘没踩它，门禁照样绿。这是 `references/assertion-pitfalls.md`
坑 #13 的同一个形状：反向测试验证的是断言，不是样本。

为什么不开 `--root` 参数：那是「只为测试存在的入口」，生产代码会为它多一条没人用的分支。
改成把 `retro_check.py` 拷进 `tmp/skills/harness-bootstrap/scripts/`——它按
`HERE.parents[1]` 推根，拷进去之后根自然落在 `tmp`，生产代码零改动。

四条断言，其中前两条针对「拦到 0」的复检结论：
  ① 拦到 0 且没有复检行 → 必须 FAIL（否则「0 次」与「一直有效」无法区分）
  ② 拦到 0 且复检行只有结论词、没有理由 → 必须 FAIL（那是一个人就能盖的章）
  ③ 拦到 0、复检行给结论 + 理由 → 必须 PASS
  ④ 拦到点名了 code → 不要求复检行（这一轮它证明过自己）→ 必须 PASS
  ⑤ done 的证据在历史里查不到、而本目录不是仓库 → 必须「判不了」（退出码 2），
     不是「工单说谎」（退出码 1）：CI 浅克隆红的就是这一格，指向了错的一边。

用法: python3 tests/retro_reverse.py
退出码: 0 = 全过；1 = 有失败；2 = 环境错误
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 校验器依赖谁就拷谁：只拷 retro_check.py 不够，它会 import retro_board（表中与证据）。
SCRIPTS = ("retro_check.py", "retro_board.py")

NOTE = """# 复盘（测试样本）

> 数字由 `make retro` 算出。

## 拦到：{hit}

## 工单：R-1

{review}
"""

REASON = "目标仓库每周真要跑一次 pre-commit，本周没有提交，所以这一轮它没机会拦到。"


def run(note, board_data=None):
    """在临时根下跑校验器：把脚本拷进 skills/harness-bootstrap/scripts/ 让 parents[1] 落在 tmp。"""
    with tempfile.TemporaryDirectory(prefix="retro-rev-") as base:
        tmp = Path(base)
        scripts = tmp / "skills/harness-bootstrap/scripts"
        scripts.mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        retro = tmp / "archive/retro"
        retro.mkdir(parents=True)
        (retro / "2026-01-01-sample.md").write_text(note, encoding="utf-8")
        board = board_data or OPEN
        (retro / "tasks.json").write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(scripts / "retro_check.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr


OPEN = {"tasks": [{"id": "R-1", "status": "open", "title": "测试工单"}]}
# 临时目录不是 git 仓库，也没有那个提交：这一格测的是「判不了」与「工单说谎」分不分得开。
DONE_UNVERIFIABLE = {
    "tasks": [{"id": "R-1", "status": "done", "title": "测试工单", "evidence": "commit:deadbeef"}]
}

CASES = (
    ("拦到 0 且无复检行", "0", "", 1, "复检", OPEN),
    ("拦到 0 但复检只有结论词", "0", "## 复检：保留。", 1, "复检行要给结论", OPEN),
    ("拦到 0 且复检给了结论与理由", "0", f"## 复检：保留 {REASON}", 0, "篇复盘通过", OPEN),
    ("拦到点名了 code（不要求复检）", "RUNT001×3", "", 0, "篇复盘通过", OPEN),
    ("done 的证据查不到且没有完整历史", "RUNT001×3", "", 2, "判不了", DONE_UNVERIFIABLE),
)


def main():
    failures = []
    for name, hit, review, want_rc, want_text, board in CASES:
        rc, out = run(NOTE.format(hit=hit, review=review), board)
        if rc != want_rc:
            failures.append(f"{name}: 期望退出码 {want_rc}，实际 {rc}\n{out[-600:]}")
        elif want_text not in out:
            failures.append(f"{name}: 输出里没有「{want_text}」——信号指错了地方\n{out[-600:]}")
        else:
            print(f"PASS {name}: exit {rc}，命中「{want_text}」")
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"{len(failures)} 例不符合期望", file=sys.stderr)
        return 1
    print("ALL RETRO REVERSE TESTS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"环境错误: {exc}", file=sys.stderr)
        sys.exit(2)
