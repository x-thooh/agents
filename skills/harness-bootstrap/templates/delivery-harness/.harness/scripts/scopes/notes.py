"""notes: 决策笔记与它所在的位置、与谁引用它（`.harness/specs/notes/`）。

  NTS001  孤儿笔记：除了自己，没有任何文档引用它——写了没人读得到
  NTS002  状态是位置：frontmatter 的 `status:` 与所在目录不一致

只判这两条，因为它们能判死。头五行齐全、`summary` ≤ 120 字、`## 不显然之处` 非空、
`scope:` ⊆ 已批准模块清单——这些要么需要模块清单与 `modules-confirmed` 那套机制，
要么是内容人判；本模板没有配套物，就在这里明说，不冒充（§六 第 3 条：弱断言比没有更坏）。

为什么「孤儿笔记」算 ERROR：笔记是给下一个人读的，没有入站链接就等于只有作者知道。
这与文档里写了却不存在的幻觉是同一处脱钩的两面——一边是「说了却没有」，这边是
「有了却没人说」。归档区不判：冻结内容不为别处文法返工，但仍要有入站链接才找得到，
所以归档目录**在**扫描面里。

零篇笔记是合法状态（新仓库还没决策），不按坑 #11 报错；但目录都不存在时记 not_applicable。
"""
import re
from pathlib import Path

from .common import add

NAME = "notes"
NOTES_REL = ".harness/specs/notes"
DIRS = ("proposed", "implemented", "rejected")
STATUS = re.compile(r"^status:\s*(.+?)\s*$", re.M)


def _notes(root):
    base = root / NOTES_REL
    out = []
    for name in DIRS:
        sub = base / name
        if sub.is_dir():
            out += [(name, p) for p in sorted(sub.glob("*.md"))]
    return out


def _corpus(root, skip):
    """引用来源：仓库根的 AGENTS.md + `.harness/` 下所有 .md（不含被查的那篇自己）。"""
    paths = [root / "AGENTS.md"]
    paths += sorted((root / ".harness").rglob("*.md"))
    parts = []
    for path in paths:
        if not path.is_file() or path.resolve() == skip.resolve():
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(parts)


def run(ctx, findings):
    root = Path(ctx["root"])
    if not (root / NOTES_REL).is_dir():
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    notes = _notes(root)
    for name, path in notes:
        rel = f"{NOTES_REL}/{name}/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            add(findings, "ERROR", NAME, rel, 1, "NTS001",
                f"读不了（{exc.strerror}）：笔记判不了，不能当通过")
            continue
        match = STATUS.search(text)
        if not match:
            add(findings, "ERROR", NAME, rel, 1, "NTS002",
                "头五行缺 `status:`：状态是位置，字段只是投影，但投影不许缺——"
                f"补成 `status: {name}`")
        elif match.group(1).strip().strip("\"'") != name:
            add(findings, "ERROR", NAME, rel, 1, "NTS002",
                f"`status: {match.group(1).strip()}` 与所在目录 `{name}/` 不一致："
                "换状态用 git mv，只改字段会留下没有版本记录的错位")
        corpus = _corpus(root, path)
        if path.name not in corpus and rel not in corpus:
            add(findings, "ERROR", NAME, rel, 1, "NTS001",
                "孤儿笔记：除了自己，没有任何文档（AGENTS.md / decisions.md / 其它笔记）"
                "引用它。没人链进来 = 写了没人读得到，与「说了却没有」是同一处脱钩的两面")
