---
name: bad-host-loading
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code HOST001 (the host-loading probe records neither where the verdict goes nor what to do when the host ignores nested entry files).
---

# Fixture: bad-host-loading

Single defect: the probe section below asks for a test but never says where the verdict is recorded, nor what to do when the host does not load nested entry files.

### 宿主加载实测

- 在仓库根建 `probe/AGENTS.md` 并写一行唯一标记，从仓库根启动宿主，让它读 `probe/` 下的文件。
- 观察标记是否进入上下文。
