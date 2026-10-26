"""deliverable：交付物必须在文档里被点名——「有了却没人说」是文档与交付物脱钩。

反方向（文档点名的路径必须存在）判不了：文档在用反引号讲**目标仓库**的布局，
按本仓库基址判会产出 26 条语义正确的误报。归属是语义不是语法——详见断言坑 #19。
反向只保留两个能判死的形态：`LINK004`（相对链接）与 `DOC002`（code / scope 名）。

本 scope 只判一个方向，也只判一件事：**每一个交付物都至少被文档提过一次**。

边界（哪些文件算「交付物」）是约定，写在 `_artifacts` 里，不是靠 glob 推断：
  * `scripts/*.py`（调度器与工具）、`tests/*.py`（自身门禁）
  * `references/*.md`（笔记与参考材料）
  * 根文件 `README.md` / `Makefile` / `LICENSE` / `pyproject.toml`
  * 每套模板的 `AGENTS.md` / `Makefile` / `TEMPLATE.md` / `README.md`

`scripts/scopes/*.py` 故意**不在**边界内：它们已经由 `references/code-index.md`
逐个点名（`CODEINDEX001` 逐字节对账）。同一个对象让两个 scope 各判一遍，
就是「同一个数不写第二遍」。

命名判据只认「出现过」：相对路径或文件名在 SKILL.md ∪ references/*.md 里出现即算。
不要求精确引用——本 scope 判的是「有没有人说过它」，不是「引用格式对不对」。

读不动的目录/文件一律显式报错，不静默跳过（坑 #11：漏掉的那个正好可能是没人说的那个）。
"""

import os

from .common import Finding

NAME = "deliverable"
CODE = "DLV001"

ROOT_FILES = ("README.md", "Makefile", "LICENSE", "pyproject.toml")
TEMPLATE_FILES = ("AGENTS.md", "Makefile", "TEMPLATE.md", "README.md")
SCAN_DIRS = ("scripts", "tests", "references")


def _listdir(path, findings):
    """列目录；读不动就报出来。返回 [] 时调用方必须已经有过一条 ERROR。"""
    try:
        return sorted(os.listdir(path))
    except OSError as exc:
        findings.append(
            Finding(
                "ERROR",
                NAME,
                0,
                CODE,
                f"读不了目录 {path}/（{exc.strerror}）：枚举不完整就不能当通过——漏掉的那个正好可能是没人说过的那个",
            )
        )
        return []


def _read(path, findings):
    """读文档；读不动就报出来。空串会让点名判定偏向漏报，所以必须显式。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        findings.append(
            Finding(
                "ERROR", NAME, 0, CODE, f"读不了 {path}（{exc.strerror}）：文档这一侧读不动，点名判不了，不能当通过"
            )
        )
        return ""


def _artifacts(skill_dir, findings):
    """按边界返回 (相对路径, 绝对路径) 列表。只取顶层：scopes/ 由 code-index 点名。"""
    out = []
    for name in ROOT_FILES:
        path = os.path.join(skill_dir, name)
        if os.path.isfile(path):
            out.append((name, path))
    for sub in SCAN_DIRS:
        base = os.path.join(skill_dir, sub)
        if not os.path.isdir(base):
            continue
        for entry in _listdir(base, findings):
            path = os.path.join(base, entry)
            if os.path.isfile(path) and entry.endswith((".py", ".md")):
                out.append((f"{sub}/{entry}", path))
    tpl_root = os.path.join(skill_dir, "templates")
    if os.path.isdir(tpl_root):
        for tpl in _listdir(tpl_root, findings):
            tdir = os.path.join(tpl_root, tpl)
            if not os.path.isdir(tdir):
                continue
            for name in TEMPLATE_FILES:
                path = os.path.join(tdir, name)
                if os.path.isfile(path):
                    out.append((f"templates/{tpl}/{name}", path))
    return out


def _documented(skill_dir, findings):
    """文档面 = SKILL.md + references/*.md + README.md。

    为什么含 README：它不跟 skill 上下文一起加载，但它是**维护者**读的那一面。
    LICENSE / pyproject.toml 这类交付物只可能在那里被点名——只算 SKILL.md 与
    references 的话，它们会永远被当成孤儿，而实际上早就写清了。判「有没有人
    说过它」时，读者是谁不重要，文档的是。
    """
    parts = []
    for name in ("SKILL.md", "README.md"):
        path = os.path.join(skill_dir, name)
        if os.path.isfile(path):
            parts.append(_read(path, findings))
    ref_dir = os.path.join(skill_dir, "references")
    if os.path.isdir(ref_dir):
        for entry in _listdir(ref_dir, findings):
            if entry.endswith(".md"):
                parts.append(_read(os.path.join(ref_dir, entry), findings))
    return "\n".join(parts)


def run(ctx, findings):
    skill_dir = ctx["skill_dir"]
    if not os.path.isdir(os.path.join(skill_dir, "scripts")):
        # 没有 scripts/ 的样本（比如只测 frontmatter 的 fixture）：判不了，不冒充通过
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    artifacts = _artifacts(skill_dir, findings)
    if not artifacts:
        # 有 scripts/ 却一个交付物都没枚举到：那是边界写坏了，不是「都没有」——坑 #11
        findings.append(
            Finding(
                "ERROR",
                NAME,
                0,
                CODE,
                "枚举到 0 个交付物：边界 `_artifacts` 失效了（这不是「没有交付物」，是扫描面写错），不能当通过",
            )
        )
        return
    text = _documented(skill_dir, findings)
    orphans = [rel for rel, _path in artifacts if rel not in text and os.path.basename(rel) not in text]
    if orphans:
        findings.append(
            Finding(
                "ERROR",
                NAME,
                0,
                CODE,
                f"{len(orphans)} 个交付物在文档里一次都没被点名：{' '.join(orphans)}。"
                "交付物只躺磁盘上、文档一句话不说，下一个人不知道它存在、也不知道它算数——"
                "「有了却没人说」与「说了却没有」是同一处脱钩的两面",
            )
        )
