"""runtime: 错误处理与并发安全（panic / 吞错 / 丢链 / context / 同步原语）。"""
import re
from pathlib import Path

from .common import (
    WORD_ERR,
    add,
    as_dict,
    blank_strings,
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
# 错误字符串字面量（单行形式；跨行写法抓不到，宁可漏报不误报）
ERROR_LITERAL = re.compile(r'(?:errors\.New|fmt\.Errorf)\(\s*"((?:[^"\\]|\\.)*)"')
# 包级错误变量：var ErrFoo = errors.New(...)
ERROR_VAR = re.compile(r"^var\s+(\w+)\s*=\s*(?:errors\.New|fmt\.Errorf)\(")
# func (r *FooError) Error() string  —— 自定义错误类型
ERROR_METHOD = re.compile(r"^func\s+\(\s*\w+\s+\*?(\w+)\s*\)\s*Error\s*\(\s*\)\s*string")
INIT_FUNC = re.compile(r"^func\s+init\s*\(\s*\)")
TRAILING_PUNCT = (".", "!", "?", ":", ";", ",")


def run(ctx, findings):
    root = Path(ctx["root"])
    src = go_src(root, as_dict(ctx.get("quality")))
    error_types = _collect_error_types(root, src)
    for path in go_files(src, include_tests=False):
        rel = rel_to(root, path)
        pkg = go_package(path)
        lines = code_lines(path)
        # code_lines 保留字面量原文（错误文案标点、%w、ERROR_LITERAL 都要读它），
        # 所以「禁某个调用」类断言读的是抹掉字面量的副本，否则
        # var _ = "panic(" 会被判成真调用。
        bare_lines = [(no, blank_strings(code)) for no, code in lines]
        body = "\n".join(code for _, code in bare_lines)
        for idx, (lineno, text) in enumerate(lines):
            bare = bare_lines[idx][1]
            _check_panic(pkg, rel, lineno, bare, findings)
            _check_exit(pkg, rel, lineno, bare, findings)
            _check_context(pkg, rel, lineno, bare, findings)
            _check_wrap(rel, lineno, text, bare, findings)
            _check_swallow(rel, lines, idx, findings)
            _check_sleep(rel, lineno, bare, findings)
            _check_goroutine(rel, lineno, bare, body, findings)
            _check_error_string(rel, lineno, text, findings)
            _check_error_var(rel, lineno, text, findings)
            _check_init(pkg, rel, lineno, text, findings)
    _check_error_type_names(error_types, findings)


def _check_panic(pkg, rel, lineno, bare, findings):
    if pkg != "main" and "panic(" in bare:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT001",
            "库代码里 panic：返回 error，由 main 决定退出")


def _check_exit(pkg, rel, lineno, bare, findings):
    if pkg == "main":
        return
    if "log.Fatal(" in bare or "os.Exit(" in bare:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT002",
            "库代码里 log.Fatal/os.Exit：进程退出只属于 main")


def _check_context(pkg, rel, lineno, bare, findings):
    if pkg == "main":
        return
    if "context.Background()" in bare or "context.TODO()" in bare:
        add(findings, "ERROR", NAME, rel, lineno, "RUNT005",
            "库代码自造 context：ctx 必须由调用方传入（首参 ctx context.Context）")


def _check_wrap(rel, lineno, code, bare, findings):
    # 调用看 bare（字面量里出现 fmt.Errorf( 不是调用），%w 看 code（它是格式串内容）。
    if "fmt.Errorf(" in bare and WORD_ERR.search(bare) and "%w" not in code:
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


def _check_sleep(rel, lineno, bare, findings):
    if "time.Sleep(" in bare:
        add(findings, "WARN", NAME, rel, lineno, "RUNT006",
            "time.Sleep 不是同步原语：用 ctx/errgroup/channel 收敛等待")


def _check_goroutine(rel, lineno, bare, body, findings):
    if not GO_STMT.match(bare):
        return
    if "errgroup" in body or "sync." in body or "chan " in body or "chan<-" in body:
        return
    add(findings, "WARN", NAME, rel, lineno, "RUNT007",
        "go 语句同文件内没有 WaitGroup/errgroup/channel：goroutine 无收敛路径")


def _check_error_string(rel, lineno, code, findings):
    """CodeReviewComments: Error Strings —— 错误串不大写开头、不带结尾标点。

    理由是它会被拼进别的消息里：log.Printf("Reading %s: %v", name, err) 不该出现句中大写。
    全大写的首词（HTTP / URL）放行，那是缩写不是句子开头。
    """
    for match in ERROR_LITERAL.finditer(code):
        message = match.group(1)
        if not message:
            continue
        first_word = message.split()[0]
        if message[0].isupper() and not first_word.isupper():
            add(findings, "ERROR", NAME, rel, lineno, "RUNT008",
                f"错误串以大写开头（{message[:24]!r}）：它会被拼进别的消息，用小写")
        if message.rstrip().endswith(TRAILING_PUNCT):
            add(findings, "ERROR", NAME, rel, lineno, "RUNT008",
                f"错误串以标点结尾（{message[:24]!r}）：去掉结尾标点")


def _check_error_var(rel, lineno, code, findings):
    """Uber: Error Naming —— 包级错误变量用 Err/err 前缀。"""
    match = ERROR_VAR.match(code)
    if not match:
        return
    name = match.group(1)
    if not (name.startswith("Err") or name.startswith("err")):
        add(findings, "ERROR", NAME, rel, lineno, "RUNT009",
            f"错误变量 {name!r} 没有 Err/err 前缀：导出用 ErrFoo，未导出用 errFoo")


def _check_init(pkg, rel, lineno, code, findings):
    """Uber: Avoid init() —— 库代码不许有 func init()。"""
    if pkg == "main":
        return
    if INIT_FUNC.match(code):
        add(findings, "ERROR", NAME, rel, lineno, "RUNT010",
            "库代码里 func init()：初始化逻辑放显式构造函数，由 main 调用")


def _collect_error_types(root, src):
    """扫出实现了 error 的类型：{(包目录, 类型名): (rel, 行号)}。"""
    found = {}
    for path in go_files(src, include_tests=False):
        rel = rel_to(root, path)
        for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = ERROR_METHOD.match(raw.strip())
            if match:
                found[(path.parent, match.group(1))] = (rel, idx)
    return found


def _check_error_type_names(error_types, findings):
    """Uber: Error Naming —— 自定义错误类型以 Error 结尾（NotFoundError）。"""
    for (_pkg_dir, name), (rel, line) in error_types.items():
        if not name.endswith("Error"):
            add(findings, "ERROR", NAME, rel, line, "RUNT009",
                f"错误类型 {name!r} 不以 Error 结尾：用 {name}Error，让调用方一眼看出它是什么")
