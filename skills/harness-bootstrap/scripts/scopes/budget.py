"""budget：脚本体量与手册总量，各两档。

  BUDGET001  `scripts/` 与 `tests/` 下单个 .py：撞 150 行 WARN，超 200 行 ERROR
  BUDGET002  `SKILL.md` 总量：撞 400 行 WARN，超 500 行 ERROR

为什么单有单节的 80/100 还不够：单节额度管的是「哪一段太长」，管不了「一共多长」。
一节一节都合规而总量翻倍，读的人仍然要整篇读完——手册的加载成本按总量算，不按最大值算。

为什么必须机检：§六 原话是「单文件长到改不动时，下一步就是写一次性补丁脚本打自己」，
实测轨迹里十几次 `.fixN.py` 全部起于一个只会变大的单文件。但这句话此前没有断言——
`layout` scope 的 200 行只量调度器（它判的是「scope 实现有没有搬回调度器」），
scopes 自己长多大没人管。规矩没有数值就是愿望。

阈值为什么是 150/200：
  200 是本仓库既有的上限，不另发明新数（现住 `common.CODE_LIMIT`，全仓一处）；
  150 是它的四分之三，与文档的 80/100（提前量 20%）同构——先给一段准备拆的余量，
  不要等到撞线才靠删内容腾地方。
  落地时三个文件正贴着这条线（audit.py 150、codeindex.py 149、layout_parity.py 149），
  所以这条规则不是装饰：下一个改动就会触发它。

不重复报 audit.py：调度器有自己的上限（`layout.LAYOUT001`，200 行）。
两处都管会让同一个文件报两条，而两份阈值迟早对不上。

为什么管到 `tests/`：只扫 `scripts/` 时，`tests/fixtures.py` 长到 238 行、自己给定的
200 行上限之上，而门禁全绿——「字面上成立、在覆盖面上一半」正是最容易过的自我欺骗（v1 评审原话）。
口径只扩到 `tests/` 顶层的 .py：`tests/fixtures/` 底下是**故意坏的样本**，
它们超行数、写坏链接都是本职工作，拿体量去审它们等于把门口的体重计摆到手术台边。
"""
import os

from . import common
from .common import Finding, line_count

NAME = "budget"

# 数值不在这里：CODE_WARN / CODE_LIMIT 住在 common.py（全仓唯一事实源）。
# 调度器也照这条线——它只该负责调度，但「多大算大」是同一把尺子。
SKIP_DIRS = {"__pycache__"}
# 扫描面：目录名 → 该目录下要跳过的顶层子目录。
# tests/fixtures 是故意坏的样本，不参与体量判定（见模块 docstring 末段）。
SCAN_DIRS = (("scripts", ()), ("tests", ("fixtures",)))


def _files(root, label, skip_top):
    """按相对路径升序返回 (相对路径, 行数)；读不动的记一条 ERROR 由调用方处理。"""
    out, unreadable = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not (dirpath == root and d in skip_top)
        )
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.join(label, os.path.relpath(full, root))
            try:
                with open(full, encoding="utf-8") as fh:
                    n = line_count(fh.read())
            except OSError as exc:
                unreadable.append(f"{rel}（{exc.strerror}）")
                continue
            out.append((rel, n))
    return out, unreadable


def _check_total(ctx, findings):
    """SKILL.md 总量。与单节额度同时生效：超总量报 BUDGET002，不并进 SECT001。"""
    total = line_count(ctx["text"])
    if total > common.SKILL_LIMIT:
        findings.append(Finding(
            "ERROR", NAME, 1, "BUDGET002",
            f"SKILL.md 共 {total} 行 > {common.SKILL_LIMIT} 行上限：外置细节，"
            f"把「要用时去查」的部分挪进 references/，别靠删判据腾地方"))
    elif total > common.SKILL_WARN:
        findings.append(Finding(
            "WARN", NAME, 1, "BUDGET002",
            f"SKILL.md 共 {total} 行 > {common.SKILL_WARN} 行：准备外置——"
            f"还有 {common.SKILL_LIMIT - total} 行余地，现在就把成段的细节搬走"))


def run(ctx, findings):
    _check_total(ctx, findings)
    present = [(label, os.path.join(ctx["skill_dir"], label), skip)
               for label, skip in SCAN_DIRS
               if os.path.isdir(os.path.join(ctx["skill_dir"], label))]
    if not present:
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    files, unreadable = [], []
    for label, root, skip in present:
        found, bad = _files(root, label, skip)
        files += found
        unreadable += bad
    for rel in unreadable:
        findings.append(Finding(
            "ERROR", NAME, 0, "BUDGET001",
            f"读不了 {rel}：体量判不了，不能当通过",
            path=rel))
    if not files:
        # 有 scripts/ 或 tests/ 却一个 .py 都没读到：那是扫描失效，不是「都很小」——坑 #11
        ctx.setdefault("not_applicable", []).append(f"{NAME}(scripts/ 与 tests/ 下没有 .py，判不了)")
        return
    for rel, n in files:
        if n > common.CODE_LIMIT:
            findings.append(Finding(
                "ERROR", NAME, 0, "BUDGET001",
                f"{n} 行 > {common.CODE_LIMIT} 行上限：必须拆——按职责分文件，"
                f"别等它长成那个「只会变大的单文件」",
                path=rel))
        elif n > common.CODE_WARN:
            findings.append(Finding(
                "WARN", NAME, 0, "BUDGET001",
                f"{n} 行 > {common.CODE_WARN} 行：准备拆——还有 {common.CODE_LIMIT - n} 行余地，"
                f"现在就把职责边界分出去，别等撞到 {common.CODE_LIMIT} 行再靠删注释腾地方",
                path=rel))
