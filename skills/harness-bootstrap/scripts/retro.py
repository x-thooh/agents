"""retro：需求复盘的事实底板——数字先算出来，AI 只许在数字上写。

为什么脚本先算：让 AI 自己总结「这套机制拦到过几次」，它最容易写的就是「整体良好」。
所以复盘正文里的每个结论都必须挂在本脚本打印的数字上；写不出数字的句子不算复盘。

为什么复盘数据不放 skill 目录：它是**本机维护历史**，不是载荷。README 的「分发边界」
写着「只为本机服务的目录，不进这个目录」；而 `references/` 受 `SECT002` 的 100 行限制，
放进去只会把参考材料长成第二个手册。所以机制在 skill 里，数据在仓库根的 `archive/retro/`。

用法:
  python3 scripts/retro.py            # 打印本轮事实（给 AI 起草用）
  python3 scripts/retro.py --check    # 校验 archive/retro/*.md 的必填栏
退出码: 0 = 通过 / 判不了；1 = 复盘缺栏；2 = 环境错误
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parents[1]
RETRO = ROOT / "archive" / "retro"

REQUIRED = ("拦到：", "工单：")
CODE = re.compile(r"\b[A-Z]{2,}[0-9]{3}\b")


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
    print("\n复盘文件写到 `archive/retro/YYYY-MM-DD-<需求>.md`，必填栏见下：")
    print("  拦到：<code 与次数；一次都没拦到就写 0，并说明为什么还留着>")
    print("  工单：<tasks/board.json 里的 id，或「无」>")
    return 0


def check():
    files = sorted(RETRO.glob("*.md")) if RETRO.is_dir() else []
    if not files:
        print(f"retro: {RETRO} 下还没有复盘——判不了，不冒充通过")
        return 0
    bad = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lack = [k for k in REQUIRED if k not in text]
        if lack:
            bad.append(f"{path.name}: 缺 {' '.join(k.rstrip('：') for k in lack)}")
            continue
        hit = text.split("拦到：", 1)[1].split("\n", 1)[0].strip()
        if hit != "0" and not CODE.search(hit):
            bad.append(f"{path.name}: 拦到一栏既不是 0，也没点名任何 code——那是感想不是台账")
    if bad:
        for line in bad:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"retro: {len(files)} 篇复盘通过（拦到栏要么点名 code、要么明确写 0）")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else facts())
