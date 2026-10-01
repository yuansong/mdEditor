# -*- coding: utf-8 -*-
"""m101: v3.36 悬浮命令栏 + 行内格式渲染（需求 #1 / #2 / #3）。

#1 标题选区尾部文案「已选标题 N，已选 M 字」
#2 悬浮栏：斜体后新增「下划线」，全局移除「插入模板」
#3 含行内格式的标题 / 列表 / 引用 / 定义列表 → 单击不再转源码态（始终渲染态），
   且渲染态原地编辑时行内格式不丢（DOM → Markdown 序列化回写）

结果写 _m101.txt，PASS/FAIL 逐条判定。
"""
import json
import os
import sys
import time

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m101.txt")
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


def setmd(win, md, ms=700):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raw0(win):
    """第 0 块 raw。"""
    try:
        return json.loads(js(win, "window.__raw()") or "{}").get("raw", [""])[0]
    except Exception:
        return ""


def jj(win, code):
    try:
        return json.loads(js(win, code) or "{}")
    except Exception:
        return {}


SEL_ALL = """(function(){
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
})()"""

FB_JS = """(function(){
  var f = document.getElementById('floatbar');
  var btns = [];
  var bs = f.querySelectorAll('button');
  for (var i = 0; i < bs.length; i++) btns.push(bs[i].title);
  var c = f.querySelector('.fbcnt');
  return JSON.stringify({ show: f.classList.contains('show'), btns: btns,
                          cnt: c ? c.textContent : '' });
})()"""

STATE_JS = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return JSON.stringify({err:'no-blk'});
  var isRaw = blk.classList.contains('raw-edit');
  var h = blk.querySelector('h1,h2,h3,h4,h5,h6');
  var li = blk.querySelector('li');
  var bq = blk.querySelector('blockquote');
  var dd = blk.querySelector('dd');
  /* v3.36 探针修正：普通段落块没有 h/li/bq/dd 宿主，退到首个 contenteditable，
     再退回 .blk 自身（此时 innerHTML 即段落渲染产物） */
  var host = h || li || bq || dd || blk.querySelector('[contenteditable]') || blk;
  return JSON.stringify({ isRaw: isRaw, host: host.tagName,
    isBlk: host === blk,
    html: host.innerHTML,
    txt: host.textContent });
})()"""


def state0(win):
    return jj(win, STATE_JS)


def act(win, action, ms=500):
    js(win, "window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def click_rendered(win, sel="h1,h2,h3", pick="h"):
    """在渲染态元素内落光标并派发 click（模拟「移开光标再移回后单击」）。"""
    code = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var t = blk.querySelector('%s');
  if (!t) return 'no-host';
  t.focus();
  var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(true);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  t.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, button: 0}));
  t.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, button: 0}));
  t.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, button: 0}));
  return 'ok';
})()""" % sel
    r = js(win, code)
    wait(350)
    return r


