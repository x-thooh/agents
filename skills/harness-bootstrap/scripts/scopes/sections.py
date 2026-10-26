"""sections：§二.5 那两个阈值的硬上限，分两档。

  SECT001 流程手册单节 —— 撞 80 行 WARN（准备拆）；超 100 行 ERROR（必须拆）
  SECT002 参考材料单文件 —— 同样两档

两档不是一个数：80 是**准备拆**，100 是**必须拆**。等到撞线才动手，等于每次都靠
删内容腾地方——§二 上一次就是这么从 102 行压回 100 的。80 给的是 20 行余地，
让人在还有地方可放的时候就开始搬，而不是先删掉难讲的那句。

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

from .common import DOC_LIMIT, DOC_WARN, Finding, line_count

NAME = "sections"

# 数值不在这里：DOC_WARN / DOC_LIMIT 住在 common.py（全仓唯一事实源）。
# 动额度要单独一轮并在 decisions 写明理由（§二.5 额度只减不增）。

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
            if span > DOC_LIMIT:
                findings.append(Finding(
                    "ERROR", NAME, idx + 1, "SECT001",
                    f"「{title}」{span} 行 > {DOC_LIMIT} 行上限：必须拆——细节外置到 references/，"
                    f"本节只留判据与链接（不是提限；提限要单独一轮并写明谁批的）"))
            elif span > DOC_WARN:
                findings.append(Finding(
                    "WARN", NAME, idx + 1, "SECT001",
                    f"「{title}」{span} 行 > {DOC_WARN} 行：准备拆——还有 {DOC_LIMIT - span} 行余地，"
                    f"现在就把细节外置到 references/，别等撞到 {DOC_LIMIT} 行再靠删内容腾地方"))
    else:
        ctx.setdefault("not_applicable", []).append(NAME)

    ref_dir = os.path.join(ctx["skill_dir"], "references")
    if not os.path.isdir(ref_dir):
        return
    try:
        names = sorted(os.listdir(ref_dir))
    except OSError as exc:
        # 目录在 isdir 之后消失、或无读权限：记 not_applicable 并写明原因，不冒充通过。
        ctx.setdefault("not_applicable", []).append(f"{NAME}(references 不可读：{exc.strerror})")
        return
    for name in names:
        if not name.endswith(".md"):
            continue
        path = os.path.join(ref_dir, name)
        try:
            with open(path, encoding="utf-8") as fh:
                n = line_count(fh.read())
        except OSError as exc:
            # 断链、是目录、编码外的乱码：这条规则判不了。报错，别当 0 条发现。
            findings.append(Finding(
                "ERROR", NAME, 0, "SECT002",
                f"读不了该文件（{exc.strerror}）：上限没法判，不能当通过——修文件或删条目",
                path=f"references/{name}"))
            continue
        if n > DOC_LIMIT:
            findings.append(Finding(
                "ERROR", NAME, 0, "SECT002",
                f"共 {n} 行 > {DOC_LIMIT} 行上限：必须拆——按主题分成多个文件，"
                f"别把手册整本搬到 references/ 里当第二个手册",
                path=f"references/{name}"))
        elif n > DOC_WARN:
            findings.append(Finding(
                "WARN", NAME, 0, "SECT002",
                f"共 {n} 行 > {DOC_WARN} 行：准备拆——还有 {DOC_LIMIT - n} 行余地，按主题预分，"
                f"别等撞到 {DOC_LIMIT} 行再拆",
                path=f"references/{name}"))
