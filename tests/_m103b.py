# -*- coding: utf-8 -*-
"""m103b: 诊断 E-R 图模板渲染失败原因 + 取各图表 SVG 的自然尺寸（viewBox）。"""
import json
import os
import sys
import time

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m103b.txt")
LINES = []


def log(s):
    LINES.append(str(s))


def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))


def js(win, code, timeout=9000):
    res = {"v": None, "done": False}

    def cb(r):
        res["v"] = r
        res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents()
        time.sleep(0.02)
    return res["v"]


def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents()
        time.sleep(0.02)


def setmd(win, md, ms=1600):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


INFO_JS = """(function(){
  var mb = document.querySelector('#editor .mermaidblock');
  if (!mb) return JSON.stringify({err:'no-mb'});
  var sv = mb.querySelector('svg');
  var err = mb.querySelector('.mmd-err');
  return JSON.stringify({
    hasSvg: !!sv,
    err: err ? err.textContent.slice(0, 300) : null,
    vb: sv ? (sv.getAttribute('viewBox') || '') : null,
    attrW: sv ? sv.getAttribute('width') : null,
    attrH: sv ? sv.getAttribute('height') : null,
    styleW: sv ? sv.style.width : null,
    styleMaxW: sv ? sv.style.maxWidth : null,
    rect: sv ? [Math.round(sv.getBoundingClientRect().width), Math.round(sv.getBoundingClientRect().height)] : null
  });
})()"""

CASES = [
    ("流程图", "flowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D"),
    ("时序图", "sequenceDiagram\n  participant U as 用户\n  participant S as 服务器\n  U->>S: 请求数据\n  S-->>U: 返回结果"),
    ("类图", "classDiagram\n  class Animal {\n    +String name\n    +eat()\n  }\n  class Dog\n  Animal <|-- Dog"),
    ("状态图", "stateDiagram-v2\n  [*] --> 空闲\n  空闲 --> 运行: 启动\n  运行 --> 空闲: 停止\n  运行 --> [*]"),
    ("E-R 图(原模板)", "erDiagram\n  用户 ||--o{ 订单 : 下单\n  用户 {\n    string name\n    int id\n  }"),
    ("E-R 图(纯关系)", "erDiagram\n  USER ||--o{ ORDER : places"),
    ("甘特图", "gantt\n  title 项目计划\n  section 阶段一\n  任务A :a1, 2026-01-01, 7d\n  任务B :after a1, 5d"),
    ("饼图", "pie title 内容占比\n  \"写作\" : 40\n  \"阅读\" : 35\n  \"整理\" : 25"),
]


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    for lb, code in CASES:
        setmd(win, "```mermaid\n" + code + "\n```")
        try:
            st = json.loads(js(win, INFO_JS) or "{}")
        except Exception:
            st = {}
        log("%-16s %s" % (lb, json.dumps(st, ensure_ascii=False)))

    log("mermaid version | " + str(js(win, "(window.mermaid && window.mermaid.version) || 'n/a'")))
    flush()
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        log("EXCEPTION " + traceback.format_exc())
        flush()
        raise
