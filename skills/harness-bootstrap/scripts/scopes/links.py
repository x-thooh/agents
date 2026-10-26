"""links：外部链接（默认跳过）与相对链接（离线强断言）。

相对链接指向的文件必须存在——离线可判，所以声明失败时是 ERROR 不是降级
（§七.12：跨文件一律相对链接，所以它得被查）。

**内联外部链接 vs 脚注里的 URL**：前者是承诺——写了就该能查，所以默认报一条
LINK001 提醒「还没查」。后者（`[^x]: <https://…>`）是引用他人材料的出处，
我们不需要也不应该替它背书；把它写成内联链接只会换来一条永久 WARN。
所以「降成脚注」不是关掉检查，是把承诺与引用分开：内联 = 承诺可查，
脚注 = 仅供追溯，本 scope 不管。新增内联外部链接时，要么真去查
（--check-links），要么降成脚注。
"""
import http.client
import pathlib
import re
import urllib.parse

from .common import Finding

NAME = "links"

FENCE = re.compile(r"^\s*```")
MD_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
MD_LINK_REL = re.compile(r"\[[^\]]*\]\((?![a-z][a-z0-9+.-]*:|#)([^)\s]+)\)")


def strip_code(text):
    """把围栏块与行内 code span 抹成空格，行号不变。

    为什么必须抹：文档里讲「链接语法」时写的 `[示例](url)` 不是链接，是**教材**。
    不抹的话，教一次写法就换来一条 LINK004——而修法只有两种：把教材删掉，或者
    给它编个真实路径。两种都让文档变差。判据要判的是**真的链接**。
    """
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
            continue
        if in_fence:
            out.append(" " * len(line))
            continue
        out.append(re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


def run(ctx, findings):
    text = strip_code(ctx["text"])
    check_relative_links(text, ctx["skill_dir"], findings)
    check_external_links(text, findings, ctx.get("check_links", False),
                         ctx.get("link_status"))


def check_relative_links(text, skill_dir, findings):
    root = pathlib.Path(skill_dir).resolve()
    for idx, ln in enumerate(text.split("\n")):
        for target in MD_LINK_REL.findall(ln):
            rel = target.split("#", 1)[0].split("?", 1)[0]
            if not rel:
                continue
            if not (root / rel).resolve().exists():
                findings.append(Finding("ERROR", NAME, idx + 1, "LINK004",
                                        f"相对链接指向不存在的文件: {target}"))


def check_external_links(text, findings, do_check, status_override=None):
    urls = []
    for idx, ln in enumerate(text.split("\n")):
        urls.extend((idx + 1, u) for u in MD_LINK.findall(ln))
    if not urls:
        return
    if not do_check:
        findings.append(Finding("WARN", NAME, urls[0][0], "LINK001",
                                f"外部链接 {len(urls)} 条未检查（--check-links 才真查）"))
        return
    for line, url in urls:
        code, err = _status(url, status_override)
        if code is None:
            findings.append(Finding("WARN", NAME, line, "LINK003",
                                    f"链接不可达（降级 WARN）: {url} ({err})"))
        elif code >= 400:
            findings.append(Finding("ERROR", NAME, line, "LINK002",
                                    f"链接返回 {code}: {url}"))


def _status(url, override):
    """取状态码。override 是 `--link-status URL=CODE` 建的测试缝（见 audit.py）。

    公网链接的两种结局（4xx、不可达）不可能靠真请求来确定：真去请求就是让门禁
    依赖网络抖动，不请求就是这两条断言永远不执行。所以把「拿状态码」这一步变成
    可注入的——默认仍走 http_status，只在传来 override 时绕过。缝在取数那一步，
    判定逻辑（>=400 算 ERROR / None 降级 WARN）没有被绕过。

    override 的值已由 audit.py 解析成 int 或 `ERR`；这里不再做字符串转数字，
    也就没有「随便输一个值就能让审计脚本崩掉」的面。
    """
    if not override or url not in override:
        return http_status(url)
    got = override[url]
    return (None, "测试缝：模拟不可达") if got == "ERR" else (got, None)


def http_status(url):
    """只对 http(s) 发 HEAD，拿状态码。直连不走代理；连不上就降级 WARN，不冒充内容错误。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, f"unsupported-scheme:{parsed.scheme}"
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    conn_cls = (http.client.HTTPSConnection if parsed.scheme == "https"
                else http.client.HTTPConnection)
    conn = None
    try:
        conn = conn_cls(parsed.hostname, parsed.port, timeout=10)
        conn.request("HEAD", path, headers={
            "User-Agent": "harness-bootstrap-audit/1",
            "Host": parsed.netloc,
        })
        return conn.getresponse().status, None
    except Exception as exc:  # 网络/代理/证书问题一律降级，不冒充内容错误
        return None, type(exc).__name__
    finally:
        if conn is not None:
            conn.close()
