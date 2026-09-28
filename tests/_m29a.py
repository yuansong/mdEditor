# -*- coding: utf-8 -*-
"""v3.29 探针：表格标注（<caption>，上方 / 下方）。v3.30.17：入口改为表格
悬浮工具条「标注」按钮（原右键菜单项迁移），上方 / 下方选择仍在弹层里。
1) 选中表格 → 悬浮条出现「标注」；2) 设置上方标注 → caption 落盘 / 渲染；
3) 切换到下方；4) 清空文字 → 标注移除；5) 编辑单元格 / 拖拽缩放后标注不丢。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29a.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


def click_btn(title_part):
    # v3.30.17：入口改为表格选中后的悬浮工具条（#objbar），按钮文本=「标注」
    return js("(function(){var b=document.querySelectorAll('#objbar button');"
              "for(var i=0;i<b.length;i++){if((b[i].textContent||'').indexOf('" + title_part + "')>=0){"
              "b[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
              "b[i].dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'}}"
              "return 'nobtn'})()")


def cap_ok(text, top):
    return js("(function(){var inp=document.getElementById('cap-input');"
              "inp.value=" + json.dumps(text) + ";"
              "var rs=document.querySelectorAll('#cappop input[name=cappos]');"
              "for(var i=0;i<rs.length;i++)rs[i].checked=(rs[i].value==='" + ("top" if top else "bottom") + "');"
              "document.getElementById('cap-ok').dispatchEvent(new MouseEvent('click',{bubbles:true}));"
              "return 'ok'})()")


wait(2500)

TBL = "| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)

# 1) 选中表格（__rzPick 触发 selectTblFrame → 悬浮条出现）→ 点开弹层
js("window.__rzPick(0)")
wait(300)
res = click_btn("标注")
wait(300)
r = js("(function(){var cp=document.getElementById('cappop');"
       "return JSON.stringify({show:cp.classList.contains('show'),"
       "title:document.getElementById('cappop-title').textContent})})()")
d = json.loads(r or "{}")
check("点「标注」→ 弹层打开且标题为表格标注",
      res == "ok" and d.get("show") is True and d.get("title") == "表格标注", str(d))

# 2) 上方标注 → caption 写入源码并渲染
cap_ok("表一：测试", True)
wait(500)
r = raw()[0]
check("上方标注 → caption class=md-tblcap top 写入源码",
      '<caption class="md-tblcap top">表一：测试</caption>' in r, r[:200])
capN = jj("(function(){return JSON.stringify({n:document.querySelectorAll('#editor .b-table caption').length,"
          "txt:(document.querySelector('#editor .b-table caption')||{}).textContent,"
          "side:getComputedStyle(document.querySelector('#editor .b-table caption')||document.body).captionSide})})()")
check("上方标注 → 渲染出 caption 且 caption-side=top",
      capN.get("n") == 1 and capN.get("txt") == "表一：测试" and capN.get("side") == "top", str(capN))

# 3) 切换到下方
js("window.__rzPick(0)")
wait(300)
click_btn("标注")
wait(300)
cap_ok("表一：测试", False)
wait(500)
r = raw()[0]
check("切换到下方 → caption class=md-tblcap bottom",
      '<caption class="md-tblcap bottom">表一：测试</caption>' in r, r[:200])

# 4) 清空文字 → 标注移除
js("window.__rzPick(0)")
wait(300)
click_btn("标注")
wait(300)
cap_ok("", False)
wait(500)
r = raw()[0]
check("清空文字 → caption 移除", "<caption" not in r and "<table" in r, r[:200])

# 5) 重新加上方标注 → 编辑单元格内容后标注不丢
js("window.__rzPick(0)")
wait(300)
click_btn("标注")
wait(300)
cap_ok("表二", True)
wait(500)
js("(function(){var td=document.querySelector('.b-table tbody td');"
   "td.focus();document.execCommand('insertText',false,'99');return 'x'})()")
wait(500)
r = raw()[0]
check("编辑单元格后标注不丢", "<caption" in r and "表二" in r, r[:200])

# 6) 整表缩放后标注不丢（拖 RZ 东手柄 +40px）
js("window.__rzPick(0)")
wait(200)
d6 = js("(function(){var rz=document.getElementById('rzframe');"
        "if(!rz)return 'no rz';var h=rz.querySelector('.rz.e');"
        "if(!h)return 'no handle';var r=h.getBoundingClientRect();"
        "function fire(el,t,x,y){el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y}));}"
        "fire(h,'mousedown',r.left,r.top);"
        "fire(document,'mousemove',r.left+40,r.top);"
        "fire(document,'mouseup',r.left+40,r.top);"
        "return 'dragged'})()")
wait(500)
r = raw()[0]
check("整表缩放后标注不丢", d6 == "dragged" and "<caption" in r and "表二" in r, r[:200])

# 7) 管道表加上标注 → 升级为 HTML 存储，Markdown 往返保留
md7 = jj("(function(){return JSON.stringify({md:window.getMarkdown()})})()")
check("getMarkdown 含 caption", "表二" in (md7.get("md") or ""), str(md7.get("md", ""))[:120])

out.append("DONE")
flush()
print("done")
