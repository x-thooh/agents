"""docphantom：文档 → 源码方向——文档点名的 code 必须真的存在。

只守 DOC001 一个方向时，删掉/改名一个 code 而文档没跟着改，两边一起漂而门禁全绿。
变异测试撞出过这个洞：把 `SKILL.md` 正文里的 `LP001` 改写成 `ZZ001`，audit 报 0 条。

两处都扫，理由不同：

  * `SKILL.md` 正文 —— 这是入口。它在替一条不存在的断言背书时，读的人不会知道。
  * `acceptance.md` 里把 code 归给 `audit.py` 的行 —— 这张表是「谁守这条规则」的台账。
    只判这些行：表里还有大量目标仓库侧的 code（CONF001 / GATE00x / CM006…），
    它们本来就不该出现在本仓库的 `scripts/scopes/` 里。

判据收窄到「本仓库真实存在的 code」= 本 skill 的 `scripts/` ∪ `templates/`，再加上
跑 audit 的那个 skill（`--skill-dir` 指向 fixture 时，fixture 正文提到父 skill 的
code 是合法的）。这样 fixture 仍构得出失败例：写一个谁都没有的 code 就要报。
"""
import os
import pathlib
import re

from .common import Finding
from .docclaim import ACCEPTANCE_REL, SCOPES_REL, _codes

NAME = "docphantom"

CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')
# 文档里写 code 不带引号（反引号或裸写都算）：只用来判「文档 → 源码」方向。
DOC_CODE_RE = re.compile(r"\b([A-Z]{2,}[0-9]{3})\b")
AUDIT_SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]


def _codes_under(root):
    codes = set()
    for path in sorted(pathlib.Path(root).rglob("*.py")):
        try:
            codes |= set(CODE_LITERAL.findall(path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return codes


def _known_codes(skill_dir):
    """「本仓库里真实存在的 code」：被审目录与跑 audit 的 skill，各自的 scripts/ 与 templates/。"""
    return (_codes_under(pathlib.Path(skill_dir) / "scripts")
            | _codes_under(pathlib.Path(skill_dir) / "templates")
            | _codes_under(AUDIT_SKILL_DIR / "scripts")
            | _codes_under(AUDIT_SKILL_DIR / "templates"))


def _check_skill(text, known, findings):
    phantom = {c for c in DOC_CODE_RE.findall(text) if c not in known}
    if phantom:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC002",
            f"SKILL.md 点到 {len(phantom)} 个 code，本仓库源码里却没有："
            f"{' '.join(sorted(phantom))}。删掉/改名一个 code 而正文没跟着改时，"
            "正文就在替一条不存在的断言背书——「逐个点名」失效的正是这个方向"))


def _check_acceptance(doc, codes, findings):
    phantom = set()
    for line in doc.split("\n"):
        if "audit.py" not in line:
            continue
        phantom |= {c for c in DOC_CODE_RE.findall(line) if c not in codes}
    if phantom:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC002",
            f"{ACCEPTANCE_REL} 把 {len(phantom)} 个 code 归给 audit.py，源码里却没有它们："
            f"{' '.join(sorted(phantom))}。文档点名的载体不存在时，这张表就是假台账",
            path=ACCEPTANCE_REL))


def run(ctx, findings):
    scopes_dir = os.path.join(ctx["skill_dir"], SCOPES_REL)
    if not os.path.isdir(scopes_dir):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    known = _known_codes(ctx["skill_dir"])
    _check_skill(ctx["text"], known, findings)
    codes, unreadable = _codes(scopes_dir)
    if unreadable:
        return  # 读不动的账由 docclaim 报 DOC001，同一原因不报两遍
    path = os.path.join(ctx["skill_dir"], ACCEPTANCE_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            _check_acceptance(fh.read(), codes, findings)
    except OSError:
        return  # 同上：读不动由 docclaim 报
