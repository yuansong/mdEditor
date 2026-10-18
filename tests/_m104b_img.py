# -*- coding: utf-8 -*-
"""m104b 图片模块复验：改用右键（contextmenu）打开图片块菜单，重跑 C/D/E/F，并诊断 B5

_m104 教训：#blkhandle 点击未更新 handleIdx → 菜单未打开（show=false）。
源码 5972-5986：块上右键 → 非源码态且 specialBlockKind → showSpecialBlockMenuAt（含图片分支）。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m104b_img.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        ABN.append(name + " || " + detail)
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(timeout, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


wait(2800)

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
       "hQGAhKmMIQAAAABJRU5ErkJggg==")
NET = "https://example.com/pic.png"


def rawof():
    try:
        return (json.loads(js("window.__raw()") or "{}").get("raw")) or []
    except Exception:
        return []


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def nblk():
    return int(jj("JSON.stringify({n:document.querySelectorAll('#editor .blk').length})").get("n") or 0)


def istate():
    return jj("(function(){var im=document.querySelector('#editor img');"
              "var fig=document.querySelector('#editor figure');"
              "var cap=document.querySelector('#editor figcaption');"
              "return JSON.stringify({sel:im?im.classList.contains('sel'):null,"
              "imgStyle:im?(im.getAttribute('style')||''):'',"
              "figCls:fig?fig.className:'',cap:cap?(cap.textContent||''):'',"
              "ae:document.activeElement?(document.activeElement.tagName+(document.activeElement.isContentEditable?'[ce]':'')):''})})()")


def ctx_img():
    """右键图片 → 弹出图片块菜单"""
    r = js("(function(){var im=document.querySelector('#editor img');if(!im)return 'no-img';"
           "var r=im.getBoundingClientRect();"
           "im.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
           "clientX:r.left+2,clientY:r.top+2}));return 'ok'})()")
    wait(560)
    return r


def mi_list():
    return jj("(function(){var BM=document.getElementById('blkmenu');"
              "if(!BM)return JSON.stringify({no:1});"
              "return JSON.stringify({show:BM.classList.contains('show'),"
              "cap:(BM.querySelector('.cap')||{}).textContent||'',"
              "items:[].slice.call(BM.querySelectorAll('.mi')).map(function(m){"
              "return m.getAttribute('data-act')+'|'+m.textContent.trim()})})})()")


def mi_click(act):
    js("(function(){var BM=document.getElementById('blkmenu');"
       "var it=BM&&BM.querySelector('.mi[data-act=\"" + act + "\"]');"
       "if(!it)return 'no-item';"
       "it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(620)


note("========== C0 右键菜单构成 ==========")
setmd("![图甲](" + PNG + ")")
ctx_img()
bm = mi_list()
labels = [str(x) for x in bm.get("items", [])]
acts = [str(x).split("|")[0] for x in labels]
note("  菜单=%s" % json.dumps(labels, ensure_ascii=False))
check("C0 右键图片 → 弹出「图片块」菜单", "图片块" in str(bm.get("cap", "")), "cap=%s" % bm.get("cap"))
# v3.39.5（MENU-4）：恢复「省略当前状态项」——默认居中 → 无 imgalign:c，只显示靠左/靠右
for need in ("edit", "imgreset", "imgsize", "imgalign:l", "imgalign:r",
             "imgreplace", "viewimg", "copyimg", "dup", "up", "down", "del"):
    check("C1 菜单含 %s" % need, need in acts, "acts=%s" % json.dumps(acts))
check("C1b 当前项省略（默认居中无 imgalign:c）", "imgalign:c" not in acts,
      "acts=%s" % json.dumps(acts))

# C1c（MENU-3/4）：并排行结构 + 菜单加宽 + 全部单行
rows = jj("(function(){var BM=document.getElementById('blkmenu');"
          "if(!BM)return '{}';"
          "var rows=[].slice.call(BM.querySelectorAll('.mirow')).map(function(r){"
          "return [].slice.call(r.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')})});"
          "var wide=BM.classList.contains('wide');"
          "var wrap=[].slice.call(BM.querySelectorAll('.mi')).filter(function(m){return m.clientHeight>42}).map(function(m){return m.getAttribute('data-act')});"
          "var w=BM.getBoundingClientRect().width;"
          "return JSON.stringify({rows:rows,wide:wide,wrap:wrap,w:w})})()")
rrows = rows.get("rows") or []
def row_of(act):
    for r in rrows:
        if act in (r or []): return r
    return None
check("C1c-1 菜单加宽 .wide（≥240px）", rows.get("wide") is True and float(rows.get("w") or 0) >= 240,
      "wide=%s w=%s" % (rows.get("wide"), rows.get("w")))
check("C1c-2 对齐同行且当前项省略（默认居中 → 行内仅 靠左+靠右）",
      row_of("imgalign:l") == ["imgalign:l", "imgalign:r"],
      "rows=%s" % json.dumps(rrows))
check("C1c-3 重置尺寸+大小设置同行", row_of("imgreset") == ["imgreset", "imgsize"],
      "rows=%s" % json.dumps(rrows))
check("C1c-4 替换图片+显示图片同行", row_of("imgreplace") == ["imgreplace", "viewimg"],
      "rows=%s" % json.dumps(rrows))
check("C1c-5 复制图片+复制块同行", row_of("copyimg") == ["copyimg", "dup"],
      "rows=%s" % json.dumps(rrows))
check("C1c-8 裁剪图片+图注同级并排一行（v3.39.8 MENU-5）", row_of("imgcrop") == ["imgcrop", "edit"],
      "rows=%s" % json.dumps(rrows))
check("C1c-6 全部菜单项单行不换行", not rows.get("wrap"),
      "wrap=%s" % json.dumps(rows.get("wrap")))
check("C1c-7 存储项不并入并排行（独立行）", row_of("imgmode") is None and row_of("imgrename") is None,
      "rows=%s" % json.dumps(rrows))

note("========== C2 对齐写入 ==========")
setmd("![图甲](" + PNG + ")")
ctx_img()
mi_click("imgalign:l")
g = rawof()
s = istate()
check("C2 靠左 → 写入 figure fig-l 并渲染", g and "fig-l" in str(g[0]),
      "raw=%s cls=%s" % (json.dumps(g, ensure_ascii=False)[:200], s.get("figCls")))
setmd("![图甲](" + PNG + ")")
ctx_img()
mi_click("imgalign:r")
g = rawof()
check("C2b 靠右 → 写入 figure fig-r", g and "fig-r" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

# C2c（MENU-4）：① 当前项省略 → 点 imgalign:c 应无此项；② 切换后菜单动态刷新
setmd("![图甲](" + PNG + ")")
ctx_img()
r_noc = js("(function(){var BM=document.getElementById('blkmenu');"
           "var it=BM&&BM.querySelector('.mi[data-act=\"imgalign:c\"]');"
           "return it?'exists':'no-item'})()")
check("C2c-1 当前已生效项（居中）不在菜单中", r_noc == "no-item", "got=%s" % r_noc)
mi_click("imgalign:l")   # 切到靠左（菜单应用后关闭）
ctx_img()                # 重新打开 → 应显示 居中+靠右，隐藏 靠左
rows2 = jj("(function(){var BM=document.getElementById('blkmenu');"
           "var r=[].slice.call(BM.querySelectorAll('.mirow')).map(function(r){"
           "return [].slice.call(r.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')})});"
           "return JSON.stringify(r)})()")
al2 = None
for rr in (rows2 or []):
    if "imgalign:c" in (rr or []): al2 = rr
check("C2c-2 切靠左后重开菜单 → 动态刷新（行内=居中+靠右，无靠左）",
      al2 == ["imgalign:c", "imgalign:r"],
      "rows=%s" % json.dumps(rows2))
g = rawof()
check("C2c-3 靠左已写入 figure fig-l", g and "fig-l" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

note("========== C3 图注写入 ==========")
setmd("![图甲](" + PNG + ")")
ctx_img()
mi_click("edit")
wait(480)
cp = jj("(function(){var CP=document.getElementById('cappop');"
        "return JSON.stringify({show:CP?CP.classList.contains('show'):null,"
        "title:(document.getElementById('cappop-title')||{}).textContent||''})})()")
note("  图注弹层=%s" % json.dumps(cp, ensure_ascii=False))
js("(function(){var CP=document.getElementById('cappop');"
   "var inp=CP?CP.querySelector('input'):null;if(!inp)return 'no-input';"
   "inp.value='新图注甲';inp.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
wait(240)
js("(function(){var b=document.getElementById('cap-ok');"
   "if(!b)return 'no-ok';b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(680)
g = rawof()
s = istate()
check("C3 图注写入 → raw 含 figcaption 且渲染可见",
      (g and "新图注甲" in str(g[0])) and s.get("cap") == "新图注甲",
      "raw=%s cap=%s" % (json.dumps(g, ensure_ascii=False)[:220], s.get("cap")))

note("========== D 尺寸 ==========")
setmd("![图甲](" + PNG + ")")
ctx_img()
mi_click("imgsize")
wait(480)
js("(function(){var w=document.getElementById('imgsize-w');if(!w)return 'no-w';"
   "w.value='180';w.dispatchEvent(new Event('input',{bubbles:true}));"
   "var p=document.getElementById('imgsizepop');"
   "if(!p)return 'no-pop';"
   "p.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(680)
g = rawof()
check("D1 只填宽 → width:180px", g and "width:180px" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:220])

setmd("![图甲](" + PNG + ")")
ctx_img()
mi_click("imgsize")
wait(480)
js("(function(){var w=document.getElementById('imgsize-w'),h=document.getElementById('imgsize-h');"
   "if(!w||!h)return 'no';w.value='180';h.value='90';"
   "w.dispatchEvent(new Event('input',{bubbles:true}));h.dispatchEvent(new Event('input',{bubbles:true}));"
   "document.getElementById('imgsizepop').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(680)
g = rawof()
check("D2 两维都填 → width+height", g and "width:180px" in str(g[0]) and "height:90px" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:220])

setmd('<figure class="md-fig">\n<img src="' + PNG + '" alt="图乙" style="width:180px">\n'
      '<figcaption>保留图注</figcaption>\n</figure>')
ctx_img()
mi_click("imgreset")
wait(680)
g = rawof()
s = istate()
check("D3 保留图注时重置尺寸 → 仅清 style，图注与 figure 保留",
      g and "width" not in str(g[0]) and "保留图注" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:220])

note("========== E 块操作 ==========")
setmd("前段\n\n![图甲](" + PNG + ")\n\n尾段")
ctx_img()
mi_click("dup")
wait(680)
g = rawof()
check("E1 复制块 → 文档内多一份图片块", len(g) == 4 and g[1] == g[2],
      "n=%s raw=%s" % (len(g), json.dumps([x[:26] for x in g], ensure_ascii=False)))

setmd("![图甲](" + PNG + ")\n\n尾段")
ctx_img()
dis = jj("(function(){var BM=document.getElementById('blkmenu');"
         "var up=BM.querySelector('.mi[data-act=\"up\"]');"
         "var dn=BM.querySelector('.mi[data-act=\"down\"]');"
         "return JSON.stringify({upDis:up?up.classList.contains('dis'):null,"
         "dnDis:dn?dn.classList.contains('dis'):null})})()")
note("  首块边界态=%s" % json.dumps(dis))
check("E2 首块「上移」置灰（边界提示）", dis.get("upDis") is True, "dis=%s" % json.dumps(dis))

setmd("前段\n\n![图甲](" + PNG + ")")
ctx_img()
mi_click("del")
wait(680)
g = rawof()
check("E3 删除块 → 图片块移除、其余保留", len(g) == 1 and g[0] == "前段",
      "raw=%s" % json.dumps([x[:26] for x in g], ensure_ascii=False))

setmd("![图甲](" + PNG + ")\n\n尾段")
ctx_img()
mi_click("down")
wait(680)
g = rawof()
check("E5 下移 → 与后一块交换顺序", len(g) == 2 and "尾段" == str(g[0]),
      "raw=%s" % json.dumps([x[:26] for x in g], ensure_ascii=False))

note("========== F 网络图片存储项 ==========")
setmd("![网络图](" + NET + ")")
ctx_img()
bm = mi_list()
labels = [str(x) for x in bm.get("items", [])]
note("  网络图菜单=%s" % json.dumps(labels, ensure_ascii=False))
# IMG-13（v3.38）：存储项统一为「转本地存储」（imglocalall，仅网络图片显示）
check("F2 网络图片菜单出现「转本地存储」",
      any("转本地存储" in x for x in labels), "items=%s" % json.dumps(labels, ensure_ascii=False))
check("F2b 内嵌/网络时不再显示「修改图片名称」",
      not any("修改图片名称" in x for x in labels), "items=%s" % json.dumps(labels, ensure_ascii=False))

note("========== H 选中后键盘删除（_m104 B5 诊断） ==========")
setmd("前段\n\n![图甲](" + PNG + ")\n\n尾段")
js("(function(){var im=document.querySelector('#editor img');"
   "if(!im)return 'no-img';"
   "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));return 'ok'})()")
wait(420)
s1 = istate()
note("  点击图片后 sel=%s activeElement=%s" % (s1.get("sel"), s1.get("ae")))
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}))")
wait(520)
nb_after = nblk()
note("  焦点在可编辑元素时按 Delete → 块数=%s（3=未删）" % nb_after)
js("(function(){if(document.activeElement&&document.activeElement.blur)document.activeElement.blur();"
   "var im=document.querySelector('#editor img');"
   "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));return 'ok'})()")
wait(420)
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}))")
wait(560)
nb_after2 = nblk()
g = rawof()
note("  失焦后按 Delete → 块数=%s raw=%s" % (nb_after2, json.dumps([x[:20] for x in g], ensure_ascii=False)))
# IMG-13（批次十七）定版行为：选中图片后即便焦点不在编辑元素，Delete 也删除图片块
check("H1 图片已删后再次 Delete 不误删其它块", nb_after2 == nb_after,
      "before=%s after=%s" % (nb_after, nb_after2))
check("H2 选中图片后 Delete 生效（blur 态删除图片块）", nb_after == 2,
      "after=%s" % nb_after)

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
