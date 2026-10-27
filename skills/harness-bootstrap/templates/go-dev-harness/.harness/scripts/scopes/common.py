"""Shared helpers for go-dev-harness verify scopes. Standard library only."""

import datetime
import json
import re
import subprocess
from pathlib import Path


class Finding:
    __slots__ = ("code", "line", "message", "path", "scope", "severity")

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


def number(value):
    """数字则返回它，否则 None——把「是不是数字」和「值是多少」合成一次判定。

    为什么必须有它：`num(x)` 只回 True/False，判定之后仍然拿原来的 `x` 做算术，
    读代码的人（和类型检查器）都无法确定 x 已被验证过。实测这在模板里攒出 12 条
    reportOptionalOperand（`None < 8`、`None * 1.2`），全是「先判后算」的同一形态。
    写法改成 `value = number(raw)` + `if value is None` 之后，分支本身就是证据。
    """
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


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
    """Require keys to exist and be non-empty. Numbers/bools pass; null does not."""
    ok = True
    for key in required:
        if not isinstance(obj, dict) or key not in obj:
            add(findings, "ERROR", scope, path, 1, code, f"{prefix}{key} 缺失")
            ok = False
            continue
        value = obj[key]
        if value is None or (isinstance(value, str) and not value.strip()) or (
            isinstance(value, (list, dict)) and not value
        ):
            add(findings, "ERROR", scope, path, 1, code, f"{prefix}{key} 不能为空")
            ok = False
    return ok


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


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
    allowed = {"contract", "design", "scope", "schedule", "env"}
    if change.get("type") not in allowed:
        add(findings, "ERROR", scope, path, 1, code, f"change {change.get('id', '?')} 的 type 不在 {sorted(allowed)}")


# --- Go source helpers -------------------------------------------------------


def go_src(root, quality):
    """Module root: quality.json `go_src` (default "."). Missing dir is not this helper's call."""
    rel = quality_get(quality, "go_src", ".")
    return Path(root) / (rel if isinstance(rel, str) and rel.strip() else ".")


def go_files(src, include_tests=True):
    files = sorted(p for p in Path(src).rglob("*.go") if p.is_file())
    if include_tests:
        return files
    return [p for p in files if not p.name.endswith("_test.go")]


def rel_to(root, path):
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def go_package(path):
    """Package clause of a Go file, or '' when absent."""
    try:
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.startswith("package "):
                return stripped.split()[1]
    except OSError:
        return ""
    return ""


def _scan(line, in_block):
    """Return (code_without_comments, in_block). String literals are kept verbatim."""
    buf = []
    i, n = 0, len(line)
    in_str = None
    while i < n:
        if in_block:
            if line.startswith("*/", i):
                in_block = False
                i += 2
                continue
            i += 1
            continue
        ch = line[i]
        if in_str:
            buf.append(ch)
            if in_str == '"' and ch == "\\" and i + 1 < n:
                buf.append(line[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if line.startswith("//", i):
            break
        if line.startswith("/*", i):
            in_block = True
            i += 2
            continue
        if ch in ('"', "`"):
            in_str = ch
            buf.append(ch)
            i += 1
            continue
        buf.append(ch)
        i += 1
    return "".join(buf), in_block


def code_lines(path):
    """[(lineno, code)] with comments stripped; line numbers stay original."""
    out = []
    in_block = False
    try:
        raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for idx, raw in enumerate(raw_lines, 1):
        code, in_block = _scan(raw, in_block)
        out.append((idx, code))
    return out


def blank_strings(code):
    """把字面量内容抹成空格，引号保留。注释不动（TODO 常常就在注释里）。

    code_lines() 故意保留字面量原文——错误文案标点（RUNT008）、%w、ERROR_LITERAL
    都要读它。所以「禁某个调用」类断言必须读这份抹过的副本：否则
    var _ = "panic(" 会被判成真调用，而正对照照样是绿的。

    抹成空格而不是删掉：删掉会让 pa"x"nic( 拼回 panic(，把误报换成另一种误报。
    """
    out = []
    in_str = None
    i = 0
    while i < len(code):
        ch = code[i]
        if in_str:
            if ch == "\\" and in_str == '"' and i + 1 < len(code):
                out.append("  ")
                i += 2
                continue
            if ch == in_str:
                in_str = None
                out.append(ch)
            else:
                out.append(" ")
            i += 1
            continue
        if ch in ('"', "`", "'"):
            in_str = ch
        out.append(ch)
        i += 1
    return "".join(out)


def is_test_file(path):
    return str(path).endswith("_test.go")


def go_imports(path):
    """Import paths of a Go file (single-line and block form)."""
    paths = []
    in_block = False
    try:
        raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return paths
    for raw in raw_lines:
        line = raw.strip()
        if in_block:
            if line.startswith(")"):
                in_block = False
                continue
            paths.append(line.strip('"'))
            continue
        if line.startswith("import ("):
            in_block = True
            continue
        if line.startswith("import "):
            paths.append(line[len("import ") :].strip().strip('"'))
    return [p for p in paths if p]


WORD_ERR = re.compile(r"\berr\b")


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


# --- 证据时效 ---------------------------------------------------------------


def head_commit(root):
    """当前 HEAD；不是 git 仓库或没有提交时返回 None。"""
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=False, capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def check_evidence_commit(root, data, rel, scope, code, findings):
    """证据必须对应当前 HEAD；没有 git 时只 WARN，不冒充通过。

    `example: true` 的示例数据跳过：strict 已经用 EXAMPLE001 拦它，这里再报一次
    只是同一原因的第二条。真实数据才要求 commit 等于 HEAD。
    """
    if data.get("example") is True:
        return
    at = data.get("at")
    try:
        datetime.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        add(findings, "ERROR", scope, rel, 1, code, f"at = {at!r} 不是 ISO 8601 时间")
    head = head_commit(root)
    if head is None:
        add(findings, "WARN", scope, rel, 1, code, "没有 git，证据时效判不了；不按通过处理")
        return
    commit = data.get("commit")
    if commit != head:
        add(
            findings,
            "ERROR",
            scope,
            rel,
            1,
            code,
            f"证据 commit {str(commit)[:12]!r} 不是当前 HEAD {head[:12]!r}：重新跑 make evidence",
        )


# --- --fix 前置条件 ---------------------------------------------------------


def git_clean(root, targets=()):
    """`--fix` 的前置条件：在 git 仓库内，且**除目标文件外**工作区干净。

    返回 None = 可以修；否则返回给人看的原因。

    目标文件必须排除，有两个理由：
      1. 派生数据的本地改动本来就是缺陷（GUIDE001 就是来抓它的），不算「你的工作」；
      2. 「提交被拦 → 修 → 再提交」这条最自然的恢复路径，正好卡在目标文件是脏的。
    没有回滚点就改文件比不改更坏：改坏了分不清哪部分是脚本干的。
    """

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True, text=True)

    inside = git("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return "需要 git 仓库（没有回滚点就不许改文件）：先 git init 并提交一次"
    # 只看 root 子树：harness 可能只是某个大仓库里的一个目录，
    # 仓库别处的脏文件跟这次修复无关，不该拦。
    pathspec = [".", *[f":!{target}" for target in targets]]
    status = git("status", "--porcelain", "--", *pathspec)
    if status.returncode != 0:
        return f"git status 失败：{status.stderr.strip()}"
    dirty = status.stdout.strip()
    if dirty:
        return (
            "工作区不干净（`--fix` 会重写的派生文件除外），先提交或 stash——"
            "否则修完分不清哪些是你改的、哪些是脚本改的\n" + dirty
        )
    return None
