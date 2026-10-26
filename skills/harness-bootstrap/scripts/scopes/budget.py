"""budget：`scripts/` 下每个文件的体量预算，两档。

  BUDGET001 撞 150 行 WARN（准备拆）；超 200 行 ERROR（必须拆）

为什么必须机检：§六 原话是「单文件长到改不动时，下一步就是写一次性补丁脚本打自己」，
实测轨迹里十几次 `.fixN.py` 全部起于一个只会变大的单文件。但这句话此前没有断言——
`layout` scope 的 200 行只量调度器（它判的是「scope 实现有没有搬回调度器」），
scopes 自己长多大没人管。规矩没有数值就是愿望。

阈值为什么是 150/200：
  200 是本仓库既有的上限（`layout.LIMIT`），不另发明新数；
  150 是它的四分之三，与文档的 80/100（提前量 20%）同构——先给一段准备拆的余量，
  不要等到撞线才靠删内容腾地方。
  落地时三个文件正贴着这条线（audit.py 150、codeindex.py 149、layout_parity.py 149），
  所以这条规则不是装饰：下一个改动就会触发它。

不重复报 audit.py：调度器有自己的上限（`layout.LAYOUT001`，200 行）。
两处都管会让同一个文件报两条，而两份阈值迟早对不上。
"""
import os

from .common import Finding

NAME = "budget"

WARN_AT = 150  # 准备拆
LIMIT = 200    # 必须拆

SKIP = {"audit.py"}  # 调度器由 LAYOUT001 管，见文件头
SKIP_DIRS = {"__pycache__"}


def _files(root):
    """按相对路径升序返回 (相对路径, 行数)；读不动的记一条 ERROR 由调用方处理。"""
    out, unreadable = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if rel in SKIP:
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    n = len(fh.read().split("\n"))
            except OSError as exc:
                unreadable.append(f"{rel}（{exc.strerror}）")
                continue
            out.append((rel, n))
    return out, unreadable


def run(ctx, findings):
    root = os.path.join(ctx["skill_dir"], "scripts")
    if not os.path.isdir(root):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    files, unreadable = _files(root)
    for rel in unreadable:
        findings.append(Finding(
            "ERROR", NAME, 0, "BUDGET001",
            f"读不了 {rel}：体量判不了，不能当通过",
            path=f"scripts/{rel}"))
    if not files:
        # 有 scripts/ 目录却一个 .py 都没读到：那是扫描失效，不是「都很小」——坑 #11
        ctx.setdefault("not_applicable", []).append(f"{NAME}(scripts/ 下没有 .py，判不了)")
        return
    for rel, n in files:
        if n > LIMIT:
            findings.append(Finding(
                "ERROR", NAME, 0, "BUDGET001",
                f"{n} 行 > {LIMIT} 行上限：必须拆——按职责分文件，"
                f"别等它长成那个「只会变大的单文件」",
                path=f"scripts/{rel}"))
        elif n > WARN_AT:
            findings.append(Finding(
                "WARN", NAME, 0, "BUDGET001",
                f"{n} 行 > {WARN_AT} 行：准备拆——还有 {LIMIT - n} 行余地，"
                f"现在就把职责边界分出去，别等撞到 {LIMIT} 行再靠删注释腾地方",
                path=f"scripts/{rel}"))
