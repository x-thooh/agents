"""反向样本：REFLECT 故意留空。"""

PLAN = {"demo": "假 scope"}

REFLECT = {"demo": ()}


def plan(name):
    return [PLAN[name]] if name in PLAN else []


def reflect(name):
    return list(REFLECT.get(name, ()))
