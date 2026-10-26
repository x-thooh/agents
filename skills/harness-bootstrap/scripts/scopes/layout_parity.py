"""layout_parity：§二.1 的布局表 ↔ 每套模板，双向对账。

  LP001 表里有、这个模板没有 —— 布局表说了要建，模板照抄时漏了
  LP002 模板里有、表里没有 —— 模板自己长出表外的产物（只判 .harness 的直接子项）
  LP003 判不了 —— 找不到布局表、消费者目录不存在、或表里一个 .harness 条目都没有

为什么必须机检：布局表是唯一事实源，模板是它的产物，产物不能反向定义规范。
§二.1 补了三格而模板没跟着补的那次是全绿的——没有任何一条断言拿两边对过账，
所以「表是根」这句话当时只是口号。

形态三分（与 §二.1 的表头一致）：
  必建  文件或目录都得在
  按需  直接子目录要在且里面至少有一个条目（空目录 git 收不上来，放 .gitkeep）；
        「按需」说的是内容，不是目录本身——目录不在，下一个人不知道能往哪放
  派生  只要求所在目录存在：派生内容由目标仓库的脚本生成，模板预置一份等于
        预置一份立刻过期的副本（§二.8「索引只派生」）

LP002 只判 `.harness/` 的直接子项：模板里的 Makefile、sample/、tests/、.golangci.yml
是模板自己的东西，不是生成物布局。判宽了会天天假阳性，判窄了正好守住「表外的
产物没人知道该不该有」这条。

`{}` 展开：一行写 `.harness/specs/notes/{proposed,implemented,rejected}/`，
逐个展开去查——路径必须报具体的那一个，不能只报花括号那一行。
"""
import os
import re

from .common import Finding

NAME = "layout_parity"

# 消费者常量表：布局表的产物。新增一套模板要在这里加一行。
# 不用 glob 自动发现：模板目录被删掉或改名时，glob 会静默变成 0 个消费者，
# 那就是 §七 坑 #2「扫到 0 个样本还报通过」。这里宁可显式列，缺了报 LP003。
CONSUMERS = (
    "templates/delivery-harness",
    "templates/go-dev-harness",
)

SHAPES = ("必建", "按需", "派生")
SPLIT = re.compile(r"\s{2,}")
BRACES = re.compile(r"\{([^{}]*)\}")


def _expand(path):
    """`.harness/specs/notes/{a,b}/` → 三个路径；没有花括号就原样返回。"""
    m = BRACES.search(path)
    if not m:
        return [path]
    out = []
    for alt in m.group(1).split(","):
        out.extend(_expand(path[:m.start()] + alt.strip() + path[m.end():]))
    return out


def _layout(lines):
    """返回布局表的行 [(原始行号, 路径, 形态, 说明)]；不是布局表就返回 []。"""
    rows = []
    for idx, ln in enumerate(lines):
        if ln.strip().startswith("```"):
            continue
        cells = [c.strip() for c in SPLIT.split(ln.strip()) if c.strip()]
        if len(cells) == 3 and cells[1] in SHAPES:
            rows.append((idx + 1, cells[0], cells[1], cells[2]))
    return rows


def _missing(tpl, path, shape):
    """过 → 空串；不过 → 缺什么的说法。"""
    full = os.path.join(tpl, path)
    is_dir = path.endswith("/")
    if shape == "必建":
        return "" if os.path.exists(full) else ("没有这个目录" if is_dir else "没有这个文件")
    if shape == "派生":
        parent = os.path.dirname(full.rstrip("/"))
        return "" if os.path.isdir(parent) else "连所在目录都没有（派生条目只要求父目录在）"
    # 按需
    if is_dir:
        if not os.path.isdir(full):
            return "没有这个目录（按需≠不建：目录要在，里面至少放一个 .gitkeep）"
        try:
            if not os.listdir(full):
                return "目录是空的（放一个 .gitkeep，否则 git 收不上来）"
        except OSError as exc:
            return f"目录读不了（{exc.strerror}）"
        return ""
    parent = os.path.dirname(full)
    return "" if os.path.isdir(parent) else "父目录不存在"


def run(ctx, findings):
    skill_dir = ctx["skill_dir"]
    present = [r for r in CONSUMERS if os.path.isdir(os.path.join(skill_dir, r))]
    if not present:
        # 没有消费者就没有对账可言。但 `templates/` 在、却没一套登记在 CONSUMERS 里，
        # 那是登记表漂了（改名/换模板）——不报就是坑 #2「扫到 0 个样本还报通过」。
        if os.path.isdir(os.path.join(skill_dir, "templates")):
            findings.append(Finding(
                "ERROR", NAME, 0, "LP003",
                "templates/ 在，但 CONSUMERS 里没有一套存在：模板改名了就把登记表改过来，"
                "否则对账静默变成 0 个消费者"))
        else:
            ctx.setdefault("not_applicable", []).append(NAME)
        return

    rows = _layout(ctx["text"].split("\n"))
    if not rows:
        findings.append(Finding(
            "ERROR", NAME, 0, "LP003",
            "有模板但找不到 §二.1 的布局表（围栏块里要有「路径 / 形态 / 说明」三列、形态取 必建|按需|派生）："
            "没有表就没有对账基准，不能当通过"))
        return

    declared = {p for _, p, _, _ in rows}
    for rel in CONSUMERS:
        tpl = os.path.join(skill_dir, rel)
        if not os.path.isdir(tpl):
            findings.append(Finding(
                "ERROR", NAME, 0, "LP003",
                f"登记的模板不存在：{rel}——改 CONSUMERS 或把模板加回来，别让它静默消失",
                path=rel))
            continue
        for line, path, shape, _desc in rows:
            for one in _expand(path):
                gap = _missing(tpl, one, shape)
                if gap:
                    findings.append(Finding(
                        "ERROR", NAME, line, "LP001",
                        f"布局表要求「{one}」（形态={shape}），模板里{gap}",
                        path=rel))
        hs = os.path.join(tpl, ".harness")
        if not os.path.isdir(hs):
            continue
        try:
            names = sorted(os.listdir(hs))
        except OSError as exc:
            findings.append(Finding(
                "ERROR", NAME, 0, "LP003",
                f"读不了 {rel}/.harness（{exc.strerror}）：对账判不了，不能当通过",
                path=rel))
            continue
        for name in names:
            p = f".harness/{name}"
            if p in declared or any(one.startswith(p + "/") for one in declared):
                continue
            findings.append(Finding(
                "WARN", NAME, 0, "LP002",
                f"模板里有「{p}」，布局表里没有：要么写进表，要么删掉——表外的产物没人知道该不该有",
                path=rel))
