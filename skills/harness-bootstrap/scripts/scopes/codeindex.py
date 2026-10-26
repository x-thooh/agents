"""codeindex：`references/code-index.md` 必须与 `scripts/scopes/` 里真实的 code 集合逐字节一致。

为什么要这个文件：`acceptance.md` 的对照表按「规则组」写，一行可能挂好几个 code，
而「每条硬规则在断言表里有对应行」是留给人的最后一项检查——**读者手上没有完整
的 code 清单，这一项根本核不了**。补一份清单，就补上了那个闭环。

为什么必须脚本生成：手写的清单是第二处真相。新增一个 code 时，代码改了、清单没改，
而没有任何断言会报——本仓库已经为同类问题付过学费（§二.8「禁人手索引」）。
所以判据是**重新生成后与磁盘逐字节一致**，不一致即 ERROR，修法是跑 make code-index。

为什么扫的是 `<skill_dir>/scripts/scopes` 而不是本脚本所在的目录：
清单描述的是**被审那个 skill** 的 code。扫自己的目录再拿去比别人的文件，
`tests/fixtures/ok-minimal` 这种没有 scopes 的样本会被判「缺清单」——
那不是它的问题，是适用范围错了。没有 `scripts/scopes/` 就记 not_applicable，不冒充通过。

为什么生成器不在本 scope 里：`audit.py` 的契约是「只读，不写文件」，
scope 不许代劳写盘——写盘等于让门禁顺手改证据。生成器住 `scripts/gen_code_index.py`，
本 scope 只比对。
"""
import os
import re

from .common import Finding

NAME = "codeindex"

INDEX_REL = "references/code-index.md"
SCOPES_REL = os.path.join("scripts", "scopes")
CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')
SEVERITY = re.compile(r'"(ERROR|WARN)"')
SCOPE_NAME = re.compile(r'^NAME\s*=\s*"([a-z_]+)"', re.M)
# 渲染顺序 = 升级顺序：先 WARN 后 ERROR，与文件里「轻→重」的说明一致
SEV_ORDER = {"WARN": 0, "ERROR": 1}


def declared(scopes_dir):
    """-> ({code: (scope 名, 级别集合)}, 读不动的模块列表)。

    级别取「同一个 Finding 调用里、紧挨在该 code 前面的那个 "ERROR" / "WARN"」。
    一个 code 可以有多个级别：`SECT001` 就是 >80 报 WARN、>100 报 ERROR 的两档——
    只写一档会让清单与实跑对不上（实测抓过：表和实跑在这两个 code 上不一致）。
    """
    out, unreadable = {}, []
    try:
        names = sorted(os.listdir(scopes_dir))
    except OSError as exc:
        return out, [f"目录不可读（{exc.strerror}）"]
    real_dir = os.path.realpath(scopes_dir)
    for name in names:
        if not name.endswith(".py") or name in ("__init__.py", "common.py"):
            continue
        path = os.path.realpath(os.path.join(scopes_dir, name))
        if os.path.dirname(path) != real_dir:
            # 不跟符号链接跑出 scopes 目录：本 scope 只负责列清单，不该变成任意文件读取面。
            unreadable.append(f"{name}（指向目录外，已跳过）")
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            unreadable.append(f"{name}（{exc.strerror}）")
            continue
        m = SCOPE_NAME.search(text)
        scope = m.group(1) if m else name[:-3]
        for hit in CODE_LITERAL.finditer(text):
            code = hit.group(1)
            sev = None
            for s in SEVERITY.finditer(text, 0, hit.start()):
                sev = s.group(1)
            entry = out.setdefault(code, (scope, set()))
            entry[1].add(sev or "?")
    return out, unreadable


