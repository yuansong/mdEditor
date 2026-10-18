# -*- coding: utf-8 -*-
"""m110：表格三浮层职责重构验收（TBL-F1/F2/F3）
依据 docs/表格交互三浮层功能划分分析-v3.37.md §六回归验收口径：
1. 点击单元格不再出现「标注」浮条；表格选中态不受影响；
2. 单元格内选中文字 → 格式栏无「＋」（行内按钮齐全）；
3. 空单元格显示占位提示（data-ph）；
4. 命令面板通道 __blkCmd（表格标注 / 还原尺寸 / 复制块）可用；
5. 特殊块选中时手柄脉冲（pulse）；
6. buildObjbar('tbl') 防御性 no-op。
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m110.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:400]))

def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]

def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)

def setmd(win, md):
    js(win, "window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(450)

def md0(win):
    return js(win, "window.getMarkdown()") or ""

TBL = "| 甲 | 乙 |\n| --- | --- |\n|  |  |\n| 已有文字 |  |"

MOUSEDOWN_TD = r"""(function(){
  var tbl = document.querySelectorAll('#editor table')[0];
  if (!tbl) return 'NOTBL';
  var td = tbl.rows[1].cells[0];
  var r = td.getBoundingClientRect();
  var ev = new MouseEvent('mousedown', {bubbles: true, cancelable: true,
    clientX: r.left + 8, clientY: r.top + 8, button: 0});
  td.dispatchEvent(ev);
  return 'ok';
})()"""

FB_BTN = r"""(function(){
  var fb = document.getElementById('floatbar');
  if (!fb) return 'NOFB';
  var names = [];
  var bs = fb.querySelectorAll('button');
  for (var i = 0; i < bs.length; i++) names.push(bs[i].textContent.trim());
  return JSON.stringify({show: fb.classList.contains('show'), btns: names});
})()"""

CELL_PH = r"""(function(){
  var tbl = document.querySelectorAll('#editor table')[0];
  if (!tbl) return '{}';
  return JSON.stringify({
    phEmpty: tbl.rows[1].cells[0].getAttribute('data-ph'),
    phFull: tbl.rows[2].cells[0].getAttribute('data-ph'),
    ceEmpty: tbl.rows[1].cells[0].getAttribute('contenteditable')
  });
})()"""

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ---------- A：点击单元格 → 无 objbar，手柄脉冲 ----------
    setmd(win, TBL)
    r = js(win, MOUSEDOWN_TD)
    wait(400)
    st = js(win, """(function(){
      var ob = document.getElementById('objbar');
      var bh = document.getElementById('blkhandle');
      var tbl = document.querySelectorAll('#editor table')[0];
      return JSON.stringify({obShow: ob ? ob.classList.contains('show') : null,
        obHtml: ob ? ob.innerHTML : null,
        bhShow: bh ? bh.style.display : null,
        bhPulse: bh ? bh.classList.contains('pulse') : null,
        bhTitle: bh ? bh.title : null,
        tblSel: tbl ? tbl.classList.contains('sel') : null});
    })()""")
    d = json.loads(st or "{}")
    log("[A] ret=%s %s" % (r, st))
    check("A1 点击单元格不再弹出「标注」浮条（TBL-F1）",
          r == "ok" and d.get("obShow") is False and not (d.get("obHtml") or ""), st)
    # selectTblFrame 路径的选中态：__rzPick 内部调 selectTblFrame（v3.30.16 钩子）
    rz = js(win, "window.__rzPick(0)")
    wait(300)
    selCls = js(win, """(function(){
      var tbl = document.querySelectorAll('#editor table')[0];
      var ob = document.getElementById('objbar');
      return JSON.stringify({sel: tbl.classList.contains('sel'),
        obShow: ob.classList.contains('show')});
    })()""")
    dRz = json.loads(selCls or "{}")
    log("[A] __rzPick=%s %s" % (rz, selCls))
    check("A2 表格选中态保留（.sel 边框）", rz == "ok" and dRz.get("sel") is True, str(dRz))
    check("A2b selectTblFrame 路径同样不弹 objbar", dRz.get("obShow") is False, str(dRz))
    check("A3 手柄脉冲提示出现（TBL-F3）",
          d.get("bhShow") == "flex" and d.get("bhPulse") is True
          and "块菜单" in (d.get("bhTitle") or ""), st)
    wait(1900)
    st2 = js(win, "document.getElementById('blkhandle').classList.contains('pulse')")
    check("A4 脉冲 1.6s 后自动退场", st2 is False, str(st2))

    # ---------- B：objbar 全程保持空（表格任何交互路径都不再生成按钮） ----------
    st3 = js(win, """(function(){
      var ob = document.getElementById('objbar');
      return JSON.stringify({html: ob.innerHTML, show: ob.classList.contains('show')});
    })()""")
    d3 = json.loads(st3 or "{}")
    check("B1 objbar 表格分支零按钮输出", d3.get("html") == "" and d3.get("show") is False, st3)

    # ---------- C：单元格内选区 → 格式栏无「＋」 ----------
    js(win, """(function(){
      var tbl = document.querySelectorAll('#editor table')[0];
      var td = tbl.rows[2].cells[0];
      td.focus();
      var rg = document.createRange(); rg.selectNodeContents(td);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
      document.dispatchEvent(new Event('selectionchange'));
      return 'ok';
    })()""")
    wait(600)
    fb = json.loads(js(win, FB_BTN) or "{}")
    log("[C] floatbar=%s" % json.dumps(fb, ensure_ascii=False))
    btns = fb.get("btns") or []
    check("C1 单元格内格式栏无「＋」且行内按钮齐全（TBL-F2）",
          all(b != "＋" for b in btns) and fb.get("show") is True and len(btns) == 8,
          json.dumps(fb, ensure_ascii=False))

    # ---------- D：空单元格占位提示 ----------
    setmd(win, TBL)
    wait(300)
    d4 = json.loads(js(win, CELL_PH) or "{}")
    log("[D] %s" % json.dumps(d4, ensure_ascii=False))
    # v3.38（TBL-F3）：占位提示按用户需求移除 —— 任何单元格都不再有 data-ph
    check("D1 空格无 data-ph（TBL-F3 已移除占位提示）",
          d4.get("phEmpty") is None, json.dumps(d4, ensure_ascii=False))
    check("D2 非空格无 data-ph", d4.get("phFull") is None, json.dumps(d4, ensure_ascii=False))

    # ---------- E：命令面板通道 __blkCmd ----------
    js(win, "window.__rzPick(0)"); wait(300)
    e1 = js(win, "window.__blkCmd('cap')")
    wait(300)
    cappop = js(win, "document.getElementById('cappop').classList.contains('show')")
    js(win, "window.__blkCmd('__x__')"); wait(150)   # 触发一次 UNKNOWN（不收浮层）
    e2 = js(win, "window.__blkCmd('dup')")
    wait(400)
    rawDup = md0(win)
    e3 = js(win, "window.__blkCmd('resetsize')")
    e4 = js(win, "window.__blkCmd('whatever')")
    log("[E] cap=%s cappop=%s dup=%s resetsize=%s unknown=%s" % (e1, cappop, e2, e3, e4))
    check("E1 表格标注入口可用", e1 == "OK" and cappop is True, "%s/%s" % (e1, cappop))
    check("E2 复制块可用（raw 出现重复表）",
          e2 == "OK" and rawDup.count("| 甲 |") == 2, e2 + " | " + rawDup[:160])
    check("E3 还原尺寸入口可用", e3 == "OK", str(e3))
    check("E4 未知命令安全返回", e4 == "UNKNOWN", str(e4))

    with io_open(OUT) as f:
        f.write("\n".join(LINES) + "\n")
    print("DONE m110")

def io_open(p):
    import io
    return io.open(p, "w", encoding="utf-8")

if __name__ == "__main__":
    main()
