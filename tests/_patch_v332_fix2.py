# -*- coding: utf-8 -*-
"""v3.32 fix2：reorderSections 连续性校验（按原始顺序）+ srcMode 探测（.t-src）。幂等。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()

old1 = """    var n = state.raw.length, lo = -1, hi = -1, prev = -1, k;
    for (k = 0; k < pairs.length; k++) {
      var s = +pairs[k][0], e = +pairs[k][1];
      if (!(s >= 0 && e > s && e <= n)) return 'invalid';
      if (prev >= 0 && s !== prev) return 'invalid';   /* 不连续（跨级 / 缓存过期） */
      if (lo < 0) lo = s;
      prev = e;
      hi = e;
    }"""
new1 = """    var n = state.raw.length, lo = -1, hi = -1, prev = -1, k;
    /* 连续性校验按【原始位置】排序后进行（pairs 是新顺序，乱序是调序的本意） */
    var sorted = pairs.slice().sort(function (a, b) { return (+a[0]) - (+b[0]); });
    for (k = 0; k < sorted.length; k++) {
      var s = +sorted[k][0], e = +sorted[k][1];
      if (!(s >= 0 && e > s && e <= n)) return 'invalid';
      if (prev >= 0 && s !== prev) return 'invalid';   /* 不连续（跨级 / 缓存过期） */
      if (prev < 0) lo = s;
      prev = e;
      hi = e;
    }"""

old2 = """    var srcMode = !!document.querySelector('.raw-edit.t-src');"""
new2 = """    var srcMode = !!document.querySelector('.t-src');   /* 源码模式：整个编辑区是源码框 */"""

n1, n2 = src.count(old1), src.count(old2)
print("counts:", n1, n2)
if (n1, n2) != (1, 1):
    sys.exit(1)
src = src.replace(old1, new1).replace(old2, new2)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("fix2 applied")
