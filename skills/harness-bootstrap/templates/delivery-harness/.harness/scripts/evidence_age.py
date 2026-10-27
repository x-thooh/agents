"""证据时效：证据必须对应当前 HEAD——过期的证据比没有证据更坏，它看起来可信。

为什么单独一个模块、两套模板共用一份（`tests/template_parity.py` 的 SHARED）：
这条判定与业务域无关，两套模板却各有一份「证据」，只写在一套里就是 §5-2 那个开口——
delivery 的门记录可以任意陈旧而无检查。共用一份之后，改判定只改一处，两边不会漂。

调用方约定：`add(findings, severity, scope, path, line, code, message)` 是两套模板
`scopes/common.py` 里同签名的记账函数，由调用方传进来。本模块不 import 任何模板内模块，
所以它能被逐字节复制到任意模板而不改一行。

三条判据，缺一条都会放行一种「看起来做完」：
  * `at` 必须是 ISO 8601——没有时间戳的证据，时效无从谈起；
  * 有 git 时 `commit` 必须等于 HEAD——改完代码没重跑，证据就过期了；
  * 没有 git 时只 WARN，**不冒充通过**（判不了就说判不了，与 verify 的退出码契约一致）。
`example: true` 的示例数据跳过：`--strict` 已经用 EXAMPLE001 拦它，这里再报只是同一原因的第二条。
"""
import datetime
import subprocess


_HEAD = {}


def head_commit(root):
    """当前 HEAD；不是 git 仓库或没有提交时返回 None。

    按 root 缓存：一次 verify 里每份证据都要判，8 个 artifact 就是 8 次 `git rev-parse`，
    而 HEAD 在一次运行内不会变。缓存的是「这次运行看到的 HEAD」，不跨运行——
    跨运行缓存会把「刚提交完的证据」误判成过期。
    """
    key = str(root)
    if key not in _HEAD:
        proc = subprocess.run(
            ["git", "-C", key, "rev-parse", "HEAD"], check=False, capture_output=True, text=True
        )
        _HEAD[key] = proc.stdout.strip() if proc.returncode == 0 else None
    return _HEAD[key]


def check(add, findings, root, data, rel, scope, code):
    if not isinstance(data, dict) or data.get("example") is True:
        return
    at = data.get("at")
    try:
        datetime.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        add(findings, "ERROR", scope, rel, 1, code, f"at = {at!r} 不是 ISO 8601 时间")
    head = head_commit(root)
    if head is None:
        add(findings, "WARN", scope, rel, 1, code, "没有 git，证据时效判不了；不按通过处理")
        return
    commit = data.get("commit")
    if commit != head:
        add(
            findings,
            "ERROR",
            scope,
            rel,
            1,
            code,
            f"证据 commit {str(commit)[:12]!r} 不是当前 HEAD {head[:12]!r}："
            "重跑产出证据的那条命令，别手改 commit",
        )
