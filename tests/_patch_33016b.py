# -*- coding: utf-8 -*-
# v3.30.16 图片能力：右键「复制图片」+ 浮层「显示」（应用内大图预览）
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
s = io.open(P, encoding="utf-8").read()
orig = s
PATCHES = []

# 1) CSS：大图预览遮罩
OLD1 = """.pop.show { display: block; animation: popin 0.12s ease; }
@keyframes popin { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }"""
NEW1 = OLD1 + """
/* v3.30.16 图片大图预览（浮层「显示」按钮 / 右键「复制图片」） */
#imgview { position: fixed; left: 0; top: 0; right: 0; bottom: 0; z-index: 9999;
  display: none; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, .72); cursor: zoom-out; }
#imgview.show { display: flex; }
#imgview img { max-width: 92vw; max-height: 88vh; background: #fff; border-radius: 4px;
  box-shadow: 0 10px 44px rgba(0, 0, 0, .55); }
#imgview-bar { position: absolute; top: 14px; right: 18px; display: flex;
  align-items: center; gap: 10px; color: #fff; font-size: 12.5px; }
#imgview-bar button { border: 1px solid rgba(255,255,255,.55); background: rgba(255,255,255,.12);
  color: #fff; border-radius: 6px; padding: 3px 10px; cursor: pointer; font-size: 12.5px; }
#imgview-bar button:hover { background: rgba(255,255,255,.24); }"""
PATCHES.append(("CSS-IMGVIEW", OLD1, NEW1))

# 2) DOM：预览浮层
OLD2 = """<div id="emojipop" class="pop"></div>"""
NEW2 = OLD2 + """
<div id="imgview">
  <div id="imgview-bar"><span id="imgview-name"></span><button type="button" id="imgview-close">关闭 ✕</button></div>
  <img id="imgview-img" alt="">
</div>"""
PATCHES.append(("DOM-IMGVIEW", OLD2, NEW2))

# 3) 预览 / 复制函数 + 事件绑定
OLD3 = """  /* ---------- 对象操作条（图片 / 图表选中后浮现） ---------- */"""
NEW3 = """  /* ---------- v3.30.16 图片：大图预览（浮层「显示」）/ 复制图片到剪贴板 ---------- */
  var imgViewIdx = -1;
  function openImgPreview(idx) {
    var IV = document.getElementById('imgview');
    var IM = document.getElementById('imgview-img');
    if (!IV || !IM) return;
    var src = imgRawSrc(idx);
    if (!src) { toastStatus('图片地址为空，无法预览'); return; }
    IM.onerror = function () { toastStatus('图片预览失败：无法加载该地址'); };
    /* 相对路径按文档目录解析成 file://（与正文 img 同一套解析，见 resolveImgSrc） */
    IM.src = resolveImgSrc(src);
    var nb = document.getElementById('imgview-name');
    if (nb) {
      var nm = String(src);
      if (/^data:/i.test(nm)) nm = '内嵌图片';
      else {
        var k = Math.max(nm.lastIndexOf('/'), nm.lastIndexOf('\\\\'));
        if (k >= 0) nm = nm.slice(k + 1);
        try { nm = decodeURIComponent(nm); } catch (e2) {}
      }
      nb.textContent = nm.slice(0, 48);
    }
    imgViewIdx = idx;
    IV.classList.add('show');
  }
  function closeImgPreview() {
    var IV = document.getElementById('imgview');
    var IM = document.getElementById('imgview-img');
    if (IV) IV.classList.remove('show');
    if (IM) { IM.onerror = null; IM.removeAttribute('src'); }
    imgViewIdx = -1;
  }
  /* 复制图片：位图进系统剪贴板（经 Python 落剪贴板，见 mainwindow._img_copy）。
     不用 navigator.clipboard.write —— QtWebEngine 下受权限 / 手势限制不可靠，
     且远程图还要先下载；Python 侧 QImage 一条路覆盖 本地 / data URL / 网络图 */
  function copyImgToClipboard(idx) {
    var src = imgRawSrc(idx);
    if (!src) { toastStatus('图片地址为空，无法复制'); return; }
    sendImgReq({ act: 'imgCopy', idx: idx, src: src });
  }
  (function () {
    var IV = document.getElementById('imgview');
    var CB = document.getElementById('imgview-close');
    if (IV) IV.addEventListener('mousedown', function (e) {
      if (e.target === IV || e.target.id === 'imgview-img') closeImgPreview();
    });
    if (CB) CB.addEventListener('click', function (e) { e.stopPropagation(); closeImgPreview(); });
    /* 预览打开时 Esc 关闭（捕获阶段，优先于编辑器的 Esc 处理） */
    document.addEventListener('keydown', function (e) {
      if (imgViewIdx < 0) return;
      if (e.key === 'Escape' || e.key === 'Esc') {
        e.preventDefault(); e.stopPropagation(); closeImgPreview();
      }
    }, true);
  })();

""" + OLD3
PATCHES.append(("FN-IMGVIEW", OLD3, NEW3))

