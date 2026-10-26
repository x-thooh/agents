---
name: ai-chat-import
description: Export the full chat history of a logged-in AI chat account through its own web API and write it verbatim into the Obsidian/PARA vault's AI-session archive (04_归档/02_AI会话，不消化只保真), one note per conversation. Verified on DeepSeek (chat.deepseek.com) and Gemini (gemini.google.com, Google batchexecute API); carries a probing recipe for a third platform. Use when the operator says 采集/导入/整理 聊天历史、会话记录、把聊天沉淀到归档, names a chat platform to export, or wants to re-run or extend a previous import. Requires a browser already logged into that platform and an in-page JS execution tool (browser-use evaluate_script); Python 3 for the converter.
metadata:
  requires: browser-use MCP（evaluate_script）+ python3；目标 vault 可写，最好有 make check-* 目标
---

# AI 聊天历史导入归档（02_AI会话）

把账号里的全部会话抓成一份 JSON，再原文保真地落成**归档笔记**（`04_归档（Archive）/02_AI会话/<平台>/YYYY-MM/`）。**不逐条点 UI**：
上千条会话点 UI 要几小时且会漏，走接口几分钟抓完，还带精确时间戳。

写入落点是**会话档案**，不是收件箱：会话是已发生的记录，不消化、只保真，提炼由提炼任务另起（T-20261023-sessions-distill 模式）。
2026-10-23 之前的导入曾直写收件箱，后整体移入归档；再导一律直写归档。

已跑通：**DeepSeek**（[references/deepseek-snippets.md](references/deepseek-snippets.md)）、
**Gemini**（[references/gemini-snippets.md](references/gemini-snippets.md)）。

## 前提

1. 浏览器已登录目标平台，页面处于选中状态（`list_pages` 确认）。
   **未登录不要代填密码**：Google 这类会跳 `accounts.google.com`，停下来请用户手动登录，再轮询页面状态。
2. 有页内 JS 执行能力。单次 `evaluate_script` **15 秒超时**，超时的脚本仍会在页内跑完，
   所以抓取一律按「进度与游标存 `window` 变量 + 每次干 10 秒 + 反复调用到 remain=0」设计。
3. 写入前先确认归档路径与命名规范（`04_归档（Archive）/02_AI会话/AGENTS.md`；layout=archive 时脚本自动按 `<平台>/YYYY-MM/YYYY-MM-DD - 标题.md` 落笔）。

## 跨平台的七条硬规则

| # | 规则 | 违反的后果 |
| --- | --- | --- |
| 1 | 规模以接口分页为准，UI 列表只是渲染窗口 | 把可见条数当总数，能差 10 倍 |
| 2 | 每个响应先校验「业务真的成功」再落数据 | 限流/错误响应也是 HTTP 200，会存成合法的空会话 |
| 3 | 游标与进度存 `window`，续跑不重置 | 每次调用都从第 1 页重来，翻页永远翻不完 |
| 4 | 默认参数往往是**截断值**（每页条数上限、轮数上限） | 长会话被静默截断，事后看不出少了几轮 |
| 5 | 正文常在 parts/fragments 里，不在单个 `content` 字段 | 只读 `content` 会得到 0 字符 |
| 6 | 大块数据用页内 Blob 下载落盘，不进对话上下文 | 十几 MB 正文挤爆上下文 |
| 7 | 落笔前把规模报给用户，重跑要幂等 | 大批写入不可逆；重复导入长出一堆 `（2）` 副本 |

两平台在方法、线格式、游标位置上几乎相反（POST vs GET、字节长度分块 vs 普通 JSON），
对照表见下，细节各看各的参考文件——**不要把一边的结论套到另一边**。

| 维度 | DeepSeek | Gemini |
| --- | --- | --- |
| 方法 | GET | POST + `f.req`，xsrf 取 `window.WIZ_global_data.SNlM0e` |
| 响应 | 普通 JSON | `)]}'` + 多段 `<UTF-8 字节长度>\n<JSON>`，数据还要二次 parse |
| 列表 | `chat_session/fetch_page`，`lte_cursor.updated_at` 游标，每页 ≤100 | `MaZiqc`，每页硬上限 100，游标在返回第 2 个元素 |
| 正文 | `chat/history_messages` 一次给全 | `hNvQHb`，第 2 参数是轮数上限（UI 传 10，要给 1000），轮次倒序返回 |
| 失败信号 | `code:40029` 限流，`data:null` | 缺 `wrb.fr` 行或 payload 解析失败 |

