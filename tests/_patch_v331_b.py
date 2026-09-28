# -*- coding: utf-8 -*-
"""v3.30.19 批次 B：FN-3/4/5 + DL-3/4 + IMG-5/6/7 + MMD-2/7 + applyBlockAct 扩展"""
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

# ---------- 1) FN 函数群（重排 / 清理 / 跳转 / 高亮） ----------
rep("fn-funcs", """  function openHintAt(el, items) {""",
"""  /* v3.30.19（FN-4）：按出现顺序重排脚注编号（跳过围栏块与行内码） */
  function fnEscapeRe(s) { return String(s).replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); }
  function fnCollectRefIds() {
    var used = {}, order = [];
    for (var q = 0; q < state.raw.length; q++) {
      var rb = String(state.raw[q] || '');
      if (blockInfo(rb).type === 'fence') continue;
      var ls = rb.split('\\n');
      for (var L = 0; L < ls.length; L++) {
        if (/^\\s{0,3}\\[\\^[^\\]\\s]+\\]:/.test(ls[L])) continue;   /* 定义行不算引用 */
        var segs = ls[L].split(/(`[^`]*`)/);
        for (var si = 0; si < segs.length; si++) {
          if (/^`/.test(segs[si])) continue;
          var reF = /\\[\\^([^\\]\\s]+)\\]/g, mF;
          while ((mF = reF.exec(segs[si])) !== null) {
            if (!used.hasOwnProperty(mF[1])) { used[mF[1]] = 1; order.push(mF[1]); }
          }
        }
      }
    }
    return order;
  }
  function renumberFootnotes() {
    commitEditSilent();
    var map = {}, order = [];
    for (var q = 0; q < state.raw.length; q++) {
      var rb = String(state.raw[q] || '');
      if (blockInfo(rb).type === 'fence') continue;
      var ls = rb.split('\\n');
      for (var L = 0; L < ls.length; L++) {
        if (/^\\s{0,3}\\[\\^[^\\]\\s]+\\]:/.test(ls[L])) continue;
        var segs = ls[L].split(/(`[^`]*`)/);
        for (var si = 0; si < segs.length; si++) {
          if (/^`/.test(segs[si])) continue;
          segs[si] = segs[si].replace(/\\[\\^([^\\]\\s]+)\\]/g, function (m0, id) {
            if (!map.hasOwnProperty(id)) { map[id] = String(order.length + 1); order.push(id); }
            return '[^' + map[id] + ']';
          });
        }
        ls[L] = segs.join('');
      }
      state.raw[q] = ls.join('\\n');
    }
    if (!order.length) { rebuild(); toastStatus('未发现脚注引用，未重排'); return; }
    /* 定义行跟随引用改号（无引用的孤儿定义保持原 id，由「清理」处理） */
    for (var q2 = 0; q2 < state.raw.length; q2++) {
      var rb2 = String(state.raw[q2] || '');
      if (blockInfo(rb2).type !== 'fndef') continue;
      var m7 = rb2.match(/^\\s{0,3}\\[\\^([^\\]\\s]+)\\]:/);
      if (m7 && map.hasOwnProperty(m7[1])) {
        state.raw[q2] = rb2.replace(
          new RegExp('^(\\\\s{0,3})\\\\[\\\\^' + fnEscapeRe(m7[1]) + '\\\\]:'),
          '$1[^' + map[m7[1]] + ']:');
      }
    }
    rebuild(); markDirty(); scheduleSnapshot();
    toastStatus('已按出现顺序重排 ' + order.length + ' 个脚注编号');
  }
  /* v3.30.19（FN-5）：清理未引用的脚注定义（孤儿定义） */
  function cleanOrphanFndefs() {
    commitEditSilent();
    var used = {};
    var order = fnCollectRefIds();
    for (var o = 0; o < order.length; o++) used[order[o]] = 1;
    var removed = 0;
    for (var q2 = state.raw.length - 1; q2 >= 0; q2--) {
      var m9 = String(state.raw[q2] || '').match(/^\\s{0,3}\\[\\^([^\\]\\s]+)\\]:/);
      if (m9 && !used.hasOwnProperty(m9[1])) { state.raw.splice(q2, 1); removed++; }
    }
    if (!state.raw.length) state.raw = [''];
    rebuild(); markDirty(); scheduleSnapshot();
    toastStatus(removed ? '已清理 ' + removed + ' 条未引用的脚注定义' : '没有未引用的脚注定义');
  }
  window.__fnRenum = function () { renumberFootnotes(); return 'OK'; };   /* 测试接口 */
  window.__fnClean = function () { cleanOrphanFndefs(); return 'OK'; };
  function openHintAt(el, items) {""")

