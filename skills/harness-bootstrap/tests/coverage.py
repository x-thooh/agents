"""覆盖闸：证明「每个 code 都有一条样本让它真的响」。

从 `fixtures.py` 拆出来，理由与本轮 `BUDGET001` 扩到 `tests/` 直接相关：闸是**逻辑**，
期望表是**数据**，跑样本是**引擎**。三件事挤在一个文件里，它长到 238 行、越过了
自己定的 200 行上限，而当时的 `BUDGET001` 只扫 `scripts/`——账一直没人看见。

三道闸，顺序从弱到强：

  ① 提取器对某个模块失效时单独报（抽到 0 个 code ≠ 这个 scope 没有 code）
  ② 每个 code 都得有 fixture
  ③ 逐个 code 脉掉验一遍：拿掉某个 code 的 fixture，闸必须**恰好**报它自己

③ 是花学费换来的：早先只抽一个三字母的 code 做反向验证，两个字母前缀的 12 个 code
整块隐形而门禁全绿。逐个验，才能把「闸自己有没有盲区」变成可执行的东西。
"""

import re
from pathlib import Path

from cases import CASES

ROOT = Path(__file__).resolve().parents[1]
SCOPES_DIR = ROOT / "scripts" / "scopes"

# 源码里出现的 code 字面量。前缀长度不固定：`FM001`/`LP001` 是两个字母，
# `XREFDOC001` 是七个。写成 `[A-Z]{3,}` 时，两个字母前缀的 12 个 code 整块隐形。
CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')


def declared_codes():
    """按 scope 模块分组返回 {模块名: {code}}。

    只算真正的 scope：有 `NAME` 常量且有 `run(` 函数的才算（`common.py` 是共用工具、
    `__init__.py` 是空包，它们本来就不报 code，不该被当成提取器失效）。
    """
    out = {}
    for src in sorted(SCOPES_DIR.glob("*.py")):
        text = src.read_text(encoding="utf-8")
        if "\ndef run(" not in text or not re.search(r"^NAME\s*=", text, re.M):
            continue
        out[src.stem] = set(CODE_LITERAL.findall(text))
    return out


def uncovered_codes(covered):
    """返回「源码里会报、但这个 covered 集合没盖住」的 code。"""
    all_codes = set()
    for codes in declared_codes().values():
        all_codes |= codes
    return sorted(all_codes - set(covered))


def check_coverage():
    """返回问题列表；空列表表示三道闸全过。"""
    by_module = declared_codes()
    if not by_module:
        return [("没识别出任何 scope 模块（需同时有 `NAME` 常量与 `run(` 函数）——提取器无从谈起，不能当通过")]
    out = []
    empty = sorted(name for name, codes in by_module.items() if not codes)
    if empty:
        out.append("这些 scope 模块没抽出任何 code（提取器对它们失效，不是它们没有 code）：" + " ".join(empty))

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
