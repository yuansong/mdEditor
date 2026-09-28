# -*- coding: utf-8 -*-
"""v3.30.18b 补丁：P2 批次（清单第六章批次 3/5/6）
- CODE-1：代码内容含 ``` 行时拒绝回写（防围栏结构静默破坏）
- CODE-2：代码区 Esc / Ctrl+Enter 退出；方向键首行首 / 末行末跳出
- CODE-3：codebar 加「复制」按钮 + toast
- F1：langpop / stylepop / renpop 打开时置 activePop（滚动收起）
- F2：窗口 resize 统一 hidePops
- F3：placePop 上缘钳位
- F4：hidePops 清 linkCtx / cpCtx
- FN-1：脚注引用在引用 / 标题 / 列表渲染层内可用（不再静默拦截）
- DL-1：空 dd 上回车升格为新 dt（多术语对无需转源码）
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

# ---------- 1. CODE-1 ----------
rep(r'''  function syncCodeBlock(codeEl) {
    var blk = codeEl.closest('.blk');
    var idx = blockIndexOf(blk);
    if (idx < 0) return;
    var lang = (state.raw[idx].split('\n')[0].match(/^```(.*)$/) || ['', ''])[1];
    var text = codeEl.textContent.replace(/\n+$/, '');
    state.raw[idx] = '```' + lang + '\n' + text + '\n```';
    markDirty(); scheduleSnapshot();
  }''',
r'''  function syncCodeBlock(codeEl) {
    var blk = codeEl.closest('.blk');
    var idx = blockIndexOf(blk);
    if (idx < 0) return;
    var lang = (state.raw[idx].split('\n')[0].match(/^```(.*)$/) || ['', ''])[1];
    var text = codeEl.textContent.replace(/\n+$/, '');
    /* v3.30.18（CODE-1）：内容含 ``` 行会在围栏中间提前闭合、后续内容溢出到
       文档（静默结构破坏）——拒绝回写并提示；保留原 raw，可转源码态改用
       四反引号围栏或删掉内嵌围栏行 */
    if (/^\s*```/m.test(codeEl.textContent)) {
      toastStatus('代码内容含 ``` 行，已阻止写入以免破坏围栏结构');
      return;
    }
    state.raw[idx] = '```' + lang + '\n' + text + '\n```';
    markDirty(); scheduleSnapshot();
  }''', "CODE-1")

# ---------- 2. CODE-2 ----------
rep(r'''  /* 代码区键盘：Enter 换行继续输入（不拆块/不退出），Tab 插入缩进 */
  ED.addEventListener('keydown', function (e) {
    var code = e.target.closest ? e.target.closest('#editor .codeblock code') : null;
    if (!code) return;
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      insertTextAtCaret('\n');
      syncCodeBlock(code);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      insertTextAtCaret('  ');
      syncCodeBlock(code);
    }
  });''',
r'''  /* 代码区键盘：Enter 换行继续输入（不拆块/不退出），Tab 插入缩进。
     v3.30.18（CODE-2）：补键盘退出路径 —— Esc / Ctrl+Enter 退出到下一块；
     方向键首行（↑/←）/ 末行末（↓/→）跳出（对齐标题 / 引用边界行为） */
  ED.addEventListener('keydown', function (e) {
    var code = e.target.closest ? e.target.closest('#editor .codeblock code') : null;
    if (!code) return;
    if (e.isComposing || e.keyCode === 229) return;
    var idxC = blockIndexOf(code.closest('.blk'));
    var codeText = code.textContent || '';
    var offC = caretRawOffset(code);
    var firstLenC = codeText.indexOf('\n');
    if (firstLenC < 0) firstLenC = codeText.length;
    var lastStartC = codeText.lastIndexOf('\n') + 1;
    if (e.key === 'Escape' || (e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
      e.preventDefault();
      syncCodeBlock(code);
      goToBlock(Math.min(idxC + 1, state.raw.length - 1), 'start');
      return;
    }
    if ((e.key === 'ArrowUp' && offC <= firstLenC || e.key === 'ArrowLeft' && offC === 0)
        && idxC > 0) {
      e.preventDefault();
      syncCodeBlock(code);
      goToBlock(idxC - 1, 'end');
      return;
    }
    if ((e.key === 'ArrowDown' && offC >= codeText.length && offC >= lastStartC
         || e.key === 'ArrowRight' && offC >= codeText.length)
        && idxC < state.raw.length - 1) {
      e.preventDefault();
      syncCodeBlock(code);
      goToBlock(idxC + 1, 'start');
      return;
    }
    if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      insertTextAtCaret('\n');
      syncCodeBlock(code);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      insertTextAtCaret('  ');
      syncCodeBlock(code);
    }
  });''', "CODE-2")

# ---------- 3. CODE-3 ----------
rep(r'''    var sbtn = document.createElement('button');
    sbtn.type = 'button';
    sbtn.className = 'lang-btn style-btn';
    sbtn.textContent = '风格';
    sbtn.title = '切换此代码块的风格（默认取系统设置）';
    sbtn.addEventListener('click', function (e) {
      e.stopPropagation(); e.preventDefault();
      SP._anchor = sbtn;
      buildStylePop(sbtn);
    });
    bar.appendChild(sbtn);''',
r'''    var sbtn = document.createElement('button');
    sbtn.type = 'button';
    sbtn.className = 'lang-btn style-btn';
    sbtn.textContent = '风格';
    sbtn.title = '切换此代码块的风格（默认取系统设置）';
    sbtn.addEventListener('click', function (e) {
      e.stopPropagation(); e.preventDefault();
      SP._anchor = sbtn;
      buildStylePop(sbtn);
    });
    bar.appendChild(sbtn);
    /* v3.30.18（CODE-3）：一键复制代码（Typora / VS Code 同款高频操作） */
    var cbtn = document.createElement('button');
    cbtn.type = 'button';
    cbtn.className = 'lang-btn copy-btn';
    cbtn.textContent = '复制';
    cbtn.title = '复制代码';
    cbtn.addEventListener('click', function (e) {
      e.stopPropagation(); e.preventDefault();
      copyTextToClipboard(code ? code.textContent : pre.textContent);
    });
    bar.appendChild(cbtn);''', "CODE-3")

# ---------- 4. F1a：langpop 置 activePop ----------
rep(r'''    langCtx = { idx: idx, act: preselect ? Math.max(0, CODE_LANGS.indexOf(preselect)) : 0, def: preselect || null };
    var q = document.getElementById('lang-q');''',
r'''    langCtx = { idx: idx, act: preselect ? Math.max(0, CODE_LANGS.indexOf(preselect)) : 0, def: preselect || null };
    activePop = 'lang';   /* v3.30.18（F1）：滚动收起 */
    var q = document.getElementById('lang-q');''', "F1-lang")

# ---------- 5. F1b：stylepop 置 activePop（buildStylePop 处） ----------
rep(r'''      SP._anchor = sbtn;
      buildStylePop(sbtn);
    });
    bar.appendChild(sbtn);''',
r'''      SP._anchor = sbtn;
      buildStylePop(sbtn);
      activePop = 'style';   /* v3.30.18（F1）：滚动收起 */
    });
    bar.appendChild(sbtn);''', "F1-style")

# ---------- 6. F1c：renpop 置 activePop ----------
rep(r'''    document.getElementById('ren-title').textContent = '修改图片存储名称';''',
r'''    document.getElementById('ren-title').textContent = '修改图片存储名称';
    activePop = 'ren';   /* v3.30.18（F1）：滚动收起 */''', "F1-ren")

# ---------- 7. F2：resize 统一收浮层 ----------
rep(r'''  if (window.addEventListener) window.addEventListener('resize', function () {
    if (rzTarget) syncRzFrame();
  });   /* node 内核测试的 window 桩无 addEventListener，做能力探测 */''',
r'''  if (window.addEventListener) window.addEventListener('resize', function () {
    if (rzTarget) syncRzFrame();
    /* v3.30.18（F2）：窗口缩放时浮层按旧坐标锚定会错位 —— 统一收起
       （缩放框自身由 syncRzFrame 重锚定，不受影响） */
    if (activePop) hidePops();
  });   /* node 内核测试的 window 桩无 addEventListener，做能力探测 */''', "F2")

# ---------- 8. F3：placePop 上缘钳位 ----------
rep(r'''    var ny = y;
    if (ny + h > window.innerHeight - 8) ny = Math.max(6, y - h - 30);
    pop.style.left = nx + 'px';''',
r'''    var ny = y;
    if (ny + h > window.innerHeight - 8) ny = Math.max(6, y - h - 30);
    if (ny < 6) ny = 6;   /* v3.30.18（F3）：上缘钳位（top−44 越出窗口上缘时） */
    pop.style.left = nx + 'px';''', "F3")

# ---------- 9. F4：hidePops 清 linkCtx / cpCtx ----------
rep(r'''    activePop = null; slashState = null; subCtx = null; hintState = null;
    tblSizeCtx = null; langCtx = null;
  }''',
r'''    activePop = null; slashState = null; subCtx = null; hintState = null;
    tblSizeCtx = null; langCtx = null;
    linkCtx = null; cpCtx = null;   /* v3.30.18（F4）：链接 / 图注弹层上下文一并清理 */
  }''', "F4")

# ---------- 10. FN-1：渲染层内脚注引用 ----------
rep(r'''      case 'footnote': {
        ensureEdit();
        var fi = state.editIdx;
        if (fi < 0 || !editEl()) return;''',
r'''      case 'footnote': {
        /* v3.30.18（FN-1）：引用 / 标题 / 列表 / 定义列表渲染层内的脚注引用 ——
           之前被 editEl() 守卫静默拦截，现在直接往渲染层光标处插入并手动回写
           （定义项仍追加到文末；「脚注定义」项在引用内依旧不支持） */
        var wysFn = null;
        if (state.editIdx < 0) {
          var selFn = getSelection();
          if (selFn.rangeCount) {
            var ancFn = selFn.getRangeAt(0).startContainer;
            ancFn = ancFn.nodeType === 1 ? ancFn : ancFn.parentElement;
            wysFn = ancFn ? ancFn.closest(
              '#editor blockquote,#editor li,#editor h1,#editor h2,#editor h3,#editor h4,#editor h5,#editor h6,#editor dt,#editor dd') : null;
            if (wysFn && wysFn.getAttribute('contenteditable') !== 'plaintext-only') wysFn = null;
          }
        }
        if (wysFn) {
          var numW = nextFootNum();
          insertTextAtCaret('[^' + numW + ']');
          var tagW = wysFn.tagName;
          if (tagW === 'LI') syncListLi(wysFn);
          else if (tagW === 'BLOCKQUOTE') syncQuoteEl(wysFn);
          else if (/^H[1-6]$/.test(tagW)) syncHeadingEl(wysFn);
          else if (tagW === 'DT' || tagW === 'DD') syncDeflistEl(wysFn);
          var hasDefW = false;
          for (var q3 = 0; q3 < state.raw.length; q3++) {
            if (new RegExp('^\\s*\\[\\^' + numW + '\\]:').test(state.raw[q3])) { hasDefW = true; break; }
          }
          if (!hasDefW) {
            state.raw.push('[^' + numW + ']: 脚注说明');
            rebuild();
            markDirty(); scheduleSnapshot();
            toastStatus('脚注 [^' + numW + '] 已插入，定义已追加到文末');
          }
          return;
        }
        ensureEdit();
        var fi = state.editIdx;
        if (fi < 0 || !editEl()) return;''', "FN-1")

# ---------- 11. DL-1：空 dd 回车升格 dt ----------
rep(r'''    if (isDL && e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      var dlEl = t.closest('dl');
      if (!dlEl) return;
      var nd = document.createElement('dd');''',
r'''    if (isDL && e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      var dlEl = t.closest('dl');
      if (!dlEl) return;
      /* v3.30.18（DL-1）：空 dd 上回车 → 升格为新 dt（新增术语，Typora 风格）——
         多术语对不再需要转源码手写；非空 dd 仍回车追加定义 */
      if (t.tagName === 'DD' && !(t.textContent || '').replace(/\u00a0/g, ' ').trim()) {
        var ndt = document.createElement('dt');
        ndt.setAttribute('contenteditable', 'plaintext-only');
        ndt.setAttribute('spellcheck', 'false');
        t.parentNode.replaceChild(ndt, t);
        syncDeflistEl(ndt);
        ndt.focus(); setCaret(ndt, 0);
        return;
      }
      var nd = document.createElement('dd');''', "DL-1")

# ---------- 12. copyTextToClipboard 工具函数（挂在 enhanceFence 前） ----------
rep(r'''  /* 代码块增强：顶部语言栏（可点击选择语言）+ 风格按钮 + 行号 + 代码区直接编辑 */
  function enhanceFence(div) {''',
r'''  /* v3.30.18（CODE-3）：纯文本复制 —— 隐藏 textarea + execCommand('copy')
     （QWebEngine file:// 上下文 navigator.clipboard 不可靠），结果 toast */
  function copyTextToClipboard(text) {
    var ta = document.createElement('textarea');
    ta.value = String(text == null ? '' : text);
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e1) { ok = false; }
    document.body.removeChild(ta);
    toastStatus(ok ? '已复制到剪贴板' : '复制失败，请手动选择复制');
  }
  /* 代码块增强：顶部语言栏（可点击选择语言）+ 风格按钮 + 行号 + 代码区直接编辑 */
  function enhanceFence(div) {''', "copy-fn")

with io.open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("ALL PATCHED")
