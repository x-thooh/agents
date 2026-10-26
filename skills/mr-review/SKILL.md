---
name: mr-review
metadata:
  version: 2.3.0
description: 审查代码合并请求（MR）。当用户要求"审查分支/审查 MR/review MR/跑 review-mr"等时触发。优先用 scripts/review-mr.sh 跑流水线，并在审查前提取 MR 元信息（远程分支、当前分支、提交、作者、文件统计）。MR 目标分支优先从提交历史自动推断。构建阶段联动项目 AGENTS.md：make all 负责生成依赖，make build 负责检查编译。流水线含 diff 安全检查（Phase 4.5 / scan-security.sh，对应状态机 CHECKING_SECURITY）。审查后可叠加云效 Codeup MCP 能力补充平台信息、校验 MR target，可选同步审查结论到 Codeup 评论，并可选发送钉钉群通知（scripts/send-dingtalk.sh）；钉钉 @ 对象默认为 **MR 发起人**，由 scripts/get-mr-author.sh 解析。
---

# MR Review

## 触发场景

用户要求审查某个分支/MR（如"审查 feature/xxx"、"review 一下这个 MR"），或要求跑 `review-mr.sh`。

## 前置：读取项目约定

审查前先读取项目根目录的 `AGENTS.md`，确认以下约定：

- 构建命令：`make all` 与 `make build NAME=xxx` 的职责区分
- 服务目录结构：通常是 `app/{name}/service/`
- 代码生成范围：`proto` / `wire` / 其他生成文件是否 gitignored
- 环境变量：`GOPRIVATE` / `GOPROXY` / repo-local `GOPATH` 是否需要显式导出
- 测试命令：`go test ./...` 是否覆盖核心逻辑

如果 `AGENTS.md` 未定义构建命令，按通用 Go 项目处理：

- `make all` = 清理并重新生成代码（wire/proto/config 等）
- `make build NAME=xxx` = 生成代码后执行 `go build`，验证项目可编译
- `NAME=` 从 repo root 传入；进入 `app/{name}/service/` 后可省略

## 入口：仅给 MR 链接时

用户可能只发 Codeup MR 链接（如 `https://codeup.aliyun.com/lsxd/ymt/marketing/change/16`）而不给分支名。此时先走云效 MCP 拿 MR 元信息，再跑本地流水线：

1. `get_current_organization_info` → 取 `lastOrganization`
2. `list_repositories`（`organizationId`）→ 按仓库名匹配，取 `id`
3. `get_change_request`（`repositoryId` + `localId`，localId 取链接末尾数字）→ 拿 `sourceBranch` / `targetBranch` / `status` / `ahead` / `behind` / `reviewers` / `unResolvedCommentCount` / `allRequirementsPass` / `checkList`
4. 若 `status != UNDER_REVIEW`（MERGED/CLOSED）→ 停止审查并提示
5. 用 `sourceBranch` 跑 `get-mr-info.sh`（`--base origin/<targetBranch>`）校验后进入流水线

顺带预判合并阻塞（见 Phase 7.5）：`allRequirementsPass=false` 时查看 `checkList.requirementRuleItems`，`REVIEWER_APPROVED_CHECK` / `COMMENTS_CHECK` 为 false 意味着合入前需评审通过 + 评论全部解决。

MR 元信息展示补充：

- Codeup MR: #16 (<https://codeup.aliyun.com/lsxd/ymt/marketing/change/16>)
- 状态：UNDER_REVIEW
- 目标分支校验：✅ 一致 / ⚠️ 不一致

## 获取 MR 元信息

在跑流水线前，先用 `scripts/get-mr-info.sh` 读取目标 MR 的基础信息，避免先跑 3-6 分钟流水线才发现参数错误。

```bash
# 方式 A：只给分支名，自动补 remote/ 前缀并推断 base
bash .pi/skills/mr-review/scripts/get-mr-info.sh feature/lr/v4.3.1

# 方式 B：显式指定 base（覆盖自动推断）
bash .pi/skills/mr-review/scripts/get-mr-info.sh feature/lr/v4.3.1 --base origin/feature/v4.3.1

# 方式 C：指定非默认 remote
bash .pi/skills/mr-review/scripts/get-mr-info.sh feature/lr/v4.3.1 --remote upstream

# 方式 D：直接给 remote/branch
bash .pi/skills/mr-review/scripts/get-mr-info.sh origin/feature/lr/v4.3.1
```

输出示例：

```text
current_branch: feature/lr/v4.3.1
remote_branch:  origin/feature/lr/v4.3.1
base:           origin/feature/v4.3.1
ahead_behind:   0 3

# commits ---
75ff5e70b | lirui | rol@thooh.com | 2026-08-10 18:06:10 +0800 | refactor(service): ...

# files changed ---
files=7 insertions=64 deletions=17
```

## 自动推断 MR target 逻辑

`--base` 省略时，脚本/流水线会从 MR 提交历史自动推断 target branch：

1. 取指定 `--remote` 下的分支 refs，筛选出是 MR 祖先的分支
2. 取 `merge-base` 日期最新的候选；同名/包含共同版本号的候选额外加分
3. 若 top1 是 `<remote>/master`，但存在更近的 `feature/` / `release/` / `bugfix/` 分支，优先选后者
4. 仍无法推断时 fallback 到 `<remote>/master`

## 流程

1. **提取 MR 元信息 + 影响服务**：当前分支、远程分支、相对 base 的 ahead/behind、提交列表（含作者/邮箱/时间）、文件统计；**「影响服务」必须显式列出**（app 服务 / 插件模块 / 共享包及引用服务 / grpc proto），不能只写「影响全部」。
2. **跑流水线脚本**（在仓库根目录执行）：

