# -*- coding: utf-8 -*-
"""m54 探针：定位 smoke23 noRawSrc 失败 —— body 里哪段文本含 'data:image'。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m54.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s)); flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; log(f"[PASS] {name} {detail}")
    else: FAIL += 1; log(f"[FAIL] {name} {detail}")


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

IMG = "data:image/png;base64,iVBORw0KGgo="
js("window.setMarkdown('')")
wait(500)
js(f"window.insertImageMarkdown('{IMG}', '测试图')")
wait(600)

# 找出包含 'data:image' 文本的最内层元素
r = js("""(function(){
function walk(el, path){
  var hits=[];
  for(var i=0;i<el.childNodes.length;i++){
    var n=el.childNodes[i];
    if(n.nodeType===3 && n.textContent.indexOf('data:image')>=0)
      hits.push({path:path, tag:el.tagName, cls:el.className&&el.className.toString?el.className.toString():'',
                 parent:(el.parentElement?el.parentElement.tagName+'.'+(el.parentElement.className||''):''),
                 txt:n.textContent.slice(0,80)});
    else if(n.nodeType===1) hits=hits.concat(walk(n, path+'>'+n.tagName));
  }
  return hits;
}
return JSON.stringify({hits: walk(document.body,'body'),
  cnt: document.body.textContent.split('data:image').length-1});
})()""")
log("hits=" + str(r))

# 顺带确认 img 是否触发 error 占位
r2 = js("""(function(){
var tip=document.querySelector('.img-broken-tip');
var broken=document.querySelector('img.img-broken');
return JSON.stringify({tip:!!tip, tipTxt:tip?tip.textContent.slice(0,60):'',
                       broken:!!broken});
})()""")
log("imgstate=" + str(r2))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
log("DONE")
flush()
