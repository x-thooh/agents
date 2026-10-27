"""round：行为级的四段对照——一轮 = 一次提交。

把 `HEAD~1` 检出到临时 worktree 跑一遍 verify，再跑当前工作树，比 ERROR 计数；
顺带比手册（`AGENTS.md`）的行数。ERROR 上升、或手册一轮涨过 `GROWTH` 行，即失败。

为什么从 git 取基准、不落状态文件：
  * 落文件就要入库，每轮都改一次，diff 全是噪声；不入库则 CI 拿不到，等于只管本地。
  * 「一轮 = 一次提交」这句话本身就是它的基准来源——父提交就是改前基准，不需要手抄。

为什么用 worktree 而不是 stash：`git stash` 会动用户的工作树，脚本不该替人保管未提交的
改动；worktree 是只读旁路，失败时删掉即可，当前树一个字节都不动。

为什么还要比行数：只比 ERROR 时，「这一轮加了一堆内容、每节都刚好贴着上限」是全绿的。
额度是上限不是目标，真正的判据是环比——20 = 单节额度 80 的四分之一。

用法: python3 .harness/scripts/round.py [基准提交，默认 HEAD~1]
退出码: 0 = 锚点未恶化；1 = ERROR 上升或手册涨太多；2 = 取不到基准 / 环境错误
"""

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERIFY = pathlib.Path(".harness/scripts/verify.py")
HANDBOOK = "AGENTS.md"
GROWTH = 20


def verify(cwd):
    """在该目录跑一次 verify，返回 (errors, warns)。失败时返回 None 并打印原因。"""
    target = cwd / VERIFY
    if not target.is_file():
        return None
    proc = subprocess.run(
        [sys.executable, str(target), "--root", str(cwd), "--json"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        summary = json.loads(proc.stdout)["summary"]
    except (json.JSONDecodeError, KeyError):
        print(f"round: {cwd} 下 verify 没给出可解析的 JSON：{proc.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return summary["errors"], summary["warns"]


def handbook_lines(root):
    """手册行数；读不动返回 None（判不了要说出来，不当 0）。"""
    try:
        return len((root / HANDBOOK).read_text(encoding="utf-8").splitlines())
    except OSError:
        return None


def repo_root():
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    return pathlib.Path(proc.stdout.strip()) if proc.returncode == 0 else None


def main(argv):
    base = argv[1] if len(argv) > 1 else "HEAD~1"
    git_root = repo_root()
    if git_root is None:
        print("round: 不在 git 仓库里，基准取不到", file=sys.stderr)
        return 2
    current = verify(ROOT)
    if current is None:
        return 2
    with tempfile.TemporaryDirectory(prefix="round-") as tmp:
        tree = pathlib.Path(tmp) / "base"
        add = subprocess.run(
            ["git", "-C", str(git_root), "worktree", "add", "--detach", str(tree), base],
            capture_output=True,
            text=True,
            check=False,
        )
        if add.returncode != 0:
            print(f"round: 取基准 {base} 失败：{add.stderr.strip()[:300]}", file=sys.stderr)
            return 2
        try:
            before = verify(tree)
            b_lines = handbook_lines(tree)
        finally:
            subprocess.run(
                ["git", "-C", str(git_root), "worktree", "remove", "--force", str(tree)],
                capture_output=True,
                text=True,
                check=False,
            )
    if before is None:
        print(f"round: 基准 {base} 下没有可跑的 verify", file=sys.stderr)
        return 2
    b_err, b_warn = before
    c_err, c_warn = current
    c_lines = handbook_lines(ROOT)
    # 先把两个数都打出来，再判。判据写在数字后面：先报错再给数，读的人只看见红。
    print(f"round: {base} = {b_err} ERROR / {b_warn} WARN  →  当前 = {c_err} ERROR / {c_warn} WARN")
    if b_lines is None or c_lines is None:
        print(f"round: {HANDBOOK} 行数读不到，环比判不了——不按通过处理", file=sys.stderr)
    else:
        print(f"round: {HANDBOOK} {b_lines} → {c_lines} 行（{c_lines - b_lines:+d}）")
    if c_err > b_err:
        print(
            f"round: ERROR 上升 {c_err - b_err} 条——说不出原因不许交付"
            "（感知 / 反思：与改前基准逐项对照，任何上升都要归因）",
            file=sys.stderr,
        )
        return 1
    if b_lines is not None and c_lines is not None and c_lines - b_lines > GROWTH:
        print(
            f"round: {HANDBOOK} 一轮涨了 {c_lines - b_lines} 行 > {GROWTH} 行：这一轮在塞内容，不是在收口——"
            "把等量的成段细节外置到 .harness/specs/，或拆成两轮",
            file=sys.stderr,
        )
        return 1
    print("round: 锚点未恶化")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
