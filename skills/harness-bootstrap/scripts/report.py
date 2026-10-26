"""report：findings 的排序、两种输出格式、退出码。

`audit.py` 只该做调度：读入 → 跑注册表里的 scope → 把结果交给这里。
它一度 152 行，其中近一半在拼两条输出格式——那是表现层，不是编排。

拆分判据沿用本仓库的规矩：**拆分前后 `--json` 输出字节等同**，不是「看起来更整齐」。
表现层搬走时最容易顺手改格式，所以它单独一个文件、拼字符串只此一处。
"""
import json
import os

ERROR = "ERROR"
WARN = "WARN"


def order(findings):
    """ERROR 在前，然后按 scope / 行 / code。输出顺序是契约的一部分（测试逐字比对）。"""
    findings.sort(key=lambda f: (f.severity != ERROR, f.scope, f.line, f.code))
    return findings


def counts(findings):
    return (sum(1 for f in findings if f.severity == ERROR),
            sum(1 for f in findings if f.severity == WARN))


def emit(*, as_json, skill_dir, skill_md, findings, scope_names, na, links_checked):
    """打印结果并返回退出码：0 = 通过（可含 WARN），1 = 有 ERROR。"""
    order(findings)
    errors, warns = counts(findings)

    if as_json:
        print(json.dumps({
            "skill_dir": skill_dir,
            "findings": [f.as_dict() for f in findings],
            "summary": {"errors": errors, "warns": warns,
                        "scopes": list(scope_names),
                        "not_applicable": na,
                        "links_checked": bool(links_checked)},
        }, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    rel = os.path.relpath(skill_md, skill_dir)
    for f in findings:
        loc = f"{f.path or rel}:{f.line}" if f.line else (f.path or rel)
        print(f"{f.severity:<5} {f.scope:<11} {loc}  {f.code:<7} {f.message}")
    print(f"{errors} ERROR, {warns} WARN  "
          f"({'links 已检查' if links_checked else 'links 未检查'})  "
          + (f"scope 未适用: {','.join(na)}  " if na else "")
          + "语义一致性=人判，不在本脚本范围")
    return 1 if errors else 0
