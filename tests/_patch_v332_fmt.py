# -*- coding: utf-8 -*-
"""v3.31.2 行内格式卫生批补丁：FMT-1/2/3（依据《行内格式化交互测试报告-v3.30.19》）

FMT-1(P1): 选区落在渲染态 <code> 内时拒绝叠加行内格式（bold/italic/strike/mark/link），
           与「跨行守卫」同款策略；code（toggle 取消）与 clearfmt（剥码壳）放行。
FMT-2(P2): 链接 toggle 取消 —— 选区紧邻 [ 与 ](url) 时移除链接而非再包一层。
FMT-3(P2): 清除格式纳入链接外壳（[ 与 ](url) 一并剥离，保留纯文字）。
"""
import io
import sys

PATH = r"E:\WorkBuddy\md-editor\src\editor.html"

PAIRS = [
    # ---------- FMT-1：行内代码内拒绝叠加格式（插在单元格分支之后、映射之前） ----------
    ("""    var cf = cellFormatCtx();
    if (cf) { applyCellFloat(cf, action); return; }
    /* 优先使用当前实时选区；若点击过程中选区被浏览器塌陷，则回退到最近一次快照 */
    var info = currentSelectionInfo() || lastFB;
    if (!info) { hidePops(); return; }
    lastFB = info;
    if (action === 'delblk') { deleteBlockAt(info.idx); return; }
""",
     """    var cf = cellFormatCtx();
    if (cf) { applyCellFloat(cf, action); return; }
    /* v3.31.2（FMT-1 根修）：选区落在渲染态 <code> 内时拒绝叠加行内格式 ——
       行内代码内容按 CommonMark 不解析任何标记，叠加只会产生字面标记（~~ 变正文），
       且渲染明文长度与 raw 错位 → 后续映射整体偏移、源码结构性损坏。
       与下方「跨行守卫」同款策略：拒绝应用并提示。
       放行两类：code（选区内码壳 toggle 取消）、clearfmt（连码壳一起剥掉）；
       delblk / 单元格路径（上方已 return）不受影响 */
    if (action === 'bold' || action === 'italic' || action === 'strike' ||
        action === 'mark' || action === 'link') {
      var _sel = getSelection();
      if (_sel && _sel.rangeCount) {
        var _sc = _sel.getRangeAt(0).startContainer;
        var _ce = _sc.nodeType === 1 ? _sc : _sc.parentElement;
        _ce = _ce && _ce.closest ? _ce.closest('#editor code') : null;
        if (_ce) {
          toastStatus('行内代码内不支持叠加行内格式（可点 T× 连码壳一起清除）');
          hidePops();
          return;
        }
      }
    }
    /* 优先使用当前实时选区；若点击过程中选区被浏览器塌陷，则回退到最近一次快照 */
    var info = currentSelectionInfo() || lastFB;
    if (!info) { hidePops(); return; }
    lastFB = info;
    if (action === 'delblk') { deleteBlockAt(info.idx); return; }
"""),
    # ---------- FMT-2：链接 toggle 取消（选区紧邻 [ 与 ](url) → 移除链接） ----------
    ("""    if (action === 'link') {
      hidePops();                              /* 先收起格式栏，再弹输入层 */
      openLinkPop(info, rawOff, rawLen);
      return;
    }
""",
     """    if (action === 'link') {
      /* v3.31.2（FMT-2）：已包裹链接 → toggle 取消（移除 [ 与 ](url)，保留文字），
         不再无条件再套一层（曾产生 [[x](u)](u) 嵌套垃圾且无法还原）。
         判定与 wrapSelection 的 toggle 同款：区间紧邻 [ 与 ](url) */
      var _ltxt = raw.slice(rawOff, rawOff + rawLen);
      if (raw.charAt(rawOff - 1) === '[') {
        var _mU = raw.slice(rawOff + rawLen).match(/^\\]\\(([^)\\n]*)\\)/);
        if (_mU) {
          state.raw[info.idx] = raw.slice(0, rawOff - 1) + _ltxt +
                               raw.slice(rawOff + rawLen + _mU[0].length);
          markDirty(); scheduleSnapshot(); rebuild();
          toastStatus('已移除链接');
          hidePops();
          return;
        }
      }
      hidePops();                              /* 先收起格式栏，再弹输入层 */
      openLinkPop(info, rawOff, rawLen);
      return;
    }
"""),
    # ---------- FMT-3：清除格式纳入链接外壳 ----------
    ("""    var markerChar = /[*_~`$=]/;
    while (a > 0 && markerChar.test(raw[a - 1])) a--;
    while (b < raw.length && markerChar.test(raw[b])) b++;
""",
     """    /* v3.31.2（FMT-3）：选区为链接文字时，把 [ 与 ](url) 外壳一并纳入清除范围
       （保留纯文字）—— 此前 markerChar 不含括号，链接清不掉（T× 失效）。
       先吸收链接外壳，再走通用标记吸附，**[x](u)** 等叠加场景一并解决 */
    var _lk = b <= raw.length ? raw.slice(b).match(/^\\]\\(([^)\\n]*)\\)/) : null;
    if (_lk && raw.charAt(a - 1) === '[') { a--; b += _lk[0].length; }
    var markerChar = /[*_~`$=]/;
    while (a > 0 && markerChar.test(raw[a - 1])) a--;
    while (b < raw.length && markerChar.test(raw[b])) b++;
"""),
]

with io.open(PATH, "r", encoding="utf-8") as f:
    txt = f.read()
for i, (old, new) in enumerate(PAIRS, 1):
    n = txt.count(old)
    if n != 1:
        print("FAIL pair#%d count=%d" % (i, n))
        sys.exit(1)
    txt = txt.replace(old, new)
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(txt)
print("OK %d patches applied" % len(PAIRS))
