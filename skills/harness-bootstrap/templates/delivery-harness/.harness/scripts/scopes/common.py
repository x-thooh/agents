"""Shared helpers for delivery-harness verify scopes. Standard library only."""
import datetime
import json
from pathlib import Path


class Finding:
    __slots__ = ("severity", "scope", "path", "line", "code", "message")

    def __init__(self, severity, scope, path, line, code, message):
        self.severity = severity
        self.scope = scope
        self.path = path
        self.line = line
        self.code = code
        self.message = message

    def as_dict(self):
        return {
            "severity": self.severity,
            "scope": self.scope,
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "message": self.message,
        }


def add(findings, severity, scope, path, line, code, message):
    findings.append(Finding(severity, scope, path, line, code, message))


def text(value):
    return isinstance(value, str) and value.strip() != ""


def num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def as_list(value):
    return value if isinstance(value, list) else []


def as_dict(value):
    return value if isinstance(value, dict) else {}


def load_json(root, rel, scope, findings, code):
    path = Path(root) / rel
    if not path.is_file():
        add(findings, "ERROR", scope, rel, 1, code, f"缺少 {rel}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add(findings, "ERROR", scope, rel, 1, code, f"{rel} 读取失败: {exc}")
        return None


def warn_example(data, rel, scope, findings, strict):
    if isinstance(data, dict) and data.get("example") is True:
        severity = "ERROR" if strict else "WARN"
        add(
            findings,
            severity,
            scope,
            rel,
            1,
            "EXAMPLE001",
            f"{rel} 是示例数据（example: true）；交付前必须替换为真实证据",
        )


def quality_get(quality, dotted, default=None):
    cur = quality
    for key in dotted.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def check_fields(obj, required, scope, path, findings, code, prefix=""):
    """Require keys to exist and be non-empty strings/lists. Numbers/bools pass."""
    ok = True
    for key in required:
        if not isinstance(obj, dict) or key not in obj:
            add(findings, "ERROR", scope, path, 1, code, f"{prefix}{key} 缺失")
            ok = False
            continue
        value = obj[key]
        if isinstance(value, str) and not value.strip():
            add(findings, "ERROR", scope, path, 1, code, f"{prefix}{key} 不能为空")
            ok = False
        elif isinstance(value, list) and not value:
            add(findings, "ERROR", scope, path, 1, code, f"{prefix}{key} 不能为空")
            ok = False
    return ok


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def business_days_between(start, end):
    """Weekdays only; holidays are intentionally out of scope."""
    if start is None or end is None or start > end:
        return -1
    days = 0
    cur = start
    while cur < end:
        cur += datetime.timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days


def has_cycle(graph):
    state = {}

    def visit(node):
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    return any(visit(node) for node in list(graph))


def validate_exception(exc, scope, path, findings, code):
    check_fields(exc, ("id", "issue", "owner", "approver", "expiry"), scope, path, findings, code, "exception.")
    expiry = parse_date(exc.get("expiry"))
    if expiry is None:
        add(findings, "ERROR", scope, path, 1, code, f"exception {exc.get('id', '?')} 的 expiry 不是 YYYY-MM-DD")
    elif expiry < datetime.date.today():
        add(findings, "ERROR", scope, path, 1, code, f"exception {exc.get('id', '?')} 已过期（{expiry}）")


def validate_change(change, scope, path, findings, code):
    check_fields(
        change,
        ("id", "type", "description", "reason", "impact", "approver", "notified", "rebaselined", "rollback"),
        scope,
        path,
        findings,
        code,
        "change.",
    )
    allowed = {"prd", "scope", "contract", "design", "schedule", "env"}
    if change.get("type") not in allowed:
        add(findings, "ERROR", scope, path, 1, code, f"change {change.get('id', '?')} 的 type 不在 {sorted(allowed)}")


GUIDE_IGNORE = {".git", "__pycache__", ".idea", ".ruff_cache", "node_modules", ".venv"}
GUIDE_SUFFIXES = {".py", ".json", ".md", ".sh", ".go", ".yaml", ".yml", ".toml"}


def build_guide(root, depth=2):
    """Deterministic code map: dirs and text files up to `depth`. Written only by gen_guide.py."""
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in GUIDE_IGNORE for part in rel.parts):
            continue
        if len(rel.parts) > depth:
            continue
        if path.is_dir():
            entries.append({"path": rel.as_posix(), "kind": "dir"})
        elif path.suffix in GUIDE_SUFFIXES:
            entries.append({"path": rel.as_posix(), "kind": "file"})
    return {"generated_by": ".harness/scripts/gen_guide.py", "depth": depth, "entries": entries}


LESSON_KEYS = ("现象", "根因", "断言")


def check_lessons(content, scope, path, findings, code):
    """每条 lesson 必须有现象/根因/断言三段；缺第三段就是抱怨，不是记忆。"""
    blocks = []
    current = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    if not blocks:
        add(findings, "ERROR", scope, path, 1, code, "lessons.md 里没有任何 `## ` 条目")
        return
    for block in blocks:
        body = "\n".join(block)
        title = block[0].strip()
        for key in LESSON_KEYS:
            if f"{key}:" not in body and f"{key}：" not in body:
                add(findings, "ERROR", scope, path, 1, code, f"{title} 缺「{key}」一段")

