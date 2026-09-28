# -*- coding: utf-8 -*-
"""v3.32 fix：懒渲染引擎对 node 测试桩的最小 DOM 环境守卫。幂等。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()

old1 = """    if (!ED.querySelector('.blk[data-lazy]')) renderMermaidIn(ED);"""
new1 = """    if (typeof ED.querySelector === 'function' && !ED.querySelector('.blk[data-lazy]'))
      renderMermaidIn(ED);"""
old2 = """  function flushLazyAll() {
    var els = ED.querySelectorAll('.blk[data-lazy]');
    for (var i = 0; i < els.length; i++) flushLazyEl(els[i]);
  }"""
new2 = """  function flushLazyAll() {
    if (typeof ED.querySelectorAll !== 'function') return;   /* node 测试桩无完整 DOM */
    var els = ED.querySelectorAll('.blk[data-lazy]');
    for (var i = 0; i < els.length; i++) flushLazyEl(els[i]);
  }"""
old3 = """  function lazySetup() {
    if (lazyObserver) { lazyObserver.disconnect(); lazyObserver = null; }"""
new3 = """  function lazySetup() {
    if (typeof ED.querySelectorAll !== 'function') return;   /* node 测试桩无完整 DOM */
    if (lazyObserver) { lazyObserver.disconnect(); lazyObserver = null; }"""

n1, n2, n3 = src.count(old1), src.count(old2), src.count(old3)
print("counts:", n1, n2, n3)
if (n1, n2, n3) != (1, 1, 1):
    sys.exit(1)
src = src.replace(old1, new1).replace(old2, new2).replace(old3, new3)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("fix applied")
