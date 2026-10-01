# -*- coding: utf-8 -*-
"""m35sp: 行首空格行为只读探针（写作模式 h1/p 敲空格 → DOM/raw/getMarkdown 三处形态）"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35sp_out.txt")
LINES = []

def log(s):
    LINES.append(str(s))

def js(win, code, timeout=8000):
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

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    # 页面就绪守卫
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    def charcodes(s):
        return " ".join("%04X" % ord(c) for c in s[:8])

    # ===== A. 标题行首敲空格 =====
    js(win, "window.setMarkdown('# 标题甲\\n\\n正文乙')")
    wait(600)
    # 聚焦 h1 块并置光标于文本起点，模拟键入空格
    r = js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var h = blk.querySelector('h1,h2,h3,h4,h5,h6');
  if (!h) return 'NO_H';
  h.focus();
  var sel = window.getSelection();
  var rng = document.createRange();
  rng.setStart(h.firstChild, 0);
  rng.collapse(true);
  sel.removeAllRanges();
  sel.addRange(rng);
  document.execCommand('insertText', false, ' ');
  var txt = h.textContent;
  return JSON.stringify({after: txt.slice(0, 6),
                         codes: Array.prototype.map.call(txt.slice(0,4), function(c){return c.charCodeAt(0).toString(16);}).join(',')});
})()""")
    log("A1 h1 行首敲空格后 textContent: %r" % (r,))
    wait(400)
    raw0 = js(win, "JSON.stringify(window.__raw ? window.__raw() : state.raw[0])")
    log("A2 __raw[0]: %r" % (raw0,))
    md = js(win, "window.getMarkdown()")
    log("A3 getMarkdown 前 12 字符 codes: %s" % (charcodes(md or "") if md else md,))
    # 触发一次 rebuild（模拟任意重建路径），看行首空格是否存活
    js(win, "window.setTheme(window.state ? (document.body.className||'light') : 'light')")
    wait(500)
    md2 = js(win, "window.getMarkdown()")
    log("A4 rebuild 后 getMarkdown codes: %s" % (charcodes(md2 or "") if md2 else md2,))

    # ===== B. 正文段落行首敲空格 =====
    js(win, "window.setMarkdown('# 甲\\n\\n段落一')")
    wait(600)
    r = js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[1];
  var p = blk.querySelector('p') || blk;
  p.focus && p.focus();
  // 正文块编辑层可能是 .b-p 之类，找 contenteditable 或直接取第一个文本节点
  var target = blk.querySelector('[contenteditable="true"]') || p;
  var sel = window.getSelection();
  var rng = document.createRange();
  if (!target.firstChild) return 'NO_TEXT';
  rng.setStart(target.firstChild, 0);
  rng.collapse(true);
  sel.removeAllRanges();
  sel.addRange(rng);
  document.execCommand('insertText', false, ' ');
  var txt = blk.textContent;
  return JSON.stringify({after: txt.slice(0, 8),
                         codes: Array.prototype.map.call(txt.slice(0,6), function(c){return c.charCodeAt(0).toString(16);}).join(',')});
})()""")
    log("B1 段落行首敲空格后 textContent: %r" % (r,))
    wait(400)
    md3 = js(win, "window.getMarkdown()")
    log("B2 getMarkdown 第二块 codes: %s" % (charcodes((md3 or "").split("\n\n")[1] if md3 and "\n\n" in md3 else (md3 or "")),))

    # ===== C. 源码模式空格形态 =====
    js(win, "window.setMarkdown('# 甲\\n\\n 行首带空格段')")
    wait(600)
    js(win, "window.setSourceMode(true)")
    wait(800)
    r = js(win, """(function(){
  var src = document.querySelector('.raw-edit');
  if (!src) return 'NO_SRC';
  var line2 = (src.textContent || '').split('\\n')[2] || '';
  return JSON.stringify({line2: line2.slice(0, 8),
                         codes: Array.prototype.map.call(line2.slice(0,4), function(c){return c.charCodeAt(0).toString(16);}).join(',')});
})()""")
    log("C1 源码模式第 3 行形态: %r" % (r,))
    js(win, "window.setSourceMode(false)")
    wait(500)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
