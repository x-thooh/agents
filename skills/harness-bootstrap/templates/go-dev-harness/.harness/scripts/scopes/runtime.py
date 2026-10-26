"""runtime: 错误处理与并发安全（panic / 吞错 / 丢链 / context / 同步原语）。"""
import re
from pathlib import Path

from .common import (
    WORD_ERR,
    add,
    as_dict,
    code_lines,
    go_files,
    go_package,
    go_src,
    rel_to,
)

NAME = "runtime"

ONE_LINE_SWALLOW = re.compile(r"^if\s+err\s*!=\s*nil\s*\{\s*return(\s+nil)?\s*\}$")
BLOCK_SWALLOW = re.compile(r"^if\s+err\s*!=\s*nil\s*\{$")
BARE_RETURN = re.compile(r"^return(\s+nil)?$")
GO_STMT = re.compile(r"^\s*go\s+(func\s*\(|\w)")


def run(ctx, findings):
    root = Path(ctx["root"])
    src = go_src(root, as_dict(ctx.get("quality")))
    for path in go_files(src, include_tests=False):
        rel = rel_to(root, path)
        pkg = go_package(path)
        lines = code_lines(path)
        body = "\n".join(code for _, code in lines)
        for idx, code in enumerate(lines):
            lineno, text = code
            _check_panic(pkg, rel, lineno, text, findings)
            _check_exit(pkg, rel, lineno, text, findings)
            _check_context(pkg, rel, lineno, text, findings)
            _check_wrap(rel, lineno, text, findings)
            _check_swallow(rel, lines, idx, findings)
            _check_sleep(rel, lineno, text, findings)
            _check_goroutine(rel, lineno, text, body, findings)


def _check_panic(pkg, rel, lineno, code, findings):
    if pkg != "main" and "panic(" in code:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT001",
            "库代码里 panic：返回 error，由 main 决定退出")


def _check_exit(pkg, rel, lineno, code, findings):
    if pkg == "main":
        return
    if "log.Fatal(" in code or "os.Exit(" in code:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT002",
            "库代码里 log.Fatal/os.Exit：进程退出只属于 main")


def _check_context(pkg, rel, lineno, code, findings):
    if pkg == "main":
        return
    if "context.Background()" in code or "context.TODO()" in code:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT005",
            "库代码自造 context：ctx 必须由调用方传入（首参 ctx context.Context）")


def _check_wrap(rel, lineno, code, findings):
    if "fmt.Errorf(" in code and WORD_ERR.search(code) and "%w" not in code:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT003",
            "fmt.Errorf 包装 err 却没带 %w：错误链断了，上层无法 errors.Is/As")


def _check_swallow(rel, lines, idx, findings):
    lineno, code = lines[idx]
    stripped = code.strip()
    if ONE_LINE_SWALLOW.match(stripped):
        add(findings, "ERROR", NAME, rel, lineno, "RUNT004", "if err != nil 后直接 return nil：吞掉了错误")
        return
    if not BLOCK_SWALLOW.match(stripped):
        return
    for nxt_line, nxt_code in lines[idx + 1:]:
        if not nxt_code.strip():
            continue
        if BARE_RETURN.match(nxt_code.strip()):
            add(findings, "ERROR", NAME, rel, nxt_line, "RUNT004",
                "if err != nil 后直接 return nil：吞掉了错误")
        return


def _check_sleep(rel, lineno, code, findings):
    if "time.Sleep(" in code:
        add(findings, "WARN", NAME, rel, lineno, "RUNT006",
            "time.Sleep 不是同步原语：用 ctx/errgroup/channel 收敛等待")


def _check_goroutine(rel, lineno, code, body, findings):
    if not GO_STMT.match(code):
        return
    if "errgroup" in body or "sync." in body or "chan " in body or "chan<-" in body:
        return
    add(findings, "WARN", NAME, rel, lineno, "RUNT007",
        "go 语句同文件内没有 WaitGroup/errgroup/channel：goroutine 无收敛路径")
