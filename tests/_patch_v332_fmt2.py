# -*- coding: utf-8 -*-
"""v3.31.2 FMT 修复二轮：修 m81 复跑暴露的 3 处判定缺陷

G1: FMT-1 守卫改用 intersectsNode —— 列表整项选区（selectNodeContents(li)）的
    起点 container 是 li 元素而非 code 内文本节点，closest 探测不到；
G2: FMT-2 toggle 判定适配 idx===L → n.re 语义（映射区间尾含 ](url)）；
G3: FMT-3 链接外壳吸附同样适配两种映射形态（尾含 / 尾不含 ](url)）。
"""
import io
import sys

PATH = r"E:\WorkBuddy\md-editor\src\editor.html"

PAIRS = [
    # ---------- G1 ----------
    ("""    if (action === 'bold' || action === 'italic' || action === 'strike' ||
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
""",
     """    if (action === 'bold' || action === 'italic' || action === 'strike' ||
        action === 'mark' || action === 'link') {
      var _sel = getSelection();
      if (_sel && _sel.rangeCount) {
        var _sc = _sel.getRangeAt(0).startContainer;
        var _pe = _sc.nodeType === 1 ? _sc : _sc.parentElement;
        var _pb = _pe && _pe.closest ? _pe.closest('#editor .blk') : null;
        /* 用 intersectsNode 而非 closest：列表整项选区（selectNodeContents(li)）
           的起点 container 是 li 元素，code 是它的子节点 —— closest 探测不到，
           必须判定选区是否与块内任一 <code> 相交 */
        if (_pb && _pb.querySelectorAll) {
          var _codes = _pb.querySelectorAll('code');
          for (var _ci = 0; _ci < _codes.length; _ci++) {
            var _hit = false;
            try { _hit = _sel.getRangeAt(0).intersectsNode(_codes[_ci]); } catch (e1) {}
            if (_hit) {
              toastStatus('行内代码内不支持叠加行内格式（可点 T× 连码壳一起清除）');
              hidePops();
              return;
            }
          }
        }
      }
    }
"""),
    # ---------- G2 ----------
    ("""      var _ltxt = raw.slice(rawOff, rawOff + rawLen);
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
""",
     """      var _ltxt = raw.slice(rawOff, rawOff + rawLen);
      /* plainToRawOffset 在 idx===L 时返回 n.re（整个链接的结尾）—— 全选链接
         文字时映射区间尾含 ](url)，先剥出来拿纯文字；再认定 [左邻 + 尾] 即可 */
      var _mE = _ltxt.match(/\\]\\(([^)\\n]*)\\)$/);
      var _inner = _mE ? _ltxt.slice(0, _mE.index) : _ltxt;
      var _mU = _mE ? _mE : raw.slice(rawOff + rawLen).match(/^\\]\\(([^)\\n]*)\\)/);
      if (_mU && _inner && raw.charAt(rawOff - 1) === '[') {
        state.raw[info.idx] = raw.slice(0, rawOff - 1) + _inner +
                             raw.slice(rawOff + rawLen + (_mE ? 0 : _mU[0].length));
        markDirty(); scheduleSnapshot(); rebuild();
        toastStatus('已移除链接');
        hidePops();
        return;
      }
"""),
    # ---------- G3 ----------
    ("""    var _lk = b <= raw.length ? raw.slice(b).match(/^\\]\\(([^)\\n]*)\\)/) : null;
    if (_lk && raw.charAt(a - 1) === '[') { a--; b += _lk[0].length; }
""",
     """    var _slk = raw.slice(a, b);
    var _mE3 = _slk.match(/\\]\\(([^)\\n]*)\\)$/);   /* 映射尾含 ](url) 形态 */
    var _lk = raw.slice(b).match(/^\\]\\(([^)\\n]*)\\)/);   /* 尾不含形态 */
    if (raw.charAt(a - 1) === '[' && _mE3) { a--; }
    else if (_lk && raw.charAt(a - 1) === '[') { a--; b += _lk[0].length; }
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
