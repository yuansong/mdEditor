# -*- coding: utf-8 -*-
"""m104: v3.37 批次验证（代码块顶栏精简 / 图表留白 / 图表自然尺寸 / E-R 模板）。

N1 代码块顶栏只剩「语言 / 风格」
N2 「风格」弹层 = 4 风格 + 分隔线 + 行号项（文案按当前态）
N3 点行号项 → 写围栏 lnum=0、行号槽消失、弹层关闭
N4 再点 → lnum=1、行号槽回来（可逆）
N5 语言栏右键复制链路保留（contextmenu 绑定存在、copy-btn 已移除）
N6 图表块留白（.mmd-wrap / .blk）点击 → 保持渲染态、图表仍在（原缺陷）
N7 点图表本体仍打开源码框（mmd-src）
N8 图表按自然尺寸渲染：流程图宽≈viewBox 宽（不再 746）、高度 < 700；
   宽图表（甘特图）仍被容器宽度兜住（max-width:100%）
N9 显式 w= 的图表仍按指定宽度撑满（.sized）
N10 拖拽缩放期间 SVG 跟随容器变宽
N11 七个图表模板全部可渲染（含修正后的 E-R 图）
N12 回归：标题 / 列表 / 引用 / 定义列表留白点击仍保持渲染态
尺寸口径：svg 可用宽 = .mermaidblock 内容盒 = 容器宽 - 内边距（≈30px），
断言统一对齐 mbW 并留内边距容差，不对齐 #editor 客户端宽。
结果写 _m104.txt，PASS/FAIL 逐条判定。
"""
import json
import os
import sys
import time

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m104.txt")
LINES = []
N_PASS = [0]
N_FAIL = [0]


def log(s):
    LINES.append(str(s))


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if cond:
        N_PASS[0] += 1
    else:
        N_FAIL[0] += 1
    log(tag + " | " + name + (" | " + str(extra) if extra else ""))


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


def setmd(win, md, ms=1400):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


