"""retro_board：复盘工单表与完成证据——「已修复」三个字要有成本。

`archive/retro/tasks.json` 是复盘里 `工单：` 栏指向的表。这边管两件事：表读不读得动
（空表与「没建表」分开——后者判不了，不冒充通过），以及标 done 的条目有没有给可核验证据。
`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在，这是「说做完了」与「做完了」
之间唯一站得住的差别。

为什么与 `retro_check.py` 分开：那边判**文字形状**（三栏在不在、结论词对不对），
这边判**表与仓库的真实状态**。失败原因不同，混在一起时「表读不动」会被写成
「复盘不合规」，报错指向的地方就错了。
"""

import json
import pathlib
import subprocess

STATUS = ("open", "done")


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def evidence_ok(root, raw):
    """`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在。"""
    if raw.startswith("commit:"):
        sha = raw.split(":", 1)[1].strip()
        if not sha:
            return False
        cmd = ["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"]
        return _run(cmd, root).returncode == 0
    if raw.startswith("path:"):
        rel = raw.split(":", 1)[1].strip()
        return bool(rel) and (pathlib.Path(root) / rel).exists()
    return False


def load(retro):
    """返回 {id: task}。None = 没建表；False = 坏 JSON。两种都判不了，调用方要分开处理。"""
    path = pathlib.Path(retro) / "tasks.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return {str(t.get("id")): t for t in data.get("tasks", []) if isinstance(t, dict)}


def findings(root, board, cited):
    """表侧的发现：状态闭集、完成态证据、未完成态不许有证据、没人引用的死库存。"""
    bad = []
    for tid, task in sorted(board.items()):
        status = task.get("status")
        if status not in STATUS:
            bad.append(f"{tid}: status {status!r} 必须是 {list(STATUS)}")
            continue
        ev = str(task.get("evidence", "")).strip()
        if status == "done" and not evidence_ok(root, ev):
            bad.append(
                f"{tid}: 标 done 却没给可核验证据（{ev or '空'}）——"
                "`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在"
            )
        if status == "open" and ev:
            bad.append(f"{tid}: 还没做完却写了 evidence——证据是完成态的凭据，不是打算")
    orphan = sorted(set(board) - cited)
    if orphan:
        bad.append(f"tasks.json 里有没人引用的工单：{' '.join(orphan)}——那是死库存")
    return bad
