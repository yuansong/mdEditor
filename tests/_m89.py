# -*- coding: utf-8 -*-
"""m89：v3.31.3 批次探针（21 项问题核心断言）

覆盖：
  G1 #1/#2 A→B→A toggle（B→S→B / S→MK→S / B→I→B 回归）× 4 容器
  G2 #3 合并格拆任意 n×m（2×3 表合并 → splitInto 3,4 → 6 行）
  G3 #5 htable 上方空段 Backspace → 进表格渲染态（不落源码态）
  G4 #7 引用空行回车退出（不再产生 "> " 行）
  G5 #8 引用内代码块 qblk + codebar + 可编辑
  G6 #10 引用内图片 qblk + 点击不转源码
  G7 #17/#18 脚注定义空内容 data-ph + 脚注引用文末定义空内容
  G8 #20 术语定义光标进 dd + dd data-ph
判定按本文件 _m89.txt 的 FAIL 计数。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m89.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, ms=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(ms, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    try:
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(ms)


def raws():
    return jj("window.__raw()").get("raw") or []


def sel_in(sel, ms=280):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=400):
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


wait(2500)

# ============ G1 #1/#2 A→B→A toggle × 4 容器 ============
CASES = [
    ("标题1", "# 演示标题内容文字", "#editor .blk h1", "# "),
    ("列表", "- 第一项内容文本", "#editor .blk li", "- "),
    ("引用", "> 引用块内的文字内容", "#editor .blk blockquote", "> "),
    ("段落", "段落内容文字示例", "#editor .blk p", ""),
]
SEQS = [
    # 前 3 步全部真实应用（第 3 步 toggle 掉 A）；末步（_want）只记录期望不应用
    ("B→S→B", [("bold", ""), ("strike", ""), ("bold", ""), ("noop_want", "~~{C}~~")]),
    ("S→MK→S", [("strike", ""), ("mark", ""), ("strike", ""), ("noop_want", "=={C}==")]),
    ("B→I→B 回归", [("bold", ""), ("italic", ""), ("bold", ""), ("noop_want", "*{C}*")]),
    ("I→B→I 回归", [("italic", ""), ("bold", ""), ("italic", ""), ("noop_want", "**{C}**")]),
]
for cname, md, sel, pre in CASES:
    note("========== G1 %s ==========" % cname)
    plain = md[len(pre):] if pre else md
    for sname, steps in SEQS:
        setmd(md)
        got = ""
        want = ""
        ok = True
        detail = []
        for act, want_tpl in steps:
            final = act.endswith("_want")
            act = act.replace("_want", "")
            if not final:
                sel_in(sel)
                fmt(act)
                got = (raws() or [""])[0]
            want = (want_tpl.replace("{C}", plain))
        body = got[len(pre):] if pre and got.startswith(pre) else got
        check("G1 %s %s → %s" % (cname, sname, want), body == want,
              "got=%r want=%r" % (body, want))

# ============ G2 #3 合并格拆任意 n×m ============
note("========== G2 #3 ==========")
setmd("| a | b | c |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |")
wait(300)
# 用测试接口精确圈选正文 2×3（r1~r2 / c0~c2），避免鼠标拖选落点误差
r = js("window.__tblSelSet(0, 1, 0, 2, 2)")
wait(200)
js("window.__tblOp('merge')")
wait(300)
r = js("window.__tblOp('splitInto', [3, 4])")
wait(400)
r3 = (raws() or [""])[0]
import re as _re
n_rows = len(_re.findall(r"<tr[ >]", r3))
n_cells = len(_re.findall(r"<t[dh][ >]", r3))   # <thead> 不计入（<th 后必须跟空格或 >）
no_span = 'colspan="2"' not in r3 and 'colspan="3"' not in r3 and \
          'rowspan="2"' not in r3 and 'rowspan="3"' not in r3
check("G2 合并格拆 3×4 → 4 行(1表头+3体) × 4 列、无大跨度格",
      n_rows == 4 and n_cells == 16 and no_span and "1 2 3 4 5 6" in r3,
      "rows=%d cells=%d span_ok=%s raw=%s" % (n_rows, n_cells, no_span, r3[:120]))

# ============ G3 #5 htable 上方空段 Backspace ============
note("========== G3 #5 ==========")
setmd('<table><thead><tr><th>a</th><th>b</th></tr></thead>'
      '<tbody><tr><td>1</td><td>2</td></tr></tbody></table>\n\n尾段')
wait(400)
r = js("""(function(){
  var blks = document.querySelectorAll('#editor .blk');
  var tidx = -1;
  for (var k = 0; k < blks.length; k++) { if (blks[k].querySelector('table')) { tidx = k; break; } }
  if (tidx < 0 || !blks[tidx + 1]) return 'NOBLK';
  /* 进入表格下方空段编辑态，再按 Backspace */
  blks[tidx + 1].click();
  return 'ok';
})()""")
wait(300)
r = js("""(function(){
  var el = document.querySelector('#editor .raw-edit');
  if (!el) return 'no-edit';
  var ev = new KeyboardEvent('keydown', {key: 'Backspace', bubbles: true, cancelable: true});
  el.dispatchEvent(ev);
  return 'sent';
})()""")
wait(400)
d5 = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit'),"
        "tblSel:!!(window.__tblSel && window.__tblSel())})})()")
check("G3 htable 下方 Backspace → 进表格渲染态（无源码层）",
      d5.get("edit") is False, json.dumps(d5))

# ============ G4 #7 引用空行回车退出 ============
note("========== G4 #7 ==========")
setmd("> ")
wait(300)
r = js("""(function(){
  var bq = document.querySelector('#editor blockquote');
  if (!bq) return 'NOBQ';
  bq.focus();
  var rg = document.createRange(); rg.selectNodeContents(bq); rg.collapse(false);
  var s = getSelection(); s.removeAllRanges(); s.addRange(rg);
  return 'ok';
})()""")
wait(200)
js("""(function(){
  var bq = document.querySelector('#editor blockquote');
  bq.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
  return 'ok';
})()""")
wait(400)
rr = raws()
check("G4 空引用行回车退出（raw 无 > 前缀行）",
      all(not l.strip().startswith(">") for l in rr), json.dumps(rr, ensure_ascii=False))

# ============ G5 #8 引用内代码块 ============
note("========== G5 #8 ==========")
setmd("> 前\n> ```C\n> int x;\n> ```")
wait(500)
d8 = jj("""(function(){
  var qb = document.querySelector('#editor blockquote .qblk');
  if (!qb) return '{"qblk":false}';
  var pre = qb.querySelector('pre.fence');
  var code = pre && pre.querySelector('code');
  var bar = qb.querySelector('.codebar');
  return JSON.stringify({qblk:true, pre:!!pre, ce: code ? code.getAttribute('contenteditable') : null, bar:!!bar});
})()""")
check("G5 引用内代码块 qblk + codebar + 可编辑",
      d8.get("pre") and d8.get("bar") and d8.get("ce") == "plaintext-only", json.dumps(d8))
# 编辑回写：改代码内容 → blur → 引用块 raw 更新
js("""(function(){
  var code = document.querySelector('#editor blockquote .qblk code');
  if (!code) return 'no-code';
  code.textContent = 'int y;';
  code.dispatchEvent(new Event('input'));
  code.dispatchEvent(new Event('blur'));
  return 'ok';
})()""")
wait(400)
rr = raws()
check("G5b 引用内代码编辑回写引用行",
      any("int y;" in l for l in rr) and any(l.startswith("> ") for l in rr),
      json.dumps(rr, ensure_ascii=False))

# ============ G6 #10 引用内图片 ============
note("========== G6 #10 ==========")
setmd("> ![图](assets/a.png)")
wait(500)
d10 = jj("""(function(){
  var qb = document.querySelector('#editor blockquote .qblk');
  var img = document.querySelector('#editor blockquote img');
  if (!img) return '{"noimg":true}';
  img.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  return JSON.stringify({qblk:!!qb, rawEdit:!!document.querySelector('#editor .raw-edit')});
})()""")
check("G6 引用内图片 qblk 渲染 + 点击不转源码",
      d10.get("qblk") is True and d10.get("rawEdit") is False, json.dumps(d10))

# ============ G7 #17/#18/#19 脚注定义 ============
note("========== G7 #17-#19 ==========")
setmd("")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('refs', 1)")
wait(600)
rr = raws()
has_fd = any(x.startswith("[^1]:") and x[5:].strip() == "" for x in rr)
fe = js("(function(){var f=document.querySelector('#editor .fnedit');"
        "return f ? JSON.stringify({ph:f.getAttribute('data-ph'),ce:f.getAttribute('contenteditable')}) : 'none'; })()")
try:
    dfe = json.loads(fe) if fe and fe.startswith("{") else {}
except Exception:
    dfe = {}
check("G7 脚注定义（refs 子项）：动态编号空内容 + data-ph + 渲染态可编辑",
      has_fd and dfe.get("ph") == "脚注说明" and dfe.get("ce") == "plaintext-only",
      "%s | %s" % (json.dumps(rr, ensure_ascii=False), fe))

setmd("正文段落", ms=800)
wait(400)
js("(function(){if(document.activeElement&&document.activeElement.blur)document.activeElement.blur();return 'ok'})()")
wait(200)
rr0 = raws()
check("G7b-0 setmd 复位干净（诊断）", rr0 == ["正文段落"], json.dumps(rr0, ensure_ascii=False))
js("""(function(){
  var p = document.querySelector('#editor .blk p');
  p.focus();
  var rg = document.createRange(); rg.selectNodeContents(p); rg.collapse(false);
  var s = getSelection(); s.removeAllRanges(); s.addRange(rg);
  return 'ok';
})()""")
wait(200)
js("window.cmd('footnote')")
wait(600)
rr = raws()
check("G7b 脚注引用 → 文末定义为空内容（无「脚注说明」文字）",
      any(x == "[^1]:" or x == "[^1]: " for x in rr) and
      not any("脚注说明" in x for x in rr), json.dumps(rr, ensure_ascii=False))

# ============ G8 #20 术语定义 ============
note("========== G8 #20 ==========")
setmd("")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('refs', 2)")
wait(600)
rr = raws()
d20 = jj("""(function(){
  var dd = document.querySelector('#editor dd[data-ph]');
  var act = document.activeElement;
  return JSON.stringify({ddPh: dd ? dd.getAttribute('data-ph') : null,
                         focusDD: !!(act && act.tagName === 'DD')});
})()""")
check("G8 术语定义插入：光标进 dd + 空定义 data-ph",
      "术语\n: " in rr and d20.get("focusDD") and d20.get("ddPh") == "定义内容",
      "%s | %s" % (json.dumps(rr, ensure_ascii=False), json.dumps(d20)))

note("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
print("DONE TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
