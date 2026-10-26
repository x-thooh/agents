"""cli：入口参数 → 已验证的值（`--only` 的 scope 选择 + `--link-status` 解析）。

为什么单独一个文件：这两件事都是「把用户输入变成已验证的值」，与调度、scope 实现无关。
留在 `audit.py` 里会让调度器越过 `BUDGET001` 的 150 行——而调度器该只有注册表与输出
（`LAYOUT001` 判的就是这件事）。搬出来之后，判据（未知 scope 即退出码 2）也更清楚：
拼错一个名字不该静默少跑一条检查，那是这套门禁最反对的那种绿灯。
"""


def parse_link_status(items):
    """`--link-status URL=CODE` → {URL: int|'ERR'}。"""
    out = {}
    for item in items:
        url, sep, value = item.rpartition("=")
        if not sep or not url:
            raise ValueError(f"--link-status 要写成 URL=CODE：{item!r}")
        if value == "ERR":
            out[url] = "ERR"
            continue
        try:
            out[url] = int(value)
        except ValueError:
            raise ValueError(f"--link-status 的 CODE 必须是整数或 ERR：{value!r}") from None
    return out


def select(mapping, only):
    """`--only frontmatter,links` → 选中的 scope 元组；空则全跑（按注册表顺序）。

    `mapping` 是 {NAME: module}，由调用方给——调度器持有注册表，这里只做选择。
    """
    if not only:
        return tuple(mapping.values())
    wanted = [w.strip() for w in only.split(",") if w.strip()]
    unknown = [w for w in wanted if w not in mapping]
    if unknown:
        raise ValueError(
            f"--only 里有未知 scope：{', '.join(unknown)}；"
            f"可选：{', '.join(sorted(mapping))}")
    if not wanted:
        raise ValueError("--only 传了空列表：要么不传（全跑），要么点名至少一个 scope")
    return tuple(mapping[w] for w in wanted)
