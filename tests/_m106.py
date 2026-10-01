# -*- coding: utf-8 -*-
"""m106：v3.37（FMT-11）标签壳外推根修回归
缺陷：列表 / 段落里连点行内格式按钮，出现 **==asfdsafdafd==** 乃至
      <u>asfdsafdafd</u> 这类**字面标记外露**（raw 的标记被插到标签内侧，
      同一 marker 出现 4 段游程，行内解析按顺序配对 → 标签当正文显示）。
根因：wrapSelection 的「外壳外推」只认同字符游程，遇 < / > 直接停 →
      外层 marker 被判「未包裹」→ 再包一层 → 游程与标签交错。

断言（列表 / 段落 双容器）：
  F1 六条叠加序列每一步都不出现字面标记外露（渲染层文本无 ** == ~~ <u>）
  F2 raw 无畸形标记结构（游程被标签劈开 / 同字符游程>=4 / 标签不配对）
  F3 LIFO 弹出语义：**<u>x</u>** 再按加粗 → <u>x</u>
  F4 **==<u>x</u>==** 再按高亮 → **<u>x</u>**
  F5 **==*~~<u>x</u>~~*==** 再按加粗 → ==*~~<u>x</u>~~*==
  F6 单格式连点 4 次在 加/取消 间往复
  F7 叠加后在末尾打字不产生畸形标记
  F8 T× 一次清除叠加格式
  F9 单元格内下划线（FMT-12）：生效 / 二次点击取消 / T× 连标签清除
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m106.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:300]))

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
    wait(400)

def md0(win):
    return js(win, "window.getMarkdown()") or ""

SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var host = blk.querySelector('[contenteditable]') || blk;
  var rg = document.createRange(); rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()"""

