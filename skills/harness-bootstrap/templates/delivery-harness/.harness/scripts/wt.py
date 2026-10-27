#!/usr/bin/env python3
"""任务级 worktree：一个任务一棵树。开工建树，收尾提交并删树。

为什么不用「在主工作树上切分支」：切分支得先把未提交的改动 stash 掉，那等于让脚本
替人保管工作，而它保管丢了没人发现。worktree 是旁路——主树保持原样，两件事互不打扰。

为什么树放在仓库外面（同级 `<repo>-wt/<task-id>`）：放在仓库里就进了 git status，
`git add -A` 一次就把它收进提交。分支名 `task/<task-id>` 与看板的 id 一一对应，
`worktree` scope 就是按这条命名对账的（WT001 / WT002）。

子命令
  new <id> [--base <ref>]   建树；起点默认 origin/main，没有就 main / master
  finish <id> [--force]     收尾：查干净 → 查已合并 → 删树 → 删分支 → prune
  list                      看板 doing/todo 任务 ↔ 本机树的对照

退出码：0 成功；1 前置条件不满足（脏 / 未合并 / 任务状态不对）；2 用法或环境错误。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BOARD = ".harness/tasks/board.json"
PREFIX = "task/"


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True, text=True
    )


def fail(message, code=1):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def repo_root():
    proc = git(Path.cwd(), "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        fail("不在 git 仓库里：worktree 没有意义（先 git init 并提交一次）", 2)
    return Path(proc.stdout.strip())


def board(root):
    path = root / BOARD
    if not path.is_file():
        fail(f"缺少 {BOARD}：看板是这条流程的入口", 2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"读不了 {BOARD}：{exc}", 2)


def task_of(data, tid):
    for task in data.get("tasks", []):
        if isinstance(task, dict) and task.get("id") == tid:
            return task
    return None


def trees(root):
    """-> {task id: 路径}。只认 `task/` 分支：别的 worktree 不是这条流程开的。"""
    proc = git(root, "worktree", "list", "--porcelain")
    if proc.returncode != 0:
        fail(f"git worktree list 失败：{proc.stderr.strip()}", 2)
    out, path = {}, None
    for line in [*proc.stdout.splitlines(), ""]:
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/" + PREFIX):
            out[line[len("branch refs/heads/" + PREFIX):]] = path
        elif not line:
            path = None
    return out


def target(root, tid):
    return root.parent / f"{root.name}-wt" / tid


def base_ref(root, asked):
    for ref in [asked] if asked else ["origin/main", "main", "master"]:
        if git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    fail("找不到可用的起点（origin/main / main / master 都不存在）：用 --base 指定", 2)


def cmd_new(root, tid, asked_base):
    task = task_of(board(root), tid)
    if task is None:
        fail(f"看板里没有任务 {tid}：先写进 {BOARD}——树是任务的下游，不是替代品")
    if task.get("status") == "done":
        fail(f"任务 {tid} 已经是 done：再开工要先改看板状态，否则收尾时对不上")
    known = trees(root)
    if tid in known:
        fail(f"任务 {tid} 的树已经存在：{known[tid]}")
    path = target(root, tid)
    if path.exists():
        fail(f"{path} 已存在但不是本仓库的 worktree：先清掉，否则 add 会失败")
    base = base_ref(root, asked_base)
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = git(root, "worktree", "add", "-b", PREFIX + tid, str(path), base)
    if proc.returncode != 0:
        fail(f"建树失败：{proc.stderr.strip()}")
    print(f"已建树 {path}（分支 {PREFIX}{tid}，起点 {base}）")
    print(f"cd {path}")


def cmd_finish(root, tid, force):
    known = trees(root)
    if tid not in known:
        fail(f"本机没有任务 {tid} 的树：先 make task-new TASK={tid}，或它已经收尾过了")
    path = known[tid]
    dirty = git(path, "status", "--porcelain")
    if dirty.returncode != 0:
        fail(f"读不了 {path} 的工作区：{dirty.stderr.strip()}", 2)
    if dirty.stdout.strip():
        fail(
            "树里有未提交的改动，拒绝收尾——删树会把它们一起丢掉：\n"
            + dirty.stdout.rstrip()
            + "\n先提交（或 git stash 后自行处理），再跑一次"
        )
    base = base_ref(root, None)
    merged = git(root, "merge-base", "--is-ancestor", PREFIX + tid, base).returncode == 0
    if not merged and not force:
        fail(
            f"分支 {PREFIX}{tid} 还没合并进 {base}：先合并或走 PR。"
            "确认要连未合并的分支一起删，加 --force"
        )
    removed = git(root, "worktree", "remove", str(path))
    if removed.returncode != 0:
        fail(f"删树失败：{removed.stderr.strip()}")
    git(root, "branch", "-d" if merged else "-D", PREFIX + tid)
    git(root, "worktree", "prune")
    note = "" if merged else "（未合并，--force 强删）"
    print(f"已收尾 {tid}：删树 {path}、删分支 {PREFIX}{tid}{note}")


def cmd_list(root):
    known = trees(root)
    rows = [
        t for t in board(root).get("tasks", [])
        if isinstance(t, dict) and t.get("status") in ("doing", "todo")
    ]
    print(f"{'任务':10} {'状态':8} {'树':4} 路径")
    for task in rows:
        tid = task.get("id", "?")
        print(f"{tid:10} {task.get('status', '?'):8} {'有' if tid in known else '无':4} {known.get(tid, '')}")
    for tid in sorted(set(known) - {t.get("id") for t in rows}):
        print(f"{tid:10} {'-':8} {'有':4} {known[tid]}  ← 不在看板或已结束")


def main():
    parser = argparse.ArgumentParser(description="任务级 worktree：开工建树，收尾提交并删树")
    sub = parser.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("new", help="建树")
    new.add_argument("task")
    new.add_argument("--base", default=None)
    finish = sub.add_parser("finish", help="收尾：删树 + 删分支")
    finish.add_argument("task")
    finish.add_argument("--force", action="store_true")
    sub.add_parser("list", help="看板 ↔ 本机树")
    args = parser.parse_args()
    root = repo_root()
    if args.cmd == "new":
        cmd_new(root, args.task, args.base)
    elif args.cmd == "finish":
        cmd_finish(root, args.task, args.force)
    else:
        cmd_list(root)


if __name__ == "__main__":
    main()