def type_at_end(win, sel, text="X"):
    """聚焦元素、光标置末尾、execCommand 输入（触发 input → 渲染态回写）。"""
    code = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var t = blk.querySelector('%s');
  if (!t) return 'no-host';
  t.focus();
  var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(false);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.execCommand('insertText', false, %s);
  return t.textContent;
})()""" % (sel, json.dumps(text))
    r = js(win, code)
    wait(300)
    return r


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ==================== #1 尾部文案 ====================
    log("---------- #1 悬浮栏尾部文案 ----------")
    setmd(win, "# 我的标题")
    js(win, SEL_ALL)
    wait(400)
    fb = jj(win, FB_JS)
    check("#1a 标题选区：标题 1，已选 4 字（v3.37 文案微调）",
          fb.get("cnt") == "标题 1，已选 4 字", repr(fb.get("cnt")))

    setmd(win, "## 二级标题")
    js(win, SEL_ALL)
    wait(400)
    fb = jj(win, FB_JS)
    check("#1b h2 同样计数", fb.get("cnt") == "标题 1，已选 4 字", repr(fb.get("cnt")))

    setmd(win, "普通段落文字")
    js(win, SEL_ALL)
    wait(400)
    fb = jj(win, FB_JS)
    check("#1c 段落无标题前缀", fb.get("cnt") == "已选 6 字", repr(fb.get("cnt")))

    # ==================== #2 按钮序列 ====================
    log("---------- #2 悬浮栏按钮 ----------")
    want = ["粗体", "斜体", "下划线", "删除线", "高亮", "行内代码", "链接", "清除格式"]
    check("#2a 段落按钮序列（斜体后为下划线）", fb.get("btns") == want, json.dumps(fb.get("btns"), ensure_ascii=False))
    check("#2b 全局无「插入模板」",
          not any((b or "").startswith("插入模板") for b in fb.get("btns") or []),
          json.dumps(fb.get("btns"), ensure_ascii=False))

    setmd(win, "# 标题按钮")
    js(win, SEL_ALL)
    wait(400)
    fb = jj(win, FB_JS)
    check("#2c 标题栏：下划线在下 + 居中按钮 + 无插入模板",
          fb.get("btns") == ["粗体", "斜体", "下划线", "删除线", "高亮", "行内代码", "链接",
                             "标题居中", "清除格式"],
          json.dumps(fb.get("btns"), ensure_ascii=False))

    # ==================== #2 下划线功能 ====================
    log("---------- #2 下划线 ----------")
    setmd(win, "普通文字测试")
    js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT);
  var n = w.nextNode();               /* 「普通文字测试」一个文本节点 */
  var rg = document.createRange(); rg.setStart(n, 2); rg.setEnd(n, 4);   /* 「文字」 */
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(400)
    act(win, "underline")
    r = raw0(win)
    st = state0(win)
    check("#2d 下划线包裹 raw", r == "普通<u>文字</u>测试", repr(r))
    check("#2e 下划线后保持渲染态（有 <u> 标签）",
          (not st.get("isRaw")) and "<u>" in (st.get("html") or ""), json.dumps(st, ensure_ascii=False))

    # 二次应用 = 取消
    js(win, SEL_ALL)
    js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var u = blk.querySelector('u');
  if (!u) return 'no-u';
  var rg = document.createRange(); rg.selectNodeContents(u);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(400)
    act(win, "underline")
    r = raw0(win)
    check("#2f 下划线二次应用 = 取消", r == "普通文字测试", repr(r))

    # 下划线 + 加粗叠加
    setmd(win, "叠加测试")
    js(win, SEL_ALL)
    wait(350)
    act(win, "underline")
    js(win, SEL_ALL)
    wait(350)
    act(win, "bold")
    r = raw0(win)
    check("#2g 下划线 + 加粗叠加", sorted([r.count("<u>"), r.count("**")]) == [1, 2] and "叠加测试" in r, repr(r))

    # 清除格式连标签一起清
    js(win, SEL_ALL)
    wait(300)
    act(win, "clearfmt")
    r = raw0(win)
    check("#2h 清除格式带走 <u>", r == "叠加测试", repr(r))

    # 标题内下划线 + 大纲纯文本
    setmd(win, "# 标题下划线")
    js(win, SEL_ALL)
    wait(350)
    act(win, "underline")
    r = raw0(win)
    st = state0(win)
    check("#2i 标题内下划线 raw", r == "# <u>标题下划线</u>", repr(r))
    out = jj(win, "JSON.stringify(window.getOutline())")
    check("#2j 大纲只显示纯文本（无 <u> 标记）",
          json.dumps(out, ensure_ascii=False).count("<u>") == 0 and
          any("标题下划线" in json.dumps(x, ensure_ascii=False) for x in (out or [])),
          json.dumps(out, ensure_ascii=False)[:160])

    # ==================== #3 渲染态点击（原缺陷） ====================
    log("---------- #3 富标题 / 富列表单击保持渲染态 ----------")

    # D1 标题加粗 → 光标移开 → 移回单击
    setmd(win, "# 我的标题")
    js(win, SEL_ALL)
    wait(350)
    act(win, "bold")
    r1 = raw0(win)
    st = state0(win)
    check("#3a 标题加粗 raw", r1 == "# **我的标题**", repr(r1))
    check("#3b 加粗后仍在渲染态", (not st.get("isRaw")) and "<strong>" in (st.get("html") or ""),
          json.dumps(st, ensure_ascii=False))

    # 移开光标：点空白 / 另一块
    setmd(win, "# **已加粗**和普通\n\n第二段")
    js(win, """(function(){
  var ps = document.querySelectorAll('#editor .blk');
  if (ps.length < 2) return 'no-2nd';
  var t = ps[1];
  t.focus();
  var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(true);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  return 'ok';
})()""")
    wait(300)
    click_rendered(win)
    st = state0(win)
    check("#3c 单击富标题：不再转源码态", st.get("isRaw") is False, json.dumps(st, ensure_ascii=False))
    check("#3d 富标题渲染仍在（<strong>）", "<strong>" in (st.get("html") or ""),
          json.dumps(st, ensure_ascii=False))

    # D2 渲染态原地输入：行内格式不丢
    type_at_end(win, "h1", "新增")
    r = raw0(win)
    check("#3e 富标题原地输入保留加粗标记",
          r == "# **已加粗**和普通新增", repr(r))

    # D3 h2 + 斜体
    setmd(win, "## 斜体标题")
    js(win, SEL_ALL)
    wait(350)
    act(win, "italic")
    r = raw0(win)
    click_rendered(win)
    st = state0(win)
    check("#3f h2 斜体 raw", r == "## *斜体标题*", repr(r))
    check("#3g h2 斜体单击保持渲染态", st.get("isRaw") is False, json.dumps(st, ensure_ascii=False))

    # D4 列表项
    setmd(win, "- **加粗项**尾巴")
    click_rendered(win, "li", "li")
    st = state0(win)
    check("#3h 富列表项单击保持渲染态", st.get("isRaw") is False, json.dumps(st, ensure_ascii=False))
    type_at_end(win, "li", "!")
    r = raw0(win)
    check("#3i 富列表项原地输入保留加粗标记", r == "- **加粗项**尾巴!", repr(r))

    # D5 引用块
    setmd(win, "> **加粗**引用")
    click_rendered(win, "blockquote", "bq")
    st = state0(win)
    check("#3j 富引用单击保持渲染态", st.get("isRaw") is False, json.dumps(st, ensure_ascii=False))
    type_at_end(win, "blockquote", "尾")
    r = raw0(win)
    check("#3k 富引用原地输入保留加粗标记", r == "> **加粗**引用尾", repr(r))

    # D6 定义列表
    setmd(win, "术语\n: **定义**内容")
    click_rendered(win, "dd", "dd")
    st = state0(win)
    check("#3l 富定义列表单击保持渲染态", st.get("isRaw") is False, json.dumps(st, ensure_ascii=False))
    type_at_end(win, "dd", "尾")
    r = raw0(win)
    check("#3m 富定义列表原地输入保留加粗标记", r == "术语\n: **定义**内容尾", repr(r))

    # D7 行内码 / 链接混合
    setmd(win, "# 标题含`码`和[链](https://a.b)接")
    click_rendered(win)
    st = state0(win)
    check("#3n 码 + 链接混合标题单击保持渲染态", st.get("isRaw") is False,
          json.dumps(st, ensure_ascii=False))
    type_at_end(win, "h1", "尾")
    r = raw0(win)
    check("#3o 混合标题原地输入保留 ` 与链接",
          r == "# 标题含`码`和[链](https://a.b)接尾", repr(r))

    # ==================== 其它同类格式操作渲染表现 ====================
    log("---------- 其它格式操作回归 ----------")
    setmd(win, "# 连续格式")
    js(win, SEL_ALL)
    wait(350)
    act(win, "bold")
    js(win, SEL_ALL)
    wait(300)
    act(win, "italic")
    r = raw0(win)
    st = state0(win)
    check("#4a 标题连套加粗 + 斜体", r == "# ***连续格式***" and (not st.get("isRaw")), repr(r))

    setmd(win, "- 列表**加粗**")
    js(win, SEL_ALL)
    wait(350)
    act(win, "mark")
    r = raw0(win)
    check("#4b 列表高亮（行内映射未错位）", r == "- ==列表**加粗**==", repr(r))

    setmd(win, "> 引用**加粗**")
    js(win, SEL_ALL)
    wait(350)
    act(win, "strike")
    r = raw0(win)
    check("#4c 引用删除线（行内映射未错位）", r == "> ~~引用**加粗**~~", repr(r))

    setmd(win, "| A | B |\n| - | - |\n| 甲 | 乙 |")
    js(win, """(function(){
  var c = document.querySelector('#editor .b-table td');
  if (!c) return 'no-cell';
  c.focus();
  var rg = document.createRange(); rg.selectNodeContents(c);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(400)
    act(win, "bold")
    full = js(win, "window.getMarkdown()") or ""
    r4 = raw0(win)
    # v3.36 探针修正：管道表加粗可能落成原生 MD（**甲**）或 HTML（<strong>甲</strong>），
    # 二者都是合法存储（「能原生 MD 就原生」），只要求「加粗生效」且「表格不丢行」
    bolded = ("<strong>甲</strong>" in full) or ("**甲**" in full) or ("<strong>甲</strong>" in r4) or ("**甲**" in r4)
    rows_ok = ("甲" in full) and ("乙" in full) and ("A" in full)
    check("#4d 表格单元格加粗生效且不丢行", bolded and rows_ok,
          "full=" + repr(full[:200]) + " raw0=" + repr(r4[:200]))

    log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    flush()
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log("EXCEPTION " + traceback.format_exc())
        log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
        flush()
        raise