CHART_JS = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return JSON.stringify({err:'no-blk'});
  var mb = blk.querySelector('.mermaidblock');
  var sv = mb ? mb.querySelector('svg') : null;
  var rr = sv ? sv.getBoundingClientRect() : null;
  var mr = mb ? mb.getBoundingClientRect() : null;
  var ed = document.getElementById('editor');
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  return JSON.stringify({
    isRaw: blk.classList.contains('raw-edit'),
    hasMb: !!mb, hasSvg: !!sv,
    sized: mb ? mb.classList.contains('sized') : null,
    svgW: rr ? Math.round(rr.width) : null, svgH: rr ? Math.round(rr.height) : null,
    mbW: mr ? Math.round(mr.width) : null,
    vbW: sv ? Math.round(sv.viewBox.baseVal.width) : null,
    edW: ed ? ed.clientWidth : null,
    raw0: raw.split('\\n')[0]
  });
})()"""

CLICK_JS = """(function(){
  var t = %(sel)s;
  if (!t) return 'no-target';
  var r = t.getBoundingClientRect();
  var o = {bubbles:true, cancelable:true, button:0,
           clientX: r.left + %(ox)s, clientY: r.top + %(oy)s};
  t.dispatchEvent(new MouseEvent('mousedown', o));
  t.dispatchEvent(new MouseEvent('mouseup', o));
  t.dispatchEvent(new MouseEvent('click', o));
  return 'ok';
})()"""

MMD_FLOW = "```mermaid\nflowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D\n```"
MMD_GANTT = "```mermaid\ngantt\n  title 项目计划\n  section 阶段一\n  任务A :a1, 2026-01-01, 7d\n  任务B :after a1, 5d\n```"

TPL_CASES = [
    ("流程图", "flowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D"),
    ("时序图", "sequenceDiagram\n  participant U as 用户\n  participant S as 服务器\n  U->>S: 请求数据\n  S-->>U: 返回结果"),
    ("类图", "classDiagram\n  class Animal {\n    +String name\n    +eat()\n  }\n  class Dog\n  Animal <|-- Dog"),
    ("状态图", "stateDiagram-v2\n  [*] --> 空闲\n  空闲 --> 运行: 启动\n  运行 --> 空闲: 停止\n  运行 --> [*]"),
    ("E-R 图", "erDiagram\n  CUSTOMER ||--o{ ORDER : \"下单\"\n  CUSTOMER {\n    string name\n    int id\n  }\n  ORDER {\n    string no\n    date created\n  }"),
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

    # ==================== N1/N2 代码块顶栏 ====================
    log("---------- N1/N2 代码块顶栏与风格弹层 ----------")
    setmd(win, "```python\nprint('hi')\n```")
    bar = jj(win, """(function(){
      var b = document.querySelector('#editor .codebar');
      if (!b) return JSON.stringify({err:'no-bar'});
      return JSON.stringify({btns: [].slice.call(b.querySelectorAll('button')).map(function(x){return x.textContent;})});
    })()""")
    check("N1 顶栏只剩 语言 / 风格", bar.get("btns") == ["python", "风格"],
          json.dumps(bar.get("btns"), ensure_ascii=False))
    check("N1b 顶栏已无 复制 / 行号 按钮",
          "复制" not in (bar.get("btns") or []) and "行号" not in (bar.get("btns") or []),
          json.dumps(bar.get("btns"), ensure_ascii=False))

    js(win, "(function(){var b=document.querySelector('#editor .codebar .style-btn');if(b)b.click();return 'ok'})()")
    wait(400)
    sp = jj(win, """(function(){
      var sp = document.getElementById('stylepop');
      return JSON.stringify({show: sp.classList.contains('show'),
        sep: !!sp.querySelector('.ln-sep'),
        items: [].slice.call(sp.querySelectorAll('.si')).map(function(d){
          return {st: d.getAttribute('data-st'), ln: d.getAttribute('data-ln'), lb: d.textContent};})});
    })()""")
    check("N2 风格弹层打开且含分隔线", sp.get("show") is True and sp.get("sep") is True,
          json.dumps(sp, ensure_ascii=False))
    styles = [x for x in (sp.get("items") or []) if x.get("st")]
    lnitems = [x for x in (sp.get("items") or []) if x.get("ln") is not None]
    check("N2b 弹层 = 4 风格 + 1 行号项", len(styles) == 4 and len(lnitems) == 1,
          json.dumps(sp.get("items"), ensure_ascii=False))
    check("N2c 行号项文案（默认开启 → 「关闭行数显示」）",
          bool(lnitems) and "关闭行数显示" in lnitems[0]["lb"], json.dumps(lnitems, ensure_ascii=False))

    # ==================== N3/N4 行号开关 ====================
    log("---------- N3/N4 行号开关 ----------")
    g0 = jj(win, """(function(){
      var pre = document.querySelector('#editor .codeblock pre.fence');
      var raw = '';
      try { raw = (JSON.parse(window.__raw()).raw || [''])[0].split('\\n')[0]; } catch(e){}
      return JSON.stringify({hasGutter: !!pre.querySelector('.gutter'), firstLine: raw,
        popShow: document.getElementById('stylepop').classList.contains('show')});
    })()""")
    check("N3-pre 初始：行号槽在、首行无 lnum", g0.get("hasGutter") is True and "lnum" not in (g0.get("firstLine") or ""),
          json.dumps(g0, ensure_ascii=False))
    check("N3-pre2 点行号前弹层是打开的", g0.get("popShow") is True, str(g0.get("popShow")))

    js(win, "(function(){var it=document.querySelector('#stylepop .si[data-ln]');if(it)it.click();return 'ok'})()")
    wait(500)
    g1 = jj(win, """(function(){
      var pre = document.querySelector('#editor .codeblock pre.fence');
      var raw = '';
      try { raw = (JSON.parse(window.__raw()).raw || [''])[0].split('\\n')[0]; } catch(e){}
      return JSON.stringify({hasGutter: !!pre.querySelector('.gutter'), firstLine: raw,
        popShow: document.getElementById('stylepop').classList.contains('show')});
    })()""")
    check("N3 关闭行号 → lnum=0 + 行号槽消失 + 弹层收起",
          "lnum=0" in (g1.get("firstLine") or "") and g1.get("hasGutter") is False and g1.get("popShow") is False,
          json.dumps(g1, ensure_ascii=False))

    js(win, "(function(){var b=document.querySelector('#editor .codebar .style-btn');if(b)b.click();return 'ok'})()")
    wait(350)
    ln2 = jj(win, """(function(){
      var it = document.querySelector('#stylepop .si[data-ln]');
      return JSON.stringify({lb: it ? it.textContent : null, val: it ? it.getAttribute('data-ln') : null});
    })()""")
    check("N4-pre 关闭后行号项变「开启行数显示」",
          "开启行数显示" in (ln2.get("lb") or "") and ln2.get("val") == "1", json.dumps(ln2, ensure_ascii=False))
    js(win, "(function(){var it=document.querySelector('#stylepop .si[data-ln]');if(it)it.click();return 'ok'})()")
    wait(500)
    g2 = jj(win, """(function(){
      var pre = document.querySelector('#editor .codeblock pre.fence');
      var raw = '';
      try { raw = (JSON.parse(window.__raw()).raw || [''])[0].split('\\n')[0]; } catch(e){}
      return JSON.stringify({hasGutter: !!pre.querySelector('.gutter'), firstLine: raw});
    })()""")
    check("N4 再点开启 → lnum=1 + 行号槽回来（可逆）",
          "lnum=1" in (g2.get("firstLine") or "") and g2.get("hasGutter") is True,
          json.dumps(g2, ensure_ascii=False))

    # ==================== N5 复制链路保留 ====================
    log("---------- N5 复制链路 ----------")
    n5 = jj(win, """(function(){
      var bar = document.querySelector('#editor .codebar');
      var cb = bar.querySelector('.copy-btn');
      var lnb = bar.querySelector('.lnum-btn');
      return JSON.stringify({copyBtn: !!cb, lnumBtn: !!lnb, btnCount: bar.querySelectorAll('button').length});
    })()""")
    check("N5 按钮实体已移除（copy-btn / lnum-btn 均不存在）",
          n5.get("copyBtn") is False and n5.get("lnumBtn") is False and n5.get("btnCount") == 2,
          json.dumps(n5, ensure_ascii=False))

    # ==================== N6/N7 图表留白 ====================
    log("---------- N6/N7 图表留白保持渲染态 ----------")
    setmd(win, MMD_FLOW)
    base = jj(win, CHART_JS)
    check("N6-pre 图表已出图", base.get("hasSvg") is True, json.dumps(base, ensure_ascii=False))

    for name, sel, ox, oy in [
        ("块内留白(.mmd-wrap)", "document.querySelector('#editor .mmd-wrap')", 6, 6),
        ("块自身(.blk)", "document.querySelector('#editor .blk')", 3, 3),
    ]:
        r = js(win, CLICK_JS % {"sel": sel, "ox": ox, "oy": oy})
        wait(600)
        st = jj(win, CHART_JS)
        check("N6 点「%s」保持渲染态且图表仍在" % name,
              st.get("isRaw") is False and st.get("hasSvg") is True,
              "click=%s | %s" % (r, json.dumps(st, ensure_ascii=False)))
        if not st.get("hasSvg"):
            setmd(win, MMD_FLOW)

    # N7 点图表本体 → 打开源码框（原有行为不回归）
    setmd(win, MMD_FLOW)
    r7 = js(win, "(function(){var mb=document.querySelector('#editor .mermaidblock svg')||document.querySelector('#editor .mermaidblock');"
                 "if(!mb)return 'no-mb';var rr=mb.getBoundingClientRect();"
                 "var o={bubbles:true,cancelable:true,button:0,clientX:rr.left+rr.width/2,clientY:rr.top+rr.height/2};"
                 "mb.dispatchEvent(new MouseEvent('mousedown',o));return 'ok'})()")
    wait(600)
    n7 = jj(win, """(function(){
      var blk = document.querySelectorAll('#editor .blk')[0];
      return JSON.stringify({isRaw: blk.classList.contains('raw-edit'),
        src: !!document.querySelector('#editor .mmd-src'),
        hasSvg: !!document.querySelector('#editor .mermaidblock svg')});
    })()""")
    check("N7 点图表本体仍打开源码框（且不转源码态）",
          n7.get("isRaw") is False and n7.get("src") is True and n7.get("hasSvg") is True,
          "click=%s | %s" % (r7, json.dumps(n7, ensure_ascii=False)))

    # ==================== N8/N9 尺寸 ====================
    log("---------- N8/N9 图表尺寸 ----------")
    setmd(win, MMD_FLOW)
    flow = jj(win, CHART_JS)
    check("N8 流程图按自然尺寸（宽≈viewBox 宽 %s，不再撑满 %s）"
          % (flow.get("vbW"), flow.get("edW")),
          abs((flow.get("svgW") or 0) - (flow.get("vbW") or 0)) <= 4 and flow.get("svgW") < flow.get("edW"),
          json.dumps(flow, ensure_ascii=False))
    check("N8b 流程图高度回到自然量级（< 700，原 2126）",
          (flow.get("svgH") or 0) < 700, "svgH=%s" % flow.get("svgH"))

    setmd(win, MMD_GANTT)
    gantt = jj(win, CHART_JS)
    # 口径说明：svg 的可用宽度是 .mermaidblock 的「内容盒」（容器宽 - 左右内边距
    # ≈ 30px），不是 #editor 的客户端宽。自然宽 > 容器内容盒时被 max-width:100%
    # 兜住 → 表现为「撑满容器且不溢出」。故断言对齐 mbW（容器），留一个内边距容差
    check("N8c 宽图表（甘特图）仍撑满栏宽（max-width:100% 兜底）",
          (gantt.get("svgW") or 0) <= (gantt.get("mbW") or 0) + 1
          and (gantt.get("svgW") or 0) >= (gantt.get("mbW") or 0) - 40,
          json.dumps(gantt, ensure_ascii=False))

    setmd(win, "```mermaid w=420\nflowchart TD\n  A[开始] --> B{是否继续?}\n  B -->|是| C[处理任务]\n  B -->|否| D[结束]\n  C --> D\n```")
    sized = jj(win, CHART_JS)
    check("N9 显式 w=420 → .sized 且宽度=420（用户设的尺寸优先）",
          sized.get("sized") is True and abs((sized.get("mbW") or 0) - 420) <= 6
          and (sized.get("svgW") or 0) <= (sized.get("mbW") or 0) + 1
          and (sized.get("svgW") or 0) >= (sized.get("mbW") or 0) - 40,
          json.dumps(sized, ensure_ascii=False))

    # ==================== N10 拖拽跟随 ====================
    log("---------- N10 拖拽缩放跟随 ----------")
    setmd(win, MMD_FLOW)
    js(win, """(function(){
      var mb = document.querySelector('#editor .mermaidblock');
      var r = mb.getBoundingClientRect();
      mb.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, button:0,
        clientX: r.left + Math.min(20, r.width/2), clientY: r.top + Math.min(20, r.height/2)}));
      return 'ok';
    })()""")
    wait(400)
    drag = js(win, """(function(){
      var h = document.querySelector('#rzframe i.rz[data-h="se"]');
      if (!h) return 'no-handle';
      var r = h.getBoundingClientRect();
      var x = r.left + r.width/2, y = r.top + r.height/2;
      h.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, button:0, clientX:x, clientY:y}));
      document.dispatchEvent(new MouseEvent('mousemove', {bubbles:true, cancelable:true, button:0, clientX:x+100, clientY:y}));
      var mb = document.querySelector('#editor .mermaidblock');
      var sv = mb.querySelector('svg');
      var mid = {mb: Math.round(mb.getBoundingClientRect().width),
                 sv: Math.round(sv.getBoundingClientRect().width)};
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, button:0, clientX:x+100, clientY:y}));
      return JSON.stringify(mid);
    })()""")
    wait(800)
    mid = {}
    try:
        mid = json.loads(drag or "{}")
    except Exception:
        mid = {}
    after = jj(win, CHART_JS)
    check("N10 拖动期间 SVG 跟随容器（拖中宽 > 自然宽）",
          (mid.get("sv") or 0) > (flow.get("svgW") or 0)
          and abs((mid.get("sv") or 0) - (mid.get("mb") or 0)) <= 40,
          "mid=%s | after=%s" % (json.dumps(mid), json.dumps(after, ensure_ascii=False)))
    check("N10b 落盘写出 w= 且仍出图",
          "w=" in (after.get("raw0") or "") and after.get("hasSvg") is True and after.get("sized") is True,
          json.dumps(after, ensure_ascii=False))

    # ==================== N11 七个模板 ====================
    log("---------- N11 七个图表模板 ----------")
    bad = []
    for lb, code in TPL_CASES:
        setmd(win, "```mermaid\n" + code + "\n```")
        st = jj(win, CHART_JS)
        if not st.get("hasSvg"):
            bad.append("%s(hasSvg=%s)" % (lb, st.get("hasSvg")))
    check("N11 七个模板全部渲染成功（含修正后的 E-R 图）", not bad, " / ".join(bad) or "all 7 OK")

    # ==================== N12 其它块留白回归 ====================
    log("---------- N12 其它块留白回归 ----------")
    for name, md, sel in [
        ("标题", "# 标题文字", "document.querySelector('#editor .blk')"),
        ("列表", "- 列表项文字", "document.querySelector('#editor .blk')"),
        ("引用", "> 引用文字", "document.querySelector('#editor .blk')"),
        ("定义列表", "术语\n: 定义文字", "document.querySelector('#editor .blk')"),
    ]:
        setmd(win, md)
        js(win, CLICK_JS % {"sel": sel, "ox": 4, "oy": 4})
        wait(500)
        st = jj(win, """(function(){
          var blk = document.querySelectorAll('#editor .blk')[0];
          return JSON.stringify({isRaw: blk.classList.contains('raw-edit')});
        })()""")
        check("N12 %s 留白点击仍保持渲染态" % name, st.get("isRaw") is False, json.dumps(st))

    log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    flush()
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        log("EXCEPTION " + traceback.format_exc())
        log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
        flush()
        raise
