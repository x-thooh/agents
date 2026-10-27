"""ledger：「双向对账」两侧必须各点名一个载体，否则它就是派生品自比较。

声明侧 = 人手维护的意图文件（如 skills.declared.yaml），事实侧 = 磁盘目录。
两边都由脚本生成时，重跑一次永远一致，构不出失败例，那就不是断言。
"""
import re

from .common import Finding
from .layout_parity import _layout

NAME = "ledger"

DUAL_TRIGGER = re.compile(r"双向对账|双向比对")
DUAL_INTENT = re.compile(r"声明|意图")
DUAL_CARRIER = re.compile(r"`[^`\s]+\.(?:ya?ml|json|csv|txt|md)`")
# 「↔ 磁盘 `skills/`」里的磁盘侧目录；它必须出现在布局表里，否则两侧各说各话。
DUAL_DISK = re.compile(r"磁盘\s*`([^`\s]+/)`")


def run(ctx, findings):
    lines = ctx["text"].splitlines()
    layout_paths = {path for _line, path, _shape, _desc in _layout(lines)}
    heads = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+", ln)
        if m:
            heads.append((i, len(m.group(1))))
    heads.append((len(lines), 0))
    for idx, (start, _level) in enumerate(heads[:-1]):
        end = heads[idx + 1][0]
        body = "\n".join(lines[start:end])
        if not DUAL_TRIGGER.search(body):
            continue
        missing = []
        if not DUAL_INTENT.search(body):
            missing.append("声明侧（人手维护的意图）")
        if not DUAL_CARRIER.search(body):
            missing.append("声明侧的具体文件路径（如 `harness/skills.declared.yaml`）")
        if missing:
            findings.append(Finding("ERROR", NAME, start + 1, "DUAL001",
                "双向对账小节没点名：" + "；".join(missing) + "。两侧都派生时断言恒真、构不出失败例"))
        for disk in DUAL_DISK.findall(body):
            if disk not in layout_paths and not any(p.startswith(disk) for p in layout_paths):
                findings.append(Finding("ERROR", NAME, start + 1, "DUAL001",
                    f"双向对账写到的磁盘侧 `{disk}` 不在布局表里：布局表是唯一事实源，"
                    "对账两侧必须有一侧是表里登记过的真实目录"))