```bash
bash .pi/skills/mr-review/scripts/review-mr.sh <branch> [--base <ref>] [--remote <remote>] [--services "a b c"] [--keep]
```

- `--base` 省略时自动推断 MR target；若用户提到明确目标分支，用 `--base` 指定
- worktree 已存在时会提示 `--cleanup`（删除重建）；重复跑同一分支时注意确认，避免误删未提交改动
- 脚本自动：fetch → 元信息 → **影响面分析（Phase 1.5：app 服务 / 插件模块 / 共享包 / grpc）** → worktree 检出 → `make all` 生成依赖 → `make build NAME=xxx` 检查编译 → 测试受影响服务 → **插件模块 `go build ./... && go test ./...`** → **diff 安全检查（Phase 4.5 / `scan-security.sh`）** → 导出 diff 到 `/tmp/mr-<branch>.diff`
- 完整跑约 3-6 分钟，用足够大的 timeout；只想快速看 diff 可加 `--no-tests --no-codegen`
- 测试失败的服务日志在 `/tmp/review-mr-{build,test}-<svc>.log`，**必须读取这些日志确认失败原因**（区分：本 MR 引入 vs 预存问题——用 `git show <base>:<file>` 对比）
- **安全检查（Phase 4.5）**：脚本自动对 diff 新增行做轻量扫描（私钥/AWS key/密钥赋值/危险命令/敏感文件），命中输出到 `/tmp/mr-<branch>.security.txt`，**只提示不阻断**——Agent 必须人工核对命中项，确认属实后按 P1/P2 写入审查结论（对应状态机 `CHECKING_SECURITY` 态）
- **影响面分析（Phase 1.5）**：脚本按 diff 分别统计 `app/{svc}/`、`plugin/**`（独立 Go module）、`pkg/**`（并反查引用它的服务）、`grpc/**`（影响全部服务），写入 meta.json 的 `services` / `plugin_modules` / `pkg_packages` / `pkg_impact_services` / `grpc_touched`。**plugin-only 的 MR 不再误报「未检测到服务变更 → 跳过编译测试」**（历史盲区：`plugin/**` 不在 `app/` 下、`make build NAME=` 覆盖不到）
- **插件模块用例多为外部依赖**（`cert/` 被 gitignore、供应商接口/活动状态会变）：失败必须先与 `--base` 对比区分预存问题，再下结论；`plugin/sdk/proto/*.pb.go` 是 gitignored 生成物，必须让 Phase 3 的 `make all` 跑过（`make proto` 内含 `make -C plugin/sdk proto`），否则插件模块会「假失败」

1. **读 diff 做实质审查**（脚本只给"通过/失败"，不给结论）：读 `/tmp/mr-<branch>.diff`，按 `AGENTS.md` 的审查重点逐条核对：
   - 构建/生成文件变更是否破坏现有生成流程
   - 错误处理：业务错误必须使用项目约定的错误体系，禁止裸 `fmt.Errorf`
   - 新逻辑是否放在对应版本文件中，不污染旧版本
   - 分层：调用方 → 业务层 → 数据层；跨服务只走 RPC/HTTP
   - benchmark 白名单文件不动
   - 扫描/分页逻辑是否可能漏单；金额/支付回调字段语义
   - **安全检查命中项核对**：读 `/tmp/mr-<branch>.security.txt`（若存在），逐条判断是否为真实泄漏/危险命令；误报则说明原因（如测试 mock 值）
   - **实战深度检查**（历次审查验证有效，逐条核对）：
     - GORM `Preload` 关联字段名必须与 do 模型字段一致（如 `GoodCompositeV4` 的 `GoodsCashV4`，旧名 `GoodsCash` 匹配不到字段）
     - 死代码/不可达分支：IIFE 或函数内引用外层 `err` 时，确认该 `err` 在到达点是否恒为 nil（如循环内 handler 出错会提前 `return`/`break`）
     - 共享包（如 `pkg/middlewares`）变更的全局影响面：`grep -rn "GrpcErr()" app/*/service/internal/server/` 确认所有注册服务
     - 跨 gRPC 错误匹配是否真实生效：`errors.Is(err, gorm.ErrRecordNotFound)` 跨进程永远匹配不上；需服务端中间件统一转 `commonv4.ErrorDbNotFound` + 客户端 `IsDbNotFound`，并验证整条链路
     - 错误码契约变更：中间件把 INTERNAL 转 404 等行为变化，需确认调用方无依赖旧错误码
     - 状态字段更新加条件（如 `receive_status != success`）后，确认无"成功后再失败"的合法场景
2. **输出分级结论**：P1（必须修：编译失败/破坏性变更/数据漏处理）→ P2（建议修）→ P3（部署/提示），附 `文件:行号`，并给出 MR 评论草稿（中文，按文件组织）。
3. **给出 MR 摘要**：在审查结论前，先给出 3-5 行中文摘要，说明这是哪类 MR、主要改了什么、影响哪些服务。
4. **附 MR 元信息**：把提取到的分支、commit、作者、文件统计附在结论里，方便追溯。
5. **（可选）同步评论并通知/合并**：审查结论可同步到 Codeup 评论（Phase 7 / `sync-codeup-comment.sh`）；无 P1 且用户要求时可按 Phase 7.5 合并 MR；同步后可选发送钉钉群通知（Phase 10 / `scripts/send-dingtalk.sh`）。用户明确要求"同步" / "合并" / "发钉钉"时执行。

## 构建命令约定（联动 AGENTS.md）

本 skill 统一遵守项目 `AGENTS.md` 的构建约定：