def render(scopes_dir):
    """-> (文件全文, 读不动的模块列表)。生成器与比对共用这一份，避免两处拼字符串。"""
    codes, unreadable = declared(scopes_dir)
    rows = []
    for code, (scope, sevs) in sorted(codes.items(), key=lambda kv: (kv[1][0], kv[0])):
        ordered = sorted(sevs, key=lambda s: SEV_ORDER.get(s, 9))
        rows.append((code, scope, " → ".join(ordered)))

    only_e = sum(1 for _c, (_s, sevs) in codes.items() if sevs == {"ERROR"})
    only_w = sum(1 for _c, (_s, sevs) in codes.items() if sevs == {"WARN"})
    both = len(codes) - only_e - only_w

    out = [
        "# 全部 code 清单（脚本生成，禁手改）",
        "",
        "> 由 `python3 scripts/gen_code_index.py` 生成；`codeindex` scope 会重新生成一遍做逐字节比对，",
        "> 不一致即 ERROR。手改这个文件一定被拦——要改就改 `scripts/scopes/*.py`，然后 `make code-index`。",
        ">",
        "> 级别取自源码里同一个 `Finding(...)` 调用中紧挨在该 code 前的 `\"ERROR\"` / `\"WARN\"` 字面量。",
        "> 这个解析依赖构造形态 `Finding(\"级别\", NAME, 行, \"code\", ...)`；形态变了这里会取错，",
        "> 所以生成后要人眼看一遍，别把它当成定义——定义在代码里。",
        "> 箭头表示同一 code 有多档：`WARN → ERROR` 即「轻了报 WARN、重了报 ERROR」。",
        "",
    ]
    if codes:
        out.append(f"共 {len(codes)} 个 code：{only_e} 个只报 ERROR、{only_w} 个只报 WARN、{both} 个分两档。")
        out.append("")
        out.append("| code | scope | 级别 |")
        out.append("| --- | --- | --- |")
        out.extend(f"| `{code}` | {scope} | {sev} |" for code, scope, sev in rows)
        out.append("")
    if unreadable:
        out.append("未读入的模块（清单因此不完整，不是它们没有 code）：" + "；".join(unreadable))
        out.append("")
    return "\n".join(out), unreadable


def run(ctx, findings):
    scopes_dir = os.path.join(ctx["skill_dir"], SCOPES_REL)
    if not os.path.isdir(scopes_dir):
        # 没有 scope 实现就没有自己的 code 集合——记 not_applicable，不冒充通过。
        ctx.setdefault("not_applicable", []).append(NAME)
        return

    path = os.path.join(ctx["skill_dir"], INDEX_REL)
    expected, unreadable = render(scopes_dir)
    if unreadable:
        findings.append(Finding(
            "ERROR", NAME, 0, "CODEINDEX001",
            "清单生成不完整，有 scope 模块读不动：" + "；".join(unreadable)
            + "——这时不能当通过（否则「清单与磁盘一致」只是因为两边都少了同一批）",
            path=INDEX_REL))
        return
    if not os.path.isfile(path):
        findings.append(Finding(
            "ERROR", NAME, 0, "CODEINDEX001",
            f"缺 {INDEX_REL}：跑 `python3 scripts/gen_code_index.py` 生成——"
            "没有它，「每条硬规则在断言表里有对应行」这项人工检查没有可核对的清单",
            path=INDEX_REL))
        return
    try:
        with open(path, encoding="utf-8") as fh:
            actual = fh.read()
    except OSError as exc:
        findings.append(Finding(
            "ERROR", NAME, 0, "CODEINDEX001",
            f"读不了 {INDEX_REL}（{exc.strerror}）：清单新鲜度判不了，不能当通过",
            path=INDEX_REL))
        return
    if actual != expected:
        findings.append(Finding(
            "ERROR", NAME, 0, "CODEINDEX001",
            f"{INDEX_REL} 与源码不一致：跑 `make code-index` 重新生成。"
            "手写/手改的清单是第二处真相——新增 code 而清单没跟着改时，没有任何其他断言会报",
            path=INDEX_REL))
