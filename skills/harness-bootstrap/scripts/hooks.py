"""hooks：每个 scope 的 plan() / reflect()——四段纪律在 scope 层的落点。

为什么集中登记，而不是每个 scope 自带一组：按 Q29a 本该由 scope 自带，但
`BUDGET001` 的 150 行只减不增——6 个 scope 已在 146–151 行，各加 6 行就会顶破
WARN 线。集中一文件不破额度、不破层间单向，而且断言更强：`loop` 会拿本表与
各 scope 源码里的 code 字面量逐条对账，漏登记或加了 code 没登记都会报。

PLAN = 判定范围（这一域管什么）；REFLECT = 它能报的 code（可反向验证的面）。
空 = 这个 scope 没有可验证的面，该合并或删——不是「通过」。
"""

PLAN = {
    "baseline": "基线机制小节的记账与收敛契约",
    "bash": "围栏代码可执行（占位符 U+2026、`bash -n` 语法）",
    "budget": "脚本体量与手册总量，各两档",
    "codeindex": "`references/code-index.md` 必须与 `scripts/scopes/` 里真实的 code 集合逐字节一致",
    "deliverable": "交付物必须在文档里被点名——「有了却没人说」是文档与交付物脱钩",
    "docclaim": "文档声称的规则载体必须覆盖代码里真实的每个 code",
    "docphantom": "文档 → 源码方向——文档点名的 code / scope 模块必须真的存在",
    "frontmatter": "name / description 合规、字段表外字段",
    "host": "分层入口的承诺必须先过宿主加载实测",
    "layout": "「一 scope 一文件」的机器判据——调度器只许调度",
    "layout_parity": "§二.1 的布局表 ↔ 每套模板，双向对账",
    "ledger": "「双向对账」两侧必须各点名一个载体，否则它就是派生品自比较",
    "links": "外部链接（默认跳过）与相对链接 + 锚点（离线强断言）",
    "loop": "四段纪律的每一节都必须留下可判的痕（感知 / 规划 / 行动 / 反思）",
    "sections": "§二.5 那两个阈值的硬上限，分两档",
    "struct": "skill 根目录是否符合标准形状",
    "terms": "规范用语「scope 分域」，不是分级",
    "tplpath": "模板文档点名的路径必须在该模板内可解析（模板即目标仓库的根）",
    "version": "规则集版本日期的保质期",
    "xref": "内部交叉引用 `§六`、`§七.5` 指向存在的章节/条目",
    "xrefdoc": "references/ 文件里的跨文件 §X.Y 引用（断言坑 #12：裸编号跨文件）",
}

REFLECT = {
    "baseline": (
        "BASE001", "BASE002", "BASE003", "BASE004",
    ),
    "bash": ("BASH001", "BASH002"),
    "budget": ("BUDGET001", "BUDGET002"),
    "codeindex": ("CODEINDEX001",),
    "deliverable": ("DLV001",),
    "docclaim": ("DOC001",),
    "docphantom": ("DOC002",),
    "frontmatter": (
        "FM001", "FM002", "FM003", "FM004",
        "FM005", "FM006", "FM007", "FM008",
        "FM009",
    ),
    "host": ("HOST001", "HOST002"),
    "layout": ("LAYOUT001",),
    "layout_parity": ("LP001", "LP002", "LP003"),
    "ledger": ("DUAL001",),
    "links": (
        "LINK001", "LINK002", "LINK003", "LINK004",
    ),
    "loop": (
        "LOOP001", "LOOP002", "LOOP003", "LOOP004",
    ),
    "sections": ("SECT001", "SECT002"),
    "struct": ("STRUCT001", "STRUCT002", "STRUCT003"),
    "terms": ("SCOPE001",),
    "tplpath": ("TP001",),
    "version": ("VER001",),
    "xref": ("XREF001", "XREF002"),
    "xrefdoc": ("XREFDOC001", "XREFDOC002"),
}


def plan(name):
    """判定范围；未登记返回空——`loop` 会把空当 ERROR，不当通过。"""
    return [PLAN[name]] if name in PLAN else []


def reflect(name):
    """它能报的 code；空即「没有可验证的面」。"""
    return list(REFLECT.get(name, ()))
