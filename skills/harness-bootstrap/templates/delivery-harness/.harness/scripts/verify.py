#!/usr/bin/env python3
"""Delivery harness verify dispatcher.

Each scope lives in scripts/scopes/<name>.py. This file only:
  * loads quality.json once;
  * runs the registered scopes;
  * sorts and prints findings;
  * owns the exit-code contract (0 = no ERROR, 1 = ERROR, 2 = usage).
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
    design,
    dev,
    gates,
    integration,
    requirements,
    review,
    selftest,
    submission,
)
from scopes.common import load_json  # noqa: E402

SCOPES = (
    gates,
    requirements,
    design,
    dev,
    integration,
    selftest,
    review,
    coherence,
    submission,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="交付流程门禁校验")
    parser.add_argument("--root", default=str(HERE.parents[1]), help="仓库根目录")
    parser.add_argument("--scope", default=None, help="只跑一个 scope")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="示例数据（example: true）按 ERROR 处理")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "AGENTS.md").is_file():
        print(f"verify: {root}/AGENTS.md 不存在", file=sys.stderr)
        return 2

    selected = SCOPES
    if args.scope:
        selected = tuple(mod for mod in SCOPES if mod.NAME == args.scope)
        if not selected:
            names = ", ".join(mod.NAME for mod in SCOPES)
            print(f"verify: 未知 scope {args.scope!r}；可选: {names}", file=sys.stderr)
            return 2

    findings = []
    quality = load_json(
        root, ".harness/config.json", "config", findings, "CFG001"
    )
    ctx = {
        "root": str(root),
        "strict": args.strict,
        "quality": quality if isinstance(quality, dict) else {},
    }

    for mod in selected:
        mod.run(ctx, findings)

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
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for f in findings:
            print(f"{f.severity:<5} {f.scope:<12} {f.path}:{f.line}  {f.code:<8} {f.message}")
        mode = "strict" if args.strict else "normal"
        print(
            f"{len(errors)} ERROR, {len(warns)} WARN  "
            f"(scopes: {', '.join(mod.NAME for mod in selected)}; mode: {mode})  "
            "人判项见 AGENTS.md「人判项（无断言）」"
        )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
