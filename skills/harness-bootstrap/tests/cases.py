"""期望表：每个 fixture 该报哪个 code。唯一的第二份，不抄到别处。

为什么单独一个文件：这张表是**数据**，`fixtures.py` 是**引擎**（跑 audit、比对、
三道覆盖闸）。混在一起时文件长到 238 行，越过了本 skill 自己定的 200 行上限——
而当时的 `BUDGET001` 只扫 `scripts/`，所以这条账一直没人发现。拆开是两件事：
改期望不该动引擎，改闸不该动数据。

期望必须精确到 code 集合，不是「有 ERROR 就算过」（`self-gates.md` 的判据）：
「某条规则报了」和「这条规则报的」是两件事，后者才能证明断言指向正确。

反方向也要有样本（`DOC002`）：既测「源码有、文档漏」也测「文档写、源码没有」。
一道闸只朝一个方向用力时，另一个方向的漂移是全绿的。
"""

CASES = (
    # 正对照：0 条发现。它一红，下面所有「符合期望」都不作数。
    ("ok-minimal", set(), ()),
    # 每个 scope 至少一条
    ("bad-frontmatter", {"FM004"}, ()),
    ("bad-bash-block", {"BASH001"}, ()),
    # --only 过滤：同一份坏样本，只跑 links 时不该报 FM008（证明选择真的生效）
    ("bad-description", set(), ("--only", "links")),
    ("bad-description", {"FM008"}, ()),
    # 产物清单也是流程摘要：只认箭头/序号时，这类写法一路绿灯（真实自欺）
    ("bad-description-deliverable", {"FM008"}, ()),
    ("bad-description-trigger", {"FM009"}, ()),
    ("bad-baseline-rule", {"BASE001"}, ()),
    ("bad-zero-baseline", {"BASE003"}, ()),
    ("bad-expiry-decor", {"BASE004"}, ()),
    ("bad-host-loading", {"HOST001"}, ()),
    ("bad-dual-ledger", {"DUAL001"}, ()),
    # 对账的磁盘侧必须出现在布局表里；只写一个不存在的目录不算对账
    ("bad-dual-disk", {"DUAL001"}, ()),
    ("bad-scope-grading", {"SCOPE001"}, ()),
    ("bad-version-ungated", {"VER001"}, ()),
    ("bad-xref", {"XREF001"}, ()),
    ("bad-xref-table", {"XREF002"}, ()),
    ("bad-relative-link", {"LINK004"}, ()),
    ("bad-xref-ext", {"XREFDOC002"}, ()),
    # 标准目录形状（本轮新增）
    ("bad-struct-extra", {"STRUCT001"}, ()),
    ("bad-struct-singular", {"STRUCT001"}, ()),
    ("bad-struct-refs-content", {"STRUCT002"}, ()),
    # 外置内容没人链：文件在、内容对，但谁也读不到（密度改造的副作用）
    ("bad-struct-orphan-ref", {"STRUCT003"}, ()),
    # 单节 100 行上限：超了要拆，不是提限
    ("bad-section-long", {"SECT001"}, ()),
    # 参考材料单文件 100 行上限：同一条规则的另一半
    ("bad-reference-long", {"SECT002"}, ()),
    # 两档：撞 80 就 WARN（准备拆），超 100 才 ERROR（必须拆）。
    # 上面两条是 ERROR 档；这两条专验 80 那一档真会触发——把 WARN 分支删掉它们就红。
    ("bad-section-warn", {"SECT001"}, ()),
    ("bad-reference-warn", {"SECT002"}, ()),
    # 布局表 ↔ 模板对账：表说了模板没建，必须报 LP001（两套模板里故意只建一套的后半）
    ("bad-layout-parity", {"LP001"}, ()),
    # 覆盖闸自身的盲区：两字母前缀曾整块看不见，这 8 个是把洞堵上后的补齐。
    # FM001–FM007 与 LP002/LP003 此前从无样本；其中 LP002 藏在瞎区里，所以缺口一直看不见。
    ("bad-no-frontmatter", {"FM001"}, ()),
    ("bad-missing-name", {"FM002"}, ()),
    ("bad-name-shape", {"FM003"}, ()),
    ("bad-empty-description", {"FM005"}, ()),
    ("bad-long-description", {"FM006"}, ()),
    ("bad-extra-field", {"FM007"}, ()),
    ("bad-layout-extra", {"LP002"}, ()),
    ("bad-layout-no-table", {"LP003"}, ()),
    # 派生清单必须与源码逐字节一致；样本自带一份故意过时的 code-index.md
    ("bad-stale-code-index", {"CODEINDEX001"}, ()),
    # 文档声称的载体必须覆盖代码里每个 code；样本的文档故意漏了一个
    ("bad-doc-missing-code", {"DOC001"}, ()),
    # 反方向：文档指向源码里已被删掉的 code（幻影），只守 DOC001 时全绿
    ("bad-doc-phantom-code", {"DOC002"}, ()),
    # 幻影的另一个方向：正文（SKILL.md）替不存在的 code 背书
    ("bad-skill-phantom-code", {"DOC002"}, ()),
    # 幻影的第三个方向：正文点名的 **scope 模块** 不存在。
    # 只补 code 方向时这里全绿——而「拿别人家代码审谁守哪条」正是靠 scope 名指路的（v2 评审 §4-3）。
    ("bad-phantom-scope", {"DOC002"}, ()),
    # 四段纪律：写了其中一节就得四节齐，且每节必须有「机器判：」/「人判：」分列
    ("bad-loop-sense", {"LOOP001"}, ()),
    ("bad-loop-plan", {"LOOP002"}, ()),
    ("bad-loop-act", {"LOOP003"}, ()),
    ("bad-loop-reflect", {"LOOP004"}, ()),
    # 钩子对账：scope 有可报的 code，但 hooks.py 的 REFLECT 留空
    ("bad-loop-hook", {"LOOP004"}, ()),
    # 锚点断链：文件在、锚点错（只判文件的门禁会放它过去）
    ("bad-anchor-link", {"LINK004"}, ()),
    # 交付物孤儿：文件在、内容对，但文档一次都没点名（「有了却没人说」）
    ("bad-orphan-deliverable", {"DLV001"}, ()),
    # 反方向只在模板侧判得动（模板即目标仓库的根）：文档点名的路径在模板里不存在。
    # 只跑 tplpath——templates/ 一出现，布局对账会按自己的规矩报 LP003，混进来就证明不了「恰好是它」。
    ("bad-template-phantom-path", {"TP001"}, ("--only", "tplpath")),
    # 体量预算两档：两档都得真会响，否则「准备拆」只是句好听话
    ("bad-budget-warn", {"BUDGET001"}, ()),
    ("bad-budget-error", {"BUDGET001"}, ()),
    # 扫描面必须含 tests/：只扫 scripts/ 时，tests/ 下的胖文件全绿（v2 评审 §4-4）
    ("bad-budget-tests", {"BUDGET001"}, ()),
    # 总量额度：每节都合规、总量翻倍时也必须响——单节额度管不了加载成本
    ("bad-skill-total", {"BUDGET002"}, ()),
    # code 级反向测试：下列每一个都曾从无 fixture（scope 级有机一条，code 级漏网），
    # 其中 LINK002/XREFDOC001 是 ERROR 级——一个从不执行的 ERROR 比 WARN 更坏。
    # LINK002/LINK003 靠 --link-status 把「取状态码」固定住，不靠公网。
    ("bad-baseline-warn", {"BASE002"}, ()),
    ("bad-bash-syntax", {"BASH002"}, ()),
    ("bad-host-no-section", {"HOST002"}, ()),
    ("bad-link-unchecked", {"LINK001"}, ()),
    ("bad-link-dead", {"LINK002"}, ("--check-links", "--link-status", "https://example.com/dead-404=404")),
    ("bad-link-unreachable", {"LINK003"}, ("--check-links", "--link-status", "https://example.com/unreachable=ERR")),
    ("bad-xrefdoc-missing", {"XREFDOC001"}, ()),
    # 调度器体征：换一个「长成实现」的调度器去审合规样本
    ("ok-minimal", {"LAYOUT001"}, ("--dispatch", "tests/fixtures/bad-inline-scope/scripts/audit.py")),
)
