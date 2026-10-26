"""loop：四段纪律的每一节都必须留下可判的痕（感知 / 规划 / 行动 / 反思）。

  LOOP001  §〇 感知节缺「机器判：」/「人判：」分列，或整节缺失
  LOOP002  §一 规划节同上
  LOOP003  §二 行动节同上
  LOOP004  §三 反思节同上

为什么不判「四段做得好不好」：那机器判不了。可判的是**它有没有把机器判项与人判项
分开写，并点名对应的 code**——这正是 §五.2「规则与断言配对」在流程轴上的同一句话：
没有断言的一句话是愿望，不标「无断言」的一句话是假承诺。四节里点名到的 code
由 `docphantom` 的 DOC002 交叉校验「真的存在」，所以本 scope 只判分列，不重复判存在性。

触发条件（防误报）：文档里**一节这样的章节都没有**时记 not_applicable——本纪律是靠
「写下这四节」opt-in 的，不给一份只讲 frontmatter 的样本扣四个 ERROR。但只要出现
一节，四节就必须齐：部分迁移比没迁移更坏，它给了一个「看起来有流程」的外观。
"""

import importlib.util
import pathlib
import re

from .common import Finding

NAME = "loop"

# 顺序即 LOOP 编号顺序：标题里的关键词 → code
TARGETS = (("感知", "LOOP001"), ("规划", "LOOP002"), ("行动", "LOOP003"), ("反思", "LOOP004"))
H2 = re.compile(r"^##\s+[" + "〇一二三四五六七八九十" + r"]+、(.+)$")
MARKERS = ("机器判：", "人判：")
CODE_LITERAL = re.compile(r'"([A-Z]{2,}[0-9]{3})"')


def _sections(lines):
    """{关键词: 该节正文}，只认 H2 标题里带该关键词的章节。"""
    out, cur, buf = {}, None, []
    for line in lines:
        m = H2.match(line)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            title = m.group(1)
            cur = next((k for k, _c in TARGETS if k in title), None)
            buf = []
            continue
        if cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def _check_hooks(ctx, findings):
    """scope 层的四段落点：`scripts/hooks.py` 里的 PLAN / REFLECT 必须与实际代码集对得上。

    对账而不是「非空就算过」：新增一个 code 却忘了登记，REFLECT 仍非空，但那个 code
    永远没有「可反向验证的面」的声明。所以逐条比集合——漏登记报缺、多登记报多。
    """
    root = pathlib.Path(ctx["skill_dir"]) / "scripts"
    target = root / "hooks.py"
    if not target.is_file():
        return False  # 目标仓库还没这套钩子：不算错，也不冒充通过
    spec = importlib.util.spec_from_file_location("_target_hooks", target)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # 语法/导入错都要报，不能静默
        findings.append(Finding("ERROR", NAME, 0, "LOOP002",
                                f"读不了 scripts/hooks.py（{exc}）：钩子判不了，不能当通过"))
        return True
    for path in sorted((root / "scopes").glob("*.py")):
        if path.stem in ("__init__", "common"):
            continue
        text = path.read_text(encoding="utf-8")
        if "\ndef run(" not in text:
            continue
        name = path.stem
        if not mod.plan(name):
            findings.append(Finding("ERROR", NAME, 0, "LOOP002",
                                    f"scope {name} 没登记 PLAN：它管什么，没人说得出来"))
        declared = set(mod.reflect(name))
        actual = set(CODE_LITERAL.findall(text))
        if not declared:
            findings.append(Finding("ERROR", NAME, 0, "LOOP004",
                                    f"scope {name} 的 REFLECT 为空：没有可反向验证的面，"
                                    "该合并或删——「空」不是通过"))
        elif declared != actual:
            lack = sorted(actual - declared)
            extra = sorted(declared - actual)
            findings.append(Finding("ERROR", NAME, 0, "LOOP004",
                                    f"scope {name} 的 REFLECT 与源码对不上："
                                    f"漏登记 {lack or '无'}、多登记 {extra or '无'}"))
    return True


def run(ctx, findings):
    has_hooks = _check_hooks(ctx, findings)
    sections = _sections(ctx["text"].split("\n"))
    if not sections:
        if not has_hooks:
            ctx.setdefault("not_applicable", []).append(NAME)
        return
    for keyword, code in TARGETS:
        if keyword not in sections:
            findings.append(
                Finding(
                    "ERROR",
                    NAME,
                    0,
                    code,
                    f"四段纪律缺「{keyword}」这一节：只要写了其中一节，四节就得齐——只写一段的纪律不是纪律，是口号",
                )
            )
            continue
        body = sections[keyword]
        lacking = [m for m in MARKERS if m not in body]
        if lacking:
            findings.append(
                Finding(
                    "ERROR",
                    NAME,
                    0,
                    code,
                    f"「{keyword}」节缺 {' / '.join(lacking)} 分列：一段纪律要么给出可判的机器判据，"
                    "要么明写「无断言」及强度来源——不标的那一种最坏，它看起来像有人守",
                )
            )
