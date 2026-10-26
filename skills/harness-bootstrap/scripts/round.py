"""round：行为级的四段对照——一轮 = 一次提交。

文本级由 `loop` scope 判（四节有没有分列、钩子与 code 集对不对账）；本脚本判的是
**这次改动到底有没有把锚点弄坏**：把 `HEAD~1` 检出到临时 worktree 跑一遍 audit，
再跑当前工作树，比计数。上升即失败。

为什么从 git 取基准、不落状态文件：
  * 落文件就要入库，每轮都改一次，diff 全是噪声；不入库则 CI 拿不到，等于只管本地。
  * 「一轮 = 一次提交」这句话本身就是它的基准来源——父提交就是改前基准，不需要手抄。

为什么用 worktree 而不是 stash：
  `git stash` 会动用户的工作树，脚本不该替人保管未提交的改动；worktree 是只读旁路，
  失败时删掉即可，当前树一个字节都不动。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent


def audit(cwd):
    """在该目录跑一次 audit，返回 (errors, warns)。失败时返回 None 并打印原因。"""
    target = cwd / "scripts" / "audit.py"
    if not target.is_file():
        return None
    proc = subprocess.run([sys.executable, str(target), "--json"],
                          cwd=str(cwd), capture_output=True, text=True, check=False)
    try:
        summary = json.loads(proc.stdout)["summary"]
    except (json.JSONDecodeError, KeyError):
        print(f"round: {cwd} 下 audit 没给出可解析的 JSON：{proc.stderr.strip()[:200]}",
              file=sys.stderr)
        return None
    return summary["errors"], summary["warns"]


def repo_root():
    proc = subprocess.run(["git", "-C", str(SKILL), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=False)
    return pathlib.Path(proc.stdout.strip()) if proc.returncode == 0 else None


def main(argv):
    base = argv[1] if len(argv) > 1 else "HEAD~1"
    root = repo_root()
    if root is None:
        print("round: 不在 git 仓库里，基准取不到", file=sys.stderr)
        return 2
    rel = SKILL.relative_to(root)
    current = audit(SKILL)
    if current is None:
        return 2
    with tempfile.TemporaryDirectory(prefix="round-") as tmp:
        tree = pathlib.Path(tmp) / "base"
        add = subprocess.run(["git", "-C", str(root), "worktree", "add", "--detach",
                              str(tree), base], capture_output=True, text=True, check=False)
        if add.returncode != 0:
            print(f"round: 取基准 {base} 失败：{add.stderr.strip()[:300]}", file=sys.stderr)
            return 2
        try:
            before = audit(tree / rel)
        finally:
            subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(tree)],
                           capture_output=True, text=True, check=False)
    if before is None:
        print(f"round: 基准 {base} 下没有可跑的 audit", file=sys.stderr)
        return 2
    b_err, b_warn = before
    c_err, c_warn = current
    print(f"round: {base} = {b_err} ERROR / {b_warn} WARN  →  当前 = {c_err} ERROR / {c_warn} WARN")
    if c_err > b_err:
        print(f"round: ERROR 上升 {c_err - b_err} 条——说不出原因不许交付"
              "（§〇 感知 / §三 反思：与改前基准逐项对照，任何上升都要归因）", file=sys.stderr)
        return 1
    print("round: 锚点未恶化")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
