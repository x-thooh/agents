"""反向 fixture：把 scope 实现塞回调度器的样子 —— LAYOUT001 的失败例。

本 skill 拆包前那 509 行单文件就是这个形状：正则常量、Finding 构造、
check_* 函数全住在一个只会变大的文件里。这里只保留症状，不保留内容。
"""
import re

NOTE_HEAD = re.compile(r"^#{2,4}\s+.*不显然")
MAKE = "ERROR"


def check_notes(text):
    if not NOTE_HEAD.search(text):
        return [Finding("ERROR", "notes", 1, "NOTE001", "缺少「不显然之处」段")]
    return []


class Finding:
    def __init__(self, sev, scope, line, code, msg):
        self.sev, self.scope, self.line, self.code, self.msg = sev, scope, line, code, msg
