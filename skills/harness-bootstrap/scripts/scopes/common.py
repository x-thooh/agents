"""所有 scope 模块共用：Finding 类型 + 纯解析工具（无副作用、不写文件）。"""
import re

CJK_NUM = "〇一二三四五六七八九十"
PLACEHOLDER = "\u2026"


class Finding:
    """一条发现。`path` 默认 None = 就在 SKILL.md 里（多数 scope 如此）；
    判的是根目录条目或别的文件时，才显式给 path，免得报错位置指错地方。"""

    __slots__ = ("code", "line", "message", "path", "scope", "severity")

    def __init__(self, severity, scope, line, code, message, path=None):
        self.severity = severity
        self.scope = scope
        self.line = line
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self):
        return {
            "severity": self.severity,
            "scope": self.scope,
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "message": self.message,
        }


def split_frontmatter(text):
    """返回 (frontmatter 行列表, frontmatter 在文件中的起始行号 1-based) 或 (None, None)。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx], 2  # 文件第 2 行起
    return None, None


def parse_fields(fm_lines, first_line):
    """解析顶层字段：key -> {line, style, body_lines}。只支持 audit 所需的简单形态。"""
    fields = {}
    cur = None
    for i, raw in enumerate(fm_lines):
        ln = raw.rstrip()
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", ln)
        if m:
            cur = m.group(1)
            fields[cur] = {"line": first_line + i, "style": m.group(2).strip(), "body": []}
        elif cur is not None and ln.startswith((" ", "\t")):
            fields[cur]["body"].append(ln.strip())
        elif ln.strip() and not ln.startswith((" ", "\t")):
            cur = None  # 其他顶层构造（列表等），不归任何字段
    return fields


def field_value(f):
    if f["style"] in (">", "|"):
        joiner = " " if f["style"] == ">" else "\n"
        return joiner.join(f["body"]).strip()
    return f["style"].strip().strip("'\"")


def as_int(digits, default=0):
    """正则已保证是数字；仍然保护一下，不让畸形输入把整个门禁搞崩。"""
    try:
        return int(digits)
    except (TypeError, ValueError):
        return default


# ── 额度常量：全仓唯一事实源。references/doc-budgets.md 只解释语义，不写数字 ──
# 文档：单节 / 参考材料单文件。撞 DOC_WARN 准备拆，超 DOC_LIMIT 必须拆。
DOC_WARN, DOC_LIMIT = 80, 100
# 代码：scripts/ 下每个文件（含调度器）。150 是 200 的四分之三，留准备拆的余量。
CODE_WARN, CODE_LIMIT = 150, 200
# 手册总量：SKILL.md 是「按顺序读完才能干对活」的那一份，单节有额度不代表总量有。
# 400 是 500 的五分之四（同「提前一段」的比例），500 是宿主侧的通用上限。
SKILL_WARN, SKILL_LIMIT = 400, 500


def line_count(text):
    """按「编辑器里的行数」数行，等价于 wc -l（文件以换行结尾时）。

    为什么要专门一个函数：len(text.split("\\n")) 在文件以换行结尾时会多算 1，
    于是「80 行上限」实际在 wc 的 79 就触发，而报错里打印的 N 也和编辑器对不上。
    同一个词「行」被三种算法解释时，读者第一个反应是不信这个门禁。
    """
    if not text:
        return 0
    return text.count("\n") if text.endswith("\n") else text.count("\n") + 1


def build_sections(lines):
    """letter -> {"line": 标题行, "subs": {条目号}}，支持 §X 与 §X.Y。"""
    secs = {}
    cur = None
    for idx, ln in enumerate(lines):
        m = re.match(r"^##\s+(?P<letter>[" + CJK_NUM + r"]+)、", ln)
        if m:
            cur = m.group("letter")
            secs[cur] = {"line": idx + 1, "subs": set()}
            continue
        if cur is None:
            continue
        mh = re.match(r"^###\s+(\d+)\.", ln)
        if mh:
            secs[cur]["subs"].add(as_int(mh.group(1)))
        ml = re.match(r"^(\d+)\.\s", ln)
        if ml:
            secs[cur]["subs"].add(as_int(ml.group(1)))
        mt = re.match(r"^\|\s*(\d+)(?=\s|\|)", ln)
        if mt:
            secs[cur]["subs"].add(as_int(mt.group(1)))
    return secs
