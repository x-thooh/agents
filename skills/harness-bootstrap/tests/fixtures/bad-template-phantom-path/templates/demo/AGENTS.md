# demo 模板（反向样本）

这份文档故意点名一个模板里不存在的路径：`.harness/scripts/retro.py`。
目标仓库照它走会扑空，而此前没有任何断言会报——`tplpath` 的 `TP001` 就是为它存在的。

同一份文档里也写了真实存在的 `.harness/workflow/contract.json`，用来证明
`TP001` 不是「见到反引号就报」：能解析的路径必须放过。
