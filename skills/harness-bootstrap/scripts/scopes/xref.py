"""xref：内部交叉引用 `§六`、`§七.5` 指向存在的章节/条目。"""
import re

from .common import CJK_NUM, Finding, as_int, build_sections

NAME = "xref"

INTERNAL_XREF = re.compile(r"§([" + CJK_NUM + r"]+)(?:\.(\d+))?")


def run(ctx, findings):
    lines = ctx["text"].split("\n")
    sections = build_sections(lines)
    for idx, ln in enumerate(lines):
        for m in INTERNAL_XREF.finditer(ln):
            letter, sub = m.group(1), m.group(2)
            if letter not in sections:
                findings.append(Finding(
                    "ERROR", NAME, idx + 1, "XREF001",
                    f"交叉引用 §{letter} 指向不存在的章节"))
            elif sub is not None and as_int(sub) not in sections[letter]["subs"]:
                findings.append(Finding(
                    "ERROR", NAME, idx + 1, "XREF002",
                    f"交叉引用 §{letter}.{sub} 指向 §{letter} 下不存在的条目"))