STATE = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  var txt = blk.textContent || '';
  return JSON.stringify({raw: raw, txt: txt, isRaw: blk.classList.contains('raw-edit'),
    html: blk.innerHTML});
})()"""

LEAK = ("**", "==", "~~", "<u>", "</u>")

import re as _re
_TAGS = ("u", "ins", "mark", "strong", "em", "del", "s", "sub", "sup")
_MAL = [
    # 同 marker 游程被标签劈开（本缺陷签名：**<u>**x**</u>**）
    _re.compile(r"([*~=])\1*<(%s)>\1" % "|".join(_TAGS)),
    _re.compile(r"([*~=])\1*</(%s)>\1" % "|".join(_TAGS)),
    # 同字符游程 >= 4
    _re.compile(r"\*{4,}|~{4,}|={4,}"),
]


def _malf(raw):
    """返回 raw 里的畸形标记签名（列表），空列表即结构正常。
    只查「结构性畸形」，不查相邻性 —— `<u>==**x**==</u>` 这类正常嵌套
    里 `<u>==` 是合法相邻，旧版子串黑名单会误报。"""
    errs = []
    for rx in _MAL:
        m = rx.search(raw)
        if m:
            errs.append(rx.pattern[:24] + " 命中 " + repr(m.group(0)))
    if raw.count("<u>") != raw.count("</u>"):
        errs.append("<u>/</u> 数量不等")
    if raw.count("<ins>") != raw.count("</ins>"):
        errs.append("<ins>/</ins> 数量不等")
    return errs
SEQS = [
    ("粗→斜→高→删→下", ["bold", "italic", "mark", "strike", "underline"]),
    ("下→高→粗→斜", ["underline", "mark", "bold", "italic"]),
    ("粗→高→下→高→粗", ["bold", "mark", "underline", "mark", "bold"]),
    ("粗→下→粗→下", ["bold", "underline", "bold", "underline"]),
    ("高→粗…交替 6 次", ["mark", "bold", "mark", "bold", "mark", "bold"]),
    ("粗→高→斜→删→下→粗", ["bold", "mark", "italic", "strike", "underline", "bold"]),
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

    # ---------- F1/F2 六条序列 × 双容器 ----------
    log("---------- F1/F2 叠加序列（列表 / 段落） ----------")
    for name, acts in SEQS:
        for host_md, tag in [("- asfdsafdafd", "列表"), ("asfdsafdafd", "段落")]:
            setmd(win, host_md)
            leaks, bads = [], []
            for a in [None] + acts:
                if a:
                    js(win, SEL_JS)
                    js(win, "window.__applyFloat(%s)" % json.dumps(a))
                    wait(400)
                d = json.loads(js(win, STATE) or "{}")
                raw = d.get("raw") or ""
                txt = d.get("txt") or ""
                if any(m in txt for m in LEAK) or d.get("isRaw"):
                    leaks.append("%s→raw=%s" % (a, raw))
                if _malf(raw):
                    bads.append("%s→raw=%s【%s】" % (a, raw, " / ".join(_malf(raw))))
            check("F1[%s/%s] 全程无字面标记外露" % (tag, name), not leaks, " ; ".join(leaks))
            check("F2[%s/%s] raw 无畸形标记对" % (tag, name), not bads, " ; ".join(bads))

    # ---------- F3/F4/F5 LIFO 弹出 ----------
    log("---------- F3~F5 LIFO 弹出语义 ----------")
    for label, setup, act, expect in [
        ("F3 **<u>x</u>** + 加粗 → <u>x</u>",
         ["bold", "underline"], "bold", "- <u>asfdsafdafd</u>"),
        ("F4 **==<u>x</u>==** + 高亮 → **<u>x</u>**",
         ["bold", "mark", "underline"], "mark", "- **<u>asfdsafdafd</u>**"),
        ("F5 **==*~~<u>x</u>~~*==** + 加粗 → ==*~~<u>x</u>~~*==",
         ["bold", "mark", "italic", "strike", "underline"], "bold",
         "- ==*~~<u>asfdsafdafd</u>~~*=="),
    ]:
        setmd(win, "- asfdsafdafd")
        for a in setup:
            js(win, SEL_JS); js(win, "window.__applyFloat(%s)" % json.dumps(a)); wait(400)
        js(win, SEL_JS); js(win, "window.__applyFloat(%s)" % json.dumps(act)); wait(450)
        got = md0(win)
        check(label, got.strip() == expect, "got=%s expect=%s" % (json.dumps(got), json.dumps(expect)))

    # ---------- F6 单格式连点往复 ----------
    log("---------- F6 单格式 toggle 往复 ----------")
    for label, act, on, off in [
        ("F6a 加粗", "bold", "- **asfdsafdafd**", "- asfdsafdafd"),
        ("F6b 高亮", "mark", "- ==asfdsafdafd==", "- asfdsafdafd"),
        ("F6c 下划线", "underline", "- <u>asfdsafdafd</u>", "- asfdsafdafd"),
    ]:
        setmd(win, "- asfdsafdafd")
        seq = []
        for _ in range(4):
            js(win, SEL_JS); js(win, "window.__applyFloat(%s)" % json.dumps(act)); wait(400)
            seq.append((md0(win) or "").strip())
        check(label + " 连点 4 次在 加/取消 间往复且不累加",
              seq == [on, off, on, off], json.dumps(seq, ensure_ascii=False))

    # ---------- F7 叠加后打字 ----------
    log("---------- F7 叠加后渲染态打字 ----------")
    setmd(win, "- asfdsafdafd")
    for a in ["bold", "mark", "underline"]:
        js(win, SEL_JS); js(win, "window.__applyFloat(%s)" % json.dumps(a)); wait(400)
    js(win, """(function(){
      var t = document.querySelector('#editor .blk [contenteditable]');
      if (!t) return 'no-host';
      t.focus();
      var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(false);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
      document.execCommand('insertText', false, 'XY');
      return t.textContent;
    })()""")
    wait(500)
    d = json.loads(js(win, STATE) or "{}")
    raw = d.get("raw") or ""
    check("F7 叠加后打字无畸形标记且在渲染态",
          d.get("isRaw") is False and "XY" in raw and "asfdsafdafd" in raw
          and not _malf(raw),
          json.dumps({"raw": raw, "isRaw": d.get("isRaw")}, ensure_ascii=False))

    # ---------- F8 T× 清除 ----------
    log("---------- F8 清除格式 ----------")
    setmd(win, "- asfdsafdafd")
    for a in ["bold", "mark", "underline"]:
        js(win, SEL_JS); js(win, "window.__applyFloat(%s)" % json.dumps(a)); wait(400)
    before = md0(win)
    js(win, SEL_JS); js(win, "window.__applyFloat('clearfmt')"); wait(500)
    after = md0(win)
    check("F8 T× 一次清除三重叠加回裸文本",
          after.strip() == "- asfdsafdafd",
          json.dumps({"before": before, "after": after}, ensure_ascii=False))

    # ---------- F9 单元格内下划线（FMT-12） ----------
    log("---------- F9 单元格内下划线 ----------")
    CELL_SEL = """(function(){
  var c = document.querySelector('#editor .b-table td');
  if (!c) return 'no-cell';
  c.focus();
  var rg = document.createRange(); rg.selectNodeContents(c);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()"""
    TBL = "| A | B |\n| - | - |\n| 甲 | 乙 |"
    setmd(win, TBL)
    js(win, CELL_SEL); wait(400)
    js(win, "window.__applyFloat('underline')"); wait(450)
    r1 = md0(win)
    check("F9a 单元格内下划线生效（<u> 落进该格）",
          "<u>甲</u>" in r1 and "乙" in r1, json.dumps(r1, ensure_ascii=False))
    js(win, CELL_SEL); wait(400)
    js(win, "window.__applyFloat('underline')"); wait(450)
    r2 = md0(win)
    check("F9b 单元格内下划线二次点击取消（toggle）",
          "<u>" not in r2 and "甲" in r2 and "乙" in r2, json.dumps(r2, ensure_ascii=False))
    js(win, CELL_SEL); wait(400)
    js(win, "window.__applyFloat('underline')"); wait(450)
    js(win, CELL_SEL); wait(400)
    js(win, "window.__applyFloat('clearfmt')"); wait(500)
    r3 = md0(win)
    check("F9c 单元格内 T× 连标签一并清除",
          "<u>" not in r3 and "</u>" not in r3 and "甲" in r3, json.dumps(r3, ensure_ascii=False))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    npass = sum(1 for x in LINES if x.startswith("PASS"))
    nfail = sum(1 for x in LINES if x.startswith("FAIL"))
    print("PASS=%d FAIL=%d" % (npass, nfail))
    for x in LINES:
        if x.startswith("FAIL"):
            print(x)


if __name__ == "__main__":
    main()
