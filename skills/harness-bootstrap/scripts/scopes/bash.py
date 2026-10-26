"""bash：围栏代码可执行（占位符 U+2026、`bash -n` 语法）。"""
import os
import re
import subprocess
import tempfile

from .common import PLACEHOLDER, Finding

NAME = "bash"

FENCE_OPEN = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")


def run(ctx, findings):
    lines = ctx["text"].split("\n")
    fence = None  # {"lang","start","content"}
    for idx, ln in enumerate(lines):
        m = FENCE_OPEN.match(ln.rstrip())
        if m and fence is None:
            fence = {"lang": m.group(1).lower(), "start": idx + 1, "content": []}
            continue
        if fence is not None and ln.strip().startswith("```"):
            lang = fence["lang"]
            content = "\n".join(fence["content"])
            if lang in ("bash", "sh", "shell", "zsh"):
                if PLACEHOLDER in content:
                    findings.append(Finding(
                        "ERROR", NAME, fence["start"], "BASH001",
                        "围栏代码含占位符 U+2026，不可执行（§七.5：文档写了、代码没实现 = 没有）"))
                bad = bash_syntax_error(content)
                if bad:
                    findings.append(Finding(
                        "ERROR", NAME, fence["start"], "BASH002",
                        f"围栏代码 bash -n 失败: {bad}"))
            fence = None
            continue
        if fence is not None:
            fence["content"].append(ln)


def bash_syntax_error(content):
    # 路径来自 tempfile.NamedTemporaryFile（无外部输入），不存在路径穿越面
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(content + "\n")
        tmp = fh.name
    try:
        proc = subprocess.run(["/bin/bash", "-n", tmp], check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            return (proc.stderr.strip().split("\n") or ["unknown error"])[0]
        return None
    finally:
        os.unlink(tmp)
