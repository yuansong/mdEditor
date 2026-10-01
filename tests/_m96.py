# -*- coding: utf-8 -*-
"""m96: 标题选区行内格式化后的状态复现探针（用户报告：清除格式后进入源码编辑态）
S1 标题加粗态 clearfmt → raw 正确 且 保持渲染态（blk 非 raw-edit）
S2 标题纯文本 strike → raw 正确 且 保持渲染态
S3 标题复合态 clearfmt → raw 正确 且 保持渲染态
S4 对照：段落 clearfmt → raw 正确（段落无 focusWysiwyg 目标，验证不崩）
结果写 _m96.txt，PASS/FAIL 逐条判定。"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m96.txt")
LINES = []
N_PASS = [0]
N_FAIL = [0]


def log(s): LINES.append(str(s))


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if cond: N_PASS[0] += 1
    else: N_FAIL[0] += 1
    log(tag + " | " + name + (" | " + str(extra) if extra else ""))


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


def setmd(win, md, ms=700):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def sel_all(win):
    """选中第 0 块全部渲染文字（heading 渲染态 = h 标签内文本节点）"""
    js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT);
  var sn = null, en = null, n;
  while (n = w.nextNode()) { if (!sn) sn = n; en = n; }
  if (!sn) return 'no-text';
  var rg = document.createRange();
  rg.setStart(sn, 0); rg.setEnd(en, en.nodeValue.length);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(300)


def act(win, action, ms=500):
    js(win, "window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def raw0(win):
    return js(win, "window.getMarkdown()") or ""


STATE_JS = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return JSON.stringify({err:'no-blk'});
  var isRaw = blk.classList.contains('raw-edit');
  var h = blk.querySelector('h1,h2,h3,h4,h5,h6');
  var ae = document.activeElement;
  var aeInH = !!(ae && ae.closest && ae.closest('h1,h2,h3,h4,h5,h6'));
  return JSON.stringify({isRaw: isRaw, hasH: !!h, aeInH: aeInH, txt: h ? h.textContent : null});
})()"""


def state0(win):
    try:
        return json.loads(js(win, STATE_JS) or "{}")
    except Exception:
        return {}


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    # S1 标题加粗态 clearfmt
    setmd(win, "# **我的标题**")
    sel_all(win); act(win, "clearfmt")
    r = raw0(win); st = state0(win)
    ok_raw = r == "# 我的标题"
    ok_st = (not st.get("isRaw", True)) and st.get("hasH")
    check("S1 标题clearfmt raw", ok_raw, repr(r))
    check("S1 标题clearfmt 保持渲染态", ok_st, json.dumps(st, ensure_ascii=False))

    # S2 标题纯文本 strike
    setmd(win, "## 我的标题")
    sel_all(win); act(win, "strike")
    r = raw0(win); st = state0(win)
    ok_raw = r == "## ~~我的标题~~"
    ok_st = (not st.get("isRaw", True)) and st.get("hasH")
    check("S2 标题strike raw", ok_raw, repr(r))
    check("S2 标题strike 保持渲染态", ok_st, json.dumps(st, ensure_ascii=False))

    # S3 标题复合态 clearfmt
    setmd(win, "### **粗**和*斜*混合")
    sel_all(win); act(win, "clearfmt")
    r = raw0(win); st = state0(win)
    ok_raw = r == "### 粗和斜混合"
    ok_st = (not st.get("isRaw", True)) and st.get("hasH")
    check("S3 标题复合clearfmt raw", ok_raw, repr(r))
    check("S3 标题复合clearfmt 保持渲染态", ok_st, json.dumps(st, ensure_ascii=False))

    # S4 对照：段落 clearfmt（无 focusWysiwyg 目标，验证 raw 正确即可）
    setmd(win, "普通**加粗**文字")
    sel_all(win); act(win, "clearfmt")
    r = raw0(win)
    check("S4 段落clearfmt raw", r == "普通加粗文字", repr(r))

    # S5 富标题（渲染态）拖选全部 → strike（应在渲染态完成并回到渲染态）
    setmd(win, "# **已加粗**和普通")
    sel_all(win); act(win, "strike")
    r = raw0(win); st = state0(win)
    ok_raw = r == "# ~~**已加粗**和普通~~"
    ok_st = (not st.get("isRaw", True)) and st.get("hasH")
    check("S5 富标题strike raw", ok_raw, repr(r))
    check("S5 富标题strike 保持渲染态", ok_st, json.dumps(st, ensure_ascii=False))

    # S6 点击富标题（v3.36 WYS-3 起恒为渲染态，不再转源码态）→ 全选 → clearfmt
    #    清除后 raw 已无行内标记，仍为渲染态（用户报告场景）
    setmd(win, "# **已加粗**和普通")
    wait(300)
    js(win, """(function(){
  var h = document.querySelector('#editor h1, #editor h2, #editor h3');
  if (!h) return 'no-h';
  h.focus();
  var rg = document.createRange(); rg.selectNodeContents(h); rg.collapse(true);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  h.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  return 'ok';
})()""")
    wait(400)
    st_click = state0(win)
    # S6 点击富标题（v3.36 WYS-3 起不再转源码态，恒为渲染态）→ 全选 → clearfmt
    check("S6 点击富标题保持渲染态（v3.36 WYS-3：点击转源码态已退役）",
          st_click.get("isRaw") is False and st_click.get("hasH") is True,
          json.dumps(st_click, ensure_ascii=False))
    sel_all(win); act(win, "clearfmt")
    r = raw0(win); st = state0(win)
    ok_raw = r == "# 已加粗和普通"
    ok_st = (not st.get("isRaw", True)) and st.get("hasH")
    check("S6 clearfmt raw", ok_raw, repr(r))
    check("S6 clearfmt 回渲染态", ok_st, json.dumps(st, ensure_ascii=False))

    log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")


if __name__ == "__main__":
    main()
