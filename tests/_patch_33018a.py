# -*- coding: utf-8 -*-
"""v3.30.18a 补丁：P1 批次（清单 v3.30.11 第六章批次 1+2）
- LIST-1 根修：currentSelectionInfo 行感知偏移（lineAwarePlain/lineAwarePoint）
- LIST-1 止血：applyFloatAction 跨行区间拒绝包裹 + toast
- LIST-2 / QUO-1 / DL-2 止血：渲染层含行内格式渲染产物时点击转源码编辑；
  sync* 回写守卫（宁可不存新字符也不丢格式）
- LIST-3：setMarkdown 清 lastFB
每处替换恰好命中 1 次，失败即中止。"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
with io.open(P, "r", encoding="utf-8") as f:
    src = f.read()

def rep(old, new, tag):
    global src
    n = src.count(old)
    if n != 1:
        print("FAIL %s: match count = %d" % (tag, n))
        sys.exit(1)
    src = src.replace(old, new)
    print("ok", tag)

# ---------- 1. 新函数组：行感知序列化 + 渲染层富格式检测 ----------
NEW_FUNCS = r'''  /* =========================================================
   v3.30.18（LIST-1 根修）：行感知的块内纯文本序列化。
   Range.toString() 在块级元素（li / dt / dd / tr / br 等）边界不插入任何
   分隔符，而 mapPlainToRaw / lineWalker 的行分隔模型是「行间恰好 1 个字符」
   （idx -= L + 1）—— 多行块从第 2 行起选区映射全部错位（格式套到上一行 /
   字面 == 污染，即 LIST-1）。这里按渲染层 DOM 手工序列化：行级边界输出
   '\n'，并记录每个文本节点与元素子节点间隙的位置，供 Range 端点
   (node, offset) → plain 偏移映射。 */
  function lineAwarePlain(blk) {
    var text = '';
    var marks = [];   /* 文本节点 → {node, start, end} */
    var gaps = [];    /* 元素节点 → 每个子节点间隙的位置（按 child 索引） */
    function endsNL() { return text.length > 0 && text.charAt(text.length - 1) === '\n'; }
    function rowBreak() { if (text.length && !endsNL()) text += '\n'; }
    function isRow(n) {
      return n.tagName === 'LI' || n.tagName === 'DT' || n.tagName === 'DD' || n.tagName === 'TR';
    }
    function isBlk(n) {
      return /^(P|DIV|H[1-6]|TABLE|THEAD|TBODY|TFOOT|UL|OL|BLOCKQUOTE|FIGURE|DL)$/.test(n.tagName);
    }
    function walk(n) {
      if (n.nodeType === 3) {
        marks.push({ node: n, start: text.length, end: text.length + n.nodeValue.length });
        text += n.nodeValue;
        return;
      }
      if (n.nodeType !== 1) return;
      if (n.tagName === 'BR') { text += '\n'; return; }
      if (n.classList && n.classList.contains('qblk')) {
        /* 引用内嵌富块：raw 中占 k 行 → plain 里贡献 k 个行分隔（行内容长度
           与渲染层对不上，但 qblk 不可编辑、端点不会落在其中，只求其后行
           偏移不被拉偏） */
        var kq = (n.getAttribute('data-raw') || '').split('\n').length;
        rowBreak();
        for (var q = 0; q < kq; q++) text += '\n';
        return;
      }
      if (isRow(n) || isBlk(n)) rowBreak();   /* 新行开始：与前文之间补 1 个分隔 */
      var g = n.childNodes.length ? [] : null;
      if (g) gaps.push({ node: n, arr: g });
      var kids = n.childNodes;
      for (var k = 0; k < kids.length; k++) {
        var c = kids[k];
        if (c.nodeType === 1 && c.tagName !== 'BR' && (isRow(c) || isBlk(c))) rowBreak();
        if (g) g.push({ off: k, pos: text.length });
        walk(c);
      }
      if (g) g.push({ off: kids.length, pos: text.length });
    }
    walk(blk);
    return { text: text, marks: marks, gaps: gaps };
  }
  function lineAwarePoint(ctx, node, offset) {
    var i, m;
    if (node.nodeType === 3) {
      for (i = 0; i < ctx.marks.length; i++) {
        m = ctx.marks[i];
        if (m.node === node) return Math.min(m.end, m.start + Math.max(0, offset));
      }
      return -1;
    }
    for (i = 0; i < ctx.gaps.length; i++) {
      if (ctx.gaps[i].node === node) {
        var arr = ctx.gaps[i].arr;
        for (var j = 0; j < arr.length; j++) {
          if (arr[j].off === offset) return arr[j].pos;
        }
        return arr.length ? arr[arr.length - 1].pos : -1;
      }
    }
    return -1;
  }
  function currentSelectionInfo() {'''

rep("  function currentSelectionInfo() {", NEW_FUNCS, "newfuncs+csi")

# ---------- 2. currentSelectionInfo 改用行感知偏移 ----------
rep(r'''    var pre = document.createRange();
    pre.selectNodeContents(el);
    try { pre.setEnd(r.startContainer, r.startOffset); } catch (e2) { return null; }
    var plainOff = pre.toString().length;
    var plainLen = r.toString().length;
    if (!plainLen) return null;''',
r'''    /* v3.30.18（LIST-1 根修）：行感知偏移 —— 裸 Range.toString() 在块级边界
       不插分隔符，多行块第 2 行起映射错位；映射失败时回退旧逻辑兜底 */
    var laCtx = lineAwarePlain(el);
    var laPo = lineAwarePoint(laCtx, r.startContainer, r.startOffset);
    var laPe = lineAwarePoint(laCtx, r.endContainer, r.endOffset);
    var plainOff, plainLen;
    if (laPo >= 0 && laPe >= laPo) {
      plainOff = laPo; plainLen = laPe - laPo;
    } else {
      var pre = document.createRange();
      pre.selectNodeContents(el);
      try { pre.setEnd(r.startContainer, r.startOffset); } catch (e2) { return null; }
      plainOff = pre.toString().length;
      plainLen = r.toString().length;
    }
    if (!plainLen) return null;''', "csi-lineaware")

# ---------- 3. applyFloatAction 跨行守卫 ----------
rep(r'''      rawLen = Math.max(1, rawEnd - rawOff);
    }''',
r'''      /* v3.30.18（LIST-1 止血）：CommonMark 行内标记不可跨行 —— 映射区间含
         换行说明选区跨列表项 / 引用行，包裹必然产生跨行脏标记（上一行尾 ==
         与前格式收尾连成 ====）。拒绝应用并提示，杜绝脏 raw 落盘 */
      if (raw.slice(rawOff, rawEnd).indexOf('\n') >= 0) {
        toastStatus('不支持跨行 / 跨项应用行内格式，请逐行选择后再试');
        hidePops();
        return;
      }
      rawLen = Math.max(1, rawEnd - rawOff);
    }''', "crossline-guard")

# ---------- 4. setMarkdown 清 lastFB（LIST-3） ----------
rep(r'''    state.raw = splitBlocks(text || '');
    undoStack = []; redoStack = [];''',
r'''    state.raw = splitBlocks(text || '');
    lastFB = null;          /* v3.30.18（LIST-3）：换文档清掉选区快照，防跨文档残留 */
    undoStack = []; redoStack = [];''', "lastfb-reset")

# ---------- 5. 渲染层富格式检测 + 点击转源码（QUO-1 / LIST-2 主入口止血） ----------
rep(r'''  function enterEdit(i, plainOff) {''',
r'''  /* v3.30.18（QUO-1 / LIST-2 主入口止血）：渲染层直编元素（标题 / 列表项 /
     引用 / 定义列表）含行内格式渲染产物（strong / mark / a / code…）时，
     纯文本回写（syncListLi / syncHeadingEl / syncQuoteEl / syncDeflistEl）
     会静默剥掉行内标记 —— 不可逆数据丢失。点击这类内容时转入源码态编辑
     （像代码区一样显示源码标记，失焦再渲染），对齐清单 QUO-1 短期方案。 */
  function wysHasInlineRich(el) {
    var bad = el.querySelectorAll('strong,em,mark,del,code,a,img,.inlinemath,.cell-math');
    for (var i = 0; i < bad.length; i++) {
      if (bad[i].closest && !bad[i].closest('.qblk')) return true;
    }
    return false;
  }
  function wysClickToRaw(e) {
    if (window.__previewLock) return;
    if (e.button !== 0) return;
    var t = e.target.closest ? e.target.closest(
      '#editor li,#editor h1,#editor h2,#editor h3,#editor h4,#editor h5,#editor h6,#editor blockquote,#editor dt,#editor dd') : null;
    if (!t) return;
    if (t.getAttribute('contenteditable') !== 'plaintext-only') return;
    if (t.closest('.qblk')) return;
    /* 拖选（选区非空）不拦：保留「渲染态拖选 + 悬浮栏格式化」链路（其正确性
       由 LIST-1 根修 / 跨行守卫保证）；这里只拦「点击进光标编辑」入口 */
    if (!selCollapsed()) return;
    var probe = t;
    if (t.tagName === 'LI') {
      probe = t.cloneNode(true);
      var subs = probe.querySelectorAll('ul,ol');
      for (var s = 0; s < subs.length; s++) subs[s].parentNode.removeChild(subs[s]);
    }
    if (!wysHasInlineRich(probe)) return;
    var blk = t.closest('.blk');
    var bi = blockIndexOf(blk);
    if (bi < 0) return;
    var lines = (state.raw[bi] || '').split('\n');
    var plain = 1e9;
    if (t.tagName === 'LI' && t.getAttribute('data-line') != null) {
      /* 块级 plain 基 = 前面各行（剥前缀后的渲染文本长 + 1 个行分隔） */
      var lineNo = +t.getAttribute('data-line'), base = 0;
      for (var k = 0; k < lineNo && k < lines.length; k++) {
        var s2 = lines[k].replace(/^(\s*)(?:[-*+]|\d+[.)])[ \t]*/, '');
        var tm = s2.match(/^\[([ xX])\][ \t]*/);
        if (tm) s2 = s2.slice(tm[0].length);
        base += inlinePlainLen(s2) + 1;
      }
      plain = base + caretRawOffset(t);
    } else if (/^H[1-6]$/.test(t.tagName) || t.tagName === 'BLOCKQUOTE') {
      plain = caretRawOffset(t);
    } else if (t.tagName === 'DT' || t.tagName === 'DD') {
      var base2 = 0, dlEl = t.parentNode, rowIdx = 0;
      for (var c2 = 0; c2 < dlEl.children.length; c2++) {
        if (dlEl.children[c2] === t) break;
        rowIdx++;
      }
      for (var k2 = 0; k2 < rowIdx && k2 < lines.length; k2++) {
        base2 += inlinePlainLen(lines[k2].replace(/^\s*:\s+/, '')) + 1;
      }
      plain = base2 + caretRawOffset(t);
    }
    enterEdit(bi, plain);
    toastStatus('该内容含行内格式，已转入源码编辑以保护格式（失焦恢复渲染）');
  }
  ED.addEventListener('click', wysClickToRaw, true);
  function enterEdit(i, plainOff) {''', "click-to-raw")

# ---------- 6. syncHeadingEl 守卫 ----------
rep(r'''  function syncHeadingEl(hEl) {
    var blk = hEl.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;
    var text = hEl.textContent.replace(/\u00a0/g, ' ');''',
r'''  function syncHeadingEl(hEl) {
    var blk = hEl.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;
    /* v3.30.18（QUO-1 标题侧止血）：含行内格式渲染产物时纯文本回写剥标记 */
    if (wysHasInlineRich(hEl)) return;
    var text = hEl.textContent.replace(/\u00a0/g, ' ');''', "sync-heading")

# ---------- 7. syncQuoteEl 守卫 ----------
rep(r'''  function syncQuoteEl(bq) {
    var blk = bq.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;
    var ls = quoteLinesFromDom(bq);''',
r'''  function syncQuoteEl(bq) {
    var blk = bq.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;
    /* v3.30.18（QUO-1 止血）：含行内格式渲染产物时纯文本回写剥标记 */
    if (wysHasInlineRich(bq)) return;
    var ls = quoteLinesFromDom(bq);''', "sync-quote")

# ---------- 8. syncListLi 守卫 ----------
rep(r'''    var lm = lines[lineNo].match(/^(\s*)(?:([-*+])|(\d+)([.)]))[ \t]*/);
    var prefix = lm ? (lm[1] + (lm[2] ? lm[2] + ' ' : lm[3] + lm[4] + ' ')) : '';
    var text = liPlainText(li);''',
r'''    var lm = lines[lineNo].match(/^(\s*)(?:([-*+])|(\d+)([.)]))[ \t]*/);
    var prefix = lm ? (lm[1] + (lm[2] ? lm[2] + ' ' : lm[3] + lm[4] + ' ')) : '';
    /* v3.30.18（LIST-2 止血）：含行内格式渲染产物时纯文本回写剥标记
       （宁可不存新字符也不丢格式）；嵌套子列表不算本行内容 */
    var probeLi = li.cloneNode(true);
    var subLis = probeLi.querySelectorAll('ul,ol');
    for (var sl = 0; sl < subLis.length; sl++) subLis[sl].parentNode.removeChild(subLis[sl]);
    if (wysHasInlineRich(probeLi)) return;
    var text = liPlainText(li);''', "sync-list")

# ---------- 9. syncDeflistEl 守卫 ----------
rep(r'''  function syncDeflistEl(el) {
    var dl = el.closest ? el.closest('dl') : null;
    if (!dl) return;
    var blk = dl.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;''',
r'''  function syncDeflistEl(el) {
    var dl = el.closest ? el.closest('dl') : null;
    if (!dl) return;
    var blk = dl.closest('.blk');
    var i = blockIndexOf(blk);
    if (i < 0) return;
    /* v3.30.18（DL-2 止血）：含行内格式渲染产物时纯文本回写剥标记 */
    if (wysHasInlineRich(el)) return;''', "sync-deflist")

with io.open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("ALL PATCHED")