# ---------- 2) FN-3：跳转 + 高亮（点击委托） ----------
rep("fn3-click", """    var q = e.target.closest ? e.target.closest('#editor blockquote .qblk') : null;
    if (!q) return;
    toastStatus('引用内的富内容块暂不支持直接编辑，双击可转入源码态修改');
  });""",
"""    var q = e.target.closest ? e.target.closest('#editor blockquote .qblk') : null;
    if (!q) return;
    toastStatus('引用内的富内容块暂不支持直接编辑，双击可转入源码态修改');
  });
  /* v3.30.19（FN-3）：脚注引用 ↔ 定义点击跳转（引用→定义、fnmark→引用）+ 落点高亮 */
  function fnFlash(elF) {
    if (!elF || !elF.classList) return;
    elF.classList.add('fn-flash');
    setTimeout(function () { elF.classList.remove('fn-flash'); }, 1200);
  }
  function fnJumpToDef(fid) {
    if (!fid) return;
    var idRe = new RegExp('^\\\\s{0,3}\\\\[\\\\^' + fnEscapeRe(fid) + '\\\\]:');
    for (var q = 0; q < state.raw.length; q++) {
      if (!idRe.test(String(state.raw[q] || ''))) continue;
      var blkF = ED.children[q];
      if (blkF) {
        blkF.scrollIntoView({ block: 'center' });
        fnFlash(blkF.querySelector('.fnitem') || blkF);
      }
      return;
    }
    toastStatus('未找到脚注定义 [^' + fid + ']');
  }
  function fnJumpToRef(fmEl) {
    var idm = (fmEl.textContent || '').match(/\\[([^\\]\\s]+)\\]/);
    var fid = idm ? idm[1] : '';
    if (!fid) return;
    var refs = ED.querySelectorAll('.fnref a[data-fn]');
    for (var k = 0; k < refs.length; k++) {
      if (refs[k].getAttribute('data-fn') !== fid) continue;
      refs[k].scrollIntoView({ block: 'center' });
      fnFlash(refs[k].closest('.fnref') || refs[k]);
      return;
    }
    toastStatus('未找到脚注 [^' + fid + '] 的引用位置');
  }
  ED.addEventListener('click', function (e) {
    if (window.__previewLock) return;
    var faF = e.target.closest ? e.target.closest('#editor .fnref a') : null;
    if (faF) {
      e.preventDefault(); e.stopPropagation();
      fnJumpToDef(faF.getAttribute('data-fn') || '');
      return;
    }
    var fmF = e.target.closest ? e.target.closest('#editor .fnmark') : null;
    if (fmF) {
      e.preventDefault(); e.stopPropagation();
      fnJumpToRef(fmF);
    }
  });""")

