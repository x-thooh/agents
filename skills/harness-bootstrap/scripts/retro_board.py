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


def history_available(root):
    """完整 git 历史在不在。不是仓库、或浅克隆，都算「判不了」。

    为什么要专门判一次：`git cat-file -e <sha>` 在浅克隆里查不到提交，与「工单说谎」在
    输出上一模一样，但两者的动作相反——前者补历史（CI 加 `fetch-depth: 0`），后者改工单。
    实测代价：CI 连续两次红在「R-1 标 done 却没给证据」，而本地全绿、工单也没问题。
    """
    if _run(["git", "-C", str(root), "rev-parse", "--git-dir"], root).returncode != 0:
        return False
    out = _run(["git", "-C", str(root), "rev-parse", "--is-shallow-repository"], root)
    if out.returncode != 0:  # 老 git 没有这个开关：按「有完整历史」判，不掩盖真失败
        return True
    return out.stdout.strip() != "true"


def evidence_ok(root, raw):
    """True = 可核验；False = 证据是假的；None = 判不了（历史不完整，别冒充通过）。

    `commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在。
    """
    if raw.startswith("commit:"):
        sha = raw.split(":", 1)[1].strip()
        if not sha:
            return False
        cmd = ["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"]
        if _run(cmd, root).returncode == 0:
            return True
        return None if not history_available(root) else False
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
    """返回 (bad, undecided)：bad = 真的不合规；undecided = 历史不可用、判不了。

    两类分开返回，是因为它们要做的动作相反：bad 改工单，undecided 补历史。
    合并成一张清单时，「表读不动」会被写成「复盘不合规」，报错就指向了错的地方。
    """
    bad, undecided = [], []
    for tid, task in sorted(board.items()):
        status = task.get("status")
        if status not in STATUS:
            bad.append(f"{tid}: status {status!r} 必须是 {list(STATUS)}")
            continue
        ev = str(task.get("evidence", "")).strip()
        if status == "done":
            ok = evidence_ok(root, ev)
            if ok is None:
                undecided.append(
                    f"{tid}: 证据 {ev} 在历史里查不到，而本仓库没有完整历史（浅克隆或不是 git 仓库）"
                    "——判不了，不冒充通过；CI 要 `fetch-depth: 0`，本地要完整 clone"
                )
            elif not ok:
                bad.append(
                    f"{tid}: 标 done 却没给可核验证据（{ev or '空'}）——"
                    "`commit:<sha>` 要真在历史里、`path:<相对路径>` 要真存在"
                )
        if status == "open" and ev:
            bad.append(f"{tid}: 还没做完却写了 evidence——证据是完成态的凭据，不是打算")
    orphan = sorted(set(board) - cited)
    if orphan:
        bad.append(f"tasks.json 里有没人引用的工单：{' '.join(orphan)}——那是死库存")
    return bad, undecided
