# -*- coding: utf-8 -*-
"""v3.30.17 任务2/3/4补丁（修订版）：
任务3 CSS 已在上一版应用（幂等跳过）；其余按对替换，buildObjbar 用标记切割。
注意：含反斜杠的片段必须用 r 字符串或正确加倍转义。"""
import io

n = 0


def rep(src, old, new, tag):
    c = src.count(old)
    assert c == 1, "%s match count=%d" % (tag, c)
    return src.replace(old, new)


def patch(path, pairs):
    global n
    src = io.open(path, encoding="utf-8").read()
    for old, new, tag in pairs:
        src = rep(src, old, new, tag)
        n += 1
    io.open(path, "w", encoding="utf-8").write(src)


E = r"E:\WorkBuddy\md-editor\src\editor.html"
M = r"E:\WorkBuddy\md-editor\src\mainwindow.py"

# ================= 任务 2：标注入口迁移 =================
pairs2 = [
    ("""    /* —— 清空 / 标注 —— */
    mi(svgIcon('clr'), '清空内容', 'clear');
    mi(svgIcon('cap'), '表格标注（上方 / 下方）', 'cap');""",
     """    /* —— 清空（v3.30.17：「标注」入口迁至表格选中后的悬浮工具按钮 —— ） */
    mi(svgIcon('clr'), '清空内容', 'clear');""", "cap-item"),

    ("""    if (TB) TB.classList.remove('show');
    openCapPop('tbl', idx, tbl.getBoundingClientRect(), cur, curTop);""",
     """    if (TB) TB.classList.remove('show');
    if (OB) OB.classList.remove('show');
    openCapPop('tbl', idx, tbl.getBoundingClientRect(), cur, curTop);""", "cap-ob-hide"),

    ("""  function selectTblFrame(idx, tblEl) {
    if (!tblEl) return;
    clearObjSelClass();
    tblEl.classList.add('sel');
    objSel = { kind: 'table', idx: idx, el: tblEl };   // 表格只用缩放框，不加对象操作条
    showRzFrame(tblEl, 'table', idx);
  }""",
     """  function selectTblFrame(idx, tblEl) {
    if (!tblEl) return;
    clearObjSelClass();
    tblEl.classList.add('sel');
    objSel = { kind: 'table', idx: idx, el: tblEl };
    showRzFrame(tblEl, 'table', idx);
    /* v3.30.17：表格悬浮工具按钮 —— 「标注」自右键菜单迁至此处（上方 / 下方
       的选择保留在标注弹层里）。与图片 / 图表操作条同款样式，悬在表格上方 */
    buildObjbar('tbl', idx);
    var r = tblEl.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }""", "select-tbl-frame"),
]
patch(E, pairs2)

# ---- buildObjbar：标记切割整体替换（新 tbl 分支 + 仅剩 mmd；图片分支删除） ----
src = io.open(E, encoding="utf-8").read()
START = "  function buildObjbar(kind, idx) {"
END = "  /* ---------- v3.25 图片存储操作：重命名 / 内嵌 ↔ 相对路径（经 Python 落盘） ---------- */"
i0 = src.index(START)
i1 = src.index(END)
NEW_BAR = r'''  function buildObjbar(kind, idx) {
    OB.innerHTML = '';
    var items;
    if (kind === 'tbl') {
      /* v3.30.17：表格悬浮工具按钮 —— 「标注」（上方 / 下方在弹层里选） */
      items = [['标注', function () { openTblCaption(idx); },
        '添加 / 修改表格标注（可放在上方或下方）']];
    } else {
      /* v3.30.17：图片不再使用悬浮按钮条（操作全部收进图片右键菜单），
         此分支只剩图表（mmd）—— 基础两项 + 源码 / 删除 */
      items = [
        ['图注', function () { editCaption(kind, idx); }, '添加 / 修改图注（可放在上方或下方）'],
        ['重置尺寸', function () { resetObjSize(kind, idx); }, '恢复原始尺寸'],
        ['源码', function () { openMmdEditor(ED.children[idx], idx); }, '编辑图表源码'],
        /* v3.25：图表保留删除按钮；图片块改用 DEL / Backspace 删除（见下方 keydown） */
        ['删除', function () { deleteBlockAt(idx); hideObjSel(); }, '删除整块']
      ];
    }
    items.forEach(function (b) {
      var el = document.createElement('button');
      el.type = 'button';
      el.textContent = b[0];
      el.title = b[2];
      el.addEventListener('mousedown', function (ev) { ev.preventDefault(); ev.stopPropagation(); });
      el.addEventListener('click', function (ev) { ev.stopPropagation(); b[1](); });
      OB.appendChild(el);
    });
  }
'''
src = src[:i0] + NEW_BAR + src[i1:]
n += 1
io.open(E, "w", encoding="utf-8").write(src)

