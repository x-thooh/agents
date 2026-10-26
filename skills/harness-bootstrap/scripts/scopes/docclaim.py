"""docclaim：文档声称的规则载体必须覆盖代码里真实的每个 code。

§六「文档驱动生成，生成后回写校验」的机器半边：**文档描述必须与代码一致**。
可以手写说明，但不许文档漏掉一个真实存在的发现码——漏掉的那个等于「没人守，
也没人知道它没被守」。`references/code-index.md` 给出全量 code，
本 scope 要求它们在 `references/acceptance.md` 的对照表里都被点到名。

判的是「提到过」而不是「对应的行写得对」：后者是语义，人判（acceptance.md 的强度列
已这么标）。机器能守的那一半守死，够挡住「新增一个 code 却没进文档」这类漂移。

边界：只判本 skill 自己的两份文件；没有 `scripts/scopes/` 的样本记 not_applicable，
不冒充通过（§七.2）。
"""
import os
import re

from .common import Finding

NAME = "docclaim"

CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')
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
