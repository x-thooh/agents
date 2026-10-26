#!/usr/bin/env bash
# goland-bookmarks.sh —— 读取 GoLand / JetBrains IDE 的书签（Bookmarks）
#
# 数据来源（JetBrains 2026.x）：
#   <IDE 配置目录>/workspace/<hash>.xml → <component name="BookmarksManager">
# 项目 → workspace 文件的对应关系来自 idea.log 的
#   "Project store initialized with paths: [... $PRODUCT_WORKSPACE_FILE$, value=<xml>]"
# 说明见同级 SKILL.md。
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "goland-bookmarks: 需要 python3（未找到）" >&2
  exit 2
fi

exec python3 - "$@" <<'PYCODE'
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

HOME = os.path.expanduser("~")
LOG_LINE_RE = re.compile(r"Project store initialized with paths: \[(.*)\]\s*$")
CFG_DIR_RE = re.compile(r"\$PROJECT_CONFIG_DIR\$,\s*value=([^)]*)\)")
WS_FILE_RE = re.compile(r"\$PRODUCT_WORKSPACE_FILE\$,\s*value=([^)]*)\)")
PROJECT_DIR_PREFIX = "file://$PROJECT_DIR$/"
PROJECT_DIR_ROOT = "file://$PROJECT_DIR$"

EXIT_OK, EXIT_USAGE, EXIT_MISSING, EXIT_EMPTY = 0, 2, 3, 4


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- IDE 目录

def ide_config_dirs():
    """按新旧排序返回 JetBrains IDE 配置目录（含 workspace/ 或 options/）。"""
    roots = [
        os.path.join(HOME, "Library", "Application Support", "JetBrains"),  # macOS
        os.path.join(HOME, ".config", "JetBrains"),                         # Linux
    ]
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root), reverse=True):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            if os.path.isdir(os.path.join(d, "workspace")) or os.path.isdir(os.path.join(d, "options")):
                found.append(d)
    return found


def resolve_ide(spec, verbose):
    dirs = ide_config_dirs()
    if not spec:
        if not dirs:
            eprint("goland-bookmarks: 找不到 JetBrains 配置目录" + ("（~/Library/Application Support/JetBrains）" if sys.platform == "darwin" else "（~/.config/JetBrains）"))
        return dirs
    cand = os.path.expanduser(spec)
    if os.path.isdir(cand):
        return [os.path.realpath(cand)]
    for root in (os.path.join(HOME, "Library", "Application Support", "JetBrains"),
                 os.path.join(HOME, ".config", "JetBrains")):
        d = os.path.join(root, spec)
        if os.path.isdir(d):
            return [d]
    for d in dirs:
        if os.path.basename(d).lower() == spec.lower():
            return [d]
    eprint(f"goland-bookmarks: 未找到 IDE 配置目录 '{spec}'；候选：" + (", ".join(os.path.basename(d) for d in dirs) or "无"))
    return []


# ---------------------------------------------------- 项目 → workspace 文件

def idea_log_candidates(ide):
    product = os.path.basename(ide)
    return [
        os.path.join(HOME, "Library", "Logs", "JetBrains", product, "idea.log"),  # macOS
        os.path.join(HOME, ".cache", "JetBrains", product, "log", "idea.log"),     # Linux
        os.path.join(ide, "log", "idea.log"),
    ]


def read_tail(path, size=4 * 1024 * 1024):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - size))
        return f.read().decode("utf-8", "replace")


def resolve_from_log(ide, project, verbose):
    """用 idea.log 里 ComponentStore 的路径映射精确匹配项目。"""
    target = os.path.realpath(os.path.join(project, ".idea"))
    for log in idea_log_candidates(ide):
        if not os.path.isfile(log):
            continue
        hit = None
        for line in read_tail(log).splitlines():
            m = LOG_LINE_RE.search(line)
            if not m:
                continue
            inner = m.group(1)
            cfg, ws = CFG_DIR_RE.search(inner), WS_FILE_RE.search(inner)
            if cfg and ws and os.path.realpath(cfg.group(1)) == target:
                hit = ws.group(1)
        if hit:
            if os.path.isfile(hit):
                if verbose:
                    eprint(f"  log: {log} -> {hit}")
                return hit
            if verbose:
                eprint(f"  log 命中但文件不存在: {hit}")
    return None


