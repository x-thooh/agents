"""layout: Go 模块形状与导出面（go.mod / cmd 薄 / 包边界 / 导出符号注释 / 接口大小）。"""
import re
from pathlib import Path

from .common import add, as_dict, go_files, go_package, go_src, quality_get, rel_to

NAME = "layout"

DOC_PATTERNS = (
    re.compile(r"^func \([^)]*\) ([A-Z]\w*)\("),
    re.compile(r"^func ([A-Z]\w*)\("),
    re.compile(r"^type ([A-Z]\w*)\b"),
)
IFACE = re.compile(r"^type ([A-Z]\w*) interface \{$")
GO_DIRECTIVE = re.compile(r"^go\s+(\d+)\.(\d+)")


def run(ctx, findings):
    root = Path(ctx["root"])
    quality = as_dict(ctx.get("quality"))
    src = go_src(root, quality)
    rel_src = rel_to(root, src)

    gomod = src / "go.mod"
    if not gomod.is_file():
        add(findings, "ERROR", NAME, f"{rel_src}/go.mod", 1, "LAY001",
            f"模块根 {rel_src!r} 下没有 go.mod；把 quality.json 的 go_src 指到真实模块根")
        return
    check_gomod(gomod, rel_src, quality, findings)
    check_cmd(root, src, rel_src, quality, findings)
    check_docs_and_interfaces(root, src, quality, findings)


def check_gomod(gomod, rel_src, quality, findings):
    rel = f"{rel_src}/go.mod"
    content = gomod.read_text(encoding="utf-8").splitlines()
    module = ""
    go_directive = None
    for line in content:
        stripped = line.strip()
        if stripped.startswith("module "):
            module = stripped[len("module "):].strip()
        elif stripped.startswith("go "):
            go_directive = stripped
        elif stripped.startswith("replace ") and ("=> ./" in stripped or "=> ../" in stripped):
            add(findings, "ERROR", NAME, rel, 1, "LAY003",
                f"replace 指向本地路径：{stripped}（提交前必须去掉）")
    if not module:
        add(findings, "ERROR", NAME, rel, 1, "LAY001", "go.mod 缺 module 声明")
    if go_directive is None:
        add(findings, "ERROR", NAME, rel, 1, "LAY002", "go.mod 缺 go 指令")
        return
    match = GO_DIRECTIVE.match(go_directive)
    if not match:
        add(findings, "ERROR", NAME, rel, 1, "LAY002", f"go 指令格式不对：{go_directive!r}")
        return
    minimum = quality_get(quality, "go_version_min", "1.21")
    want = GO_DIRECTIVE.match(f"go {minimum}")
    if want is None:
        add(findings, "ERROR", NAME, rel, 1, "LAY002",
            f"quality.json 的 go_version_min 不是 X.Y：{minimum!r}")
        return
    if (int(match.group(1)), int(match.group(2))) < (int(want.group(1)), int(want.group(2))):
        add(findings, "ERROR", NAME, rel, 1, "LAY002",
            f"go 版本 {match.group(1)}.{match.group(2)} 低于要求 {minimum}")


def check_cmd(root, src, rel_src, quality, findings):
    cmd = src / "cmd"
    max_lines = quality_get(quality, "main_max_lines", 80)
    if not cmd.is_dir():
        add(findings, "ERROR", NAME, f"{rel_src}/cmd", 1, "LAY004",
            "缺 cmd/<服务名>/main.go（入口必须可执行且可测）")
        return
    services = sorted(p for p in cmd.iterdir() if p.is_dir())
    if not services:
        add(findings, "ERROR", NAME, f"{rel_src}/cmd", 1, "LAY004", "cmd/ 下没有服务目录")
    for service in services:
        main = service / "main.go"
        rel = rel_to(root, main)
        if not main.is_file():
            add(findings, "ERROR", NAME, f"{rel_to(root, service)}/main.go", 1, "LAY004",
                "缺 main.go")
            continue
        lines = main.read_text(encoding="utf-8").splitlines()
        if len(lines) > max_lines:
            add(findings, "ERROR", NAME, rel, 1, "LAY004",
                f"main.go 有 {len(lines)} 行，超过 {max_lines}：装配逻辑应下沉到 internal/")
    for path in sorted(cmd.rglob("*.go")):
        pkg = go_package(path)
        if pkg != "main":
            add(findings, "ERROR", NAME, rel_to(root, path), 1, "LAY005",
                f"cmd/ 下的文件必须是 package main，实际 {pkg!r}：业务代码放 internal/")


def check_docs_and_interfaces(root, src, quality, findings):
    max_methods = quality_get(quality, "max_interface_methods", 5)
    for path in go_files(src, include_tests=False):
        rel = rel_to(root, path)
        lines = path.read_text(encoding="utf-8").splitlines()
        head = "\n".join(lines[:5])
        if "Code generated" in head:
            continue
        for idx, raw in enumerate(lines):
            code = raw.strip()
            name = _exported_name(code)
            if name and not _documented(lines, idx, name):
                add(findings, "ERROR", NAME, rel, idx + 1, "LAY006",
                    f"导出符号 {name} 缺 doc 注释（形如 // {name} ...）")
        for idx, raw in enumerate(lines):
            match = IFACE.match(raw.strip())
            if not match:
                continue
            count = _method_count(lines, idx)
            if count > max_methods:
                add(findings, "WARN", NAME, rel, idx + 1, "LAY007",
                    f"接口 {match.group(1)} 有 {count} 个方法，超过 {max_methods}：按调用方需要拆小")


def _exported_name(code):
    for pattern in DOC_PATTERNS:
        match = pattern.match(code)
        if match:
            return match.group(1)
    return None


def _documented(lines, idx, name):
    end = idx - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    if end < 0 or not lines[end].strip().startswith("//"):
        return False
    start = end
    while start - 1 >= 0 and lines[start - 1].strip().startswith("//"):
        start -= 1
    return re.match(rf"^//\s+{re.escape(name)}\b", lines[start].strip()) is not None


def _method_count(lines, idx):
    count = 0
    depth = 1
    cursor = idx + 1
    while cursor < len(lines) and depth > 0:
        code = lines[cursor].strip()
        if code.startswith("}"):
            break
        if code and not code.startswith("//") and "(" in code:
            count += 1
        cursor += 1
    return count
