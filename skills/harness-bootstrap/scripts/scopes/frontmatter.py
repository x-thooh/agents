"""frontmatter：name / description 合规、字段表外字段。

§二.2：description 只写触发条件与症状，绝不总结流程
（superpowers writing-skills 的理由：读了流程摘要的 agent 会照摘要做而不读正文）。
"""
import os
import re

from .common import Finding, field_value, parse_fields, split_frontmatter

NAME = "frontmatter"

SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TRIGGER_MARKERS = ("用于", "适用于", "使用时", "适用", "当", "Use when", "When ")
PROCESS_MARKERS = ("\u2192", "->", "第一步", "第二步", "第三步", "然后", "接着", "最后再", "先…再")


def run(ctx, findings):
    text = ctx["text"]
    skill_dir = ctx["skill_dir"]
    fm_lines, first = split_frontmatter(text)
    if fm_lines is None:
        findings.append(Finding("ERROR", NAME, 1, "FM001",
                                "缺少 frontmatter 或未用 --- 闭合"))
        return
    fields = parse_fields(fm_lines, first)

    extra = [k for k in fields if k not in SPEC_FIELDS]
    for k in extra:
        findings.append(Finding("ERROR", NAME, fields[k]["line"], "FM007",
                                f"字段 {k!r} 不在 spec 字段表 {sorted(SPEC_FIELDS)} 内"))

    if "name" not in fields:
        findings.append(Finding("ERROR", NAME, first, "FM002", "缺少 name 字段"))
    else:
        name = field_value(fields["name"])
        if not name or len(name) > 64 or not NAME_RE.match(name):
            findings.append(Finding(
                "ERROR", NAME, fields["name"]["line"], "FM003",
                f"name 非法（要求 1-64、小写字母数字连字符、不首尾/连续连字符）: {name!r}"))
        elif name != os.path.basename(skill_dir.rstrip("/")):
            findings.append(Finding(
                "ERROR", NAME, fields["name"]["line"], "FM004",
                f"name 与目录名不一致（spec 要求匹配）: name={name!r} dir={os.path.basename(skill_dir.rstrip(chr(47)))!r}"))

    if "description" not in fields:
        findings.append(Finding("ERROR", NAME, first, "FM005", "缺少 description 字段"))
    else:
        desc = field_value(fields["description"])
        where = fields["description"]["line"]
        if not desc.strip():
            # 空值一个就够。再加一条 FM009（没有触发条件）是把同一个原因报两遍——
            # 「没有触发条件」是因为它什么都没有，不是因为写法漏了触发语。
            findings.append(Finding("ERROR", NAME, where, "FM005", "description 为空"))
        else:
            if len(desc) > 1024:
                findings.append(Finding("ERROR", NAME, where,
                                        "FM006", f"description 超长 {len(desc)} > 1024"))
            if not any(t in desc for t in TRIGGER_MARKERS):
                findings.append(Finding(
                    "ERROR", NAME, where, "FM009",
                    "description 没有触发条件（用于/适用于/使用时/Use when）——读的人不知道何时唤起它"))
            hits = [p for p in PROCESS_MARKERS if p in desc]
            if hits:
                findings.append(Finding(
                    "ERROR", NAME, where, "FM008",
                    f"description 在总结流程 {hits}——读了流程摘要的 agent 会照摘要做而不读正文；只写触发条件与症状"))
