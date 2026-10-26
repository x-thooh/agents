# DeepSeek 页内抓取脚本（browser-use → evaluate_script）

全部在 `https://chat.deepseek.com/` 已登录页里跑。单次调用 **15 秒超时**，
超时的脚本仍会在页内继续执行，所以按「可续跑」设计：进度存在 `window.__DS`，
每次调用只干活 10 秒然后返回计数，反复调用直到补齐。

## 0. 探针：登录态 + token + 接口连通

```js
async () => {
  const raw = localStorage.getItem('userToken');           // 是 JSON 串，不是裸 token
  const tok = raw ? JSON.parse(raw).value : null;          // 整串当 token 用会 INVALID_TOKEN
  const r = await fetch('/api/v0/chat_session/fetch_page?count=3', { headers: { 'Authorization': 'Bearer ' + tok } });
  const t = await r.text();                                 // 必须是 GET：POST 返回 405
  return { status: r.status, tokenLen: tok ? tok.length : 0, head: t.slice(0, 300) };
}
```

期望：`status: 200`，`head` 里出现 `"code":0` 与 `chat_sessions`。

## 1. 会话清单：分页拉全（只跑一次，结果留在页内）

`count` 上限 100，传 200 报 `illegal count`。侧边栏只渲染 100 条，**别拿可见数当总数**。
游标是对象式查询参数：`lte_cursor.pinned=false&lte_cursor.updated_at=<浮点>`，
用浮点原值（取整会跳过边界那条），返回含首条重复，靠 id 去重。

```js
async () => {
  const tok = JSON.parse(localStorage.getItem('userToken')).value;
  const h = { 'Authorization': 'Bearer ' + tok };
  const all = [], seen = new Set();
  let cursor = null, pages = 0;
  while (pages < 40) {
    let url = '/api/v0/chat_session/fetch_page?count=100&lte_cursor.pinned=false';
    if (cursor !== null) url += '&lte_cursor.updated_at=' + cursor;
    const j = await (await fetch(url, { headers: h })).json();
    const bd = j.data && j.data.biz_data;
    if (!bd) break;
    let added = 0;
    for (const s of bd.chat_sessions) if (!seen.has(s.id)) { seen.add(s.id); all.push(s); added++; }
    pages++;
    if (!bd.has_more || !bd.chat_sessions.length || added === 0) break;
    cursor = bd.chat_sessions[bd.chat_sessions.length - 1].updated_at;
  }
  window.__DS = { sessions: all, data: {} };
  return { total: all.length, pages };
}
```

## 2. 逐会话抓正文：断点续跑 + 限流退避

正文不在 `message.content`，在 `message.fragments[].content`，类型
`REQUEST`（提问）/`RESPONSE`/`TEMPLATE_RESPONSE`（回答）/`THINK`（深度思考）/
`SEARCH`/`TOOL_SEARCH`/`TOOL_OPEN`/`TOOL_FIND`/`TIP`（检索与提示）/`FILE`。

**必须校验 `code === 0` 再写入**：限流时 `code:40029 TOO_MANY_REQUESTS`、`data:null`，
不校验就会把会话存成空数组，事后看起来像「这个会话没内容」。

```js
async () => {
  const tok = JSON.parse(localStorage.getItem('userToken')).value;
  const h = { 'Authorization': 'Bearer ' + tok };
  const S = window.__DS.sessions;
  const need = S.filter(s => { const r = window.__DS.data[s.id]; return !(r && r.messages.length); });
  const t0 = performance.now();
  let i = 0, ok = 0, limited = 0;
  const worker = async () => {
    while (i < need.length && performance.now() - t0 < 10000) {
      const s = need[i++];
      let j;
      try { j = await (await fetch('/api/v0/chat/history_messages?chat_session_id=' + s.id, { headers: h })).json(); }
      catch (e) { continue; }
      if (!j || j.code !== 0) {                       // 40029 等，退避后交给下一轮
        if (j && j.code === 40029) { limited++; await new Promise(x => setTimeout(x, 2000)); }
        continue;
      }
      const msgs = (j.data.biz_data && j.data.biz_data.chat_messages) || [];
      window.__DS.data[s.id] = {
        id: s.id, title: s.title, updated_at: s.updated_at,
        messages: msgs.map(m => ({ role: m.role, ts: m.inserted_at,
          frags: (m.fragments || []).map(f => ({ type: f.type, text: f.content })) }))
      };
      ok++;
      await new Promise(x => setTimeout(x, 60));
    }
  };
  await Promise.all([worker(), worker(), worker()]);
  const good = S.filter(s => window.__DS.data[s.id] && window.__DS.data[s.id].messages.length).length;
  return { ok, limited, good, total: S.length, remain: S.length - good };
}
```

3 并发 × 60ms 约 150 条/10 秒；1000 条会话调 7～8 次。`remain` 归 0 才算抓完。

## 3. 合并落盘：Blob 下载，别把正文回传对话

十几 MB 正文走 tool 返回会撑爆上下文。页内序列化后 `<a download>` 落 `~/Downloads`，
自动化 Chrome 不弹保存框，几秒后文件即出现。

```js
() => {
  const S = window.__DS.sessions;
  const merged = S.map(s => window.__DS.data[s.id]).filter(r => r && r.messages.length);
  const text = JSON.stringify({ exported_at: Math.floor(Date.now() / 1000), source: 'chat.deepseek.com', count: merged.length, sessions: merged });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  a.download = 'ds-export-merged.json';
  document.body.appendChild(a); a.click(); a.remove();
  return { sessions: merged.length, bytes: new Blob([text]).size };
}
```

## 验收口径

- `sessions` == 接口分页到底的总数（不是侧边栏的 100）
- 空会话数 == 0；`max(messages)` 出现在 90+ 也属正常，不是截断
- 抽查一个多轮会话：笔记里 `## 第 N 轮 · 我` 与 `## 第 N 轮 · DeepSeek` 数量相等
