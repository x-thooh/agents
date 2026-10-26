"""demo：反向样本里的假 scope，只为让 DOC001 有东西可比。"""
NAME = "demo"


def run(ctx, findings):
    findings.append(("ERROR", NAME, 1, "DEMO001", "假 scope，不会被真的执行"))