# ================= 任务 4：图片交互重构 =================
pairs4 = [
    ("""  function selectObj(kind, idx, el) {
    if (!el) { hideObjSel(); return; }
    clearObjSelClass();
    el.classList.add('sel');
    objSel = { kind: kind, idx: idx, el: el };
    showRzFrame(el, kind, idx);
    buildObjbar(kind, idx);
    var r = el.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }""",
     """  function selectObj(kind, idx, el) {
    if (!el) { hideObjSel(); return; }
    clearObjSelClass();
    el.classList.add('sel');
    objSel = { kind: kind, idx: idx, el: el };
    showRzFrame(el, kind, idx);
    /* v3.30.17：图片操作全部收进右键菜单 —— 选中只出蓝框，不再浮现按钮条；
       图表（mmd）保留悬浮按钮条 */
    if (kind === 'img') return;
    buildObjbar(kind, idx);
    var r = el.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }""", "select-obj"),

    ("""      if (!blk.classList.contains('raw-edit') && specialBlockKind(bi)) {
        e.preventDefault();
        hidePops();
        showSpecialBlockMenuAt(bi, e.clientX, e.clientY);
        return;
      }""",
     """      if (!blk.classList.contains('raw-edit') && specialBlockKind(bi)) {
        e.preventDefault();
        hidePops();
        /* v3.30.17：右键图片 → 先选中（蓝框）再弹菜单，操作对象与所见一致 */
        var _imgT = e.target.closest ? e.target.closest('#editor img') : null;
        if (_imgT && blk.querySelector('img') === _imgT) selectObj('img', bi, _imgT);
        showSpecialBlockMenuAt(bi, e.clientX, e.clientY);
        return;
      }""", "ctx-img-select"),

    (r"""    } else {
      if (SPEC_EDIT[kind]) {
        html += '<div class="mi" data-act="edit"><span style="width:18px;text-align:center">✎</span>' +
                SPEC_EDIT[kind] + '</div>';
        html += '<div class="sep"></div>';
      }
      /* v3.30.10（MMD-5）：图表块菜单补「复制块」（dup 为通用动作）；
         图片块维持 v3.24 决策不加复制块 */
      if (kind === 'chart')
        html += '<div class="mi" data-act="dup"><span style="width:18px;text-align:center">⧉</span>复制块</div>';
      /* v3.30.16：图片块右键「复制图片」—— 位图进剪贴板（可粘贴到微信 / Word），
         区别于「复制块」（在文档内复制一份） */
      if (kind === 'image')
        html += '<div class="mi" data-act="copyimg"><span style="width:18px;text-align:center">🖼</span>复制图片</div>';
      html += '<div class="mi" data-act="up"><span style="width:18px;text-align:center">⬆</span>上移</div>';""",
     r"""    } else if (kind === 'image') {
      /* v3.30.17：图片右键菜单（替代悬浮按钮条）—— 图注 / 重置尺寸恒显；
         存储项按当前存储方式动态显示：相对路径 → 转内嵌 + 修改图片名称；
         内嵌 / 网络 → 转相对路径。未保存文档（无 __docDir）且非绝对路径时
         不显示存储项（点了只会得到「请先保存文档」报错）。
         显示 / 复制图片 / 上移 / 下移 / 删除块保留 */
      html += '<div class="mi" data-act="edit"><span style="width:18px;text-align:center">✎</span>图注</div>';
      html += '<div class="mi" data-act="imgreset"><span style="width:18px;text-align:center">↺</span>重置尺寸</div>';
      var _isrc = imgRawSrc(idx), _isData = /^data:/i.test(_isrc), _isRemote = /^https?:/i.test(_isrc);
      var _isAbs = /^(?:[A-Za-z]:[\\/]|file:)/i.test(_isrc);
      var _canStore = !!window.__docDir || _isAbs;
      if (_isrc && !_isData && !_isRemote) {
        if (_canStore) {
          html += '<div class="mi" data-act="imgmode"><span style="width:18px;text-align:center">🔄</span>转化为内嵌式存储</div>';
          html += '<div class="mi" data-act="imgrename"><span style="width:18px;text-align:center">✏</span>修改图片名称</div>';
        }
      } else if (_canStore) {
        html += '<div class="mi" data-act="imgmode"><span style="width:18px;text-align:center">🔄</span>转化为相对路径存储</div>';
      }
      html += '<div class="sep"></div>';
      /* v3.30.16：「显示图片」= 应用内大图预览（Esc / 点遮罩关闭） */
      html += '<div class="mi" data-act="viewimg"><span style="width:18px;text-align:center">👁</span>显示图片</div>';
      /* v3.30.16：「复制图片」—— 位图进剪贴板（可粘贴到微信 / Word），
         区别于「复制块」（在文档内复制一份） */
      html += '<div class="mi" data-act="copyimg"><span style="width:18px;text-align:center">🖼</span>复制图片</div>';
      html += '<div class="sep"></div>';
      html += '<div class="mi" data-act="up"><span style="width:18px;text-align:center">⬆</span>上移</div>';""",
     "img-menu"),

    ("""    /* v3.30.16：图片块「显示图片」—— 应用内大图预览 */
    if (act === 'viewimg') { hidePops(); openImgPreview(i); return; }""",
     """    /* v3.30.16：图片块「显示图片」—— 应用内大图预览 */
    if (act === 'viewimg') { hidePops(); openImgPreview(i); return; }
    /* v3.30.17：图片右键菜单 —— 重置尺寸 / 存储转换 / 修改图片名称 */
    if (act === 'imgreset') { hidePops(); resetObjSize('img', i); return; }
    if (act === 'imgmode') { hidePops(); requestImgModeSwitch(i); return; }
    if (act === 'imgrename') { hidePops(); openRenamePop(i); return; }""", "apply-acts"),

    (r"""  function imgRawSrc(idx) {
    var spec = figFromRaw(state.raw[idx]);
    return spec ? spec.src : '';
  }""",
     r"""  function imgRawSrc(idx) {
    var spec = figFromRaw(state.raw[idx]);
    return spec ? spec.src : '';
  }
  /* v3.30.17：状态栏图片描述（存储方式 + 存储文件名），随 getCaretLineCol 轮询回报 */
  function imgStatusLabel(idx) {
    var src = imgRawSrc(idx);
    if (!src) return '';
    if (/^data:/i.test(src)) return '图片 · 内嵌存储';
    if (/^https?:/i.test(src)) return '图片 · 网络图片';
    var k = Math.max(src.lastIndexOf('/'), src.lastIndexOf('\\'));
    var name = k >= 0 ? src.slice(k + 1) : src;
    try { name = decodeURIComponent(name); } catch (e2) {}
    var abs = /^(?:[A-Za-z]:[\\/]|file:)/i.test(src);
    return '图片 · ' + (abs ? '绝对路径存储' : '相对路径存储') + ' · ' + name;
  }
  window.__imgStatusLabel = function (idx) { return imgStatusLabel(idx); };""", "img-status-fn"),

    ("""      if (bi < 0 || bi >= state.raw.length) return null;""",
     """      if (bi < 0 || bi >= state.raw.length) {
        /* v3.30.17：未在文字编辑态 —— 选中图片时回报存储方式 / 文件名（状态栏），
           未选中回报空（Python 清掉上一条的图片状态） */
        return JSON.stringify({ imgsel: 1,
          type: (objSel && objSel.kind === 'img') ? imgStatusLabel(objSel.idx) : '' });
      }""", "caret-imgsel"),
]
patch(E, pairs4)

patch(M, [
    ("""        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}")
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")""",
     """        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}")
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")
        elif isinstance(data, dict) and data.get("imgsel"):
            # v3.30.17：选中图片 → 状态栏显示存储方式 / 存储文件名；取消选中 → 清空
            self._blktype.setText(data.get("type") or "")""", "py-caret"),
])

print("patched ok, %d replacements" % n)
