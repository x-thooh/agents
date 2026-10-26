"""baseline：基线机制小节的记账与收敛契约。

四层要求，缺哪层这一小节就从账本退化成免罪符：
  BASE001 条数 + 逐条输出（只报计数的基线会把同类再犯吞掉）
  BASE003 零基线 + accepted 白名单 + 只减不增（首版灌满 = 开张即免罪）
  BASE004 保质期（复查日期到期未续即 ERROR，否则日期是装饰）
"""
import re

from .common import Finding

NAME = "baseline"

BASE_HEAD = re.compile(r"^(#{2,4})\s+.*基线")
BASE_COUNT = re.compile(r"条数|count|数量")
BASE_ITEM = re.compile(r"逐条|每条|逐项")
BASE_ZERO = re.compile(r"零基线|首版[^\n]{0,12}空")
BASE_ACCEPT = re.compile(r"accepted|白名单")
BASE_MONO = re.compile(r"只减不增|不得增加|不许增加")
BASE_EXPIRE = re.compile(r"(过期|到期)[^\n]{0,40}(ERROR|报错|失效|重新盖章|重盖)")


def run(ctx, findings):
    text = ctx["text"]
    lines = text.splitlines()
    start = None
    level = 0
    for i, ln in enumerate(lines):
        m = BASE_HEAD.match(ln)
        if m:
            start, level = i, len(m.group(1))
            break
    if start is None:
        if "基线" in text:
            findings.append(Finding("WARN", NAME, 1, "BASE002",
                                    "文档提到基线但没有基线机制小节：要么补一小节，要么不提"))
        return
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    body = "\n".join(lines[start:end])
    missing = []
    if not BASE_COUNT.search(body):
        missing.append("条数（判断同一格是不是又犯了）")
    if not BASE_ITEM.search(body):
        missing.append("逐条输出（不许只报「基线内 N 条」）")
    if missing:
        findings.append(Finding("ERROR", NAME, start + 1, "BASE001",
                                "基线机制小节缺：" + ";".join(missing)))
    missing3 = []
    if not BASE_ZERO.search(body):
        missing3.append("零基线（首版 baseline 必须为空，不许把当天 ERROR 灌进去当见面礼）")
    if not BASE_ACCEPT.search(body):
        missing3.append("accepted 白名单（每条带理由 + 负责人 + 复查日期，不许既不修也不豁免）")
    if not BASE_MONO.search(body):
        missing3.append("accepted/基线总数只减不增（新增即 ERROR，不许只增不减）")
    if missing3:
        findings.append(Finding("ERROR", NAME, start + 1, "BASE003",
                                "基线机制小节缺：" + ";".join(missing3)))
    if not BASE_EXPIRE.search(body):
        findings.append(Finding("ERROR", NAME, start + 1, "BASE004",
                                "豁免没有保质期：没写「复查日期过期未续或未移除即报 ERROR」——不定义到期行为，复查日期就只是装饰"))