def resolve_by_heuristic(ide, project, verbose):
    """日志不可用时的回退：按“书签文件真实存在于该项目”打分。"""
    best, best_score = None, 0
    for f in sorted(glob.glob(os.path.join(ide, "workspace", "*.xml"))):
        marks = load_bookmarks(f, project)
        if not marks:
            continue
        score = sum(1 for m in marks if m["absPath"] and not m["external"] and os.path.exists(m["absPath"]))
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                if project in fh.read():
                    score += 1000
        except OSError:
            pass
        if verbose:
            eprint(f"  candidate {f}: score={score}")
        if score > best_score:
            best, best_score = f, score
    return best


def resolve_workspace(ide_dirs, project, verbose):
    for ide in ide_dirs:
        ws = resolve_from_log(ide, project, verbose)
        if ws:
            return ws, "idea.log"
    for ide in ide_dirs:
        ws = resolve_by_heuristic(ide, project, verbose)
        if ws:
            return ws, "heuristic"
    return None, None


# ------------------------------------------------------------------ 解析 XML

def opt_value(node, name, default=""):
    for o in node.findall("option"):
        if o.get("name") == name:
            return o.get("value") or ""
    return default


def url_to_path(url, project):
    """返回 (absPath, external?)。"""
    if not url:
        return None, False
    if url.startswith(PROJECT_DIR_PREFIX):
        return os.path.join(project, url[len(PROJECT_DIR_PREFIX):]), False
    if url == PROJECT_DIR_ROOT:
        return project, False
    if url.startswith("file://"):
        return url[len("file://"):], False
    return url, True


def collect_bookmark(node, group, project):
    attrs = {e.get("key"): (e.get("value") or "") for e in node.iter("entry")}
    opts = {o.get("name"): (o.get("value") or "") for o in node.findall("option")}
    abs_path, external = url_to_path(attrs.get("url", ""), project)
    rel = os.path.relpath(abs_path, project) if abs_path and not external and abs_path.startswith(project + os.sep) else abs_path
    line = attrs.get("line", "")
    return {
        "group": group,
        "path": rel,
        "absPath": abs_path,
        "external": external,
        "line": int(line) if line.isdigit() else None,
        "column": int(attrs["column"]) if attrs.get("column", "").isdigit() else None,
        "description": opts.get("description", ""),
        "mnemonic": opts.get("mnemonic", ""),
        "lineText": attrs.get("lineText", ""),
        "provider": (opts.get("provider", "").split(".")[-1] or ""),
    }


def walk_group(node, prefix, project, out):
    name = opt_value(node, "name") or "default"
    gname = f"{prefix}/{name}" if prefix else name
    for b in node.findall("option[@name='bookmarks']/BookmarkState"):
        out.append(collect_bookmark(b, gname, project))
    for sub in node.findall("option[@name='groups']/GroupState"):
        walk_group(sub, gname, project, out)


def load_bookmarks(ws_path, project):
    """返回书签列表；文件里没有 BookmarksManager 组件时返回 None（IDE 尚未落盘）。"""
    try:
        root = ET.parse(ws_path).getroot()
    except (OSError, ET.ParseError):
        return None
    comps = [c for c in root.iter("component") if c.get("name") == "BookmarksManager"]
    if not comps:
        return None
    out = []
    for c in comps:
        for g in c.findall("option[@name='groups']/GroupState"):
            walk_group(g, "", project, out)
    return out


# --------------------------------------------------------------------- 输出

def fmt_location(m):
    if m["external"]:
        return m["path"] or "<no-url>"
    p = m["path"]
    if m["line"] is not None:
        p += f":{m['line']}"
        if m["column"] is not None:
            p += f":{m['column']}"
    return p


