# 交付物模板

- `gate-record.json`：每个阶段门记录的最小字段；复制到 `.harness/deliverables/gates/`。
- `submission-manifest.json`：提测材料包清单与冒烟/版本字段；复制到 `.harness/deliverables/artifacts/submission.json`。

各阶段证据模板直接用 `.harness/deliverables/artifacts/*.json` 的示例结构；替换 `example: true` 与示例值后，运行 `make check-strict`。
