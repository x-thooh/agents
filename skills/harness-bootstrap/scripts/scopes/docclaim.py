"""docclaim：文档声称的规则载体必须覆盖代码里真实的每个 code。

§六「文档驱动生成，生成后回写校验」的机器半边：**文档描述必须与代码一致**。
可以手写说明，但不许文档漏掉一个真实存在的发现码——漏掉的那个等于「没人守，
也没人知道它没被守」。`references/code-index.md` 给出全量 code，
本 scope 要求它们在 `references/acceptance.md` 的对照表里都被点到名。

判的是「提到过」而不是「对应的行写得对」：后者是语义，人判（acceptance.md 的强度列
已这么标）。机器能守的那一半守死，够挡住「新增一个 code 却没进文档」这类漂移。

  DOC001  源码 → 文档：代码里会报的 code，文档必须点到名（漏了=没人知道谁守它）。
  DOC002  反方向在 `docphantom.py`（文档点名的 code 必须真存在）。
          只守 DOC001 时，删掉一个 code 而文档没改，两边一起漂而门禁全绿——「幻影 code」。
          判据收窄到「同一行里出现 `audit.py`」的行：acceptance.md 里还有大量目标仓库侧
          的 code（CONF001 / GATE00x / CM006…），它们本来就不该在这个仓库的源码里。

边界：只判本 skill 自己的两份文件；没有 `scripts/scopes/` 的样本记 not_applicable，
不冒充通过（§七.2）。
"""
import os
import pathlib
import re

from .common import Finding

NAME = "docclaim"

CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')
# 文档里写 code 不带引号（反引号或裸写都算）：只用来判「文档 → 源码」方向。
DOC_CODE_RE = re.compile(r"\b([A-Z]{2,}[0-9]{3})\b")
ACCEPTANCE_REL = os.path.join("references", "acceptance.md")
SCOPES_REL = os.path.join("scripts", "scopes")


def _codes(scopes_dir):
    codes, unreadable = set(), []
    real_dir = os.path.realpath(scopes_dir)
    try:
        names = sorted(os.listdir(scopes_dir))
    except OSError as exc:
        return codes, [f"目录不可读（{exc.strerror}）"]
    for name in names:
        if not name.endswith(".py"):
            continue
        path = os.path.realpath(os.path.join(scopes_dir, name))
        if os.path.dirname(path) != real_dir:
            unreadable.append(f"{name}（指向目录外，已跳过）")
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                codes |= set(CODE_LITERAL.findall(fh.read()))
        except OSError as exc:
            unreadable.append(f"{name}（{exc.strerror}）")
    return codes, unreadable


def run(ctx, findings):
    scopes_dir = os.path.join(ctx["skill_dir"], SCOPES_REL)
    if not os.path.isdir(scopes_dir):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    codes, unreadable = _codes(scopes_dir)
    if unreadable:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC001",
            "有 scope 模块读不动，文档覆盖判不了，不能当通过：" + "；".join(unreadable),
            path=SCOPES_REL))
        return
    path = os.path.join(ctx["skill_dir"], ACCEPTANCE_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()
    except OSError as exc:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC001",
            f"读不了 {ACCEPTANCE_REL}（{exc.strerror}）：文档覆盖判不了，不能当通过",
            path=ACCEPTANCE_REL))
        return

    missing = sorted(c for c in codes if c not in doc)
    if missing:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC001",
            f"{ACCEPTANCE_REL} 少点了 {len(missing)} 个 code：{' '.join(missing)}。"
            "代码里会报却发现文档里没有它的行——那就没人知道这条规则是否有人守。"
            "补进对照表（或显式标「无断言」并写明强度来源）",
            path=ACCEPTANCE_REL))