| 命令 | 职责 | 调用时机 |
| --------- | ------ | ------ |
| `make all` | 清理并重新生成项目依赖（proto/wire/config 等） | worktree 检出后、编译前 |
| `make build NAME=xxx` | 生成代码后执行编译，验证项目可构建 | 生成依赖后、测试前 |
| `make proto NAME=xxx` | 仅重新生成 proto | 仅 proto 变更时可按需调用 |
| `make wire NAME=xxx` | 仅重新生成 wire | 仅 wire 变更时可按需调用 |
| `plugin/**`（独立 module） | 在各自模块目录内 `go build ./...` / `go test ./...`（**不经 make**） | 改 `plugin/sdk`、`plugin/utils`、`plugin/plugins/*` 时 |
| `make -C plugin all` | 全量插件构建（产出 `plugin/build/{linux,mac}/*.so`） | 改 `plugin/Makefile` 或需要出产物时 |
| `make proto` | 含 `make -C plugin/sdk proto`（生成 plugin/sdk 的 pb.go） | 改动 `plugin/sdk/proto/**` 时 |

- `NAME=` 从 repo root 传入；进入 `app/{name}/service/` 后可省略
- 若 MR 影响多个服务，按受影响服务逐个执行 `make build NAME=xxx`
- **`plugin/**` 不是 app 服务**：共 14 个独立 `go.mod`（`plugin/sdk`、`plugin/utils`、`plugin/plugins/*`），`make build NAME=xxx` 覆盖不到，必须按模块单独 `go build`/`go test`（脚本 Phase 4 已内置）
- 若 `AGENTS.md` 中命令名称或参数不同，以 `AGENTS.md` 为准，并在审查结论中说明实际使用的命令

## 分支与合并路径（feature → release → test → master）

本仓库分支模型（实测于 `origin/test` / `origin/master` 历史）：

| 分支 | 角色 |
| --------- | --------- |
| `master` | 主分支（`origin/HEAD` 指向它） |
| `release/vX.Y.Z` | 版本集成分支，feature 分支通常 MR 到这里 |
| `test` | **提测分支**，Codeup 上的历史形态是 `Merge #N into test from release/vX.Y.Z` |

**改动要进主分支（master）需要走的路径**：

1. `feature/xxx` --MR--> `release/vX.Y.Z`（评审 MR；**合并用 `rebase`**，Phase 7.5）
2. `release/vX.Y.Z` --MR--> `test`（**提测**；**普通合并（merge commit）**，Codeup API 取值为 `no-fast-forward`，与历史 `Merge #N into test from release/...` 一致，Phase 7.6）
3. 最终由发布流程把 `release/*` 合入 `master`（**本 skill 不自动做**，仅提供前置条件与报错排查）

**能合入的前提（三个分支共用同一套合入规则）**：

- `allRequirementsPass=true`；不满足时看 `checkList.requirementRuleItems`：
  - `MERGE_CONFLICT_CHECK` → false：先本地 rebase 解决冲突
  - `REVIEWER_APPROVED_CHECK` → false：需评审 `PASS`（`POST .../changeRequests/{id}/review`）
  - `COMMENTS_CHECK` → false：所有评论必须 `resolved`（**审查评论默认 unresolved，会阻塞合入**）
- 合并方式按分支区分：**`test` 提测用普通合并（merge commit）→ API 取值 `no-fast-forward`**；**其他 MR 合并用 `rebase`**。实测（提测 MR #168）：`mergeType=merge` 被 **403 拒结**、`no-fast-forward` 成功；`ff-only` / `squash` 同样不支持
- 失败码：400 参数缺/错（最常见缺 `mergeType`）、403 不支持该合并方式、405 合入规则不满足

## 云效平台增强

本 skill 在 git-based 审查流水线之外，可叠加云效 Codeup 平台能力，
让 MR 审查从“本地代码审查”升级为“平台级审查”。

### 前置：云效 MCP 可用性检查

- 配置位置：`~/.pi/agent/mcp.json`
- 环境变量：`YUNXIAO_ACCESS_TOKEN`
- 可用性验证：调用 `alibabacloud_devops_mcp_server_get_current_organization_info`，取 `lastOrganization`
- 若不可用，退回纯 git 审查流程，不要阻塞

### Phase 6: Codeup MR 元信息补充（由 Agent 执行）

`review-mr.sh` 执行完毕后，Agent 读取 `/tmp/mr-<branch>.meta.json`，然后按序调用云效 MCP：

1. **获取组织/仓库信息**
   - `get_current_organization_info` → 取 `lastOrganization`
   - `list_repositories` → 按 `name` 或 `repo_path` 匹配当前仓库，取 `id`

2. **定位 MR**
   - `list_change_requests` → 按 `sourceBranch` / `targetBranch` 匹配
   - 若已知 MR localId，直接调用 `get_change_request`

3. **补充 MR 信息**
   - 标题、描述、创建时间、状态（`UNDER_REVIEW` / `MERGED` / `CLOSED`）
   - 评审人列表、订阅者、评审状态（`hasReviewed` / `reviewOpinionStatus`）
   - ahead / behind、conflictCheckStatus、allRequirementsPass
   - patch sets（版本 ID、commit、创建时间、relatedMergeItemType）

4. **校验 base branch**
   - 对比 `get_change_request` 返回的 `targetBranch` 与 git 推断的 `BASE`
   - 不一致时提示：`Codeup 显示 target 为 xxx，git 推断为 yyy，建议用 --base xxx`

5. **获取 MR 评论**
   - `list_change_request_comments` → 读取已有评论，避免重复审查已知问题
   - 过滤 `resolved=false` 的评论，优先关注未解决问题

