---
name: bad-xref-ext
description: 用于反向测试：reference/ 里的跨文件引用指向不存在的条目，该被 xrefdoc 抓住。
license: MIT
---

# bad-xref-ext

反向样本。它测的是跨文件裸编号：`reference/notes.md` 引了 §一 里并不存在的第 5 条，而 §一 只有两条——SKILL.md 内部的同类错误 xref 早就管了，这份样本证明跨到 reference/ 的另一半也有人管。

## 用法

跑一次自身门禁（预期且仅预期 XREFDOC002）：

```bash
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref-ext
```

## 基线机制

- 基线按条数记，逐条输出，不许只报「基线内 N 条」。
- 零基线：首版 baseline 必须为空，存量问题要么修，要么进 accepted 白名单。
- accepted 每条带理由 + 负责人 + 复查日期；accepted 与基线总数只减不增，新增即 ERROR。
- 保质期：复查日期过期未续或未移除条目的，verify 报 ERROR。

## 一、门禁

1. 门禁跑通且退出码为 0。
2. 全部引用可解析到存在的章节与条目。
