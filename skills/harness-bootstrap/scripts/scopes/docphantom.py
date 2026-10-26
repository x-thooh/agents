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

第三个方向：文档点名的 **scope 模块** 也必须真的存在（v2 评审 §4-3）。只守 code 时，
把 `layout_parity` 改写成 `ghostscope` 仍全绿——而「.harness/scripts/scopes/ 一个 scope
一个文件」这件事靠 scope 名指路，名字错了指向就不存在。

为什么不能直接「见 `` `xxx` `` 就查」：文档里大量反引号是字段名、路径、命令
（`scope`、`summary`、`import`、`verify`），抓一个报一个。实测 20+ 处误报，
而误报会把真发现淹掉。所以只在两种写法上判，**并且要求这一行在讲本仓库的载体**
（提到 `audit.py` 或本仓库某个真实 code）——`acceptance.md` 里 `scope=notes` 指的是
目标仓库自己的 scope，不是本仓库的，那行不满足条件就不查。
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
# scope 名的三种写法：`` `name` scope ``、`scope=name`、以及 `` `name` 的 `CODE` ``（文档把
# scope 与它报的 code 写在同一个句子里，这是最自然的指路方式）。
BACKTICK_SCOPE = re.compile(r"`([a-z][a-z0-9_]*)`\s+scope\b")
SCOPE_EQ = re.compile(r"scope=([a-z][a-z0-9_]*)")
PAIRED_SCOPE = re.compile(r"`([a-z][a-z0-9_]*)`[^`\n]{0,6}`[A-Z]{2,}[0-9]{3}`")
# 「目标仓库」一出现，说明该行在讲**别人家的**载体：`acceptance.md` 右欄大量是
# 「目标仓库 verify `scope=archive`」。拿本仓库的 scope 名单去审这些行，每一条都是误报。
# 不把「模板」也列进来：模板自己的 scope 已经在本仓库的已知名单里（`_scopes_under`
# 走 rglob，连 `.harness/scripts/scopes/` 一并收），列进来只会让「模板是产物」这类
# 正文里的普通用词变成漏判。
OTHER_REPO = ("目标仓库",)
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


def _scopes_under(root):
    """任何 `scopes/` 目录下的模块名。rglob 而不是只看一层：模板的 scope 在
    `.harness/scripts/scopes/` 下，与本 skill 的 `scripts/scopes/` 不同深度。"""
    return {p.stem for p in pathlib.Path(root).rglob("*.py") if p.parent.name == "scopes"}


def _check_scopes(text, known_scopes, known_codes, findings):
    """文档点名的 scope 模块必须存在。只在「这一行在讲本仓库载体」时判（见模块 docstring）。"""
    phantom = set()
    for line in text.splitlines():
        if any(word in line for word in OTHER_REPO):
            continue
        if "audit.py" not in line and not any(code and code in line for code in known_codes):
            continue
        names = (set(BACKTICK_SCOPE.findall(line)) | set(SCOPE_EQ.findall(line))
                 | set(PAIRED_SCOPE.findall(line)))
        phantom |= {n for n in names if n not in known_scopes}
    if phantom:
        findings.append(Finding(
            "ERROR", NAME, 0, "DOC002",
            f"文档点到 {len(phantom)} 个 scope 模块，本仓库里却没有："
            f"{' '.join(sorted(phantom))}。改 scope 名而文档没跟着改时，"
            "「一个 scope 一个文件」这句话指向的目录已经不存在了"))


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
    known_scopes = (_scopes_under(ctx["skill_dir"]) | _scopes_under(AUDIT_SKILL_DIR))
    _check_scopes(ctx["text"], known_scopes, known, findings)
    codes, unreadable = _codes(scopes_dir)
    if unreadable:
        return  # 读不动的账由 docclaim 报 DOC001，同一原因不报两遍
    path = os.path.join(ctx["skill_dir"], ACCEPTANCE_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            _check_acceptance(fh.read(), codes, findings)
    except OSError:
        return  # 同上：读不动由 docclaim 报
