#!/usr/bin/env python3
"""校验提交消息是否符合 Conventional Commits 1.0.0。

只判规范里机器判得了的条文（条文号见 https://www.conventionalcommits.org/en/v1.0.0/）：
  #1  type[(scope)][!]: <description>      → CM001
  #2  feat / fix 等 type 必须是已知的 noun   → CM002（本文件用 allowlist）
  #6  body 与 description 之间必须空一行     → CM003
  #12 BREAKING CHANGE 必须全大写             → CM004

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
            "首行不符合 `type(scope): 描述`（scope 与 ! 可省）："
            f"{subject[:60]!r}",
        ))
    elif match.group(1) not in TYPES:
        problems.append((
            "CM002",
            f"type {match.group(1)!r} 不在允许集 {sorted(TYPES)}："
            "自定类型要同步改 check_commit.py 的 TYPES",
        ))
    if len(subject) > SUBJECT_MAX:
        problems.append((
            "CM005",
            f"首行 {len(subject)} 字，超过 {SUBJECT_MAX}：摘要只写一句，细节放 body",
        ))

    # #6：body 必须与 description 之间空一行
    if len(lines) > 1 and lines[1].strip() != "":
        problems.append(("CM003", "description 与 body 之间必须空一行"))

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
