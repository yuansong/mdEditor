# -*- coding: utf-8 -*-
"""诊断2：抓取 editor.html 主脚本文本，try/catch 重执行拿崩溃堆栈。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34e.txt")
out = []


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
    QTimer.singleShot(30000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


wait(3000)
code = """
(function(){
  var scripts = document.querySelectorAll('script');
  var s = scripts[scripts.length-1];
  if (!s || !s.textContent) return JSON.stringify({err:'no-script'});
  var text = s.textContent;
  try {
    (new Function(text))();
    return JSON.stringify({ok:true, len:text.length});
  } catch(e) {
    return JSON.stringify({msg: e.message, stack: (e.stack||'').split('\\n').slice(0,6)});
  }
})()
"""
r = js(code)
out.append("RESULT: " + str(r))
out.append("DONE")
flush()
print("done")