### Phase 6.5: 平台预检查（由 Agent 执行，审查前必做）

在开始实质审查前，Agent 应通过 MCP 完成以下平台级检查：

1. **MR 状态检查**
   - `get_change_request` → 确认 MR 仍为 `UNDER_REVIEW`
   - 若已 `MERGED` / `CLOSED`，停止审查并提示

2. **CI 状态检查（需要显式 pipelineId）**
   - 当前 MCP 工具 `get_latest_pipeline_run` 的入参是 `pipelineId`，**无法从 MR 自动反查流水线 ID**
   - 若用户提供了 `--pipeline-id <id>`，则调用 `get_latest_pipeline_run` 检查最近一次构建状态
   - 若流水线失败，提示：`CI 失败，建议修复流水线后再审查`
   - **若未提供 --pipeline-id，跳过 CI 检查并提示用户该步骤需手动补充**

3. **评审人状态检查**
   - `search_organization_members` → 获取评审人详细信息
   - 检查是否所有评审人已审阅（`hasReviewed=true`）
   - 若存在未审阅评审人，提示：`xxx 尚未审阅`

4. **评论冲突检查**
   - `list_change_request_comments` → 检查是否有未解决的阻塞评论
   - 若 `unResolvedCommentCount > 0`，提示：`存在 N 条未解决评论，请先处理`

### Phase 7: 审查结论同步到 Codeup（由 Agent 执行）

审查结论生成后，可自动同步到 Codeup MR：

1. **评论前检查**
   - 读取现有评论，避免重复发布相同结论
   - 检查 MR 状态，避免在已关闭 MR 上评论

2. **全局评论**
   - 工具：`create_change_request_comment`
   - `comment_type`: `GLOBAL_COMMENT`
   - `patchset_biz_id`: 使用 MR 最新源版本 ID（`list_change_request_patch_sets` 中 `relatedMergeItemType=MERGE_SOURCE` 的 `patchSetBizId`）
   - `content`: 审查摘要 + 分级结论

3. **行内评论（可选）**
   - `comment_type`: `INLINE_COMMENT`
   - 额外必传：`file_path`, `line_number`, `from_patchset_biz_id`, `to_patchset_biz_id`
   - 适合逐行指出具体问题

4. **评论生命周期管理**
   - `update_change_request_comment` → 更新旧评论内容或解决状态
   - 若 MR 已修复，可将旧评论标记为 `resolved=true`
   - **注意：审查评论默认 `resolved=false`，会阻塞合入**（`COMMENTS_CHECK` 规则）；结论为"无 P1 可合入"时，合并前需将审查评论置为 `resolved=true`（Phase 7.5）
   - `update_change_request_comment` → 更新旧评论内容或解决状态
   - 若 MR 已修复，可将旧评论标记为 `resolved=true`

5. **评论策略**
   - 优先同步 P1 结论（必须修）
   - P2/P3 可合并为一段建议
   - 若评论过长，按文件拆分多条评论
   - 草稿模式：`draft=true` 可先不发布，确认后再改为正式评论

### Phase 7.5: 合并 MR（可选，由 Agent 执行）

审查无 P1 且用户要求"合并/合入"时，走 Codeup OpenAPI 合并（MCP 无合并工具）。**先解除合入规则阻塞，再调 merge 接口**——实测 405 SYSTEM_FORBIDDEN_ERROR 绝大多数是合入规则不满足，不是参数问题。

1. **合并前置检查**：`get_change_request` → 看 `allRequirementsPass`；为 false 时查 `checkList.requirementRuleItems`：
   - `MERGE_CONFLICT_CHECK`：false = 有冲突，需先解决（本地 rebase 后 push）
   - `REVIEWER_APPROVED_CHECK`：false = 无评审人通过 → 调评审接口 `POST .../changeRequests/{localId}/review`，body `{"reviewOpinion":"PASS","reviewComment":"..."}`（`reviewOpinion` 取值 `PASS` / `NOT_PASS`）
   - `COMMENTS_CHECK`：false = 存在未解决评论（**审查评论默认 unresolved 会计入**）→ 把已处理评论 `update_change_request_comment` 置 `resolved=true`

2. **调合并接口**：`POST https://openapi-rdc.aliyuncs.com/oapi/v1/codeup/organizations/{orgId}/repositories/{repoId}/changeRequests/{localId}/merge`
   - Header：`x-yunxiao-token: ${YUNXIAO_ACCESS_TOKEN}`
   - Body：`{"mergeMessage":"...","mergeType":"..."}`，**`mergeType` 必填**，取值小写：`ff-only` / `no-fast-forward` / `squash` / `rebase`
   - 本仓库实测**只支持 `rebase`**（其余三种返回 403 "不支持xxx合并方式"）；behind>0 时也无法 ff-only
   - 失败排查：400 = 参数缺/错（最常见缺 `mergeType`）；403 = 不支持该合并方式或规则仍不满足；405 = 合入规则不满足（回第 1 步看 checkList）

3. **合并后确认**：重新 `get_change_request`，`status` 应为 `MERGED`、`allRequirementsPass=true`。

### Phase 7.6: 自动合并到 test（提测，由 Agent 执行）

改动已合入 release 后需要提测时执行（等价于历史 `Merge #N into test from release/vX.Y.Z`）：

```bash
# 只打印计划，不做任何写操作
bash .pi/skills/mr-review/scripts/merge-to-test.sh --source release/v4.3.6.2 --dry-run

# 真正提测：找/建 release/vX.Y.Z → test 的 MR，解除合入规则阻塞后以普通合并（no-fast-forward）合并
bash .pi/skills/mr-review/scripts/merge-to-test.sh --source release/v4.3.6.2
```

