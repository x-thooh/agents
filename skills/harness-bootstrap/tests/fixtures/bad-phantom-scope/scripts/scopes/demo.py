"""demo：反向样本里的假 scope，只为让 scope 名有东西可比。"""
NAME = "demo"


def run(ctx, findings):
    findings.append(("ERROR", NAME, 1, "DEMO001", "假 scope，不会被真的执行"))
