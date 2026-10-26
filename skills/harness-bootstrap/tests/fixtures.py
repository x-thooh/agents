#!/usr/bin/env python3
"""把 tests/fixtures/ 的期望变成可执行的断言。

每个 fixture 一件缺陷，期望的 code 要**精确对上**——不是「有 ERROR 就算过」。
README 里那张手动命令表靠人记得跑；这张表把它变成 make check 的一部分。
不这么做的后果，SKILL.md §六 写过：scope 可能上线起就没执行过，跑一百次都「通过」。

正对照（ok-minimal）排第一：没有它，「全部符合期望」可能只是检查器根本没跑。

用法: python3 tests/fixtures.py
退出码: 0 = 全部符合期望；1 = 有偏差；2 = 环境错误
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SCOPES_DIR = ROOT / "scripts" / "scopes"

# 源码里出现的 code 字面量。前缀长度不固定：`FM001`/`LP001` 是两个字母，`XREFDOC001`
# 是七个。之前写成 `[A-Z]{3,}` 时，两个字母前缀的 12 个 code（FM001–009、LP001–003）
# 整块隐形，而反向测试抽的是 BASE002（三个字母）—— 抽到了，闸却是瞎的。
CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')


def declared_codes():
    """按 scope 模块分组返回 {模块名: {code}}。

    只算真正的 scope：有 `NAME` 常量且有 `run(` 函数的才算（`common.py` 是共用工具、
    `__init__.py` 是空包，它们本来就不报 code，不该被当成提取器失效）。
    抽到 0 个 code 的真 scope 要单独报——那不是「这个 scope 没有 code」，是提取器
    对它失效了（坑 #11 用在闸自己身上）。
    """
    out = {}
    for src in sorted(SCOPES_DIR.glob("*.py")):
        text = src.read_text(encoding="utf-8")
        if "\ndef run(" not in text or not re.search(r'^NAME\s*=', text, re.M):
            continue
        out[src.stem] = set(CODE_LITERAL.findall(text))
    return out


def uncovered_codes(covered):
    """返回「源码里会报、但这个 covered 集合没盖住」的 code。

    这个函数就是 §六「每个新 scope 必须做反向测试」从 scope 级提到 code 级的断言：
    scope 有一条 fixture 不代表它的每个 code 都活着——实测过 7 个 code 从来没被
    任何 case 触发过（其中 LINK002/XREFDOC001 还是 ERROR 级），而 make check 全绿。
    「声明即承诺」换个主语：写了这条 ERROR 分支，就得有样本证明它真会响。
    """
    all_codes = set()
    for codes in declared_codes().values():
        all_codes |= codes
    return sorted(all_codes - set(covered))

# (fixture, 期望的 code 集合, 额外命令行参数)
CASES = (
    # 正对照：0 条发现。它一红，下面所有「符合期望」都不作数。
    ("ok-minimal", set(), ()),
    # 每个 scope 至少一条
    ("bad-frontmatter", {"FM004"}, ()),
    ("bad-bash-block", {"BASH001"}, ()),
    ("bad-description", {"FM008"}, ()),
    ("bad-description-trigger", {"FM009"}, ()),
    ("bad-baseline-rule", {"BASE001"}, ()),
    ("bad-zero-baseline", {"BASE003"}, ()),
    ("bad-expiry-decor", {"BASE004"}, ()),
    ("bad-host-loading", {"HOST001"}, ()),
    ("bad-dual-ledger", {"DUAL001"}, ()),
    ("bad-scope-grading", {"SCOPE001"}, ()),
    ("bad-version-ungated", {"VER001"}, ()),
    ("bad-xref", {"XREF001"}, ()),
    ("bad-xref-table", {"XREF002"}, ()),
    ("bad-relative-link", {"LINK004"}, ()),
    ("bad-xref-ext", {"XREFDOC002"}, ()),
    # 标准目录形状（本轮新增）
    ("bad-struct-extra", {"STRUCT001"}, ()),
    ("bad-struct-singular", {"STRUCT001"}, ()),
    ("bad-struct-refs-content", {"STRUCT002"}, ()),
    # 单节 100 行上限：超了要拆，不是提限
    ("bad-section-long", {"SECT001"}, ()),
    # 参考材料单文件 100 行上限：同一条规则的另一半
    ("bad-reference-long", {"SECT002"}, ()),
    # 两档：撞 80 就 WARN（准备拆），超 100 才 ERROR（必须拆）。
    # 上面两条是 ERROR 档；这两条专验 80 那一档真会触发——把 WARN 分支删掉它们就红。
    ("bad-section-warn", {"SECT001"}, ()),
    ("bad-reference-warn", {"SECT002"}, ()),
    # 布局表 ↔ 模板对账：表说了模板没建，必须报 LP001（两套模板里故意只建一套的后半）
    ("bad-layout-parity", {"LP001"}, ()),
    # 覆盖闸自身的盲区：两字母前缀曾整块看不见，这 8 个是把洞堵上后的补齐。
    # FM001–FM007 与 LP002/LP003 此前从无样本；其中 LP002 藏在瞎区里，所以缺口一直看不见。
    ("bad-no-frontmatter", {"FM001"}, ()),
    ("bad-missing-name", {"FM002"}, ()),
    ("bad-name-shape", {"FM003"}, ()),
    ("bad-empty-description", {"FM005"}, ()),
    ("bad-long-description", {"FM006"}, ()),
    ("bad-extra-field", {"FM007"}, ()),
    ("bad-layout-extra", {"LP002"}, ()),
    ("bad-layout-no-table", {"LP003"}, ()),
    # 派生清单必须与源码逐字节一致；样本自带一份故意过时的 code-index.md
    ("bad-stale-code-index", {"CODEINDEX001"}, ()),
    # 体量预算两档：两档都得真会响，否则「准备拆」只是句好听话
    ("bad-budget-warn", {"BUDGET001"}, ()),
    ("bad-budget-error", {"BUDGET001"}, ()),
    # code 级反向测试：下列每一个都曾从无 fixture（scope 级有机一条，code 级漏网），
    # 其中 LINK002/XREFDOC001 是 ERROR 级——一个从不执行的 ERROR 比 WARN 更坏。
    # LINK002/LINK003 靠 --link-status 把「取状态码」固定住，不靠公网。
    ("bad-baseline-warn", {"BASE002"}, ()),
    ("bad-bash-syntax", {"BASH002"}, ()),
    ("bad-host-no-section", {"HOST002"}, ()),
    ("bad-link-unchecked", {"LINK001"}, ()),
    ("bad-link-dead", {"LINK002"},
     ("--check-links", "--link-status", "https://example.com/dead-404=404")),
    ("bad-link-unreachable", {"LINK003"},
     ("--check-links", "--link-status", "https://example.com/unreachable=ERR")),
    ("bad-xrefdoc-missing", {"XREFDOC001"}, ()),
    # 调度器体征：换一个「长成实现」的调度器去审合规样本
    ("ok-minimal", {"LAYOUT001"}, ("--dispatch", "tests/fixtures/bad-inline-scope/scripts/audit.py")),
)


def run_case(fixture, extra):
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "audit.py"),
        "--skill-dir",
        str(FIXTURES / fixture),
        "--json",
        *extra,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(f"audit 没输出 JSON（fixture={fixture}）：{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def check_coverage():
    """三道闸，顺序从弱到强：

    ① 提取器对本模块失效时单独报（抽到 0 个 code ≠ 这个 scope 没有 code）
    ② 每个 code 都得有 fixture（Q2）
    ③ 逐个 code 脉掉验一遍：拿掉某个 code 的 fixture，闸必须**恰好**报它自己。
       这正是 Q1 选的 (c)——一次只抽一个（BASE002，三字母）时，闸对 FM/LP
       瞎了也看不出来；逐个验才能把「闸自己有没有盲区」变成可执行的东西。
    """
    by_module = declared_codes()
    if not by_module:
        return ["没识别出任何 scope 模块（需同时有 `NAME` 常量与 `run(` 函数）——"
                "提取器无从谈起，不能当通过"]
    out = []
    empty = sorted(name for name, codes in by_module.items() if not codes)
    if empty:
        out.append("这些 scope 模块没抽出任何 code（提取器对它们失效，不是它们没有 code）："
                   + " ".join(empty))
    if empty:
        out.append("这些 scope 模块没抽出任何 code（提取器对它们失效，不是它们没有 code）："
                   + " ".join(empty))

    covered = set()
    for _fixture, expected, _extra in CASES:
        covered |= set(expected)
    missing = uncovered_codes(covered)
    if missing:
        out.append("以下 code 会报但没有任何 fixture 证明它会报：" + " ".join(missing))

    blind = []
    for code in sorted(covered):
        got = uncovered_codes(covered - {code})
        if got != [code]:
            blind.append(f"{code}（脉掉后报的是 {got or '无'}）")
    if blind:
        out.append("覆盖闸对下列 code 不敏感（脉掉它却不报它）：" + "；".join(blind))
    return out


def main():
    failures = list(check_coverage())
    for fixture, expected, extra in CASES:
        label = fixture + (" " + " ".join(extra) if extra else "")
        try:
            payload = run_case(fixture, extra)
        except RuntimeError as exc:
            failures.append(f"{label}: {exc}")
            continue
        findings = payload["findings"]
        actual = {f["code"] for f in findings}
        summary = payload["summary"]
        if actual != expected:
            failures.append(
                f"{label}: 期望 {sorted(expected) or '无'}，实际 {sorted(actual) or '无'}")
            continue
        if not expected and (summary["errors"] or summary["warns"]):
            failures.append(
                f"{label}: 正对照必须 0 ERROR 0 WARN，实际 "
                f"{summary['errors']} ERROR / {summary['warns']} WARN")
            continue
        print(f"PASS {label}: {sorted(expected) or '0 条发现'}")

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"{len(failures)} 例不符合期望", file=sys.stderr)
        return 1
    print(f"ALL {len(CASES)} FIXTURES MATCHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