# ---------- 3) FN-4/5：脚注定义块右键菜单 ----------
rep("fn-contextmenu", """      buildTblbar();
      activePop = 'table';
      placePop(TB, e.clientX, e.clientY);
      return;
    }
    if (e.target.closest && e.target.closest(
        '#editor .codebar, #editor .codeblock, #editor .mmd-src, #editor input')) return;""",
"""      buildTblbar();
      activePop = 'table';
      placePop(TB, e.clientX, e.clientY);
      return;
    }
    /* v3.30.19（FN-4/5）：脚注定义块右键 → 重排编号 / 清理未引用定义 */
    var fnCm = e.target.closest ? e.target.closest('#editor .fnbody') : null;
    if (fnCm) {
      var fnBlk = fnCm.closest('.blk');
      var fnIdx = fnBlk ? blockIndexOf(fnBlk) : -1;
      if (fnIdx >= 0) {
        e.preventDefault(); e.stopPropagation();
        handleIdx = fnIdx;
        BM.innerHTML = '<div class="cap">脚注</div>' +
          '<div class="mi" data-act="fnrenum"><span style="width:18px;text-align:center">№</span>按出现顺序重排编号</div>' +
          '<div class="mi" data-act="fnclean"><span style="width:18px;text-align:center">🧹</span>清理未引用的脚注定义</div>';
        activePop = 'block';
        placePop(BM, e.clientX, e.clientY);
        return;
      }
    }
    if (e.target.closest && e.target.closest(
        '#editor .codebar, #editor .codeblock, #editor .mmd-src, #editor input')) return;""")

# ---------- 4) applyBlockAct：fnrenum / fnclean / imgalign / imglocalall / imgsize ----------
rep("aba-cases", """    /* v3.30.17：图片右键菜单 —— 重置尺寸 / 存储转换 / 修改图片名称 */
    if (act === 'imgreset') { hidePops(); resetObjSize('img', i); return; }
    if (act === 'imgmode') { hidePops(); requestImgModeSwitch(i); return; }
    if (act === 'imgrename') { hidePops(); openRenamePop(i); return; }""",
"""    /* v3.30.17：图片右键菜单 —— 重置尺寸 / 存储转换 / 修改图片名称 */
    if (act === 'imgreset') { hidePops(); resetObjSize('img', i); return; }
    if (act === 'imgmode') { hidePops(); requestImgModeSwitch(i); return; }
    if (act === 'imgrename') { hidePops(); openRenamePop(i); return; }
    /* v3.30.19（FN-4/5）：脚注重排 / 清理 */
    if (act === 'fnrenum') { hidePops(); renumberFootnotes(); return; }
    if (act === 'fnclean') { hidePops(); cleanOrphanFndefs(); return; }
    /* v3.30.19（IMG-5/6/7）：对齐 / 全部网络图片本地化 / 精确尺寸 */
    if (act.indexOf('imgalign:') === 0) {
      hidePops();
      var alI = act.slice(9);
      var spI = figFromRaw(state.raw[i]);
      if (spI) {
        spI.align = (alI === 'l' || alI === 'r') ? alI : '';
        writeFigure(i, spI);
        toastStatus('图片对齐：' + (alI === 'l' ? '靠左' : alI === 'r' ? '靠右' : '居中'));
      }
      return;
    }
    if (act === 'imglocalall') { hidePops(); localizeRemoteImages(); return; }
    if (act === 'imgsize') { hidePops(); openImgSizePop(i); return; }""")

# ---------- 5) DL-3：Tab 新增定义 / Shift+Tab 退出 ----------
rep("dl3-tab", """    /* v3.26：定义列表渲染态编辑 —— 回车新增定义，行首退格退出/删除 */
    if (isDL && e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {""",
"""    /* v3.30.19（DL-3）：Tab 新增定义 / Shift+Tab 退出定义列表（键盘流补齐） */
    if (isDL && e.key === 'Tab' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      if (e.shiftKey) {
        syncDeflistEl(t);
        goToBlock(Math.min(i + 1, state.raw.length - 1), 'start');
        return;
      }
      var dlT3 = t.closest('dl');
      if (!dlT3) return;
      var ndd3 = document.createElement('dd');
      ndd3.setAttribute('contenteditable', 'plaintext-only');
      ndd3.setAttribute('spellcheck', 'false');
      t.parentNode.insertBefore(ndd3, t.nextSibling);
      syncDeflistEl(t);
      ndd3.focus(); setCaret(ndd3, 0);
      return;
    }
    /* v3.26：定义列表渲染态编辑 —— 回车新增定义，行首退格退出/删除 */
    if (isDL && e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {""")

