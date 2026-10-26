"""links：外部链接（默认跳过）与相对链接（离线强断言）。

相对链接指向的文件必须存在——离线可判，所以声明失败时是 ERROR 不是降级
（§七.12：跨文件一律相对链接，所以它得被查）。
"""
import http.client
import pathlib
import re
import urllib.parse

from .common import Finding

NAME = "links"

MD_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
MD_LINK_REL = re.compile(r"\[[^\]]*\]\((?![a-z][a-z0-9+.-]*:|#)([^)\s]+)\)")


def run(ctx, findings):
    text = ctx["text"]
    check_relative_links(text, ctx["skill_dir"], findings)
    check_external_links(text, findings, ctx.get("check_links", False))


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


def check_external_links(text, findings, do_check):
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
        code, err = http_status(url)
        if code is None:
            findings.append(Finding("WARN", NAME, line, "LINK003",
                                    f"链接不可达（降级 WARN）: {url} ({err})"))
        elif code >= 400:
            findings.append(Finding("ERROR", NAME, line, "LINK002",
                                    f"链接返回 {code}: {url}"))


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
