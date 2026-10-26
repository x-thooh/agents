---
name: bad-scope-grading
description: 用于反向测试本 skill 的检查器（A deliberately broken fixture）。 Expects exactly one ERROR with code SCOPE001 (scope is described as a cumulative level, which UHP conformance classes are but harness scopes, being orthogonal domains, are not).
---

# Fixture: bad-scope-grading

Single defect: the line below copies UHP's cumulative grading onto harness scopes, which are orthogonal domains with no containment between them.

scope 分级：每个 scope 就是一个 class，声明即承诺。