脚本行为：① 先比 `origin/<test>` 与 `origin/<source>`（**用远端 ref，避免本地过期 release 分支造成误判**），已全部包含则直接退出（幂等，可重复跑）；② 复用进行中的 source→test MR，没有才创建（**创建需带 `sourceProjectId`/`targetProjectId`，否则 Codeup 直接 500**）；③ 预检 `allRequirementsPass`：冲突/未解决评论 → 停止并给出处置方式（**不擅自 resolve 别人的评论**），缺评审 → 自动提交 `PASS`；④ 以普通合并（`no-fast-forward`，产生 merge commit）并校验 `status=MERGED`。

选项：`--test-branch <name>`（默认 `test`）、`--merge-type`（默认 `no-fast-forward`）、`--no-review-pass`、`--repo-id 7289138`、`--dry-run`。

- **提测是写共享分支的动作**（会触发测试环境发布）：**只在用户明确说「提测」时才执行**；不确定就先 `--dry-run` 把计划给用户确认
- 本 skill 的写操作只有四类，且都需用户明确要求：**评论**（Phase 7）、**钉钉通知**（Phase 10）、**合并 MR**（Phase 7.5，`rebase`）、**提测**（Phase 7.6，普通合并 `no-fast-forward`）；**不会自动合并到 `master`**
- 依赖：`YUNXIAO_ACCESS_TOKEN`；`curl` / `jq` / `git`

### Phase 8: Shell 级平台信息查询（绕过 Agent/MCP）

若 Agent 不可用或需在 CI 中快速查看平台信息，可使用 `scripts/mr-platform-info.sh`。

```bash
# 读取 meta 文件，自动获取 MR 详情、评论、评审人
bash .pi/skills/mr-review/scripts/mr-platform-info.sh \
  --meta /tmp/mr-<branch>.meta.json

# 带评论和流水线信息
bash .pi/skills/mr-review/scripts/mr-platform-info.sh \
  --meta /tmp/mr-<branch>.meta.json \
  --with-comments --with-pipelines --with-members

# 原始 JSON 输出
bash .pi/skills/mr-review/scripts/mr-platform-info.sh \
  --local-id 9 --repo-id 7289138 --json
```

该脚本直接调用 Codeup OpenAPI，输出 MR 详情、patchsets、评论、评审人等信息。

### Phase 9: Shell 级评论同步（绕过 Agent/MCP）

若 Agent 不可用或需在 CI 中直接发评论，可使用 `scripts/sync-codeup-comment.sh`。该脚本直接调用 Codeup OpenAPI，不需要依赖 MCP 或 Agent。

```bash
# 最小可用：从 meta 文件推断所有信息，自动查找 MR 与 patchset
bash .pi/skills/mr-review/scripts/sync-codeup-comment.sh \
  --meta /tmp/mr-<branch>.meta.json \
  --comment "review conclusion"

# 带文件内容
bash .pi/skills/mr-review/scripts/sync-codeup-comment.sh \
  --meta /tmp/mr-<branch>.meta.json \
  --file review-summary.md

# 草稿评论（不发布）
bash .pi/skills/mr-review/scripts/sync-codeup-comment.sh \
  --local-id 9 \
  --repo-id 7289138 \
  --comment "P1: need fix" \
  --draft
```

自动推断顺序（均可手动 `--` 覆盖）：

1. `organizationId` → `YUNXIAO_ORG_ID` 环境变量 → `GET /oapi/v1/platform/user` 取 `lastOrganization`
2. `repositoryId` → `YUNXIAO_REPO_ID` / `--repo-id` → `--repo-path` → git remote URL 推断路径 → `list_repositories?search=`
3. `localId` → `--local-id` → meta 文件的 `remote_branch` → `list_change_requests` 按 sourceBranch 匹配
4. `patchset_biz_id` → `--patchset-biz-id` → `list_change_request_patch_sets` 取最新 `MERGE_SOURCE` 版本
   - `--meta` 自动推断时，同名仓库可能 warn "exact path 未命中"，建议显式 `--repo-id <id>`（本项目仓库 id 为 `7289138`）

注意：

- 依赖环境变量 `YUNXIAO_ACCESS_TOKEN`（必填）
- 依赖 `curl`、`jq`、`git`
- 默认 API 网关：`https://openapi-rdc.aliyuncs.com`（可通过 `YUNXIAO_API_BASE_URL` 覆盖）
- region 站需设置 `YUNXIAO_EDITION=region`，organizationId 固定为 `default`

## 钉钉通知（可选，Phase 10）

审查结论同步 Codeup 后，可发送钉钉群通知。统一使用 `scripts/send-dingtalk.sh`（封装了 UTF-8 payload 与加签逻辑）。

**@ 对象 = MR 发起人 + 本 MR 全部提交者（去重）**，审查**通过**时再追加**测试人员**（本项目：潘婷）。发送前先用 `scripts/get-mr-author.sh` 解析出**手机号列表**，再传给 `send-dingtalk.sh --at`。

该脚本：① 读 **MR author**；② 用**本地 git 两点差集** `git log <base>..<ref>` 取「本 MR 自己的提交」的全部作者（**必须是两点差集**：三点差集 `<base>...<ref>` 是对称差集，分支落后目标分支时会把 base 侧提交的作者一并串进来——实测 behind 107 的 MR 因此多 @ 了 4 位无关同事；`--base` 默认 `origin/<MR targetBranch>`，与 review-mr.sh 一致；git 不可用时回退 API）；③ 逐人解析手机号；④ 输出 `at_mobiles` / `at_text_hint` / `recipients` / `unresolved`。

