#!/usr/bin/env python3
"""harness-bootstrap 自身门禁：只审 --skill-dir 指定的这一个 skill。
边界（不要越界）：只审一个 skill 目录（默认 = 本脚本所在 skill），不扫描其他 skill；
  * 读取面 = 本 skill 目录：SKILL.md 全文；references/*.md（链接/锚点、§X.Y 引用、
    行数额度、交付物点名）；scripts/、tests/、templates/ 的机械检查；只做机械检查，不判语义；
  * 只读，不写文件；不依赖 git；同输入同输出（可重复执行）；不审目标仓库的 harness——
    那是目标仓库自己的 verify.py 的事。

本文件只做调度：读入 → 跑注册表里的 scope → 把结果交给 `report.py`。scope 实现在
`scripts/scopes/<name>.py`，输出与退出码在 `scripts/report.py`（§六 verify 脚本规范：
单文件长到一次只能改一处、改不动时，就该拆了）。拆分判据：拆分前后输出字节等同。

语义一致性机器判不了——那是人判项，由 SKILL.md 的「判据类型」列标注，本脚本不冒充。
用法: python3 scripts/audit.py [--skill-dir DIR] [--only a,b] [--check-links] [--json]

退出码: 0 = 通过（可含 WARN）；1 = 有 ERROR；2 = 用法/环境错误
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import report  # noqa: E402  （同目录，sys.path 已就位）
from cli import parse_link_status, select  # noqa: E402
from scopes import (  # noqa: E402  （必须先修好 sys.path 再导入）
    baseline,
    bash,
    budget,
    codeindex,
    deliverable,
    docclaim,
    docphantom,
    frontmatter,
    host,
    layout,
    layout_parity,
    ledger,
    links,
    loop,
    sections,
    struct,
    terms,
    tplpath,
    version,
    xref,
    xrefdoc,
)

# 注册表：顺序 = 跑的顺序（输出还会按 severity/scope/line/code 再排序）
SCOPES = (
    frontmatter,
    bash,
    baseline,
    host,
    layout,
    layout_parity,
    budget,
    sections,
    struct,
    codeindex,
    docclaim,
    docphantom,
    deliverable,
    ledger,
    terms,
    tplpath,
    version,
    xref,
    xrefdoc,
    links,
    loop,
)


def run_all(text, path, skill_dir, check_links, dispatch=None, link_status=None, scopes=None):
    findings = []
    ctx = {
        "text": text,
        "path": path,
        "skill_dir": skill_dir,
        "check_links": check_links,
        "dispatch": dispatch,
        "link_status": link_status or {},
    }
    for mod in scopes or SCOPES:
        mod.run(ctx, findings)
    return findings, ctx.get("not_applicable", [])


def main(argv=None):
    parser = argparse.ArgumentParser(description="审 harness-bootstrap 这一个 skill 的 SKILL.md（不碰其他 skill）")
    parser.add_argument("--skill-dir", default=None, help="skill 目录（默认 = 本脚本所在的 skill）")
    parser.add_argument("--check-links", action="store_true", help="真的请求外部链接（默认只报一条未检查 WARN）")
    parser.add_argument(
        "--link-status",
        action="append",
        default=[],
        metavar="URL=CODE",
        help="测试缝：把某个 URL 的状态码固定成 CODE（整数）或 ERR（不可达）。\n"
        "只为反向测试 LINK002/LINK003 存在——公网结果不能用来判门禁。",
    )
    parser.add_argument(
        "--only",
        default=None,
        metavar="SCOPE[,SCOPE]",
        help="只跑这些 scope（逗号分隔）；默认全跑。\n给别的 skill 复用时必须点名：有些 scope 判的是本仓库的约定",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--dispatch", default=None, help="调度器源码路径（默认 <skill-dir>/scripts/audit.py；只为反向测试存在）"
    )
    args = parser.parse_args(argv)

    try:
        link_status = parse_link_status(args.link_status)
        scopes = select({mod.NAME: mod for mod in SCOPES}, args.only)
    except ValueError as exc:
        parser.error(str(exc))  # 退出码 2，与「用法错误」一致，不带 traceback

    skill_dir = os.path.abspath(args.skill_dir or os.path.dirname(_HERE))
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

    findings, na = run_all(text, skill_md, skill_dir, args.check_links, args.dispatch, link_status, scopes)
    return report.emit(
        as_json=args.json,
        skill_dir=skill_dir,
        skill_md=skill_md,
        findings=findings,
        scope_names=[m.NAME for m in scopes],
        na=na,
        links_checked=args.check_links,
    )


if __name__ == "__main__":
    sys.exit(main())
