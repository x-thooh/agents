"""version：规则集版本日期的保质期。

`rules_version` 是日期版本（不是 semver），它唯一的信息量是「什么时候被人重新确认过」。
到期而不重新确认就必须报出来，否则日期就是第二个装饰字段——和基线机制
「保质期」条同族：字段存在、行为未定义。

判据落在**同一行**：提到 `rules_version` 的那一行本身要同时写出保质期天数与到期行为。
不允许「隔壁段落写了句过期就报 ERROR」蒙混——那正是「字段在此、行为在彼」的装饰形态。
"""
import re

from .common import Finding

NAME = "version"

VER_MENTION = re.compile(r"rules_version")
VER_DAYS = re.compile(r"\d{1,3}\s*天")
VER_EXPIRE = re.compile(r"(到期|过期)[^\n]{0,40}(ERROR|报错|失效|重新确认|重新盖章|重盖)")


def run(ctx, findings):
    mentions = [ln for ln in ctx["text"].splitlines() if VER_MENTION.search(ln)]
    if not mentions:
        return
    if any(VER_DAYS.search(ln) and VER_EXPIRE.search(ln) for ln in mentions):
        return
    missing = []
    if not any(VER_DAYS.search(ln) for ln in mentions):
        missing.append("保质期天数（N 天）")
    if not any(VER_EXPIRE.search(ln) for ln in mentions):
        missing.append("到期行为（到期未重新确认即报 ERROR）")
    findings.append(Finding(
        "ERROR", NAME, 1, "VER001",
        "rules_version 只盖章没有到期行为：" + "；".join(missing)
        + "——提到它的那一行就要写明天数与到期行为，否则日期就是装饰（基线机制「保质期」条的同族病）"))
