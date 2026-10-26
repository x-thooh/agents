#!/usr/bin/env python3
"""Delivery harness verify dispatcher.

Each scope lives in scripts/scopes/<name>.py. This file only:
  * loads quality.json once;
  * runs the registered scopes;
  * applies --fix fixes declared by scopes (FIXERS), then re-runs;
  * sorts and prints findings;
  * owns the exit-code contract (0 = no ERROR, 1 = ERROR, 2 = usage / 前置条件不满足).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from scopes import (  # noqa: E402
    coherence,
    conf,
    design,
    dev,
    gates,
    integration,
    requirements,
    review,
    selftest,
    submission,
    baseline,
)
from scopes.common import git_clean, load_json  # noqa: E402

SCOPES = (
    gates,
    conf,
    requirements,
    design,
    dev,
    integration,
    selftest,
    review,
    coherence,
    submission,
    baseline,
)


def collect(root, selected, strict):
    """跑一遍全部 scope。--fix 前后各调一次，结论只认后一次。"""
    findings = []
    quality = load_json(root, ".harness/config.json", "config", findings, "CFG001")
    ctx = {
        "root": str(root),
        "strict": strict,
        "quality": quality if isinstance(quality, dict) else {},
    }
    for mod in selected:
        mod.run(ctx, findings)
    return findings


def fixers_of(selected):
    """收集 scope 模块导出的 FIXERS = {code: (fn(root) -> 说明, 会被重写的路径)}。

    路径不是装饰：前置条件要按它排除——派生文件的本地改动不算「你的工作」。
    """
    table = {}
    for mod in selected:
        table.update(getattr(mod, "FIXERS", None) or {})
    return table


def apply_fixes(root, findings, fixers):
    """每个可修 code 只修一次（同一 code 可能命中多条）。返回 [(code, 说明)]。"""
    done = []
    seen = set()
    for finding in findings:
        entry = fixers.get(finding.code)
        if entry is None or finding.code in seen:
            continue
        seen.add(finding.code)
        fix, _target = entry
        done.append((finding.code, fix(root)))
    return done


def main(argv=None):
    parser = argparse.ArgumentParser(description="交付流程门禁校验")
    parser.add_argument("--root", default=str(HERE.parents[1]), help="仓库根目录")
    parser.add_argument("--scope", default=None, help="只跑一个 scope")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="示例数据（example: true）按 ERROR 处理")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="自动修派生数据（仅 FIXERS 声明的 code），修完重跑；要求 git 工作区干净",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "AGENTS.md").is_file():
        print(f"verify: {root}/AGENTS.md 不存在", file=sys.stderr)
        return 2

    selected = SCOPES
    if args.scope:
        selected = tuple(mod for mod in SCOPES if args.scope == mod.NAME)
        if not selected:
            names = ", ".join(mod.NAME for mod in SCOPES)
            print(f"verify: 未知 scope {args.scope!r}；可选: {names}", file=sys.stderr)
            return 2

    fixers = fixers_of(selected)
    if args.fix:
        reason = git_clean(root, [target for _fix, target in fixers.values()])
        if reason:
            print(f"verify --fix: {reason}", file=sys.stderr)
            return 2

    findings = collect(root, selected, args.strict)

    fixed = []
    if args.fix:
        fixed = apply_fixes(root, findings, fixers)
        if fixed:
            # 修完必须重跑：不能拿修前的结论凑数，也不能假设一定修好了
            findings = collect(root, selected, args.strict)

    findings.sort(
        key=lambda f: (f.severity != "ERROR", f.scope, f.path, f.line, f.code)
    )
    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "findings": [f.as_dict() for f in findings],
                    "summary": {
                        "errors": len(errors),
                        "warns": len(warns),
                        "scopes": [mod.NAME for mod in selected],
                        "strict": args.strict,
                        "fixable": sorted(fixers),
                        "fixed": [{"code": c, "note": n} for c, n in fixed],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for code, note in fixed:
            print(f"FIXED {code:<8} {note}")
        for f in findings:
            print(f"{f.severity:<5} {f.scope:<12} {f.path}:{f.line}  {f.code:<8} {f.message}")
        if args.fix:
            manual = sorted({f.code for f in findings if f.code not in fixers})
            if manual:
                print(
                    f"--fix 只修派生数据（{', '.join(sorted(fixers))}）；"
                    f"其余 {len(manual)} 类需人判，未自动修：{', '.join(manual)}"
                )
        mode = "strict" if args.strict else "normal"
        print(
            f"{len(errors)} ERROR, {len(warns)} WARN  "
            f"(scopes: {', '.join(mod.NAME for mod in selected)}; mode: {mode}"
            + ("; fix" if args.fix else "")
            + ")  人判项见 AGENTS.md「人判项（无断言）」"
        )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
