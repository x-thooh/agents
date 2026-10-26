"""release: 发布与观察（artifacts/release.json）：版本一致、回滚预案、冒烟、观察窗。"""
from pathlib import Path

from .common import add, as_dict, check_fields, load_json, num, quality_get, text, warn_example

NAME = "release"
REL = ".harness/deliverables/artifacts/release.json"
ENVS = {"dev", "gray", "prod"}


def run(ctx, findings):
    data = load_json(Path(ctx["root"]), REL, NAME, findings, "REL001")
    if not isinstance(data, dict):
        return
    warn_example(data, REL, NAME, findings, ctx["strict"])
    quality = as_dict(ctx.get("quality"))
    check_version(data, findings)
    check_rollback(data, findings)
    check_smoke(data, quality, findings)
    check_observe(data, quality, findings)
    check_gray(data, findings)


def check_version(data, findings):
    check_fields(data, ("version", "tag", "commit", "env"), NAME, REL, findings, "REL001")
    version = data.get("version")
    tag = data.get("tag")
    if text(version) and text(tag) and tag != f"v{version}":
        add(findings, "ERROR", NAME, REL, 1, "REL001",
            f"tag {tag!r} 与 version {version!r} 不一致（应为 v{version}）")
    if data.get("env") not in ENVS:
        add(findings, "ERROR", NAME, REL, 1, "REL001",
            f"env = {data.get('env')!r}，必须是 {sorted(ENVS)} 之一")


def check_rollback(data, findings):
    rollback = as_dict(data.get("rollback"))
    if not rollback:
        add(findings, "ERROR", NAME, REL, 1, "REL002", "缺 rollback：没有回滚预案不许发布")
        return
    check_fields(rollback, ("trigger", "command", "owner"), NAME, REL, findings, "REL002", "rollback.")


def check_smoke(data, quality, findings):
    smoke = as_dict(data.get("smoke"))
    total = smoke.get("total")
    passed = smoke.get("passed")
    minimum = quality_get(quality, "release.smoke_min_total", 8)
    if not (num(total) and num(passed)):
        add(findings, "ERROR", NAME, REL, 1, "REL003", "smoke 需要 total 与 passed 两个数字")
        return
    if total < minimum:
        add(findings, "ERROR", NAME, REL, 1, "REL003",
            f"冒烟用例 {total} 条，少于要求的 {minimum}")
    if passed != total:
        add(findings, "ERROR", NAME, REL, 1, "REL003",
            f"冒烟 {passed}/{total} 通过：未全绿不许放量")


def check_observe(data, quality, findings):
    observe = as_dict(data.get("observe"))
    window = observe.get("window_min")
    min_window = quality_get(quality, "release.observe_min_window_min", 30)
    max_error_rate = quality_get(quality, "release.max_error_rate", 1.0)
    max_p99 = quality_get(quality, "release.max_p99_ms", 300)
    if not num(window) or window < min_window:
        add(findings, "ERROR", NAME, REL, 1, "REL004",
            f"观察窗 {window!r} 分钟，少于要求的 {min_window}")
    error_rate = observe.get("error_rate")
    if not num(error_rate) or error_rate > max_error_rate:
        add(findings, "ERROR", NAME, REL, 1, "REL004",
            f"错误率 {error_rate!r}% 超过阈值 {max_error_rate}%")
    p99 = observe.get("p99_ms")
    if not num(p99) or p99 > max_p99:
        add(findings, "ERROR", NAME, REL, 1, "REL004",
            f"p99 {p99!r}ms 超过阈值 {max_p99}ms")


def check_gray(data, findings):
    gray = as_dict(data.get("gray"))
    if not gray:
        add(findings, "ERROR", NAME, REL, 1, "REL005", "缺 gray：放量比例与持续时间必须显式声明")
        return
    percent = gray.get("percent")
    duration = gray.get("duration_min")
    if not num(percent) or not 0 < percent <= 100:
        add(findings, "ERROR", NAME, REL, 1, "REL005", f"gray.percent = {percent!r}，应在 (0, 100]")
    if not num(duration) or duration <= 0:
        add(findings, "ERROR", NAME, REL, 1, "REL005", f"gray.duration_min = {duration!r}，必须为正")
