---
name: goland-bookmarks
description: 读取 JetBrains IDE（GoLand/IDEA/PyCharm 等 2026.x）的书签（Bookmarks），列出书签位置、分组、备注与源码上下文。当用户要求"读取 GoLand 书签/我的书签有哪些/列出书签/按书签继续工作/校验书签是否失效"等时触发。全局脚本：~/.pi/agent/skills/goland-bookmarks/scripts/goland-bookmarks.sh，参数 [--project DIR] [--ide NAME] [-g GROUP] [-f table|plain|json] [-c N] [--check] [--flush]。
---

# goland-bookmarks（读取 IDE 书签）

IDE 的 MCP 接口**没有**书签工具（`goland__execute_tool` 的工具清单里无 bookmark），书签只能读落盘文件。本 skill 把「找到目标项目那份 workspace 文件 → 解析书签」这一串固定下来，任意项目可用。

## 使用方法

```sh
S=~/.pi/agent/skills/goland-bookmarks/scripts/goland-bookmarks.sh

$S                          # 当前项目全部书签（表格；解析证据在 stderr）
$S -p /path/to/other/repo   # 指定项目
$S -f plain                 # 只输出 path:line，可直接管道
$S -f json                  # 结构化输出（group/path/absPath/line/description/lineText）
$S -g marketing             # 只看某个书签组
$S -c 3                     # 每条书签附 3 行源码上下文
$S --check                  # 校验文件存在与行号；失效则退出码 3
$S --flush                  # 先切走窗口焦点触发 IDE 落盘，再读取（macOS）
```

项目默认取 `git rev-parse --show-toplevel`，非 git 目录取当前目录。多 IDE/多版本时按配置目录名倒序自动找，`--ide GoLand2026.2` 可指定。

## 关键事实（JetBrains 2026.x）

- 书签**不再存**在项目 `.idea/workspace.xml`，而是存进**产品级** workspace 文件：
  `<IDE 配置目录>/workspace/<hash>.xml` 的 `<component name="BookmarksManager">`。
  - macOS：`~/Library/Application Support/JetBrains/<产品版本>/workspace/`
  - Linux：`~/.config/JetBrains/<产品版本>/workspace/`
  - 更老的 IDE 版本仍在 `.idea/workspace.xml`；2026.2 实测属新布局。
- 项目 → workspace 文件的映射无法由路径推导（文件名是 hash）。脚本从 `idea.log` 的
  `Project store initialized with paths: [... $PROJECT_CONFIG_DIR$, value=<项目>/.idea ... $PRODUCT_WORKSPACE_FILE$, value=<xml>]`
  取最后一处精确命中；日志不可用时回退为「书签文件真实存在于该项目」打分。
- **落盘是延迟的**：新增/修改书签后文件 mtime 不变，需窗口失焦或 IDE 退出才写。
  文件里找不到 `BookmarksManager` 时脚本退出码 4 并给出提示；用 `--flush` 或手动切一次焦点再跑。
- 书签按组（`GroupState`）组织，组名默认是项目名；`description` 是用户重命名的备注，
  `lineText` 是加书签那一刻的行快照（代码改动后会与当前内容不一致，`--check` 以当前文件为准）。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 正常输出 |
| 2 | 参数错误（如 `--context` 与 `-f plain` 同时使用、路径不存在） |
| 3 | `--check` 发现失效书签（文件不存在 / 行号超出 EOF） |
| 4 | 找不到书签：未匹配到该项目、IDE 未落盘、或 `--strict` 下组内为空 |

stdout 保持可管道（表格模式下表头/证据写到 stderr）；`-v` 打印命中的日志行与候选文件打分。

## 依赖与边界

- 需要 `python3`（XML 解析）；脚本是零第三方依赖的 bash 包装。
- 只读：不修改 IDE 状态；`--flush` 唯一副作用是把焦点切到 Finder。
- 外部书签（`http(s)://` 等非项目文件）标记 `EXTERNAL`，`--check` 跳过校验。
