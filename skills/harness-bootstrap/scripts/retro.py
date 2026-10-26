"""retro：需求复盘的事实底板——数字先算，AI 只许在数字上写。

让 AI 自己总结「机制拦到过几次」，它最容易写「整体良好」。所以复盘正文的每个结论
都必须挂在本脚本打印的数字上。数据放 `archive/retro/` 而非 skill 目录：那是本机维护
历史、不是载荷（README 的分发边界），且 `references/` 受 SECT002 的 100 行限制。

这边只**算数**，不判合不合规——那是 `scripts/retro_check.py`（`make retro-check`）。
分开的理由：底板坏了是什么都算不出，校验器坏了是算得出却判不了，前者会掩护后者。
栏位的定义只有一份，在 `retro_check.py` 里，这里 import 过来打印，不重写一遍。

用法: python3 scripts/retro.py
退出码: 0 = 打出事实；2 = 用法错误（--check 已拆走）
"""

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from retro_check import DECISIONS, REQUIRED, REVIEW, REVIEW_MIN  # noqa: E402  （先修 sys.path）

SKILL = HERE.parent


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def audit_summary():
    proc = _run([sys.executable, "scripts/audit.py", "--json"], SKILL)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data["summary"], sorted({f["code"] for f in data["findings"]})


def fixtures_count():
    proc = _run([sys.executable, "tests/fixtures.py"], SKILL)
    hit = re.search(r"ALL (\d+) FIXTURES MATCHED", proc.stdout)
    return int(hit.group(1)) if hit else None


def round_delta():
    proc = _run([sys.executable, "scripts/round.py"], SKILL)
    return proc.returncode, proc.stdout.strip().splitlines()[:1]


def facts():
    print("=== 本轮事实（AI 只能基于这些写复盘，不许自己编数）===")
    got = audit_summary()
    if got is None:
        print("audit: 拿不到 JSON——先修它，再谈复盘")
        return 2
    summary, codes = got
    print(f"audit   : {summary['errors']} ERROR / {summary['warns']} WARN")
    print(f"本轮报出: {' '.join(codes) if codes else '（无发现）'}")
    print(f"fixtures: {fixtures_count()} 条 PASS")
    rc, line = round_delta()
    print(f"round   : exit {rc}  {line[0] if line else ''}")
    print("\n复盘写到 `archive/retro/YYYY-MM-DD-<需求>.md`，必填栏：")
    print(f"  {REQUIRED[0]}<code 与次数；一次都没拦到就写 0>")
    print(f"  {REQUIRED[1]}<tasks.json 里的 id，或「无」>")
    print(
        f"  {REVIEW}<仅当拦到 0：{'/'.join(DECISIONS)} 之一 + 为什么还留着或本轮削什么，"
        f"理由不少于 {REVIEW_MIN} 字>"
    )
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("retro: --check 已拆到 scripts/retro_check.py（同一条 make retro-check）", file=sys.stderr)
        sys.exit(2)
    sys.exit(facts())