# ---------- 6) DL-4：空定义识别 / nbsp 渲染 / 缩进回写 ----------
rep("dl4-blockinfo", """    if (lines.length >= 2 && first.trim() !== '' && /^\\s*:\\s+\\S/.test(lines[1])) {
      return { type: 'deflist' };
    }""",
"""    if (lines.length >= 2 && first.trim() !== '' && /^\\s*:\\s+(?:\\S.*)?$/.test(lines[1])) {
      return { type: 'deflist' };   /* v3.30.19（DL-4）：空定义 ": " 不再使块类型漂移 */
    }""")
rep("dl4-render", """        var dlh = '<dl class="deflist">';
        for (var q = 0; q < lines.length; q++) {
          if (/^\\s*:\\s+/.test(lines[q])) dlh += '<dd>' + inlineHTML(lines[q].replace(/^\\s*:\\s+/, '')) + '</dd>';
          else if (lines[q].trim() !== '') dlh += '<dt>' + inlineHTML(lines[q]) + '</dt>';
        }
        return dlh + '</dl>';""",
"""        var dlh = '<dl class="deflist">';
        for (var q = 0; q < lines.length; q++) {
          /* v3.30.19（DL-4）：空定义渲染 &nbsp; 占位（保持可点击聚焦），存储仍为 ": " */
          if (/^\\s*:\\s/.test(lines[q])) {
            var ddH = inlineHTML(lines[q].replace(/^\\s*:\\s?/, ''));
            dlh += '<dd>' + (ddH || '&nbsp;') + '</dd>';
          }
          else if (lines[q].trim() !== '') dlh += '<dt>' + inlineHTML(lines[q]) + '</dt>';
        }
        return dlh + '</dl>';""")
rep("dl4-sync", """    var lines = [];
    for (var k = 0; k < dl.children.length; k++) {
      var c = dl.children[k];
      var txt = (c.textContent || '').replace(/\\u00a0/g, ' ');
      lines.push(c.tagName === 'DD' ? ': ' + txt : txt);
    }
    state.raw[i] = lines.join('\\n');""",
"""    /* v3.30.19（DL-4）：回写保留原定义行的缩进；空 dd（&nbsp; 占位）不写空格尾巴 */
    var oldDL = String(state.raw[i] || '').split('\\n');
    var ddInd = [];
    for (var oi = 0; oi < oldDL.length; oi++) {
      if (/^\\s*:\\s/.test(oldDL[oi])) ddInd.push((oldDL[oi].match(/^\\s*/) || [''])[0]);
    }
    var lines = [], ddK = 0;
    for (var k = 0; k < dl.children.length; k++) {
      var c = dl.children[k];
      var txt = (c.textContent || '').replace(/\\u00a0/g, ' ');
      if (!txt.trim()) txt = '';
      if (c.tagName === 'DD') {
        var indD = ddInd[ddK] != null ? ddInd[ddK] : '';
        ddK++;
        lines.push(indD + ': ' + txt);
      } else lines.push(txt);
    }
    state.raw[i] = lines.join('\\n');""")

# ---------- 7) IMG-5：align 进出存储 ----------
rep("img5-fromraw-plain", """      return m ? { src: m[2], alt: m[1], style: '', cap: '', captop: false } : null;""",
"""      return m ? { src: m[2], alt: m[1], style: '', cap: '', captop: false, align: '' } : null;""")
rep("img5-fromraw-fig", """    return {
      src: attr('src'), alt: attr('alt'),
      style: attr('style').replace(/;\\s*$/, '').trim(),
      cap: cm ? cm[1].replace(/<[^>]*>/g, '').trim() : '',
      captop: /<figure[^>]*\\bclass\\s*=\\s*"[^"]*\\btop\\b/i.test(s)
    };""",
"""    var am6 = s.match(/<figure[^>]*\\bclass\\s*=\\s*"[^"]*\\bfig-([lr])\\b/i);
    return {
      src: attr('src'), alt: attr('alt'),
      style: attr('style').replace(/;\\s*$/, '').trim(),
      cap: cm ? cm[1].replace(/<[^>]*>/g, '').trim() : '',
      captop: /<figure[^>]*\\bclass\\s*=\\s*"[^"]*\\btop\\b/i.test(s),
      align: am6 ? am6[1] : ''   /* v3.30.19（IMG-5） */
    };""")
