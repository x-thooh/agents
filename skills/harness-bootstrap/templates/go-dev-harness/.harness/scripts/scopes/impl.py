"""impl: 编码阶段证据（build/vet/lint）+ 源码卫生。"""

import re
from pathlib import Path

from .common import (
    add,
    as_dict,
    blank_strings,
    check_fields,
    go_files,
    go_src,
    load_json,
    quality_get,
    rel_to,
    warn_example,
)

NAME = "impl"
REL = ".harness/deliverables/artifacts/impl.json"
TOOLCHAIN = ("build", "vet", "lint")
TODO = re.compile(r"\b(TODO|FIXME)\b(?!\([\w.\-]+\):)")
SPACE_INDENT = re.compile(r"^( {2,})\S")


def run(ctx, findings):
    root = Path(ctx["root"])
    data = load_json(root, REL, NAME, findings, "IMP001")
    if isinstance(data, dict):
        warn_example(data, REL, NAME, findings, ctx["strict"])
        check_fields(data, ("build", "vet", "lint", "changed_packages"), NAME, REL, findings, "IMP001")
        for key in TOOLCHAIN:
            if key in data and data.get(key) != "pass":
                add(findings, "ERROR", NAME, REL, 1, "IMP001", f"{key} = {data.get(key)!r}，必须为 'pass'")
    scan_sources(root, as_dict(ctx.get("quality")), findings)


def scan_sources(root, quality, findings):
    src = go_src(root, quality)
    max_lines = quality_get(quality, "max_file_lines", 400)
    for path in go_files(src):
        rel = rel_to(root, path)
        raw = path.read_bytes()
        if b"\r\n" in raw:
            add(findings, "ERROR", NAME, rel, 1, "IMP002", "文件含 CRLF 行尾（gofmt 只认 LF）")
        lines = raw.decode("utf-8", errors="replace").splitlines()
        in_raw = False
        for idx, line in enumerate(lines, 1):
            if line != line.rstrip():
                add(findings, "ERROR", NAME, rel, idx, "IMP002", "行尾有多余空白")
            if not in_raw and SPACE_INDENT.match(line):
                add(findings, "ERROR", NAME, rel, idx, "IMP002", "用空格缩进（Go 用 tab）")
            # 只抹字面量、保留注释：TODO 本来就常写在注释里，但 "TODO 这种写法" 只是文案。
            if TODO.search(blank_strings(line)):
                add(findings, "WARN", NAME, rel, idx, "IMP004", "TODO/FIXME 必须带负责人，形如 TODO(name): 原因")
            if line.count("`") % 2 == 1:
                in_raw = not in_raw
        if len(lines) > max_lines:
            add(findings, "WARN", NAME, rel, 1, "IMP003", f"文件 {len(lines)} 行，超过 {max_lines}：按职责拆分")
        check_import_groups(rel, lines, findings)


def check_import_groups(rel, lines, findings):
    """CodeReviewComments: Imports —— 标准库单独一组放最前，组间空一行。

    goimports 会替你排，但它没被跑过的时候总得有人看出来。判据只用路径形状：
    首段带点（example.com / github.com）就是第三方，不带点就是标准库。
    """
    seen_third_party = False
    for start, paths in _import_groups(lines):
        stdlib = [p for p in paths if _is_stdlib(p)]
        third = [p for p in paths if not _is_stdlib(p)]
        if stdlib and third:
            add(
                findings,
                "ERROR",
                NAME,
                rel,
                start,
                "IMP005",
                "import 组里混了标准库与第三方：标准库单独放第一组，组间空一行",
            )
            seen_third_party = True
            continue
        if stdlib and seen_third_party:
            add(findings, "ERROR", NAME, rel, start, "IMP005", "标准库出现在第三方之后：标准库必须是最前面的一组")
        if third:
            seen_third_party = True


def _import_groups(lines):
    """import (...) 里按空行切组，返回 [(首行行号, [导入路径])]。"""
    groups = []
    in_block = False
    current = None
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if not in_block:
            if line.startswith("import ("):
                in_block = True
            continue
        if line.startswith(")"):
            if current:
                groups.append((current[0], current[1]))
            in_block = False
            current = None
            continue
        if not line:
            if current:
                groups.append((current[0], current[1]))
                current = None
            continue
        path = _import_path(line)
        if path is None:
            continue
        if current is None:
            current = (idx, [])
        current[1].append(path)
    return groups


def _import_path(line):
    if line.startswith("//"):
        return None
    quoted = re.findall(r'"([^"]+)"', line)
    return quoted[0] if quoted else None


def _is_stdlib(path):
    return "." not in path.split("/")[0]
