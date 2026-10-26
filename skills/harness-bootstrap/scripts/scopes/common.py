"""所有 scope 模块共用：Finding 类型 + 纯解析工具（无副作用、不写文件）。"""
import re

CJK_NUM = "〇一二三四五六七八九十"
PLACEHOLDER = "\u2026"


class Finding:
    __slots__ = ("severity", "scope", "line", "code", "message")

    def __init__(self, severity, scope, line, code, message):
        self.severity = severity
        self.scope = scope
        self.line = line
        self.code = code
        self.message = message

    def as_dict(self):
        return {
            "severity": self.severity,
            "scope": self.scope,
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
