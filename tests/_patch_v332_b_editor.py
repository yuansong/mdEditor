# -*- coding: utf-8 -*-
"""v3.32 editor.html 补丁：#15 懒渲染 + #18/#19 查找全部命中 + #7/#8 大纲数据增强 + CSS。幂等。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()

EDITS = []


def rep(old, new, n=1):
    EDITS.append((old, new, n))


# ---- E1) state 加 lazyBuild ----
rep("  var state = { raw: [''], editIdx: -1, dirty: false };",
    "  var state = { raw: [''], editIdx: -1, dirty: false, lazyBuild: false };   /* v3.31（#15）：lazyBuild 仅在 rebuild 全文构建期间为 true */")

# ---- E2) rebuild 懒渲染化 + 懒渲染引擎 ----
rep("""  function rebuild() {
    ED.textContent = '';
    for (var i = 0; i < state.raw.length; i++) ED.appendChild(blockEl(i));
    /* Mermaid 图表渲染回调为异步，且渲染时块可能尚未挂载，
       这里在整体挂载后补渲染一次（已渲染的块会被直接覆盖，无副作用） */
    renderMermaidIn(ED);
    applyFolds();
    applyFootnoteTips();
  }""",
    """  /* v3.31（#15）超长文档懒渲染阈值：块数达到该值时 rebuild 只建骨架，
     KaTeX / mermaid / 代码着色等重型增强由视口观察器按需补齐 */
  var LAZY_MIN = 400;
  function rebuild() {
    ED.textContent = '';
    state.lazyBuild = state.raw.length >= LAZY_MIN;
    for (var i = 0; i < state.raw.length; i++) ED.appendChild(blockEl(i));
    state.lazyBuild = false;   /* 单块插入 / 局部重建永远全量增强 */
    /* Mermaid 图表渲染回调为异步，且渲染时块可能尚未挂载，
       这里在整体挂载后补渲染一次（已渲染的块会被直接覆盖，无副作用）；
       懒渲染时跳过全局补渲染，由 lazySetup 按视口补齐 */
    if (!ED.querySelector('.blk[data-lazy]')) renderMermaidIn(ED);
    applyFolds();
    applyFootnoteTips();
    lazySetup();
  }
  /* ---------- v3.31（#15）懒渲染引擎：视口附近补齐重型增强 ---------- */
  var lazyObserver = null;
  function flushLazyEl(el) {
    if (!el || !el.getAttribute || !el.getAttribute('data-lazy')) return;
    el.removeAttribute('data-lazy');
    renderMathIn(el);
    renderMermaidIn(el);
    var pre = el.querySelector('pre.fence');
    if (pre) applyCodeEnhance(pre, false);
  }
  function flushLazyAll() {
    var els = ED.querySelectorAll('.blk[data-lazy]');
    for (var i = 0; i < els.length; i++) flushLazyEl(els[i]);
  }
  window.__lazyFlushAll = flushLazyAll;   /* 导出 / 测试前补齐 */
  window.__lazyCount = function () { return ED.querySelectorAll('.blk[data-lazy]').length; };
  function lazySetup() {
    if (lazyObserver) { lazyObserver.disconnect(); lazyObserver = null; }
    var els = ED.querySelectorAll('.blk[data-lazy]');
    if (!els.length) return;
    if (typeof IntersectionObserver === 'undefined') { flushLazyAll(); return; }
    lazyObserver = new IntersectionObserver(function (entries) {
      for (var k = 0; k < entries.length; k++) {
        if (entries[k].isIntersecting) {
          lazyObserver.unobserve(entries[k].target);
          flushLazyEl(entries[k].target);
        }
      }
    }, { rootMargin: '900px 0px' });
    for (var j = 0; j < els.length; j++) lazyObserver.observe(els[j]);
  }""")

# ---- E3) blockEl 懒渲染分支 ----
rep("""    div.innerHTML = blockHTML(state.raw[i]);
    resolveImgsIn(div);
    renderMathIn(div);
    renderMermaidIn(div);
    if (inf.type === 'table' || inf.type === 'htable') enhanceTable(div);
    else if (inf.type === 'fence') enhanceFence(div, i);
    else enhanceWysiwygBlock(div, i);""",
    """    div.innerHTML = blockHTML(state.raw[i]);
    resolveImgsIn(div);
    /* v3.31（#15）：懒渲染构建期跳过 KaTeX / mermaid / 着色（骨架与索引不受影响），
       块保留 data-lazy 标记，进视口后 flushLazyEl 补齐 */
    if (state.lazyBuild) {
      div.setAttribute('data-lazy', '1');
      if (inf.type === 'table' || inf.type === 'htable') enhanceTable(div);
      else if (inf.type === 'fence') enhanceFence(div, i, true);
      else enhanceWysiwygBlock(div, i);
    } else {
      renderMathIn(div);
      renderMermaidIn(div);
      if (inf.type === 'table' || inf.type === 'htable') enhanceTable(div);
      else if (inf.type === 'fence') enhanceFence(div, i);
      else enhanceWysiwygBlock(div, i);
    }""")

# ---- E4) applyCodeEnhance 签名 + 懒跳过 ----
rep("""  function applyCodeEnhance(pre, editing, idxHint) {
    if (!pre) return;""",
    """  function applyCodeEnhance(pre, editing, idxHint, lazy) {
    if (!pre) return;
    /* v3.31（#15）：懒渲染构建期不着色（hlCodeHTML 逐字符 tokenizer 是构建热点） */
    if (lazy) return;""")

# ---- E5) enhanceFence 签名 + 尾调用 ----
rep("  function enhanceFence(div, idxHint) {",
    "  function enhanceFence(div, idxHint, lazy) {   /* v3.31（#15）：lazy=构建期不着色 */")
rep("    applyCodeEnhance(pre, false, idxHint);\n  }",
    "    applyCodeEnhance(pre, false, idxHint, lazy);   /* v3.31（#15） */\n  }")

# ---- E6) getOutline：end + words ----
rep("""  window.getOutline = function () {
    var out = [];
    for (var i = 0; i < state.raw.length; i++) {
      var bi = blockInfo(state.raw[i]);
      if (bi.type && /^h[1-6]$/.test(bi.type)) {
        out.push({
          index: i,
          level: +bi.type[1],
          text: state.raw[i].replace(/^#{1,7}\\s+/, '').slice(0, 60)
        });
      }
    }
    return out;
  };""",
    """  window.getOutline = function () {
    var out = [], i;
    for (i = 0; i < state.raw.length; i++) {
      var bi = blockInfo(state.raw[i]);
      if (bi.type && /^h[1-6]$/.test(bi.type)) {
        out.push({
          index: i,
          level: +bi.type[1],
          text: state.raw[i].replace(/^#{1,7}\\s+/, '').slice(0, 60)
        });
      }
    }
    /* v3.31（#7/#8）：节结束块（下一同级/更高级标题处）+ 分节字数（非空白字符，
       前缀和一次累计，避免 O(块数×标题数) 重复统计） */
    var cum = [0];
    for (i = 0; i < state.raw.length; i++)
      cum.push(cum[i] + String(state.raw[i] || '').replace(/\\s+/g, '').length);
    for (var k = 0; k < out.length; k++) {
      var end = state.raw.length;
      for (var m = k + 1; m < out.length; m++) {
        if (out[m].level <= out[k].level) { end = out[m].index; break; }
      }
      out[k].end = end;
      out[k].words = cum[end] - cum[out[k].index];
    }
    return out;
  };""")

# ---- E7) reorderSections（插在 gotoHeading 之后）----
rep("""    setTimeout(function () { el.classList.remove('flash'); }, 1600);
  };
  /* ---------- 指定行号：跳转（Ctrl+G）与光标行列上报 ---------- */""",
    """    setTimeout(function () { el.classList.remove('flash'); }, 1600);
  };
  /* ---------- v3.31（#7）大纲拖拽调序：按新顺序整段重排同级章节 ----------
     pairs = [[start, end), ...]（新顺序）；各节必须首尾相接覆盖一段连续区间 */
  window.reorderSections = function (pairsJson) {
    var pairs;
    try { pairs = JSON.parse(pairsJson); } catch (e0) { return 'invalid'; }
    if (!Array.isArray(pairs) || pairs.length < 2) return 'invalid';
    if (state.editIdx >= 0 && editEl()) commitEditSilent();   /* 源码编辑态先落回 */
    var n = state.raw.length, lo = -1, hi = -1, prev = -1, k;
    for (k = 0; k < pairs.length; k++) {
      var s = +pairs[k][0], e = +pairs[k][1];
      if (!(s >= 0 && e > s && e <= n)) return 'invalid';
      if (prev >= 0 && s !== prev) return 'invalid';   /* 不连续（跨级 / 缓存过期） */
      if (lo < 0) lo = s;
      prev = e;
      hi = e;
    }
    var mid = [];
    for (var j = 0; j < pairs.length; j++)
      mid = mid.concat(state.raw.slice(+pairs[j][0], +pairs[j][1]));
    state.raw = state.raw.slice(0, lo).concat(mid, state.raw.slice(hi));
    rebuild();
    markDirty();
    scheduleSnapshot();
    return 'ok';
  };
  /* ---------- 指定行号：跳转（Ctrl+G）与光标行列上报 ---------- */""")

# ---- E8) findAll / findClearHits / gotoMatch（插在 findCount 之后）----
rep("""  window.findCount = function (q, cs, regex) {
    var sep = '\\n\\n';
    var abs = '';
    for (var i = 0; i < state.raw.length; i++) abs += state.raw[i] + sep;
    var rx = buildRegex(q, !!cs, !!regex, true);
    return rx ? countMatchesIn(abs, rx) : 0;
  };""",
    """  window.findCount = function (q, cs, regex) {
    var sep = '\\n\\n';
    var abs = '';
    for (var i = 0; i < state.raw.length; i++) abs += state.raw[i] + sep;
    var rx = buildRegex(q, !!cs, !!regex, true);
    return rx ? countMatchesIn(abs, rx) : 0;
  };
  /* ---------- v3.31（#18/#19）查找全部命中：全文高亮 + 命中列表 ----------
     高亮用 CSS Custom Highlight API（Range 不改 DOM、不污染存储、编辑时自动跟随）；
     不支持该 API 时返回 hl:false，命中列表跳转仍可用 */
  var FIND_HL = 'find-hit';
  function makeHitRange(nodes, offs, a, b) {
    var r = document.createRange();
    var k = 0;
    while (k < nodes.length - 1 && offs[k + 1] <= a) k++;
    r.setStart(nodes[k], Math.min(a - offs[k], nodes[k].length));
    var k2 = k;
    while (k2 < nodes.length - 1 && offs[k2 + 1] < b) k2++;
    r.setEnd(nodes[k2], Math.min(b - offs[k2], nodes[k2].length));
    return r;
  }
  window.findAll = function (q, cs, regex, limit) {
    limit = Math.max(1, +limit || 500);
    window.findClearHits();
    var rx = buildRegex(q, !!cs, !!regex, true);
    if (!rx || !q) return JSON.stringify({ count: 0, matches: [] });
    var srcMode = !!document.querySelector('.raw-edit.t-src');
    var supportsHL = false;
    try { supportsHL = !srcMode && typeof Highlight !== 'undefined' && !!CSS.highlights; } catch (e0) {}
    var ranges = supportsHL ? [] : null;
    var matches = [], total = 0;
    function pushMatch(bi, full, idx, len) {
      total++;
      if (matches.length >= limit) return;
      var s0 = Math.max(0, idx - 30), e0 = Math.min(full.length, idx + len + 30);
      matches.push({ i: bi, off: idx,
        prev: (s0 > 0 ? '…' : '') + full.slice(s0, e0).replace(/\\s+/g, ' ').trim() +
              (e0 < full.length ? '…' : '') });
    }
    if (srcMode) {
      /* 源码模式：渲染 DOM 是整体源码框，按 state.raw 统计（无高亮） */
      for (var si = 0; si < state.raw.length; si++) {
        var stext = String(state.raw[si] || '');
        rx.lastIndex = 0;
        var sm;
        while ((sm = rx.exec(stext)) !== null) {
          if (!sm[0].length) { rx.lastIndex++; continue; }
          pushMatch(si, stext, sm.index, sm[0].length);
          if (total >= limit) break;
        }
        if (total >= limit) break;
      }
      return JSON.stringify({ count: total, matches: matches, hl: false });
    }
    for (var i = 0; i < ED.children.length; i++) {
      var blk = ED.children[i];
      if (blk.classList.contains('raw-edit')) continue;
      var nodes = [], texts = [];
      var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT, null);
      var tn;
      while ((tn = w.nextNode()))
        if ((tn.nodeValue || '').length) { nodes.push(tn); texts.push(tn.nodeValue); }
      if (!nodes.length) continue;
      var full = texts.join(''), offs = null;
      rx.lastIndex = 0;
      var m;
      while ((m = rx.exec(full)) !== null) {
        if (!m[0].length) { rx.lastIndex++; continue; }
        if (total >= limit) break;   /* 达上限即停（统计同样封顶） */
        if (!offs) {
          offs = [0];
          for (var x = 0; x < texts.length; x++) offs.push(offs[x] + texts[x].length);
        }
        if (ranges) {
          try { ranges.push(makeHitRange(nodes, offs, m.index, m.index + m[0].length)); } catch (e1) {}
        }
        pushMatch(i, full, m.index, m[0].length);
      }
      if (total >= limit) break;
    }
    if (ranges && ranges.length) {
      try { CSS.highlights.set(FIND_HL, new Highlight(...ranges)); } catch (e2) {}
    }
    return JSON.stringify({ count: total, matches: matches, hl: !!(ranges && ranges.length) });
  };
  window.findClearHits = function () {
    try { CSS.highlights.delete(FIND_HL); } catch (e) {}
  };
  window.gotoMatch = function (bi, _off) {
    /* 块级定位（与 gotoHeading 同款滚动 + flash）；命中文字由高亮自行标示 */
    var el = ED.children[bi];
    if (!el) return 'err';
    el.scrollIntoView({ block: 'center' });
    el.classList.remove('flash');
    void el.offsetWidth;
    el.classList.add('flash');
    setTimeout(function () { el.classList.remove('flash'); }, 1600);
    return 'ok';
  };""")

# ---- E9) 导出前补齐懒渲染 ----
rep("""  window.getExportHTML = function () {
    var css = document.getElementById('app-style').textContent;""",
    """  window.getExportHTML = function () {
    flushLazyAll();   /* v3.31（#15）：懒渲染块先补齐（图表 SVG / 公式已渲染） */
    var css = document.getElementById('app-style').textContent;""")

# ---- E10) CSS：命中高亮（浅色） ----
rep(".fn-flash { background: #ffe9a8 !important; border-radius: 3px; transition: background 1.1s ease; }",
    """.fn-flash { background: #ffe9a8 !important; border-radius: 3px; transition: background 1.1s ease; }
/* v3.31（#18）：查找全部命中高亮（CSS Custom Highlight API，不改 DOM） */
#editor ::highlight(find-hit) { background: #ffe08a; color: inherit; }""")

# ---- E11) CSS：命中高亮（深色系主题） ----
rep('body[data-theme="dark"] mark { background: #8a7a1e; color: #fff; }',
    '''body[data-theme="dark"] mark { background: #8a7a1e; color: #fff; }
/* v3.31（#18）：命中高亮深色系配色 */
body[data-theme="dark"] #editor ::highlight(find-hit),
body[data-theme="night"] #editor ::highlight(find-hit),
body[data-theme="panda"] #editor ::highlight(find-hit) { background: #6b5416; color: #ffe9a8; }''')

fail = [i for i, (o, nw, n) in enumerate(EDITS) if src.count(o) != n]
if fail:
    for i in fail:
        print("ANCHOR FAIL #%d count=%d" % (i, src.count(EDITS[i][0])))
    sys.exit(1)
for o, nw, _n in EDITS:
    src = src.replace(o, nw)

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("editor.html patched: %d edits" % len(EDITS))
