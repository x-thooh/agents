"""sections：§二.5 那两个「100 行」阈值的硬上限。

  SECT001 流程手册单节超 100 行 —— 拆：细节外置到 references/，本节只留判据与链接
  SECT002 参考材料单文件超 100 行 —— 拆：按主题分成多个 references 文件

为什么必须机检：有上限而无数值、无断言，等于没有上限。数值写在散文里，
下次谁加五行就越界，门禁照样全绿——本 skill 的 §二 就这么撞过一次（102 行），
而当时没有任何一条断言会报出来。

SECT001 判的是 `##` 节，不是整文件行数：整篇可以很长（它是手册），但**任何一节都不许
长成第二个手册**。超了怎么办：拆，**不是提限**——提限要单独一轮改并写明谁批的
（§二.5 额度只减不增）。

边界（与断言坑 #11「扫到 0 个样本要报错」的区别）：这里没有 glob、没有路径，
文本是已经读进来的；「0 个标题」「references 里没有 .md」都是合法状态，不是扫描失效。
所以记 not_applicable 并在摘要里显式打印，不冒充通过。
"""
import os
import re

from .common import Finding

NAME = "sections"

LIMIT = 100  # 两个阈值共用的数。改它=提限，要单独一轮并在 decisions 写明理由。

HEAD = re.compile(r"^(#{1,2})\s+\S")


def _headings(lines):
    """返回 [(行下标, 级别, 标题)]；围栏代码块里的 # 是内容，不是标题。"""
    heads = []
    fence = False
    for idx, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = HEAD.match(ln)
        if m:
            heads.append((idx, len(m.group(1)), ln.strip()))
    return heads


def run(ctx, findings):
    lines = ctx["text"].split("\n")
    heads = _headings(lines)
    if heads:
        for k, (idx, _level, title) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            span = end - idx
            if span > LIMIT:
                findings.append(Finding(
                    "ERROR", NAME, idx + 1, "SECT001",
                    f"「{title}」{span} 行 > {LIMIT} 行上限：拆——细节外置到 references/，"
                    f"本节只留判据与链接（不是提限；提限要单独一轮并写明谁批的）"))
    else:
        ctx.setdefault("not_applicable", []).append(NAME)

    ref_dir = os.path.join(ctx["skill_dir"], "references")
    if not os.path.isdir(ref_dir):
        return
    for name in sorted(os.listdir(ref_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(ref_dir, name)
        with open(path, encoding="utf-8") as fh:
            n = len(fh.read().split("\n"))
        if n > LIMIT:
            findings.append(Finding(
                "ERROR", NAME, 0, "SECT002",
                f"共 {n} 行 > {LIMIT} 行上限：拆——按主题分成多个文件，"
                f"别把手册整本搬到 references/ 里当第二个手册",
                path=f"references/{name}"))
