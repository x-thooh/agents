"""layout：「一 scope 一文件」的机器判据——调度器只许调度。

机器判不了「这个文件算不算调度器」（那是语义），但判得了它退化成实现的两个体征：
调度器里出现 scope 专属正则常量、或出现 Finding 构造（= 检查逻辑本体）。
反例就是本 skill 拆包之前那 509 行单文件版本。

不管体量：那是 budget scope 的职责，它对调度器同样成立。两处都管会让同一个文件报两条，
而「200」这个数就会有两处副本、迟早对不上——实测踩过。

适用性：只在 <skill_dir>/scripts/audit.py 存在时检查；不存在时记 not_applicable，
**不冒充通过**（§七.2：扫到 0 个样本和全绿长得一模一样，所以要显式区分）。
"""
import os
import re

from .common import Finding

NAME = "layout"

CONST = re.compile(r"^[A-Z_][A-Z0-9_]*\s*=\s*re\.compile\(", re.M)
MAKE = re.compile(r"\bFinding\(")


def run(ctx, findings):
    path = ctx.get("dispatch") or os.path.join(ctx["skill_dir"], "scripts", "audit.py")
    if not os.path.isfile(path):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    hits = []
    if CONST.search(src):
        hits.append("scope 专属正则常量")
    if MAKE.search(src):
        hits.append("Finding 构造（检查逻辑本体）")
    if hits:
        findings.append(Finding(
            "ERROR", NAME, 1, "LAYOUT001",
            "调度器里长出了 scope 实现：" + "；".join(hits)
            + "——scope 实现搬进 scripts/scopes/<name>.py，调度器只留注册表与输出",
            path=os.path.relpath(path, ctx["skill_dir"])))
