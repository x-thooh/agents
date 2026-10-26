"""terms：规范用语「scope 分域」，不是分级。

UHP 的 conformance class 是一维累计的（Full ⊇ Extended ⊇ Core，有严格蕴含）；
harness 的 scope 按域分、互相正交，没有谁包含谁。抄「分级」两个字会让读章节
对照表的人去找一张不存在的级别表。禁同义词：只认「scope 分域」。
"""
import re

from .common import Finding

NAME = "terms"

SCOPE_CANON = re.compile(r"scope 分域")
SCOPE_BAD = re.compile(r"scope[^\n]{0,8}分级|分级[^\n]{0,8}scope")


def run(ctx, findings):
    text = ctx["text"]
    hit = SCOPE_BAD.search(text)
    if hit:
        line = text[:hit.start()].count("\n") + 1
        findings.append(Finding("ERROR", NAME, line, "SCOPE001",
                                "「scope」与「分级」同现：scope 按域分、互相正交，不是 UHP 的累计级别；用「scope 分域」"))
        return
    if "conformance" in text and not SCOPE_CANON.search(text):
        findings.append(Finding("ERROR", NAME, 1, "SCOPE001",
                                "提了 conformance 却没有规范用语「scope 分域」：只借用「声明即承诺」，不借用累计分级"))
