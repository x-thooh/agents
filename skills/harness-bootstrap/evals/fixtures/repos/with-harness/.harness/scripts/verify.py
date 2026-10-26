#!/usr/bin/env python3
"""最小 verify：两个 scope。folders 断言 docs 目录带日期前缀（当前 DELETE_ME_文档 违规，基线内老账）。"""
import re, sys, pathlib
ERRORS = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
for d in sorted(p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
    if d.startswith("docs"):
        if not re.match(r"\d{4}", d):
            ERRORS.append(("folders", d, "目录未带日期前缀: #"))
for f, p, m in ERRORS:
    print(f"ERROR {f} {p} {m}")
sys.exit(1 if ERRORS else 0)
