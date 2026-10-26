# Gemini（gemini.google.com）抓取片段

接口是 Google 内部的 `batchexecute`，与 DeepSeek 完全不同。以下结论实测于 2026-10，
账号 563 条会话、7315 条消息，8 并发无限流。

## 认证与调用骨架

xsrf token 在页面全局变量里，cookie 由浏览器自带：

```js
const at = window.WIZ_global_data.SNlM0e;                    // 'AIa…:1792…'
const res = performance.getEntriesByType('resource').map(e => e.name).filter(u => u.includes('batchexecute'));
const bl = res[0].match(/bl=([^&]+)/)[1];                    // 构建号，会随版本变
const sid = res[0].match(/f\.sid=([^&]+)/)[1];
const call = async (rpc, inner, sp) => {
  const payload = JSON.stringify([[[rpc, JSON.stringify(inner), null, 'generic']]]);
  const url = '/_/BardChatUi/data/batchexecute?rpcids=' + rpc + '&source-path=' + encodeURIComponent(sp || '/app') +
              '&bl=' + bl + '&f.sid=' + sid + '&hl=zh-CN&_reqid=' + Math.floor(Math.random() * 1e6) + '&rt=c';
  const r = await fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'content-type': 'application/x-www-form-urlencoded;charset=UTF-8', 'x-same-domain': '1' },
    body: 'f.req=' + encodeURIComponent(payload) + '&at=' + encodeURIComponent(at) + '&'
  });
  const t = await r.text();
  return { status: r.status, bytes: t.length, text: t };
};
```

`POST` 才有 body，`GET` 一律失败（与 DeepSeek 相反）。

## 线格式解析：两个必踩的坑

响应是 `)]}'` + 多段 `<长度>\n<JSON>`。

1. **长度是 UTF-8 字节数**，中文 3 字节/字。按 JS 字符串下标切片会越界，`JSON.parse` 抛错。
2. 每段是「行的数组」，`wrb.fr` 在里层；真正的数据在 `row[2]`，且**它还是个 JSON 字符串**，要二次 `parse`。

按行切最省事（JSON 体内不含裸换行）：

```js
window.__parse = (t) => String(t).split('\n')
  .filter(l => l.charAt(0) === '[')
  .map(l => { try { return JSON.parse(l); } catch (e) { return null; } })
  .filter(Boolean);

window.__payload = (rows, rpc) => {
  const flat = [];
  rows.forEach(r => { if (Array.isArray(r)) (r[0] === 'wrb.fr' ? [r] : r).forEach(x => { if (Array.isArray(x) && x[0] === 'wrb.fr') flat.push(x); }); });
  for (const r of flat) if (r[1] === rpc && typeof r[2] === 'string') { try { return JSON.parse(r[2]); } catch (e) { return null; } }
  return null;
};
```

## 会话清单：`MaZiqc`

```js
const tail = [null, null, 1, null, null, null, null, null, null, null, 1];
const d = window.__payload(window.__parse((await call('MaZiqc', [100, token, tail])).text), 'MaZiqc');
```

- 第 1 个参数是每页条数，**上限 100**（传 1000 仍只回 100）。
- 第 2 个参数是游标 token：第一页传 `null`，之后传上一页返回的 `d[1]`；`d[1]` 为 null 即到底。
- 会话列表在 `d` 里第一个「长度 > 5 的数组」元素；条目形状 `[c_id, title, …, [sec, nanos], …]`，时间戳在 `it[5][0]`。
- 翻页游标失效或 UI 侧不可见时，别用「本页有重复」当停止条件——续跑循环要把 token 存到 `window`，否则每次调用都从第 1 页重来。

## 会话正文：`hNvQHb`

```js
const inner = ['c_' + id, 1000, null, 1, [1], [4], null, 1];   // 第二个参数是轮数上限
const d = window.__payload(window.__parse((await call('hNvQHb', inner, '/app/' + id)).text), 'hNvQHb');
```

- **第二个参数是轮数上限**，UI 默认传 `10`，长会话会被静默截断；给 `1000`。返回 `d[1]` 非空说明还没到底。
- `d[0]` 是轮次数组，**倒序**返回，按 `t[4][0]` 升序排回。
- 每轮 `t`：`t[0]` = `[c_id, r_id]`；`t[2][0]` = 提问 parts；`t[3][0][i][1]` = 回答文本 parts（字符串数组）；`t[4]` = `[秒, 纳秒]`。
- `t[3][12]` 是答案的分块副本（逐块文本 + 代码块），与 `t[3][0]` 重复，取正文时**跳过下标 0 和 12**，剩下的长字符串就是检索/引征信息（搜索关键词、检索模型名），适合折进 `<details>`。
- 检索信息里夹着 `https://www.gstatic.com/images/branding/...` 图标 URL，落盘前正则清掉。

## 归一化后复用转换脚本

抓完在页内映射成与 DeepSeek 相同的形状，`chat_to_notes.py` 一行不用改：

```text
{ id, title, updated_at, messages: [{ role: 'USER'|'ASSISTANT', ts, frags: [{ type: 'REQUEST'|'RESPONSE'|'TIP', text }] }] }
```

`--account Gemini --tag Gemini --source-base "https://gemini.google.com/app/"` 即可，
生成的 `source` 正是网页里能直接打开的会话链接。

## 接口探测方法（换平台时照做）

1. 登录态先探针确认：Google 会跳 `accounts.google.com`，此时**请用户手动登录**，绝不代填密码。
2. rpcid 列表从 `performance.getEntriesByType('resource')` 的 `?rpcids=` 参数拿，但**看不出哪个是列表**——要靠拦截器。
3. 拦截器必须**同时挂 `window.fetch` 和 `XMLHttpRequest.prototype`**：Angular 的 HttpClient 走 XHR，混着用会漏。
4. 要在 `document.readyState === 'interactive'` 时就装上：重载页面后 Angular bootstrap 期间发的请求抓不到，就只能看到「列表凭空出现」。
5. 请求体在 `input instanceof Request` 时要 `await input.clone().text()`，同步读拿不到。
6. 命中缓存就不会重发（同一 SPA 内来回点没用）：重载、或换一个会改变参数的触发点（切页签、改筛选）。
7. 确认 rpcid 后，把它参数逐个试探（页大小、游标位置、顺序），拿「本页新 id 数」验证猜法，比读混淆 JS 快得多。
