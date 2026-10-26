"""xrefdoc：reference/ 文件里的跨文件 §X.Y 引用（断言坑 #12：裸编号跨文件）。

SKILL.md 内部的 §X.Y 由 xref scope 管。reference/*.md 里的 §X.Y 指向 ../SKILL.md 的
章节，audit.py 此前完全不读它们——Q7 事故（SKILL.md 写了不存在的 §七.10）若发生在
reference/ 里会静默烂掉。

边界（如实）：这是**存在性检查**——答不了「重排后 §X.Y 是不是原来那一节」（#12
原文：存在性检查答不了「是不是原来那一节」，重排同号静默指向别处仍属人判）。
抓得住的一半是：改号、删节、外置后引用没跟着改。无豁免：引言行里的 §二.5 也是
真引用，一样要能解析（Q1 定的「无豁免」在这里同样生效）。
"""
import os
import re

from .common import CJK_NUM, Finding, as_int, build_sections

NAME = "xrefdoc"

REF_DIR = "reference"
INTERNAL_XREF = re.compile(r"§([" + CJK_NUM + r"]+)(?:\.(\d+))?")

# 两条报错共用的边界说明：存在性检查抓得到改号，抓不到重排同号。
_NOTE = "（跨文件存在性检查；重排同号它管不了，那属人判）"


def run(ctx, findings):
    ref_dir = os.path.join(ctx["skill_dir"], REF_DIR)
    if not os.path.isdir(ref_dir):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    sections = build_sections(ctx["text"].split("\n"))
    for name in sorted(os.listdir(ref_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(ref_dir, name)
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        for idx, ln in enumerate(lines):
            for m in INTERNAL_XREF.finditer(ln):
                letter, sub = m.group(1), m.group(2)
                rel = f"{REF_DIR}/{name}:{idx + 1}"
                if letter not in sections:
                    findings.append(Finding(
                        "ERROR", NAME, idx + 1, "XREFDOC001",
                        f"{rel} §{letter} 指向 SKILL.md 不存在的章节" + _NOTE))
                elif sub is not None and as_int(sub) not in sections[letter]["subs"]:
                    findings.append(Finding(
                        "ERROR", NAME, idx + 1, "XREFDOC002",
                        f"{rel} §{letter}.{sub} 指向 §{letter} 下不存在的条目" + _NOTE))
