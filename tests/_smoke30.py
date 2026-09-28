# -*- coding: utf-8 -*-
"""v3.26 冒烟测试：mermaid 图表浏览器端渲染验证（renderMermaidEl 失败重试）。

1) 合法图表 → 渲染为 <svg>，无 .mmd-err
2) 非法图表 → 重试一次后显示 .mmd-err（不再无限重试）
3) 快速连续重建（模拟自动测试中的瞬时竞争）→ 最终块正常渲染无 .mmd-err
输出：tests/_smoke30.txt
"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke30.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


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


MMD_OK = "```mermaid\nflowchart TD\n  A[开始] --> B{判断}\n  B -->|是| C[结束]\n```"
MMD_BAD = "```mermaid\nflowchart TD\n  A--\n```"

wait(2500)

# ---------- 1) 合法图表渲染 ----------
js(f"window.setMarkdown({json.dumps(MMD_OK)})")
wait(1500)
r = js("(function(){var m=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({svg:!!(m&&m.querySelector('svg')),"
       "err:!!document.querySelector('#editor .mmd-err')});})()")
d = json.loads(r or "{}")
check("合法图表渲染为 svg", bool(d.get("svg")), r)
check("合法图表无 .mmd-err", not d.get("err"), r)

# ---------- 2) 非法图表：重试一次后报错 ----------
js(f"window.setMarkdown({json.dumps(MMD_BAD)})")
wait(1200)
r = js("(function(){var e=document.querySelector('#editor .mmd-err');"
       "return JSON.stringify({err:!!e,txt:e?e.textContent.slice(0,60):''});})()")
d = json.loads(r or "{}")
check("非法图表显示 .mmd-err（重试后仍失败才报错）", bool(d.get("err")), r)

# ---------- 3) 快速连续重建后最终块正常 ----------
for i in range(8):
    js(f"window.setMarkdown({json.dumps(MMD_OK)})")
    wait(60)
wait(1500)
r = js("(function(){var m=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({n:document.querySelectorAll('#editor .mermaidblock').length,"
       "svg:!!(m&&m.querySelector('svg')),err:!!document.querySelector('#editor .mmd-err')});})()")
d = json.loads(r or "{}")
check("快速连续重建 8 次 → 最终块渲染 svg", bool(d.get("svg")), r)
check("快速连续重建后无 .mmd-err", not d.get("err"), r)

results.append("DONE")
flush()
print("SMOKE30 DONE")
