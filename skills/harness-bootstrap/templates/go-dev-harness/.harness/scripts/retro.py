"""retro：需求复盘的事实底板——数字先算，AI 只许在数字上写。

让 AI 自己总结「机制拦到过几次」，它最容易写「整体良好」。所以复盘正文的每个结论
都必须挂在本脚本打印的数字上。复盘与工单表放 `archive/retro/`，不放 `.harness/`：
那是本机维护历史、不是交付物布局的一部分（布局表只登记 `.harness/` 下的东西）。

这边只**算数**，不判合不合规——那是 `.harness/scripts/retro_check.py`（`make retro-check`）。
分开的理由：底板坏了是什么都算不出，校验器坏了是算得出却判不了，前者会掩护后者。
栏位的定义只有一份，在 `retro_check.py` 里，这里 import 过来打印，不重写一遍。

用法: python3 .harness/scripts/retro.py
退出码: 0 = 打出事实；2 = 环境错误（拿不到 verify 的 JSON）
"""

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from retro_check import DECISIONS, REQUIRED, REVIEW, REVIEW_MIN  # noqa: E402  （先修 sys.path）

ROOT = HERE.parents[1]
VERIFY = pathlib.Path(".harness/scripts/verify.py")
REVERSE = "tests/reverse.py"


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def verify_summary():
    """当前工作树的 verify 计数与报出的 code。拿不到 JSON 时返回 None。"""
    target = ROOT / VERIFY
    if not target.is_file():
        return None
    proc = _run([sys.executable, str(target), "--root", str(ROOT), "--json"], ROOT)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data["summary"], sorted({f["code"] for f in data["findings"]})


def reverse_count():
    """反向测试的用例数：`PASS ` 开头的行数（与 tests/reverse.py 的输出契约）。"""
    target = ROOT / REVERSE
    if not target.is_file():
        return None
    proc = _run([sys.executable, REVERSE], ROOT)
    hits = len([ln for ln in proc.stdout.splitlines() if ln.startswith("PASS ")])
    return hits if hits else None


def round_delta():
    proc = _run([sys.executable, ".harness/scripts/round.py"], ROOT)
    return proc.returncode, proc.stdout.strip().splitlines()[:1]


def facts():
    print("=== 本轮事实（AI 只能基于这些写复盘，不许自己编数）===")
    got = verify_summary()
    if got is None:
        print("verify: 拿不到 JSON——先修它，再谈复盘")
        return 2
    summary, codes = got
    print(f"verify  : {summary['errors']} ERROR / {summary['warns']} WARN")
    print(f"本轮报出: {' '.join(codes) if codes else '（无发现）'}")
    print(f"reverse : {reverse_count()} 条 PASS")
    rc, line = round_delta()
    print(f"round   : exit {rc}  {line[0] if line else ''}")
    print("\n复盘写到 `archive/retro/YYYY-MM-DD-<需求>.md`，必填栏：")
    print(f"  {REQUIRED[0]}<code 与次数；一次都没拦到就写 0>")
    print(f"  {REQUIRED[1]}<archive/retro/tasks.json 里的 R-N，或「无」>")
    print(f"  {REVIEW}<仅当拦到 0：{'/'.join(DECISIONS)} 之一 + 为什么还留着或本轮削什么，理由不少于 {REVIEW_MIN} 字>")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("retro: --check 已拆到 .harness/scripts/retro_check.py（同一条 make retro-check）", file=sys.stderr)
        sys.exit(2)
    sys.exit(facts())