def note_of(m, width=70):
    note = m["description"] or (m["lineText"].strip() if m["lineText"] else "")
    if m["mnemonic"]:
        note = f"[{m['mnemonic']}] {note}".strip()
    return note if len(note) <= width else note[: width - 1] + "…"


def status_of(m):
    if m["external"] or not m["absPath"]:
        return "EXTERNAL"
    if not os.path.exists(m["absPath"]):
        return "MISSING"
    if m["line"] is not None:
        try:
            with open(m["absPath"], encoding="utf-8", errors="replace") as fh:
                total = sum(1 for _ in fh)
        except OSError:
            return "UNREADABLE"
        if m["line"] > total:
            return f"BEYOND-EOF({total})"
    return ""


def print_table(marks, project, ws, source, args):
    eprint(f"project:   {project}")
    eprint(f"workspace: {ws}  (匹配方式: {source})")
    group_note = f"，已过滤 group={args.group}" if args.group else ""
    eprint(f"bookmarks: {len(marks)}{group_note}\n")

    rows = []
    for i, m in enumerate(marks, 1):
        st = status_of(m) if args.check else ""
        note = note_of(m)
        if st:
            note = f"{note}  «{st}»".strip()
        rows.append((str(i), fmt_location(m), note))
    w0 = max([len("#")] + [len(r[0]) for r in rows])
    w1 = max([len("location")] + [len(r[1]) for r in rows])
    print(f"{'#':>{w0}}  {'location':<{w1}}  note")
    print(f"{'-' * w0}  {'-' * w1}  {'-' * 4}")
    for a, b, c in rows:
        print(f"{a:>{w0}}  {b:<{w1}}  {c}".rstrip())

    if args.context:
        for m in marks:
            if m["external"] or not m["absPath"] or not os.path.exists(m["absPath"]) or m["line"] is None:
                continue
            print(f"\n--- {fmt_location(m)}")
            try:
                with open(m["absPath"], encoding="utf-8", errors="replace") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                continue
            lo = max(1, m["line"] - args.context)
            hi = min(len(lines), m["line"] + args.context)
            for n in range(lo, hi + 1):
                mark = ">" if n == m["line"] else " "
                print(f"{mark} {n:>5} | {lines[n - 1]}")


def print_plain(marks):
    for m in marks:
        print(fmt_location(m))


