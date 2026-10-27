"""tplpath：模板文档点名的路径必须在该模板内可解析（`TP001`）。

为什么单列一个 scope，不并进 `deliverable`：`DLV001` 判「交付物 → 文档」（有了没人说），
这里判的是反方向（说了却没有）。两个方向的失效代价不同——前者是死重量，后者是
**照文档走会扑空**——混在一个文件里，`BUDGET001` 的 200 行先到，两个方向会一起被挤掉。

为什么只判模板、不判本 skill 的 SKILL.md：SKILL.md 用反引号讲的是**目标仓库**的布局，
按本仓库基址判会产出 26 条语义正确的误报（断言坑 #19）。模板不一样——模板本身就是
目标仓库的根，`.harness/scripts/verify.py` 在那里是**可解析的真路径**。所以这条规则的
作用域是「模板 = 根」这个性质，不是「文档里出现过路径」这个语法特征。

它拦的是 v1 P0-1 那个形态的复发：文档点名 `.harness/scripts/retro.py`，模板里却没有
这个文件——目标仓库照文档走会扑空，而当时没有任何断言会报。

不判：路径指得对不对（语义）、目标仓库该不该有它（那是采用方的决定）。
"""
import os
import re

from .common import Finding

NAME = "tplpath"
CODE = "TP001"

# 扫描面：模板里「目标仓库的人会照着做」的那几份文档。
DOCS = ("AGENTS.md", "TEMPLATE.md", "README.md")
TICK = re.compile(r"`([^`\n]+)`")
# 这些字符一出现就不是一个具体路径：通配、花括号展开、占位符、变量、并列词。
NOT_A_PATH = set(" *{}<>$~|")
PATH_EXT = (".py", ".md", ".json", ".yml", ".yaml", ".go", ".sh", ".txt", ".toml", ".proto", ".mod")
# 解析基址：模板根（= 目标仓库根）与模板的 .harness/。后者是文档里最常省略的前缀。
BASES = ("", ".harness")


def _looks_like_path(tok):
    """这个反引号片段像不像「目标仓库里的一个路径」。

    四条排除都不是口味问题，是误报来源的实测清单：通配/花括号/占位符不是具体路径；
    没有 `/` 的是 basename（文档里说「`config.json`」指的是同名文件，不是这个路径）；
    URL 不是本地路径。剩下「带扩展名」或「.harness/ 开头」的才判——前者是文件引用，
    后者是目录引用，两者都能在模板里解析。
    """
    if not tok or any(c in NOT_A_PATH for c in tok):
        return False
    if tok.startswith(("http://", "https://", "mailto:")):
        return False
    if "/" not in tok:
        return False
    if tok.startswith(".harness/"):
        return True
    return tok.rsplit("/", 1)[-1].endswith(PATH_EXT)


def _read(path, findings):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        findings.append(
            Finding("ERROR", NAME, 0, CODE, f"读不了 {path}（{exc.strerror}）：这一份判不了，不能当通过")
        )
        return ""


def run(ctx, findings):
    tpl_root = os.path.join(ctx["skill_dir"], "templates")
    if not os.path.isdir(tpl_root):
        ctx.setdefault("not_applicable", []).append(NAME)
        return
    try:
        names = sorted(os.listdir(tpl_root))
    except OSError as exc:
        findings.append(
            Finding("ERROR", NAME, 0, CODE, f"读不了 templates/（{exc.strerror}）：判不了，不能当通过")
        )
        return
    seen = 0
    for tpl in names:
        tdir = os.path.join(tpl_root, tpl)
        if not os.path.isdir(tdir):
            continue
        for name in DOCS:
            doc = os.path.join(tdir, name)
            if not os.path.isfile(doc):
                continue
            seen += 1
            text = _read(doc, findings)
            for tok in sorted({t.strip().rstrip("/") for t in TICK.findall(text)}):
                if not _looks_like_path(tok):
                    continue
                if any(os.path.exists(os.path.join(tdir, base, tok)) for base in BASES):
                    continue
                findings.append(
                    Finding(
                        "ERROR",
                        NAME,
                        0,
                        CODE,
                        f"模板文档点名 `{tok}`，模板里没有这个路径：目标仓库照这份文档走会扑空——"
                        "要么补文件，要么改成它自己该有的路径（模板即目标仓库的根，这里判得动）",
                        path=f"templates/{tpl}/{name}",
                    )
                )
    if seen == 0:
        # 有 templates/ 却一份文档都没读到：扫描面失效，不是「模板没有文档」——坑 #11
        findings.append(
            Finding(
                "ERROR",
                NAME,
                0,
                CODE,
                "templates/ 下没扫到任何 AGENTS.md / TEMPLATE.md / README.md：扫描面写错了，"
                "这不是「没有可判的文档」",
            )
        )
