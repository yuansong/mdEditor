# -*- coding: utf-8 -*-
"""m78 回归：v3.30.17 四项交互改动

  1) 表格标注入口 = 选中表格后的悬浮工具条「标注」按钮（右键菜单已无此项）；
     弹层保留上方 / 下方选择
  2) 表格「+」按钮外框为矩形（border-radius 3px，不再是 50% 圆形）
  3) 图片选中：不出现悬浮按钮条（只出蓝框）；右键菜单项按存储方式动态；
  4) 选中图片 → getCaretLineCol 回报 imgsel + 存储方式 / 文件名（状态栏显示）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m78.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def parse(s):
    try:
        return json.loads(s)
    except Exception:
        return {"err": str(s)[:160]}


def raw():
    return parse(js("window.__raw()")).get("raw") or [""]


wait(3000)

# ---------- 1. 表格标注入口（悬浮工具条） ----------
TBL = "| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |"
js("window.setMarkdown(%s)" % json.dumps(TBL))
wait(700)
# 真实路径：点击单元格选中表格 → 悬浮工具条浮现
CLICK_CELL = ("(function(){var td=document.querySelector('#editor .b-table td');"
              "var r=td.getBoundingClientRect();"
              "td.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
              "clientX:r.left+5,clientY:r.top+5,button:0,detail:1}));return 'ok'})()")
js(CLICK_CELL)
wait(200)
d = parse(js("(function(){var ob=document.getElementById('objbar');"
             "var btns=[].map.call(ob.querySelectorAll('button'),function(x){return x.textContent});"
             "return JSON.stringify({show:ob.classList.contains('show'),btns:btns})})()"))
log("1 objbar = %s" % json.dumps(d))
check("点击选中表格 → 悬浮工具条出现且含「标注」",
      d.get("show") is True and "标注" in (d.get("btns") or []), json.dumps(d))

# 右键菜单不再含「表格标注」
js("(function(){var td=document.querySelector('#editor .b-table td');"
   "var r=td.getBoundingClientRect();"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
   "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));return 'x'})()")
wait(300)
d = parse(js("(function(){var tb=document.getElementById('tblbar');"
             "var ts=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
             "return JSON.stringify({titles:ts})})()"))
log("1 ctx titles = %s" % json.dumps(d))
check("右键菜单已无「表格标注」项",
      not any("表格标注" in t for t in (d.get("titles") or [])), json.dumps(d.get("titles")))

# 点「标注」→ 弹层打开（标题=表格标注）→ 上方标注落盘
js(CLICK_CELL)
wait(300)
d = parse(js("(function(){var ob=document.getElementById('objbar');"
             "var b=[].filter.call(ob.querySelectorAll('button'),function(x){return x.textContent==='标注'})[0];"
             "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
             "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));"
             "var cp=document.getElementById('cappop');"
             "return JSON.stringify({show:cp.classList.contains('show'),"
             "title:(document.getElementById('cappop-title')||{}).textContent||''})})()"))
wait(200)
check("点「标注」→ 弹层打开且标题=表格标注",
      d.get("show") is True and d.get("title") == "表格标注", json.dumps(d))
js("(function(){document.getElementById('cap-input').value='表A';"
   "var rs=document.querySelectorAll('#cappop input[name=cappos]');rs[1].checked=true;"
   "document.getElementById('cap-ok').click();return 'x'})()")
wait(500)
r = raw()[0]
check("上方标注落盘（md-tblcap top）", '<caption class="md-tblcap top">表A</caption>' in r, r[:160])
# 下方切换仍可用
js(CLICK_CELL)
wait(300)
js("(function(){var ob=document.getElementById('objbar');"
   "var b=[].filter.call(ob.querySelectorAll('button'),function(x){return x.textContent==='标注'})[0];"
   "b.click();return 'x'})()")
wait(300)
js("(function(){document.getElementById('cap-input').value='表A';"
   "var rs=document.querySelectorAll('#cappop input[name=cappos]');rs[0].checked=true;"
   "document.getElementById('cap-ok').click();return 'x'})()")
wait(500)
r = raw()[0]
check("下方标注切换（md-tblcap bottom）", '<caption class="md-tblcap bottom">表A</caption>' in r, r[:160])

# ---------- 2. 「+」按钮矩形外框 ----------
d = parse(js("(function(){var el=document.getElementById('tbladd');"
             "return JSON.stringify({br:getComputedStyle(el).borderRadius,"
             "w:el.offsetWidth,h:el.offsetHeight})})()"))
log("2 tbladd = %s" % json.dumps(d))
check("「+」按钮外框为矩形（border-radius 3px）", d.get("br") == "3px", json.dumps(d))

# ---------- 3/4. 图片：右键菜单 + 状态栏 ----------
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAD0lEQVR4nGNgCLqJQMRxANiTErFDEzQeAAAAAElFTkSuQmCC"
DOC_IMG = "X\n\n![图](%s)" % PNG
js("window.setMarkdown(%s)" % json.dumps(DOC_IMG))
wait(800)

# 3a) 选中图片：蓝框出现、操作条不出现
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
             "return JSON.stringify({sel:JSON.parse(window.__objSel()),"
             "frame:document.getElementById('rzframe').classList.contains('show'),"
             "bar:document.getElementById('objbar').classList.contains('show')})})()"))
log("3a select = %s" % json.dumps(d))
check("选中图片：蓝框出现、悬浮按钮条不出现",
      d.get("sel", {}).get("kind") == "img" and d.get("frame") is True and d.get("bar") is False,
      json.dumps(d))

# 3b) 未保存文档 + 内嵌图：菜单无存储项
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "var r=img.getBoundingClientRect();"
             "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
             "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
             "var bm=document.getElementById('blkmenu');"
             "return JSON.stringify({acts:[].map.call(bm.querySelectorAll('.mi'),"
             "function(x){return x.getAttribute('data-act')})})})()"))
log("3b acts(unsaved+embed) = %s" % json.dumps(d))
check("未保存+内嵌图：菜单 = 图注/重置尺寸/显示/复制图片/上移/下移/删除（无存储项）",
      d.get("acts") == ["edit", "imgreset", "viewimg", "copyimg", "up", "down", "del"],
      json.dumps(d.get("acts")))

# 3c) 已保存文档 + 相对路径图：菜单含 转内嵌 + 改名
js("window.setDocDir('C:/tmpdir/md78')")
js("window.setMarkdown(%s)" % json.dumps("X\n\n![图](doc.assets/00001_a.png)"))
wait(800)
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "var r=img.getBoundingClientRect();"
             "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
             "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
             "var bm=document.getElementById('blkmenu');"
             "return JSON.stringify({acts:[].map.call(bm.querySelectorAll('.mi'),"
             "function(x){return x.getAttribute('data-act')}),"
             "labels:[].map.call(bm.querySelectorAll('.mi'),function(x){return x.textContent.trim()})})})()"))
log("3c acts(saved+rel) = %s" % json.dumps(d))
check("相对路径图：菜单含 转化为内嵌式存储 + 修改图片名称",
      d.get("acts") == ["edit", "imgreset", "imgmode", "imgrename", "viewimg", "copyimg", "up", "down", "del"]
      and any("转化为内嵌式存储" in t for t in (d.get("labels") or []))
      and any("修改图片名称" in t for t in (d.get("labels") or [])), json.dumps(d))

# 3d) 内嵌图 + 已保存文档：菜单含 转化为相对路径存储（且无改名）
js("window.setMarkdown(%s)" % json.dumps(DOC_IMG))
wait(800)
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "var r=img.getBoundingClientRect();"
             "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
             "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
             "var bm=document.getElementById('blkmenu');"
             "return JSON.stringify({acts:[].map.call(bm.querySelectorAll('.mi'),"
             "function(x){return x.getAttribute('data-act')}),"
             "labels:[].map.call(bm.querySelectorAll('.mi'),function(x){return x.textContent.trim()})})})()"))
log("3d acts(saved+embed) = %s" % json.dumps(d))
check("内嵌图（已保存）：菜单含 转化为相对路径存储、无 修改图片名称",
      "imgmode" in d.get("acts") and "imgrename" not in d.get("acts")
      and any("转化为相对路径存储" in t for t in (d.get("labels") or [])), json.dumps(d))
js("window.setDocDir('')")

# 4) 状态栏：选中图片 → getCaretLineCol 回报 imgsel + 存储方式 / 文件名
js("window.setDocDir('C:/tmpdir/md78')")
js("window.setMarkdown(%s)" % json.dumps("X\n\n![图](doc.assets/00001_a.png)"))
wait(800)
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
             "return JSON.stringify({st:JSON.parse(window.getCaretLineCol())})})()"))
log("4 status(rel) = %s" % json.dumps(d))
st = d.get("st") or {}
check("状态栏回报：相对路径存储 + 文件名",
      st.get("imgsel") == 1 and "相对路径存储" in str(st.get("type"))
      and "00001_a.png" in str(st.get("type")), json.dumps(st))
# 内嵌图 → 内嵌存储
js("window.setMarkdown(%s)" % json.dumps(DOC_IMG))
wait(800)
d = parse(js("(function(){var img=document.querySelector('#editor img');"
             "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
             "return JSON.stringify({st:JSON.parse(window.getCaretLineCol())})})()"))
st = d.get("st") or {}
check("状态栏回报：内嵌存储", st.get("imgsel") == 1 and "内嵌存储" in str(st.get("type")), json.dumps(st))
# 取消选中 → 回报空
js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(300)
d = parse(js("(function(){return JSON.stringify({st:JSON.parse(window.getCaretLineCol())})})()"))
st = d.get("st") or {}
check("取消选中图片 → 状态栏回报清空", st.get("imgsel") == 1 and st.get("type") == "", json.dumps(st))
js("window.setDocDir('')")

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
out.append("DONE")
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))