> ⚠️ **平台限制（实测）**：云效**不提供**查询成员手机号的 API —— `search_organization_members` / `get_organization_member_info(_by_user_id)` / `list_organization_members` 用当前 token 一律 **403**（`Current token has no permission to api.`，原始 OpenAPI 亦然）；`list_commits` 只返回 `authorName/authorEmail`，**无手机号字段**。故手机号只能来自 username/email 内嵌或收件人映射文件。

```text
# 1) 解析收件人手机号列表（审查通过时记得加 --with-tester → 追加测试人员潘婷）
bash .pi/skills/mr-review/scripts/get-mr-author.sh --local-id 120 --repo-id 7289138 --with-tester
#    输出: at_mobiles=15339891972,13678235158,15708432566
#          at_text_hint="@15339891972 @13678235158 @15708432566"  ← 直接粘进 markdown 正文
#          recipients=[{name,email,mobile,source,matched,is_tester}] / unresolved=[{name,email}]
#    其他: --meta /tmp/mr-<branch>.meta.json 自动推断；--json 输出纯 JSON（提示走 stderr）；
#          --base origin/release/v4.3.6 显式指定差集基线；--no-git 跳过本地 git；
#          --at 15708432566 额外追加收件人（可逗号分隔多个）

# 2) 发送通知：把上一步的 at_mobile 传给 --at（正文必须含 @手机号 文本才会渲染 @）
bash .pi/skills/mr-review/scripts/send-dingtalk.sh \
  --keyword 提测 --title "MR #91 提测审查通知" --file /tmp/mr91-dingtalk.md \
  --at <at_mobile>

# 最小可用：markdown 通知（不 @ 任何人；webhook 自动探测）
bash .pi/skills/mr-review/scripts/send-dingtalk.sh \
  --title "MR #16 审查完成" --file /tmp/mr16-review.md

# 纯文本
bash .pi/skills/mr-review/scripts/send-dingtalk.sh --text "提测：MR #16 审查通过"

# 显式指定/覆盖 @ 对象（临时改 @ 别人时用）
bash .pi/skills/mr-review/scripts/send-dingtalk.sh --keyword 提测 --title "MR #16 提测审查通知" --file /tmp/mr16-review.md --at 15708432566

# 只检查 webhook 模式与关键词，不发送
bash .pi/skills/mr-review/scripts/send-dingtalk.sh --keyword 提测 --title x --content "提测x" --check
```

### 钉钉机器人机制与坑（必读）

1. **环境变量**：`DINGTALK_WEBHOOK_UR`（**注意：本仓库环境变量拼写少一个 L**），脚本优先读正确拼写的 `DINGTALK_WEBHOOK_URL`、回退 `DINGTALK_WEBHOOK_UR`；也可 `--webhook` 显式指定。
2. **安全模式由 URL 判断**：URL 含 `secret=` 参数 → 加签模式（脚本自动计算 `timestamp` + HMAC-SHA256 签名）；否则 → 自定义关键词模式。
3. **关键词模式（本项目）**：消息文本必须包含管理员配置的关键词，否则返回 `errcode 310000`（关键词不匹配）。本项目机器人关键词为「提测」；**未知关键词先问用户，勿盲目试词**（可能触发限流）。
4. **中文编码坑（重要）**：bash 内联中文 payload 会编码异常，导致关键词匹配失败（消息里明明有「提测」仍 310000）。必须用 python3 `json.dumps(...).encode('utf-8')` 构造 payload——`send-dingtalk.sh` 已封装此逻辑，**不要用 curl 内联中文 JSON**。
5. **bash 变量插值坑**：脚本/消息中 `$VAR` 后紧跟全角字符（如 `$KEYWORD」`）时，UTF-8 locale 下 bash 会把全角字符当变量名续字符导致未绑定错误；一律用 `${VAR}`。
6. **成功标志**：`DINGTALK_SEND_OK`；失败时非零退出并打印 `DINGTALK_SEND_FAIL errcode=...`。
7. **@ 对象（重要，默认多收件人）**：`--at <手机号[,手机号...]>` 传入 `at.atMobiles` 可一次 @ 多人；**名单由 `scripts/get-mr-author.sh` 解析**（MR 发起人 + 本 MR 全部提交者；审查通过时加 `--with-tester` 追加测试人员潘婷），不要写死固定号码。两个实测坑：① **仅传 `--at` 群内不显示 @**——**markdown 正文必须包含 `@手机号` 文本**（用脚本的 `at_text_hint`，如 `@15339891972 @13678235158 @15708432566`）才会渲染出 @ 人；② 钉钉不支持按名字 @，`atMobiles` 必须精确匹配群内成员的钉钉绑定手机号，若发送成功但群里没有 @，说明该号不在机器人所在群。
8. **钉钉 markdown 兼容性**：**不支持表格**（渲染为纯文本/乱码），影响服务与功能影响点等列表须用 `-` 无序列表；支持 `###` 标题、`**加粗**`、行内 `` `code` ``、`-`/`1.` 列表、emoji、`---` 分隔线、`[链接](url)`。
9. **收件人与手机号解析（多人）**：钉钉 @ 只认手机号，而平台不提供成员手机号查询（`search_organization_members` 等一律 403；`list_commits` 无手机号字段），故 `scripts/get-mr-author.sh` 的做法是——
   **a) 名单**：① MR 发起人（MR API `author`）；② **本 MR 全部提交者**，用本地 `git log <base>...<ref>` 三点差集得出（= 本 MR 自己的提交，与目标分支无关的历史会被排除；`--base` 默认 `origin/<targetBranch>`），git 不可用时回退 API；③ `--with-tester` 时追加配置里 `roles.tester`（**代码审查通过时使用**，本项目为潘婷 15708432566）。
   **b) 逐人解析手机号**：① `--at` 显式追加 → `explicit`；② **收件人映射文件** → `config`，查找顺序 `MR_REVIEW_RECIPIENTS` → `~/.pi/mr-review-recipients.json`（私有，不进仓库，**推荐**）→ `<skill>/config/dingtalk-recipients.json`，键支持 `by_user_id` / `by_username` / **`by_commit_email`** / `by_email` / `by_name` / **`by_commit_name`**（优先级同序）；③ `username` 形如 `aliyun:<11位手机号>_xxx` → `username`（实测：周永高 `aliyun:15184345039_Y4Y`）；④ 邮箱前缀即手机号 → `email`（实测：`15339891972@163.com`）；⑤ 提交人姓名本身是手机号 → `name`；⑥ 取不到 → 该人**列入 `unresolved` 不 @**（其余人照常 @），**禁止猜号码**。
   **c) 去重与上限**：同一手机号只 @ 一次；人敟超 `MR_REVIEW_MAX_RECIPIENTS`（默认 10）时截断并告警。
   **d) 防误抓**：邮箱/姓名提取仅接受**恰好 11 位且 `1[3-9]` 开头**，故 QQ 号（`1971162852@qq.com`）、gmail 用户名（`1abc@gmail.com`）等不会误抓；也不拿**他人**的手机号冒充本人（早期版本曾把分支上他人映射邮箱当成发起人，已修并加回归用例）。

