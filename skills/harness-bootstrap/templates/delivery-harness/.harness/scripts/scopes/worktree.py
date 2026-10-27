"""worktree：看板任务 ↔ 本机 worktree 的对照（一个任务一棵树）。

  WT001  树还在，但任务已 done 或不在看板 —— 收尾只做了一半，本机留下的残树
  WT002  树已开，任务还是 todo —— 顺序反了：先开树再改状态，或状态忘了改

为什么只判这两条：「忘了开树」判不了——任务可能在别人机器上做，本机没有树是正常的，
把它判成 ERROR 等于让每个人的机器互相告状。能判死的是**本机树与看板状态的矛盾**：
树在而任务完了，就是没删；树在而任务没开始，就是流程反了。判不了的写进「人判项」，
不用一条弱断言假装守住（坑 #3：弱断言比没有更坏，它给绿灯）。

为什么根目录不是仓库根时记 not_applicable：模板本身是某个大仓库的子目录，那时
`git worktree list` 返回的是**别人**的树，拿它判等于张冠李戴。判不了就说判不了。

为什么认 `task/` 前缀：`wt.py` 的约定是分支 `task/<id>`。不按这条命名手工建的树，
收尾脚本认不出、本 scope 也不认——那是「约定大于配置」的另一面：约定之外没有默认识别。
"""
import json
import subprocess
from pathlib import Path

from .common import add

NAME = "worktree"
BOARD = ".harness/tasks/board.json"
BRANCH = "refs/heads/task/"


def _toplevel(root):
    """仓库根；不是 git 仓库、或 root 只是某大仓库的子目录时返回 None。"""
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        top = Path(proc.stdout.strip()).resolve()
    except OSError:
        return None
    return top if top == root.resolve() else None


def _trees(root):
    """-> {task id: 路径}；`git` 跑不动时返回 None（判不了，不是没树）。"""
    proc = subprocess.run(
        ["git", "-C", str(root), "worktree", "list", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    out, path = {}, None
    for line in [*proc.stdout.splitlines(), ""]:
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch " + BRANCH):
            out[line[len("branch " + BRANCH):]] = path
        elif not line:
            path = None
    return out


def _tasks(board):
    try:
        data = json.loads(board.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {t.get("id"): t for t in data.get("tasks", []) if isinstance(t, dict)}


def run(ctx, findings):
    root = Path(ctx["root"])
    board = root / BOARD
    tasks = _tasks(board) if board.is_file() else None
    trees = _trees(root) if _toplevel(root) else None
    if tasks is None or trees is None:
        # 看板坏了由 gates 的 GATE007 报；这里只说明「这一域判不了」，不重复报同一缺陷
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    for tid, path in sorted(trees.items()):
        task = tasks.get(tid)
        if task is None or task.get("status") == "done":
            add(findings, "ERROR", NAME, BOARD, 1, "WT001",
                f"任务 {tid} 已结束或不在看板，本机还留着树 {path}：收尾只做了一半。"
                f"跑 `make task-done TASK={tid}`——它会先查工作区干净、查分支已合并，再删树删分支")
        elif task.get("status") == "todo":
            add(findings, "WARN", NAME, BOARD, 1, "WT002",
                f"任务 {tid} 还是 todo，本机却已经开了树 {path}：先改看板状态再开工，"
                "否则收尾时对不上——看板是入口，树是它的下游")