rep("img5-tostorage", """  function figToStorage(spec) {
    if (!spec.style && !spec.cap) {
      return '![' + (spec.alt || '') + '](' + spec.src + ')';
    }
    var esc2 = function (v) { return String(v == null ? '' : v).replace(/"/g, '&quot;'); };
    var out = ['<figure class="md-fig' + (spec.captop ? ' top' : '') + '">'];""",
"""  function figToStorage(spec) {
    if (!spec.style && !spec.cap && !spec.align) {
      return '![' + (spec.alt || '') + '](' + spec.src + ')';
    }
    var esc2 = function (v) { return String(v == null ? '' : v).replace(/"/g, '&quot;'); };
    var out = ['<figure class="md-fig' + (spec.captop ? ' top' : '') +
      (spec.align === 'l' ? ' fig-l' : spec.align === 'r' ? ' fig-r' : '') + '">'];""")

# ---------- 8) IMG 菜单项 + 对齐二级菜单 ----------
rep("img-menu", """      html += '<div class="mi" data-act="imgreset"><span style="width:18px;text-align:center">↺</span>重置尺寸</div>';""",
"""      html += '<div class="mi" data-act="imgreset"><span style="width:18px;text-align:center">↺</span>重置尺寸</div>';
      /* v3.30.19（IMG-7 / IMG-5）：精确尺寸输入 + 对齐（随存储持久化） */
      html += '<div class="mi" data-act="imgsize"><span style="width:18px;text-align:center">⤢</span>精确尺寸</div>';
      html += '<div class="mi has-sub" data-act="imgalign-sub"><span style="width:18px;text-align:center">⇔</span>对齐</div>';
      /* v3.30.19（IMG-6）：全部网络图片转存 assets */
      html += '<div class="mi" data-act="imglocalall"><span style="width:18px;text-align:center">⤓</span>全部网络图片转本地</div>';""")
rep("imgalign-sub", """    var act = t.getAttribute('data-act');
    if (act === 'to-h' || act === 'to-list') {  // 展开二级子菜单""",
"""    var act = t.getAttribute('data-act');
    /* v3.30.19（IMG-5）：图片对齐二级菜单 */
    if (act === 'imgalign-sub') {
      var curAl = '';
      var spA = figFromRaw(state.raw[handleIdx] || '');
      if (spA) curAl = spA.align || '';
      openSub(t, [
        { ic: '⊙' + (curAl === '' ? ' ✓' : ''), lb: '居中（默认）', act: 'imgalign:c' },
        { ic: '⭰' + (curAl === 'l' ? ' ✓' : ''), lb: '靠左', act: 'imgalign:l' },
        { ic: '⭲' + (curAl === 'r' ? ' ✓' : ''), lb: '靠右', act: 'imgalign:r' }
      ], '对齐', function (leaf) { if (leaf) applyBlockAct(leaf.act); }, 0);
      return;
    }
    if (act === 'to-h' || act === 'to-list') {  // 展开二级子菜单""")