---

### 输出格式增强

在原有输出基础上，补充以下 Codeup 平台信息：

```text
## MR 信息
- 分支：feature/lr/v4.3.1
- 目标：origin/feature/v4.3.1（自动推断）或显式 --base
- 提交：3 个
- 作者：lirui
- 文件：7 files changed, 64 insertions(+), 17 deletions(-)
- 影响服务（**必填**，来自 Phase 1.5 / meta.json）：
  - app 服务：supplier user（编译 + 测试范围）
  - 插件模块：plugins/zltx_v2、sdk、utils（独立 module，单独编译 + 测试）
  - 共享包：pkg/middlewares → 引用服务 activity admin gateway merchant openapi order supplier task user
  - grpc proto：无改动 / 有改动（影响全部服务）
- Codeup MR: #9 (https://codeup.aliyun.com/lsxd/ymt/marketing/change/9)
- 标题：refactor(service): ...
- 状态：UNDER_REVIEW
- 评审人：name [reviewOpinionStatus] hasReviewed
- ahead/behind：3/0
- 目标分支校验：✅ 一致 / ⚠️ 不一致
- 钉钉通知：✅ 已发送（@ 发起人 周永高 / 15102807142） / 跳过（未要求） / ⚠️ 已发送但不 @（未解析到发起人手机号，at_source=none）
```

### 注意事项

- 云效 MCP 依赖 `YUNXIAO_ACCESS_TOKEN` 有效期，若调用失败提示 token 过期
- **CI 检查需要显式 `--pipeline-id`**：`get_latest_pipeline_run` 不接受 `changeRequestId`，MCP 无法自动关联流水线
- `list_change_requests` 返回的是仓库下所有 MR，需按 `sourceBranch` / `targetBranch` 精确匹配
- 行内评论需要准确的 `patchset_biz_id`，建议从 `list_change_request_patch_sets` 获取
- 创建评论前检查 `unResolvedCommentCount`，避免在已关闭 MR 上评论
- 若 Codeup MCP 不可用，保留纯 git 审查能力，不阻塞流程
- 钉钉发送：环境变量 `DINGTALK_WEBHOOK_UR`（本仓库拼写少 L）；关键词模式消息必须含机器人关键词（本项目「提测」）；必须用 python3 构造 UTF-8 payload（bash 内联中文会编码异常导致 310000）；errcode 310000 = 关键词不匹配，未知关键词先问用户
- **钉钉 @ 名单（多收件人）**：跑 `scripts/get-mr-author.sh` 拿 `at_mobiles` 传给 `send-dingtalk.sh --at`，并把 `at_text_hint` 粘进正文；**代码审查通过时加 `--with-tester`** 追加测试人员（潘婷 15708432566）。名单 = MR 发起人 + 本 MR 全部提交者（git 三点差集）+（通过时）测试人员；解析不到的人列入 `unresolved` 不 @（补号优先用 **`by_commit_email`**——提交记录邮箱可读性远好于云效 `author.email` 的 teambition 别名邮箱，如 `{"by_commit_email":{"rol@thooh.com":"13xxxxxxxxx"}}`）

### 流水线状态机（Phase 0-10 总览）

结合「代码审查 Skill 实战」的状态机思想，mr-review 流水线是一条显式状态链；每个 Phase 有明确产物与失败处理路径：

