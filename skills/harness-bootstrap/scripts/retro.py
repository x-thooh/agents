"""retro：需求复盘的事实底板——数字先算，AI 只许在数字上写。

让 AI 自己总结「机制拦到过几次」，它最容易写「整体良好」。所以复盘正文的每个结论
都必须挂在本脚本打印的数字上。数据放 `archive/retro/` 而非 skill 目录：那是本机维护
历史、不是载荷（README 的分发边界），且 `references/` 受 SECT002 的 100 行限制。

用法: python3 scripts/retro.py [--check]   # 无参=打印事实；--check=校验复盘
退出码: 0 = 通过 / 判不了；1 = 复盘不合规；2 = 环境错误
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

REQUIRED, STATUS = ("拦到：", "工单："), ("open", "done")
CODE = re.compile(r"\b[A-Z]{2,}[0-9]{3}\b")


def _evidence_ok(raw):
    """`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在。

    「已修复」三个字没有成本，一个真存在的 sha 或路径有——这就是「说做完了」与「做完了」。
    """
    if raw.startswith("commit:"):
        sha = raw.split(":", 1)[1].strip()
        if not sha:
            return False
        rc = _run(["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"], ROOT)
        return rc.returncode == 0
    if raw.startswith("path:"):
        rel = raw.split(":", 1)[1].strip()
        return bool(rel) and (ROOT / rel).exists()
    return False


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
    print("  拦到：<code 与次数；一次都没拦到就写 0，并说明为什么还留着>")
    print("  工单：<tasks/board.json 里的 id，或「无」>")
    return 0


def _board():
    """反思工单表：{id: status}。空表与「没建表」分开——后者判不了，不冒充通过。"""
    path = RETRO / "tasks.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return {str(t.get("id")): t for t in data.get("tasks", []) if isinstance(t, dict)}


def check():
    """两栏都必须可核验：拦到栏点名 code，工单栏指向表里有的 id 且完成态带证据。"""
    files = sorted(RETRO.glob("*.md")) if RETRO.is_dir() else []
    if not files:
        print(f"retro: {RETRO} 下还没有复盘——判不了，不冒充通过")
        return 0
    board = _board()
    if not board:  # None = 没建表；False = 坏 JSON。两种都判不了，不冒充通过
        print(f"retro: {RETRO}/tasks.json 缺失或不是合法 JSON——工单栏无从核验", file=sys.stderr)
        return 2
    bad, cited = [], set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        lack = [k for k in REQUIRED if k not in text]
        if lack:
            bad.append(f"{path.name}: 缺 {' '.join(k.rstrip('：') for k in lack)}")
            continue
        hit = text.split("拦到：", 1)[1].split("\n", 1)[0].strip()
        if hit != "0" and not CODE.search(hit):
            bad.append(f"{path.name}: 拦到一栏既不是 0，也没点名任何 code——那是感想不是台账")
        ids = re.findall(r"\bR-\d+\b", text.split("工单：", 1)[1].split("\n", 1)[0])
        if not ids:
            bad.append(f"{path.name}: 工单栏没有指向任何 R-N——「无」不是默认值，要写就必须给理由")
            continue
        for tid in ids:
            cited.add(tid)
            if tid not in board:
                bad.append(f"{path.name}: 工单 {tid} 不在 tasks.json 里")
    for tid, task in sorted(board.items()):
        status = task.get("status")
        if status not in STATUS:
            bad.append(f"{tid}: status {status!r} 必须是 {list(STATUS)}")
            continue
        ev = str(task.get("evidence", "")).strip()
        if status == "done" and not _evidence_ok(ev):
            bad.append(
                f"{tid}: 标 done 却没给可核验证据（{ev or '空'}）——"
                "`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在"
            )
        if status == "open" and ev:
            bad.append(f"{tid}: 还没做完却写了 evidence——证据是完成态的凭据，不是打算")
    orphan = sorted(set(board) - cited)
    if orphan:
        bad.append(f"tasks.json 里有没人引用的工单：{' '.join(orphan)}——那是死库存")
    if bad:
        for line in bad:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"retro: {len(files)} 篇复盘通过；工单 {len(cited)} 条全部可追溯")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else facts())