## 流程

```
- [ ] 1 探针：登录态、token 可见、试打一个接口
- [ ] 2 清单：分页拉全，拿到会话总数（向用户报数，别用 UI 条数）
- [ ] 3 正文：断点续跑抓取，直到 remain == 0
- [ ] 4 落盘：Blob 下载 JSON，校验空会话 == 0
- [ ] 5 报规模：数量级与「思考/检索折叠还是丢弃」由用户拍板
- [ ] 6 查重：库里既无同源笔记（source 反查），也无同名主题
- [ ] 7 转换：先 dry-run 看样例，再 --write
- [ ] 8 校验：make check-links（归档不参与 check-single / check-inbox）；补决策记录
```

## 转换

脚本与平台无关：页内先归一化成
`{id, title, updated_at, messages:[{role, ts, frags:[{type, text}]}]}`
（`type` 用 `REQUEST` / `RESPONSE` / `THINK` / `TIP`，检索类信息归 `TIP` 会自动折叠）。

```bash
python3 scripts/chat_to_notes.py --json <导出.json> \
  --inbox "<vault>/04_归档（Archive）/02_AI会话" \
  --account Gemini --tag Gemini --source-base "https://gemini.google.com/app/"   # dry-run
  # 加 --write 落盘；DeepSeek 用 --account DeepSeek --source-base "https://chat.deepseek.com/a/chat/s/"
```

`--layout` 默认 `archive`：`<root>/<平台>/YYYY-MM/YYYY-MM-DD - 标题.md`，frontmatter `status: archived`。
历史值 `--layout inbox`（`<root>/YYYY-MM/YYYY-MM-DD 标题.md`、`status: inbox`）只留给剪藏类导入，会话不要再用。

内置规则（细节读脚本）：layout=archive 时文件名 `YYYY-MM-DD - 标题.md`、`<平台>/YYYY-MM/` 分月；标题折叠空白、
`| : ? * / \ " < > #` 转全角、超 60 字截断、同日同名加 `（2）`；frontmatter
（`source` 用会话永久链接，浏览器可直开）；一轮一节且**连续多条 assistant 合并进同一轮**；
未闭合 ``` 补齐；`[[…]]` 只在解析不到目标时转义（库根从 `--inbox` 向上找 `.obsidian` 自动判定），真实附件嵌入保持原样；
按 frontmatter 的 source id 找回既有笔记**原地覆盖**，重跑不产生副本。

## 换第三个平台

`performance.getEntriesByType('resource')` 只能看到 rpcid/路径，看不出哪个是列表——
要挂拦截器：`window.fetch` 与 `XMLHttpRequest.prototype` **两层都挂**（Angular 走 XHR），
并在 `document.readyState === 'interactive'` 时就装上；请求体遇到 `Request` 实例要
`await input.clone().text()`；命中缓存不重发，得重载或换改变参数的触发点。
拿到 rpcid 后逐个试参数，用「本页新 id 数」验证猜法，比读混淆 JS 快。
完整可抄版本见 [references/gemini-snippets.md](references/gemini-snippets.md) 末节。

## 别做

- 别用 UI 逐条点开抓正文；别代填密码。
- 别把正文回传对话上下文（用 Blob 下载落盘）。
- 别把导入的原文当笔记改写：会话档案**不消化只保真**，提炼由提炼任务另起、写入领域/资源。
- 已入档的笔记一个字都不动（含 frontmatter）：历史快照保持 `status: inbox` 是刻意的原始痕迹，新导入才用 `archived`。
- 别静默略过校验：`make check` 的既有 ERROR（如插件生成的目录）要如实说明。
- 交付时说明抓取时刻——抓的是**快照**，之后新聊的会话不在这批里。