# ---------- 9) IMG-6/7：批量本地化 + 精确尺寸弹层 ----------
rep("img-funcs", """  /* 向 Python 发请求（collect 轮询带出，只发一次）；Python 处理后回调 imgReqDone */
  function sendImgReq(req) {""",
"""  /* v3.30.19（IMG-6）：批量把网络图片转存到 assets（复用 imgToAssets 通道，逐张接力） */
  function findNextRemoteImg() {
    for (var q = 0; q < state.raw.length; q++) {
      var rb = String(state.raw[q] || '');
      if (!isImageBlockRaw(rb)) continue;
      var sp = figFromRaw(rb);
      if (sp && /^https?:/i.test(sp.src)) return { idx: q, src: sp.src };
    }
    return null;
  }
  function localizeRemoteImages() {
    if (!window.__docDir) { toastStatus('请先保存文档，再下载网络图片到 assets'); return; }
    var hit = findNextRemoteImg();
    if (!hit) { toastStatus('未发现网络图片'); return; }
    window.__imgLocalAll = true;
    toastStatus('开始下载网络图片到 assets…');
    sendImgReq({ act: 'imgToAssets', idx: hit.idx, src: hit.src });
  }
  /* v3.30.19（IMG-7）：精确尺寸弹层（像素 / 百分比，Enter 写回 figure style） */
  function openImgSizePop(idx) {
    var spec = figFromRaw(state.raw[idx]);
    if (!spec) return;
    var el = ED.children[idx] ? ED.children[idx].querySelector('img') : null;
    if (!el) return;
    var pop = document.getElementById('imgsizepop');
    if (!pop) {
      pop = document.createElement('div');
      pop.id = 'imgsizepop';
      pop.className = 'pop';
      pop.innerHTML = '<div class="cap">精确尺寸</div>' +
        '<div class="row"><input id="imgsize-w" type="text" placeholder="宽">' +
        '<span style="align-self:center">×</span>' +
        '<input id="imgsize-h" type="text" placeholder="高">' +
        '<span style="align-self:center;color:#8b949e;font-size:11px">px / %</span></div>' +
        '<div style="margin-top:5px;color:#8b949e;font-size:11px;padding:0 2px">Enter 应用 · 一处留空按另一维等比 · Esc 取消</div>';
      document.body.appendChild(pop);
      pop.addEventListener('mousedown', function (e) { e.stopPropagation(); });
      pop.addEventListener('keydown', function (e) {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); applyImgSize(); }
        else if (e.key === 'Escape') { pop.classList.remove('show'); }
      });
    }
    function applyImgSize() {
      var idx2 = pop._idx;
      if (idx2 == null) return;
      var wv = document.getElementById('imgsize-w').value.trim();
      var hv = document.getElementById('imgsize-h').value.trim();
      var okV = function (v) { return /^\\d+(\\.\\d+)?%?$/.test(v); };
      var sp2 = figFromRaw(state.raw[idx2]);
      if (!sp2) return;
      var style2 = '';
      if (wv && okV(wv)) style2 = 'width:' + wv + (/%$/.test(wv) ? '' : 'px');
      else if (hv && okV(hv)) style2 = 'height:' + hv + (/%$/.test(hv) ? '' : 'px');
      if (style2) {
        sp2.style = style2;
        writeFigure(idx2, sp2);
        toastStatus('图片尺寸已更新：' + style2.replace(':', ' '));
      }
      pop.classList.remove('show');
    }
    pop._idx = idx;
    document.getElementById('imgsize-w').value = '';
    document.getElementById('imgsize-h').value = '';
    activePop = 'imgsize';
    var r = el.getBoundingClientRect();
    placePop(pop, r.left + r.width / 2 - 95, r.bottom + 8);
    document.getElementById('imgsize-w').focus();
  }
  /* 向 Python 发请求（collect 轮询带出，只发一次）；Python 处理后回调 imgReqDone */
  function sendImgReq(req) {""")
rep("imgreqdone", """  window.imgReqDone = function (idx, newSrc) {
    if (idx == null || idx < 0 || idx >= state.raw.length || !newSrc) return;
    updateFigure(idx, { src: String(newSrc) });
  };""",
"""  window.imgReqDone = function (idx, newSrc) {
    if (idx == null || idx < 0 || idx >= state.raw.length || !newSrc) { window.__imgLocalAll = false; return; }
    updateFigure(idx, { src: String(newSrc) });
    /* v3.30.19（IMG-6）：批量本地化接力（处理完一张自动找下一张网络图片） */
    if (window.__imgLocalAll) {
      var nx6 = findNextRemoteImg();
      if (nx6) sendImgReq({ act: 'imgToAssets', idx: nx6.idx, src: nx6.src });
      else { window.__imgLocalAll = false; toastStatus('网络图片已全部转存到 assets'); }
    }
  };""")

