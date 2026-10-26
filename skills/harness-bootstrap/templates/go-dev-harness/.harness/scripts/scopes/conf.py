"""conf: .harness/config.json 自身的诚实性——示例标记、键名拼写、go_src 是否已接线。

三条都来自一次真实事故：模板拷进空仓库后，把 deliverables 里的 example 去掉、
config.json 没动，`verify --strict` 报 0 ERROR 0 WARN —— 而仓库真实代码里的
`panic` 一次也没被检查到，因为 go_src 还指着模板自带的 `sample/`。
假绿灯比漏报更坏：它给了一句「已经验过了」。

  CONF001    键名拼错 / 未知键      → ERROR（静默忽略未知键 = 整条扫描被关掉）
  CONF002    go_src 仍指向 sample/  → strict 下 ERROR（门禁扫的是模板样本，不是你的代码）
  EXAMPLE001 config.json 自己是示例数据（复用 common.warn_example）
"""
from .common import add, quality_get, warn_example

NAME = "conf"

# 键名闭集：枚举值一律常量表（§二.2）。值 None = 标量；值 set = 该键下允许的子键。
# 新增一个配置项要同批改这里，否则 verify 报未知键——这正是要的。
ALLOWED = {
    "example": None,
    "go_src": None,
    "go_version_min": None,
    "main_max_lines": None,
    "max_file_lines": None,
    "max_interface_methods": None,
    "coverage": {"total_min", "core_min"},
    "review": {"max_lines", "min_reviewers"},
    "release": {"smoke_min_total", "observe_min_window_min", "max_error_rate", "max_p99_ms"},
}

REL = ".harness/config.json"
SHIPPED_SAMPLE = "sample"  # 模板自带的示例模块目录；指向它说明还没接线


def _unknown(findings, key, allowed_hint):
    add(findings, "ERROR", NAME, REL, 1, "CONF001",
        f"未知配置键 {key!r}：verify 会静默忽略它——一整条扫描就此被关掉。"
        f"允许的键：{allowed_hint}。新增配置项要同批更新 conf.py 的 ALLOWED")


def run(ctx, findings):
    quality = ctx.get("quality") or {}
    warn_example(quality, REL, NAME, findings, ctx["strict"])

    for key in sorted(quality):
        spec = ALLOWED.get(key, "unknown")
        if spec == "unknown":
            _unknown(findings, key, ", ".join(sorted(ALLOWED)))
            continue
        if isinstance(spec, set) and isinstance(quality.get(key), dict):
            for sub in sorted(quality[key]):
                if sub not in spec:
                    _unknown(findings, f"{key}.{sub}", ", ".join(sorted(spec)))

    src_rel = quality_get(quality, "go_src", ".")
    if isinstance(src_rel, str) and src_rel.strip().strip("./") == SHIPPED_SAMPLE:
        severity = "ERROR" if ctx["strict"] else "WARN"
        add(findings, severity, NAME, REL, 1, "CONF002",
            f"go_src 仍指向 {SHIPPED_SAMPLE!r}（模板自带的示例模块）：门禁扫的是样本，不是你仓库的代码。"
            "把 go_src 改成真实模块根（通常是 \".\"）。若你的模块确实放在 sample/，请把目录改名——"
            "sample/ 是模板保留位置，门禁会一直提醒你还没接线")