| Phase | 状态 | 产物 | 失败处理 |
| ------- | ------ | ------ | ---------- |
| 0 | METADATA | MR 元信息（分支/提交/文件统计） | 分支不存在 → 提示并停止 |
| 1 | FETCH | 远程引用更新 | 网络失败 → 重试/提示 |
| 1.5 | IMPACT | 影响服务（app 服务 / 插件模块 / 共享包 + 引用服务 / grpc）→ meta.json 与汇总区 | 无法判定 → 提示人工 `--services` 指定 |
| 2 | WORKTREE | 隔离 worktree | 已存在 → `--cleanup` 或复用 |
| 3 | CODEGEN | `make all` 生成依赖 | 生成失败 → 停止（编译必然失败） |
| 4 | BUILD+TEST | 服务编译/测试结果 | 失败看 `/tmp/review-mr-*.log`，区分引入 vs 预存 |
| 4.5 | CHECKING_SECURITY | diff 安全检查（`scan-security.sh`）→ `/tmp/mr-<branch>.security.txt` | 只提示不阻断；命中项 Agent 人工核对 |
| 5 | DIFF | `/tmp/mr-<branch>.diff` | — |
| 6 | PLATFORM | Codeup MR 元信息补充 | MCP 不可用 → 退回纯 git |
| 6.5 | PRECHECK | 状态/CI/评审人/评论检查 | MR 已合并/关闭 → 停止审查 |
| 7 | SYNC | Codeup 评论 | — |
| 7.5 | MERGE | MR 合并 | 规则不满足 → 看 checkList |
| 7.6 | MERGE-TEST | 提测：`release/* → test` 的 MR（`merge-to-test.sh`，普通合并 `no-fast-forward`） | 冲突/他人未解决评论 → 停止并给处置方式；规则不满足 → 打印 checkList |
| 10 | NOTIFY | 钉钉通知（**@ MR 发起人 + 本 MR 全部提交者**，审查通过时加 `--with-tester` 追加测试人员，名单由 `get-mr-author.sh` 解析） | 关键词不匹配 → 问用户；部分人解析不到 → 列入 `unresolved` 不 @ 其余照常 @ |

### 钩子与扩展点（on_start / on_issue_found / on_complete）

流水线在关键节点提供钩子语义，80% 定制走钩子而非 fork 脚本：

- **on_start** = Phase 6.5 平台预检查（审查前必做：MR 状态 / 评审人 / 未解决评论）
- **on_issue_found** = 发现 P1 → 停止合并（Phase 7.5 前置检查 `allRequirementsPass`）；Phase 4.5 安全检查命中可疑信号时同样触发提示
- **on_complete** = 审查结论同步 Codeup（Phase 7）+ 可选钉钉通知（Phase 10）

### 性能说明（Phase 4 并发）

- 服务间 build/test **并行执行**（默认并发 4，`MAX_PARALLEL` 环境变量可调）；单服务内 build → test 保持顺序
- 共享 repo-local GOPATH（`.go/`）作为依赖缓存，worktree 不重复下载依赖
- 完整流水线约 3-6 分钟；`--no-tests --no-codegen` 可快速只看 diff
- **Trace（第4篇思想）**：脚本记录 `START_TS`，汇总区输出总耗时，meta.json 带 `duration_sec`——审查偏慢时用耗时定位瓶颈阶段

### 阶段编号说明

- review-mr.sh 内部按 Phase 0-5.5 输出进度；本节的云效增强接续编号为 Phase 6-9（Phase 7.5 为合并 MR）。
- 钉钉通知为 Phase 10（`scripts/send-dingtalk.sh`，**@ 名单 = MR 发起人 + 本 MR 全部提交者 +（审查通过）测试人员**，由 `scripts/get-mr-author.sh` 解析），接续在 Phase 7 同步评论之后、用户要求"发钉钉"时执行
- “流程”章节的步骤 1-4 是同一流程的高层描述，与脚本阶段一一对应：步骤 1→Phase 0，步骤 2→Phase 3-5，步骤 3→Phase 6.5 实质审查，步骤 4→Phase 7 同步评论（合并见 Phase 7.5）。
- 影响面分析为 Phase 1.5（在 review-mr.sh 内）；提测合并为 Phase 7.6（`scripts/merge-to-test.sh`，普通 `merge`），在 Phase 7.5 合入 MR 目标分支之后、**用户明确要求「提测」**时执行。
- 分支与合并路径（feature → release → test → master）见上文专节：**`test` 用 `merge`、其他合并用 `rebase`、`master` 不自动合并**。

### 质量检查

修改 `scripts/` 下任何脚本后，提交前至少执行：

```bash
bash -n scripts/*.sh scripts/lib/*.sh          # 语法检查
shellcheck scripts/*.sh scripts/lib/*.sh       # 静态检查（如已安装）
```

**测试与调试（第4篇单测/Mock 思想）**：

- 核心脚本提供 dry-run 自检入口，改动后先跑冒烟再交付：
  - `bash scripts/tests/smoke.sh` — 一键冒烟（语法 + send-dingtalk --check 三路径 + get-mr-author 自检/缺 token 保护 + sync-codeup 缺参保护 + scan-security 自检）
  - `scan-security.sh --self-test` — 安全检查 mock 数据自检（命中 3 类信号 + 误报过滤）
  - `send-dingtalk.sh --check` — 校验 webhook 模式与关键词，不真实发送
  - `get-mr-author.sh --self-test` — 收件人 @ 手机号解析自检：映射键优先级（含 `by_commit_email`）/ username 与邮箱前缀提取 / 多人聚合去重 / **不跨人串号**（回归用例）/ 测试人员角色 / 误抓防护（QQ号·gmail），**16 条断言，离线**
  - `sync-codeup-comment.sh --draft` — 草稿评论，确认后再发布
  - `review-mr.sh --no-tests --no-codegen` — 快速只看 diff，绕过耗时步骤
- 外部依赖（Codeup API / 钉钉 webhook）不可用时，脚本应**降级不阻塞**（如 MCP 不可用退回纯 git 审查），避免单点故障
- 修改 `scripts/lib/` 公共函数后，用 `bash -n` + 一次真实或 `--check` 调用验证，别跳步骤

注意：脚本依赖 bash >= 4（使用 mapfile），macOS 自带 bash 3.2 无法运行，需通过 brew 安装 bash 或调整 PATH。

---
