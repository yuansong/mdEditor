# -*- coding: utf-8 -*-
"""m103: 图表（mermaid）缩放后「点图表区域外 → 图表不显示」复现 + 默认尺寸测量。

R1 基线：插入流程图 → 出图（svg 存在）
R2 缩放：选中 → 拖 #rzframe se 手柄 +120px 宽 → 松手落盘（围栏 info 写 w=）
R3 缩放后仍出图
R4 依次点击「块内空白 / 块外空白 / 另一个段落块」→ 每一次都报告
   （块是否转源码态 raw-edit / svg 是否还在）—— 用于判定「无法显示」的确切形态
S1 七个图表模板插入后的自然尺寸（宽 × 高），用于「默认尺寸过大」的定量依据
结果写 _m103.txt。
"""
import json
import os
import sys
import time

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m103.txt")
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


def jj(win, code):
    try:
        return json.loads(js(win, code) or "{}")
    except Exception:
        return {}


def setmd(win, md, ms=1500):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


CHART_JS = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return JSON.stringify({err:'no-blk'});
  var mb = blk.querySelector('.mermaidblock');
  var sv = mb ? mb.querySelector('svg') : null;
  var r = mb ? mb.getBoundingClientRect() : null;
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  return JSON.stringify({
    isRaw: blk.classList.contains('raw-edit'),
    cls: blk.className,
    mbCls: mb ? mb.className : null,
    hasMb: !!mb,
    hasSvg: !!sv,
    mbW: r ? Math.round(r.width) : null,
    mbH: r ? Math.round(r.height) : null,
    svgW: sv ? Math.round(sv.getBoundingClientRect().width) : null,
    svgH: sv ? Math.round(sv.getBoundingClientRect().height) : null,
    raw: raw.split('\\n')[0]
  });
})()"""

# 选中图表（模拟单击）→ objbar + rzframe 出现
SELECT_JS = """(function(){
  var mb = document.querySelector('#editor .mermaidblock');
  if (!mb) return 'no-mb';
  var r = mb.getBoundingClientRect();
  var x = r.left + Math.min(20, r.width/2), y = r.top + Math.min(20, r.height/2);
  var o = {bubbles:true, cancelable:true, button:0, clientX:x, clientY:y};
  mb.dispatchEvent(new MouseEvent('mousedown', o));
  mb.dispatchEvent(new MouseEvent('mouseup', o));
  mb.dispatchEvent(new MouseEvent('click', o));
  return 'ok';
})()"""

RZ_INFO_JS = """(function(){
  var f = document.getElementById('rzframe');
  var h = f ? f.querySelector('i.rz[data-h="se"]') : null;
  return JSON.stringify({show: f ? f.classList.contains('show') : null,
                         hasHandle: !!h,
                         hx: h ? Math.round(h.getBoundingClientRect().left) : null});
})()"""

DRAG_JS = """(function(){
  var h = document.querySelector('#rzframe i.rz[data-h="se"]');
  if (!h) return 'no-handle';
  var r = h.getBoundingClientRect();
  var x = r.left + r.width/2, y = r.top + r.height/2;
  h.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, button:0, clientX:x, clientY:y}));
  document.dispatchEvent(new MouseEvent('mousemove', {bubbles:true, cancelable:true, button:0,
    clientX:x+%(dx)d, clientY:y+%(dy)d}));
  document.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, button:0,
    clientX:x+%(dx)d, clientY:y+%(dy)d}));
  return 'ok';
})()"""

# 在某个选择器命中的元素上派发完整的鼠标事件序列（模拟真实单击）
CLICK_JS = """(function(){
  var t = %(sel)s;
  if (!t) return 'no-target';
  var r = t.getBoundingClientRect();
  var x = r.left + %(ox)s, y = r.top + %(oy)s;
  var o = {bubbles:true, cancelable:true, button:0, clientX:x, clientY:y};
  t.dispatchEvent(new MouseEvent('mousedown', o));
  t.dispatchEvent(new MouseEvent('mouseup', o));
  t.dispatchEvent(new MouseEvent('click', o));
  return 'ok';
})()"""

MMD = "```mermaid\nflowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D\n```"


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    log("========== R 图表缩放后「点区域外不显示」复现 ==========")

    # ---------- R1 基线 ----------
    setmd(win, MMD)
    st = jj(win, CHART_JS)
    log("R1 基线 | " + json.dumps(st, ensure_ascii=False))
    if not st.get("hasSvg"):
        log("R1 未出图，后续步骤无意义 —— 结束")
        flush()
        print("DONE")
        return

    # ---------- R2 选中 + 拖 se 手柄放大 120px ----------
    log("SELECT | " + str(js(win, SELECT_JS)))
    wait(400)
    log("RZ-INFO | " + json.dumps(jj(win, RZ_INFO_JS), ensure_ascii=False))
    log("DRAG | " + str(js(win, DRAG_JS % {"dx": 120, "dy": 0})))
    wait(900)
    st = jj(win, CHART_JS)
    log("R2 缩放落盘后 | " + json.dumps(st, ensure_ascii=False))

    # ---------- R3/R4 三种「区域外」点击 ----------
    targets = [
        ("块内空白(.mmd-wrap)", "document.querySelector('#editor .mmd-wrap')", 6, 6),
        ("块自身(.blk)", "document.querySelector('#editor .blk')", 3, 3),
        ("编辑区空白(#editor)", "document.getElementById('editor')", 40, 400),
    ]
    for name, sel, ox, oy in targets:
        code = CLICK_JS % {"sel": sel, "ox": ox, "oy": oy}
        r = js(win, code)
        wait(700)
        st = jj(win, CHART_JS)
        log("R4 点击「%s」(%s) → isRaw=%s hasMb=%s hasSvg=%s mbCls=%s svgW=%s raw0=%s"
            % (name, r, st.get("isRaw"), st.get("hasMb"), st.get("hasSvg"),
               st.get("mbCls"), st.get("svgW"), repr(st.get("raw"))))
        # 复原：重新出图，保证下一步是干净基线
        if not st.get("hasSvg"):
            setmd(win, MMD)
            js(win, SELECT_JS)
            wait(300)
            js(win, DRAG_JS % {"dx": 120, "dy": 0})
            wait(700)

    # ---------- S1 七个模板的自然尺寸 ----------
    log("========== S1 七个图表模板自然尺寸 ==========")
    tpls = jj(win, """(function(){
      var out = [];
      try {
        var defs = window.__slashTpls ? window.__slashTpls() : null;
        if (defs) return JSON.stringify(defs);
      } catch(e) {}
      return JSON.stringify(out);
    })()""")
    log("slashTpls probe | " + json.dumps(tpls, ensure_ascii=False)[:200])

    log("========== S2 逐个插入测量 ==========")
    for lb, code in [
        ("流程图", "flowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D"),
        ("时序图", "sequenceDiagram\n  participant U as 用户\n  participant S as 服务器\n  U->>S: 请求数据\n  S-->>U: 返回结果"),
        ("类图", "classDiagram\n  class Animal {\n    +String name\n    +eat()\n  }\n  class Dog\n  Animal <|-- Dog"),
        ("状态图", "stateDiagram-v2\n  [*] --> 空闲\n  空闲 --> 运行: 启动\n  运行 --> 空闲: 停止\n  运行 --> [*]"),
        ("E-R 图", "erDiagram\n  用户 ||--o{ 订单 : 下单\n  用户 {\n    string name\n    int id\n  }"),
        ("甘特图", "gantt\n  title 项目计划\n  section 阶段一\n  任务A :a1, 2026-01-01, 7d\n  任务B :after a1, 5d"),
        ("饼图", "pie title 内容占比\n  \"写作\" : 40\n  \"阅读\" : 35\n  \"整理\" : 25"),
    ]:
        setmd(win, "```mermaid\n" + code + "\n```")
        st = jj(win, CHART_JS)
        log("S2 %-5s 容器 %sx%s  svg %sx%s  hasSvg=%s"
            % (lb, st.get("mbW"), st.get("mbH"), st.get("svgW"), st.get("svgH"), st.get("hasSvg")))

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
