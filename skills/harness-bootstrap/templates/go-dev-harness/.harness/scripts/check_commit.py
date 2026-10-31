#!/usr/bin/env python3
"""校验提交消息是否符合 Conventional Commits 1.0.0。

只判规范里机器判得了的条文（条文号见 https://www.conventionalcommits.org/en/v1.0.0/）：
  #1  type[(scope)][!]: <description>      → CM001
  #2  feat / fix 等 type 必须是已知的 noun   → CM002（本文件用 allowlist）
  #6  body 与 description 之间必须空一行     → CM003
  #12 BREAKING CHANGE 必须全大写             → CM004
  本项目自定：一个提交只做一件事              → CM006（启发式，见 MULTI_PURPOSE）

不判：description 写得好不好、body 讲清没讲清——那是人的事。

用法: python3 check_commit.py <commit-msg-file>
退出码: 0 = 通过（可含 WARN）；1 = 不合规；2 = 用法错误
"""
import re
import sys

# #14：feat/fix 之外的类型由团队自定；这里取 @commitlint/config-conventional 的常用集
TYPES = {
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
}
SUBJECT = re.compile(r"^([a-z]+)(\([^)]+\))?(!)?: (\S.*)$")
BREAKING_FOOTER = re.compile(r"^breaking[ -]change:", re.I)
SUBJECT_MAX = 72

# 一个提交只做一件事：正文里以并列连接词另起一件事，就是在合并多功能提交。
# 这只是启发式——机器判不了「两处改动算不算同一件事」。所以判据刻意收窄：
# 必须在行首（可带列表符），且连接词后 10 字内出现标点；句子中间出现「同时」不算。
# 为什么是「10 字内出现标点」而不是「紧跟标点」：自然写法是「顺带修了两处：…」，
# 紧跟标点只有刻意造句才成立。按「紧跟」判，这条规则在真实提交上几乎从不触发——
# 实测作者本人的合并提交就是这么漏过去的。仍判不了的部分归人判。
MULTI_PURPOSE = re.compile(r"^\s*(?:[-*]\s*)?(顺带|另外|附带|同时|此外)[^。；;]{0,10}?[:：，,]")


def check(text):
    """返回 [(code, message)]，空列表 = 通过。"""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return [("CM001", "提交消息为空")]

    problems = []
    subject = lines[0]
    match = SUBJECT.match(subject)
    if not match:
        problems.append((
            "CM001",
            ("首行不符合 `type(scope): 描述`（scope 与 ! 可省）："
             f"{subject[:60]!r}"),
        ))
    elif match.group(1) not in TYPES:
        problems.append((
            "CM002",
            (f"type {match.group(1)!r} 不在允许集 {sorted(TYPES)}："
             "自定类型要同步改 check_commit.py 的 TYPES"),
        ))
    if len(subject) > SUBJECT_MAX:
        problems.append((
            "CM005",
            f"首行 {len(subject)} 字，超过 {SUBJECT_MAX}：摘要只写一句，细节放 body",
        ))

    # #6：body 必须与 description 之间空一行
    if len(lines) > 1 and lines[1].strip() != "":
        problems.append(("CM003", "description 与 body 之间必须空一行"))

    # 一个提交只做一件事（启发式）：正文行首出现并列连接词即为信号
    for idx, line in enumerate(lines[2:], 3):
        if MULTI_PURPOSE.match(line):
            problems.append((
                "CM006",
                (f"第 {idx} 行以并列连接词起头（{line.strip()[:30]!r}）：一个提交只做一件事，"
                 "拆成两个提交。判据收窄到行首+标点，句中出现不算"),
            ))

    # #12：BREAKING CHANGE 必须全大写（BREAKING-CHANGE 是它的同义写法，#16）
    for idx, line in enumerate(lines[1:], 2):
        if BREAKING_FOOTER.match(line.strip()) and not line.strip().startswith("BREAKING"):
            problems.append(("CM004", f"第 {idx} 行 BREAKING CHANGE 必须全大写"))

    return problems


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("用法: check_commit.py <commit-msg-file>", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"check_commit: 读不了 {argv[0]}: {exc}", file=sys.stderr)
        return 2

    # 注释行（git 模板里的 # 提示）不算正文
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    problems = check(body)
    if not problems:
        return 0
    print("提交消息不合 Conventional Commits 1.0.0：", file=sys.stderr)
    for code, message in problems:
        print(f"  {code}  {message}", file=sys.stderr)
    print(
        "\n格式：<type>[(scope)][!]: <描述>\n"
        f"      type ∈ {sorted(TYPES)}\n"
        "      破坏性变更：type 后加 !，或 footer 写 `BREAKING CHANGE: ...`\n"
        "      细则：https://www.conventionalcommits.org/en/v1.0.0/",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