# 4) 浮层「显示」按钮（图片块专用，恒定显示）
OLD4 = """      var canStore = !!window.__docDir || isAbs;
      if (isLocalImg) {"""
NEW4 = """      var canStore = !!window.__docDir || isAbs;
      /* v3.30.16：「显示」= 应用内大图预览，与存储状态无关，固定排在最前 */
      items.unshift(['显示', function () { openImgPreview(idx); },
        '显示图片（大图预览，点击任意处或 Esc 关闭）']);
      if (isLocalImg) {"""
PATCHES.append(("BAR-VIEW", OLD4, NEW4))

# 5) 右键菜单：图片块加「复制图片」
OLD5 = """      if (kind === 'chart')
        html += '<div class="mi" data-act="dup"><span style="width:18px;text-align:center">⧉</span>复制块</div>';"""
NEW5 = OLD5 + """
      /* v3.30.16：图片块右键「复制图片」—— 位图进剪贴板（可粘贴到微信 / Word），
         区别于「复制块」（在文档内复制一份） */
      if (kind === 'image')
        html += '<div class="mi" data-act="copyimg"><span style="width:18px;text-align:center">🖼</span>复制图片</div>';"""
PATCHES.append(("MENU-COPY", OLD5, NEW5))

# 6) 动作分发
OLD6 = """    if (act === 'edit') { openBlockEditor(i); return; }"""
NEW6 = """    if (act === 'edit') { openBlockEditor(i); return; }
    /* v3.30.16：图片块右键「复制图片」—— 只写剪贴板，不改文档、不入撤销历史 */
    if (act === 'copyimg') { hidePops(); copyImgToClipboard(i); return; }
    /* v3.30.16：图片块「显示图片」—— 应用内大图预览 */
    if (act === 'viewimg') { hidePops(); openImgPreview(i); return; }"""
PATCHES.append(("ACT-DISPATCH", OLD6, NEW6))

# 7) 测试钩子
OLD7 = """    return (rzTarget && rzTarget.kind === 'table') ? 'ok' : 'noframe';
  };"""
NEW7 = OLD7 + """
  /* v3.30.16 测试辅助：大图预览状态 / 触发复制图片（供回归用例检查） */
  window.__imgView = function () {
    var IV = document.getElementById('imgview');
    var IM = document.getElementById('imgview-img');
    return JSON.stringify({ show: !!(IV && IV.classList.contains('show')),
                            src: IM ? (IM.getAttribute('src') || '') : '',
                            name: (document.getElementById('imgview-name') || {}).textContent || '' });
  };
  window.__imgCopy = function (idx) {
    copyImgToClipboard(idx);
    var r = window.__req;
    return JSON.stringify({ act: r ? r.act : null, idx: r ? r.idx : null,
                            srcLen: r && r.src ? String(r.src).length : 0 });
  };
  window.__imgViewOpen = function (idx) { openImgPreview(idx); return window.__imgView(); };"""
PATCHES.append(("HOOK", OLD7, NEW7))

fails = []
for name, o, n in PATCHES:
    cnt = s.count(o)
    if cnt != 1:
        fails.append("%s hits=%d" % (name, cnt))
        continue
    s = s.replace(o, n, 1)

if fails:
    sys.stdout.write("FAILED: " + "; ".join(fails) + "\n")
    sys.exit(1)

io.open(P, "w", encoding="utf-8", newline="").write(s)
sys.stdout.write("OK patched %d, len %d -> %d\n" % (len(PATCHES), len(orig), len(s)))