def print_json(marks, project, ws, source):
    payload = {
        "project": project,
        "workspaceFile": ws,
        "resolvedBy": source,
        "bookmarks": [
            {k: m[k] for k in ("group", "path", "absPath", "external", "line", "column",
                               "description", "mnemonic", "lineText", "provider")}
            for m in marks
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------- 主流程

def main(argv):
    p = argparse.ArgumentParser(
        prog="goland-bookmarks.sh",
        description="列出 GoLand / JetBrains IDE 书签（Bookmarks）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  goland-bookmarks.sh                       # 当前项目全部书签
  goland-bookmarks.sh -f plain              # path:line，可直接管道
  goland-bookmarks.sh -c 3 -g marketing     # 带 3 行上下文，只看某个组
  goland-bookmarks.sh --check               # 校验书签指向的文件/行是否还有效
  goland-bookmarks.sh --flush               # 先让 IDE 落盘再读（macOS）
""",
    )
    p.add_argument("-p", "--project", help="项目根目录（默认：git 顶层目录，其次当前目录）")
    p.add_argument("--ide", help="IDE 配置目录名（如 GoLand2026.2）或绝对路径（默认：自动取最新）")
    p.add_argument("--workspace-file", help="直接指定 workspace XML，跳过解析")
    p.add_argument("-g", "--group", help="只输出该书签组")
    p.add_argument("-f", "--format", default="table", choices=["table", "plain", "json"], help="输出格式（默认 table）")
    p.add_argument("-c", "--context", type=int, default=0, metavar="N", help="每条书签附 N 行源码上下文（table 格式）")
    p.add_argument("--check", action="store_true", help="校验文件存在与行号，有失效项时退出码 3")
    p.add_argument("--flush", action="store_true", help="macOS：切换窗口焦点以触发 IDE 落盘后读取")
    p.add_argument("--strict", action="store_true", help="未找到书签时退出码 4")
    p.add_argument("-v", "--verbose", action="store_true", help="打印解析证据到 stderr")
    args = p.parse_args(argv)

    if args.context and args.format != "table":
        p.error("--context 只能与 --format table 一起使用")
    if args.check and args.format == "plain":
        p.error("--check 只能与 --format table/json 一起使用")

    project = args.project
    if not project:
        try:
            project = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                              stderr=subprocess.DEVNULL).decode().strip()
        except (OSError, subprocess.CalledProcessError):
            project = os.getcwd()
    project = os.path.realpath(os.path.expanduser(project))
    if not os.path.isdir(project):
        eprint(f"goland-bookmarks: 项目目录不存在: {project}")
        return EXIT_USAGE

    if args.flush:
        if sys.platform != "darwin":
            eprint("goland-bookmarks: --flush 仅支持 macOS，已忽略")
        else:
            try:
                subprocess.run(["osascript", "-e", 'tell application "Finder" to activate'],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                eprint("goland-bookmarks: 已切走焦点以触发 IDE 落盘")
                import time
                time.sleep(1.5)
            except OSError:
                eprint("goland-bookmarks: osascript 不可用，--flush 已忽略")

    if args.workspace_file:
        ws = os.path.realpath(os.path.expanduser(args.workspace_file))
        source = "--workspace-file"
        if not os.path.isfile(ws):
            eprint(f"goland-bookmarks: workspace 文件不存在: {ws}")
            return EXIT_USAGE
    else:
        ide_dirs = resolve_ide(args.ide, args.verbose)
        if not ide_dirs:
            return EXIT_EMPTY
        ws, source = resolve_workspace(ide_dirs, project, args.verbose)
        if not ws:
            eprint("goland-bookmarks: 未能在任何 IDE workspace 文件里匹配到本项目")
            eprint(f"  项目: {project}")
            eprint("  可尝试: goland-bookmarks.sh --ide <目录名> 或 --workspace-file <xml>")
            return EXIT_EMPTY

    marks = load_bookmarks(ws, project)
    if marks is None:
        eprint(f"goland-bookmarks: {ws} 里没有 BookmarksManager 组件")
        eprint("  原因通常是 IDE 尚未落盘（JetBrains 2026.x 在工作区失焦/退出时才写）。")
        eprint("  处理：切一次窗口焦点，或加 --flush 后重试。")
        return EXIT_EMPTY

    if args.group:
        marks = [m for m in marks if m["group"] == args.group]
    if not marks:
        eprint(f"project:   {project}")
        eprint(f"workspace: {ws}  (匹配方式: {source})")
        eprint(f"goland-bookmarks: 没有匹配的书签（group={args.group or '*'}）")
        return EXIT_EMPTY if args.strict else EXIT_OK

    if args.format == "json":
        print_json(marks, project, ws, source)
    elif args.format == "plain":
        print_plain(marks)
    else:
        print_table(marks, project, ws, source, args)

    if args.check:
        statuses = [(m, status_of(m)) for m in marks]
        external = [(m, st) for m, st in statuses if st == "EXTERNAL"]
        broken = [(m, st) for m, st in statuses if st and st != "EXTERNAL"]
        sys.stdout.flush()
        if external:
            eprint(f"外部书签（非项目文件，跳过校验）: {len(external)} 条")
        if broken:
            eprint(f"失效书签: {len(broken)} 条")
            for m, st in broken:
                eprint(f"  {fmt_location(m)}  «{st}»")
            return EXIT_MISSING
        eprint("校验通过：全部书签指向的文件与行号有效")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PYCODE
