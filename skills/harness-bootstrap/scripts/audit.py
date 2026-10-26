#!/usr/bin/env python3
"""harness-bootstrap 自身门禁：只审 --skill-dir 指定的这一个 skill。

边界（不要越界）：
  * 只审一个 skill 目录（默认 = 本脚本所在 skill），不扫描 ~/.pi/agent/skills 下其他 skill；
  * 读取面 = SKILL.md 全文 + skill 根目录与 references/ 的条目名（struct）+ references/*.md
    里的 §X.Y 引用（仅存在性，xrefdoc）——不对 references 做全文审查，也不改写它们；
  * 只读，不写文件；不依赖 git；同输入同输出（可重复执行）；
  * 不审目标仓库的 harness —— 那是目标仓库自己的 verify.py 的事。

本文件只做调度：每个 scope 一个文件，实现在 scripts/scopes/<name>.py
（§六 verify 脚本规范：单文件长到一次只能改一处、改不动时，就该拆了）。

语义一致性（如「阶段 0–2 没有 verify」）机器判不了 —— 那是人判项，
由 SKILL.md §十 的「判据类型」列标注，本脚本不冒充。

用法:
  python3 scripts/audit.py [--skill-dir DIR] [--check-links] [--json]

退出码: 0 = 通过（可含 WARN）；1 = 有 ERROR；2 = 用法/环境错误
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from scopes import (  # noqa: E402  （必须先修好 sys.path 再导入）
    baseline,
    bash,
    budget,
    codeindex,
    docclaim,
    frontmatter,
    host,
    layout,
    layout_parity,
    ledger,
    links,
    sections,
    struct,
    terms,
    version,
    xref,
    xrefdoc,
)

# 注册表：顺序 = 跑的顺序（输出还会按 severity/scope/line/code 再排序）
SCOPES = (frontmatter, bash, baseline, host, layout, layout_parity, budget, sections, struct,
          codeindex, docclaim, ledger, terms, version, xref, xrefdoc, links)


def run_all(text, path, skill_dir, check_links, dispatch=None, link_status=None):
    findings = []
    ctx = {"text": text, "path": path, "skill_dir": skill_dir,
           "check_links": check_links, "dispatch": dispatch,
           "link_status": link_status or {}}
    for mod in SCOPES:
        mod.run(ctx, findings)
    return findings, ctx.get("not_applicable", [])


def _parse_link_status(items):
    """`--link-status URL=CODE` → {URL: int|'ERR'}。

    在入口就把值验完：写错值时报用法错误（退出码 2），而不是让 links 拿到一个
    字符串去 int() 然后在某个 fixture 里 traceback。
    """
    out = {}
    for item in items:
        url, sep, value = item.rpartition("=")
        if not sep or not url:
            raise ValueError(f"--link-status 要写成 URL=CODE：{item!r}")
        if value == "ERR":
            out[url] = "ERR"
            continue
        try:
            out[url] = int(value)
        except ValueError:
            raise ValueError(
                f"--link-status 的 CODE 必须是整数或 ERR：{value!r}") from None
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="审 harness-bootstrap 这一个 skill 的 SKILL.md（不碰其他 skill）")
    parser.add_argument("--skill-dir", default=None,
                        help="skill 目录（默认 = 本脚本所在的 skill）")
    parser.add_argument("--check-links", action="store_true",
                        help="真的请求外部链接（默认只报一条未检查 WARN）")
    parser.add_argument("--link-status", action="append", default=[],
                        metavar="URL=CODE",
                        help="测试缝：把某个 URL 的状态码固定成 CODE（整数）或 ERR（不可达）。\n"
                             "只为反向测试 LINK002/LINK003 存在——公网结果不能用来判门禁。")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--dispatch", default=None,
                        help="调度器源码路径（默认 <skill-dir>/scripts/audit.py；只为反向测试存在）")
    args = parser.parse_args(argv)

    try:
        link_status = _parse_link_status(args.link_status)
    except ValueError as exc:
        parser.error(str(exc))  # 退出码 2，与「用法错误」一致，不带 traceback

    skill_dir = args.skill_dir or os.path.dirname(_HERE)
    skill_dir = os.path.abspath(skill_dir)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        print(f"audit: {skill_md} 不存在", file=sys.stderr)
        return 2

    try:
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"audit: 读不了 {skill_md}: {exc}", file=sys.stderr)
        return 2

    findings, na = run_all(text, skill_md, skill_dir, args.check_links, args.dispatch,
                           link_status)
    findings.sort(key=lambda f: (f.severity != "ERROR", f.scope, f.line, f.code))
    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]

    if args.json:
        print(json.dumps({
            "skill_dir": skill_dir,
            "findings": [f.as_dict() for f in findings],
            "summary": {"errors": len(errors), "warns": len(warns),
                        "scopes": [m.NAME for m in SCOPES],
                        "not_applicable": na,
                        "links_checked": bool(args.check_links)},
        }, ensure_ascii=False, indent=2))
    else:
        rel = os.path.relpath(skill_md, skill_dir)
        for f in findings:
            loc = f"{f.path or rel}:{f.line}" if f.line else (f.path or rel)
            print(f"{f.severity:<5} {f.scope:<11} {loc}  {f.code:<7} {f.message}")
        print(f"{len(errors)} ERROR, {len(warns)} WARN  "
              f"({'links 已检查' if args.check_links else 'links 未检查'})  "
              + (f"scope 未适用: {','.join(na)}  " if na else "")
              + "语义一致性=人判，不在本脚本范围")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
