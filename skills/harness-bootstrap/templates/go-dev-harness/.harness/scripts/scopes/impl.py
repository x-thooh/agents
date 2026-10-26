"""impl: 编码阶段证据（build/vet/lint）+ 源码卫生。"""
import re
from pathlib import Path

from .common import add, as_dict, check_fields, go_files, go_src, load_json, quality_get, rel_to, warn_example

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
                add(findings, "ERROR", NAME, REL, 1, "IMP001",
                    f"{key} = {data.get(key)!r}，必须为 'pass'")
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
            if TODO.search(line):
                add(findings, "WARN", NAME, rel, idx, "IMP004",
                    "TODO/FIXME 必须带负责人，形如 TODO(name): 原因")
            if line.count("`") % 2 == 1:
                in_raw = not in_raw
        if len(lines) > max_lines:
            add(findings, "WARN", NAME, rel, 1, "IMP003",
                f"文件 {len(lines)} 行，超过 {max_lines}：按职责拆分")
