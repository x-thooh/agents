"""struct：skill 根目录是否符合标准形状。

标准四件：`SKILL.md`（必需，入口与元数据）、`references/`（按需查的支撑文档）、
`scripts/`（可执行代码）、`agents/`（子 Agent 定义）。多出来的目录不算错，但必须
**声明**——没声明的目录会悄悄长成第二个入口，下一个人不知道该读哪个。

所以本 scope 只判两件机器判得了的事：
  1. 拼写：`reference` / `script` / `agent` 这类近似名一律按错报（标准是复数）；
  2. 声明：根下每个条目必须落在 STANDARD、EXTRAS（带理由）或 TOOL_JUNK 里。

不判：目录里放什么、层级多深、内容质量——那些是别的 scope 与人判的事。
"""

import os

from .common import Finding

NAME = "struct"

# 标准形状。缺哪个不算错（除了 SKILL.md，它由 audit.py 主入口兜底），多了才判。
STANDARD = {"SKILL.md", "references", "scripts", "agents"}

# 标准之外允许存在的条目：每个都必须有一句理由，理由写不出来就该挪走。
EXTRAS = {
    "README.md": "维护者入口，给人看，不进 skill 上下文",
    "Makefile": "统一命令入口（§十 自检项：所有命令从统一入口走）",
    "tests": "自身门禁的反向 fixture",
    "templates": "生成物模板，拷进目标仓库用，不是参考文档",
    ".gitignore": "git 忽略清单",
    ".github": "CI 门禁（pre-commit 可被 --no-verify 绕过）",
    ".git": "版本库",
    "LICENSE": "采用条款；本 skill 的安装方式就是拷贝，没有许可在法务上等于保留一切权利",
    "pyproject.toml": "Python 静态检查（ruff）的唯一配置处；不打包发布，只放工具配置",
}

# 近似名 = 拼错的信号。单数/大小写变体都按错报，不猜意图。
NEAR_MISS = {
    "reference": "references",
    "references.md": "references/",
    "script": "scripts",
    "agent": "agents",
}

# 工具缓存不是结构，不参与判定（.gitignore 已经管它们）。
TOOL_JUNK = {".DS_Store", ".idea", ".ruff_cache", "__pycache__", ".pytest_cache"}

REF_DIR = "references"
REF_SUFFIX = ".md"


def run(ctx, findings):
    skill_dir = ctx["skill_dir"]
    try:
        entries = sorted(os.listdir(skill_dir))
    except OSError as exc:
        findings.append(Finding("ERROR", NAME, 0, "STRUCT001", f"读不了 skill 目录: {exc}"))
        return

    for name in entries:
        if name in STANDARD or name in EXTRAS or name in TOOL_JUNK:
            continue
        if name in NEAR_MISS:
            findings.append(Finding(
                "ERROR", NAME, 0, "STRUCT001",
                f"标准拼写是 {NEAR_MISS[name]}，不是 {name!r}",
                path=name))
            continue
        findings.append(Finding(
            "ERROR", NAME, 0, "STRUCT001",
            f"根下多出未声明的条目 {name!r}：要么并进标准四件，"
            "要么在 scripts/scopes/struct.py 的 EXTRAS 里写明理由",
            path=name))

    check_references(skill_dir, findings)


def check_references(skill_dir, findings):
    """references/ 只放供按需读取的文档：代码归 scripts/，子目录归新的一层。"""
    ref_dir = os.path.join(skill_dir, REF_DIR)
    if not os.path.isdir(ref_dir):
        return
    for name in sorted(os.listdir(ref_dir)):
        rel = f"{REF_DIR}/{name}"
        if os.path.isdir(os.path.join(ref_dir, name)):
            findings.append(Finding(
                "ERROR", NAME, 0, "STRUCT002",
                "references/ 不建子目录：层级一深，「要用时去查」就变成「得先找」",
                path=rel))
        elif not name.endswith(REF_SUFFIX):
            findings.append(Finding(
                "ERROR", NAME, 0, "STRUCT002",
                f"references/ 只放 {REF_SUFFIX} 文档，可执行代码放 scripts/",
                path=rel))