# ---------- 10) MMD-7：全局图表主题 ----------
rep("mmd7-theme", """  function mermaidTheme() {
    var t = document.body.dataset.theme;
    return (t === 'dark' || t === 'night' || t === 'panda') ? 'dark' : 'default';
  }""",
"""  /* v3.30.19（MMD-7）：全局图表主题（QSettings 下发；空 = 跟随界面主题） */
  window.__mmdThemeOverride = '';
  window.setMmdTheme = function (t) {
    window.__mmdThemeOverride = String(t || '');
    if (window.mermaid) {
      initMermaid();
      var els7 = document.querySelectorAll('#editor .mermaidblock');
      for (var k7 = 0; k7 < els7.length; k7++) renderMermaidEl(els7[k7]);
    }
  };
  function mermaidTheme() {
    if (window.__mmdThemeOverride) return window.__mmdThemeOverride;
    var t = document.body.dataset.theme;
    return (t === 'dark' || t === 'night' || t === 'panda') ? 'dark' : 'default';
  }""")

# ---------- 11) MMD-2：导出位图化（SVG → canvas PNG） ----------
rep("mmd2-export", """      '</body>\\n</html>';
  };""",
"""      '</body>\\n</html>';
  };
  /* v3.30.19（MMD-2）：导出用图表位图化 —— 已渲染 SVG 经 canvas 转 PNG dataURL，
     Python 轮询 __mmdExportState 收齐后交给导出器嵌入 DOCX / EPUB；
     单图失败（如 canvas 被污染）跳过，导出回落「源码 + 标注」降级 */
  window.__mmdExportState = null;
  window.__mmdExportStart = function () {
    var mms = document.querySelectorAll('#editor .mermaidblock');
    var jobs = [], seenE = {};
    for (var kE = 0; kE < mms.length; kE++) {
      var dsE = mms[kE].getAttribute('data-src') || '';
      var svE = mms[kE].querySelector('svg');
      if (!dsE || !svE || seenE[dsE]) continue;
      seenE[dsE] = 1;
      jobs.push({ src: dsE, svg: svE });
    }
    var st = window.__mmdExportState = { total: jobs.length, done: 0, items: [] };
    (function next() {
      if (!jobs.length) return;
      var job = jobs.shift();
      try {
        var xml = new XMLSerializer().serializeToString(job.svg);
        var vb = job.svg.viewBox && job.svg.viewBox.baseVal;
        var wE = vb && vb.width ? vb.width : (job.svg.clientWidth || 800);
        var hE = vb && vb.height ? vb.height : (job.svg.clientHeight || 600);
        var scale = 2;
        var imgE = new Image();
        imgE.onload = function () {
          try {
            var cv = document.createElement('canvas');
            cv.width = Math.max(1, Math.round(wE * scale));
            cv.height = Math.max(1, Math.round(hE * scale));
            var ctx = cv.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, cv.width, cv.height);
            ctx.drawImage(imgE, 0, 0, cv.width, cv.height);
            st.items.push({ src: job.src, data: cv.toDataURL('image/png') });
          } catch (e5) { /* 污染等异常：跳过该图 */ }
          st.done++; next();
        };
        imgE.onerror = function () { st.done++; next(); };
        imgE.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
      } catch (e4) { st.done++; next(); }
    })();
    return st.total;
  };""")

io.open(P, "w", encoding="utf-8", newline="").write(src)
print("APPLIED:", len(applied))
for t in applied: print("  +", t)
if fails:
    print("FAILED:", len(fails))
    for f in fails: print("  -", f)
    sys.exit(1)
print("ALL OK")
