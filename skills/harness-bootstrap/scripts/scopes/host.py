"""host：分层入口的承诺必须先过宿主加载实测。

覆盖链断言只能证明「文件之间互相覆盖」，证明不了「宿主读取了它们」；
pi 从仓库根启动时不读子目录的 AGENTS.md——没实测过的分层就是一批没人读的死规则，
而覆盖链断言照样全绿。
"""
import re

from .common import Finding

NAME = "host"

HOST_HEAD = re.compile(r"^(#{2,4})\s+(?=.*加载)(?=.*实测)")
HOST_COMMIT = re.compile(r"各目录一份|关键目录")
HOST_FALLBACK = re.compile(r"降级|只写根")


def run(ctx, findings):
    text = ctx["text"]
    lines = text.splitlines()
    start = None
    level = 0
    for i, ln in enumerate(lines):
        m = HOST_HEAD.match(ln)
        if m:
            start, level = i, len(m.group(1))
            break
    if start is None:
        if HOST_COMMIT.search(text):
            findings.append(Finding("ERROR", NAME, 1, "HOST002",
                "承诺了分层入口（各目录一份/关键目录）但没有「宿主加载实测」小节：覆盖链断言证明不了宿主会读取非根文件"))
        return
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    body = "\n".join(lines[start:end])
    missing = []
    if "decisions" not in body:
        missing.append("结论落 decisions.md（宿主名 + 版本 + 日期）")
    if not HOST_FALLBACK.search(body):
        missing.append("宿主不支持时的降级动作")
    if missing:
        findings.append(Finding("ERROR", NAME, start + 1, "HOST001",
                                "宿主加载实测小节缺：" + "；".join(missing)))
