# -*- coding: utf-8 -*-
"""v3.30.19 批次 A：CSS + CODE-4/5/6 + QUO-2/3/4/6/7 + HR-6 + MATH-6 + U1/2/3/4/6 + D2/D3/D8"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()
fails = []
applied = []

def rep(tag, old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        fails.append("%s: expect %d hit(s), got %d" % (tag, cnt, n))
        return
    src = src.replace(old, new)
    applied.append(tag)

# ---------- 1) CSS：IMG-5 对齐 / FN-3 高亮 / U3 退场 ----------
rep("css", """.md-fig figcaption[contenteditable]:focus { outline: 1px dashed var(--accent); border-radius: 3px; }""",
""".md-fig figcaption[contenteditable]:focus { outline: 1px dashed var(--accent); border-radius: 3px; }
/* v3.30.19（IMG-5）：图片对齐（随 figure class 持久化；默认居中） */
.md-fig.fig-l { text-align: left; }
.md-fig.fig-r { text-align: right; }
/* v3.30.19（FN-3）：脚注跳转落点高亮 */
.fn-flash { background: #ffe9a8 !important; border-radius: 3px; transition: background 1.1s ease; }
/* v3.30.19（U3）：浮层退场淡出（尊重 prefers-reduced-motion） */
.pop.hiding { display: block; opacity: 0; transition: opacity .09s ease; pointer-events: none; }
@media (prefers-reduced-motion: reduce) { .pop.hiding { transition: none; } }""")

# ---------- 2) CODE-4：fenceInfoLine 支持 st ----------
rep("fenceInfoLine-order", """    var parts = [lang];
    var order = ['w', 'h', 'cap', 'captop'];""",
"""    var parts = [lang];
    var order = ['w', 'h', 'cap', 'captop', 'st'];   /* v3.30.19（CODE-4）：st= 单块风格落围栏 info */""")
rep("fenceInfoLine-st", """      if (k === 'captop') { parts.push('captop'); return; }""",
"""      if (k === 'captop') { parts.push('captop'); return; }
      if (k === 'st') { parts.push('st=' + String(v).replace(/[^\\w-]/g, '')); return; }   /* v3.30.19（CODE-4） */""")

# ---------- 3) CODE-4：applyCodeEnhance 风格解析 ----------
rep("applyCodeEnhance-style", """    /* 风格：全局偏好（会话内可用代码栏「风格」按钮对当前块临时覆盖） */
    var st = pre.parentNode.className.match(/st-(\\w+)/);
    var style = st ? st[1] : CODE_PREFS.style;""",
"""    /* 风格：围栏 info 属性 st= 优先（v3.30.19 CODE-4：单块风格持久化），
       其次 DOM 类（会话内切换未回写时），再次全局偏好 */
    var stAttr = idx >= 0 ? parseFenceInfo(String(state.raw[idx] || '').split('\\n')[0]).attrs.st : null;
    var st = pre.parentNode.className.match(/st-(\\w+)/);
    var style = stAttr ? String(stAttr) : (st ? st[1] : CODE_PREFS.style);""")

# ---------- 4) CODE-4：风格弹层点击回写 raw ----------
rep("stylepop-click", """    if (cb) {
      var pre = cb.querySelector('pre.fence');
      cb.className = 'codeblock' + (it.getAttribute('data-st') !== 'classic' ? ' st-' + it.getAttribute('data-st') : '');
      if (pre) applyCodeEnhance(pre, false);
    }""",
"""    if (cb) {
      var pre = cb.querySelector('pre.fence');
      var stSel = it.getAttribute('data-st');
      cb.className = 'codeblock' + (stSel !== 'classic' ? ' st-' + stSel : '');
      /* v3.30.19（CODE-4）：单块风格写入围栏 info 属性（st=xxx），rebuild 后不丢 */
      var blkS = cb.closest('.blk');
      var idxS = blkS ? blockIndexOf(blkS) : -1;
      if (idxS >= 0) {
        var linesS = String(state.raw[idxS] || '').split('\\n');
        var fiS = parseFenceInfo(linesS[0]);
        var atS = fiS.attrs || {};
        atS.st = stSel;
        linesS[0] = fenceInfoLine(fiS.lang, atS);
        state.raw[idxS] = linesS.join('\\n');
        markDirty(); scheduleSnapshot();
      }
      if (pre) applyCodeEnhance(pre, false);
    }""")

# ---------- 5) CODE-4：buildStylePop 当前风格读围栏属性 ----------
rep("buildStylePop-cur", """    var cur = (cb.className.match(/st-(\\w+)/) || [])[1] || 'classic';""",
"""    var blkB = cb.closest('.blk');
    var idxB = blkB ? blockIndexOf(blkB) : -1;
    var attrB = idxB >= 0 ? parseFenceInfo(String(state.raw[idxB] || '').split('\\n')[0]).attrs.st : null;
    var cur = attrB ? String(attrB) : ((cb.className.match(/st-(\\w+)/) || [])[1] || 'classic');   /* v3.30.19（CODE-4） */""")

# ---------- 6) CODE-5：syncCodeBlock 保留首行 + 尾空行 ≤2 ----------
rep("syncCodeBlock-head", """    var lang = (state.raw[idx].split('\\n')[0].match(/^```(.*)$/) || ['', ''])[1];
    var text = codeEl.textContent.replace(/\\n+$/, '');""",
"""    /* v3.30.19（CODE-5）：首行原样保留（语言 + info 属性不丢）；尾部空行保留 ≤2 个 */
    var firstC = String(state.raw[idx] || '').split('\\n')[0] || '```';
    var trailC = (codeEl.textContent.match(/\\n*$/) || [''])[0].length;
    if (trailC > 2) trailC = 2;
    var text = codeEl.textContent.replace(/\\n+$/, '') + (trailC ? new Array(trailC + 1).join('\\n') : '');""")
rep("syncCodeBlock-write", """    state.raw[idx] = '```' + lang + '\\n' + text + '\\n```';""",
"""    state.raw[idx] = firstC + '\\n' + text + '\\n```';""")

# ---------- 7) CODE-6：选区 Tab 批量缩进 ----------
rep("code-tab", """    } else if (e.key === 'Tab') {
      e.preventDefault();
      insertTextAtCaret('  ');
      syncCodeBlock(code);
    }
  });""",
"""    } else if (e.key === 'Tab') {
      e.preventDefault();
      /* v3.30.19（CODE-6）：选区跨行时整段批量缩进 / 反缩进（行首批两空格） */
      var selC6 = getSelection();
      var rC6 = selC6.rangeCount ? selC6.getRangeAt(0) : null;
      var codeText6 = code.textContent || '';
      var offS6 = -1, offE6 = -1;
      if (rC6 && !rC6.collapsed) {
        var rs6 = document.createRange();
        rs6.selectNodeContents(code);
        try { rs6.setEnd(rC6.startContainer, rC6.startOffset); } catch (eS6) { rs6 = null; }
        var re6b = document.createRange();
        re6b.selectNodeContents(code);
        try { re6b.setEnd(rC6.endContainer, rC6.endOffset); } catch (eE6) { re6b = null; }
        if (rs6 && re6b) { offS6 = rs6.toString().length; offE6 = re6b.toString().length; }
      }
      if (offS6 < 0 || offE6 < 0 || codeText6.slice(Math.min(offS6, offE6), Math.max(offS6, offE6)).indexOf('\\n') === -1) {
        insertTextAtCaret('  ');
        syncCodeBlock(code);
        return;
      }
      var ls6 = codeText6.split('\\n');
      var sLine6 = codeText6.slice(0, offS6).split('\\n').length - 1;
      var eLine6 = codeText6.slice(0, offE6).split('\\n').length - 1;
      var oldStarts6 = [], acc6 = 0, k6;
      for (k6 = 0; k6 < ls6.length; k6++) { oldStarts6.push(acc6); acc6 += ls6[k6].length + 1; }
      var chg6 = [];
      for (k6 = 0; k6 < ls6.length; k6++) chg6.push(0);
      for (k6 = sLine6; k6 <= eLine6 && k6 < ls6.length; k6++) {
        if (e.shiftKey) {
          var rm6 = (ls6[k6].match(/^ {1,2}/) || [''])[0].length;
          if (rm6) { ls6[k6] = ls6[k6].slice(rm6); chg6[k6] = -rm6; }
        } else if (ls6[k6] !== '') {
          ls6[k6] = '  ' + ls6[k6]; chg6[k6] = 2;
        }
      }
      code.textContent = ls6.join('\\n');
      var newStarts6 = [], acc7 = 0;
      for (k6 = 0; k6 < ls6.length; k6++) { newStarts6.push(acc7); acc7 += ls6[k6].length + 1; }
      var mapOff6 = function (o6) {
        var L6 = 0;
        while (L6 + 1 < oldStarts6.length && oldStarts6[L6 + 1] <= o6) L6++;
        var col6 = Math.max(0, o6 - oldStarts6[L6]);
        var nc6 = Math.min(Math.max(0, col6 + chg6[L6]), ls6[L6].length);
        return newStarts6[L6] + nc6;
      };
      var nS6 = mapOff6(Math.min(offS6, offE6)), nE6 = mapOff6(Math.max(offS6, offE6));
      syncCodeBlock(code);
      setCaretSel(code, nS6, Math.max(0, nE6 - nS6));
    }
  });""")

# ---------- 8) QUO-7：受限文案统一 ----------
rep("quo7-title", """'" title="引用内的表格 / 代码块暂不支持直接编辑（双击转入源码态修改）">'""",
"""'" title="引用内的富内容块暂不支持直接编辑（双击转入源码态修改）">'""")
rep("quo7-toast", """    toastStatus('引用内的表格 / 代码块暂不支持直接编辑，双击可转入源码态修改');""",
"""    toastStatus('引用内的富内容块暂不支持直接编辑，双击可转入源码态修改');""")

# ---------- 9) QUO-2：quoteAppendBlock 按光标行插入 ----------
rep("quoteAppendBlock", """  function quoteAppendBlock(i, blockRaw) {
    var cur = String(state.raw[i] || '').split('\\n');
    while (cur.length && /^\\s*(?:>[^\\S\\n]?)*\\s*$/.test(cur[cur.length - 1])) cur.pop();
    var adds = String(blockRaw || '').split('\\n').map(function (l) { return l ? '> ' + l : '>'; });
    state.raw[i] = cur.concat(adds).join('\\n');""",
"""  function quoteAppendBlock(i, blockRaw, atLine) {
    var cur = String(state.raw[i] || '').split('\\n');
    while (cur.length && /^\\s*(?:>[^\\S\\n]?)*\\s*$/.test(cur[cur.length - 1])) cur.pop();
    var adds = String(blockRaw || '').split('\\n').map(function (l) { return l ? '> ' + l : '>'; });
    /* v3.30.19（QUO-2）：光标在引用内时按光标行之后插入（不再固定块尾）；
       含内嵌富块（.qblk）的引用行模型与 DOM 不一致，维持追加块尾 */
    var atQ = cur.length;
    var selQ2 = getSelection();
    var qEl2 = ED.children[i] && ED.children[i].querySelector('blockquote');
    if (atLine != null && atLine >= 0 && atLine <= cur.length) {
      atQ = atLine;
    } else if (qEl2 && selQ2.rangeCount && !qEl2.querySelector('.qblk')) {
      var ancQ = selQ2.getRangeAt(0).startContainer;
      if (ancQ && qEl2.contains(ancQ.nodeType === 1 ? ancQ : ancQ.parentNode)) {
        var liQ = quoteText(qEl2).slice(0, quoteCaretOff(qEl2)).split('\\n').length - 1;
        if (liQ >= 0 && liQ < cur.length) atQ = liQ + 1;
      }
    }
    var argsQ = [atQ, 0].concat(adds);
    cur.splice.apply(cur, argsQ);
    state.raw[i] = cur.join('\\n');""")

# ---------- 10) QUO-3：行首退格先退一级嵌套 ----------
rep("quo3-backspace", """      } else {
        /* 行首（含首行行首）→ 整块引用转段落（含空行时拆成多个段落块） */
        e.preventDefault();""",
"""      } else if (!t.querySelector('.qblk') &&
                 (function () {
                   var rl3 = String(state.raw[i] || '').split('\\n');
                   var cur3b = rl3[qLi] || '';
                   var dm3 = cur3b.match(/^\\s*((?:>[^\\S\\n]*)*)/);
                   return dm3 ? (dm3[1].match(/>/g) || []).length : 0;
                 })() >= 2) {
        /* v3.30.19（QUO-3）：行首退格先退一级嵌套（Typora 式渐进），退光再转段落 */
        e.preventDefault();
        var rls5 = String(state.raw[i] || '').split('\\n');
        rls5[qLi] = rls5[qLi].replace(/^(\\s*)>[^\\S\\n]?/, '$1');
        state.raw[i] = rls5.join('\\n');
        rebuild(); markDirty(); scheduleSnapshot();
        var bq5b = ED.children[i] && ED.children[i].querySelector('blockquote');
        if (bq5b) setQuoteCaret(bq5b, Math.max(0, qoffB - 2));
        return;
      } else {
        /* 行首（含首行行首）→ 整块引用转段落（含空行时拆成多个段落块） */
        e.preventDefault();""")

# ---------- 11) QUO-4：多行选区批量缩进 + quoteCaretOff 带端点 ----------
rep("quoteCaretOff-sig", """  function quoteCaretOff(bq) {
    var sel = getSelection();
    if (!sel.rangeCount) return 0;
    var r = sel.getRangeAt(0);
    var pre = document.createRange();
    pre.selectNodeContents(bq);
    try { pre.setEnd(r.startContainer, r.startOffset); } catch (ex) { return 0; }""",
"""  function quoteCaretOff(bq, epNode, epOff) {
    var sel = getSelection();
    if (!sel.rangeCount) return 0;
    var r = sel.getRangeAt(0);
    var eN = epNode || r.startContainer;
    var eO = epOff == null ? r.startOffset : epOff;
    var pre = document.createRange();
    pre.selectNodeContents(bq);
    try { pre.setEnd(eN, eO); } catch (ex) { return 0; }""")
rep("quo4-tab", """      e.preventDefault();
      var qtx2 = quoteText(t);
      var qoff2 = quoteCaretOff(t);
      var li2 = qtx2.slice(0, qoff2).split('\\n').length - 1;
      var rls = state.raw[i].split('\\n');
      if (li2 >= rls.length) return;""",
"""      e.preventDefault();
      /* v3.30.19（QUO-4）：多行选区整段批量增减 '> ' 前缀（含 .qblk 时行模型
         不可靠，维持单行行为）；选区恢复以选区起点塌陷近似 */
      var selQ3 = getSelection();
      var rq3 = selQ3.rangeCount ? selQ3.getRangeAt(0) : null;
      if (rq3 && !rq3.collapsed && !t.querySelector('.qblk')) {
        var qtA = quoteCaretOff(t, rq3.startContainer, rq3.startOffset);
        var qtB = quoteCaretOff(t, rq3.endContainer, rq3.endOffset);
        var lo3 = Math.min(qtA, qtB);
        var hi3 = Math.max(qtA, qtB);
        var qtxM = quoteText(t);
        var liS3 = qtxM.slice(0, lo3).split('\\n').length - 1;
        var liE3 = qtxM.slice(0, hi3).split('\\n').length - 1;
        var rlsM = state.raw[i].split('\\n');
        var touched3 = false;
        for (var lq3 = liS3; lq3 <= liE3 && lq3 < rlsM.length; lq3++) {
          if (e.shiftKey) rlsM[lq3] = rlsM[lq3].replace(/^(\\s*)>[^\\S\\n]?/, '$1');
          else rlsM[lq3] = '> ' + rlsM[lq3];
          touched3 = true;
        }
        if (touched3) {
          state.raw[i] = rlsM.join('\\n');
          rebuild(); markDirty(); scheduleSnapshot();
          var bq3M = ED.children[i] && ED.children[i].querySelector('blockquote');
          if (bq3M) setQuoteCaret(bq3M, Math.max(0, lo3 + (e.shiftKey ? -2 : 2)));
          return;
        }
        return;
      }
      var qtx2 = quoteText(t);
      var qoff2 = quoteCaretOff(t);
      var li2 = qtx2.slice(0, qoff2).split('\\n').length - 1;
      var rls = state.raw[i].split('\\n');
      if (li2 >= rls.length) return;""")

# ---------- 12) QUO-6：粘贴块级内容转富块 ----------
rep("quo6-paste", """    if (tg === 'BLOCKQUOTE') {
      /* 引用是 <br> 行模型：整段插入后由 quoteLinesFromDom 重建 '> ' 行 */
      document.execCommand('insertText', false, md);
      syncQuoteEl(t);
      return true;
    }""",
"""    if (tg === 'BLOCKQUOTE') {
      /* v3.30.19（QUO-6）：粘贴内容含围栏 / 表格语法 → 走 quoteAppendBlock
         生成引用内嵌富块（不再降级为字面文本） */
      if (/(^|\\n)[ \\t]{0,3}(```|~~~)/.test(md) ||
          (/^\\s{0,3}\\|.*\\|\\s*$/m.test(md) && /^\\s{0,3}\\|?[\\s:|-]+\\|?[\\s-]*$/m.test(md))) {
        var blkQ6 = t.closest('.blk');
        var iQ6 = blkQ6 ? blockIndexOf(blkQ6) : -1;
        if (iQ6 >= 0) { quoteAppendBlock(iQ6, md); return true; }
      }
      /* 引用是 <br> 行模型：整段插入后由 quoteLinesFromDom 重建 '> ' 行 */
      document.execCommand('insertText', false, md);
      syncQuoteEl(t);
      return true;
    }""")

# ---------- 13) HR-6：--- 回车显式提示 ----------
rep("hr6-toast", """      splitBlock(i, off);
      return;""",
"""      /* v3.30.19（HR-6）：单行 --- 回车显式转分割线，给轻提示 */
      if (String(raw).indexOf('\\n') === -1 &&
          /^\\s{0,3}(?:[-*_]\\s*){3,}$/.test(String(raw))) toastStatus('已转换为分割线（hr）');
      splitBlock(i, off);
      return;""")

# ---------- 14) MATH-6：$$…$$ 识别渲染（保留原语法存储） ----------
rep("math6-blockinfo", """    var htag = htmlBlockRoot(first);""",
"""    /* v3.30.19（MATH-6）：$$…$$ 块级公式 —— 识别渲染，原语法保留存储 */
    if (/^\\s*\\$\\$/.test(first)) return { type: 'mathdl' };
    var htag = htmlBlockRoot(first);""")
rep("math6-blockhtml", """      case 'list': return renderList(lines);""",
"""      /* v3.30.19（MATH-6）：$$…$$ 识别渲染（data-tex 占位，KaTeX 统一渲染） */
      case 'mathdl': {
        var m6L = lines.slice();
        m6L[0] = String(m6L[0]).replace(/^\\s*\\$\\$/, '');
        m6L[m6L.length - 1] = String(m6L[m6L.length - 1]).replace(/\\$\\$\\s*$/, '');
        return '<div class="mathblock" data-tex="' + esc(m6L.join('\\n').trim()) + '"></div>';
      }
      case 'list': return renderList(lines);""")
rep("math6-gotoblock", """      if (inf.type === 'fence' && inf.lang === 'math') {
        /* 公式：进入就地编辑（源码框在上方，公式保持可见） */
        openMathEditor(blk, i);
        return;
      }""",
"""      if (inf.type === 'fence' && inf.lang === 'math') {
        /* 公式：进入就地编辑（源码框在上方，公式保持可见） */
        openMathEditor(blk, i);
        return;
      }
      if (inf.type === 'mathdl') {
        /* v3.30.19（MATH-6）：$$ 块级公式同款就地编辑 */
        openMathEditor(blk, i);
        return;
      }""")
rep("math6-commit", """    var tex = mathCtx.ta.value.replace(/\\u00a0/g, ' ');
    state.raw[mathCtx.idx] = '```math\\n' + tex + '\\n```';""",
"""    var tex = mathCtx.ta.value.replace(/\\u00a0/g, ' ');
    /* v3.30.19（MATH-6）：$$ 形态的块保留原语法存储（存储形态不漂移） */
    if (mathCtx.dollar) {
      state.raw[mathCtx.idx] = tex.indexOf('\\n') >= 0 ? '$$\\n' + tex + '\\n$$' : '$$' + tex + '$$';
    } else {
      state.raw[mathCtx.idx] = '```math\\n' + tex + '\\n```';
    }""")
rep("math6-ctx", """    mathCtx = { idx: idx, blk: blk, mbEl: mb, ta: ta, timer: null };""",
"""    mathCtx = { idx: idx, blk: blk, mbEl: mb, ta: ta, timer: null,
                dollar: String(state.raw[idx] || '').replace(/^\\s+/, '').indexOf('$$') === 0 };   /* v3.30.19（MATH-6） */""")
rep("math6-typelabel", """      deflist: '定义列表',""",
"""      deflist: '定义列表', mathdl: '公式',""")

# ---------- 15) U1：非空块行首 / 触发 ----------
rep("u1-trigger", """      var el = e.target.closest ? e.target.closest('.raw-edit') : null;
      if (!el || el.classList.contains('t-src')) return;
      var i = state.editIdx;
      if (i < 0 || state.raw[i] !== '' || el.textContent !== '') return;
      e.preventDefault(); e.stopPropagation();
      openSlashAt(el);
      return;""",
"""      var el = e.target.closest ? e.target.closest('.raw-edit') : null;
      if (!el || el.classList.contains('t-src')) return;
      var i = state.editIdx;
      if (i < 0) return;
      /* v3.30.19（U1）：非空块行首键入 / 也触发 —— 应用时在当前块后插入新块，
         不再破坏已有内容；光标须在块首（行中键入不触发） */
      var nonEmptyU1 = state.raw[i] !== '' || el.textContent !== '';
      if (nonEmptyU1 && textBeforeCaret(el) !== '') return;
      e.preventDefault(); e.stopPropagation();
      openSlashAt(el);
      if (nonEmptyU1) { slashState.nonEmpty = true; slashState.anchorIdx = i; }
      return;""")
rep("u1-apply", """    if (item.children) {  // 父项：打开二级菜单（不显示父菜单名）""",
"""    /* v3.30.19（U1）：非空块行首触发的菜单 —— 叶子项在当前块之后插入新块，
       不覆盖当前块已有内容（空块路径仍是整块替换 item.t） */
    if (slashState && slashState.nonEmpty && !item.children &&
        item.menu !== 'tbl' && item.menu !== 'image' && item.menu !== 'code' &&
        !item.pick && !item.fn) {
      hidePops();
      commitEditSilent();
      var atU1 = Math.min((slashState.anchorIdx != null ? slashState.anchorIdx : state.editIdx) + 1,
        state.raw.length);
      var rawU1 = item.math != null ? '```math\\n' + item.math + '\\n```' : item.t;
      state.raw.splice(atU1, 0, rawU1);
      rebuild(); markDirty(); scheduleSnapshot();
      var infU1 = blockInfo(state.raw[atU1]);
      if (infU1.type === 'fence' && infU1.lang === 'mermaid') openMmdEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence' && infU1.lang === 'math') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'mathdl') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence') focusCodeBlock(atU1);
      else goToBlock(atU1, 'start');
      return;
    }
    if (item.children) {  // 父项：打开二级菜单（不显示父菜单名）""")

# ---------- 16) U2/U3/U6：重锚定 + 退场动画 + 滚动提示 ----------
rep("u2-global", """  var activePop = null;   // 'slash' | 'block' | 'table' | 'hint'""",
"""  var activePop = null;   // 'slash' | 'block' | 'table' | 'hint'
  var popReanchor = null;   /* v3.30.19（U2）：锚定型浮层滚动重锚定回调 */""")
rep("hidepops", """  function hidePops() {
    FB.classList.remove('show'); SM.classList.remove('show');
    BM.classList.remove('show'); TB.classList.remove('show');
    SUB.classList.remove('show');
    var tsz = document.getElementById('tblsize'); if (tsz) tsz.classList.remove('show');
    var lp = document.getElementById('langpop'); if (lp) lp.classList.remove('show');
    var lkp = document.getElementById('linkpop'); if (lkp) lkp.classList.remove('show');
    var ip = document.getElementById('imgpop'); if (ip) ip.classList.remove('show');
    /* v3.25：代码风格弹层 / 图片重命名弹层一并收起 */
    var sp = document.getElementById('stylepop'); if (sp) sp.classList.remove('show');
    var rp = document.getElementById('renpop'); if (rp) rp.classList.remove('show');
    /* v3.30.11（MATH-5）：单元格公式编辑弹层一并收起 */
    var mpp = document.getElementById('mathpop'); if (mpp) mpp.classList.remove('show');""",
"""  /* v3.30.19（U3）：浮层退场淡出 —— 加 .hiding（保持显示 + 透明过渡 + 立即
     不可交互），110ms 后摘除；placePop / openSub 显示前清掉残留的 .hiding */
  function fadeOutPop(el) {
    if (!el || !el.classList || !el.classList.contains('show')) return;
    el.classList.add('hiding');
    el.classList.remove('show');
    setTimeout(function () { el.classList.remove('hiding'); }, 110);
  }
  function hidePops() {
    popReanchor = null;   /* v3.30.19（U2） */
    fadeOutPop(FB); fadeOutPop(SM); fadeOutPop(BM); fadeOutPop(TB); fadeOutPop(SUB);
    var tsz = document.getElementById('tblsize'); fadeOutPop(tsz);
    var lp = document.getElementById('langpop'); fadeOutPop(lp);
    var lkp = document.getElementById('linkpop'); fadeOutPop(lkp);
    var ip = document.getElementById('imgpop'); fadeOutPop(ip);
    /* v3.25：代码风格弹层 / 图片重命名弹层一并收起 */
    var sp = document.getElementById('stylepop'); fadeOutPop(sp);
    var rp = document.getElementById('renpop'); fadeOutPop(rp);
    /* v3.30.11（MATH-5）：单元格公式编辑弹层一并收起 */
    var mpp = document.getElementById('mathpop'); fadeOutPop(mpp);
    /* v3.30.19（IMG-7）：精确尺寸弹层一并收起 */
    var isp = document.getElementById('imgsizepop'); fadeOutPop(isp);""")
rep("hidepops-ob", """    var ob2 = document.getElementById('objbar'); if (ob2) ob2.classList.remove('show');
    var cp = document.getElementById('cappop'); if (cp) cp.classList.remove('show');""",
"""    var ob2 = document.getElementById('objbar'); fadeOutPop(ob2);
    var cp = document.getElementById('cappop'); fadeOutPop(cp);""")
rep("u2u6-scroll", """  ED.addEventListener('scroll', function () {
    if (activePop) hidePops();""",
"""  ED.addEventListener('scroll', function () {
    /* v3.30.19（U2/U6）：锚定型浮层滚动重锚定（斜杠 / 二级 / 提示 / 风格弹层）；
       其余浮层（含输入框型）维持「随滚动收起」并给轻提示 */
    if (activePop) {
      if (typeof popReanchor === 'function') {
        try { popReanchor(); } catch (eRA) { hidePops(); toastStatus('菜单已随滚动收起'); }
      } else {
        hidePops();
        toastStatus('菜单已随滚动收起');
      }
    }""")
rep("u3-placepop", """  function placePop(pop, x, y) {
    pop.classList.add('show');""",
"""  function placePop(pop, x, y) {
    pop.classList.remove('hiding');   /* v3.30.19（U3）：清退场残态 */
    pop.classList.add('show');""")
rep("u4u2-opensub", """    SUB.classList.add('show');
    var r = anchorEl.getBoundingClientRect();
    placePop(SUB, r.right + 4, r.top - 4);
  }""",
"""    SUB.classList.remove('hiding');
    SUB.classList.add('show');
    var r = anchorEl.getBoundingClientRect();
    /* v3.30.19（U4）：右缘放不下时改锚父项左侧（不再贴边硬钳覆盖父菜单） */
    var xU4 = r.right + 4;
    if (xU4 + SUB.offsetWidth > window.innerWidth - 8)
      xU4 = Math.max(6, r.left - SUB.offsetWidth - 4);
    placePop(SUB, xU4, r.top - 4);
    /* v3.30.19（U2）：二级菜单跟随父项重锚定 */
    popReanchor = function () {
      if (!anchorEl.isConnected) { hidePops(); return; }
      var r2 = anchorEl.getBoundingClientRect();
      var x2 = r2.right + 4;
      if (x2 + SUB.offsetWidth > window.innerWidth - 8)
        x2 = Math.max(6, r2.left - SUB.offsetWidth - 4);
      placePop(SUB, x2, r2.top - 4);
    };
  }""")
rep("u2-hint", """    activePop = 'hint';
    var rect = el.getBoundingClientRect();
    placePop(SM, rect.left + 16, rect.bottom + 6);
  }""",
"""    activePop = 'hint';
    var rect = el.getBoundingClientRect();
    placePop(SM, rect.left + 16, rect.bottom + 6);
    popReanchor = function () {   /* v3.30.19（U2） */
      if (!el.isConnected) { hidePops(); return; }
      var rc = el.getBoundingClientRect();
      placePop(SM, rc.left + 16, rc.bottom + 6);
    };
  }""")
rep("u2-slash", """    slashRender();
    var rect = el.getBoundingClientRect();
    placePop(SM, rect.left + 16, rect.bottom + 6);
  }""",
"""    slashRender();
    var rect = el.getBoundingClientRect();
    placePop(SM, rect.left + 16, rect.bottom + 6);
    popReanchor = function () {   /* v3.30.19（U2）：斜杠菜单跟随锚点滚动 */
      if (!el.isConnected) { hidePops(); return; }
      var rc = el.getBoundingClientRect();
      placePop(SM, rc.left + 16, rc.bottom + 6);
    };
  }""")
rep("u2-style", """    SP._anchor = btn;
    var r = btn.getBoundingClientRect();
    placePop(SP, r.left, r.bottom + 4);
  }""",
"""    SP._anchor = btn;
    var r = btn.getBoundingClientRect();
    placePop(SP, r.left, r.bottom + 4);
    popReanchor = function () {   /* v3.30.19（U2） */
      if (!btn.isConnected) { hidePops(); return; }
      var r2 = btn.getBoundingClientRect();
      placePop(SP, r2.left, r2.bottom + 4);
    };
  }""")

# ---------- 17) D2：mermaid 错误带行号 ----------
rep("d2-err", """      el.innerHTML = '<div class="mmd-err">图表语法校验未通过（' + esc(String(msg || '').slice(0, 160)) +
                     '），已显示源码；双击图表可继续编辑：</div>' +
                     '<pre class="mmd-src-show">' + esc(src) + '</pre>';""",
"""      /* v3.30.19（D2）：错误摘要带行号（mermaid 报错文本通常含 line N） */
      var lm6 = String(msg || '').match(/line (\\d+)/i) || String(msg || '').match(/第\\s*(\\d+)\\s*行/);
      var ln6 = lm6 ? '（出错位置：第 ' + lm6[1] + ' 行附近）' : '';
      el.innerHTML = '<div class="mmd-err">图表语法校验未通过' + ln6 + '（' + esc(String(msg || '').slice(0, 160)) +
                     '），已显示源码；双击图表可继续编辑：</div>' +
                     '<pre class="mmd-src-show">' + esc(src) + '</pre>';""")

# ---------- 18) D3：语言栏右键复制全部代码 ----------
rep("d3-codebar", """    bar.appendChild(cbtn);
    pre.parentNode.insertBefore(wrap, pre);""",
"""    bar.appendChild(cbtn);
    /* v3.30.19（D3）：语言栏右键 = 复制全部代码（与「复制」按钮同链路） */
    bar.addEventListener('contextmenu', function (ev) {
      ev.preventDefault(); ev.stopPropagation();
      copyTextToClipboard(code ? code.textContent : pre.textContent);
    });
    pre.parentNode.insertBefore(wrap, pre);""")

# ---------- 19) D8：语言弹层最近使用置顶 ----------
rep("d8-recent", """  function langFilter(q) {
    if (!q) return CODE_LANGS;
    var s = q.toLowerCase();
    return CODE_LANGS.filter(function (l) { return l.toLowerCase().indexOf(s) !== -1; });
  }""",
"""  /* v3.30.19（D8）：最近使用语言置顶（localStorage，跨会话，至多 5 个） */
  function recentLangs() {
    try {
      if (typeof localStorage === 'undefined') return [];
      var r = JSON.parse(localStorage.getItem('mdeditor_recent_langs') || '[]');
      return Array.isArray(r) ? r : [];
    } catch (e) { return []; }
  }
  function pushRecentLang(l) {
    try {
      if (typeof localStorage === 'undefined' || !l) return;
      var r = recentLangs().filter(function (x) { return x !== l; });
      r.unshift(l);
      localStorage.setItem('mdeditor_recent_langs', JSON.stringify(r.slice(0, 5)));
    } catch (e) { /* 忽略存储异常 */ }
  }
  function langFilter(q) {
    if (!q) {
      var rec = recentLangs().filter(function (l) { return CODE_LANGS.indexOf(l) !== -1; });
      return rec.concat(CODE_LANGS.filter(function (l) { return rec.indexOf(l) === -1; }));
    }
    var s = q.toLowerCase();
    return CODE_LANGS.filter(function (l) { return l.toLowerCase().indexOf(s) !== -1; });
  }""")
rep("d8-push", """      var dispName = String(name || '').trim();
      name = dispName.toLowerCase();""",
"""      var dispName = String(name || '').trim();
      name = dispName.toLowerCase();
      pushRecentLang(name);   /* v3.30.19（D8） */""")

io.open(P, "w", encoding="utf-8", newline="").write(src)
print("APPLIED:", len(applied))
for t in applied: print("  +", t)
if fails:
    print("FAILED:", len(fails))
    for f in fails: print("  -", f)
    sys.exit(1)
print("ALL OK")
