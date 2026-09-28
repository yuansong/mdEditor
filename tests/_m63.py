# -*- coding: utf-8 -*-
"""m63 诊断探针：跨 thead/tbody 的 rowspan 渲染行为定位。
T1: 原生表格（无编辑器 CSS）+ thead rowspan=2 → tbody 行1 各 td 的 x
T2: 同结构 + table-layout:fixed;width:600px
T3: 同结构但无 thead（首行 th 放 tbody）
T4: 编辑器管线渲染的用户 HTML → innerHTML dump + 几何
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m63.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s)); flush()


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


wait(3000)

# 动态创建实验表格并测量
EXP = ("(function(tag, styleAttr){"
       "try{"
       "var host=document.createElement('div');"
       "host.style.cssText='position:fixed;left:-9999px;top:0;';"
       "var h='<table '+(styleAttr||'')+'>'"
       "+'<thead><tr><th>a</th><th rowspan=\"2\">M</th><th>b</th><th>c</th></tr></thead>'"
       "+'<tbody><tr><td>1</td><td>2</td><td>3</td></tr>'"
       "+'<tr><td>4</td><td>5</td><td>6</td><td>7</td></tr></tbody></table>';"
       "if(tag==='nothead'){"
       "h='<table '+(styleAttr||'')+'><tbody>'"
       "+'<tr><th>a</th><th rowspan=\"2\">M</th><th>b</th><th>c</th></tr>'"
       "+'<tr><td>1</td><td>2</td><td>3</td></tr>'"
       "+'<tr><td>4</td><td>5</td><td>6</td><td>7</td></tr></tbody></table>';}"
       "host.innerHTML=h;document.body.appendChild(host);"
       "var t=host.querySelector('table');"
       "var trs=t.querySelectorAll('tr');"
       "var r1=trs[1];"
       "var info={rowspanH:Math.round(t.querySelector('[rowspan]').getBoundingClientRect().height),"
       "r1cells:[]};"
       "for(var q=0;q<r1.cells.length;q++){var rc=r1.cells[q].getBoundingClientRect();"
       "info.r1cells.push({x:Math.round(rc.left),w:Math.round(rc.width),txt:r1.cells[q].textContent});}"
       "var cols=t.querySelectorAll('tr:first-child th');"
       "info.colX=[];"
       "for(var q2=0;q2<cols.length;q2++)info.colX.push(Math.round(cols[q2].getBoundingClientRect().left));"
       "document.body.removeChild(host);"
       "return JSON.stringify(info);"
       "}catch(e){return 'ERR:'+e.message}})")

for name, tag, style in [
    ("T1 原生auto布局", "thead", ""),
    ("T2 原生fixed布局", "thead", 'style="table-layout:fixed;width:600px"'),
    ("T3 无thead fixed", "nothead", 'style="table-layout:fixed;width:600px"'),
    ("T4 无thead auto", "nothead", ""),
]:
    r = js(EXP + f"('{tag}','{style}')")
    log(f"{name}: {r}")

# 编辑器管线渲染用户 HTML → dump DOM 结构 + 几何
USER_HTML = ('<table class="md-tbl">\n<thead>\n<tr><th></th><th rowspan="2"></th>'
             '<th></th><th></th></tr>\n</thead>\n<tbody>\n'
             '<tr><td></td><td></td><td></td></tr>\n'
             '<tr><td></td><td></td><td></td><td></td></tr>\n</tbody>\n</table>')
js(f"window.setMarkdown({json.dumps(USER_HTML)})")
wait(700)
DUMP = ("(function(){"
        "var t=document.querySelector('.b-table table');if(!t)return 'notable';"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var rows=[];"
        "for(var q=0;q<trs.length;q++){var cs=[];"
        "for(var q2=0;q2<trs[q].cells.length;q2++){var c=trs[q].cells[q2];"
        "cs.push(c.tagName+(c.getAttribute('rowspan')?'[rs='+c.getAttribute('rowspan')+']':'')"
        "+(c.className?'.'+c.className:''));}"
        "rows.push(cs);}"
        "var rsEl=t.querySelector('[rowspan]');"
        "var rc=rsEl?rsEl.getBoundingClientRect():null;"
        "var r1=trs[1];var r1x=[];"
        "if(r1)for(var q3=0;q3<r1.cells.length;q3++)"
        "r1x.push(Math.round(r1.cells[q3].getBoundingClientRect().left));"
        "return JSON.stringify({rows:rows,"
        "rsH:rc?Math.round(rc.height):-1,r1x:r1x,"
        "computedTL:getComputedStyle(t).tableLayout,"
        "computedW:getComputedStyle(t).width});})()")
r = js(DUMP)
log(f"T5 编辑器渲染用户HTML: {r}")

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
flush()
os._exit(0)
